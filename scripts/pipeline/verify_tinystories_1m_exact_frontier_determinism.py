#!/usr/bin/env python3
"""Verify the two preserved live Task 5 determinism evidence bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
from typing import Any


_MODEL = "tiny-stories-1m-kev-gpt-exact"
_ALIAS = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake"
_REGISTERED_ORDER = [
    "pytorch-exported",
    "torch",
    "linalg",
    "scf",
    "flat-scf",
    "calyx",
    "calyx-native-sv",
]
_STAGES = ["pytorch-exported", "torch", "linalg", "scf"]
_NOT_RUN = ["flat-scf", "calyx", "calyx-native-sv"]
_DIAGNOSTIC = (
    "error: registered scf stage status is 'unavailable': "
    "baseline hardware pipeline lowers through CF and Handshake"
)
_SCF_MANIFEST = {
    "reason": "baseline hardware pipeline lowers through CF and Handshake",
    "stage": "scf",
    "status": "unavailable",
}
_CLASSIFIER = "scripts/pipeline/classify_tinystories_1m_exact_frontier.py"
_VERIFIER = "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py"
_SEMANTIC_VERIFIER = "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
_SEMANTIC_REPORT = "artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json"
_DECISION = "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"
_PREDECESSOR = (
    "artifacts/comparison/tinystories-1m-exact-frontier-determinism/run-1/receipt.json"
)
_FROZEN_IDENTITIES = {
    "adapter_sha256": "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e",
    "contract_sha256": "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c",
    "package_manifest_sha256": "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35",
    "task_1_audit_file_sha256": "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd",
    "task_1_audit_payload_sha256": "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766",
    "task_2_artifact_file_sha256": "173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a",
    "task_2_artifact_sha256": "af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838",
    "task_2_model_receipt_sha256": "5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834",
    "task_3_generation_artifact_sha256": "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3",
    "task_3_generation_file_sha256": "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3",
    "task_3_generation_result_sha256": "c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644",
}
_DECISION_SELF_SHA256 = "429da5a367755d35bc38308589beaf25d291a8272ebf4d8944bfa4b8919ef8fe"
_PREDECESSOR_FILE_SHA256 = "b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55"
_PREDECESSOR_SELF_SHA256 = "af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b"
_V5_SOURCE_COMMIT = "c22c5f8d85e453a56b185f6238970933f5b1d407"
_ACCEPTED_TASK4_COMMIT = "7eed3592a661c0cb3c417dc59b29839266446b2d"
_REGISTRATION_COMMIT = "3314a70ac1cfe0e998f445162d1a2b5ae8398a20"
_RESIDUAL_DIAGNOSTIC = (
    "error: registered flat-scf stage completed with residuals; "
    "artifact remains rejected"
)
_CRITICAL_INPUTS = (
    "TinyStories/model_adapter_exact_package.py",
    "artifacts/reference/tinystories-1m-exact-generation.json",
    "artifacts/reference/tinystories-1m-exact-input-audit.json",
    "artifacts/reference/tinystories-1m-exact-input-contract.json",
    "artifacts/reference/tinystories-1m-exact-package-model.json",
    "docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
    "flake.lock",
    "flake.nix",
    "nix/models.nix",
    "nix/pipeline.nix",
    "scripts/compile-pytorch.py",
    "scripts/materialize-pytorch-exported.py",
)
_V5_TOP_KEYS = {
    "capture_tools",
    "claims",
    "diagnostic",
    "frontier",
    "frontier_evidence",
    "frozen_task_1_through_3_identities",
    "full_failing_input",
    "model",
    "pipeline_execution",
    "pipeline_source_identity",
    "predecessor_receipt",
    "registered_build_execution",
    "schema",
    "semantic_gate",
    "sha256",
    "source_commit",
    "stage",
    "stages",
    "status",
    "task_2_decision_self_sha256",
}
_V5_CLAIMS = {
    "backend_model_quantization_ddr_pcie_changed": False,
    "board_inference": False,
    "calyx_native_sv": False,
    "functional_equivalence": False,
    "resource_or_timing": False,
    "syntax_validated": False,
    "synthesis_validated": False,
}
_V5_PIPELINE_EXECUTION_KEYS = {
    "first_invalid_stage",
    "not_run",
    "registered_order",
    "stopped_after_first_invalid_stage",
}
_V5_STAGE_KEYS = {
    "artifact",
    "artifact_accepted",
    "artifact_bytes",
    "artifact_sha256",
    "command",
    "exit_code",
    "log",
    "log_bytes",
    "log_sha256",
    "stage",
    "status",
    "terminal_diagnostics",
    "tool_revisions",
    "upstream_identity",
}
_V5_TOOL_REVISION_KEYS = {
    "build_command_sha256",
    "derivation",
    "derivation_file_sha256",
    "derivation_json_sha256",
    "evidence_source_commit",
}
_V5_EXECUTION_KEYS = {
    "artifact",
    "artifact_accepted",
    "artifact_bytes",
    "artifact_sha256",
    "attribute",
    "backend",
    "captured_derivation",
    "captured_derivation_bytes",
    "captured_derivation_json",
    "captured_derivation_json_bytes",
    "captured_derivation_json_sha256",
    "captured_derivation_sha256",
    "command",
    "derivation",
    "derivation_build_command",
    "derivation_build_command_sha256",
    "derivation_file_sha256",
    "derivation_json_sha256",
    "derivation_tool_bindings",
    "exit_code",
    "frontend",
    "invoked",
    "log",
    "log_bytes",
    "log_sha256",
    "result",
    "route_alias",
}
_V5_FULL_INPUT_KEYS = {
    "archive_bytes",
    "archive_sha256",
    "content_bytes",
    "content_sha256",
    "path",
    "source_artifact",
    "source_stage",
}
_V5_FRONTIER_KEYS = {
    "blockers",
    "kind",
    "manifest",
    "minimization",
    "operation",
    "residual_artifact",
    "types",
}
_V5_MANIFEST_BINDING_KEYS = {
    "artifact",
    "blockers",
    "bytes",
    "path",
    "reason",
    "sha256",
    "stage",
    "status",
}
_V5_FILE_BINDING_KEYS = {"bytes", "path", "sha256"}
_V5_MINIMIZATION_KEYS = {"reason", "status"}
_V5_SOURCE_KEYS = {
    "accepted_task4_commit",
    "critical_inputs",
    "critical_inputs_clean",
    "evidence_source_commit",
    "export_derivation",
    "flake_archive_nar_hash",
    "flake_archive_path",
    "flake_archive_source",
    "task4_is_ancestor",
    "torch_derivation",
}
_V5_CRITICAL_INPUT_KEYS = {
    "authenticated_blob",
    "authenticated_commit",
    "authenticated_sha256",
    "evidence_blob",
    "flake_archive_path",
    "flake_archive_sha256",
    "task4_blob",
    "task4_sha256",
    "workspace_sha256",
}
_V5_EVALUATED_CRITICAL_INPUTS = {
    "TinyStories/model_adapter_exact_package.py",
    "artifacts/reference/tinystories-1m-exact-generation.json",
    "artifacts/reference/tinystories-1m-exact-input-audit.json",
    "artifacts/reference/tinystories-1m-exact-input-contract.json",
    "artifacts/reference/tinystories-1m-exact-package-model.json",
    "docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
    "scripts/compile-pytorch.py",
    "scripts/materialize-pytorch-exported.py",
}
_V5_DERIVATION_IDENTITY_KEYS = {
    "attribute",
    "build_command",
    "build_command_sha256",
    "build_inputs",
    "canonical_json",
    "file_sha256",
    "input_derivations",
    "input_sources",
    "json_sha256",
    "output",
    "path",
}
_V5_SEMANTIC_GATE_KEYS = {
    "command",
    "evidence",
    "probe_report",
    "probe_report_sha256",
    "status",
    "verifier",
    "verifier_sha256",
}
_V5_SEMANTIC_EVIDENCE_KEYS = {"contract", "registered_stage", "semantic_probe"}
_V5_SEMANTIC_CONTRACT_KEYS = {
    "decision_sha256",
    "fixture_file_sha256",
    "fixture_self_hash",
    "rejected_cases",
    "shift_one_output",
    "valid_cases",
}
_V5_SEMANTIC_REGISTERED_KEYS = {"stage_artifact_sha256", "status"}
_V5_SEMANTIC_PROBE_KEYS = {
    "probe_report_sha256",
    "stage_artifact",
    "stage_artifact_sha256",
    "status",
}
_V5_BUNDLE_MANIFEST_KEYS = {
    "canonical_files",
    "expected_comparison",
    "runs",
    "schema",
    "source_commit",
}
_V1_CANONICAL_FILES = (
    "receipt.json",
    "pytorch-exported-build.log",
    "torch-mlir.log",
    "compiler-import-capture.log",
)
_V2_LEGACY_CANONICAL_FILES = (
    "receipt.json",
    "pytorch-exported.log",
    "torch.log",
    "linalg.log",
    "scf.log",
    "full-input.gz",
    "minimal-reproducer.json",
)
_V2_CURRENT_CANONICAL_FILES = (
    *_V2_LEGACY_CANONICAL_FILES,
    "linalg.drv",
    "linalg.derivation.json",
    "scf.drv",
    "scf.derivation.json",
)
_RUN_METADATA_FILES: frozenset[str] = frozenset()
_LEGACY_V3_SOURCE_COMMIT = "aec02920481bf9fc4650062f74191fde4943ce3a"


class VerificationError(RuntimeError):
    """Raised when preserved determinism evidence is incomplete or inconsistent."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _require_json_dict(value: object, context: str) -> dict[str, Any]:
    _require(type(value) is dict, f"{context}: JSON type mismatch; expected object")
    return value


def _require_json_list(value: object, context: str) -> list[Any]:
    _require(type(value) is list, f"{context}: JSON type mismatch; expected array")
    return value


def _require_json_str(value: object, context: str) -> str:
    _require(type(value) is str, f"{context}: JSON type mismatch; expected string")
    return value


def _require_json_bool(value: object, context: str) -> bool:
    _require(type(value) is bool, f"{context}: JSON type mismatch; expected boolean")
    return value


def _require_json_int(
    value: object, context: str, *, nonnegative: bool = True
) -> int:
    _require(type(value) is int, f"{context}: JSON type mismatch; expected integer")
    _require(
        not nonnegative or value >= 0,
        f"{context}: JSON type/range mismatch; expected nonnegative integer",
    )
    return value


def _require_json_null(value: object, context: str) -> None:
    _require(value is None, f"{context}: JSON type mismatch; expected null")


def _require_json_str_list(value: object, context: str) -> list[str]:
    items = _require_json_list(value, context)
    for index, item in enumerate(items):
        _require_json_str(item, f"{context}[{index}]")
    return items


def _require_json_int_list(value: object, context: str) -> list[int]:
    items = _require_json_list(value, context)
    for index, item in enumerate(items):
        _require_json_int(item, f"{context}[{index}]", nonnegative=False)
    return items


def _require_json_str_fields(
    value: dict[str, Any], fields: set[str], context: str
) -> None:
    for field in fields:
        _require_json_str(value.get(field), f"{context}.{field}")


def _require_json_int_fields(
    value: dict[str, Any], fields: set[str], context: str
) -> None:
    for field in fields:
        _require_json_int(value.get(field), f"{context}.{field}")


def _require_exact_keys(
    value: object, expected: set[str], context: str
) -> dict[str, Any]:
    mapping = _require_json_dict(value, context)
    _require(
        set(mapping) == expected,
        f"{context}: exact schema keys mismatch",
    )
    return mapping


