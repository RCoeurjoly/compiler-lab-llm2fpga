#!/usr/bin/env python3
"""Validate the frozen survey evidence package and render D13--D16 offline.

The report is intentionally a *consumer* of the frozen evidence rather than a
second screening pipeline.  It refuses to produce a completion claim unless
the checked-in D1--D12 artifacts still validate, then records exactly which
inputs were used to render the portable Markdown, LaTeX, Mermaid, and PDF
deliverables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


if __package__ in {None, ""}:
    # A file invocation sets sys.path[0] to survey/scripts rather than the
    # repository root. Keep the documented direct CLI form import-equivalent to
    # ``python -m survey.scripts.build_report``.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from survey.scripts.audit_repositories import (
    validate_artifact_inventory,
    validate_repository_audit,
)
from survey.scripts.common import load_scope
from survey.scripts.finalize_screening import (
    make_project_families,
    summarize_final_screening,
    validate_decisions,
)
from survey.scripts.make_figures import (
    FINAL_LEVELS,
    ROUTE_TAXONOMY,
    build_route_family_comparison,
    render_corpus_flow,
    render_route_family_comparison,
    render_timeline,
    validate_mermaid,
    write_figures,
)
from survey.scripts.mlir_stage_matrix import (
    FROZEN_ROUTE_IDS,
    hard_gates_pass,
    validate_decision_matrix,
    validate_stage_matrix,
    render_stage_markdown,
)
from survey.scripts.run_compatibility import ROUTES, validate_receipt
from survey.scripts.select_deep_review import select_families, validate_reviews


ROOT = Path(__file__).resolve().parents[2]
DELIVERABLES = [f"D{number}" for number in range(1, 17)]

# These are source inputs to the completion report, not generated files.  The
# provenance manifest hashes each one by repository-relative path.
ROUTE_RECEIPT_INPUTS = tuple(
    f"survey/compatibility/{route.slug}/{filename}"
    for route in ROUTES.values()
    for filename in ("manifest.json", "README.md", "commands.sh", "stdout.log", "stderr.log")
)

# The report renderer and validators depend on this direct, versioned source
# closure in addition to the frozen evidence files below. The separate source
# manifest pins the expected bytes so a metadata refresh alone cannot bless a
# modified generator.
REPORT_GENERATOR_SOURCES = (
    "survey/scripts/build_report.py",
    "survey/scripts/make_figures.py",
    "survey/scripts/audit_repositories.py",
    "survey/scripts/common.py",
    "survey/scripts/finalize_screening.py",
    "survey/scripts/mlir_stage_matrix.py",
    "survey/scripts/run_compatibility.py",
    "survey/scripts/select_deep_review.py",
)
REPORT_GENERATOR_SOURCE_MANIFEST = "survey/build/report_generator_sources.json"

REPORT_INPUTS = (
    "flake.nix",
    "flake.lock",
    REPORT_GENERATOR_SOURCE_MANIFEST,
    *REPORT_GENERATOR_SOURCES,
    "LLM-inference-on-FPGA-papers/data/catalog.json",
    "LLM-inference-on-FPGA-papers/data/survey.csv",
    "survey/protocol.md",
    "survey/config/scope.yaml",
    "survey/data/manual_overrides.csv",
    "survey/data/route_vocabulary.csv",
    "survey/build/provenance.json",
    "survey/build/api_retrieval_log.csv",
    "survey/build/api-cache/index.json",
    "survey/build/environment_manifest.json",
    "survey/build/records_normalized.csv",
    "survey/build/duplicate_groups.csv",
    "survey/build/works_deduplicated.csv",
    "survey/build/phase1_mapping.csv",
    "survey/build/phase1_mapping.parquet",
    "survey/build/flow_counts.json",
    "survey/build/phase1_run.json",
    "survey/data/screening_decisions.csv",
    "survey/build/phase1_exclusions.csv",
    "survey/build/screening_audit.md",
    "survey/build/project_families.csv",
    "survey/build/deep_review.csv",
    "survey/build/deep_review.md",
    "survey/build/artifact_inventory.csv",
    "survey/build/repository_audit.csv",
    "survey/build/compatibility_fixtures.json",
    "survey/build/compatibility_summary.csv",
    "survey/build/mlir_circt_stage_matrix.csv",
    "survey/build/mlir_circt_stage_matrix.md",
    "survey/build/decision_matrix_scored.csv",
    "survey/build/route_selection.md",
    "survey/build/final_flow_counts.json",
    "survey/data/mlir_circt_stage_catalog.json",
) + ROUTE_RECEIPT_INPUTS

REPORT_CITATIONS = (
    "flake.nix",
    "flake.lock",
    "survey/protocol.md",
    "survey/config/scope.yaml",
    "LLM-inference-on-FPGA-papers/data/catalog.json",
    "survey/build/provenance.json",
    "survey/build/api_retrieval_log.csv",
    "survey/build/phase1_run.json",
    "survey/data/screening_decisions.csv",
    "survey/build/records_normalized.csv",
    "survey/build/duplicate_groups.csv",
    "survey/build/phase1_mapping.csv",
    "survey/build/screening_audit.md",
    "survey/build/project_families.csv",
    "survey/build/deep_review.csv",
    "survey/build/deep_review.md",
    "survey/build/artifact_inventory.csv",
    "survey/build/repository_audit.csv",
    "survey/build/api-cache/index.json",
    "survey/build/final_flow_counts.json",
    "survey/build/compatibility_summary.csv",
    "survey/compatibility/R1-mlir-circt/manifest.json",
    "survey/compatibility/R1-mlir-circt/commands.sh",
    "survey/compatibility/R1-mlir-circt/stdout.log",
    "survey/compatibility/R1-mlir-circt/stderr.log",
    "survey/build/mlir_circt_stage_matrix.csv",
    "survey/build/mlir_circt_stage_matrix.md",
    "survey/build/decision_matrix_scored.csv",
    "survey/build/route_selection.md",
)

# The build manifest is a report output, so it cannot be an input to its own
# hash manifest. All other report evidence paths must be listed in
# ``REPORT_INPUTS`` and hash checked before rendering.
REPORT_OUTPUT_REFERENCES = frozenset({"survey/build/final_report_build.json"})
TEXTUAL_OUTPUTS = (
    "corpus_flow.mmd",
    "route_family_comparison.csv",
    "route_family_comparison.md",
    "timeline.mmd",
    "final_report.md",
    "final_report.tex",
    "final_report_pdflatex.txt",
    "final_report_build.json",
)
HASHED_OUTPUTS = tuple(
    filename for filename in TEXTUAL_OUTPUTS if filename != "final_report_build.json"
) + ("final_report.pdf",)
_REPORT_PATH = re.compile(
    r"`(?P<path>(?:(?:survey|LLM-inference-on-FPGA-papers)/[^`#\s]+|flake\.(?:nix|lock)))(?:#[^`]*)?`"
)
_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9.])/(?:[A-Za-z0-9._-]+/)+")
_CREDENTIAL_HEADER = re.compile(
    r"(?im)^(?:authorization|proxy-authorization|cookie|x-api-key|x-auth-token)\s*:"
)
_CREDENTIAL_URL = re.compile(r"https?://[^/\s]+@", re.IGNORECASE)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?[\"']?"
    r"[A-Za-z_][A-Za-z0-9_.-]*(?:token|password|secret|api[_-]?key|credential)[A-Za-z0-9_.-]*"
    r"[\"']?\s*(?:=|:)\s*[\"']?(?!<redacted>|redacted\b)[^\s#\"']+"
)
_PRIVATE_KEY_MATERIAL = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.IGNORECASE
)
_TEX_FAILURE = re.compile(
    r"(?:undefined references|undefined citations|emergency stop|! LaTeX Error|!.*Error)",
    re.IGNORECASE,
)
_TEX_SUCCESS = re.compile(
    r"^Output written on .+\.pdf \(\d+ pages?, \d+ bytes\)\.$", re.MULTILINE
)
_TEX_COMMAND = (
    "$ pdflatex -interaction=nonstopmode -halt-on-error -output-directory . "
    "final_report.tex"
)

REQUIRED_REPORT_TEXT = (
    "459 to 461",
    "461 source records",
    "456 unique works",
    "5 duplicate manifestations",
    "A=30, B=57, C=75, D=68, X=231",
    "230 included records",
    "226 project families",
    "36 reviewed project-family/control rows",
    "3 projects x 20 canonical transformations = 60 assessed cells",
    "NO_PRIMARY_ROUTE_PASSED",
    "Primary route: none",
    "R1 is the ineligible next evidence-gathering route",
    "R2 is an ineligible different-family hypothesis",
    "H1 — unsupported for the current route.",
    "H2 — bounded/partial support only.",
    "H3 — inconclusive.",
    "board remains unspecified",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: cannot read JSON evidence at {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: JSON evidence must be an object: {path}")
    return payload


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _require_file(root: Path, relative: str, delivery: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"{delivery}: evidence path must be repository-relative: {relative}")
    resolved_root = root.resolve()
    path = (resolved_root / candidate).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"{delivery}: evidence path escapes repository: {relative}") from error
    if not path.is_file():
        raise ValueError(f"{delivery}: required evidence is missing: {relative}")
    return path


def _read_csv(root: Path, relative: str, delivery: str, **kwargs: object) -> pd.DataFrame:
    path = _require_file(root, relative, delivery)
    try:
        return pd.read_csv(path, **kwargs)
    except (OSError, pd.errors.ParserError) as error:
        raise ValueError(f"{delivery}: cannot parse CSV evidence: {relative}") from error


def _require(condition: bool, delivery: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{delivery}: {message}")


def _report_source_paths(markdown: str) -> set[str]:
    """Return file paths quoted as evidence in Markdown, without locators."""

    return {match["path"] for match in _REPORT_PATH.finditer(markdown)}


def _validate_textual_outputs(out: Path) -> None:
    """Reject local machine paths and credential-shaped text in every output."""

    for filename in TEXTUAL_OUTPUTS:
        content = _require_file(out, filename, "D16").read_text(encoding="utf-8")
        if "file://" in content.lower():
            raise ValueError(f"D16: {filename} contains a file URL")
        if _ABSOLUTE_PATH.search(content):
            raise ValueError(f"D16: {filename} contains an absolute filesystem path")
        if _CREDENTIAL_HEADER.search(content):
            raise ValueError(f"D16: {filename} contains a credential header")
        if _CREDENTIAL_URL.search(content):
            raise ValueError(f"D16: {filename} contains a credential-bearing URL")
        if _CREDENTIAL_ASSIGNMENT.search(content):
            raise ValueError(f"D16: {filename} contains a credential assignment")
        if _PRIVATE_KEY_MATERIAL.search(content):
            raise ValueError(f"D16: {filename} contains private-key material")


def _validate_report_generator_source_manifest(root: Path) -> None:
    """Bind report generation to the reviewed direct Python source closure."""

    manifest = _read_json(
        _require_file(root, REPORT_GENERATOR_SOURCE_MANIFEST, "D16"), "D16"
    )
    _require(
        manifest.get("schema_version") == 1,
        "D16",
        "generator source manifest schema_version must be 1",
    )
    source_hashes = manifest.get("source_sha256")
    _require(
        isinstance(source_hashes, Mapping),
        "D16",
        "generator source manifest hashes are missing",
    )
    _require(
        set(source_hashes) == set(REPORT_GENERATOR_SOURCES),
        "D16",
        "generator source manifest must list the exact direct source closure",
    )
    for relative_path in REPORT_GENERATOR_SOURCES:
        expected_hash = source_hashes.get(relative_path)
        _require(
            isinstance(expected_hash, str),
            "D16",
            f"generator source hash is missing: {relative_path}",
        )
        _require(
            _sha256(_require_file(root, relative_path, "D16")) == expected_hash,
            "D16",
            f"generator source hash drifted: {relative_path}",
        )


def _validate_final_flow(root: Path) -> dict[str, object]:
    flow = _read_json(
        _require_file(root, "survey/build/final_flow_counts.json", "D6"), "D6"
    )
    expected = {
        "input_records": 461,
        "candidate_unique_works": 456,
        "duplicate_manifestations": 5,
        "included_records": 230,
        "excluded_records": 231,
        "project_family_count": 226,
    }
    for field, value in expected.items():
        _require(_integer(flow.get(field), f"D6 {field}") == value, "D6", f"{field} must be {value}")
    levels = flow.get("final_levels")
    _require(isinstance(levels, Mapping), "D6", "final_levels is missing")
    normalized_levels = {str(key): _integer(value, f"D6 final_levels.{key}") for key, value in levels.items()}
    _require(normalized_levels == FINAL_LEVELS, "D6", "final A/B/C/D/X counts do not match the adjudicated result")
    _require(sum(normalized_levels.values()) == 461, "D6", "final levels must reconcile to 461 records")
    _require(230 + 231 == 461, "D6", "included and excluded counts must reconcile")
    return flow


def _validate_final_flow_against_screened(
    screened: pd.DataFrame, final_flow: Mapping[str, object]
) -> None:
    """Bind D13's frozen counts to the controlled final decisions."""

    summary = summarize_final_screening(screened)
    controlled_levels = summary["final_levels"]
    _require(
        isinstance(controlled_levels, Mapping),
        "D6",
        "controlled decisions lack final levels",
    )
    _require(
        controlled_levels == FINAL_LEVELS,
        "D6",
        "final screening levels derived from controlled decisions must match frozen A/B/C/D/X counts",
    )
    flow_levels = final_flow.get("final_levels")
    _require(isinstance(flow_levels, Mapping), "D6", "final flow lacks final levels")
    normalized_flow_levels = {
        str(level): _integer(value, f"D6 final_levels.{level}")
        for level, value in flow_levels.items()
    }
    _require(
        normalized_flow_levels == controlled_levels,
        "D6",
        "final flow screening levels must match controlled decisions",
    )
    controlled_included = _integer(summary["included_records"], "D6 included_records")
    controlled_excluded = _integer(summary["excluded_records"], "D6 excluded_records")
    _require(
        (controlled_included, controlled_excluded) == (230, 231),
        "D6",
        "controlled decisions must contain exactly 230 included and 231 excluded records",
    )
    _require(
        _integer(final_flow.get("included_records"), "D6 included_records")
        == controlled_included,
        "D6",
        "final flow included_records must match controlled decisions",
    )
    _require(
        _integer(final_flow.get("excluded_records"), "D6 excluded_records")
        == controlled_excluded,
        "D6",
        "final flow excluded_records must match controlled decisions",
    )
    _require(
        len(screened) == sum(controlled_levels.values()) == _integer(
            final_flow.get("input_records"), "D6 input_records"
        ),
        "D6",
        "controlled final levels must reconcile to the final flow input count",
    )


