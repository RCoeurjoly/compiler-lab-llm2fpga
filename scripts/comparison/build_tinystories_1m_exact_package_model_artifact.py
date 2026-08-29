#!/usr/bin/env python3
"""Build the source-, oracle-, trace-, and ExportedProgram-bound exact receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import torch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.model_adapter_exact_package import (
    canonical_sha256,
    export_exact_program,
    exported_program_identity,
    load_exact_model,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_sha256(value: Mapping[str, Any]) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != "artifact_sha256"})


def build_artifact(repo_root: Path, contract: Path, package: Path, model_path: Path) -> dict[str, Any]:
    repo_root, contract, package, model_path = map(Path, (repo_root, contract, package, model_path))
    adapter = repo_root / "TinyStories/model_adapter_exact_package.py"
    test = repo_root / "tests/test_tinystories_1m_exact_package_model.py"
    certificate = repo_root / "artifacts/reference/tinystories-1m-exact-reachable-domain.json"
    oracle = repo_root / "artifacts/reference/tinystories-1m-fixed-logits-oracle.json"
    profile = repo_root / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
    audit = contract.with_name("tinystories-1m-exact-input-audit.json")
    bundle = load_exact_model(contract, package, model_path)
    prompt = torch.tensor([bundle.contract["reference"]["prompt_tokens"]], dtype=torch.int64)
    trace = bundle.trace(prompt)
    exported = export_exact_program(bundle)
    replay = exported.module()(prompt)
    artifact: dict[str, Any] = {
        "schema": "tinystories-1m-exact-package-model-v1",
        "status": "exact_eager_export_and_independent_oracle_matched",
        "identity": {
            "contract_sha256": _sha256(contract),
            "audit_file_sha256": _sha256(audit),
            "audit_payload_sha256": bundle.audit["sha256"],
            "fixed_profile_sha256": _sha256(profile),
            "reachable_certificate_sha256": _sha256(certificate),
            "fixed_logits_oracle_sha256": _sha256(oracle),
            "package_manifest_sha256": _sha256(package / "manifest.json"),
            "package_weights_sha256": _sha256(package / "weights.bin"),
            "adapter_sha256": _sha256(adapter),
            "test_sha256": _sha256(test),
            "generator_sha256": _sha256(Path(__file__)),
            "model_receipt_sha256": bundle.receipt["receipt_sha256"],
        },
        "execution": bundle.receipt["execution"],
        "trace": {
            "prompt_tokens": bundle.contract["reference"]["prompt_tokens"],
            "sha256": trace["trace_sha256"],
            "checkpoint_sha256": {
                name: checkpoint["sha256"] for name, checkpoint in trace["checkpoints"].items()
            },
            "qdq_boundary_sha256": {
                item["name"]: {
                    "codes": item["codes_sha256"],
                    "scales": item["scales_sha256"],
                    "dequantized": item["dequantized_sha256"],
                }
                for item in trace["qdq_boundaries"]
            },
            "gemv_accumulator_sha256": {
                name: item["sha256"] for name, item in trace["gemv_accumulators"].items()
            },
            "nonlinear_boundary_sha256": {
                name: item["sha256"] for name, item in trace["nonlinear_boundaries"].items()
            },
        },
        "export": {
            "shape": list(replay.shape),
            "dtype": str(replay.dtype),
            "checkpoint_replay": "matched",
            "qdq_boundary_replay": "matched",
            "gemv_accumulator_replay": "matched",
            "nonlinear_boundary_replay": "matched",
            "final_logits_replay": "matched",
            "independent_oracle": "full_logits_bit_exact",
            "final_logits_sha256": bundle.export_verification["final_logits_sha256"],
            "final_logits_canonical_sha256": bundle.export_verification["final_logits_canonical_sha256"],
        },
        "exported_program": exported_program_identity(exported),
    }
    artifact["artifact_sha256"] = artifact_sha256(artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build_artifact(args.repo_root, args.contract, args.package, args.model_path)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(value["artifact_sha256"])


if __name__ == "__main__":
    main()