def _verify_v5_schema(receipt: dict[str, Any], run_name: str) -> None:
    """Reject every missing, unversioned, or mistyped v5 field."""

    _require_exact_keys(receipt, _V5_TOP_KEYS, f"{run_name}: receipt schema")
    _require_json_str_fields(
        receipt,
        {
            "diagnostic",
            "frontier",
            "model",
            "schema",
            "sha256",
            "source_commit",
            "stage",
            "status",
            "task_2_decision_self_sha256",
        },
        f"{run_name}: receipt",
    )
    capture_tools = _require_exact_keys(
        receipt.get("capture_tools"),
        {"classifier", "determinism_verifier"},
        f"{run_name}: capture tools schema",
    )
    for name in ("classifier", "determinism_verifier"):
        tool = _require_exact_keys(
            capture_tools.get(name), {"path", "sha256"}, f"{run_name}: {name} schema"
        )
        _require_json_str_fields(tool, {"path", "sha256"}, f"{run_name}: {name}")

    claims = _require_exact_keys(
        receipt.get("claims"), set(_V5_CLAIMS), f"{run_name}: claims schema"
    )
    for name, value in claims.items():
        _require_json_bool(value, f"{run_name}: claims.{name}")
    identities = _require_exact_keys(
        receipt.get("frozen_task_1_through_3_identities"),
        set(_FROZEN_IDENTITIES),
        f"{run_name}: frozen identity schema",
    )
    _require_json_str_fields(
        identities, set(_FROZEN_IDENTITIES), f"{run_name}: frozen identity"
    )
    predecessor = _require_exact_keys(
        receipt.get("predecessor_receipt"),
        {"file_sha256", "historical_bundle", "self_sha256"},
        f"{run_name}: predecessor identity schema",
    )
    _require_json_str_fields(
        predecessor,
        {"file_sha256", "historical_bundle", "self_sha256"},
        f"{run_name}: predecessor identity",
    )

    semantic = _require_exact_keys(
        receipt.get("semantic_gate"),
        _V5_SEMANTIC_GATE_KEYS,
        f"{run_name}: semantic gate schema",
    )
    _require_json_str_fields(
        semantic,
        _V5_SEMANTIC_GATE_KEYS - {"evidence"},
        f"{run_name}: semantic gate",
    )
    evidence = _require_exact_keys(
        semantic.get("evidence"),
        _V5_SEMANTIC_EVIDENCE_KEYS,
        f"{run_name}: semantic evidence schema",
    )
    contract = _require_exact_keys(
        evidence.get("contract"),
        _V5_SEMANTIC_CONTRACT_KEYS,
        f"{run_name}: semantic contract schema",
    )
    _require_json_str_fields(
        contract,
        {"decision_sha256", "fixture_file_sha256", "fixture_self_hash"},
        f"{run_name}: semantic contract",
    )
    _require_json_str_list(
        contract.get("rejected_cases"), f"{run_name}: semantic contract.rejected_cases"
    )
    _require_json_str_list(
        contract.get("valid_cases"), f"{run_name}: semantic contract.valid_cases"
    )
    _require_json_int_list(
        contract.get("shift_one_output"),
        f"{run_name}: semantic contract.shift_one_output",
    )
    registered_stage = _require_exact_keys(
        evidence.get("registered_stage"),
        _V5_SEMANTIC_REGISTERED_KEYS,
        f"{run_name}: semantic registered-stage schema",
    )
    _require_json_str_fields(
        registered_stage,
        _V5_SEMANTIC_REGISTERED_KEYS,
        f"{run_name}: semantic registered-stage",
    )
    semantic_probe = _require_exact_keys(
        evidence.get("semantic_probe"),
        _V5_SEMANTIC_PROBE_KEYS,
        f"{run_name}: semantic probe schema",
    )
    _require_json_str_fields(
        semantic_probe, _V5_SEMANTIC_PROBE_KEYS, f"{run_name}: semantic probe"
    )

    pipeline = _require_exact_keys(
        receipt.get("pipeline_execution"),
        _V5_PIPELINE_EXECUTION_KEYS,
        f"{run_name}: pipeline execution schema",
    )
    _require_json_str(
        pipeline.get("first_invalid_stage"),
        f"{run_name}: pipeline execution.first_invalid_stage",
    )
    _require_json_str_list(
        pipeline.get("registered_order"),
        f"{run_name}: pipeline execution.registered_order",
    )
    _require_json_str_list(
        pipeline.get("not_run"), f"{run_name}: pipeline execution.not_run"
    )
    _require_json_bool(
        pipeline.get("stopped_after_first_invalid_stage"),
        f"{run_name}: pipeline execution.stopped_after_first_invalid_stage",
    )
    stages = _require_json_list(receipt.get("stages"), f"{run_name}: stages")
    for index, record in enumerate(stages):
        context = f"{run_name}: stage {index}"
        stage = _require_exact_keys(
            record, _V5_STAGE_KEYS, f"{context} schema"
        )
        _require_json_str_fields(
            stage,
            {
                "artifact",
                "artifact_sha256",
                "command",
                "log",
                "log_sha256",
                "stage",
                "status",
                "upstream_identity",
            },
            context,
        )
        _require_json_bool(stage.get("artifact_accepted"), f"{context}.artifact_accepted")
        _require_json_int_fields(stage, {"artifact_bytes", "exit_code", "log_bytes"}, context)
        _require_json_str_list(
            stage.get("terminal_diagnostics"), f"{context}.terminal_diagnostics"
        )
        revisions = _require_exact_keys(
            stage.get("tool_revisions"),
            _V5_TOOL_REVISION_KEYS,
            f"{context} tool revision schema",
        )
        _require_json_str_fields(
            revisions, _V5_TOOL_REVISION_KEYS, f"{context} tool revision"
        )

    execution = _require_json_dict(
        receipt.get("registered_build_execution"), f"{run_name}: execution"
    )
    for stage_name, value in execution.items():
        context = f"{run_name}: {stage_name} execution"
        run = _require_exact_keys(
            value, _V5_EXECUTION_KEYS, f"{context} schema"
        )
        _require_json_str_fields(
            run,
            {
                "artifact",
                "artifact_sha256",
                "attribute",
                "backend",
                "captured_derivation",
                "captured_derivation_json",
                "captured_derivation_json_sha256",
                "captured_derivation_sha256",
                "command",
                "derivation",
                "derivation_build_command",
                "derivation_build_command_sha256",
                "derivation_file_sha256",
                "derivation_json_sha256",
                "frontend",
                "log",
                "log_sha256",
                "result",
                "route_alias",
            },
            context,
        )
        for name in ("artifact_accepted", "invoked"):
            _require_json_bool(run.get(name), f"{context}.{name}")
        _require_json_int_fields(
            run,
            {
                "artifact_bytes",
                "captured_derivation_bytes",
                "captured_derivation_json_bytes",
                "exit_code",
                "log_bytes",
            },
            context,
        )
        bindings = _require_json_list(
            run.get("derivation_tool_bindings"), f"{context}.derivation_tool_bindings"
        )
        for index, binding in enumerate(bindings):
            tool_binding = _require_exact_keys(
                binding,
                {"bytes", "path", "sha256"},
                f"{context} tool binding {index} schema",
            )
            _require_json_int(
                tool_binding.get("bytes"), f"{context} tool binding {index}.bytes"
            )
            _require_json_str_fields(
                tool_binding,
                {"path", "sha256"},
                f"{context} tool binding {index}",
            )

    full = _require_exact_keys(
        receipt.get("full_failing_input"),
        _V5_FULL_INPUT_KEYS,
        f"{run_name}: full input schema",
    )
    _require_json_int_fields(
        full,
        {"archive_bytes", "content_bytes"},
        f"{run_name}: full input",
    )
    _require_json_str_fields(
        full,
        {"archive_sha256", "content_sha256", "path", "source_artifact", "source_stage"},
        f"{run_name}: full input",
    )
    frontier = _require_exact_keys(
        receipt.get("frontier_evidence"),
        _V5_FRONTIER_KEYS,
        f"{run_name}: frontier evidence schema",
    )
    _require_json_str(frontier.get("kind"), f"{run_name}: frontier evidence.kind")
    _require_json_null(frontier.get("operation"), f"{run_name}: frontier evidence.operation")
    _require_json_null(frontier.get("types"), f"{run_name}: frontier evidence.types")
    manifest = _require_exact_keys(
        frontier.get("manifest"),
        _V5_MANIFEST_BINDING_KEYS,
        f"{run_name}: frontier manifest schema",
    )
    _require_json_str_fields(
        manifest,
        {"artifact", "blockers", "path", "sha256", "stage", "status"},
        f"{run_name}: frontier manifest",
    )
    _require_json_int(manifest.get("bytes"), f"{run_name}: frontier manifest.bytes")
    _require_json_null(manifest.get("reason"), f"{run_name}: frontier manifest.reason")
    for name in ("residual_artifact", "blockers"):
        binding = _require_exact_keys(
            frontier.get(name),
            _V5_FILE_BINDING_KEYS,
            f"{run_name}: frontier {name} schema",
        )
        _require_json_int(binding.get("bytes"), f"{run_name}: frontier {name}.bytes")
        _require_json_str_fields(
            binding, {"path", "sha256"}, f"{run_name}: frontier {name}"
        )
    minimization = _require_exact_keys(
        frontier.get("minimization"),
        _V5_MINIMIZATION_KEYS,
        f"{run_name}: frontier minimization schema",
    )
    _require_json_str_fields(
        minimization, _V5_MINIMIZATION_KEYS, f"{run_name}: frontier minimization"
    )

    source = _require_exact_keys(
        receipt.get("pipeline_source_identity"),
        _V5_SOURCE_KEYS,
        f"{run_name}: pipeline source identity schema",
    )
    _require_json_str_fields(
        source,
        {
            "accepted_task4_commit",
            "evidence_source_commit",
            "flake_archive_nar_hash",
            "flake_archive_path",
            "flake_archive_source",
        },
        f"{run_name}: pipeline source identity",
    )
    for name in ("critical_inputs_clean", "task4_is_ancestor"):
        _require_json_bool(
            source.get(name), f"{run_name}: pipeline source identity.{name}"
        )
    critical = _require_json_dict(
        source.get("critical_inputs"), f"{run_name}: critical inputs"
    )
    _require(
        set(critical) == set(_CRITICAL_INPUTS),
        f"{run_name}: critical input schema mismatch",
    )
    for path, binding in critical.items():
        expected = set(_V5_CRITICAL_INPUT_KEYS)
        if path in _V5_EVALUATED_CRITICAL_INPUTS:
            expected.update({"derivation_store_path", "derivation_store_sha256"})
        critical_binding = _require_exact_keys(
            binding, expected, f"{run_name}: critical input {path} schema"
        )
        _require_json_str_fields(
            critical_binding, expected, f"{run_name}: critical input {path}"
        )
    for name in ("export_derivation", "torch_derivation"):
        derivation = _require_exact_keys(
            source.get(name),
            _V5_DERIVATION_IDENTITY_KEYS,
            f"{run_name}: {name} source identity schema",
        )
        _require_json_str_fields(
            derivation,
            _V5_DERIVATION_IDENTITY_KEYS - {"input_derivations", "input_sources"},
            f"{run_name}: {name} source identity",
        )
        _require_json_str_list(
            derivation.get("input_derivations"),
            f"{run_name}: {name} source identity.input_derivations",
        )
        _require_json_str_list(
            derivation.get("input_sources"),
            f"{run_name}: {name} source identity.input_sources",
        )


def _verify_v5_bundle_manifest_schema(manifest: dict[str, Any]) -> None:
    _require_exact_keys(manifest, _V5_BUNDLE_MANIFEST_KEYS, "v5 bundle manifest schema")
    _require_json_str_fields(
        manifest, {"schema", "source_commit"}, "v5 bundle manifest"
    )
    _require_json_str_list(
        manifest.get("canonical_files"), "v5 bundle manifest.canonical_files"
    )
    expected = _require_exact_keys(
        manifest.get("expected_comparison"),
        {"byte_identical", "first_invalid_stage", "receipt_file_sha256", "receipt_self_hash"},
        "v5 bundle expected comparison schema",
    )
    _require_json_bool(
        expected.get("byte_identical"),
        "v5 bundle expected comparison.byte_identical",
    )
    _require_json_str_fields(
        expected,
        {"first_invalid_stage", "receipt_file_sha256", "receipt_self_hash"},
        "v5 bundle expected comparison",
    )
    runs = _require_json_dict(manifest.get("runs"), "v5 bundle manifest.runs")
    for run_name, value in runs.items():
        run = _require_exact_keys(
            value,
            {"files", "receipt_self_hash", "source_commit"},
            f"{run_name}: run manifest schema",
        )
        _require_json_str_fields(
            run, {"receipt_self_hash", "source_commit"}, f"{run_name}: run manifest"
        )
        files = _require_json_dict(run.get("files"), f"{run_name}: file manifest")
        for filename, value in files.items():
            binding = _require_exact_keys(
                value,
                {"bytes", "sha256"},
                f"{run_name}: file manifest {filename} schema",
            )
            _require_json_int(
                binding.get("bytes"), f"{run_name}: file manifest {filename}.bytes"
            )
            _require_json_str(
                binding.get("sha256"), f"{run_name}: file manifest {filename}.sha256"
            )