def _validate_d1_to_d6(root: Path) -> dict[str, object]:
    scope_path = _require_file(root, "survey/config/scope.yaml", "D1")
    scope = load_scope(scope_path)
    protocol = _require_file(root, "survey/protocol.md", "D1").read_text(encoding="utf-8")
    _require("459" in protocol and "461" in protocol, "D1", "protocol lacks the explicit 459-to-461 amendment")
    _require(
        tuple(str(route) for route in scope.get("route_families", [])) == ROUTE_TAXONOMY,
        "D1",
        "scope route taxonomy drifted",
    )

    provenance = _read_json(
        _require_file(root, "survey/build/provenance.json", "D2"), "D2"
    )
    _require(provenance.get("schema_version") == 1, "D2", "provenance schema_version must be 1")
    _require(provenance.get("expected_records") == 461, "D2", "provenance expected_records must be 461")
    _require(provenance.get("actual_catalogue_records") == 461, "D2", "provenance actual catalogue count must be 461")
    _require(provenance.get("protocol_record_count") == 459, "D2", "provenance must preserve the supplied protocol count")
    repositories = provenance.get("repositories")
    _require(isinstance(repositories, Mapping), "D2", "provenance repositories are missing")
    _require(set(repositories) == {"compiler_lab", "papers", "llm2fpga"}, "D2", "provenance must pin all three repositories")
    for name, entry in repositories.items():
        _require(isinstance(entry, Mapping), "D2", f"repository provenance is malformed for {name}")
        _require(bool(_text(entry.get("commit"))), "D2", f"repository commit is blank for {name}")
        _require(bool(_text(entry.get("remote"))), "D2", f"repository remote is blank for {name}")
    cache_index = _read_json(
        _require_file(root, "survey/build/api-cache/index.json", "D2"), "D2"
    )
    _require(
        cache_index.get("schema_version") == 1,
        "D2",
        "API cache index schema_version must be 1",
    )
    environment_manifest = _read_json(
        _require_file(root, "survey/build/environment_manifest.json", "D2"), "D2"
    )
    _require(
        environment_manifest.get("schema_version") == 1,
        "D2",
        "environment manifest schema_version must be 1",
    )
    for manifest_field, source_path in (
        ("flake_nix_sha256", "flake.nix"),
        ("flake_lock_sha256", "flake.lock"),
    ):
        _require(
            environment_manifest.get(manifest_field)
            == _sha256(_require_file(root, source_path, "D2")),
            "D2",
            f"environment manifest does not bind current {source_path}",
        )
    api_log = _read_csv(root, "survey/build/api_retrieval_log.csv", "D2", keep_default_na=False)
    _require(len(api_log) == 102, "D2", "API retrieval log must retain 102 recorded requests")
    _require({"request_url", "raw_response_path", "response_sha256", "failure_code"}.issubset(api_log.columns), "D2", "API retrieval log schema is incomplete")
    _require(not api_log["raw_response_path"].astype(str).str.startswith(("/", "file:")).any(), "D2", "API response paths must remain relative")

    normalized = _read_csv(root, "survey/build/records_normalized.csv", "D3", keep_default_na=False)
    _require(len(normalized) == 461, "D3", "normalised record count must be 461")
    _require("record_id" in normalized and not normalized["record_id"].duplicated().any(), "D3", "normalised records must have unique record_id values")

    duplicate_groups = _read_csv(root, "survey/build/duplicate_groups.csv", "D4", keep_default_na=False)
    deduplicated = _read_csv(root, "survey/build/works_deduplicated.csv", "D4", keep_default_na=False)
    _require(len(duplicate_groups) == 461, "D4", "duplicate lineage must cover all source records")
    _require(not duplicate_groups["record_id"].duplicated().any(), "D4", "duplicate lineage must retain one row per record")
    _require(len(deduplicated) == 456 and deduplicated["work_id"].nunique() == 456, "D4", "deduplicated works must be exactly 456")
    _require(duplicate_groups["work_id"].nunique() == 456, "D4", "duplicate lineage unique works must be 456")
    excess = len(duplicate_groups) - duplicate_groups["work_id"].nunique()
    multi_groups = int((duplicate_groups.groupby("work_id").size() > 1).sum())
    _require(excess == 5 and multi_groups == 5, "D4", "deduplication must record five duplicate manifestations/groups")

    mapping = _read_csv(root, "survey/build/phase1_mapping.csv", "D5", keep_default_na=False)
    _require(len(mapping) == 461 and not mapping["record_id"].duplicated().any(), "D5", "Phase 1 mapping must cover exactly 461 unique records")
    parquet = _require_file(root, "survey/build/phase1_mapping.parquet", "D5")
    try:
        parquet_mapping = pd.read_parquet(parquet)
    except (OSError, ValueError, ImportError) as error:
        raise ValueError("D5: cannot read phase1_mapping.parquet") from error
    _require(len(parquet_mapping) == 461, "D5", "Phase 1 parquet mapping must cover 461 records")
    phase1_run = _read_json(_require_file(root, "survey/build/phase1_run.json", "D5"), "D5")
    output_hashes = phase1_run.get("output_sha256")
    _require(isinstance(output_hashes, Mapping), "D5", "phase1_run output_sha256 is missing")
    for filename, expected_hash in output_hashes.items():
        observed = _sha256(_require_file(root, f"survey/build/{filename}", "D5"))
        _require(observed == expected_hash, "D5", f"Phase 1 output hash mismatch: {filename}")
    auto_flow = _read_json(_require_file(root, "survey/build/flow_counts.json", "D5"), "D5")
    _require(_integer(auto_flow.get("input_records"), "D5 input_records") == 461, "D5", "Phase 1 input count must be 461")
    _require(_integer(auto_flow.get("candidate_unique_works"), "D5 candidate_unique_works") == 456, "D5", "Phase 1 unique works must be 456")

    decisions_path = _require_file(root, "survey/data/screening_decisions.csv", "D6")
    decisions = pd.read_csv(decisions_path, keep_default_na=False)
    screened = validate_decisions(mapping, decisions)
    exclusions = _read_csv(root, "survey/build/phase1_exclusions.csv", "D6", keep_default_na=False)
    _require(len(exclusions) == 231, "D6", "controlled exclusions must contain 231 records")
    _require(not exclusions["record_id"].duplicated().any(), "D6", "exclusions must have unique record_id values")
    _require(set(exclusions["record_id"]) == set(screened.loc[screened["final_level"].eq("X"), "record_id"]), "D6", "exclusions must match final X decisions")
    final_flow = _validate_final_flow(root)
    _validate_final_flow_against_screened(screened, final_flow)
    _require(
        final_flow.get("source_screening_decisions_sha256")
        == _sha256(decisions_path),
        "D6",
        "final flow must pin the controlled screening decisions hash",
    )
    _require(_sha256(_require_file(root, "survey/build/flow_counts.json", "D6")) == final_flow.get("source_phase1_flow_counts_sha256"), "D6", "final flow must pin the immutable Phase 1 flow hash")
    _require(_sha256(_require_file(root, "survey/build/phase1_mapping.csv", "D6")) == final_flow.get("source_phase1_mapping_sha256"), "D6", "final flow must pin the immutable Phase 1 mapping hash")
    _require(_sha256(_require_file(root, "survey/build/phase1_run.json", "D6")) == final_flow.get("source_phase1_run_sha256"), "D6", "final flow must pin the immutable Phase 1 receipt hash")
    return {
        "scope": scope,
        "mapping": mapping,
        "screened": screened,
        "final_flow": final_flow,
    }


