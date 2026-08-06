#!/usr/bin/env python3
"""Audit every selected artifact and paper-attributed GitHub repository."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit

try:
    from survey.scripts.enrich_metadata import (
        cached_request,
        enrich_selected_metadata,
        licence_state,
        LOG_FIELDS,
        MalformedResponseError,
        retrieval_log_rows,
        retrieval_failure_code,
        response_json,
        write_retrieval_log,
    )
except ModuleNotFoundError:  # Direct ``python survey/scripts/...`` execution.
    from enrich_metadata import (  # type: ignore[no-redef]
        cached_request,
        enrich_selected_metadata,
        licence_state,
        LOG_FIELDS,
        MalformedResponseError,
        retrieval_log_rows,
        retrieval_failure_code,
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
    "artifact_evidence_request_ids_json",
    "artifact_endpoint_evidence_json",
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
    "requested_ref",
    "observed_ref",
    "observation_source",
    "default_branch",
    "observed_commit",
    "archived_state",
    "release_tags_json",
    "licence_state",
    "licence_spdx_id",
    "licence_evidence",
    "source_closure_state",
    "submodules_json",
    "submodule_gitlinks_json",
    "generated_or_omitted_rtl",
    "build_files_json",
    "dependency_manifests_json",
    "tool_manifests_json",
    "ci_files_json",
    "tool_indicators_json",
    "vendor_ip_indicators_json",
    "vendor_ip_evidence_json",
    "encrypted_vendor_ip_json",
    "vendor_headers_json",
    "binary_files_json",
    "fpga_families_json",
    "tests_json",
    "limitations",
    "observed_status",
    "http_status",
    "failure_code",
    "evidence_request_ids_json",
    "local_evidence_ids_json",
    "endpoint_evidence_json",
]

# These are project artifacts explicitly attributed by the cited paper, not
# dependencies merely mentioned in prose. The two future-release claims remain
# claims even if their current endpoint is absent.
CLAIMED_ARTIFACTS: dict[str, dict[str, str]] = {
    "CONTROL-COMPILER-LAB": {
        "url": "https://github.com/RCoeurjoly/compiler-lab-llm2fpga",
        "kind": "github_repository",
        "relation": "local_project_control",
        "commit": "433592c448f8b19a30dd046a1ec726b09a86d892",
        "superseded_default_commit": "ea15b070c12461065047a18c8a05108a222d0eac",
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
            "submodule_gitlinks_json": "[]",
            "build_files_json": "[]",
            "dependency_manifests_json": "[]",
            "tool_manifests_json": "[]",
            "ci_files_json": "[]",
            "tool_indicators_json": "[]",
            "vendor_ip_indicators_json": "[]",
            "vendor_ip_evidence_json": "[]",
            "encrypted_vendor_ip_json": "[]",
            "vendor_headers_json": "[]",
            "binary_files_json": "[]",
            "fpga_families_json": "[]",
            "tests_json": "[]",
            "evidence_request_ids_json": "[]",
            "local_evidence_ids_json": "[]",
            "endpoint_evidence_json": "{}",
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
    if (
        not isinstance(payload, dict)
        or payload.get("encoding") != "base64"
        or not isinstance(payload.get("content"), str)
    ):
        raise MalformedResponseError("README response lacks base64 content contract")
    try:
        encoded = "".join(str(payload.get("content", "")).split())
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        raise MalformedResponseError("README response has malformed base64/UTF-8") from error


def _endpoint_json(
    entry: object,
    endpoint: str,
    expected_type: type | tuple[type, ...],
) -> tuple[object | None, str]:
    status = int(getattr(entry, "http_status"))
    if status < 200 or status >= 300:
        return None, f"{endpoint.upper()}_{retrieval_failure_code(status)}"
    try:
        payload = response_json(entry)  # type: ignore[arg-type]
    except MalformedResponseError:
        return None, f"MALFORMED_RESPONSE_{endpoint.upper()}"
    if not isinstance(payload, expected_type):
        return None, f"MALFORMED_RESPONSE_{endpoint.upper()}"
    return payload, ""


def _endpoint_receipt(entry: object, source: str, failure_code: str) -> dict[str, object]:
    return {
        "source": source,
        "http_status": int(getattr(entry, "http_status")),
        "failure_code": failure_code,
        "request_identifier": str(getattr(entry, "identifier")),
        "raw_response_path": str(getattr(entry, "raw_response_path")),
        "response_sha256": str(getattr(entry, "response_sha256")),
    }


def zenodo_artifact_observation(entry: object) -> dict[str, str]:
    payload, failure = _endpoint_json(entry, "zenodo", dict)
    receipt = _endpoint_receipt(entry, "zenodo_api", failure)
    if failure:
        return {
            "observed_status": "unavailable",
            "licence_state": "unavailable",
            "licence_evidence": (
                f"Zenodo record API HTTP {receipt['http_status']}; {failure}; "
                f"raw response SHA-256 {receipt['response_sha256']}"
            ),
            "failure_code": failure,
            "endpoint_evidence_json": _json({"record": receipt}),
        }
    assert isinstance(payload, dict)
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        receipt["failure_code"] = "MALFORMED_RESPONSE_ZENODO"
        return {
            "observed_status": "unavailable",
            "licence_state": "unavailable",
            "licence_evidence": "Zenodo record metadata has a malformed object contract",
            "failure_code": "MALFORMED_RESPONSE_ZENODO",
            "endpoint_evidence_json": _json({"record": receipt}),
        }
    licence = metadata.get("license", {})
    licence_id = (
        str(licence.get("id") or "")
        if isinstance(licence, dict)
        else str(licence or "")
    )
    return {
        "observed_status": "observed",
        "licence_state": "detected" if licence_id else "none_detected",
        "licence_evidence": (
            f"Zenodo record API licence: {licence_id}"
            if licence_id
            else "Zenodo record API contains no licence identifier"
        ),
        "failure_code": "NONE" if licence_id else "NO_LICENSE_DETECTED",
        "endpoint_evidence_json": _json({"record": receipt}),
    }


def _paths_matching(paths: list[str], patterns: tuple[str, ...]) -> list[str]:
    return sorted(
        path for path in paths if any(re.search(pattern, path, re.I) for pattern in patterns)
    )


def _tree_observations(tree_items: list[object], readme: str) -> dict[str, object]:
    paths = sorted(
        str(item.get("path"))
        for item in tree_items
        if isinstance(item, dict) and item.get("path")
    )
    submodule_gitlinks = sorted(
        (
            {"path": str(item.get("path")), "sha": str(item.get("sha") or "")}
            for item in tree_items
            if isinstance(item, dict) and str(item.get("mode")) == "160000"
        ),
        key=lambda item: item["path"],
    )
    dependency_manifests = _paths_matching(
        paths,
        (
            r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.(py|cfg)|poetry\.lock)$",
            r"(^|/)(pipfile(?:\.lock)?|environment\.ya?ml|package(?:-lock)?\.json)$",
            r"(^|/)(cargo\.(toml|lock)|go\.(mod|sum)|conanfile\.(txt|py)|vcpkg\.json)$",
        ),
    )
    tool_manifests = _paths_matching(
        paths,
        (
            r"(^|/)(makefile|cmakelists\.txt|flake\.(nix|lock)|dockerfile)$",
            r"\.(tcl|xpr|qpf|qsf|sbt|mk)$",
        ),
    )
    build_files = sorted(set(dependency_manifests + tool_manifests))
    ci_files = _paths_matching(
        paths, (r"^\.github/workflows/", r"(^|/)\.gitlab-ci\.yml$")
    )
    tests = _paths_matching(
        paths,
        (
            r"(^|/)(tests?|testbench|tb|sim)(/|$)",
            r"(^|/)[^/]*(test|tb)\.(v|sv|vhd|py|cpp)$",
        ),
    )
    encrypted_ip = _paths_matching(paths, (r"(^|/)(encrypted|encryption)(/|$)",))
    vendor_paths = _paths_matching(
        paths,
        (r"\.(xci|dcp|edf|edn|ngc|qip)$", r"(^|/)(ip|ipcore|vendor)(/|$)"),
    )
    vendor_ip_evidence = []
    for path in sorted(set(vendor_paths + encrypted_ip)):
        codes = []
        if re.search(r"\.(xci|dcp|edf|edn|ngc|qip)$", path, re.I):
            codes.append("VENDOR_IP_FILE_EXTENSION")
        if re.search(r"(^|/)(ip|ipcore|vendor)(/|$)", path, re.I):
            codes.append("VENDOR_IP_PATH_MARKER")
        if re.search(r"(^|/)(encrypted|encryption)(/|$)", path, re.I):
            codes.append("ENCRYPTED_PATH_MARKER")
        vendor_ip_evidence.append({"evidence_codes": codes, "path": path})
    vendor_headers = _paths_matching(
        paths,
        (
            r"(^|/)(vendor|third_party|external|deps|ip|ipcore)/.*\.(h|hh|hpp|hxx|vh|svh|vhi)$",
        ),
    )
    binaries = _paths_matching(
        paths, (r"\.(bin|bit|sof|a|so|dll|exe|jar|pt|pth|onnx|npz|npy)$",)
    )
    searchable = "\n".join(paths) + "\n" + readme
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
    generated_markers = sorted(
        set(
            re.findall(
                r"(?i)generated (?:rtl|verilog|vhdl)|generate[s|d]* (?:rtl|verilog|vhdl)",
                readme,
            )
        )
    )
    omitted_markers = sorted(
        set(
            re.findall(
                r"(?i)(?:not included|not committed|omitted|coming soon|will be released)",
                readme,
            )
        )
    )
    return {
        "paths": paths,
        "submodule_gitlinks": submodule_gitlinks,
        "submodules": [item["path"] for item in submodule_gitlinks],
        "dependency_manifests": dependency_manifests,
        "tool_manifests": tool_manifests,
        "build_files": build_files,
        "ci_files": ci_files,
        "tests": tests,
        "vendor_ip": sorted(set(vendor_paths + encrypted_ip)),
        "vendor_ip_evidence": vendor_ip_evidence,
        "encrypted_ip": encrypted_ip,
        "vendor_headers": vendor_headers,
        "binaries": binaries,
        "tool_names": tool_names,
        "fpga_families": fpga_families,
        "rtl_count": sum(
            path.lower().endswith((".v", ".sv", ".vhd", ".vhdl")) for path in paths
        ),
        "generated_markers": generated_markers,
        "omitted_markers": omitted_markers,
    }


def _local_git_tree(repository: Path, commit: str) -> list[object]:
    completed = subprocess.run(
        ["git", "-C", str(repository), "ls-tree", "-r", "-z", commit],
        check=True,
        capture_output=True,
    )
    items: list[object] = []
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, object_type, sha = metadata.decode("ascii").split(" ")
        items.append(
            {
                "mode": mode,
                "type": object_type,
                "sha": sha,
                "path": path.decode("utf-8"),
            }
        )
    return items


def _local_git_blob(repository: Path, commit: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    )
    return completed.stdout.decode("utf-8")


def repository_source_closure(
    *,
    tree_status: int,
    tree_truncated: bool,
    submodules: list[str],
    vendor_ip: list[str],
    binaries: list[str],
    omitted_markers: list[str],
) -> tuple[str, list[str]]:
    """Classify only what API/tree evidence can establish."""

    if tree_status != 200:
        return "unavailable", ["TREE_UNAVAILABLE"]
    failures = ["TREE_TRUNCATED"] if tree_truncated else []
    incomplete = bool(
        failures or submodules or vendor_ip or binaries or omitted_markers
    )
    return (
        "incomplete_indicators_observed" if incomplete else "api_tree_observed",
        failures,
    )


def audit_repository(
    url: str,
    commit: str | None,
    *,
    local_repository: Path | None = None,
    superseded_default_commit: str | None = None,
) -> dict[str, object]:
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

    repo_payload, repo_failure = _endpoint_json(repo_entry, "repository", dict)
    if not repo_failure and isinstance(repo_payload, dict):
        if (
            not isinstance(repo_payload.get("default_branch"), str)
            or not str(repo_payload.get("default_branch")).strip()
            or not isinstance(repo_payload.get("archived"), bool)
        ):
            repo_failure = "MALFORMED_RESPONSE_REPOSITORY"
    if repo_failure:
        row.update(
            {
                "observed_status": "unavailable",
                "failure_code": repo_failure,
                "source_closure_state": "unavailable",
                "limitations": "repository metadata HTTP 200 response was malformed",
                "evidence_request_ids_json": _json(request_ids),
                "endpoint_evidence_json": _json(
                    {
                        "repository": _endpoint_receipt(
                            repo_entry, "github_api", repo_failure
                        )
                    }
                ),
            }
        )
        return row
    assert isinstance(repo_payload, dict)
    default_branch = str(repo_payload.get("default_branch") or "")
    row["default_branch"] = default_branch
    row["archived_state"] = "archived" if repo_payload.get("archived") else "active"

    requested_ref = commit or default_branch
    row["requested_ref"] = requested_ref
    commit_url = f"{api}/commits/{quote(requested_ref, safe='')}"
    commit_entry = cached_request(
        "github", f"{slug.lower()}:commit:{requested_ref}", commit_url
    )
    request_ids.append(commit_entry.identifier)
    commit_payload, commit_failure = _endpoint_json(commit_entry, "commit", dict)
    observed_commit = str(commit_payload.get("sha") or "") if isinstance(commit_payload, dict) else ""
    if not commit_failure and not re.fullmatch(r"[0-9a-fA-F]{40}", observed_commit):
        commit_failure = "MALFORMED_RESPONSE_COMMIT"
    row["observed_commit"] = observed_commit
    if commit_entry.http_status != 200 or not re.fullmatch(r"[0-9a-fA-F]{40}", observed_commit):
        failure = commit_failure or "COMMIT_UNAVAILABLE"
        local_commit_available = False
        if local_repository is not None and re.fullmatch(r"[0-9a-fA-F]{40}", requested_ref):
            local_commit_available = (
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(local_repository),
                        "cat-file",
                        "-e",
                        f"{requested_ref}^{{commit}}",
                    ],
                    check=False,
                    capture_output=True,
                ).returncode
                == 0
            )
        if local_commit_available:
            tree_items = _local_git_tree(local_repository, requested_ref)
            readme = _local_git_blob(local_repository, requested_ref, "README.md")
            licence_text = _local_git_blob(local_repository, requested_ref, "LICENSE")
            observations = _tree_observations(tree_items, readme)
            releases_entry = cached_request(
                "github", f"{slug.lower()}:releases", f"{api}/releases?per_page=100"
            )
            request_ids.append(releases_entry.identifier)
            releases_payload, releases_failure = _endpoint_json(
                releases_entry, "releases", list
            )
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
            endpoint_evidence = {
                "repository": _endpoint_receipt(repo_entry, "github_api", ""),
                "remote_commit": _endpoint_receipt(
                    commit_entry,
                    "github_api",
                    f"REMOTE_REF_{retrieval_failure_code(commit_entry.http_status)}",
                ),
                "local_tree": {
                    "source": "local_git_worktree",
                    "http_status": 200,
                    "failure_code": "",
                    "request_identifier": f"local-git:{requested_ref}:tree",
                },
                "local_readme": {
                    "source": "local_git_worktree",
                    "http_status": 200,
                    "failure_code": "",
                    "request_identifier": f"local-git:{requested_ref}:README.md",
                },
                "local_licence": {
                    "source": "local_git_worktree",
                    "http_status": 200,
                    "failure_code": "",
                    "request_identifier": f"local-git:{requested_ref}:LICENSE",
                },
                "releases": _endpoint_receipt(
                    releases_entry, "github_api_repository_scope", releases_failure
                ),
            }
            failures = [
                f"REMOTE_REF_{retrieval_failure_code(commit_entry.http_status)}"
            ]
            if releases_failure:
                failures.append(releases_failure)
            if superseded_default_commit:
                superseded_id = (
                    f"{slug.lower()}:readme:{superseded_default_commit}"
                )
                superseded_entry = cached_request(
                    "github",
                    superseded_id,
                    f"{api}/readme?ref={superseded_default_commit}",
                )
                request_ids.append(superseded_entry.identifier)
                superseded_failure = (
                    ""
                    if 200 <= superseded_entry.http_status < 300
                    else "SUPERSEDED_DEFAULT_README_"
                    + retrieval_failure_code(superseded_entry.http_status)
                )
                if superseded_failure:
                    failures.append(superseded_failure)
                superseded_receipt = _endpoint_receipt(
                    superseded_entry,
                    "github_api_not_used_as_frozen_ref_evidence",
                    superseded_failure,
                )
                superseded_receipt["ref"] = superseded_default_commit
                endpoint_evidence["superseded_default_readme"] = superseded_receipt
            closure, closure_failures = repository_source_closure(
                tree_status=200,
                tree_truncated=False,
                submodules=observations["submodules"],
                vendor_ip=observations["vendor_ip"],
                binaries=observations["binaries"],
                omitted_markers=observations["omitted_markers"],
            )
            failures.extend(closure_failures)
            spdx = (
                "AGPL-3.0"
                if "GNU AFFERO GENERAL PUBLIC LICENSE" in licence_text
                else ""
            )
            licence = "detected" if spdx else "none_detected"
            if not spdx:
                failures.append("NO_LICENSE_DETECTED")
            row.update(
                {
                    "observed_commit": requested_ref,
                    "observed_ref": requested_ref,
                    "observation_source": "local_git_worktree",
                    "release_tags_json": _json(releases),
                    "licence_state": licence,
                    "licence_spdx_id": spdx,
                    "licence_evidence": (
                        f"local git blob LICENSE at {requested_ref}: {spdx}"
                        if spdx
                        else f"local git tree at {requested_ref} has no detected licence"
                    ),
                    "source_closure_state": closure,
                    "submodules_json": _json(observations["submodules"]),
                    "submodule_gitlinks_json": _json(
                        observations["submodule_gitlinks"]
                    ),
                    "generated_or_omitted_rtl": (
                        f"rtl_files={observations['rtl_count']};"
                        f"generated_markers={_json(observations['generated_markers'])};"
                        f"omitted_markers={_json(observations['omitted_markers'])}"
                    ),
                    "build_files_json": _json(observations["build_files"]),
                    "dependency_manifests_json": _json(
                        observations["dependency_manifests"]
                    ),
                    "tool_manifests_json": _json(observations["tool_manifests"]),
                    "ci_files_json": _json(observations["ci_files"]),
                    "tool_indicators_json": _json(observations["tool_names"]),
                    "vendor_ip_indicators_json": _json(observations["vendor_ip"]),
                    "vendor_ip_evidence_json": _json(
                        observations["vendor_ip_evidence"]
                    ),
                    "encrypted_vendor_ip_json": _json(observations["encrypted_ip"]),
                    "vendor_headers_json": _json(observations["vendor_headers"]),
                    "binary_files_json": _json(observations["binaries"]),
                    "fpga_families_json": _json(observations["fpga_families"]),
                    "tests_json": _json(observations["tests"]),
                    "limitations": (
                        f"Exact frozen ref {requested_ref} observed only through the local git "
                        f"object database/worktree; GitHub returned HTTP {commit_entry.http_status} "
                        "for that ref, so remote publication is unresolved. Repository-scoped "
                        "releases are not frozen-ref evidence; the superseded default-ref README "
                        "receipt is retained only as negative provenance and was not substituted. "
                        "No dependency fetch, build, generated-file comparison, or binary inspection."
                    ),
                    "observed_status": "observed_with_failures",
                    "failure_code": "|".join(dict.fromkeys(failures)),
                    "evidence_request_ids_json": _json(request_ids),
                    "local_evidence_ids_json": _json(
                        [
                            f"local-git:{requested_ref}:tree",
                            f"local-git:{requested_ref}:README.md",
                            f"local-git:{requested_ref}:LICENSE",
                        ]
                    ),
                    "endpoint_evidence_json": _json(endpoint_evidence),
                }
            )
            return row
        row.update(
            {
                "observed_status": "unavailable",
                "failure_code": failure,
                "source_closure_state": "unavailable",
                "limitations": "repository observed but requested commit could not be pinned",
                "evidence_request_ids_json": _json(request_ids),
                "endpoint_evidence_json": _json(
                    {
                        "repository": _endpoint_receipt(
                            repo_entry, "github_api", ""
                        ),
                        "remote_commit": _endpoint_receipt(
                            commit_entry, "github_api", failure
                        ),
                    }
                ),
            }
        )
        return row
    row["observed_ref"] = observed_commit
    row["observation_source"] = "github_api"

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

    failures: list[str] = []
    tree_payload, tree_failure = _endpoint_json(entries["tree"], "tree", dict)
    if tree_failure:
        failures.append(tree_failure)
    tree_items = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
    if isinstance(tree_payload, dict) and (
        not isinstance(tree_items, list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("mode"), str)
            or not isinstance(item.get("sha"), str)
            for item in tree_items
        )
    ):
        tree_items = []
        failures.append("MALFORMED_RESPONSE_TREE")
        tree_failure = "MALFORMED_RESPONSE_TREE"
    tree_truncated = bool(
        tree_payload.get("truncated") if isinstance(tree_payload, dict) else False
    )
    paths = sorted(
        str(item.get("path"))
        for item in tree_items
        if isinstance(item, dict) and item.get("path")
    )
    submodule_gitlinks = sorted(
        (
            {"path": str(item.get("path")), "sha": str(item.get("sha") or "")}
            for item in tree_items
            if isinstance(item, dict) and str(item.get("mode")) == "160000"
        ),
        key=lambda item: item["path"],
    )
    submodules = [item["path"] for item in submodule_gitlinks]
    releases_payload, releases_failure = _endpoint_json(entries["releases"], "releases", list)
    if not releases_failure and isinstance(releases_payload, list) and any(
        not isinstance(item, dict) for item in releases_payload
    ):
        releases_payload = None
        releases_failure = "MALFORMED_RESPONSE_RELEASES"
    if releases_failure:
        failures.append(releases_failure)
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
    licence_payload, licence_failure = _endpoint_json(entries["licence"], "licence", dict)
    if (
        not licence_failure
        and isinstance(licence_payload, dict)
        and not isinstance(licence_payload.get("license"), dict)
    ):
        licence_payload = None
        licence_failure = "MALFORMED_RESPONSE_LICENCE"
    if licence_failure and entries["licence"].http_status != 404:
        failures.append(licence_failure)
    licence_object = (
        licence_payload.get("license", {}) if isinstance(licence_payload, dict) else {}
    )
    spdx = str(licence_object.get("spdx_id") or "") if isinstance(licence_object, dict) else ""
    licence_name = str(licence_object.get("name") or "") if isinstance(licence_object, dict) else ""
    evidence = spdx if spdx and spdx != "NOASSERTION" else licence_name
    state = licence_state(repo_entry.http_status, entries["licence"].http_status, evidence)
    if licence_failure.startswith("MALFORMED_RESPONSE"):
        state = "unavailable"
    readme_payload, readme_failure = _endpoint_json(entries["readme"], "readme", dict)
    readme = ""
    if readme_failure:
        failures.append(readme_failure)
    else:
        try:
            readme = _decode_readme(readme_payload)
        except MalformedResponseError:
            readme_failure = "MALFORMED_RESPONSE_README"
            failures.append(readme_failure)
    observations = _tree_observations(tree_items, readme)
    submodules = observations["submodules"]
    submodule_gitlinks = observations["submodule_gitlinks"]
    build_files = observations["build_files"]
    dependency_manifests = observations["dependency_manifests"]
    tool_manifests = observations["tool_manifests"]
    ci_files = observations["ci_files"]
    tests = observations["tests"]
    vendor_ip = observations["vendor_ip"]
    vendor_ip_evidence = observations["vendor_ip_evidence"]
    encrypted_ip = observations["encrypted_ip"]
    vendor_headers = observations["vendor_headers"]
    binaries = observations["binaries"]
    tool_names = observations["tool_names"]
    fpga_families = observations["fpga_families"]
    rtl_count = observations["rtl_count"]
    generated_markers = observations["generated_markers"]
    omitted_markers = observations["omitted_markers"]
    closure, closure_failures = repository_source_closure(
        tree_status=(0 if tree_failure else entries["tree"].http_status),
        tree_truncated=tree_truncated,
        submodules=submodules,
        vendor_ip=vendor_ip,
        binaries=binaries,
        omitted_markers=omitted_markers,
    )
    failures.extend(closure_failures)
    failures = list(dict.fromkeys(failures))
    if state == "none_detected":
        failures.append("NO_LICENSE_DETECTED")
    elif state == "unavailable":
        failures.append("LICENSE_API_UNAVAILABLE")
    if row["archived_state"] == "archived":
        failures.append("ARCHIVED_REPOSITORY")

    endpoint_failures = {
        "repository": "",
        "remote_commit": commit_failure,
        "tree": tree_failure,
        "releases": releases_failure,
        "licence": licence_failure,
        "readme": readme_failure,
    }

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
            "submodule_gitlinks_json": _json(submodule_gitlinks),
            "generated_or_omitted_rtl": (
                f"rtl_files={rtl_count};generated_markers={_json(generated_markers)};"
                f"omitted_markers={_json(omitted_markers)}"
            ),
            "build_files_json": _json(build_files),
            "dependency_manifests_json": _json(dependency_manifests),
            "tool_manifests_json": _json(tool_manifests),
            "ci_files_json": _json(ci_files),
            "tool_indicators_json": _json(tool_names),
            "vendor_ip_indicators_json": _json(vendor_ip),
            "vendor_ip_evidence_json": _json(vendor_ip_evidence),
            "encrypted_vendor_ip_json": _json(encrypted_ip),
            "vendor_headers_json": _json(vendor_headers),
            "binary_files_json": _json(binaries),
            "fpga_families_json": _json(fpga_families),
            "tests_json": _json(tests),
            "limitations": (
                "GitHub repository/tree/licence/release/README API evidence only; "
                "no clone, dependency fetch, build, generated-file comparison, or binary inspection"
            ),
            "observed_status": "observed" if not failures else "observed_with_failures",
            "failure_code": "|".join(failures),
            "evidence_request_ids_json": _json(request_ids),
            "endpoint_evidence_json": _json(
                {
                    name: _endpoint_receipt(
                        entry,
                        "github_api",
                        endpoint_failures[name],
                    )
                    for name, entry in {
                        "repository": repo_entry,
                        "remote_commit": commit_entry,
                        **entries,
                    }.items()
                }
            ),
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
                "artifact_evidence_request_ids_json": "[]",
                "artifact_endpoint_evidence_json": "{}",
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
        if str(row["observed_status"]) in {"observed", "observed_with_failures"}:
            for field in (
                "requested_ref",
                "observed_ref",
                "observation_source",
                "endpoint_evidence_json",
            ):
                if not str(row[field]).strip():
                    raise ValueError(f"repository audit observed {field} is blank")
            if not re.fullmatch(r"[0-9a-fA-F]{40}", str(row["observed_commit"])):
                raise ValueError("repository audit observed_commit is not a pinned SHA")
        for field in (
            "release_tags_json",
            "submodules_json",
            "submodule_gitlinks_json",
            "build_files_json",
            "dependency_manifests_json",
            "tool_manifests_json",
            "ci_files_json",
            "tool_indicators_json",
            "vendor_ip_indicators_json",
            "vendor_ip_evidence_json",
            "encrypted_vendor_ip_json",
            "vendor_headers_json",
            "binary_files_json",
            "fpga_families_json",
            "tests_json",
            "evidence_request_ids_json",
            "local_evidence_ids_json",
        ):
            if not isinstance(json.loads(str(row[field])), list):
                raise ValueError(f"repository audit {field} is not a JSON list")
        if not isinstance(json.loads(str(row["endpoint_evidence_json"])), dict):
            raise ValueError("repository audit endpoint_evidence_json is not a JSON object")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_csv_bundle_atomic(
    out: Path,
    specs: tuple[tuple[str, list[str], list[dict[str, object]]], ...],
) -> None:
    """Stage all CSVs before publishing; a new output directory appears whole."""

    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}-staging-", dir=out.parent))
    published_as_directory = False
    try:
        for filename, fields, rows in specs:
            _write_csv(staging / filename, fields, rows)
        if not out.exists():
            staging.replace(out)
            published_as_directory = True
            return
        out.mkdir(parents=True, exist_ok=True)
        for filename, _, _ in specs:
            (staging / filename).replace(out / filename)
    finally:
        if not published_as_directory:
            shutil.rmtree(staging, ignore_errors=True)


def run_audit(deep_review: Path, records: Path, out: Path) -> None:
    inventory = build_artifact_inventory(deep_review, records)
    metadata = enrich_selected_metadata(deep_review, records)
    audits: list[dict[str, object]] = []
    audits_by_family: dict[str, dict[str, object]] = {}
    for family_id, claim in CLAIMED_ARTIFACTS.items():
        if claim["kind"] != "github_repository":
            continue
        audit = audit_repository(
            claim["url"],
            claim.get("commit"),
            local_repository=(ROOT if family_id == "CONTROL-COMPILER-LAB" else None),
            superseded_default_commit=claim.get("superseded_default_commit"),
        )
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
    zenodo_observation = zenodo_artifact_observation(zenodo)
    for row in inventory:
        statuses = metadata.get(row["project_family_id"], {})
        row["metadata_services_json"] = _json(sorted(statuses))
        row["metadata_status_codes_json"] = _json(statuses)
        if row["artifact_kind"] == "github_repository":
            audit = audits_by_family[row["project_family_id"]]
            row["observed_status"] = str(audit["observed_status"])
            row["licence_state"] = str(audit["licence_state"])
            row["licence_evidence"] = str(audit["licence_evidence"])
            row["artifact_evidence_request_ids_json"] = str(
                audit["evidence_request_ids_json"]
            )
            row["artifact_endpoint_evidence_json"] = str(
                audit["endpoint_evidence_json"]
            )
            row["failure_code"] = str(audit["failure_code"])
            if not row["failure_code"] and audit["licence_state"] == "detected":
                row["failure_code"] = "NONE"
            row["limitations"] = str(audit["limitations"])
        elif row["artifact_kind"] == "zenodo_deposit":
            for field in (
                "observed_status",
                "licence_state",
                "licence_evidence",
                "failure_code",
            ):
                row[field] = zenodo_observation[field]
            row["artifact_evidence_request_ids_json"] = _json([zenodo.identifier])
            row["artifact_endpoint_evidence_json"] = zenodo_observation[
                "endpoint_evidence_json"
            ]
            row["limitations"] = (
                "Zenodo record API evidence only; deposit files were not downloaded or executed"
            )

    audits.sort(key=lambda row: str(row["project_family_id"]))
    validate_artifact_inventory(inventory)
    validate_repository_audit(audits)
    _write_csv_bundle_atomic(
        out,
        (
            ("artifact_inventory.csv", ARTIFACT_INVENTORY_FIELDS, inventory),
            ("repository_audit.csv", REPOSITORY_AUDIT_FIELDS, audits),
            ("api_retrieval_log.csv", LOG_FIELDS, retrieval_log_rows()),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep-review", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    run_audit(arguments.deep_review, arguments.records, arguments.out)


if __name__ == "__main__":
    main()