def _canonical_receipt_hash(receipt: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load JSON evidence {path}: {error}") from error
    if type(value) is not dict:
        raise VerificationError(f"JSON evidence must be an object: {path}")
    return value


def _enumerate_run_files(run_root: Path, run_name: str) -> set[str]:
    """Enumerate one run without following links and reject non-regular entries."""

    try:
        root_mode = run_root.lstat().st_mode
    except OSError as error:
        raise VerificationError(f"missing preserved run directory: {run_name}") from error
    _require(
        stat.S_ISDIR(root_mode) and not run_root.is_symlink(),
        f"{run_name}: run root must be a real directory",
    )
    actual_files: set[str] = set()
    try:
        entries = list(run_root.iterdir())
    except OSError as error:
        raise VerificationError(f"{run_name}: cannot enumerate run directory: {error}") from error
    for entry in entries:
        try:
            mode = entry.lstat().st_mode
        except OSError as error:
            raise VerificationError(f"{run_name}: cannot inspect {entry.name}: {error}") from error
        _require(
            not stat.S_ISLNK(mode) and stat.S_ISREG(mode),
            f"{run_name}: run directory contents must be regular files: {entry.name}",
        )
        actual_files.add(entry.name)
    return actual_files


def _verify_run_directory(
    run_root: Path, run_name: str, canonical_files: tuple[str, ...]
) -> None:
    """Enforce one run's exact schema-defined regular-file set."""

    actual_files = _enumerate_run_files(run_root, run_name)
    expected_files = set(canonical_files) | _RUN_METADATA_FILES
    _require(
        actual_files == expected_files,
        f"{run_name}: run directory contents mismatch: "
        f"expected {sorted(expected_files)}, found {sorted(actual_files)}",
    )


def _run(command: list[str], repo_root: Path) -> str:
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    if result.returncode != 0:
        raise VerificationError(
            f"independent command failed ({result.returncode}): {shlex.join(command)}\n"
            f"{result.stderr}"
        )
    return result.stdout


def _registered_attribute(stage: str) -> str:
    return f"{_MODEL}-pytorch-exported" if stage == "pytorch-exported" else f"{_ALIAS}-{stage}"


def _canonicalize_execution_text(
    value: str,
    ephemeral_paths: dict[str, str] | None = None,
    *,
    drop_git_dirty_warning: bool = False,
    drop_nix_progress: bool = False,
) -> str:
    canonical = value
    for actual, placeholder in sorted(
        (ephemeral_paths or {}).items(), key=lambda item: len(item[0]), reverse=True
    ):
        canonical = canonical.replace(actual, placeholder)
    lines = [line.rstrip() for line in canonical.splitlines()]
    if drop_git_dirty_warning:
        lines = [line for line in lines if not line.startswith("warning: Git tree ")]
    if drop_nix_progress:
        filtered: list[str] = []
        in_store_path_list = False
        for line in lines:
            if re.fullmatch(
                r"(?:this derivation|these \d+ derivations|these paths) will be (?:built|fetched):",
                line,
            ):
                in_store_path_list = True
                continue
            if in_store_path_list and re.fullmatch(r"  /nix/store/\S+", line):
                continue
            in_store_path_list = False
            if re.fullmatch(
                r"(?:building|copying path) '/nix/store/[^']+'(?: from '\S+')?\.\.\.",
                line,
            ):
                continue
            filtered.append(line)
        lines = filtered
    return "\n".join(lines)


def _canonical_execution_evidence(
    receipt_command: list[str],
    result: subprocess.CompletedProcess[str],
    ephemeral_paths: dict[str, str] | None = None,
) -> bytes:
    command = _canonicalize_execution_text(shlex.join(receipt_command), ephemeral_paths)
    stdout = _canonicalize_execution_text(
        result.stdout, ephemeral_paths, drop_git_dirty_warning=True
    )
    stderr = _canonicalize_execution_text(
        result.stderr,
        ephemeral_paths,
        drop_git_dirty_warning=True,
        drop_nix_progress=True,
    )
    payload = f"$ {command}\nexit_code: {result.returncode}\n--- stdout ---\n"
    if stdout:
        payload += stdout + "\n"
    payload += "--- stderr ---\n"
    if stderr:
        payload += stderr + "\n"
    return payload.encode()


def _expected_v5_replay_log(
    stage: str, live: dict[str, Any], *, residual_rejected: bool = False
) -> bytes:
    """Reconstruct classifier validation appended after the raw registered build log."""

    raw = live.get("log_bytes")
    _require(isinstance(raw, bytes), f"{stage}: live replay log missing")
    if not residual_rejected:
        return raw
    _require(stage == "flat-scf", "residual replay validation is only valid at flat-scf")

    artifact = live.get("artifact_bytes")
    _require(isinstance(artifact, bytes), "flat-scf: live manifest bytes missing")
    try:
        manifest = json.loads(artifact)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"flat-scf: live residual manifest is invalid: {error}") from error
    _require(
        isinstance(manifest, dict)
        and set(manifest) == {"artifact", "blockers", "stage", "status"}
        and manifest.get("artifact") == "flat.scf.mlir"
        and manifest.get("blockers") == "blockers.json"
        and manifest.get("stage") == "flat-scf"
        and manifest.get("status") == "completed-with-residuals",
        "flat-scf: live residual manifest contract mismatch",
    )
    prefix = raw if not raw or raw.endswith(b"\n") else raw + b"\n"
    return prefix + (
        b"--- classifier validation ---\n"
        b"error: registered flat-scf stage completed with residuals; "
        b"artifact remains rejected\n"
    )


def _build_command_file_bindings(build_command: str) -> list[dict[str, Any]]:
    candidates = re.findall(
        r"/nix/store/[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._?=/:-]+)?",
        build_command,
    )
    result: list[dict[str, Any]] = []
    for value in sorted(set(candidates)):
        path = Path(value.rstrip("'\"),;"))
        if path.is_file():
            data = path.read_bytes()
            result.append(
                {"path": str(path), "bytes": len(data), "sha256": _sha256_bytes(data)}
            )
    return result


def _live_derivation(
    repo_root: Path,
    stage: str,
    flake_reference: str = ".",
    attribute: str | None = None,
) -> dict[str, Any]:
    attribute = attribute or f"{_MODEL}-{stage}"
    document = json.loads(
        _run(
            ["nix", "derivation", "show", f"{flake_reference}#{attribute}"],
            repo_root,
        )
    )
    derivations = document.get("derivations", {})
    _require(len(derivations) == 1, f"{stage}: live derivation count mismatch")
    basename, derivation = next(iter(derivations.items()))
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    drv = Path("/nix/store") / basename
    drv_bytes = drv.read_bytes()
    output_name = derivation.get("outputs", {}).get("out", {}).get("path")
    _require(isinstance(output_name, str), f"{stage}: live output missing")
    build_command = str(derivation.get("env", {}).get("buildCommand", ""))
    input_data = derivation.get("inputs", {})
    receipt_derivation = {
        "attribute": attribute,
        "path": str(drv),
        "file_sha256": _sha256_bytes(drv_bytes),
        "json_sha256": _sha256_bytes(canonical),
        "canonical_json": canonical.decode("utf-8"),
        "output": f"/nix/store/{output_name}",
        "build_command": build_command,
        "build_command_sha256": _sha256_bytes(build_command.encode()),
        "build_inputs": str(derivation.get("env", {}).get("buildInputs", "")),
        "input_derivations": sorted(
            f"/nix/store/{name}" for name in input_data.get("drvs", {})
        ),
        "input_sources": sorted(
            f"/nix/store/{name}" for name in input_data.get("srcs", [])
        ),
    }
    return {
        "attribute": attribute,
        "path": str(drv),
        "file_bytes": drv_bytes,
        "file_sha256": _sha256_bytes(drv_bytes),
        "canonical_json": canonical,
        "json_sha256": _sha256_bytes(canonical),
        "output": f"/nix/store/{output_name}",
        "build_command": build_command,
        "build_command_sha256": _sha256_bytes(build_command.encode()),
        "tool_bindings": _build_command_file_bindings(build_command),
        "receipt_derivation": receipt_derivation,
    }


def _primary_artifact(stage: str, output: Path) -> Path:
    if stage == "pytorch-exported":
        return output / "exported.pt2"
    if stage in {"torch", "linalg", "scf"}:
        return output
    if stage == "flat-scf":
        return output / "flat.scf.mlir"
    if stage == "calyx":
        return output / "model.calyx.mlir"
    if stage == "calyx-native-sv":
        return output / "sv" / "main.sv"
    raise VerificationError(f"unregistered stage: {stage}")


def _git_source_bytes(repo_root: Path, source_commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{source_commit}:{path}"], cwd=repo_root, capture_output=True
    )
    _require(result.returncode == 0, f"source commit lacks {path}")
    return result.stdout


def _git_object(repo_root: Path, revision: str) -> tuple[str, str]:
    resolved = _run(["git", "rev-parse", revision], repo_root).strip()
    object_type = _run(["git", "cat-file", "-t", resolved], repo_root).strip()
    return resolved, object_type


def _verify_pinned_v5_source_commit(
    repo_root: Path, source_commit: object, context: str
) -> None:
    _require(
        source_commit == _V5_SOURCE_COMMIT,
        f"{context}: producer source commit is not the pinned c22 commit",
    )
    resolved, object_type = _git_object(repo_root, str(source_commit))
    _require(
        resolved == _V5_SOURCE_COMMIT and object_type == "commit",
        f"{context}: producer source object is not the pinned commit",
    )
    for ancestor, label in (
        (_ACCEPTED_TASK4_COMMIT, "accepted Task 4"),
        (_REGISTRATION_COMMIT, "registered route"),
    ):
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, resolved],
            cwd=repo_root,
            capture_output=True,
        )
        _require(result.returncode == 0, f"{context}: producer lacks {label} ancestry")


def _authenticate_v5_pipeline_source(
    receipt: dict[str, Any], trust: dict[str, Any], run_name: str
) -> None:
    repo_root = trust["repo_root"]
    source_commit = receipt.get("source_commit")
    _verify_pinned_v5_source_commit(repo_root, source_commit, run_name)

    source = receipt.get("pipeline_source_identity")
    expected_source = trust.get("pipeline_source_identity")
    _require(
        isinstance(source, dict) and isinstance(expected_source, dict),
        f"{run_name}: pipeline source identity missing",
    )
    _require(
        source == expected_source,
        f"{run_name}: exact pipeline source identity mismatch",
    )


