#!/usr/bin/env python3
"""Diagnose compiler/reference identity and quantization alignment.

This is an evidence gate, not an identity-repair tool.  A historical compiler
artifact may be useful for inspection, but rewriting its sidecar to the frozen
reference would make an unauthenticated FP32 artifact appear equivalent to the
INT8/per-output-QDQ package.  The report therefore names every observed
identity mismatch and leaves the next compiler boundary explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-contract-alignment-v1"
CANONICAL_CONTRACT = Path(__file__).resolve().parents[2] / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
CANONICAL_METADATA = Path(__file__).resolve().parents[2] / "artifacts/comparison/tinystories-1m-baseline-float-sv-metadata.json"
CANONICAL_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
CANONICAL_METADATA_SHA256 = "158ef76497aa0e0f1509a260059ca28880389d6c1234acee7a81f41ee609a3a1"
CONTRACT_SCHEMA_VERSION = 1
METADATA_SCHEMA = "tinystories-1m-compiler-artifact-metadata-v1"


class AlignmentEvidenceError(ValueError):
    """Raised when the diagnostic inputs are not the authenticated artifacts."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _authenticate_inputs(contract_path: Path, metadata_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authenticate immutable inputs before reading their semantic fields."""
    contract_path = Path(contract_path).resolve()
    metadata_path = Path(metadata_path).resolve()
    if contract_path != CANONICAL_CONTRACT.resolve():
        raise AlignmentEvidenceError("contract_path_not_canonical")
    if metadata_path != CANONICAL_METADATA.resolve():
        raise AlignmentEvidenceError("compiler_metadata_path_not_canonical")
    try:
        contract_bytes = contract_path.read_bytes()
        metadata_bytes = metadata_path.read_bytes()
    except OSError as error:
        raise AlignmentEvidenceError(f"authenticated_input_unreadable: {error}") from error
    if hashlib.sha256(contract_bytes).hexdigest() != CANONICAL_CONTRACT_SHA256:
        raise AlignmentEvidenceError("contract_sha256_mismatch")
    if hashlib.sha256(metadata_bytes).hexdigest() != CANONICAL_METADATA_SHA256:
        raise AlignmentEvidenceError("compiler_metadata_sha256_mismatch")
    contract = load_json(contract_path)
    metadata = load_json(metadata_path)
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise AlignmentEvidenceError("contract_schema_mismatch")
    if metadata.get("schema") != METADATA_SCHEMA:
        raise AlignmentEvidenceError("compiler_metadata_schema_mismatch")
    return contract, metadata


def _contract_identity(contract: dict[str, Any]) -> dict[str, Any]:
    model = contract.get("model")
    package = contract.get("package")
    if not isinstance(model, dict) or not isinstance(package, dict):
        raise ValueError("frozen contract lacks model/package identity")
    return {
        "model": {key: model.get(key) for key in ("name", "source_model_id", "source_revision")},
        "package": {key: package.get(key) for key in ("sha256", "manifest_sha256")},
    }


def _metadata_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    identity = metadata.get("contract_identity")
    if not isinstance(identity, dict):
        return {}
    return identity


def _diagnose_documents(contract: dict[str, Any], metadata: dict[str, Any], *,
                        contract_path: Path, metadata_path: Path,
                        contract_sha256: str, metadata_sha256: str) -> dict[str, Any]:
    expected = _contract_identity(contract)
    observed = _metadata_identity(metadata)
    mismatches: list[dict[str, Any]] = []
    for section, keys in (("model", ("name", "source_model_id", "source_revision")),
                          ("package", ("sha256", "manifest_sha256"))):
        actual_section = observed.get(section)
        if not isinstance(actual_section, dict):
            for key in keys:
                mismatches.append({"path": f"{section}.{key}", "expected": expected[section][key], "observed": None})
            continue
        for key in keys:
            if actual_section.get(key) != expected[section][key]:
                mismatches.append({
                    "path": f"{section}.{key}",
                    "expected": expected[section][key],
                    "observed": actual_section.get(key),
                })
    if mismatches:
        status = "contract_mismatch"
        boundary = {
            "code": "compiler_artifact_identity",
            "component": "compiler_artifact_metadata",
            "reason": "the realized compiler sidecar does not authenticate the frozen TinyStories-1M package",
        }
    else:
        status = "compiler_quantization_unverified"
        boundary = {
            "code": "compiler_quantization",
            "component": "compiler_artifact_metadata",
            "reason": "identity matches, but the sidecar does not prove INT8/per-output weights and 97 activation Q/DQ boundaries",
        }
    return {
        "schema": SCHEMA,
        "model": "TinyStories-1M",
        "status": status,
        "inputs": {
            "contract": {"path": str(contract_path), "sha256": contract_sha256},
            "compiler_metadata": {"path": str(metadata_path), "sha256": metadata_sha256},
        },
        "expected_identity": expected,
        "observed_identity": observed,
        "mismatches": mismatches,
        "first_boundary": boundary,
        "next_boundary": {
            "required_evidence": [
                "compiler_quantization",
                "compiler_weight_image_hash",
                "compiler_activation_qdq_boundaries",
                "compiler_artifact_generated_from_frozen_package",
            ],
            "action": "regenerate or adapt the compiler input from the authenticated package; do not rewrite historical metadata",
            "transport_changes": False,
        },
        "provenance": {
            "reference_role": "content_authenticated_behavioral_oracle_only",
            "reference_source_or_rtl_copied": False,
            "llm_assistance_disclosure_required": True,
        },
    }


def diagnose(contract_path: Path, metadata_path: Path) -> dict[str, Any]:
    contract, metadata = _authenticate_inputs(contract_path, metadata_path)
    return _diagnose_documents(
        contract,
        metadata,
        contract_path=Path("artifacts/reference/tinystories-1m-kev-gpt-contract.json"),
        metadata_path=Path("artifacts/comparison/tinystories-1m-baseline-float-sv-metadata.json"),
        contract_sha256=CANONICAL_CONTRACT_SHA256,
        metadata_sha256=CANONICAL_METADATA_SHA256,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--compiler-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = diagnose(args.contract, args.compiler_metadata)
    result["sha256"] = canonical_sha256(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
