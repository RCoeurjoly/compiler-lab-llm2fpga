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


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


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


def diagnose(contract_path: Path, metadata_path: Path) -> dict[str, Any]:
    contract = load_json(Path(contract_path))
    metadata = load_json(Path(metadata_path))
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
            "contract": {"path": str(contract_path), "sha256": hashlib.sha256(Path(contract_path).read_bytes()).hexdigest()},
            "compiler_metadata": {"path": str(metadata_path), "sha256": hashlib.sha256(Path(metadata_path).read_bytes()).hexdigest()},
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