def _independent_v5_trust(
    repo_root: Path, source_commit: str, executed_stages: list[str]
) -> dict[str, Any]:
    """Replay the semantic gate first, then every registered alias derivation."""

    semantic_command = [
        "nix",
        "develop",
        "-c",
        "python",
        _SEMANTIC_VERIFIER,
        "--probe-report",
        _SEMANTIC_REPORT,
    ]
    semantic_evidence = json.loads(_run(semantic_command, repo_root))
    decision = _load_json(repo_root / _DECISION)
    _require(
        decision.get("identity_hashes") == _FROZEN_IDENTITIES,
        "live frozen Task 1-3 identities changed",
    )
    _require(
        decision.get("sha256") == _DECISION_SELF_SHA256,
        "live Task 2 decision identity changed",
    )
    predecessor_path = repo_root / _PREDECESSOR
    predecessor = _load_json(predecessor_path)
    _require(
        _sha256_bytes(predecessor_path.read_bytes()) == _PREDECESSOR_FILE_SHA256,
        "live predecessor file identity changed",
    )
    _require(
        predecessor.get("sha256") == _PREDECESSOR_SELF_SHA256,
        "live predecessor self identity changed",
    )
    source_flake = f"git+file://{repo_root}?rev={source_commit}"
    derivations: dict[str, dict[str, Any]] = {}
    for stage in executed_stages:
        attribute = _registered_attribute(stage)
        live = _live_derivation(
            repo_root, stage, source_flake, attribute=attribute
        )
        actual_command = [
            "nix",
            "build",
            "--no-link",
            "--print-out-paths",
            "-L",
            f"{source_flake}#{attribute}",
        ]
        receipt_command = [
            "nix",
            "build",
            "--no-link",
            "--print-out-paths",
            "-L",
            f".#{attribute}",
        ]
        result = subprocess.run(
            actual_command, cwd=repo_root, text=True, capture_output=True
        )
        live.update(
            {
                "exit_code": result.returncode,
                "log_bytes": _canonical_execution_evidence(receipt_command, result),
                "result": live["output"] if result.returncode == 0 else None,
            }
        )
        output = Path(live["output"])
        if result.returncode == 0:
            manifest = output / "manifest.json" if output.is_dir() else None
            artifact = (
                manifest
                if stage in {"scf", "flat-scf", "calyx", "calyx-native-sv"}
                and manifest is not None
                and manifest.is_file()
                else _primary_artifact(stage, output)
            )
            live["artifact_bytes"] = artifact.read_bytes()
            live["artifact_path"] = str(artifact)
            if stage == "flat-scf" and output.is_dir():
                residual_payloads: dict[str, dict[str, object]] = {}
                for filename in ("flat.scf.mlir", "blockers.json"):
                    payload = output / filename
                    if payload.is_file() and not payload.is_symlink():
                        payload_bytes = payload.read_bytes()
                        residual_payloads[filename] = {
                            "path": str(payload),
                            "bytes": payload_bytes,
                            "sha256": _sha256_bytes(payload_bytes),
                        }
                live["residual_payloads"] = residual_payloads
        derivations[stage] = live
        if result.returncode != 0:
            break
    archive_document = json.loads(
        _run(["nix", "flake", "archive", "--json", source_flake], repo_root)
    )
    archive = Path(archive_document["path"])
    archive_nar_hash = _run(["nix", "hash", "path", str(archive)], repo_root).strip()
    evaluated_sources = {
        "scripts/compile-pytorch.py": ("torch", "-compile-pytorch.py", None),
        "scripts/materialize-pytorch-exported.py": (
            "pytorch-exported",
            "-materialize-pytorch-exported.py",
            None,
        ),
        "TinyStories/model_adapter_exact_package.py": (
            "pytorch-exported",
            "-TinyStories",
            "model_adapter_exact_package.py",
        ),
        "artifacts/reference/tinystories-1m-exact-input-contract.json": (
            "pytorch-exported",
            "-tinystories-1m-exact-input-contract.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-input-audit.json": (
            "pytorch-exported",
            "-tinystories-1m-exact-input-audit.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-package-model.json": (
            "pytorch-exported",
            "-tinystories-1m-exact-package-model.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-generation.json": (
            "pytorch-exported",
            "-tinystories-1m-exact-generation.json",
            None,
        ),
        "docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md": (
            "pytorch-exported",
            "-2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
            None,
        ),
    }
    critical: dict[str, dict[str, Any]] = {}
    for path in _CRITICAL_INPUTS:
        evidence_bytes = _git_source_bytes(repo_root, source_commit, path)
        task4_bytes = _git_source_bytes(repo_root, _ACCEPTED_TASK4_COMMIT, path)
        authenticated_commit = (
            _REGISTRATION_COMMIT if path == "flake.nix" else _ACCEPTED_TASK4_COMMIT
        )
        authenticated_bytes = _git_source_bytes(repo_root, authenticated_commit, path)
        archived = archive / path
        _require(archived.is_file(), f"archived critical input missing: {path}")
        archived_bytes = archived.read_bytes()
        evidence_blob, evidence_type = _git_object(repo_root, f"{source_commit}:{path}")
        task4_blob, task4_type = _git_object(repo_root, f"{_ACCEPTED_TASK4_COMMIT}:{path}")
        authenticated_blob, authenticated_type = _git_object(
            repo_root, f"{authenticated_commit}:{path}"
        )
        _require(
            evidence_type == task4_type == authenticated_type == "blob"
            and archived_bytes == evidence_bytes == authenticated_bytes,
            f"authenticated critical input bytes mismatch: {path}",
        )
        binding: dict[str, Any] = {
            "workspace_sha256": _sha256_bytes(evidence_bytes),
            "task4_sha256": _sha256_bytes(task4_bytes),
            "task4_blob": task4_blob,
            "authenticated_commit": authenticated_commit,
            "authenticated_sha256": _sha256_bytes(authenticated_bytes),
            "authenticated_blob": authenticated_blob,
            "evidence_blob": evidence_blob,
            "flake_archive_path": str(archived),
            "flake_archive_sha256": _sha256_bytes(archived_bytes),
        }
        if path in evaluated_sources:
            stage, suffix, child = evaluated_sources[path]
            candidates = [
                Path(value)
                for value in derivations[stage]["receipt_derivation"]["input_sources"]
                if str(value).endswith(suffix)
            ]
            _require(len(candidates) == 1, f"evaluated source identity missing: {path}")
            evaluated = candidates[0] / child if child else candidates[0]
            evaluated_bytes = evaluated.read_bytes()
            _require(evaluated_bytes == evidence_bytes, f"evaluated source bytes mismatch: {path}")
            binding.update({
                "derivation_store_path": str(evaluated),
                "derivation_store_sha256": _sha256_bytes(evaluated_bytes),
            })
        critical[path] = binding
    pipeline_source_identity = {
        "accepted_task4_commit": _ACCEPTED_TASK4_COMMIT,
        "evidence_source_commit": source_commit,
        "task4_is_ancestor": True,
        "critical_inputs_clean": True,
        "flake_archive_path": str(archive),
        "flake_archive_nar_hash": archive_nar_hash,
        "flake_archive_source": source_flake,
        "critical_inputs": critical,
        "export_derivation": derivations["pytorch-exported"]["receipt_derivation"],
        "torch_derivation": derivations["torch"]["receipt_derivation"],
    }
    return {
        "repo_root": repo_root,
        "capture_tool_paths": {
            "classifier": _CLASSIFIER,
            "determinism_verifier": _VERIFIER,
        },
        "semantic_gate": {
            "command": shlex.join(semantic_command),
            "status": "accepted",
            "verifier": _SEMANTIC_VERIFIER,
            "verifier_sha256": _sha256_bytes(
                _git_source_bytes(repo_root, source_commit, _SEMANTIC_VERIFIER)
            ),
            "probe_report": _SEMANTIC_REPORT,
            "probe_report_sha256": _sha256_bytes(
                (repo_root / _SEMANTIC_REPORT).read_bytes()
            ),
            "evidence": semantic_evidence,
        },
        "identities": _FROZEN_IDENTITIES,
        "decision_self_sha256": _DECISION_SELF_SHA256,
        "predecessor": {
            "historical_bundle": "artifacts/comparison/tinystories-1m-exact-frontier-determinism",
            "file_sha256": _PREDECESSOR_FILE_SHA256,
            "self_sha256": _PREDECESSOR_SELF_SHA256,
        },
        "derivations": derivations,
        "pipeline_source_identity": pipeline_source_identity,
    }


def _independent_trust(repo_root: Path, source_commit: str) -> dict[str, Any]:
    decision = _load_json(repo_root / _DECISION)
    _require(decision.get("identity_hashes") == _FROZEN_IDENTITIES, "live frozen Task 1-3 identities changed")
    _require(decision.get("sha256") == _DECISION_SELF_SHA256, "live Task 2 decision identity changed")
    predecessor_path = repo_root / _PREDECESSOR
    predecessor = _load_json(predecessor_path)
    _require(_sha256_bytes(predecessor_path.read_bytes()) == _PREDECESSOR_FILE_SHA256, "live predecessor file identity changed")
    _require(predecessor.get("sha256") == _PREDECESSOR_SELF_SHA256, "live predecessor self identity changed")
    semantic_command = [
        "nix", "develop", "-c", "python", _SEMANTIC_VERIFIER,
        "--probe-report", _SEMANTIC_REPORT,
    ]
    semantic_evidence = json.loads(_run(semantic_command, repo_root))
    source_flake = f"git+file://{repo_root}?rev={source_commit}"
    _run(
        [
            "nix", "build", "--no-link", "--print-out-paths",
            f"{source_flake}#{_MODEL}-linalg",
            f"{source_flake}#{_MODEL}-scf",
        ],
        repo_root,
    )
    derivations = {
        stage: _live_derivation(repo_root, stage, source_flake)
        for stage in ("linalg", "scf")
    }
    linalg_artifact = Path(derivations["linalg"]["output"])
    scf_artifact = Path(derivations["scf"]["output"]) / "manifest.json"
    for stage, artifact in (("linalg", linalg_artifact), ("scf", scf_artifact)):
        data = artifact.read_bytes()
        derivations[stage]["artifact_bytes"] = data
        derivations[stage]["artifact_sha256"] = _sha256_bytes(data)
    return {
        "repo_root": repo_root,
        "capture_tool_paths": {
            "classifier": _CLASSIFIER,
            "determinism_verifier": _VERIFIER,
        },
        "semantic_gate": {
            "command": shlex.join(semantic_command),
            "status": "accepted",
            "verifier": _SEMANTIC_VERIFIER,
            "verifier_sha256": _sha256_bytes((repo_root / _SEMANTIC_VERIFIER).read_bytes()),
            "probe_report": _SEMANTIC_REPORT,
            "probe_report_sha256": _sha256_bytes((repo_root / _SEMANTIC_REPORT).read_bytes()),
            "evidence": semantic_evidence,
        },
        "identities": _FROZEN_IDENTITIES,
        "decision_self_sha256": _DECISION_SELF_SHA256,
        "predecessor": {
            "historical_bundle": "artifacts/comparison/tinystories-1m-exact-frontier-determinism",
            "file_sha256": _PREDECESSOR_FILE_SHA256,
            "self_sha256": _PREDECESSOR_SELF_SHA256,
        },
        "derivations": derivations,
    }


def _verify_v4_receipt(
    receipt: dict[str, Any], files: dict[str, bytes], trust: dict[str, Any], run_name: str
) -> None:
    """Validate a v4 capture against independently reconstructed live facts."""

    _require(receipt.get("model") == _MODEL, f"{run_name}: model mismatch")
    _require(receipt.get("semantic_gate") == trust["semantic_gate"], f"{run_name}: semantic gate/probe mismatch")
    _require(
        receipt.get("frozen_task_1_through_3_identities") == trust["identities"]
        and receipt.get("task_2_decision_self_sha256") == trust["decision_self_sha256"],
        f"{run_name}: frozen Task 1-3 identity mismatch",
    )
    _require(receipt.get("predecessor_receipt") == trust["predecessor"], f"{run_name}: predecessor identity mismatch")

    source_commit = receipt.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), f"{run_name}: source commit missing")
    tools = receipt.get("capture_tools")
    _require(isinstance(tools, dict), f"{run_name}: capture tool bindings missing")
    repo_root = trust.get("repo_root")
    for name, path_string in trust["capture_tool_paths"].items():
        expected = tools.get(name)
        _require(isinstance(expected, dict) and expected.get("path") == path_string, f"{run_name}: {name} path mismatch")
        if isinstance(repo_root, Path):
            committed = subprocess.run(
                ["git", "show", f"{source_commit}:{path_string}"],
                cwd=repo_root,
                capture_output=True,
            )
            _require(committed.returncode == 0, f"{run_name}: {name} is absent from source commit")
            tool_bytes = committed.stdout
        else:
            tool_bytes = trust["capture_tool_bytes"][name]
        _require(
            expected.get("sha256") == _sha256_bytes(tool_bytes),
            f"{run_name}: {name} source-commit-byte hash mismatch",
        )

    _require(receipt.get("status") == "compiler_frontier", f"{run_name}: frontier status mismatch")
    _require(receipt.get("frontier") == "pre_calyx_frontier", f"{run_name}: frontier class mismatch")
    _require(receipt.get("stage") == "scf", f"{run_name}: first invalid stage is not SCF")
    _require(receipt.get("diagnostic") == _DIAGNOSTIC, f"{run_name}: diagnostic mismatch")
    pipeline = receipt.get("pipeline_execution")
    _require(
        pipeline == {
            "registered_order": ["pytorch-exported", "torch", "linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"],
            "first_invalid_stage": "scf",
            "stopped_after_first_invalid_stage": True,
            "not_run": _NOT_RUN,
        },
        f"{run_name}: exact stop semantics mismatch",
    )
    stages = receipt.get("stages")
    execution = receipt.get("registered_build_execution")
    _require(isinstance(stages, list) and isinstance(execution, dict), f"{run_name}: stage evidence missing")
    stage_sequence = [stage.get("stage") for stage in stages if isinstance(stage, dict)]
    _require(stage_sequence == _STAGES, f"{run_name}: stage sequence mismatch")
    _require(set(execution) == set(stage_sequence), f"{run_name}: execution stage set mismatch")
    registered_order = pipeline.get("registered_order")
    first_invalid = pipeline.get("first_invalid_stage")
    _require(
        isinstance(registered_order, list)
        and registered_order[: len(stage_sequence)] == stage_sequence
        and first_invalid == stage_sequence[-1]
        and pipeline.get("stopped_after_first_invalid_stage") is True
        and pipeline.get("not_run") == registered_order[len(stage_sequence) :],
        f"{run_name}: execution sequence/stop contract mismatch",
    )
    expected_files = {
        "receipt.json", "pytorch-exported.log", "torch.log", "linalg.log",
        "scf.log", "full-input.gz", "minimal-reproducer.json", "linalg.drv",
        "linalg.derivation.json", "scf.drv", "scf.derivation.json",
    }
    _require(set(files) == expected_files, f"{run_name}: canonical evidence file set mismatch")
    for index, stage in enumerate(_STAGES):
        record = stages[index]
        run = execution.get(stage)
        _require(isinstance(run, dict), f"{run_name}: {stage} execution missing")
        filename = f"{stage}.log"
        log = files.get(filename)
        _require(log is not None, f"{run_name}: {stage} log missing")
        expected_status = "compiler_failure" if stage == "scf" else "succeeded"
        expected_accepted = stage != "scf"
        expected_diagnostics = [_DIAGNOSTIC] if stage == "scf" else []
        _require(run.get("invoked") is True, f"{run_name}: {stage.upper()} execution was not invoked")
        _require(record.get("status") == expected_status, f"{run_name}: {stage} status mismatch")
        _require(record.get("artifact_accepted") is expected_accepted, f"{run_name}: {stage} acceptance mismatch")
        _require(
            run.get("artifact_accepted") is expected_accepted
            and run.get("artifact_accepted") is record.get("artifact_accepted"),
            f"{run_name}: {stage} execution acceptance mismatch",
        )
        _require(record.get("exit_code") == 0 and run.get("exit_code") == 0, f"{run_name}: {stage} exit mismatch")
        _require(record.get("terminal_diagnostics") == expected_diagnostics, f"{run_name}: {stage} terminal diagnostic mismatch")
        _require(record.get("log_bytes") == len(log) and run.get("log_bytes") == len(log), f"{run_name}: {stage} log byte mismatch")
        expected_log = f"reproducers/scf/{stage}.log"
        _require(record.get("log") == expected_log and run.get("log") == expected_log, f"{run_name}: {stage} log path mismatch")
        log_hash = _sha256_bytes(log)
        _require(record.get("log_sha256") == log_hash and run.get("log_sha256") == log_hash, f"{run_name}: {stage} log hash mismatch")
        expected_command = shlex.join(["nix", "build", "--no-link", "--print-out-paths", "-L", f".#{_MODEL}-{stage}"])
        _require(record.get("command") == expected_command and run.get("command") == expected_command, f"{run_name}: {stage} command mismatch")
    _require(_DIAGNOSTIC.encode() in files["scf.log"], f"{run_name}: SCF diagnostic absent from log")

    for stage in ("linalg", "scf"):
        live = trust["derivations"][stage]
        run = execution[stage]
        record = stages[_STAGES.index(stage)]
        _require(run.get("derivation") == live["path"], f"{run_name}: {stage} derivation path mismatch")
        _require(run.get("derivation_file_sha256") == live["file_sha256"], f"{run_name}: {stage} derivation hash mismatch")
        _require(run.get("derivation_json_sha256") == live["json_sha256"], f"{run_name}: {stage} derivation JSON hash mismatch")
        _require(run.get("derivation_build_command") == live["build_command"], f"{run_name}: {stage} build command mismatch")
        _require(run.get("derivation_build_command_sha256") == live["build_command_sha256"], f"{run_name}: {stage} build command hash mismatch")
        _require(run.get("derivation_tool_bindings") == live["tool_bindings"], f"{run_name}: {stage} tool binding mismatch")
        _require(record.get("tool_revisions", {}).get("build_command_sha256") == live["build_command_sha256"], f"{run_name}: {stage} stage build binding mismatch")
        expected_artifact = live["output"] if stage == "linalg" else f"{live['output']}/manifest.json"
        _require(run.get("result") == live["output"], f"{run_name}: {stage} result/output mismatch")
        _require(run.get("artifact") == expected_artifact and record.get("artifact") == expected_artifact, f"{run_name}: {stage} artifact path mismatch")
        drv = files.get(f"{stage}.drv")
        drv_json = files.get(f"{stage}.derivation.json")
        _require(drv == live["file_bytes"], f"{run_name}: {stage} captured .drv mismatch")
        _require(drv_json == live["canonical_json"], f"{run_name}: {stage} captured derivation JSON mismatch")
        _require(run.get("captured_derivation") == f"reproducers/scf/{stage}.drv", f"{run_name}: {stage} captured .drv path mismatch")
        _require(run.get("captured_derivation_json") == f"reproducers/scf/{stage}.derivation.json", f"{run_name}: {stage} captured derivation JSON path mismatch")
        _require(run.get("captured_derivation_bytes") == len(drv) and run.get("captured_derivation_sha256") == _sha256_bytes(drv), f"{run_name}: {stage} captured .drv receipt mismatch")
        _require(run.get("captured_derivation_json_bytes") == len(drv_json) and run.get("captured_derivation_json_sha256") == _sha256_bytes(drv_json), f"{run_name}: {stage} captured derivation JSON receipt mismatch")

    full = receipt.get("full_failing_input")
    _require(isinstance(full, dict), f"{run_name}: full input binding missing")
    archive = files.get("full-input.gz")
    _require(archive is not None and full.get("archive_bytes") == len(archive) and full.get("archive_sha256") == _sha256_bytes(archive), f"{run_name}: Linalg archive binding mismatch")
    try:
        content = gzip.decompress(archive)
    except (OSError, EOFError) as error:
        raise VerificationError(f"{run_name}: invalid full input gzip: {error}") from error
    _require(full.get("source_stage") == "linalg", f"{run_name}: full input source stage mismatch")
    _require(full.get("path") == "reproducers/scf/full-input.gz", f"{run_name}: full input path mismatch")
    _require(full.get("source_artifact") == trust["derivations"]["linalg"]["output"], f"{run_name}: full input source artifact mismatch")
    _require(full.get("content_bytes") == len(content) and full.get("content_sha256") == _sha256_bytes(content), f"{run_name}: decompressed Linalg content mismatch")
    linalg_record = stages[2]
    _require(linalg_record.get("artifact_bytes") == len(content) and linalg_record.get("artifact_sha256") == _sha256_bytes(content), f"{run_name}: Linalg artifact/content mismatch")
    _require(content == trust["derivations"]["linalg"]["artifact_bytes"], f"{run_name}: decompressed Linalg bytes differ from live derivation output")

    minimal = receipt.get("minimal_reproducer")
    manifest_bytes = files.get("minimal-reproducer.json")
    _require(isinstance(minimal, dict) and manifest_bytes is not None, f"{run_name}: SCF manifest binding missing")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise VerificationError(f"{run_name}: invalid SCF manifest: {error}") from error
    _require(manifest == _SCF_MANIFEST, f"{run_name}: exact SCF manifest mismatch")
    _require(manifest_bytes == trust["derivations"]["scf"]["artifact_bytes"], f"{run_name}: SCF manifest differs from live derivation output")
    _require(minimal.get("stage") == "scf" and minimal.get("diagnostic") == _DIAGNOSTIC, f"{run_name}: SCF reproducer semantics mismatch")
    _require(minimal.get("path") == "reproducers/scf/minimal-reproducer.json", f"{run_name}: SCF reproducer path mismatch")
    _require(minimal.get("bytes") == len(manifest_bytes) and minimal.get("sha256") == _sha256_bytes(manifest_bytes), f"{run_name}: SCF manifest receipt mismatch")
    _require(stages[3].get("artifact_bytes") == len(manifest_bytes) and stages[3].get("artifact_sha256") == _sha256_bytes(manifest_bytes), f"{run_name}: SCF artifact/manifest mismatch")


def _verify_file_binding(
    binding: object,
    files: dict[str, bytes],
    filename: str,
    canonical_root: str,
    run_name: str,
) -> bytes:
    _require(isinstance(binding, dict), f"{run_name}: missing binding for {filename}")
    data = files.get(filename)
    _require(data is not None, f"{run_name}: missing {filename}")
    _require(
        binding.get("path") == f"{canonical_root}/{filename}",
        f"{run_name}: path mismatch for {filename}",
    )
    _require(
        binding.get("bytes") == len(data)
        and binding.get("sha256") == _sha256_bytes(data),
        f"{run_name}: binding mismatch for {filename}",
    )
    return data


def _verify_v5_frontier_evidence(
    receipt: dict[str, Any],
    files: dict[str, bytes],
    run_name: str,
    *,
    live_derivation: dict[str, Any] | None = None,
) -> set[str]:
    """Validate the v5 branch union and derive its exact regular-file set."""

    pipeline = receipt.get("pipeline_execution")
    stages = receipt.get("stages")
    execution = receipt.get("registered_build_execution")
    _require(isinstance(pipeline, dict), f"{run_name}: pipeline execution missing")
    _require(isinstance(stages, list) and stages, f"{run_name}: stage evidence missing")
    _require(isinstance(execution, dict), f"{run_name}: execution evidence missing")
    registered = pipeline.get("registered_order")
    sequence = [record.get("stage") for record in stages if isinstance(record, dict)]
    first_invalid = pipeline.get("first_invalid_stage")
    _require(
        registered
        == ["pytorch-exported", "torch", "linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"]
        and sequence == registered[: len(sequence)]
        and first_invalid == sequence[-1]
        and pipeline.get("stopped_after_first_invalid_stage") is True
        and pipeline.get("not_run") == registered[len(sequence) :],
        f"{run_name}: execution sequence/stop contract mismatch",
    )
    _require(set(execution) == set(sequence), f"{run_name}: execution stage set mismatch")
    canonical_root = f"reproducers/{first_invalid}"
    expected_files = {"receipt.json", "full-input.gz"}
    for stage in sequence:
        expected_files.update(
            {f"{stage}.log", f"{stage}.drv", f"{stage}.derivation.json"}
        )
        record = next(item for item in stages if item.get("stage") == stage)
        run = execution[stage]
        log = files.get(f"{stage}.log")
        _require(log is not None, f"{run_name}: missing {stage} log")
        _require(
            record.get("log_sha256") == _sha256_bytes(log)
            and run.get("log_sha256") == _sha256_bytes(log),
            f"{run_name}: failure log mismatch for {stage}",
        )
        for suffix, path_key, bytes_key, hash_key in (
            ("drv", "captured_derivation", "captured_derivation_bytes", "captured_derivation_sha256"),
            (
                "derivation.json",
                "captured_derivation_json",
                "captured_derivation_json_bytes",
                "captured_derivation_json_sha256",
            ),
        ):
            filename = f"{stage}.{suffix}"
            data = files.get(filename)
            _require(data is not None, f"{run_name}: missing captured derivation {filename}")
            _require(
                run.get(path_key) == f"{canonical_root}/{filename}"
                and run.get(bytes_key) == len(data)
                and run.get(hash_key) == _sha256_bytes(data),
                f"{run_name}: captured derivation binding mismatch for {stage}",
            )

    final_record = stages[-1]
    final_run = execution[first_invalid]
    _require(
        final_record.get("artifact_accepted") is False
        and final_run.get("artifact_accepted") is False,
        f"{run_name}: invalid artifact was accepted",
    )
    _require(
        isinstance(final_run.get("derivation_build_command"), str)
        and bool(final_run["derivation_build_command"])
        and final_run.get("derivation_build_command_sha256")
        == _sha256_bytes(final_run["derivation_build_command"].encode()),
        f"{run_name}: build command binding missing",
    )
    full = receipt.get("full_failing_input")
    _require(isinstance(full, dict), f"{run_name}: full input binding missing")
    archive = files.get("full-input.gz")
    _require(
        archive is not None
        and full.get("path") == f"{canonical_root}/full-input.gz"
        and full.get("archive_bytes") == len(archive)
        and full.get("archive_sha256") == _sha256_bytes(archive),
        f"{run_name}: full input archive mismatch",
    )
    try:
        content = gzip.decompress(archive)
    except (OSError, EOFError) as error:
        raise VerificationError(f"{run_name}: invalid full input gzip: {error}") from error
    _require(
        full.get("content_bytes") == len(content)
        and full.get("content_sha256") == _sha256_bytes(content),
        f"{run_name}: full input content mismatch",
    )

    frontier = receipt.get("frontier_evidence")
    _require(isinstance(frontier, dict), f"{run_name}: frontier evidence missing")
    kind = frontier.get("kind")
    if kind == "control_manifest":
        _require(
            final_record.get("exit_code") == 0 and final_run.get("exit_code") == 0,
            f"{run_name}: control manifest requires zero exit",
        )
        _require(
            frontier.get("operation") is None and frontier.get("types") is None,
            f"{run_name}: control manifest operation/types must be null",
        )
        _require(
            frontier.get("minimization")
            == {"status": "not_applicable", "reason": "control_manifest_is_minimal"},
            f"{run_name}: control manifest minimization mismatch",
        )
        manifest_binding = frontier.get("manifest")
        _require(
            "minimal-reproducer.json" in files,
            f"{run_name}: control manifest is missing minimal-reproducer.json",
        )
        manifest_bytes = _verify_file_binding(
            manifest_binding,
            files,
            "minimal-reproducer.json",
            canonical_root,
            run_name,
        )
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as error:
            raise VerificationError(f"{run_name}: invalid control manifest: {error}") from error
        manifest = _require_json_dict(manifest, f"{run_name}: control manifest")
        _require_json_str(manifest.get("stage"), f"{run_name}: control manifest.stage")
        _require_json_str(manifest.get("status"), f"{run_name}: control manifest.status")
        _require(isinstance(manifest_binding, dict), f"{run_name}: control manifest binding missing")
        exact_identity = (
            isinstance(manifest, dict)
            and manifest.get("stage") == first_invalid
            and manifest_binding.get("stage") == manifest.get("stage")
            and manifest_binding.get("status") == manifest.get("status")
            and manifest_binding.get("reason") == manifest.get("reason")
        )
        status = manifest.get("status") if isinstance(manifest, dict) else None
        if status in {"unavailable", "rejected"}:
            _require_exact_keys(
                manifest,
                {"reason", "stage", "status"},
                f"{run_name}: control manifest schema",
            )
            _require_json_str_fields(
                manifest,
                {"reason", "stage", "status"},
                f"{run_name}: control manifest",
            )
            _require(
                exact_identity
                and isinstance(manifest.get("reason"), str)
                and bool(manifest["reason"])
                and "residual_artifact" not in frontier
                and "blockers" not in frontier,
                f"{run_name}: exact control manifest mismatch",
            )
        elif status == "completed-with-residuals":
            _require_exact_keys(
                manifest,
                {"artifact", "blockers", "stage", "status"},
                f"{run_name}: control manifest schema",
            )
            _require_json_str_fields(
                manifest,
                {"artifact", "blockers", "stage", "status"},
                f"{run_name}: control manifest",
            )
            _require(
                exact_identity
                and first_invalid == "flat-scf"
                and set(manifest) == {"artifact", "blockers", "stage", "status"}
                and manifest.get("reason") is None
                and manifest.get("artifact") == "flat.scf.mlir"
                and manifest.get("blockers") == "blockers.json"
                and manifest_binding.get("artifact") == "flat.scf.mlir"
                and manifest_binding.get("blockers") == "blockers.json",
                f"{run_name}: exact control manifest mismatch",
            )
            _require(
                "flat.scf.mlir" in files,
                f"{run_name}: residual artifact is missing",
            )
            residual = _verify_file_binding(
                frontier.get("residual_artifact"),
                files,
                "flat.scf.mlir",
                canonical_root,
                run_name,
            )
            blockers = _verify_file_binding(
                frontier.get("blockers"),
                files,
                "blockers.json",
                canonical_root,
                run_name,
            )
            _require(bool(residual), f"{run_name}: residual artifact is empty")
            _require(bool(blockers), f"{run_name}: blockers evidence is empty")
            _require(
                isinstance(live_derivation, dict),
                f"{run_name}: live flat-scf derivation missing",
            )
            live_output = live_derivation.get("output")
            live_payloads = live_derivation.get("residual_payloads")
            _require(
                isinstance(live_output, str) and isinstance(live_payloads, dict),
                f"{run_name}: live residual payloads missing",
            )
            for filename, preserved in (
                ("flat.scf.mlir", residual),
                ("blockers.json", blockers),
            ):
                live_payload = live_payloads.get(filename)
                _require(
                    isinstance(live_payload, dict)
                    and live_payload.get("path") == str(Path(live_output) / filename),
                    f"{run_name}: live residual payload path mismatch for {filename}",
                )
                live_bytes = live_payload.get("bytes")
                _require(
                    isinstance(live_bytes, bytes)
                    and live_payload.get("sha256") == _sha256_bytes(live_bytes)
                    and preserved == live_bytes,
                    f"{run_name}: {filename} differs from live registered output",
                )
            expected_files.update({"flat.scf.mlir", "blockers.json"})
        else:
            raise VerificationError(f"{run_name}: exact control manifest mismatch")
        _require(
            final_record.get("artifact_sha256") == _sha256_bytes(manifest_bytes)
            and final_run.get("artifact_sha256") == _sha256_bytes(manifest_bytes),
            f"{run_name}: control manifest artifact mismatch",
        )
        expected_files.add("minimal-reproducer.json")
    elif kind == "compiler_failure":
        _require(
            isinstance(final_run.get("derivation_tool_bindings"), list)
            and bool(final_run["derivation_tool_bindings"]),
            f"{run_name}: tool binding missing",
        )
        _require(
            final_record.get("exit_code") not in {None, 0}
            and final_run.get("exit_code") == final_record.get("exit_code"),
            f"{run_name}: compiler failure requires the same nonzero exit",
        )
        _require(frontier.get("manifest") is None, f"{run_name}: compiler failure cannot carry any manifest")
        diagnostic = frontier.get("diagnostic")
        _require(
            isinstance(diagnostic, str)
            and diagnostic == receipt.get("diagnostic")
            and diagnostic.encode() in files[f"{first_invalid}.log"],
            f"{run_name}: failure log lost normalized diagnostic",
        )
        _require(
            final_record.get("artifact_sha256") == _sha256_bytes(content)
            and final_run.get("artifact_sha256") == _sha256_bytes(content)
            and final_record.get("artifact") == full.get("source_artifact")
            and final_run.get("artifact") == full.get("source_artifact"),
            f"{run_name}: compiler failure did not preserve full input artifact",
        )
        searchable = diagnostic + "\n" + content.decode("utf-8", errors="replace")
        operation = frontier.get("operation")
        types = frontier.get("types")
        _require(
            operation is None or (isinstance(operation, str) and operation in searchable),
            f"{run_name}: operation is not bound by diagnostic or input",
        )
        _require(
            types is None or (isinstance(types, str) and types in searchable),
            f"{run_name}: types are not bound by diagnostic or input",
        )
        interestingness = frontier.get("interestingness")
        _require(isinstance(interestingness, dict), f"{run_name}: interestingness evidence missing")
        _verify_file_binding(
            interestingness.get("test"), files, "interestingness-test.sh", canonical_root, run_name
        )
        _verify_file_binding(
            interestingness.get("full_log"), files, "interesting-full.log", canonical_root, run_name
        )
        expected_files.update({"interestingness-test.sh", "interesting-full.log", "reduction.log"})
        minimization = frontier.get("minimization")
        _require(isinstance(minimization, dict), f"{run_name}: minimization evidence missing")
        _verify_file_binding(
            minimization.get("reduction_log"), files, "reduction.log", canonical_root, run_name
        )
        status_value = minimization.get("status")
        if status_value == "verified":
            _verify_file_binding(
                minimization.get("minimal_reproducer"),
                files,
                "minimal-reproducer.mlir",
                canonical_root,
                run_name,
            )
            _verify_file_binding(
                minimization.get("interesting_reproducer_log"),
                files,
                "interesting-reproducer.log",
                canonical_root,
                run_name,
            )
            _require("reason" not in minimization, f"{run_name}: verified minimization has a reason")
            expected_files.update({"minimal-reproducer.mlir", "interesting-reproducer.log"})
        else:
            _require(
                status_value == "not_practical"
                and minimization.get("reason")
                in {"mlir_reduce_unavailable", "full_input_not_interesting", "reduction_failed"}
                and "minimal_reproducer" not in minimization
                and "interesting_reproducer_log" not in minimization,
                f"{run_name}: invalid not-practical minimization",
            )
    else:
        raise VerificationError(f"{run_name}: unsupported frontier evidence kind")

    _require(
        set(files) == expected_files,
        f"{run_name}: run directory contents mismatch: expected {sorted(expected_files)}, found {sorted(files)}",
    )
    return expected_files


def _verify_v5_receipt(
    receipt: dict[str, Any],
    files: dict[str, bytes],
    trust: dict[str, Any],
    run_name: str,
) -> set[str]:
    _require(receipt.get("model") == _MODEL, f"{run_name}: model mismatch")
    _authenticate_v5_pipeline_source(receipt, trust, run_name)
    _require(
        receipt.get("semantic_gate") == trust["semantic_gate"],
        f"{run_name}: semantic gate/probe mismatch",
    )
    _require(
        receipt.get("frozen_task_1_through_3_identities") == trust["identities"]
        and receipt.get("task_2_decision_self_sha256")
        == trust["decision_self_sha256"],
        f"{run_name}: frozen Task 1-3 identity mismatch",
    )
    _require(
        receipt.get("predecessor_receipt") == trust["predecessor"],
        f"{run_name}: predecessor identity mismatch",
    )
    source_commit = receipt.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), f"{run_name}: source commit missing")
    tools = receipt.get("capture_tools")
    _require(isinstance(tools, dict), f"{run_name}: capture tool bindings missing")
    repo_root = trust["repo_root"]
    for name, path in trust["capture_tool_paths"].items():
        binding = tools.get(name)
        _require(
            isinstance(binding, dict)
            and binding.get("path") == path
            and binding.get("sha256")
            == _sha256_bytes(_git_source_bytes(repo_root, source_commit, path)),
            f"{run_name}: {name} source-commit-byte hash mismatch",
        )

    pipeline = receipt.get("pipeline_execution")
    stages = receipt.get("stages")
    execution = receipt.get("registered_build_execution")
    _require(isinstance(pipeline, dict), f"{run_name}: pipeline execution missing")
    _require(isinstance(stages, list), f"{run_name}: stages missing")
    _require(isinstance(execution, dict), f"{run_name}: execution missing")
    sequence = [record.get("stage") for record in stages if isinstance(record, dict)]
    first_invalid = pipeline.get("first_invalid_stage")
    _require(
        first_invalid == "flat-scf"
        and len(stages) == 5
        and all(isinstance(record, dict) for record in stages)
        and sequence == _REGISTERED_ORDER[:5]
        and set(execution) == set(sequence)
        and pipeline.get("registered_order") == _REGISTERED_ORDER
        and pipeline.get("not_run") == _REGISTERED_ORDER[5:]
        and pipeline.get("stopped_after_first_invalid_stage") is True,
        f"{run_name}: exact c22 stage order mismatch",
    )
    _require(
        receipt.get("status") == "compiler_frontier"
        and receipt.get("stage") == first_invalid,
        f"{run_name}: frontier classification mismatch",
    )
    expected_frontier = (
        "calyx_frontier"
        if first_invalid == "calyx"
        else "sv_frontier"
        if first_invalid == "calyx-native-sv"
        else "pre_calyx_frontier"
    )
    _require(
        receipt.get("frontier") == expected_frontier,
        f"{run_name}: frontier class mismatch",
    )
    _require(
        receipt.get("diagnostic") == _RESIDUAL_DIAGNOSTIC,
        f"{run_name}: top-level control-manifest diagnostic mismatch",
    )
    live_frontier = trust["derivations"].get(first_invalid)
    expected_files = _verify_v5_frontier_evidence(
        receipt,
        files,
        run_name,
        live_derivation=live_frontier,
    )
    canonical_root = f"reproducers/{first_invalid}"

    for index, stage in enumerate(sequence):
        record = stages[index]
        run = execution[stage]
        live = trust["derivations"].get(stage)
        _require(isinstance(live, dict), f"{run_name}: live derivation missing for {stage}")
        attribute = _registered_attribute(stage)
        expected_command = shlex.join(
            ["nix", "build", "--no-link", "--print-out-paths", "-L", f".#{attribute}"]
        )
        log_name = f"{stage}.log"
        log_path = f"{canonical_root}/{log_name}"
        log = files.get(log_name)
        _require(isinstance(log, bytes), f"{run_name}: missing log for {stage}")
        artifact = live.get("artifact_bytes")
        _require(isinstance(artifact, bytes), f"{run_name}: live artifact missing for {stage}")
        expected_accepted = stage != first_invalid
        expected_diagnostics = [] if expected_accepted else [_RESIDUAL_DIAGNOSTIC]
        expected_upstream = (
            f"package_manifest_sha256:{_FROZEN_IDENTITIES['package_manifest_sha256']}"
            if index == 0
            else _sha256_bytes(trust["derivations"][sequence[index - 1]]["artifact_bytes"])
        )
        _require(
            record.get("status") == ("succeeded" if expected_accepted else "compiler_failure")
            and record.get("terminal_diagnostics") == expected_diagnostics
            and record.get("artifact") == live.get("artifact_path")
            and record.get("artifact_bytes") == len(artifact)
            and record.get("artifact_sha256") == _sha256_bytes(artifact)
            and record.get("upstream_identity") == expected_upstream,
            f"{run_name}: stage semantics mismatch for {stage}",
        )
        expected_tool_revisions = {
            "build_command_sha256": live["build_command_sha256"],
            "derivation": live["path"],
            "derivation_file_sha256": live["file_sha256"],
            "derivation_json_sha256": live["json_sha256"],
            "evidence_source_commit": _V5_SOURCE_COMMIT,
        }
        _require(
            record.get("tool_revisions") == expected_tool_revisions,
            f"{run_name}: exact tool revision mismatch for {stage}",
        )
        _require(
            record.get("log") == log_path
            and run.get("log") == log_path
            and record.get("log_bytes") == len(log)
            and run.get("log_bytes") == len(log)
            and record.get("log_sha256") == _sha256_bytes(log)
            and run.get("log_sha256") == _sha256_bytes(log),
            f"{run_name}: exact log binding mismatch for {stage}",
        )
        _require(
            run.get("invoked") is True
            and run.get("result") == live.get("output")
            and run.get("route_alias") == _ALIAS
            and run.get("frontend") == "linalg"
            and run.get("backend") == "calyx-native-sv"
            and run.get("artifact") == live.get("artifact_path")
            and run.get("artifact_bytes") == len(artifact)
            and run.get("artifact_sha256") == _sha256_bytes(artifact),
            f"{run_name}: execution semantics mismatch for {stage}",
        )
        _require(
            record.get("command") == expected_command
            and run.get("command") == expected_command
            and run.get("attribute") == attribute,
            f"{run_name}: registered command mismatch for {stage}",
        )
        _require(
            record.get("exit_code") == live["exit_code"]
            and run.get("exit_code") == live["exit_code"],
            f"{run_name}: replay exit mismatch for {stage}",
        )
        _require(
            files[f"{stage}.log"]
            == _expected_v5_replay_log(
                stage,
                live,
                residual_rejected=(
                    stage == first_invalid
                    and receipt.get("frontier_evidence", {}).get("kind")
                    == "control_manifest"
                    and receipt.get("frontier_evidence", {})
                    .get("manifest", {})
                    .get("status")
                    == "completed-with-residuals"
                ),
            ),
            f"{run_name}: replay log mismatch for {stage}",
        )
        _require(
            run.get("derivation") == live["path"]
            and run.get("derivation_file_sha256") == live["file_sha256"]
            and run.get("derivation_json_sha256") == live["json_sha256"]
            and run.get("derivation_build_command") == live["build_command"]
            and run.get("derivation_build_command_sha256")
            == live["build_command_sha256"]
            and run.get("derivation_tool_bindings") == live["tool_bindings"],
            f"{run_name}: derivation/tool/build command mismatch for {stage}",
        )
        _require(
            files[f"{stage}.drv"] == live["file_bytes"]
            and files[f"{stage}.derivation.json"] == live["canonical_json"],
            f"{run_name}: captured derivation bytes mismatch for {stage}",
        )
        _require(
            record.get("artifact_accepted") is expected_accepted
            and run.get("artifact_accepted") is expected_accepted,
            f"{run_name}: replay acceptance mismatch for {stage}",
        )
        if expected_accepted:
            _require(
                record.get("artifact") == live.get("artifact_path")
                and run.get("artifact") == live.get("artifact_path")
                and record.get("artifact_sha256") == _sha256_bytes(artifact)
                and run.get("artifact_sha256") == _sha256_bytes(artifact),
                f"{run_name}: live artifact mismatch for {stage}",
            )

    full = receipt["full_failing_input"]
    upstream_stage = sequence[-2]
    upstream_live = trust["derivations"][upstream_stage]
    upstream_bytes = upstream_live.get("artifact_bytes")
    _require(isinstance(upstream_bytes, bytes), f"{run_name}: live upstream input missing")
    _require(
        gzip.decompress(files["full-input.gz"]) == upstream_bytes
        and full.get("source_stage") == upstream_stage
        and full.get("source_artifact") == upstream_live.get("artifact_path"),
        f"{run_name}: full input differs from live upstream artifact",
    )
    frontier = receipt["frontier_evidence"]
    if frontier["kind"] == "control_manifest":
        live_manifest = trust["derivations"][first_invalid].get("artifact_bytes")
        _require(
            isinstance(live_manifest, bytes)
            and files["minimal-reproducer.json"] == live_manifest,
            f"{run_name}: control manifest differs from registered output",
        )
    else:
        _require(
            trust["derivations"][first_invalid]["exit_code"] != 0,
            f"{run_name}: compiler failure did not replay",
        )
        script = Path(tempfile.mkdtemp(prefix="exact-frontier-verify-script-")) / "interestingness-test.sh"
        try:
            script.write_bytes(files["interestingness-test.sh"])
            script.chmod(0o755)
            candidate = script.parent / "full-input.mlir"
            candidate.write_bytes(upstream_bytes)
            result = subprocess.run([str(script), str(candidate)], text=True, capture_output=True)
            replay_log = _canonical_execution_evidence(
                [str(script), str(candidate)],
                result,
                {str(script.parent): "<evidence-dir>", str(candidate): "<full-input>"},
            )
            _require(result.returncode == 0, f"{run_name}: full input interestingness replay failed")
            _require(
                replay_log == files["interesting-full.log"],
                f"{run_name}: full input interestingness log mismatch",
            )
        finally:
            for child in script.parent.iterdir():
                child.unlink()
            script.parent.rmdir()
    claims = receipt.get("claims")
    _require(
        claims == _V5_CLAIMS,
        f"{run_name}: exact claims mismatch",
    )
    return expected_files