def _validate_d7_to_d12(root: Path, context: Mapping[str, object]) -> dict[str, object]:
    mapping = context["mapping"]
    screened = context["screened"]
    if not isinstance(mapping, pd.DataFrame) or not isinstance(screened, pd.DataFrame):
        raise ValueError("D7: internal screening validation context is malformed")

    families = _read_csv(root, "survey/build/project_families.csv", "D7", dtype=str, keep_default_na=False)
    expected_families = make_project_families(screened)
    actual_lineage = set(
        zip(
            families["project_family_id"].astype(str),
            families["work_id"].astype(str),
            families["is_primary_work"].astype(str).str.lower(),
            strict=True,
        )
    )
    expected_lineage = set(
        zip(
            expected_families["project_family_id"].astype(str),
            expected_families["work_id"].astype(str),
            expected_families["is_primary_work"].astype(str).str.lower(),
            strict=True,
        )
    )
    _require(actual_lineage == expected_lineage, "D7", "project-family lineage differs from controlled final decisions")
    primary = families.loc[families["is_primary_work"].str.lower().eq("true")]
    _require(len(families) == 230 and len(primary) == 226, "D7", "project families must retain 230 rows and 226 primary works")
    _require(primary["project_family_id"].nunique() == 226, "D7", "primary project family count must be 226")

    reviews = _read_csv(root, "survey/build/deep_review.csv", "D8", keep_default_na=False)
    validated_reviews = validate_reviews(reviews)
    selected = select_families(families, validated_reviews)
    _require(len(selected) == 36 and 25 <= len(selected) <= 40, "D8", "deep review must contain the current 36 rows within the 25--40 bound")
    _require(set(selected["project_family_id"]) == set(validated_reviews["project_family_id"]), "D8", "deep-review selection must preserve the frozen reviewed set")

    inventory = _read_csv(root, "survey/build/artifact_inventory.csv", "D9", dtype=str, keep_default_na=False)
    repository_audit = _read_csv(root, "survey/build/repository_audit.csv", "D9", dtype=str, keep_default_na=False)
    validate_artifact_inventory(inventory.to_dict(orient="records"))
    validate_repository_audit(repository_audit.to_dict(orient="records"))
    _require(set(inventory["project_family_id"]) == set(validated_reviews["project_family_id"]), "D9", "artifact inventory must cover the exact deep-review set")
    referenced_audits = {value for value in inventory["repository_audit_id"].astype(str) if value}
    _require(referenced_audits == set(repository_audit["repository_audit_id"].astype(str)), "D9", "repository audit must cover every referenced repository")
    _require(len(repository_audit) == 9, "D9", "repository audit must retain nine evidence rows")

    decision_matrix = _read_csv(root, "survey/build/decision_matrix_scored.csv", "D10", keep_default_na=False)
    validate_decision_matrix(decision_matrix, root)
    route_ids = tuple(decision_matrix["route_id"].astype(str))
    _require(set(route_ids) == set(FROZEN_ROUTE_IDS) == set(ROUTES), "D10", "decision matrix must include exactly R1--R8")
    for row in decision_matrix.to_dict(orient="records"):
        route_id = str(row["route_id"])
        manifest_path = _require_file(root, str(row["receipt_manifest"]), "D10")
        readme_path = _require_file(root, str(row["receipt_readme"]), "D10")
        _require(readme_path.parent == manifest_path.parent, "D10", f"receipt README directory mismatch for {route_id}")
        manifest = _read_json(manifest_path, "D10")
        validate_receipt(manifest, manifest_path.parent)
        _require(manifest.get("route_id") == route_id, "D10", f"receipt route_id mismatch for {route_id}")
    _require_file(root, "survey/build/compatibility_fixtures.json", "D10")
    summary = _read_csv(root, "survey/build/compatibility_summary.csv", "D10", keep_default_na=False)
    _require(set(summary["route_id"].astype(str)) == set(FROZEN_ROUTE_IDS), "D10", "compatibility summary must cover R1--R8")

    stage_matrix = _read_csv(root, "survey/build/mlir_circt_stage_matrix.csv", "D11", keep_default_na=False)
    validate_stage_matrix(stage_matrix, root)
    _require(len(stage_matrix) == 60, "D11", "stage matrix must have exactly 3 x 20 = 60 rows")
    _require(stage_matrix["project"].nunique() == 3 and stage_matrix["ordinal"].nunique() == 20, "D11", "stage matrix must preserve three projects and all 20 canonical transformations")
    stage_markdown = _require_file(root, "survey/build/mlir_circt_stage_matrix.md", "D11").read_text(encoding="utf-8")
    _require(
        stage_markdown == render_stage_markdown(stage_matrix, root),
        "D11",
        "stage report must exactly match the canonical MLIR/CIRCT renderer",
    )
    _require("Weight-loading interface" in stage_markdown, "D11", "stage report must include the source-faithful weight-loading transformation")
    _require("60 assessment rows" in stage_markdown, "D11", "stage report must describe all 60 assessed cells")

    _require((decision_matrix["selection_status"] == "INELIGIBLE").all(), "D12", "every current route must remain ineligible")
    for row in decision_matrix.to_dict(orient="records"):
        _require(not hard_gates_pass(row), "D12", f"{row['route_id']} incorrectly passes every hard gate")
    selection = _require_file(root, "survey/build/route_selection.md", "D12").read_text(encoding="utf-8")
    _require("NO_PRIMARY_ROUTE_PASSED" in selection, "D12", "route selection must record no eligible primary")
    _require("Primary route: ``" in selection, "D12", "route selection must leave the primary empty")
    _require("Next evidence-gathering route: `R1`" in selection, "D12", "R1 next evidence route is missing")
    _require("Fallback hypothesis: `R2`" in selection, "D12", "R2 different-family hypothesis is missing")
    return {
        "families": families,
        "reviews": validated_reviews,
        "decision_matrix": decision_matrix,
        "stage_matrix": stage_matrix,
    }


