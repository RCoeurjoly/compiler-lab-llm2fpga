#!/usr/bin/env python3
"""Validate the immutable kev-gpt TinyStories-1M package as a compiler input.

This tool deliberately does *not* deserialize the package into a PyTorch
module.  The package is the frozen reference input, not compiler-generated
RTL; a later adapter must make that conversion while preserving every hash and
quantization rule recorded here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


class InputVerificationError(ValueError):
    """A frozen reference input was incomplete or did not authenticate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


FROZEN_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputVerificationError("invalid_json", f"{label}: {error}") from error
    if not isinstance(data, dict):
        raise InputVerificationError("invalid_json", f"{label} must be a JSON object")
    return data


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise InputVerificationError(code, message)


def _require_hash(path: Path, expected: object, label: str) -> str:
    _require(path.is_file(), "package_file_missing", f"missing {label}: {path}")
    _require(isinstance(expected, str) and len(expected) == 64,
             "invalid_contract", f"missing SHA-256 for {label}")
    actual = _sha256(path)
    _require(actual == expected, "package_hash_mismatch",
             f"{label} SHA-256 {actual} != frozen {expected}")
    return actual


def _require_equal(actual: object, expected: object, label: str) -> None:
    _require(actual == expected, "package_semantic_mismatch",
             f"{label}: {actual!r} != frozen {expected!r}")


def _validate_receipt(package: Path, receipt: dict[str, Any], manifest_hash: str) -> None:
    _require_equal(receipt.get("schema_version"), 1, "receipt.schema_version")
    _require_equal(receipt.get("manifest_sha256"), manifest_hash, "receipt.manifest_sha256")
    files = receipt.get("files")
    _require(isinstance(files, dict), "invalid_receipt", "receipt.files must be an object")
    for name, entry in sorted(files.items()):
        _require(isinstance(name, str) and isinstance(entry, dict),
                 "invalid_receipt", "receipt file entry is malformed")
        path = package / name
        _require(path.is_file(), "package_file_missing", f"receipt names absent {name}")
        _require_equal(entry.get("size"), path.stat().st_size, f"receipt.files.{name}.size")
        _require_equal(entry.get("sha256"), _sha256(path), f"receipt.files.{name}.sha256")