def _verify_run(
    bundle_root: Path,
    run_name: str,
    run_manifest: dict[str, Any],
    canonical_files: list[str],
    source_commit: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    run_root = bundle_root / run_name
    _verify_run_directory(run_root, run_name, tuple(canonical_files))
    _require(
        run_manifest.get("source_commit") == source_commit,
        f"{run_name}: source commit does not match manifest root",
    )
    metadata = run_manifest.get("noncanonical_metadata")
    _require(isinstance(metadata, dict), f"{run_name}: noncanonical metadata missing")
    _require(metadata.get("canonical") is False, f"{run_name}: metadata must be noncanonical")
    _require(
        isinstance(metadata.get("receipt_captured_at"), str)
        and bool(metadata["receipt_captured_at"]),
        f"{run_name}: capture timestamp missing",
    )
    _require(
        isinstance(metadata.get("runtime_seconds_approximate"), (int, float)),
        f"{run_name}: approximate runtime missing",
    )

    file_manifest = run_manifest.get("files")
    _require(isinstance(file_manifest, dict), f"{run_name}: file manifest missing")
    _require(
        sorted(file_manifest) == sorted(canonical_files),
        f"{run_name}: canonical file set does not match manifest",
    )
    file_bytes: dict[str, bytes] = {}
    for filename in canonical_files:
        _require(Path(filename).name == filename, f"unsafe canonical filename: {filename}")
        path = run_root / filename
        _require(path.is_file(), f"{run_name}: missing canonical file {filename}")
        data = path.read_bytes()
        binding = file_manifest[filename]
        _require(isinstance(binding, dict), f"{run_name}: bad binding for {filename}")
        _require(
            binding.get("bytes") == len(data),
            f"{run_name}: byte count mismatch for {filename}",
        )
        actual_sha256 = _sha256_bytes(data)
        _require(
            binding.get("sha256") == actual_sha256,
            f"{run_name}: SHA-256 mismatch for {filename}",
        )
        file_bytes[filename] = data

    receipt = _load_json(run_root / "receipt.json")
    _require(
        receipt.get("source_commit") == source_commit,
        f"{run_name}: receipt source commit mismatch",
    )
    self_hash = receipt.get("sha256")
    _require(
        isinstance(self_hash, str) and self_hash == _canonical_receipt_hash(receipt),
        f"{run_name}: receipt self-hash mismatch",
    )
    _require(
        run_manifest.get("receipt_self_hash") == self_hash,
        f"{run_name}: manifest receipt self-hash mismatch",
    )

    execution = receipt.get("registered_build_execution")
    capture = receipt.get("compiler_import_capture")
    _require(isinstance(execution, dict), f"{run_name}: registered execution missing")
    _require(isinstance(capture, dict), f"{run_name}: compiler capture missing")
    export = execution.get("pytorch-exported")
    torch = execution.get("torch-mlir")
    _require(isinstance(export, dict), f"{run_name}: export execution missing")
    _require(isinstance(torch, dict), f"{run_name}: Torch execution missing")

    expected_commands = {
        "pytorch-exported": export.get("command"),
        "torch-mlir": torch.get("command"),
        "compiler-import-capture": capture.get("command"),
    }
    expected_exits = {
        "pytorch-exported": export.get("exit_code"),
        "torch-mlir": torch.get("exit_code"),
        "compiler-import-capture": capture.get("exit_code"),
    }
    _require(
        run_manifest.get("commands") == expected_commands,
        f"{run_name}: commands do not match receipt",
    )
    _require(
        run_manifest.get("exit_codes") == expected_exits,
        f"{run_name}: exit codes do not match receipt",
    )

    log_bindings = {
        "pytorch-exported-build.log": export,
        "torch-mlir.log": torch,
        "compiler-import-capture.log": capture,
    }
    for filename, receipt_binding in log_bindings.items():
        data = file_bytes[filename]
        _require(
            receipt_binding.get("log_bytes") == len(data),
            f"{run_name}: receipt byte count mismatch for {filename}",
        )
        _require(
            receipt_binding.get("log_sha256") == _sha256_bytes(data),
            f"{run_name}: receipt SHA-256 mismatch for {filename}",
        )

    torch_text = file_bytes["torch-mlir.log"].decode("utf-8")
    capture_text = file_bytes["compiler-import-capture.log"].decode("utf-8")
    _require(
        str(receipt.get("diagnostic")) in torch_text,
        f"{run_name}: Torch log lost receipt diagnostic",
    )
    _require(
        str(capture.get("diagnostic")) in capture_text,
        f"{run_name}: capture log lost receipt diagnostic",
    )
    return receipt, file_bytes


def _verify_v1_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    """Verify both preserved live runs and require byte-identical canonical files."""

    bundle_root = bundle_root.resolve()
    manifest = _load_json(bundle_root / "manifest.json")
    _require(
        manifest.get("schema") == "tinystories-1m-exact-frontier-determinism-bundles-v1",
        "unsupported determinism manifest schema",
    )
    source_commit = manifest.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), "source commit missing")
    canonical_files = manifest.get("canonical_files")
    _require(
        canonical_files == list(_V1_CANONICAL_FILES),
        "v1 canonical file list does not match schema",
    )
    runs = manifest.get("runs")
    _require(isinstance(runs, dict), "run manifests missing")
    run_names = sorted(runs)
    _require(run_names == ["run-1", "run-2"], "exactly run-1 and run-2 are required")

    verified: dict[str, tuple[dict[str, Any], dict[str, bytes]]] = {}
    for run_name in run_names:
        _require(isinstance(runs[run_name], dict), f"invalid manifest for {run_name}")
        verified[run_name] = _verify_run(
            bundle_root,
            run_name,
            runs[run_name],
            canonical_files,
            source_commit,
        )

    first_receipt, first_files = verified["run-1"]
    second_receipt, second_files = verified["run-2"]
    for filename in canonical_files:
        _require(
            first_files[filename] == second_files[filename],
            f"preserved runs differ at canonical file {filename}",
        )
    _require(first_receipt == second_receipt, "parsed receipts differ")

    receipt_file_sha256 = _sha256_bytes(first_files["receipt.json"])
    receipt_self_hash = str(first_receipt["sha256"])
    expected = manifest.get("expected_comparison")
    _require(isinstance(expected, dict), "expected comparison missing")
    _require(expected.get("byte_identical") is True, "manifest does not expect identity")
    _require(
        expected.get("receipt_file_sha256") == receipt_file_sha256,
        "manifest comparison receipt SHA-256 mismatch",
    )
    _require(
        expected.get("receipt_self_hash") == receipt_self_hash,
        "manifest comparison receipt self-hash mismatch",
    )

    return {
        "source_commit": source_commit,
        "runs": run_names,
        "byte_identical": True,
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_self_hash": receipt_self_hash,
        "noncanonical_metadata_present": all(
            isinstance(runs[name].get("noncanonical_metadata"), dict)
            for name in run_names
        ),
    }


