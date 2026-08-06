from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from survey.scripts.audit_repositories import (
    ARTIFACT_INVENTORY_FIELDS,
    REPOSITORY_AUDIT_FIELDS,
    audit_repository,
    build_artifact_inventory,
    normalize_github_url,
    repository_source_closure,
    validate_artifact_inventory,
    validate_repository_audit,
)
from survey.scripts.enrich_metadata import (
    cached_request,
    licence_state,
    retrieval_failure_code,
)


ROOT = Path(__file__).resolve().parents[1]
DEEP_REVIEW = ROOT / "survey/build/deep_review.csv"
RECORDS = ROOT / "survey/build/records_normalized.csv"
AUDIT_SCRIPT = ROOT / "survey/scripts/audit_repositories.py"


def _write_cache_entry(
    cache_root: Path,
    *,
    service: str,
    identifier: str,
    url: str,
    body: bytes,
    status: int = 200,
) -> dict[str, object]:
    digest = hashlib.sha256(body).hexdigest()
    relative = Path("responses") / service / f"{digest}.json"
    target = cache_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    entry: dict[str, object] = {
        "service": service,
        "identifier": identifier,
        "request_url": url,
        "raw_response_path": relative.as_posix(),
        "http_status": status,
        "retrieved_at_utc": "2026-08-06T10:00:00+00:00",
        "response_sha256": digest,
        "error_body_sha256": "" if status < 400 else digest,
    }
    index = {"schema_version": 1, "entries": [entry]}
    (cache_root / "index.json").write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return entry


