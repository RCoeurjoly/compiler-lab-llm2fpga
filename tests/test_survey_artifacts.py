from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from survey.scripts.audit_repositories import (
    ARTIFACT_INVENTORY_FIELDS,
    CLAIMED_ARTIFACTS,
    REPOSITORY_AUDIT_FIELDS,
    _tree_observations,
    _write_csv_bundle_atomic,
    audit_repository,
    build_artifact_inventory,
    normalize_github_url,
    repository_source_closure,
    validate_artifact_inventory,
    validate_repository_audit,
    zenodo_artifact_observation,
)
from survey.scripts.enrich_metadata import (
    cached_request,
    licence_state,
    retrieval_failure_code,
    write_retrieval_log,
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
    index_path = cache_root / "index.json"
    index = (
        json.loads(index_path.read_text(encoding="utf-8"))
        if index_path.exists()
        else {"schema_version": 1, "entries": []}
    )
    index["entries"].append(entry)
    index["entries"].sort(
        key=lambda item: (item["service"], item["identifier"], item["request_url"])
    )
    index_path.write_text(
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

    def test_public_cache_rejects_service_host_mismatch_and_sensitive_inputs(self) -> None:
        rejected = (
            ("github", "owner/repo:repository", "https://zenodo.org/api/records/1"),
            ("github", "person@example.org", "https://api.github.com/repos/Owner/Repo"),
            ("github", "token=abcdef", "https://api.github.com/repos/Owner/Repo"),
            (
                "github",
                "owner/repo:repository",
                "https://api.github.com/repos/Owner/Repo?unknown=x",
            ),
            (
                "github",
                "owner/repo:repository",
                "https://api.github.com/repos/Owner/Repo?ref=person%40example.org",
            ),
            (
                "github",
                "owner/repo:repository",
                "https://api.github.com/repos/Owner/Repo?recursive=1",
            ),
            (
                "github",
                "owner/repo:repository",
                "https://api.github.com/repos/Owner/Repo?ref=ghp_1234567890abcdef",
            ),
        )
        with TemporaryDirectory() as temporary, patch(
            "survey.scripts.enrich_metadata.requests.get"
        ) as get:
            root = Path(temporary)
            with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                for service, identifier, url in rejected:
                    with self.subTest(service=service, identifier=identifier, url=url):
                        with self.assertRaises(ValueError):
                            cached_request(service, identifier, url)
            get.assert_not_called()
            self.assertFalse((root / "index.json").exists())

    def test_concurrent_cache_requests_preserve_both_atomic_entries(self) -> None:
        class Response:
            status_code = 200

            def __init__(self, url: str) -> None:
                self.content = json.dumps({"url": url}).encode("utf-8")

        requests = (
            ("github", "owner/one:repository", "https://api.github.com/repos/Owner/One"),
            ("github", "owner/two:repository", "https://api.github.com/repos/Owner/Two"),
        )
        with TemporaryDirectory() as temporary, patch(
            "survey.scripts.enrich_metadata.requests.get",
            side_effect=lambda url, **_: Response(url),
        ):
            root = Path(temporary)
            with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    entries = list(executor.map(lambda args: cached_request(*args), requests))

            index = json.loads((root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [entry["identifier"] for entry in index["entries"]],
                ["owner/one:repository", "owner/two:repository"],
            )
            for entry in entries:
                body = (root / entry.raw_response_path).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), entry.response_sha256)
            self.assertEqual(list(root.rglob("*.tmp")), [])

    def test_retrieval_log_rejects_an_unsafe_injected_index_entry(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_cache_entry(
                root,
                service="github",
                identifier="person@example.org",
                url="https://api.github.com/repos/Owner/Repo?recursive=1",
                body=b"{}",
            )
            log_path = root / "unsafe.csv"
            with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                with self.assertRaises(ValueError):
                    write_retrieval_log(log_path)
            self.assertFalse(log_path.exists())


class ArtifactInventoryTests(unittest.TestCase):
    def test_tree_evidence_keeps_manifests_gitlinks_vendor_headers_and_encryption_separate(self) -> None:
        observations = _tree_observations(
            [
                {"path": "deps/requirements.txt", "mode": "100644", "sha": "1" * 40},
                {"path": "flake.nix", "mode": "100644", "sha": "2" * 40},
                {"path": "vendor/core.hpp", "mode": "100644", "sha": "3" * 40},
                {"path": "encrypted/core.dcp", "mode": "100644", "sha": "4" * 40},
                {"path": "upstream", "mode": "160000", "sha": "5" * 40},
            ],
            "",
        )
        self.assertEqual(observations["dependency_manifests"], ["deps/requirements.txt"])
        self.assertEqual(observations["tool_manifests"], ["flake.nix"])
        self.assertEqual(observations["vendor_headers"], ["vendor/core.hpp"])
        self.assertEqual(observations["encrypted_ip"], ["encrypted/core.dcp"])
        self.assertEqual(
            observations["submodule_gitlinks"],
            [{"path": "upstream", "sha": "5" * 40}],
        )
        self.assertEqual(
            observations["vendor_ip_evidence"],
            [
                {
                    "evidence_codes": [
                        "VENDOR_IP_FILE_EXTENSION",
                        "ENCRYPTED_PATH_MARKER",
                    ],
                    "path": "encrypted/core.dcp",
                },
                {
                    "evidence_codes": ["VENDOR_IP_PATH_MARKER"],
                    "path": "vendor/core.hpp",
                },
            ],
        )

    def test_malformed_zenodo_success_is_negative_with_raw_receipt(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_cache_entry(
                root,
                service="zenodo",
                identifier="10.5281/zenodo.10422477",
                url="https://zenodo.org/api/records/10422477",
                body=b"not-json",
            )
            with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                entry = cached_request(
                    "zenodo",
                    "10.5281/zenodo.10422477",
                    "https://zenodo.org/api/records/10422477",
                )
            observation = zenodo_artifact_observation(entry)
        self.assertEqual(observation["observed_status"], "unavailable")
        self.assertEqual(observation["licence_state"], "unavailable")
        self.assertEqual(observation["failure_code"], "MALFORMED_RESPONSE_ZENODO")
        receipt = json.loads(observation["endpoint_evidence_json"])["record"]
        self.assertEqual(receipt["http_status"], 200)
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(b"not-json").hexdigest())

    def test_truncated_api_tree_is_incomplete_source_closure(self) -> None:
        state, failures = repository_source_closure(
            tree_status=200,
            tree_truncated=True,
            submodules=[],
            vendor_ip=[],
            binaries=[],
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

    def test_each_malformed_success_endpoint_fails_closed(self) -> None:
        slug = "owner/repo"
        api = "https://api.github.com/repos/Owner/Repo"
        commit = "1" * 40
        fixtures = {
            "repository": (
                f"{slug}:repository",
                api,
                b'{"default_branch":"main","archived":false}',
            ),
            "commit": (
                f"{slug}:commit:main",
                f"{api}/commits/main",
                json.dumps({"sha": commit}).encode(),
            ),
            "tree": (
                f"{slug}:tree:{commit}",
                f"{api}/git/trees/{commit}?recursive=1",
                b'{"tree":[],"truncated":false}',
            ),
            "releases": (
                f"{slug}:releases",
                f"{api}/releases?per_page=100",
                b"[]",
            ),
            "licence": (
                f"{slug}:licence:{commit}",
                f"{api}/license?ref={commit}",
                b'{"license":{"spdx_id":"MIT"}}',
            ),
            "readme": (
                f"{slug}:readme:{commit}",
                f"{api}/readme?ref={commit}",
                b'{"encoding":"base64","content":""}',
            ),
        }
        for malformed_endpoint in fixtures:
            with self.subTest(endpoint=malformed_endpoint), TemporaryDirectory() as temporary:
                root = Path(temporary)
                malformed_body = (
                    b'{"encoding":"base64","content":"!!!"}'
                    if malformed_endpoint == "readme"
                    else b"\xffnot-json"
                )
                for name, (identifier, url, body) in fixtures.items():
                    _write_cache_entry(
                        root,
                        service="github",
                        identifier=identifier,
                        url=url,
                        body=malformed_body if name == malformed_endpoint else body,
                    )
                with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                    row = audit_repository("https://github.com/Owner/Repo", None)

                code = f"MALFORMED_RESPONSE_{malformed_endpoint.upper()}"
                self.assertIn(code, row["failure_code"])
                self.assertNotEqual(row["observed_status"], "observed")
                endpoints = json.loads(row["endpoint_evidence_json"])
                endpoint_key = (
                    "remote_commit" if malformed_endpoint == "commit" else malformed_endpoint
                )
                receipt = endpoints[endpoint_key]
                self.assertEqual(receipt["http_status"], 200)
                self.assertEqual(receipt["failure_code"], code)
                self.assertEqual(
                    receipt["response_sha256"],
                    hashlib.sha256(malformed_body).hexdigest(),
                )
                self.assertTrue(receipt["raw_response_path"].startswith("responses/github/"))
                if malformed_endpoint == "tree":
                    self.assertEqual(row["source_closure_state"], "unavailable")
                    self.assertEqual(json.loads(row["dependency_manifests_json"]), [])
                if malformed_endpoint == "licence":
                    self.assertEqual(row["licence_state"], "unavailable")
                if malformed_endpoint == "releases":
                    self.assertEqual(json.loads(row["release_tags_json"]), [])

    def test_success_endpoint_payload_shapes_fail_closed(self) -> None:
        slug = "owner/repo"
        api = "https://api.github.com/repos/Owner/Repo"
        commit = "1" * 40
        valid = {
            "repository": b'{"default_branch":"main","archived":false}',
            "commit": json.dumps({"sha": commit}).encode(),
            "tree": b'{"tree":[],"truncated":false}',
            "releases": b"[]",
            "licence": b'{"license":{"spdx_id":"MIT"}}',
            "readme": b'{"encoding":"base64","content":""}',
        }
        invalid = {
            "repository": b'{"archived":false}',
            "commit": b'{"sha":"short"}',
            "tree": b'{"tree":[42],"truncated":false}',
            "releases": b"[42]",
            "licence": b'{"license":"MIT"}',
            "readme": b'{"encoding":"base64"}',
        }
        endpoint = {
            "repository": (f"{slug}:repository", api),
            "commit": (f"{slug}:commit:main", f"{api}/commits/main"),
            "tree": (
                f"{slug}:tree:{commit}",
                f"{api}/git/trees/{commit}?recursive=1",
            ),
            "releases": (f"{slug}:releases", f"{api}/releases?per_page=100"),
            "licence": (
                f"{slug}:licence:{commit}",
                f"{api}/license?ref={commit}",
            ),
            "readme": (f"{slug}:readme:{commit}", f"{api}/readme?ref={commit}"),
        }
        for malformed_endpoint, malformed_body in invalid.items():
            with self.subTest(endpoint=malformed_endpoint), TemporaryDirectory() as temporary:
                root = Path(temporary)
                for name, body in valid.items():
                    identifier, url = endpoint[name]
                    _write_cache_entry(
                        root,
                        service="github",
                        identifier=identifier,
                        url=url,
                        body=(malformed_body if name == malformed_endpoint else body),
                    )
                with patch.dict(os.environ, {"SURVEY_API_CACHE_ROOT": str(root)}):
                    row = audit_repository("https://github.com/Owner/Repo", None)
                self.assertIn(
                    f"MALFORMED_RESPONSE_{malformed_endpoint.upper()}",
                    row["failure_code"],
                )
                self.assertNotEqual(row["observed_status"], "observed")

    def test_fresh_csv_bundle_is_absent_when_staging_fails(self) -> None:
        with TemporaryDirectory() as temporary:
            out = Path(temporary) / "fresh-output"
            with self.assertRaises(ValueError):
                _write_csv_bundle_atomic(
                    out,
                    (
                        ("one.csv", ["a"], [{"a": "one"}]),
                        (
                            "two.csv",
                            ["b"],
                            [{"b": "two", "unexpected": "must fail"}],
                        ),
                    ),
                )
            self.assertFalse(out.exists())


class CommittedArtifactEvidenceTests(unittest.TestCase):
    def test_repository_validation_rejects_observed_rows_without_ref_or_receipts(self) -> None:
        with (ROOT / "survey/build/repository_audit.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            row = next(csv.DictReader(handle))
        for field in (
            "requested_ref",
            "observed_ref",
            "observation_source",
            "endpoint_evidence_json",
        ):
            with self.subTest(field=field):
                broken = dict(row)
                broken[field] = ""
                with self.assertRaisesRegex(ValueError, field):
                    validate_repository_audit([broken])

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

        expected_external = {
            "PF-1326C1A7929FA973": "https://github.com/OswaldHe/HeteroLLM",
            "PF-4EBDD47F47E94583": "https://github.com/Edwina1030/TinyTransformer4TS",
            "PF-85A0286974EFC09E": "https://github.com/PKU-SEC-Lab/LightMamba",
            "PF-86FE8DBFB50CB04C": "https://github.com/cornell-zhang/allo",
            "PF-99E0323A054EE2AD": "https://github.com/LUT-FPGA/LUT-LLM",
            "PF-DA130C9A8682ACE6": "https://github.com/zjnyly/LoopLynx",
            "PF-E7AA5B0B1A09F007": "https://github.com/HLSTransform/submission",
            "PF-E9C1300B04E80B95": "https://github.com/JoshuaLandgraf/cascade",
        }
        self.assertEqual(
            {
                row["project_family_id"]: row["normalized_repository_url"]
                for row in audits
                if row["project_family_id"] != "CONTROL-COMPILER-LAB"
            },
            expected_external,
        )
        self.assertEqual(
            {
                family_id: normalize_github_url(claim["url"])
                for family_id, claim in CLAIMED_ARTIFACTS.items()
                if claim["kind"] == "github_repository"
                and family_id != "CONTROL-COMPILER-LAB"
            },
            expected_external,
        )

        log_identity = {
            (row["service"], row["identifier"], row["request_url"]): row
            for row in retrievals
        }
        index_identity = {
            (entry["service"], entry["identifier"], entry["request_url"]): entry
            for entry in index["entries"]
        }
        self.assertEqual(set(log_identity), set(index_identity))
        self.assertEqual(len(log_identity), len(retrievals))
        for identity, entry in index_identity.items():
            logged = log_identity[identity]
            for field in (
                "raw_response_path",
                "http_status",
                "retrieved_at_utc",
                "response_sha256",
                "error_body_sha256",
            ):
                self.assertEqual(str(entry[field]), logged[field])
            raw = index_path.parent / entry["raw_response_path"]
            self.assertEqual(
                hashlib.sha256(raw.read_bytes()).hexdigest(),
                entry["response_sha256"],
            )
            self.assertEqual(
                logged["failure_code"],
                retrieval_failure_code(int(entry["http_status"])),
            )
            if int(entry["http_status"]) == 0 or int(entry["http_status"]) >= 400:
                self.assertEqual(entry["error_body_sha256"], entry["response_sha256"])

        index_by_identifier = {entry["identifier"]: entry for entry in index["entries"]}
        self.assertEqual(len(index_by_identifier), len(index["entries"]))
        for audit in audits:
            for identifier in json.loads(audit["evidence_request_ids_json"]):
                self.assertIn(identifier, index_by_identifier)
            for receipt in json.loads(audit["endpoint_evidence_json"]).values():
                if str(receipt["source"]).startswith("github_api"):
                    indexed = index_by_identifier[receipt["request_identifier"]]
                    self.assertEqual(receipt["http_status"], indexed["http_status"])
                    self.assertEqual(
                        receipt["response_sha256"], indexed["response_sha256"]
                    )
                    self.assertEqual(
                        receipt["raw_response_path"], indexed["raw_response_path"]
                    )
            if audit["licence_state"] == "none_detected":
                licence_receipt = json.loads(audit["endpoint_evidence_json"])["licence"]
                self.assertEqual(licence_receipt["http_status"], 404)
                self.assertEqual(licence_receipt["failure_code"], "LICENCE_NOT_FOUND")

        frozen = "433592c448f8b19a30dd046a1ec726b09a86d892"
        control = next(
            row for row in audits if row["project_family_id"] == "CONTROL-COMPILER-LAB"
        )
        self.assertEqual(control["requested_ref"], frozen)
        self.assertEqual(control["observed_commit"], frozen)
        self.assertEqual(control["observation_source"], "local_git_worktree")
        self.assertEqual(control["observed_status"], "observed_with_failures")
        self.assertIn("REMOTE_REF_INVALID_IDENTIFIER_OR_REF", control["failure_code"])
        endpoints = json.loads(control["endpoint_evidence_json"])
        self.assertEqual(endpoints["remote_commit"]["http_status"], 422)
        self.assertEqual(endpoints["superseded_default_readme"]["http_status"], 403)
        self.assertEqual(endpoints["local_tree"]["source"], "local_git_worktree")
        self.assertEqual(
            json.loads(control["submodule_gitlinks_json"]),
            [
                {
                    "path": "LLM-inference-on-FPGA-papers",
                    "sha": "95fd9b9a509f275dd3cfdb3360b33dbcca7429f0",
                }
            ],
        )
        control_inventory = next(
            row for row in inventory if row["project_family_id"] == "CONTROL-COMPILER-LAB"
        )
        self.assertEqual(control_inventory["observed_status"], "observed_with_failures")
        self.assertIn(
            "REMOTE_REF_INVALID_IDENTIFIER_OR_REF",
            control_inventory["failure_code"],
        )
        self.assertEqual(
            json.loads(control_inventory["artifact_endpoint_evidence_json"])[
                "remote_commit"
            ]["response_sha256"],
            next(
                entry["response_sha256"]
                for entry in index["entries"]
                if entry["identifier"]
                == f"rcoeurjoly/compiler-lab-llm2fpga:commit:{frozen}"
            ),
        )

        list_fields = (
            "dependency_manifests_json",
            "tool_manifests_json",
            "vendor_headers_json",
            "submodule_gitlinks_json",
            "encrypted_vendor_ip_json",
            "vendor_ip_evidence_json",
        )
        for row in audits:
            for field in list_fields:
                self.assertIsInstance(json.loads(row[field]), list)
            self.assertIsInstance(json.loads(row["endpoint_evidence_json"]), dict)

        hls_transform = next(
            row for row in audits if row["project_family_id"] == "PF-E7AA5B0B1A09F007"
        )
        self.assertEqual(json.loads(hls_transform["vendor_ip_indicators_json"]), [])
        self.assertEqual(
            json.loads(hls_transform["binary_files_json"]),
            [
                "cpu_benchmarks/runq.exe",
                "cpu_benchmarks/tokenizer.bin",
                "llama_xrt/src/tokenizer.bin",
            ],
        )

        serialized = json.dumps(index, sort_keys=True) + "\n" + "".join(
            ",".join(row.values()) for row in retrievals
        )
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("/home/", serialized)
        self.assertNotIn("/tmp/", serialized)


if __name__ == "__main__":
    unittest.main()