def _verify_v2_run(
    bundle_root: Path,
    run_name: str,
    run_manifest: dict[str, Any],
    canonical_files: list[str],
    source_commit: str,
    trust: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    run_root = bundle_root / run_name
    _verify_run_directory(run_root, run_name, tuple(canonical_files))
    _require(
        run_manifest.get("source_commit") == source_commit,
        f"{run_name}: source commit mismatch",
    )
    bindings = run_manifest.get("files")
    _require(isinstance(bindings, dict), f"{run_name}: file bindings missing")
    _require(
        sorted(bindings) == sorted(canonical_files),
        f"{run_name}: canonical file set mismatch",
    )
    files: dict[str, bytes] = {}
    for filename in canonical_files:
        _require(Path(filename).name == filename, f"unsafe canonical filename: {filename}")
        path = run_root / filename
        _require(path.is_file(), f"{run_name}: missing canonical file {filename}")
        data = path.read_bytes()
        binding = bindings[filename]
        _require(isinstance(binding, dict), f"{run_name}: invalid binding for {filename}")
        _require(binding.get("bytes") == len(data), f"{run_name}: byte count mismatch for {filename}")
        _require(
            binding.get("sha256") == _sha256_bytes(data),
            f"{run_name}: SHA-256 mismatch for {filename}",
        )
        files[filename] = data

    receipt = _load_json(run_root / "receipt.json")
    schema = receipt.get("schema")
    _require(
        schema in {
            "tinystories-1m-exact-current-pipeline-frontier-v3",
            "tinystories-1m-exact-current-pipeline-frontier-v4",
        },
        f"{run_name}: unsupported receipt schema",
    )
    _require(receipt.get("source_commit") == source_commit, f"{run_name}: receipt source mismatch")
    _require(receipt.get("stage") == "scf", f"{run_name}: first invalid stage is not SCF")
    _require(receipt.get("status") == "compiler_frontier", f"{run_name}: frontier status mismatch")
    _require(receipt.get("sha256") == _canonical_receipt_hash(receipt), f"{run_name}: receipt self-hash mismatch")
    _require(
        run_manifest.get("receipt_self_hash") == receipt.get("sha256"),
        f"{run_name}: manifest receipt self-hash mismatch",
    )
    execution = receipt.get("pipeline_execution")
    _require(isinstance(execution, dict), f"{run_name}: pipeline execution missing")
    _require(execution.get("first_invalid_stage") == "scf", f"{run_name}: SCF stop missing")
    _require(execution.get("stopped_after_first_invalid_stage") is True, f"{run_name}: stop flag missing")
    _require(
        execution.get("not_run") == ["flat-scf", "calyx", "calyx-native-sv"],
        f"{run_name}: later-stage exclusion mismatch",
    )
    stages = receipt.get("stages")
    _require(isinstance(stages, list), f"{run_name}: stage records missing")
    _require(
        [record.get("stage") for record in stages if isinstance(record, dict)]
        == ["pytorch-exported", "torch", "linalg", "scf"],
        f"{run_name}: executed stage order mismatch",
    )
    _require(all(record.get("artifact_accepted") is True for record in stages[:-1]), f"{run_name}: valid prefix rejected")
    _require(stages[-1].get("artifact_accepted") is False, f"{run_name}: invalid SCF artifact accepted")

    full_input = receipt.get("full_failing_input")
    minimal = receipt.get("minimal_reproducer")
    _require(isinstance(full_input, dict), f"{run_name}: full input binding missing")
    _require(isinstance(minimal, dict), f"{run_name}: minimal reproducer binding missing")
    _require(full_input.get("archive_sha256") == _sha256_bytes(files["full-input.gz"]), f"{run_name}: full input receipt hash mismatch")
    _require(minimal.get("sha256") == _sha256_bytes(files["minimal-reproducer.json"]), f"{run_name}: reproducer receipt hash mismatch")
    _require(minimal.get("operation_and_types_not_applicable") is True, f"{run_name}: frontier kind mismatch")
    for stage in ("pytorch-exported", "torch", "linalg", "scf"):
        record = next(item for item in stages if item["stage"] == stage)
        filename = f"{stage}.log"
        _require(record.get("log_sha256") == _sha256_bytes(files[filename]), f"{run_name}: receipt log hash mismatch for {stage}")
    if schema == "tinystories-1m-exact-current-pipeline-frontier-v4":
        _require(trust is not None, f"{run_name}: independent v4 trust is missing")
        _verify_v4_receipt(receipt, files, trust, run_name)
    return receipt, files


def _verify_v2_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    manifest = _load_json(bundle_root / "manifest.json")
    source_commit = manifest.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), "source commit missing")
    canonical_files = manifest.get("canonical_files")
    enumerated_runs = {
        name: _enumerate_run_files(bundle_root / name, name)
        for name in ("run-1", "run-2")
    }
    first_receipt = _load_json(bundle_root / "run-1" / "receipt.json")
    receipt_schema = first_receipt.get("schema")
    if receipt_schema == "tinystories-1m-exact-current-pipeline-frontier-v4":
        schema_files = _V2_CURRENT_CANONICAL_FILES
    elif (
        receipt_schema == "tinystories-1m-exact-current-pipeline-frontier-v3"
        and source_commit == _LEGACY_V3_SOURCE_COMMIT
    ):
        schema_files = _V2_LEGACY_CANONICAL_FILES
    else:
        raise VerificationError("unsupported v2 receipt schema/source identity")
    _require(
        canonical_files == list(schema_files),
        "v2 canonical file list does not match receipt schema",
    )
    for name, actual_files in enumerated_runs.items():
        _require(
            actual_files == set(schema_files) | _RUN_METADATA_FILES,
            f"{name}: run directory contents mismatch: "
            f"expected {sorted(set(schema_files) | _RUN_METADATA_FILES)}, "
            f"found {sorted(actual_files)}",
        )
    runs = manifest.get("runs")
    _require(isinstance(runs, dict), "run manifests missing")
    run_names = sorted(runs)
    _require(run_names == ["run-1", "run-2"], "exactly run-1 and run-2 are required")
    trust = (
        _independent_trust(Path(__file__).resolve().parents[2], str(source_commit))
        if first_receipt.get("schema")
        == "tinystories-1m-exact-current-pipeline-frontier-v4"
        else None
    )
    verified = {
        name: _verify_v2_run(
            bundle_root, name, runs[name], canonical_files, source_commit, trust
        )
        for name in run_names
    }
    first_receipt, first_files = verified["run-1"]
    second_receipt, second_files = verified["run-2"]
    for filename in canonical_files:
        _require(
            first_files[filename] == second_files[filename],
            f"preserved runs differ at canonical file {filename}",
        )
    _require(first_receipt == second_receipt, "parsed receipts differ")
    expected = manifest.get("expected_comparison")
    _require(isinstance(expected, dict), "expected comparison missing")
    receipt_file_sha256 = _sha256_bytes(first_files["receipt.json"])
    _require(expected.get("byte_identical") is True, "manifest does not expect identity")
    _require(expected.get("first_invalid_stage") == "scf", "manifest frontier mismatch")
    _require(expected.get("receipt_file_sha256") == receipt_file_sha256, "manifest receipt file hash mismatch")
    _require(expected.get("receipt_self_hash") == first_receipt["sha256"], "manifest receipt self-hash mismatch")
    return {
        "source_commit": source_commit,
        "runs": run_names,
        "byte_identical": True,
        "first_invalid_stage": "scf",
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_self_hash": first_receipt["sha256"],
        "canonical_file_count": len(canonical_files),
    }


