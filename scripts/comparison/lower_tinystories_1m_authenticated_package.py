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
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories import model_adapter_reference_package as package_adapter  # noqa: E402


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


def _canonical_verified_input(contract_path: Path, package: Path) -> dict[str, Any]:
    """Recompute the canonical verifier receipt from the package currently on disk."""
    try:
        verifier = package_adapter._load_verifier()
        verified = verifier.verify_input(contract_path, package)
    except package_adapter.PackageAdapterError as error:
        raise LoweringGateError(error.code, str(error)) from error
    except Exception as error:
        code = getattr(error, "code", "canonical_verifier_failed")
        raise LoweringGateError(code, str(error)) from error
    if not isinstance(verified, dict):
        raise LoweringGateError("canonical_verifier_failed", "canonical verifier did not return an object")
    return verified


def _verified_receipt(
    receipt: dict[str, Any], contract: dict[str, Any], contract_path: Path, package: Path,
    verified_input_provider=_canonical_verified_input,
) -> None:
    if receipt.get("schema") != CONTRACT_SCHEMA or receipt.get("status") != "dequantized_weight_export_ready":
        raise LoweringGateError("adapter_receipt_schema_mismatch", "adapter receipt schema is not canonical")
    if receipt.get("receipt_sha256") != package_adapter.receipt_sha256(receipt):
        raise LoweringGateError("adapter_receipt_hash_mismatch", "adapter receipt self-hash is not canonical")
    identity = receipt.get("identity")
    if not isinstance(identity, dict):
        raise LoweringGateError("adapter_receipt_identity_missing", "adapter receipt lacks identity")
    expected_identity = {
        "contract_sha256": _sha256(contract_path),
        "model": contract.get("model"),
        "tokenizer": contract.get("tokenizer"),
        "package": contract.get("package"),
        "config_sha256": package_adapter.CONFIG_SHA256,
    }
    if identity != expected_identity:
        raise LoweringGateError("adapter_receipt_identity_mismatch", "adapter receipt model/package identity differs")
    canonical_verified_input = verified_input_provider(contract_path, package)
    if receipt.get("verified_input") != canonical_verified_input:
        raise LoweringGateError(
            "verified_input_recomputation_mismatch",
            "adapter receipt verified_input differs from canonical verification of current package files",
        )
    try:
        package_adapter.validate_verifier_receipt(
            canonical_verified_input, contract, contract_path, package
        )
    except package_adapter.PackageAdapterError as error:
        raise LoweringGateError(error.code, str(error)) from error
    expected_package_receipt = contract.get("package", {}).get("files", {}).get("receipt.json")
    if not isinstance(expected_package_receipt, str) or _sha256(package / "receipt.json") != expected_package_receipt:
        raise LoweringGateError("package_receipt_hash_mismatch", "package receipt does not match frozen contract")
    manifest = _load_json(package / "manifest.json")
    try:
        expected_boundaries = package_adapter._activation_boundaries(manifest)
    except package_adapter.PackageAdapterError as error:
        raise LoweringGateError(error.code, str(error)) from error
    if receipt.get("activation_qdq_boundaries") != expected_boundaries:
        raise LoweringGateError(
            "activation_boundary_content_mismatch",
            "adapter Q/DQ names, widths, values, or hashes differ from authenticated package manifest",
        )
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


def _artifact_path(export_dir: Path, item: dict[str, Any]) -> Path:
    relative = item.get("path")
    if not isinstance(relative, str) or not relative:
        raise LoweringGateError("adapter_artifacts_missing", "adapter artifact path is malformed")
    candidate = (export_dir / relative).resolve()
    if candidate.parent != export_dir.resolve():
        raise LoweringGateError("adapter_artifact_path_invalid", "adapter artifact path escapes package export")
    return candidate


def _prepare_output(out_dir: Path) -> Path:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise LoweringGateError("output_not_empty", f"refusing to overwrite nonempty output directory {out_dir}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists():
        out_dir.rmdir()
    return Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))


def lower_gate(
    contract_path: Path, package_export: Path, package: Path, out_dir: Path,
    lower_command: list[str] | None = None, verified_input_provider=_canonical_verified_input,
) -> dict[str, Any]:
    contract = _load_json(contract_path)
    identity = _contract_identity(contract)
    receipt_path = package_export / "adapter-receipt.json"
    receipt = _load_json(receipt_path)
    _verified_receipt(receipt, contract, contract_path, package, verified_input_provider)
    staging = _prepare_output(out_dir)
    try:
        receipt_files = {
            "contract": _copy_required(contract_path, staging / "canonical-contract.json"),
            "adapter_receipt": _copy_required(receipt_path, staging / "adapter-receipt.json"),
            "package_receipt": _copy_required(package / "receipt.json", staging / "package-receipt.json"),
        }
        artifacts = receipt["artifacts"]
        export_item = artifacts["exported_program"]
        trace_item = artifacts["numeric_trace"]
        receipt_files["exported_program"] = _copy_required(
            _artifact_path(package_export, export_item), staging / "exported.pt2", export_item["sha256"]
        )
        receipt_files["numeric_trace"] = _copy_required(
            _artifact_path(package_export, trace_item), staging / "numeric-trace.json", trace_item["sha256"]
        )

        qdq = receipt.get("activation_qdq_execution")
        activation_boundaries = receipt.get("activation_qdq_boundaries")
        # ``metadata_only`` is itself the proven non-representability condition.
        # It must never fall through to the FP32 compiler just because it has
        # the expected spelling.
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
            _write_json(staging / "lowering-attempt.json", result)
            _write_json(staging / "compiler-artifact-metadata.json", result)
            os.replace(staging, out_dir)
            return result

        if not lower_command:
            raise LoweringGateError("lower_command_missing", "representable Q/DQ receipt requires an explicit compiler command")
        completed = subprocess.run(lower_command, cwd=staging, text=True, capture_output=True, check=False)
        (staging / "compiler.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            result = base | {
                "status": "lowering_failed",
                "compiler_artifact": None,
                "failure": {"stage": "compiler", "code": "compiler_command_failed", "exit_code": completed.returncode},
            }
        else:
            result = base | {
                "status": "lowered_unaligned",
                "compiler_artifact": {"path": "compiler.mlir", "sha256": _sha256(staging / "compiler.mlir")},
                "failure": {"stage": "alignment", "code": "alignment_not_yet_authenticated"},
            }
        _write_json(staging / "lowering-attempt.json", result)
        _write_json(staging / "compiler-artifact-metadata.json", result)
        os.replace(staging, out_dir)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


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