def _validate_source_deliverables(root: Path) -> dict[str, object]:
    """Validate the immutable D1--D12 package before generating anything."""

    initial = _validate_d1_to_d6(root)
    return {**initial, **_validate_d7_to_d12(root, initial)}


def _validate_generated_deliverables(
    root: Path, out: Path, context: Mapping[str, object] | None = None
) -> None:
    """Validate D13--D16 in a requested output directory."""

    root = root.resolve()
    context = context or _validate_source_deliverables(root)
    _validate_report_generator_source_manifest(root)
    flow = context.get("final_flow")
    _require(isinstance(flow, Mapping), "D13", "report context lacks final flow")
    corpus_flow = _require_file(out, "corpus_flow.mmd", "D13").read_text(encoding="utf-8")
    validate_mermaid(corpus_flow)
    _require(
        corpus_flow == render_corpus_flow(flow),
        "D13",
        "corpus flow must exactly match the canonical final-count graph",
    )

    expected_comparison, unassigned = build_route_family_comparison(root)
    comparison = _read_csv(out, "route_family_comparison.csv", "D14", keep_default_na=False)
    _require(comparison.equals(expected_comparison), "D14", "route comparison must be exactly derived from frozen taxonomy data")
    comparison_markdown = _require_file(out, "route_family_comparison.md", "D14").read_text(encoding="utf-8")
    _require(
        comparison_markdown
        == render_route_family_comparison(expected_comparison, unassigned),
        "D14",
        "route comparison Markdown must exactly match the canonical frozen taxonomy report",
    )

    timeline = _require_file(out, "timeline.mmd", "D15").read_text(encoding="utf-8")
    validate_mermaid(timeline)
    _require(
        timeline == render_timeline(),
        "D15",
        "timeline must exactly match the canonical date-independent protocol",
    )

    markdown_path = _require_file(out, "final_report.md", "D16")
    latex_path = _require_file(out, "final_report.tex", "D16")
    pdf_path = _require_file(out, "final_report.pdf", "D16")
    transcript_path = _require_file(out, "final_report_pdflatex.txt", "D16")
    metadata_path = _require_file(out, "final_report_build.json", "D16")
    markdown = markdown_path.read_text(encoding="utf-8")
    latex = latex_path.read_text(encoding="utf-8")
    _require(
        markdown == _render_markdown(context),
        "D16",
        "Markdown report must exactly match the canonical generator output",
    )
    _require(
        latex == _render_latex(context),
        "D16",
        "LaTeX report must exactly match the canonical generator output",
    )
    _require(pdf_path.stat().st_size > 0, "D16", "rendered PDF is empty")
    transcript = transcript_path.read_text(encoding="utf-8")
    _require(bool(transcript.strip()), "D16", "pdflatex transcript is empty")
    pass_markers = re.findall(r"^# pdflatex pass ([0-9]+)$", transcript, re.MULTILINE)
    _require(
        pass_markers == ["1", "2"],
        "D16",
        "transcript must show exactly two successful pdflatex passes",
    )
    _require(
        transcript.count(_TEX_COMMAND) == 2,
        "D16",
        "transcript must record exactly two logical pdflatex commands",
    )
    _require(
        len(_TEX_SUCCESS.findall(transcript)) == 2,
        "D16",
        "transcript must record successful PDF output for both pdflatex passes",
    )
    _require(
        not _TEX_FAILURE.search(transcript),
        "D16",
        "pdflatex transcript reports an error or unresolved reference",
    )
    _validate_deterministic_pdf_replay(root, latex, pdf_path, transcript)
    _validate_textual_outputs(out)
    for text in REQUIRED_REPORT_TEXT:
        _require(text in markdown, "D16", f"report misses required conclusion: {text}")
    _require(
        set(REPORT_CITATIONS).issubset(REPORT_INPUTS),
        "D16",
        "substantive report citations must be included in REPORT_INPUTS",
    )
    for citation in REPORT_CITATIONS:
        _require(citation in markdown, "D16", f"report lacks evidence citation: {citation}")
        _require_file(root, citation, "D16")
    cited_paths = _report_source_paths(markdown)
    untracked_citations = cited_paths - set(REPORT_INPUTS) - REPORT_OUTPUT_REFERENCES
    _require(
        not untracked_citations,
        "D16",
        "report cites paths absent from its hash manifest: "
        + ", ".join(sorted(untracked_citations)),
    )
    for citation in cited_paths - REPORT_OUTPUT_REFERENCES:
        _require_file(root, citation, "D16")
    metadata = _read_json(metadata_path, "D16")
    _require(metadata.get("pdflatex_runs") == 2, "D16", "report must record exactly two pdflatex runs")
    _require(metadata.get("pdf_sha256") == _sha256(pdf_path), "D16", "recorded PDF hash does not match the PDF")
    pdflatex = metadata.get("pdflatex")
    _require(isinstance(pdflatex, Mapping), "D16", "pdflatex provenance is missing")
    _require(pdflatex.get("command") == "pdflatex", "D16", "pdflatex command must be logical and portable")
    _require(bool(_text(pdflatex.get("version"))), "D16", "pdflatex version is missing")
    _require(
        pdflatex.get("environment") == "declared-flake-texlive",
        "D16",
        "pdflatex must be supplied by the declared Nix environment",
    )
    inputs = metadata.get("input_sha256")
    _require(isinstance(inputs, Mapping), "D16", "report input hash manifest is missing")
    _require(set(inputs) == set(REPORT_INPUTS), "D16", "report input hash paths are incomplete or non-portable")
    for relative, expected_hash in inputs.items():
        _require(_sha256(_require_file(root, str(relative), "D16")) == expected_hash, "D16", f"report input hash drifted: {relative}")
    generated = metadata.get("generated_sha256")
    expected_generated = {
        "corpus_flow.mmd",
        "route_family_comparison.csv",
        "route_family_comparison.md",
        "timeline.mmd",
        "final_report.md",
        "final_report.tex",
    }
    _require(isinstance(generated, Mapping) and set(generated) == expected_generated, "D16", "generated output hash manifest is incomplete")
    for filename, expected_hash in generated.items():
        _require(_sha256(_require_file(out, str(filename), "D16")) == expected_hash, "D16", f"generated output hash drifted: {filename}")
    retained = metadata.get("retained_sha256")
    _require(
        isinstance(retained, Mapping) and set(retained) == set(HASHED_OUTPUTS),
        "D16",
        "retained output hash manifest is incomplete",
    )
    for filename, expected_hash in retained.items():
        _require(
            _sha256(_require_file(out, str(filename), "D16")) == expected_hash,
            "D16",
            f"retained output hash drifted: {filename}",
        )
    _require(
        metadata.get("transcript_sha256")
        == retained.get("final_report_pdflatex.txt"),
        "D16",
        "transcript hash is missing or inconsistent",
    )
    metadata_without_hash = {
        key: value for key, value in metadata.items() if key != "metadata_sha256"
    }
    _require(
        metadata.get("metadata_sha256") == _canonical_json_sha256(metadata_without_hash),
        "D16",
        "build metadata self-hash is inconsistent",
    )
    _require(_integer(flow["input_records"], "D16 input_records") == 461, "D16", "report must remain tied to final-flow evidence")