def _verify_v3_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    manifest = _load_json(bundle_root / "manifest.json")
    _verify_v5_bundle_manifest_schema(manifest)
    _require(
        manifest.get("schema") == "tinystories-1m-exact-frontier-determinism-bundles-v3",
        "unsupported v3 determinism manifest schema",
    )
    try:
        root_entries = {entry.name: entry for entry in bundle_root.iterdir()}
    except OSError as error:
        raise VerificationError(f"cannot enumerate bundle root: {error}") from error
    _require(
        set(root_entries) == {"manifest.json", "run-1", "run-2"},
        "v3 bundle root contents mismatch",
    )
    _require(
        root_entries["manifest.json"].is_file()
        and not root_entries["manifest.json"].is_symlink()
        and all(
            root_entries[name].is_dir() and not root_entries[name].is_symlink()
            for name in ("run-1", "run-2")
        ),
        "v3 bundle root entry types mismatch",
    )
    source_commit = manifest.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), "source commit missing")
    repo_root = Path(__file__).resolve().parents[2]
    _verify_pinned_v5_source_commit(repo_root, source_commit, "bundle")
    runs_manifest = manifest.get("runs")
    _require(
        isinstance(runs_manifest, dict) and sorted(runs_manifest) == ["run-1", "run-2"],
        "exactly run-1 and run-2 are required",
    )
    first_receipt = _load_json(bundle_root / "run-1" / "receipt.json")
    _verify_v5_schema(first_receipt, "run-1")
    _require(
        first_receipt.get("schema") == "tinystories-1m-exact-current-pipeline-frontier-v5",
        "v3 bundle requires a v5 receipt",
    )
    first_stages = first_receipt.get("stages")
    _require(isinstance(first_stages, list), "v5 stage sequence missing")
    executed_stages = [
        record.get("stage") for record in first_stages if isinstance(record, dict)
    ]
    _require(
        executed_stages == _REGISTERED_ORDER[: len(executed_stages)],
        "v5 executed prefix mismatch",
    )
    trust = _independent_v5_trust(
        repo_root, source_commit, executed_stages
    )
    verified: dict[str, tuple[dict[str, Any], dict[str, bytes], set[str]]] = {}
    for run_name in ("run-1", "run-2"):
        run_root = bundle_root / run_name
        names = _enumerate_run_files(run_root, run_name)
        files = {name: (run_root / name).read_bytes() for name in names}
        receipt = _load_json(run_root / "receipt.json")
        _verify_v5_schema(receipt, run_name)
        _require(
            receipt.get("schema") == "tinystories-1m-exact-current-pipeline-frontier-v5"
            and receipt.get("source_commit") == source_commit
            and receipt.get("sha256") == _canonical_receipt_hash(receipt),
            f"{run_name}: receipt identity mismatch",
        )
        expected_files = _verify_v5_receipt(receipt, files, trust, run_name)
        run_manifest = _require_exact_keys(
            runs_manifest[run_name],
            {"files", "receipt_self_hash", "source_commit"},
            f"{run_name}: run manifest schema",
        )
        bindings = run_manifest.get("files")
        _require(
            run_manifest.get("source_commit") == source_commit
            and run_manifest.get("receipt_self_hash") == receipt.get("sha256")
            and isinstance(bindings, dict)
            and set(bindings) == expected_files,
            f"{run_name}: manifest bindings mismatch",
        )
        for filename in expected_files:
            binding = _require_exact_keys(
                bindings[filename],
                {"bytes", "sha256"},
                f"{run_name}: manifest file binding schema for {filename}",
            )
            _require(
                isinstance(binding, dict)
                and binding.get("bytes") == len(files[filename])
                and binding.get("sha256") == _sha256_bytes(files[filename]),
                f"{run_name}: manifest file binding mismatch for {filename}",
            )
        verified[run_name] = (receipt, files, expected_files)
    first, first_files, first_expected = verified["run-1"]
    second, second_files, second_expected = verified["run-2"]
    _require(first_expected == second_expected, "run schemas differ")
    _require(
        manifest.get("canonical_files") == sorted(first_expected),
        "v3 canonical file list differs from verifier-derived schema",
    )
    for filename in first_expected:
        _require(
            first_files[filename] == second_files[filename],
            f"preserved runs differ at canonical file {filename}",
        )
    _require(first == second, "parsed receipts differ")
    expected = manifest.get("expected_comparison")
    receipt_file_sha256 = _sha256_bytes(first_files["receipt.json"])
    _require(
        isinstance(expected, dict)
        and expected.get("byte_identical") is True
        and expected.get("first_invalid_stage")
        == first["pipeline_execution"]["first_invalid_stage"]
        and expected.get("receipt_file_sha256") == receipt_file_sha256
        and expected.get("receipt_self_hash") == first["sha256"],
        "v3 expected comparison mismatch",
    )
    return {
        "source_commit": source_commit,
        "runs": ["run-1", "run-2"],
        "byte_identical": True,
        "first_invalid_stage": first["pipeline_execution"]["first_invalid_stage"],
        "frontier_evidence_kind": first["frontier_evidence"]["kind"],
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_self_hash": first["sha256"],
        "canonical_file_count": len(first_expected),
    }


