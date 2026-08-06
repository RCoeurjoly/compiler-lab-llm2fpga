#!/usr/bin/env python3
"""Audit every selected artifact and paper-attributed GitHub repository."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

try:
    from survey.scripts.enrich_metadata import (
        cached_request,
        enrich_selected_metadata,
        licence_state,
        response_json,
        write_retrieval_log,
    )
except ModuleNotFoundError:  # Direct ``python survey/scripts/...`` execution.
    from enrich_metadata import (  # type: ignore[no-redef]
        cached_request,
        enrich_selected_metadata,
        licence_state,
        response_json,
        write_retrieval_log,
    )


ROOT = Path(__file__).resolve().parents[2]

ARTIFACT_INVENTORY_FIELDS = [
    "project_family_id",
    "title",
    "level_final",
    "route_family",
    "preferred_record_id",
    "stable_identifier_type",
    "stable_identifier",
    "source_url",
    "artifact_claim_state",
    "paper_reported_url",
    "normalized_artifact_url",
    "artifact_kind",
    "artifact_relation",
    "evidence_location",
    "observed_status",
    "licence_state",
    "licence_evidence",
    "repository_audit_id",
    "metadata_services_json",
    "metadata_status_codes_json",
    "failure_code",
    "limitations",
]

REPOSITORY_AUDIT_FIELDS = [
    "repository_audit_id",
    "project_family_id",
    "repository_url",
    "normalized_repository_url",
    "evidence_relation",
    "default_branch",
    "observed_commit",
    "archived_state",
    "release_tags_json",
    "licence_state",
    "licence_spdx_id",
    "licence_evidence",
    "source_closure_state",
    "submodules_json",
    "generated_or_omitted_rtl",
    "build_files_json",
    "ci_files_json",
    "tool_indicators_json",
    "vendor_ip_indicators_json",
    "fpga_families_json",
    "tests_json",
    "limitations",
    "observed_status",
    "http_status",
    "failure_code",
    "evidence_request_ids_json",
]

# These are project artifacts explicitly attributed by the cited paper, not
# dependencies merely mentioned in prose. The two future-release claims remain
# claims even if their current endpoint is absent.
CLAIMED_ARTIFACTS: dict[str, dict[str, str]] = {
    "CONTROL-COMPILER-LAB": {
        "url": "https://github.com/RCoeurjoly/compiler-lab-llm2fpga",
        "kind": "github_repository",
        "relation": "local_project_control",
    },
    "PF-1326C1A7929FA973": {
        "url": "https://github.com/OswaldHe/HeteroLLM",
        "kind": "github_repository",
        "relation": "paper_reported_project_repository",
    },
    "PF-4EBDD47F47E94583": {
        "url": "https://github.com/Edwina1030/TinyTransformer4TS",
        "kind": "github_repository",
        "relation": "paper_reported_future_release_repository",
    },
    "PF-7FF210B343FEAC43": {
        "url": "https://doi.org/10.5281/zenodo.10422477",
        "kind": "zenodo_deposit",
        "relation": "paper_reported_project_artifact",
    },
    "PF-85A0286974EFC09E": {
        "url": "https://github.com/PKU-SEC-Lab/LightMamba",
        "kind": "github_repository",
        "relation": "paper_reported_project_repository",
    },
    "PF-86FE8DBFB50CB04C": {
        "url": "https://github.com/cornell-zhang/allo/tree/main/examples",
        "kind": "github_repository",
        "relation": "paper_reported_future_release_repository",
    },
    "PF-99E0323A054EE2AD": {
        "url": "https://github.com/LUT-FPGA/LUT-LLM",
        "kind": "github_repository",
        "relation": "paper_reported_project_repository",
    },
    "PF-DA130C9A8682ACE6": {
        "url": "https://github.com/zjnyly/LoopLynx",
        "kind": "github_repository",
        "relation": "paper_reported_project_repository",
    },
    "PF-E7AA5B0B1A09F007": {
        "url": "https://github.com/HLSTransform/submission",
        "kind": "github_repository",
        "relation": "paper_reported_project_repository",
    },
    "PF-E9C1300B04E80B95": {
        "url": "https://github.com/JoshuaLandgraf/cascade/blob/artifact/experiments/README.md",
        "kind": "github_repository",
        "relation": "paper_reported_experiment_repository",
        "commit": "artifact",
    },
}


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def normalize_github_url(url: str) -> str:
    text = url.strip()
    if re.match(r"^git@github\.com:", text, re.IGNORECASE):
        text = "https://github.com/" + text.split(":", 1)[1]
    parsed = urlsplit(text)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {
        "github.com",
        "www.github.com",
    }:
        raise ValueError("not a GitHub HTTPS repository URL")
    if parsed.username or parsed.password or parsed.query:
        raise ValueError("GitHub repository URL contains credentials or query data")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() in {"features", "marketplace", "topics"}:
        raise ValueError("malformed GitHub repository URL")
    owner, repository = parts[:2]
    repository = re.sub(r"\.git$", "", repository, flags=re.IGNORECASE)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("malformed GitHub owner or repository")
    return f"https://github.com/{owner}/{repository}"


def _blank_repository_audit(url: str) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in REPOSITORY_AUDIT_FIELDS}
    row.update(
        {
            "repository_url": url,
            "release_tags_json": "[]",
            "licence_state": "unavailable",
            "submodules_json": "[]",
            "build_files_json": "[]",
            "ci_files_json": "[]",
            "tool_indicators_json": "[]",
            "vendor_ip_indicators_json": "[]",
            "fpga_families_json": "[]",
            "tests_json": "[]",
            "evidence_request_ids_json": "[]",
        }
    )
    return row


def _status_failure(status: int) -> str:
    if status in {403, 429}:
        return "RATE_LIMITED"
    if status == 404:
        return "REPOSITORY_UNAVAILABLE"
    return "API_UNAVAILABLE"


def _decode_readme(payload: object) -> str:
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return ""
    try:
        return base64.b64decode(str(payload.get("content", ""))).decode(
            "utf-8", errors="replace"
        )
    except (ValueError, TypeError):
        return ""


def _paths_matching(paths: list[str], patterns: tuple[str, ...]) -> list[str]:
    return sorted(
        path for path in paths if any(re.search(pattern, path, re.I) for pattern in patterns)
    )


def repository_source_closure(
    *,
    tree_status: int,
    tree_truncated: bool,
    submodules: list[str],
    vendor_ip: list[str],
    omitted_markers: list[str],
) -> tuple[str, list[str]]:
    """Classify only what API/tree evidence can establish."""

    if tree_status != 200:
        return "unavailable", ["TREE_UNAVAILABLE"]
    failures = ["TREE_TRUNCATED"] if tree_truncated else []
    incomplete = bool(failures or submodules or vendor_ip or omitted_markers)
    return (
        "incomplete_indicators_observed" if incomplete else "api_tree_observed",
        failures,
    )


def audit_repository(url: str, commit: str | None) -> dict[str, object]:
    """Audit one repository using GitHub API/tree evidence, never a clone."""

    row = _blank_repository_audit(url)
    try:
        normalized = normalize_github_url(url)
    except ValueError:
        row.update(
            {
                "observed_status": "malformed",
                "failure_code": "MALFORMED_REPOSITORY_URL",
                "source_closure_state": "unavailable",
                "limitations": "repository URL rejected before any network request",
            }
        )
        return row

    owner, repository = normalized.removeprefix("https://github.com/").split("/", 1)
    slug = f"{owner}/{repository}"
    api = f"https://api.github.com/repos/{owner}/{repository}"
    request_ids: list[str] = []

    repo_entry = cached_request("github", f"{slug.lower()}:repository", api)
    request_ids.append(repo_entry.identifier)
    row["normalized_repository_url"] = normalized
    row["http_status"] = repo_entry.http_status
    if repo_entry.http_status != 200:
        row.update(
            {
                "observed_status": "unavailable",
                "failure_code": _status_failure(repo_entry.http_status),
                "source_closure_state": "unavailable",
                "limitations": "repository metadata unavailable; no tree evidence",
                "evidence_request_ids_json": _json(request_ids),
            }
        )
        return row

    repo_payload = response_json(repo_entry)
    if not isinstance(repo_payload, dict):
        repo_payload = {}
    default_branch = str(repo_payload.get("default_branch") or "")
    row["default_branch"] = default_branch
    row["archived_state"] = "archived" if repo_payload.get("archived") else "active"

    requested_ref = commit or default_branch
    commit_url = f"{api}/commits/{quote(requested_ref, safe='')}"
    commit_entry = cached_request(
        "github", f"{slug.lower()}:commit:{requested_ref}", commit_url
    )
    request_ids.append(commit_entry.identifier)
    commit_payload = response_json(commit_entry)
    observed_commit = (
        str(commit_payload.get("sha") or "") if isinstance(commit_payload, dict) else ""
    )
    row["observed_commit"] = observed_commit
    if commit_entry.http_status != 200 or not re.fullmatch(r"[0-9a-fA-F]{40}", observed_commit):
        row.update(
            {
                "observed_status": "unavailable",
                "failure_code": "COMMIT_UNAVAILABLE",
                "source_closure_state": "unavailable",
                "limitations": "repository observed but requested commit could not be pinned",
                "evidence_request_ids_json": _json(request_ids),
            }
        )
        return row

    endpoints = {
        "tree": (
            f"{slug.lower()}:tree:{observed_commit}",
            f"{api}/git/trees/{observed_commit}?recursive=1",
        ),
        "releases": (f"{slug.lower()}:releases", f"{api}/releases?per_page=100"),
        "licence": (
            f"{slug.lower()}:licence:{observed_commit}",
            f"{api}/license?ref={observed_commit}",
        ),
        "readme": (
            f"{slug.lower()}:readme:{observed_commit}",
            f"{api}/readme?ref={observed_commit}",
        ),
    }
    entries = {}
    for name, (identifier, endpoint) in endpoints.items():
        entries[name] = cached_request("github", identifier, endpoint)
        request_ids.append(identifier)

    tree_payload = response_json(entries["tree"])
    tree_items = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
    tree_truncated = bool(
        tree_payload.get("truncated") if isinstance(tree_payload, dict) else False
    )
    paths = sorted(
        str(item.get("path"))
        for item in tree_items
        if isinstance(item, dict) and item.get("path")
    )
    submodules = sorted(
        {
            str(item.get("path"))
            for item in tree_items
            if isinstance(item, dict) and str(item.get("mode")) == "160000"
        }
    )
    releases_payload = response_json(entries["releases"])
    releases = (
        sorted(
            {
                str(item.get("tag_name"))
                for item in releases_payload
                if isinstance(item, dict) and item.get("tag_name")
            }
        )
        if isinstance(releases_payload, list)
        else []
    )
    licence_payload = response_json(entries["licence"])
    licence_object = (
        licence_payload.get("license", {}) if isinstance(licence_payload, dict) else {}
    )
    spdx = str(licence_object.get("spdx_id") or "") if isinstance(licence_object, dict) else ""
    licence_name = str(licence_object.get("name") or "") if isinstance(licence_object, dict) else ""
    evidence = spdx if spdx and spdx != "NOASSERTION" else licence_name
    state = licence_state(repo_entry.http_status, entries["licence"].http_status, evidence)
    readme = _decode_readme(response_json(entries["readme"]))
    searchable = "\n".join(paths) + "\n" + readme

    build_files = _paths_matching(
        paths,
        (
            r"(^|/)(makefile|cmakelists\.txt|build\.gradle|flake\.nix)$",
            r"\.(tcl|xpr|qpf|qsf|sbt|mk)$",
            r"(^|/)(requirements[^/]*\.txt|environment\.ya?ml)$",
        ),
    )
    ci_files = _paths_matching(paths, (r"^\.github/workflows/", r"(^|/)\.gitlab-ci\.yml$"))
    tests = _paths_matching(
        paths,
        (r"(^|/)(tests?|testbench|tb|sim)(/|$)", r"(^|/)[^/]*(test|tb)\.(v|sv|vhd|py|cpp)$"),
    )
    vendor_ip = _paths_matching(
        paths,
        (r"\.(xci|dcp|edf|edn|ngc|qip|sof|bit|bin)$", r"(^|/)(ip|ipcore|encrypted)(/|$)"),
    )
    tool_names = sorted(
        {
            match.group(0).lower()
            for match in re.finditer(
                r"\b(vivado|vitis(?: hls)?|quartus|spinalhdl|chisel|verilator|yosys|nextpnr|intel hls|sdaccel)\b",
                searchable,
                re.I,
            )
        }
    )
    fpga_families = sorted(
        {
            match.group(0)
            for match in re.finditer(
                r"\b(?:alveo\s+)?(?:u280|u250|u55c|v80|vck190|vpk180|vu9p|kv260|zcu104|pynq-z2|spartan-7|ice40|amazon f1|arria[- ]?10)\b",
                searchable,
                re.I,
            )
        },
        key=str.lower,
    )
    rtl_count = sum(path.lower().endswith((".v", ".sv", ".vhd", ".vhdl")) for path in paths)
    generated_markers = sorted(
        set(re.findall(r"(?i)generated (?:rtl|verilog|vhdl)|generate[s|d]* (?:rtl|verilog|vhdl)", readme))
    )
    omitted_markers = sorted(
        set(re.findall(r"(?i)(?:not included|not committed|omitted|coming soon|will be released)", readme))
    )
    closure, failures = repository_source_closure(
        tree_status=entries["tree"].http_status,
        tree_truncated=tree_truncated,
        submodules=submodules,
        vendor_ip=vendor_ip,
        omitted_markers=omitted_markers,
    )
    if state == "none_detected":
        failures.append("NO_LICENSE_DETECTED")
    elif state == "unavailable":
        failures.append("LICENSE_API_UNAVAILABLE")
    if row["archived_state"] == "archived":
        failures.append("ARCHIVED_REPOSITORY")

    row.update(
        {
            "release_tags_json": _json(releases),
            "licence_state": state,
            "licence_spdx_id": spdx,
            "licence_evidence": (
                f"GitHub licence API at {observed_commit}: {evidence}"
                if evidence
                else f"GitHub licence API HTTP {entries['licence'].http_status} at {observed_commit}"
            ),
            "source_closure_state": closure,
            "submodules_json": _json(submodules),
            "generated_or_omitted_rtl": (
                f"rtl_files={rtl_count};generated_markers={_json(generated_markers)};"
                f"omitted_markers={_json(omitted_markers)}"
            ),
            "build_files_json": _json(build_files),
            "ci_files_json": _json(ci_files),
            "tool_indicators_json": _json(tool_names),
            "vendor_ip_indicators_json": _json(vendor_ip),
            "fpga_families_json": _json(fpga_families),
            "tests_json": _json(tests),
            "limitations": (
                "GitHub repository/tree/licence/release/README API evidence only; "
                "no clone, dependency fetch, build, generated-file comparison, or binary inspection"
            ),
            "observed_status": "observed" if not failures else "observed_with_failures",
            "failure_code": "|".join(failures),
            "evidence_request_ids_json": _json(request_ids),
        }
    )
    return row


def _evidence_for_claim(selected: dict[str, str]) -> str:
    try:
        evidence = json.loads(selected.get("evidence_locations", "{}"))
    except json.JSONDecodeError:
        return ""
    return str(
        evidence.get("artifact_availability_score")
        or evidence.get("rq4_source_openness")
        or ""
    )


def build_artifact_inventory(
    deep_review_path: Path, records_path: Path
) -> list[dict[str, str]]:
    with records_path.open(encoding="utf-8", newline="") as handle:
        records = {row["record_id"]: row for row in csv.DictReader(handle)}
    output: list[dict[str, str]] = []
    with deep_review_path.open(encoding="utf-8", newline="") as handle:
        selected_rows = list(csv.DictReader(handle))
    for selected in selected_rows:
        record = records.get(selected["preferred_record_id"], {})
        claim = CLAIMED_ARTIFACTS.get(selected["project_family_id"])
        row = {field: "" for field in ARTIFACT_INVENTORY_FIELDS}
        stable_type = "arxiv" if record.get("arxiv_id") else ("doi" if record.get("doi") else "local_control")
        stable_identifier = record.get("arxiv_id") or record.get("doi") or selected["project_family_id"]
        row.update(
            {
                "project_family_id": selected["project_family_id"],
                "title": selected["title"],
                "level_final": selected["level_final"],
                "route_family": selected["route_family"],
                "preferred_record_id": selected["preferred_record_id"],
                "stable_identifier_type": stable_type,
                "stable_identifier": stable_identifier,
                "source_url": record.get("source_url", "") or record.get("abs_url", ""),
                "metadata_services_json": "[]",
                "metadata_status_codes_json": "{}",
            }
        )
        if not claim:
            row.update(
                {
                    "artifact_claim_state": "not_reported",
                    "artifact_kind": "none_reported",
                    "artifact_relation": "no_project_artifact_claim_found_in_task4_pdf_audit",
                    "evidence_location": _evidence_for_claim(selected),
                    "observed_status": "negative_evidence",
                    "licence_state": "unavailable",
                    "licence_evidence": "No attributed project artifact endpoint to inspect",
                    "failure_code": "NO_PROJECT_ARTIFACT_REPORTED",
                    "limitations": "No project artifact URL was attributed by the frozen paper audit",
                }
            )
        else:
            normalized = (
                normalize_github_url(claim["url"])
                if claim["kind"] == "github_repository"
                else claim["url"]
            )
            row.update(
                {
                    "artifact_claim_state": (
                        "paper_reported_future_release"
                        if "future_release" in claim["relation"]
                        else "paper_reported_available"
                    ),
                    "paper_reported_url": claim["url"],
                    "normalized_artifact_url": normalized,
                    "artifact_kind": claim["kind"],
                    "artifact_relation": claim["relation"],
                    "evidence_location": _evidence_for_claim(selected),
                    "observed_status": "pending_api_audit",
                    "licence_state": "unavailable",
                    "licence_evidence": "Pending current endpoint/API evidence",
                    "repository_audit_id": (
                        f"REPO-{selected['project_family_id']}"
                        if claim["kind"] == "github_repository"
                        else ""
                    ),
                    "failure_code": "PENDING_API_AUDIT",
                    "limitations": "Paper report is not current availability, licence, or source-closure evidence",
                }
            )
        output.append(row)
    validate_artifact_inventory(output)
    return output


def validate_artifact_inventory(rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("artifact inventory cannot be empty")
    seen: set[str] = set()
    required = {
        "project_family_id",
        "title",
        "level_final",
        "route_family",
        "stable_identifier_type",
        "stable_identifier",
        "artifact_claim_state",
        "artifact_kind",
        "artifact_relation",
        "observed_status",
        "licence_state",
        "licence_evidence",
        "limitations",
    }
    for row in rows:
        if set(row) != set(ARTIFACT_INVENTORY_FIELDS):
            raise ValueError("artifact inventory row does not use the mandatory exact schema")
        family_id = str(row["project_family_id"])
        if family_id in seen:
            raise ValueError(f"duplicate project_family_id: {family_id}")
        seen.add(family_id)
        for field in required:
            if not str(row[field]).strip():
                raise ValueError(f"{family_id}: mandatory {field} is blank")
        if str(row["licence_state"]) not in {
            "detected",
            "none_detected",
            "unavailable",
        }:
            raise ValueError(f"{family_id}: invalid licence_state")
        negative = str(row["artifact_claim_state"]) == "not_reported" or str(
            row["observed_status"]
        ) in {
            "negative_evidence",
            "unavailable",
            "malformed",
            "pending_api_audit",
        }
        if negative and not str(row["failure_code"]).strip():
            raise ValueError(f"{family_id}: failure_code is blank")
        if str(row["artifact_kind"]) != "none_reported":
            if not str(row["paper_reported_url"]).strip() or not str(
                row["normalized_artifact_url"]
            ).strip():
                raise ValueError(f"{family_id}: claimed artifact URL is blank")


def validate_repository_audit(rows: list[dict[str, object]]) -> None:
    seen: set[str] = set()
    for row in rows:
        if set(row) != set(REPOSITORY_AUDIT_FIELDS):
            raise ValueError("repository audit row does not use the mandatory exact schema")
        normalized = str(row["normalized_repository_url"]).lower()
        if not normalized:
            raise ValueError("normalized_repository_url is blank")
        if normalized in seen:
            raise ValueError(f"duplicate normalized_repository_url: {normalized}")
        seen.add(normalized)
        for field in (
            "repository_audit_id",
            "project_family_id",
            "repository_url",
            "evidence_relation",
            "licence_state",
            "source_closure_state",
            "limitations",
            "observed_status",
            "evidence_request_ids_json",
        ):
            if not str(row[field]).strip():
                raise ValueError(f"repository audit mandatory {field} is blank")
        if str(row["licence_state"]) not in {"detected", "none_detected", "unavailable"}:
            raise ValueError("invalid licence_state")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_audit(deep_review: Path, records: Path, out: Path) -> None:
    inventory = build_artifact_inventory(deep_review, records)
    metadata = enrich_selected_metadata(deep_review, records)
    audits: list[dict[str, object]] = []
    audits_by_family: dict[str, dict[str, object]] = {}
    for family_id, claim in CLAIMED_ARTIFACTS.items():
        if claim["kind"] != "github_repository":
            continue
        audit = audit_repository(claim["url"], claim.get("commit"))
        audit.update(
            {
                "repository_audit_id": f"REPO-{family_id}",
                "project_family_id": family_id,
                "evidence_relation": claim["relation"],
            }
        )
        audits.append(audit)
        audits_by_family[family_id] = audit

    zenodo = cached_request(
        "zenodo",
        "10.5281/zenodo.10422477",
        "https://zenodo.org/api/records/10422477",
    )
    zenodo_payload = response_json(zenodo)
    zenodo_metadata = (
        zenodo_payload.get("metadata", {})
        if isinstance(zenodo_payload, dict)
        else {}
    )
    zenodo_licence = (
        zenodo_metadata.get("license", {})
        if isinstance(zenodo_metadata, dict)
        else {}
    )
    zenodo_licence_id = (
        str(zenodo_licence.get("id") or "")
        if isinstance(zenodo_licence, dict)
        else str(zenodo_licence or "")
    )
    for row in inventory:
        statuses = metadata.get(row["project_family_id"], {})
        row["metadata_services_json"] = _json(sorted(statuses))
        row["metadata_status_codes_json"] = _json(statuses)
        if row["artifact_kind"] == "github_repository":
            audit = audits_by_family[row["project_family_id"]]
            row["observed_status"] = str(audit["observed_status"])
            row["licence_state"] = str(audit["licence_state"])
            row["licence_evidence"] = str(audit["licence_evidence"])
            row["failure_code"] = str(audit["failure_code"])
            if not row["failure_code"] and audit["licence_state"] == "detected":
                row["failure_code"] = "NONE"
            row["limitations"] = str(audit["limitations"])
        elif row["artifact_kind"] == "zenodo_deposit":
            row["observed_status"] = "observed" if zenodo.http_status == 200 else "unavailable"
            if zenodo.http_status != 200:
                row["licence_state"] = "unavailable"
                row["licence_evidence"] = f"Zenodo record API HTTP {zenodo.http_status}"
                row["failure_code"] = "ZENODO_UNAVAILABLE"
            elif zenodo_licence_id:
                row["licence_state"] = "detected"
                row["licence_evidence"] = f"Zenodo record API licence: {zenodo_licence_id}"
                row["failure_code"] = "NONE"
            else:
                row["licence_state"] = "none_detected"
                row["licence_evidence"] = "Zenodo record API contains no licence identifier"
                row["failure_code"] = "NO_LICENSE_DETECTED"
            row["limitations"] = (
                "Zenodo record API evidence only; deposit files were not downloaded or executed"
            )

    audits.sort(key=lambda row: str(row["project_family_id"]))
    validate_artifact_inventory(inventory)
    validate_repository_audit(audits)
    _write_csv(out / "artifact_inventory.csv", ARTIFACT_INVENTORY_FIELDS, inventory)
    _write_csv(out / "repository_audit.csv", REPOSITORY_AUDIT_FIELDS, audits)
    write_retrieval_log(out / "api_retrieval_log.csv")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep-review", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    run_audit(arguments.deep_review, arguments.records, arguments.out)


if __name__ == "__main__":
    main()