def _validate_model(contract: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    expected = contract.get("model")
    actual = manifest.get("model")
    _require(isinstance(expected, dict) and isinstance(actual, dict),
             "invalid_contract", "contract/package model identity missing")
    # The package manifest has no HF name or explicit head_dim.  They remain
    # authenticated by the frozen contract, while all representable package
    # fields are checked below.
    _require_equal(actual.get("source_revision"), expected["source_revision"], "model.source_revision")
    _require_equal(actual.get("model_type"), "gpt_neo", "model.model_type")
    _require_equal(actual.get("n_layer"), expected["n_layer"], "model.n_layer")
    _require_equal(actual.get("hidden_size"), expected["hidden_size"], "model.hidden_size")
    _require_equal(actual.get("n_head"), expected["n_head"], "model.n_head")
    _require_equal(actual.get("vocab_size"), expected["vocab_size"], "model.vocab_size")
    _require_equal(actual.get("max_context"), expected["max_context"], "model.max_context")
    _require_equal(actual.get("tie_word_embeddings"), expected["tie_word_embeddings"], "model.tie_word_embeddings")
    _require_equal(actual.get("activation_function"), expected["activation_function"], "model.activation_function")
    _require_equal(actual.get("head_dim"), expected["head_dim"], "model.head_dim")
    _require_equal(manifest.get("max_context"), expected["max_context"], "manifest.max_context")
    return {
        "source_model_id": expected["source_model_id"],
        "source_revision": actual["source_revision"],
        "model_type": actual.get("model_type"),
        "n_layer": actual["n_layer"],
        "hidden_size": actual["hidden_size"],
        "n_head": actual["n_head"],
        "head_dim": actual["head_dim"],
        "vocab_size": actual["vocab_size"],
        "max_context": actual["max_context"],
        "tie_word_embeddings": actual["tie_word_embeddings"],
        "activation_function": actual["activation_function"],
    }


def _validate_quantization(
    contract: dict[str, Any], manifest: dict[str, Any], weight_image: bytes, scale_image: bytes
) -> dict[str, Any]:
    contract_q = contract.get("quantization")
    _require(isinstance(contract_q, dict), "invalid_contract", "contract quantization missing")
    _require_equal(manifest.get("activation_format"), "symmetric_int8", "manifest.activation_format")
    tensors = manifest.get("tensors")
    overrides = manifest.get("weight_overrides")
    scales = manifest.get("activation_scales")
    _require(isinstance(tensors, dict) and isinstance(overrides, dict) and isinstance(scales, dict),
             "invalid_package", "package quantization fields missing")
    int8_weights = []
    weight_offset = 0
    scale_offset = 0
    for name, entry in sorted(tensors.items()):
        if not isinstance(entry, dict):
            raise InputVerificationError("invalid_package", f"tensor entry {name} is malformed")
        for key in ("offset", "nbytes", "scale_offset", "scale_nbytes", "sha256", "scale_sha256"):
            _require(key in entry, "invalid_package", f"tensors.{name}.{key} missing")
        _require_equal(entry["offset"], weight_offset, f"tensors.{name}.offset")
        _require_equal(entry["scale_offset"], scale_offset, f"tensors.{name}.scale_offset")
        _require(isinstance(entry["nbytes"], int) and entry["nbytes"] >= 0,
                 "invalid_package", f"tensors.{name}.nbytes is invalid")
        _require(isinstance(entry["scale_nbytes"], int) and entry["scale_nbytes"] >= 0,
                 "invalid_package", f"tensors.{name}.scale_nbytes is invalid")
        weight_end = weight_offset + entry["nbytes"]
        scale_end = scale_offset + entry["scale_nbytes"]
        _require(weight_end <= len(weight_image), "package_extent_mismatch",
                 f"tensors.{name} exceeds weights.bin")
        _require(scale_end <= len(scale_image), "package_extent_mismatch",
                 f"tensors.{name} exceeds scales.bin")
        _require_equal(hashlib.sha256(weight_image[weight_offset:weight_end]).hexdigest(),
                       entry["sha256"], f"tensors.{name}.sha256")
        _require_equal(hashlib.sha256(scale_image[scale_offset:scale_end]).hexdigest(),
                       entry["scale_sha256"], f"tensors.{name}.scale_sha256")
        weight_offset = weight_end
        scale_offset = scale_end
        if entry.get("format") == "symmetric_int8_per_output":
            _require_equal(entry.get("bits"), 8, f"tensors.{name}.bits")
            _require_equal(entry.get("signed"), True, f"tensors.{name}.signed")
            _require(isinstance(entry.get("scale_nbytes"), int) and entry["scale_nbytes"] > 0,
                     "invalid_package", f"tensors.{name} lacks output scales")
            int8_weights.append(name)
    _require_equal(weight_offset, len(weight_image), "tensors.weight_extent")
    _require_equal(scale_offset, len(scale_image), "tensors.scale_extent")
    _require_equal(len(int8_weights), 50, "tensors.int8_per_output_count")
    _require(set(overrides) == set(int8_weights), "package_semantic_mismatch",
             "weight_overrides must name exactly the INT8 per-output tensors")
    _require_equal(len(scales), 97, "activation_scale_entry_count")
    lengths = set()
    for name, values in sorted(scales.items()):
        _require(isinstance(name, str) and isinstance(values, list), "package_semantic_mismatch",
                 f"activation_scales.{name} must be a list")
        _require(len(values) in (64, 256), "package_semantic_mismatch",
                 f"activation_scales.{name} has unsupported width {len(values)}")
        _require(all(isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and value > 0 for value in values),
                 "package_semantic_mismatch", f"activation_scales.{name} must be finite and positive")
        lengths.add(len(values))
    _require_equal(sorted(lengths), [64, 256], "activation_scale_widths")
    _require_equal(contract_q.get("weights"), "symmetric per-output INT8", "contract.quantization.weights")
    _require_equal(contract_q.get("accumulator"), "signed INT32", "contract.quantization.accumulator")
    _require_equal(contract_q.get("scale_format"), "little-endian float32", "contract.quantization.scale_format")
    return {
        "weight_format": "symmetric_int8_per_output",
        "int8_weight_tensor_count": len(int8_weights),
        "activation_format": "symmetric_int8",
        "activation_scale_entries": len(scales),
        "activation_scale_lengths": sorted(lengths),
        "scale_format": "little-endian float32",
        "contract_detail": (
            "The frozen contract's high-level activation label is retained unchanged; "
            "the authenticated package manifest supplies the required 97 per-channel "
            "scale vectors (length 64 or 256)."
        ),
    }


def verify_input(contract_path: Path, package: Path) -> dict[str, Any]:
    """Authenticate the package and return the adapter input receipt.

    An authenticated receipt is intentionally not an equivalence claim: the
    current compiler exports FP32 checkpoint weights and cannot deserialize this
    canonical byte layout or replay its activation Q/DQ boundaries.
    """
    contract_path = Path(contract_path)
    package = Path(package)
    _require(contract_path.is_file(), "frozen_contract_missing", f"missing contract: {contract_path}")
    _require(_sha256(contract_path) == FROZEN_CONTRACT_SHA256, "frozen_contract_mismatch",
             "contract SHA-256 does not match the immutable frozen TinyStories-1M contract")
    contract = _load_json(contract_path, "frozen contract")
    _require_equal(contract.get("schema_version"), 1, "contract.schema_version")
    _require_equal(contract.get("model", {}).get("name"), "TinyStories-1M", "contract.model.name")
    package_contract = contract.get("package")
    _require(isinstance(package_contract, dict), "invalid_contract", "contract package missing")
    manifest_hash = _require_hash(package / "manifest.json", package_contract.get("manifest_sha256"), "manifest.json")
    _require_hash(package / "weights.bin", package_contract.get("sha256"), "weights.bin")
    files = package_contract.get("files")
    _require(isinstance(files, dict), "invalid_contract", "contract package file hashes missing")
    for name in ("scales.bin", "calibration_ids.bin", "receipt.json"):
        _require_hash(package / name, files.get(name), name)
    manifest = _load_json(package / "manifest.json", "package manifest")
    receipt = _load_json(package / "receipt.json", "package receipt")
    _validate_receipt(package, receipt, manifest_hash)
    model = _validate_model(contract, manifest)
    quantization = _validate_quantization(
        contract, manifest, (package / "weights.bin").read_bytes(), (package / "scales.bin").read_bytes()
    )
    package_files = manifest.get("files")
    _require(isinstance(package_files, dict), "invalid_package", "manifest.files missing")
    for name in ("weights.bin", "scales.bin", "calibration_ids.bin"):
        entry = package_files.get(name)
        _require(isinstance(entry, dict), "invalid_package", f"manifest.files.{name} missing")
        _require_equal(entry.get("sha256"), _sha256(package / name), f"manifest.files.{name}.sha256")
    return {
        "schema": "tinystories-1m-reference-compiler-input-v1",
        "status": "identity_verified_adapter_required",
        "frozen_contract_path": str(contract_path),
        "frozen_contract_sha256": _sha256(contract_path),
        "package": {
            "path": str(package),
            "manifest_sha256": manifest_hash,
            "weights_sha256": _sha256(package / "weights.bin"),
            "scales_sha256": _sha256(package / "scales.bin"),
            "calibration_ids_sha256": _sha256(package / "calibration_ids.bin"),
            "receipt_sha256": _sha256(package / "receipt.json"),
            "weight_bytes": (package / "weights.bin").stat().st_size,
            "scale_bytes": (package / "scales.bin").stat().st_size,
        },
        "model": model,
        "quantization": quantization,
        "adapter_requirement": (
            "The current FP32 compiler adapter does not deserialize the package or emit "
            "the package's weight dequantization and 97 activation Q/DQ boundaries. "
            "The next compiler adapter must consume only this authenticated receipt, map "
            "the canonical tensor names to GPT-Neo state keys, preserve the per-output "
            "INT8 scales and little-endian float32 scale image, and reject any hash mismatch."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = verify_input(args.contract, args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
