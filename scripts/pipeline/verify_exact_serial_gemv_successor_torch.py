#!/usr/bin/env python3
"""Verify the successor-only exact serial-GEMV export and Torch-stage receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SUCCESSOR_MODEL = "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor"
TASK1_RECEIPT_RELATIVE = Path(
    "artifacts/comparison/tinystories-1m-exact-serial-gemv-successor.json"
)
GENERATION_RELATIVE = Path("artifacts/reference/tinystories-1m-exact-generation.json")
EXACT_ADAPTER_RELATIVE = Path("TinyStories/model_adapter_exact_package.py")
BOUNDARY_RELATIVE = Path("TinyStories/serial_gemv_boundary.py")
SUCCESSOR_ADAPTER_RELATIVE = Path(
    "TinyStories/model_adapter_exact_serial_gemv_successor.py"
)

TASK1_RECEIPT_FILE_SHA256 = (
    "d6c71ad94ccb0e00c2edb0dfbc3a2004d9e21bf1a30984b9df57570c04415dee"
)
TASK1_RECEIPT_SHA256 = (
    "ec9985628911a28374d9b304e7896e61d1dc9635612e74311d6667eef470f7db"
)
GENERATION_FILE_SHA256 = (
    "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3"
)
GENERATION_ARTIFACT_SHA256 = (
    "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3"
)
EXACT_ADAPTER_SHA256 = (
    "5f2dfa10c54134e44a31f89608b562aea33ef39deacfcd62eadac1f0fda94892"
)
BOUNDARY_SHA256 = (
    "a3e0c9f5ccd56fcd530174e2e15747008344b8e32384e508611c793008037b14"
)
HISTORICAL_MODEL_BLOCK_SHA256 = (
    "f51745f3ab9e15d2377c89853dc7403f472fecc1c4c56a992d470a46a122b62d"
)
ROUTE_SOURCES = {
    "successor_adapter": SUCCESSOR_ADAPTER_RELATIVE,
    "authority_and_stage_verifier": Path(
        "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py"
    ),
    "model_registration": Path("nix/models.nix"),
    "pipeline_registration": Path("flake.nix"),
    "pipeline_driver": Path("nix/pipeline.nix"),
    "torch_import_driver": Path("scripts/compile-pytorch.py"),
    "legalizer": Path("tools/torch-mlir-passes/LegalizeExactSerialGemv.cpp"),
}


class VerificationError(ValueError):
    """A claimed successor-stage identity or result is not reproducible."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return sha256_bytes(encoded)


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"invalid {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def file_binding(path: Path, root: Path | None = None) -> dict[str, object]:
    require(path.is_file(), f"bound file is missing: {path}")
    rendered = str(path.relative_to(root)) if root is not None else str(path)
    return {
        "path": rendered,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _require_self_hash(value: dict[str, Any], key: str, label: str) -> None:
    claimed = value.get(key)
    without_hash = {name: item for name, item in value.items() if name != key}
    require(
        claimed == canonical_sha256(without_hash),
        f"{label} self-hash mismatch",
    )


def verify_successor_authority(root: Path) -> dict[str, Any]:
    """Bind Task 1's successor proof to its changed adapter and boundary bytes."""

    root = Path(root).resolve()
    receipt_path = root / TASK1_RECEIPT_RELATIVE
    generation_path = root / GENERATION_RELATIVE
    exact_adapter_path = root / EXACT_ADAPTER_RELATIVE
    boundary_path = root / BOUNDARY_RELATIVE

    require(
        receipt_path.is_file()
        and sha256_file(receipt_path) == TASK1_RECEIPT_FILE_SHA256,
        "Task 1 successor receipt file mismatch",
    )
    receipt = load_object(receipt_path, "Task 1 successor receipt")
    _require_self_hash(receipt, "receipt_sha256", "Task 1 successor receipt")
    require(
        receipt.get("receipt_sha256") == TASK1_RECEIPT_SHA256
        and receipt.get("schema") == "tinystories-1m-exact-serial-gemv-successor-v1"
        and receipt.get("status") == "post_boundary_generation_matched",
        "Task 1 successor receipt identity mismatch",
    )
    require(
        generation_path.is_file()
        and sha256_file(generation_path) == GENERATION_FILE_SHA256,
        "canonical Task 1--3 generation artifact mismatch",
    )
    generation = load_object(generation_path, "canonical Task 1--3 generation artifact")
    require(
        generation.get("artifact_sha256") == GENERATION_ARTIFACT_SHA256,
        "canonical Task 1--3 generation artifact self identity mismatch",
    )
    receipt_generation = receipt.get("historical_authority", {}).get("generation", {})
    require(
        receipt_generation.get("path") == str(GENERATION_RELATIVE)
        and receipt_generation.get("file_sha256") == GENERATION_FILE_SHA256
        and receipt_generation.get("artifact_sha256") == GENERATION_ARTIFACT_SHA256
        and receipt_generation.get("status") == "matched",
        "Task 1 successor receipt generation binding mismatch",
    )
    successor = receipt.get("successor", {})
    verification = receipt.get("verification", {})
    require(
        exact_adapter_path.is_file()
        and sha256_file(exact_adapter_path) == EXACT_ADAPTER_SHA256
        and successor.get("adapter_sha256") == EXACT_ADAPTER_SHA256,
        "Task 1 successor exact adapter mismatch",
    )
    require(
        boundary_path.is_file()
        and sha256_file(boundary_path) == BOUNDARY_SHA256
        and successor.get("boundary_sha256") == BOUNDARY_SHA256,
        "Task 1 successor serial-GEMV boundary mismatch",
    )
    require(
        verification.get("frozen_generation_artifact") == "matched"
        and verification.get("all_adapter_gemvs_cross_boundary") is True
        and verification.get("boundary_eager_export_status") == "matched"
        and verification.get("runtime_gemv_operation_count") == 49
        and verification.get("successor_exported_operator_count") == 49
        and verification.get("successor_prompt_logits") == "matched"
        and verification.get("successor_tokens") == "matched"
        and verification.get("successor_token_count") == 16,
        "Task 1 successor receipt semantic proof mismatch",
    )
    generation_binding = file_binding(generation_path, root)
    receipt_binding = file_binding(receipt_path, root)
    return {
        "historical_generation": {
            "path": generation_binding["path"],
            "bytes": generation_binding["bytes"],
            "file_sha256": generation_binding["sha256"],
            "artifact_sha256": GENERATION_ARTIFACT_SHA256,
        },
        "task1_successor_receipt": {
            "path": receipt_binding["path"],
            "bytes": receipt_binding["bytes"],
            "file_sha256": receipt_binding["sha256"],
            "receipt_sha256": TASK1_RECEIPT_SHA256,
        },
        "changed_sources": {
            "exact_adapter": file_binding(exact_adapter_path, root),
            "serial_gemv_boundary": file_binding(boundary_path, root),
        },
    }


def _load_boundary(root: Path) -> None:
    boundary = root / BOUNDARY_RELATIVE
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location(
            "tinystories_successor_stage_boundary", boundary
        )
        require(spec is not None and spec.loader is not None, "boundary loader unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass


def build_export_manifest(root: Path, exported_dir: Path) -> dict[str, Any]:
    """Verify the materialized program and bind it to the successor authority."""

    import torch

    root = Path(root).resolve()
    exported_dir = Path(exported_dir).resolve()
    authority = verify_successor_authority(root)
    successor_adapter = root / SUCCESSOR_ADAPTER_RELATIVE
    require(successor_adapter.is_file(), "successor adapter is missing")
    _load_boundary(root)
    exported = torch.export.load(exported_dir / "exported.pt2")
    operator_count = sum(
        node.op == "call_function"
        and str(node.target) == "llm2fpga.serial_gemv.default"
        for node in exported.graph_module.graph.nodes
    )
    require(operator_count == 49, "successor exported operator count mismatch")
    manifest: dict[str, Any] = {
        "schema": "tinystories-1m-exact-serial-gemv-successor-export-v1",
        "model": SUCCESSOR_MODEL,
        "authority": authority,
        "successor_adapter": file_binding(successor_adapter, root),
        "exported_program": file_binding(exported_dir / "exported.pt2"),
        "materializer_manifest": file_binding(exported_dir / "manifest.json"),
        "serial_gemv_operator_count": operator_count,
    }
    manifest["receipt_sha256"] = canonical_sha256(manifest)
    return manifest


def validate_export_manifest(value: dict[str, Any], root: Path) -> dict[str, Any]:
    require(
        value.get("schema") == "tinystories-1m-exact-serial-gemv-successor-export-v1"
        and value.get("model") == SUCCESSOR_MODEL,
        "successor export manifest identity mismatch",
    )
    _require_self_hash(value, "receipt_sha256", "successor export manifest")
    require(value.get("authority") == verify_successor_authority(root),
            "successor export authority mismatch")
    require(value.get("serial_gemv_operator_count") == 49,
            "successor export operator count mismatch")
    for key in ("successor_adapter", "exported_program", "materializer_manifest"):
        binding = value.get(key)
        require(isinstance(binding, dict), f"successor export {key} binding missing")
        path = Path(str(binding.get("path", "")))
        if key == "successor_adapter":
            path = root / path
        require(
            path.is_file()
            and path.stat().st_size == binding.get("bytes")
            and sha256_file(path) == binding.get("sha256"),
            f"successor export {key} binding mismatch",
        )
    return value


def _historical_model_block_sha256(root: Path) -> str:
    source = (root / "nix/models.nix").read_text(encoding="utf-8")
    start = source.index('  "tiny-stories-1m-kev-gpt-exact" = registerModel {')
    end = source.index('  "tinystories-w8a8" = registerModel {', start)
    return sha256_bytes(source[start:end].encode())


def build_artifact_receipt(
    root: Path,
    export_manifest_path: Path,
    output_path: Path,
    tool_path: Path,
    plugin_path: Path,
) -> dict[str, Any]:
    """Build a content-bound receipt for a successful registered Torch stage."""

    root = Path(root).resolve()
    export_manifest_path = Path(export_manifest_path).resolve()
    output_path = Path(output_path).resolve()
    tool_path = Path(tool_path).resolve()
    plugin_path = Path(plugin_path).resolve()
    export_manifest = validate_export_manifest(
        load_object(export_manifest_path, "successor export manifest"), root
    )
    output_text = output_path.read_text(encoding="utf-8")
    raw_count = export_manifest["serial_gemv_operator_count"]
    remaining_raw_count = output_text.count(
        'torch.operator "torch.llm2fpga.serial_gemv"'
    )
    legalized_count = output_text.count('"llm2fpga.serial_gemv"')
    require(
        raw_count == 49 and remaining_raw_count == 0 and legalized_count == 49,
        "successful Torch artifact does not prove all exact serial-GEMV legalizations",
    )
    require(
        _historical_model_block_sha256(root) == HISTORICAL_MODEL_BLOCK_SHA256,
        "historical exact model registration changed",
    )
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-serial-gemv-torch-stage-v1",
        "model": SUCCESSOR_MODEL,
        "historical_model": {
            "model": "tiny-stories-1m-kev-gpt-exact",
            "registration_sha256": HISTORICAL_MODEL_BLOCK_SHA256,
            "preservation": "byte_for_byte_authoritative",
        },
        "timeout_seconds": 1800,
        "command": [
            "nix",
            "build",
            "--no-link",
            "--print-out-paths",
            "-L",
            f".#{SUCCESSOR_MODEL}-torch",
        ],
        "authority": verify_successor_authority(root),
        "registered_route": {
            name: file_binding(root / relative, root)
            for name, relative in ROUTE_SOURCES.items()
        },
        "compiler": {
            "torch_mlir_opt": file_binding(tool_path),
            "pass_plugin": file_binding(plugin_path),
        },
        "input": {
            "successor_export_manifest": file_binding(export_manifest_path),
            "exported_program": export_manifest["exported_program"],
            "serial_gemv_operator_count": raw_count,
        },
        "legalizer": {
            "status": "completed",
            "raw_serial_gemv_operator_count": raw_count,
            "remaining_raw_serial_gemv_operator_count": remaining_raw_count,
            "legalized_serial_gemv_operator_count": legalized_count,
        },
        "result": {
            "status": "artifact",
            "frontier": None,
            "output": file_binding(output_path),
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def _validate_source_bindings(bindings: object, root: Path) -> None:
    require(isinstance(bindings, dict) and bindings, "registered route bindings missing")
    for label, binding in bindings.items():
        require(isinstance(binding, dict), f"registered route {label} binding missing")
        path = root / str(binding.get("path", ""))
        require(
            path.is_file()
            and path.stat().st_size == binding.get("bytes")
            and sha256_file(path) == binding.get("sha256"),
            f"registered route {label} binding mismatch",
        )


def validate_artifact(value: dict[str, Any], root: Path) -> dict[str, Any]:
    """Authenticate a successful Torch artifact or a post-legalizer frontier."""

    root = Path(root).resolve()
    require(
        value.get("schema") == "tinystories-1m-exact-serial-gemv-torch-stage-v1"
        and value.get("model") == SUCCESSOR_MODEL
        and value.get("timeout_seconds") == 1800,
        "successor Torch-stage receipt identity mismatch",
    )
    _require_self_hash(value, "receipt_sha256", "successor Torch-stage receipt")
    require(
        value.get("historical_model") == {
            "model": "tiny-stories-1m-kev-gpt-exact",
            "registration_sha256": HISTORICAL_MODEL_BLOCK_SHA256,
            "preservation": "byte_for_byte_authoritative",
        }
        and _historical_model_block_sha256(root) == HISTORICAL_MODEL_BLOCK_SHA256,
        "historical exact model registration changed",
    )
    require(
        value.get("command") == [
            "nix",
            "build",
            "--no-link",
            "--print-out-paths",
            "-L",
            f".#{SUCCESSOR_MODEL}-torch",
        ],
        "successor Torch-stage command mismatch",
    )
    require(value.get("authority") == verify_successor_authority(root),
            "successor Torch-stage authority mismatch")
    _validate_source_bindings(value.get("registered_route"), root)

    compiler = value.get("compiler")
    require(isinstance(compiler, dict), "compiler bindings missing")
    for label in ("torch_mlir_opt", "pass_plugin"):
        binding = compiler.get(label)
        require(isinstance(binding, dict), f"compiler {label} binding missing")
        path = Path(str(binding.get("path", "")))
        require(
            path.is_file()
            and path.stat().st_size == binding.get("bytes")
            and sha256_file(path) == binding.get("sha256"),
            f"compiler {label} binding mismatch",
        )

    exported_binding = value.get("input", {}).get("successor_export_manifest")
    require(isinstance(exported_binding, dict), "successor export manifest binding missing")
    exported_manifest_path = Path(str(exported_binding.get("path", "")))
    require(
        exported_manifest_path.is_file()
        and exported_manifest_path.stat().st_size == exported_binding.get("bytes")
        and sha256_file(exported_manifest_path) == exported_binding.get("sha256"),
        "successor export manifest file binding mismatch",
    )
    validate_export_manifest(
        load_object(exported_manifest_path, "successor export manifest"), root
    )

    legalizer = value.get("legalizer")
    require(isinstance(legalizer, dict), "legalizer evidence missing")
    require(
        legalizer.get("status") == "completed"
        and legalizer.get("raw_serial_gemv_operator_count") == 49
        and legalizer.get("remaining_raw_serial_gemv_operator_count") == 0
        and legalizer.get("legalized_serial_gemv_operator_count") == 49,
        "exact serial-GEMV legalizer evidence mismatch",
    )
    result = value.get("result")
    require(isinstance(result, dict), "successor Torch-stage result missing")
    if result.get("status") == "artifact":
        require(result.get("frontier") is None, "successful Torch artifact names a frontier")
        output = result.get("output")
        require(isinstance(output, dict), "Torch artifact binding missing")
        output_path = Path(str(output.get("path", "")))
        require(
            output_path.is_file()
            and output_path.stat().st_size == output.get("bytes")
            and sha256_file(output_path) == output.get("sha256"),
            "Torch artifact binding mismatch",
        )
        output_text = output_path.read_text(encoding="utf-8")
        require(
            output_text.count('"llm2fpga.serial_gemv"')
            == legalizer.get("legalized_serial_gemv_operator_count")
            and output_text.count('torch.operator "torch.llm2fpga.serial_gemv"')
            == legalizer.get("remaining_raw_serial_gemv_operator_count")
            and legalizer.get("legalized_serial_gemv_operator_count") == 49
            and legalizer.get("remaining_raw_serial_gemv_operator_count") == 0,
            "Torch artifact legalization census mismatch",
        )
    else:
        require(
            result.get("status") == "diagnostic"
            and result.get("frontier") == "torch_mlir_frontier"
            and result.get("stage") == "fixed_backend_after_exact_serial_gemv",
            "successor diagnostic is not the first post-legalizer frontier",
        )
        diagnostic = result.get("diagnostic")
        require(isinstance(diagnostic, dict), "post-legalizer diagnostic binding missing")
        diagnostic_path = root / str(diagnostic.get("path", ""))
        require(
            diagnostic_path.is_file()
            and diagnostic_path.stat().st_size == diagnostic.get("bytes")
            and sha256_file(diagnostic_path) == diagnostic.get("sha256"),
            "post-legalizer diagnostic binding mismatch",
        )
        diagnostic_text = diagnostic_path.read_text(encoding="utf-8")
        require("exact package export provenance mismatch" not in diagnostic_text,
                "diagnostic regressed to historical identity frontier")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("verify-authority", "write-export", "write-artifact", "verify")
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--exported-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--tool", type=Path)
    parser.add_argument("--plugin", type=Path)
    args = parser.parse_args()
    if args.action == "verify-authority":
        result = verify_successor_authority(args.root)
    elif args.action == "write-export":
        require(args.exported_dir is not None and args.output is not None,
                "write-export requires --exported-dir and --output")
        result = build_export_manifest(args.root, args.exported_dir)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif args.action == "write-artifact":
        require(
            args.exported_dir is not None
            and args.output is not None
            and args.tool is not None
            and args.plugin is not None
            and args.receipt is not None,
            "write-artifact requires --exported-dir, --output, --tool, --plugin, and --receipt",
        )
        export_manifest = (
            args.exported_dir / "exact-serial-gemv-successor-provenance.json"
        )
        result = build_artifact_receipt(
            args.root, export_manifest, args.output, args.tool, args.plugin
        )
        args.receipt.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        require(args.receipt is not None, "verify requires --receipt")
        result = validate_artifact(
            load_object(args.receipt, "successor Torch-stage receipt"), args.root
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