class CacheAndNormalizationTests(unittest.TestCase):
    def test_audit_script_is_directly_executable_from_the_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_cached_request_reuses_only_a_hash_verified_raw_response(self) -> None:
        body = b'{"full_name":"Owner/Repo"}'
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_cache_entry(
                root,
                service="github",
                identifier="owner/repo:repository",
                url="https://api.github.com/repos/Owner/Repo",
                body=body,
            )
            with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                entry = cached_request(
                    "github",
                    "owner/repo:repository",
                    "https://api.github.com/repos/Owner/Repo",
                )
                self.assertTrue(entry.from_cache)
                self.assertEqual(entry.body, body)
                self.assertEqual(entry.response_sha256, hashlib.sha256(body).hexdigest())

                (root / entry.raw_response_path).write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    cached_request(
                        "github",
                        "owner/repo:repository",
                        "https://api.github.com/repos/Owner/Repo",
                    )

    def test_github_repository_aliases_normalize_and_malformed_urls_fail_closed(self) -> None:
        expected = "https://github.com/Owner/Repo"
        aliases = (
            "https://github.com/Owner/Repo/",
            "https://www.github.com/Owner/Repo.git",
            "git@github.com:Owner/Repo.git",
            "https://github.com/Owner/Repo/tree/main/examples",
        )
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertEqual(normalize_github_url(alias), expected)

        for invalid in (
            "https://gitlab.com/Owner/Repo",
            "https://github.com/Owner",
            "https://github.com/Owner/Repo?access_token=secret",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_github_url(invalid)

    def test_licence_states_distinguish_detected_none_and_unavailable(self) -> None:
        self.assertEqual(licence_state(200, 200, "MIT"), "detected")
        self.assertEqual(licence_state(200, 404, ""), "none_detected")
        for repository_status, licence_status in ((404, 0), (429, 0), (200, 429)):
            with self.subTest(
                repository_status=repository_status, licence_status=licence_status
            ):
                self.assertEqual(
                    licence_state(repository_status, licence_status, ""), "unavailable"
                )

    def test_retrieval_failures_have_controlled_codes(self) -> None:
        expected = {
            0: "REQUEST_ERROR",
            200: "NONE",
            403: "RATE_LIMITED_OR_FORBIDDEN",
            404: "NOT_FOUND",
            422: "INVALID_IDENTIFIER_OR_REF",
            429: "RATE_LIMITED_OR_FORBIDDEN",
            503: "SERVICE_ERROR",
        }
        for status, code in expected.items():
            with self.subTest(status=status):
                self.assertEqual(retrieval_failure_code(status), code)


class ArtifactInventoryTests(unittest.TestCase):
    def test_truncated_api_tree_is_incomplete_source_closure(self) -> None:
        state, failures = repository_source_closure(
            tree_status=200,
            tree_truncated=True,
            submodules=[],
            vendor_ip=[],
            omitted_markers=[],
        )
        self.assertEqual(state, "incomplete_indicators_observed")
        self.assertEqual(failures, ["TREE_TRUNCATED"])

    def test_inventory_retains_all_selected_rows_and_eight_external_repo_hypotheses(self) -> None:
        inventory = build_artifact_inventory(DEEP_REVIEW, RECORDS)

        self.assertEqual(len(inventory), 36)
        with DEEP_REVIEW.open(encoding="utf-8") as handle:
            selected_ids = {
                row["project_family_id"] for row in csv.DictReader(handle)
            }
        self.assertEqual(
            {row["project_family_id"] for row in inventory}, selected_ids
        )
        self.assertEqual(
            sum(row["artifact_kind"] == "github_repository" for row in inventory),
            9,
        )
        self.assertEqual(
            sum(
                row["artifact_kind"] == "github_repository"
                and row["project_family_id"] != "CONTROL-COMPILER-LAB"
                for row in inventory
            ),
            8,
        )
        self.assertEqual(
            sum(row["failure_code"] == "NO_PROJECT_ARTIFACT_REPORTED" for row in inventory),
            26,
        )
        self.assertTrue(
            all(
                row["licence_state"] in {"detected", "none_detected", "unavailable"}
                for row in inventory
            )
        )
        validate_artifact_inventory(inventory)

    def test_inventory_validation_requires_every_field_and_negative_failure_code(self) -> None:
        valid = {field: "observed" for field in ARTIFACT_INVENTORY_FIELDS}
        valid.update(
            {
                "project_family_id": "PF-0000000000000001",
                "artifact_claim_state": "not_reported",
                "artifact_kind": "none_reported",
                "paper_reported_url": "",
                "normalized_artifact_url": "",
                "licence_state": "unavailable",
                "licence_evidence": "No attributed artifact endpoint",
                "failure_code": "NO_PROJECT_ARTIFACT_REPORTED",
            }
        )
        validate_artifact_inventory([valid])

        for mutation in ("title", "failure_code"):
            with self.subTest(mutation=mutation):
                broken = dict(valid)
                broken[mutation] = ""
                with self.assertRaisesRegex(ValueError, mutation):
                    validate_artifact_inventory([broken])

    def test_malformed_repository_is_a_negative_audit_row_not_an_exception(self) -> None:
        row = audit_repository("https://github.com/only-owner", None)

        self.assertEqual(set(row), set(REPOSITORY_AUDIT_FIELDS))
        self.assertEqual(row["observed_status"], "malformed")
        self.assertEqual(row["licence_state"], "unavailable")
        self.assertEqual(row["failure_code"], "MALFORMED_REPOSITORY_URL")


class CommittedArtifactEvidenceTests(unittest.TestCase):
    def test_committed_task5_outputs_are_complete_deduplicated_and_secret_free(self) -> None:
        inventory_path = ROOT / "survey/build/artifact_inventory.csv"
        audit_path = ROOT / "survey/build/repository_audit.csv"
        log_path = ROOT / "survey/build/api_retrieval_log.csv"
        index_path = ROOT / "survey/build/api-cache/index.json"

        with inventory_path.open(encoding="utf-8") as handle:
            inventory = list(csv.DictReader(handle))
        with audit_path.open(encoding="utf-8") as handle:
            audits = list(csv.DictReader(handle))
        with log_path.open(encoding="utf-8") as handle:
            retrievals = list(csv.DictReader(handle))
        index = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(len(inventory), 36)
        self.assertEqual(len(audits), 9)
        self.assertGreaterEqual(len(retrievals), 9 * 5)
        validate_artifact_inventory(inventory)
        validate_repository_audit(audits)

        normalized = [row["normalized_repository_url"].lower() for row in audits]
        self.assertEqual(len(normalized), len(set(normalized)))
        self.assertTrue(all(row["licence_state"] for row in audits))
        self.assertEqual(
            next(
                row["licence_state"]
                for row in inventory
                if row["artifact_kind"] == "zenodo_deposit"
            ),
            "detected",
        )
        self.assertEqual(len(index["entries"]), len(retrievals))

        serialized = json.dumps(index, sort_keys=True) + "\n" + "".join(
            ",".join(row.values()) for row in retrievals
        )
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("/home/", serialized)
        self.assertNotIn("/tmp/", serialized)


if __name__ == "__main__":
    unittest.main()