def validate_deliverables(root: Path = ROOT) -> list[str]:
    """Confirm all D1--D16 artifacts, evidence links, counts, and report hashes."""

    root = root.resolve()
    context = _validate_source_deliverables(root)
    _validate_generated_deliverables(root, root / "survey/build", context)
    return DELIVERABLES.copy()


def _render_markdown(context: Mapping[str, object]) -> str:
    flow = context["final_flow"]
    if not isinstance(flow, Mapping):
        raise ValueError("D16: report context lacks final flow counts")
    return """# Executable LLM2FPGA survey evidence report

## Question, scope, and amendment

This report asks which implementation route has the strongest evidence-supported
prospect of reproducible, end-to-end causal-language-model inference on an FPGA
with a substantially open toolchain. The frozen protocol amendment reconciles
the supplied catalogue count **459 to 461**: the commit-pinned source contains
**461 source records**, and the study question and eligibility rules are
unchanged. Evidence: `survey/protocol.md#lines=5-17`; `survey/config/scope.yaml`;
`LLM-inference-on-FPGA-papers/data/catalog.json`; `survey/build/provenance.json`.

## Methods and corpus lineage

The package preserves each source record in
`survey/build/records_normalized.csv`, records duplicate/version lineage in
`survey/build/duplicate_groups.csv`, performs rule-based triage in the immutable
`survey/build/phase1_mapping.csv`, and retains adjudicated screening decisions in
`survey/data/screening_decisions.csv`. Source and command provenance are pinned
in `survey/build/provenance.json`, `survey/build/api_retrieval_log.csv`, and
`survey/build/phase1_run.json`.

The final (not automatic) corpus flow is **461 source records**, **456 unique works**, and **5 duplicate manifestations**. Final decisions are
**A=30, B=57, C=75, D=68, X=231**: **230 included records** and 231 controlled
exclusions. The final reconciliation and the immutable Phase 1 hashes are in
`survey/build/final_flow_counts.json`; the readable audit is
`survey/build/screening_audit.md`.

## Families, sample, and artifact audit

The controlled grouping has **226 project families** represented by 230
included work rows in `survey/build/project_families.csv`. The bounded manual
sample has **36 reviewed project-family/control rows**, satisfying the planned
25--40 range, with RQ1--RQ6 evidence recorded in
`survey/build/deep_review.csv` and `survey/build/deep_review.md`.

Artifact and licence claims remain evidence-qualified: the complete reviewed
set is represented in `survey/build/artifact_inventory.csv`, while the nine
repository observations (including source-closure and licence limitations) are
in `survey/build/repository_audit.csv`. The API evidence index is
`survey/build/api-cache/index.json`; raw API bodies are not required to render
or validate this offline package.

## Compatibility and MLIR/CIRCT evidence

Every tested route R1--R8 has a receipt, command script, standard output, and
standard error under the checked-in compatibility receipt directories; the checked summary is
`survey/build/compatibility_summary.csv`. In particular,
`survey/compatibility/R1-mlir-circt/manifest.json` records the final observed
R1 stop at `RTL_GENERATION/F_SOURCE_MISSING`; its reproducible command and
observations are `survey/compatibility/R1-mlir-circt/commands.sh`,
`survey/compatibility/R1-mlir-circt/stdout.log`, and
`survey/compatibility/R1-mlir-circt/stderr.log`. This is not an RTL pass.

The source-faithful MLIR/CIRCT catalog is **3 projects x 20 canonical transformations = 60 assessed cells**, rather than a claim that there are only
20 assessments. It retains source evidence and H1--H3 bounded conclusions in
`survey/build/mlir_circt_stage_matrix.csv` and
`survey/build/mlir_circt_stage_matrix.md`, including the canonical
weight-loading interface transformation.

The bounded hypothesis outcomes are explicit: **H1 — unsupported for the current route.** **H2 — bounded/partial support only.** **H3 — inconclusive.** Their source-faithful evidence and limits are recorded in
`survey/build/mlir_circt_stage_matrix.md#lines=90-94`.

## Selection result

`survey/build/decision_matrix_scored.csv` evaluates the frozen hard gates
before any weighted score. The selection outcome is
**NO_PRIMARY_ROUTE_PASSED**. **Primary route: none.** All R1--R8 candidates are
ineligible, so no score is used to promote a primary route.

**R1 is the ineligible next evidence-gathering route**: its required next step
is to restore the pinned native-SV helper, regenerate RTL, and then obtain
independent lint and synthesis evidence. **R2 is an ineligible different-family hypothesis**: its proprietary RTL and `SOURCE_CLOSURE/F_VENDOR_IP` finding make
it neither a selected fallback nor a primary. These statements are reproduced
from `survey/build/route_selection.md` and their receipt evidence, including
`survey/compatibility/R1-mlir-circt/manifest.json`.

## Reproduction and limits

Run the offline validation and renderer from the repository root:

```sh
nix develop -c python -m unittest discover -s tests -p 'test_survey_*.py' -v
nix develop -c python survey/scripts/build_report.py --root . --out survey/build
```

The renderer writes date-independent Mermaid source for the final corpus flow,
route-family comparison, and canonical protocol sequence; it invokes `pdflatex`
twice and records its transcript plus PDF SHA-256 in
`survey/build/final_report_build.json`. The pinned `flake.nix` and `flake.lock`
development shell supplies the **declared pdflatex** command, so rendering does
not depend on a host-profile TeX installation. The evidence supports no eligible
primary route, makes no completed end-to-end causal-LM claim, and retains the
protocol limitation that the target **board remains unspecified**. A future
route must obtain new, attributable source, licence, hard-gate, and independent
execution evidence before this conclusion can change.
"""


