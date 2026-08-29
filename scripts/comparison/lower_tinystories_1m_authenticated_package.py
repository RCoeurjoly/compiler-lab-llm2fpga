#!/usr/bin/env python3
"""Fail-closed handoff from the authenticated package export to lowering.

This is deliberately a *gate*, not an FP32 fallback.  The package adapter can
reconstruct GPT-Neo weights and export logits, but its receipt records that the
97 activation Q/DQ boundaries have metadata only.  Passing that export to the
ordinary FP32 pipeline would silently drop the implementation profile and make
an apparently successful, but unaligned, compiler artifact.

The script therefore preserves the authenticated inputs and emits a stable
lowering-attempt sidecar.  It only invokes a lowering command after an adapter
receipt says that all boundary execution semantics are representable.  Until
then its successful process exit means that the evidence was recorded; the
JSON ``status`` remains ``unsupported`` and cannot be mistaken for alignment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-authenticated-package-lowering-v1"
CONTRACT_SCHEMA = "tinystories-1m-package-gpt-neo-adapter-v1"
EXPECTED_QDQ = {
    "status": "metadata_only",
    "reason_code": "activation_rounding_semantics_unavailable",
}


class LoweringGateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LoweringGateError("invalid_json", f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise LoweringGateError("invalid_json", f"{path} must contain an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _contract_identity(contract: dict[str, Any]) -> dict[str, Any]:
    model, package = contract.get("model"), contract.get("package")
    if not isinstance(model, dict) or not isinstance(package, dict):
        raise LoweringGateError("invalid_contract", "model/package identity is absent")
    model_keys = ("name", "source_model_id", "source_revision")
    package_keys = ("sha256", "manifest_sha256")
    if any(not isinstance(model.get(key), str) or not model[key] for key in model_keys):
        raise LoweringGateError("invalid_contract", "model identity is malformed")
    if any(not isinstance(package.get(key), str) or len(package[key]) != 64 for key in package_keys):
        raise LoweringGateError("invalid_contract", "package identity is malformed")
    return {
        "model": {key: model[key] for key in model_keys},
        "package": {key: package[key] for key in package_keys},
    }


def _verified_receipt(receipt: dict[str, Any], contract: dict[str, Any], contract_path: Path) -> None:
    if receipt.get("schema") != CONTRACT_SCHEMA:
        raise LoweringGateError("adapter_receipt_schema_mismatch", "adapter receipt schema is not canonical")
    identity = receipt.get("identity")
    if not isinstance(identity, dict):
        raise LoweringGateError("adapter_receipt_identity_missing", "adapter receipt lacks identity")
    if identity.get("contract_sha256") != _sha256(contract_path):
        raise LoweringGateError("adapter_receipt_contract_mismatch", "adapter receipt is not bound to this contract")
    if identity.get("model") != contract.get("model") or identity.get("package") != contract.get("package"):
        raise LoweringGateError("adapter_receipt_identity_mismatch", "adapter receipt model/package identity differs")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise LoweringGateError("adapter_artifacts_missing", "adapter receipt does not bind exported artifacts")
    for key in ("exported_program", "numeric_trace"):
        item = artifacts.get(key)
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise LoweringGateError("adapter_artifacts_missing", f"adapter artifact {key!r} is malformed")


def _copy_required(source: Path, output: Path, expected_hash: str | None = None) -> str:
    if not source.is_file():
        raise LoweringGateError("artifact_missing", f"missing required artifact {source}")
    digest = _sha256(source)
    if expected_hash is not None and digest != expected_hash:
        raise LoweringGateError("artifact_hash_mismatch", f"{source} SHA-256 differs from adapter receipt")
    shutil.copy2(source, output)
    return digest


def lower_gate(contract_path: Path, package_export: Path, package: Path, out_dir: Path, lower_command: list[str] | None = None) -> dict[str, Any]:
    contract = _load_json(contract_path)
    identity = _contract_identity(contract)
    receipt_path = package_export / "adapter-receipt.json"
    receipt = _load_json(receipt_path)
    _verified_receipt(receipt, contract, contract_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_files = {
        "contract": _copy_required(contract_path, out_dir / "canonical-contract.json"),
        "adapter_receipt": _copy_required(receipt_path, out_dir / "adapter-receipt.json"),
        "package_receipt": _copy_required(package / "receipt.json", out_dir / "package-receipt.json"),
    }
    artifacts = receipt["artifacts"]
    export_item = artifacts["exported_program"]
    trace_item = artifacts["numeric_trace"]
    receipt_files["exported_program"] = _copy_required(
        package_export / export_item["path"], out_dir / "exported.pt2", export_item["sha256"]
    )
    receipt_files["numeric_trace"] = _copy_required(
        package_export / trace_item["path"], out_dir / "numeric-trace.json", trace_item["sha256"]
    )

    qdq = receipt.get("activation_qdq_execution")
    activation_boundaries = receipt.get("activation_qdq_boundaries")
    if not isinstance(activation_boundaries, dict) or len(activation_boundaries) != 97:
        raise LoweringGateError(
            "activation_boundary_metadata_invalid",
            "adapter receipt must bind exactly 97 activation Q/DQ boundaries",
        )
    # ``metadata_only`` is itself the proven non-representability condition.
    # It must never fall through to the FP32 compiler just because it has the
    # expected spelling.
    qdq_error = qdq == EXPECTED_QDQ
    if not qdq_error:
        raise LoweringGateError(
            "activation_qdq_receipt_unknown",
            "adapter receipt does not carry a recognized executable Q/DQ contract",
        )
    base = {
        "schema": SCHEMA,
        "model": "TinyStories-1M",
        "contract": {"path": "canonical-contract.json", "sha256": receipt_files["contract"], "identity": identity},
        "contract_identity": identity,
        "package_export": {
            "adapter_receipt_sha256": receipt_files["adapter_receipt"],
            "exported_program_sha256": receipt_files["exported_program"],
            "numeric_trace_sha256": receipt_files["numeric_trace"],
            "package_receipt_sha256": receipt_files["package_receipt"],
        },
        "activation_qdq_execution": qdq,
        "activation_qdq_boundary_count": len(activation_boundaries) if isinstance(activation_boundaries, dict) else None,
        # Compatible with Task 2's source metadata identity check.  It is not
        # a source claim until a representable lowering has produced one.
        "task2_source_metadata": {"contract_identity": identity},
        "alignment_status": "unaligned",
    }
    if qdq_error:
        result = base | {
            "status": "unsupported",
            "compiler_artifact": None,
            "failure": {
                "stage": "authenticated-package-lowering-preflight",
                "code": "activation_rounding_semantics_unavailable",
                "message": (
                    "the authenticated package has 97 activation boundaries, but its adapter receipt "
                    "declares metadata_only because rounding, saturation, and clamp semantics are unavailable"
                ),
            },
        }
        _write_json(out_dir / "lowering-attempt.json", result)
        _write_json(out_dir / "compiler-artifact-metadata.json", result)
        return result

    if not lower_command:
        raise LoweringGateError("lower_command_missing", "representable Q/DQ receipt requires an explicit compiler command")
    completed = subprocess.run(lower_command, cwd=out_dir, text=True, capture_output=True, check=False)
    (out_dir / "compiler.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        result = base | {
            "status": "lowering_failed",
            "compiler_artifact": None,
            "failure": {"stage": "compiler", "code": "compiler_command_failed", "exit_code": completed.returncode},
        }
    else:
        result = base | {
            "status": "lowered_unaligned",
            "compiler_artifact": {"path": "compiler.mlir", "sha256": _sha256(out_dir / "compiler.mlir")},
            "failure": {"stage": "alignment", "code": "alignment_not_yet_authenticated"},
        }
    _write_json(out_dir / "lowering-attempt.json", result)
    _write_json(out_dir / "compiler-artifact-metadata.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--package-export", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--lower-command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    lower_gate(args.contract, args.package_export, args.package, args.out_dir, args.lower_command or None)


if __name__ == "__main__":
    main()