def verify_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    """Verify historical v1 or current v2 deterministic capture bundles."""

    bundle_root = bundle_root.resolve()
    manifest = _load_json(bundle_root / "manifest.json")
    schema = manifest.get("schema")
    if schema == "tinystories-1m-exact-frontier-determinism-bundles-v1":
        return _verify_v1_determinism_bundles(bundle_root)
    if schema == "tinystories-1m-exact-frontier-determinism-bundles-v2":
        return _verify_v2_determinism_bundles(bundle_root)
    if schema == "tinystories-1m-exact-frontier-determinism-bundles-v3":
        return _verify_v3_determinism_bundles(bundle_root)
    raise VerificationError("unsupported determinism manifest schema")


def verify_public_v5_evidence(repo_root: Path, bundle_root: Path) -> dict[str, Any]:
    """Verify the canonical bundles and their public receipt/reproducer projections."""

    result = verify_determinism_bundles(bundle_root)
    manifest = _load_json(bundle_root / "manifest.json")
    _require(
        manifest.get("schema") == "tinystories-1m-exact-frontier-determinism-bundles-v3"
        and manifest.get("source_commit") == _V5_SOURCE_COMMIT,
        "public evidence requires the pinned c22 v5 bundle",
    )
    run_receipts = [
        (bundle_root / run_name / "receipt.json").read_bytes()
        for run_name in ("run-1", "run-2")
    ]
    public_receipt = (
        repo_root
        / "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"
    )
    try:
        receipt_mode = public_receipt.lstat().st_mode
        public_receipt_bytes = public_receipt.read_bytes()
    except OSError as error:
        raise VerificationError(f"public receipt is missing: {error}") from error
    _require(
        stat.S_ISREG(receipt_mode)
        and not public_receipt.is_symlink()
        and public_receipt_bytes == run_receipts[0] == run_receipts[1],
        "public receipt differs from canonical bundled receipts",
    )

    canonical_files = manifest.get("canonical_files")
    _require(isinstance(canonical_files, list), "public canonical file list missing")
    expected_reproducers = set(canonical_files) - {"receipt.json"}
    public_reproducers = repo_root / "reproducers/flat-scf"
    actual_reproducers = _enumerate_run_files(public_reproducers, "public reproducer")
    _require(
        actual_reproducers == expected_reproducers,
        "public reproducer directory contents mismatch",
    )
    for filename in expected_reproducers:
        public_bytes = (public_reproducers / filename).read_bytes()
        run_1_bytes = (bundle_root / "run-1" / filename).read_bytes()
        run_2_bytes = (bundle_root / "run-2" / filename).read_bytes()
        _require(
            public_bytes == run_1_bytes == run_2_bytes,
            f"public reproducer differs from canonical bundle: {filename}",
        )
    return {**result, "public_reproducer_file_count": len(expected_reproducers)}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_bundle = (
        repo_root
        / "artifacts"
        / "comparison"
        / "tinystories-1m-exact-frontier-determinism-flat-scf"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle)
    args = parser.parse_args()
    if args.bundle_dir.resolve() == default_bundle.resolve():
        result = verify_public_v5_evidence(repo_root, args.bundle_dir)
    else:
        result = verify_determinism_bundles(args.bundle_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