def _render_latex(_: Mapping[str, object]) -> str:
    path = lambda value: r"\path{" + value + "}"
    return "\n".join(
        (
            r"\documentclass[11pt]{article}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{hyperref}",
            r"\pdfinfo{/Title (Executable LLM2FPGA survey evidence report) /CreationDate (D:19700101000000Z) /ModDate (D:19700101000000Z)}",
            r"\pdftrailerid{<4C4C4D32465047415F53555256455931>}",
            r"\sloppy",
            r"\title{Executable LLM2FPGA Survey Evidence Report}",
            r"\author{}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
            r"\section{Question, scope, and amendment}",
            "The frozen protocol reconciles 459 to 461 source records without changing the study question or eligibility rules. Evidence: " + path("survey/protocol.md#lines=5-17") + ", " + path("survey/config/scope.yaml") + ", " + path("LLM-inference-on-FPGA-papers/data/catalog.json") + ", and " + path("survey/build/provenance.json") + ".",
            r"\section{Methods and corpus}",
            "Every record is retained in " + path("survey/build/records_normalized.csv") + "; duplicate lineage is in " + path("survey/build/duplicate_groups.csv") + "; and controlled decisions are in " + path("survey/data/screening_decisions.csv") + ". The final corpus is 461 source records, 456 unique works, and 5 duplicate manifestations. Final counts are A=30, B=57, C=75, D=68, X=231, with 230 included records and 231 exclusions; see " + path("survey/build/final_flow_counts.json") + ".",
            r"\section{Review and audit}",
            "The final grouping has 226 project families and the bounded review has 36 reviewed project-family/control rows. Evidence: " + path("survey/build/project_families.csv") + ", " + path("survey/build/deep_review.csv") + ", " + path("survey/build/artifact_inventory.csv") + ", and " + path("survey/build/repository_audit.csv") + ".",
            r"\section{Compatibility and MLIR/CIRCT}",
            "R1--R8 receipts are validated before reporting. R1 stops at RTL generation rather than passing RTL; see " + path("survey/compatibility/R1-mlir-circt/manifest.json") + ", " + path("survey/compatibility/R1-mlir-circt/commands.sh") + ", and " + path("survey/compatibility/R1-mlir-circt/stderr.log") + ". The source-faithful MLIR/CIRCT catalog is 3 projects x 20 canonical transformations = 60 assessed cells; see " + path("survey/build/mlir_circt_stage_matrix.csv") + ". H1 --- unsupported for the current route. H2 --- bounded/partial support only. H3 --- inconclusive. Evidence: " + path("survey/build/mlir_circt_stage_matrix.md#lines=90-94") + ".",
            r"\section{Selection result and limits}",
            "The decision matrix at " + path("survey/build/decision_matrix_scored.csv") + " yields NO\_PRIMARY\_ROUTE\_PASSED. Primary route: none. R1 is the ineligible next evidence-gathering route; R2 is an ineligible different-family hypothesis. The route selection rationale is " + path("survey/build/route_selection.md") + ". The target board remains unspecified, and no route is claimed as an eligible end-to-end causal-LM implementation.",
            r"\section{Reproduction}",
            r"Run \texttt{nix develop -c python -m unittest discover -s tests -p 'test\_survey\_*.py' -v}, then \texttt{nix develop -c python survey/scripts/build\_report.py --root . --out survey/build}. The pinned \path{flake.nix} and \path{flake.lock} development shell supplies the declared pdflatex command rather than a host-profile TeX installation. The renderer validates every evidence path, renders Mermaid source, invokes pdflatex twice, and records the transcript and PDF SHA-256.",
            r"\end{document}",
            "",
        )
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<OUTPUT_DIR>" if path.suffix == "" else f"<OUTPUT_DIR>/{path.name}"


def _portable_transcript(text: str, root: Path, out: Path) -> str:
    """Remove machine-local paths while retaining the compiler's diagnostic text."""

    portable = text.replace(str(root.resolve()), ".")
    portable = portable.replace(str(out.resolve()), "<OUTPUT_DIR>")
    portable = re.sub(
        r"(?<![A-Za-z0-9.])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._+@=-]*",
        "<LOCAL_PATH>",
        portable,
    )
    return "\n".join(line.rstrip() for line in portable.splitlines())


def _render_pdf(root: Path, out: Path, tex_path: Path) -> tuple[Path, str, dict[str, str]]:
    """Run the logical pdflatex command from the declared Nix environment."""

    out.mkdir(parents=True, exist_ok=True)
    out = out.resolve()
    tex_path = tex_path.resolve()
    if tex_path.parent != out:
        raise ValueError(
            "D16: LaTeX source must reside in the requested report output directory"
        )
    executable = shutil.which("pdflatex")
    declared_texlive = os.environ.get("SURVEY_DECLARED_TEXLIVE")
    resolved_executable = Path(executable).resolve() if executable else None
    declared_prefix = Path(declared_texlive).resolve() if declared_texlive else None
    if (
        resolved_executable is None
        or declared_prefix is None
        or not declared_prefix.is_relative_to("/nix/store")
        or not resolved_executable.is_relative_to(declared_prefix)
    ):
        raise ValueError(
            "D16: pdflatex must come from the declared Nix development environment"
        )
    command = (
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        ".",
        tex_path.name,
    )
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = "0"
    try:
        version_result = subprocess.run(
            ("pdflatex", "--version"),
            cwd=out,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise ValueError(
            "D16: pdflatex is unavailable; enter the declared Nix development environment"
        ) from error
    if version_result.returncode != 0 or not version_result.stdout.strip():
        raise ValueError("D16: pdflatex --version failed in the declared environment")
    version = _portable_transcript(version_result.stdout, root, out).splitlines()[0]
    transcript: list[str] = []
    for run in range(1, 3):
        try:
            result = subprocess.run(
                command,
                cwd=out,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise ValueError(
                "D16: pdflatex disappeared from the declared environment"
            ) from error
        stdout = _portable_transcript(result.stdout, root, out)
        stderr = _portable_transcript(result.stderr, root, out)
        if result.returncode == 0 and not _TEX_SUCCESS.search(stdout):
            raise ValueError(
                f"D16: pdflatex pass {run} did not report successful PDF output"
            )
        transcript.extend(
            (
                "# working directory: <OUTPUT_DIR>",
                _TEX_COMMAND,
                f"# pdflatex pass {run}",
                stdout,
                stderr,
            )
        )
        if result.returncode != 0:
            raise ValueError(f"D16: pdflatex pass {run} failed\n{result.stdout}\n{result.stderr}")
    transcript_text = "\n".join(transcript).rstrip() + "\n"
    if _TEX_FAILURE.search(transcript_text):
        raise ValueError("D16: pdflatex reported unresolved references or errors")
    pdf_path = out / "final_report.pdf"
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise ValueError("D16: pdflatex did not produce a non-empty PDF")
    if _ABSOLUTE_PATH.search(transcript_text):
        raise ValueError("D16: pdflatex transcript contains an absolute filesystem path")
    for suffix in (".aux", ".log", ".out", ".toc"):
        temporary = out / f"final_report{suffix}"
        if temporary.exists():
            temporary.unlink()
    return pdf_path, transcript_text, {
        "command": "pdflatex",
        "version": version,
        "environment": "declared-flake-texlive",
    }


def _validate_deterministic_pdf_replay(
    root: Path, latex: str, pdf_path: Path, transcript: str
) -> None:
    """Re-render D16 outside its output tree and compare deterministic bytes."""

    with TemporaryDirectory(prefix="survey-d16-pdf-") as directory:
        replay_out = Path(directory)
        replay_tex = replay_out / "final_report.tex"
        _write_text(replay_tex, latex)
        replay_pdf, replay_transcript, _ = _render_pdf(root, replay_out, replay_tex)
        _require(
            _sha256(replay_pdf) == _sha256(pdf_path),
            "D16",
            "PDF must exactly match the deterministic PDF replay",
        )
        _require(
            replay_transcript == transcript,
            "D16",
            "pdflatex transcript must exactly match the deterministic PDF replay",
        )


def _input_hashes(root: Path) -> dict[str, str]:
    return {relative: _sha256(_require_file(root, relative, "D16")) for relative in REPORT_INPUTS}


def build_report(root: Path = ROOT, out: Path | None = None) -> Path:
    """Render an offline report only after validating its complete evidence base."""

    root = root.resolve()
    out = (out or root / "survey/build").resolve()
    context = _validate_source_deliverables(root)
    _validate_report_generator_source_manifest(root)

    figures = write_figures(root, out)
    for path in figures.values():
        if not path.is_file():
            raise ValueError(f"D13: figure writer did not produce {path.name}")
    markdown_path = out / "final_report.md"
    tex_path = out / "final_report.tex"
    _write_text(markdown_path, _render_markdown(context))
    _write_text(tex_path, _render_latex(context))
    pdf_path, transcript, pdflatex = _render_pdf(root, out, tex_path)
    _write_text(out / "final_report_pdflatex.txt", transcript)

    generated_names = (
        "corpus_flow.mmd",
        "route_family_comparison.csv",
        "route_family_comparison.md",
        "timeline.mmd",
        "final_report.md",
        "final_report.tex",
    )
    retained = {name: _sha256(out / name) for name in HASHED_OUTPUTS}
    metadata: dict[str, object] = {
        "schema_version": 1,
        "pdflatex_runs": 2,
        "pdflatex": pdflatex,
        "pdf_sha256": retained["final_report.pdf"],
        "transcript_sha256": retained["final_report_pdflatex.txt"],
        "retained_sha256": retained,
        "input_sha256": _input_hashes(root),
        "generated_sha256": {name: _sha256(out / name) for name in generated_names},
    }
    metadata["metadata_sha256"] = _canonical_json_sha256(metadata)
    _write_text(
        out / "final_report_build.json",
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
    )
    _validate_generated_deliverables(root, out, context)
    return pdf_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    pdf = build_report(root, args.out)
    print(_display_path(root, pdf))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
