#!/usr/bin/env python3
"""Authenticate, probe, and receipt the kev-gpt TinyStories-1M Q/DQ rules.

The AGPL reference is executed as an oracle after its exact source identities
have been checked.  No reference implementation or RTL is copied into the
compiler.  The receipt intentionally remains incomplete where the frozen
contract does not select between the reference's floating and synthesizable
numeric profiles.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


SCHEMA = "tinystories-1m-qdq-semantics-v1"
EXPECTED_GIT_REVISION = "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f"
EXPECTED_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
EXPECTED_SOURCES = {
    "LICENSE": "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0",
    "tinystories/int_reference.py": "b6353d10d4227d676f78a7130af9a73fca2f0d68422f3215aec9307e0fb893d8",
    "tinystories/hardware_reference.py": "3780015d7f4be69cae3952fb630af971a37490a17cf8519fd6ac81a7bb080371",
    "tinystories/write_rtl_fixture.py": "c920b5e05cf44cef859ed40fd85d67b473a094e782a6e5b86941c0509714cb74",
    "fpga/rtl/gptneo_resident_gemv.sv": "2dc80a527e6c6c8bb48f76f607df20b8674e505c7e1162d2acf9901fc2c7ebb5",
    "fpga/rtl/gptneo_iterative_divider.sv": "8665cc99e7bf98e0415775a36c78aa4ff242d30c976dce0719e6d465686a1540",
    "host/kevin_jtag_cli.py": "e22a5916eef0cddeaaa0be9934e7b075f655b7d41f842ec8150d67c80f91204f",
}
CHECKPOINT_SHAPES: dict[str, tuple[int, ...]] = {
    "block.input": (64,),
    "block.ln_1.output": (64,),
    "block.attention.q": (16, 4),
    "block.attention.k": (16, 4),
    "block.attention.v": (16, 4),
    "block.attention.output": (64,),
    "block.residual.attention": (64,),
    "block.ln_2.output": (64,),
    "block.mlp.fc_in": (256,),
    "block.mlp.activation": (256,),
    "block.mlp.fc_out": (64,),
    "block.output": (64,),
}


class SemanticsAuthenticationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})


def oracle_sha256(oracle: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in oracle.items() if key != "sha256"})


def _require_integer_sequence(values: Iterable[Any], label: str) -> list[int]:
    result = list(values)
    if any(not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_)) for value in result):
        raise ValueError(f"{label} must contain integer values")
    return [int(value) for value in result]


def quantize_q16_to_int8(values_q16: Iterable[Any], scales_q24: Iterable[Any]) -> list[int]:
    """Fixed datapath activation quantization, including signed tie behavior."""

    values = _require_integer_sequence(values_q16, "values_q16")
    scales = _require_integer_sequence(scales_q24, "scales_q24")
    if len(values) != len(scales) or not values:
        raise ValueError("values and scales must have the same non-zero length")
    if any(scale <= 0 for scale in scales):
        raise ValueError("scales_q24 must be positive")
    result = []
    for value, scale in zip(values, scales, strict=True):
        numerator = value << 8
        magnitude = (abs(numerator) + scale // 2) // scale
        code = -magnitude if numerator < 0 else magnitude
        result.append(max(-128, min(127, code)))
    return result


def _round_shift_signed(value: int, shift: int) -> int:
    if shift < 0:
        raise ValueError("shift must be non-negative")
    if shift == 0:
        return value
    magnitude = (abs(value) + (1 << (shift - 1))) >> shift
    return -magnitude if value < 0 else magnitude


def dequantize_int8_to_q16(codes: Iterable[Any], scales_q24: Iterable[Any]) -> list[int]:
    code_values = _require_integer_sequence(codes, "codes")
    scales = _require_integer_sequence(scales_q24, "scales_q24")
    if len(code_values) != len(scales) or not code_values:
        raise ValueError("codes and scales must have the same non-zero length")
    if any(code < -128 or code > 127 for code in code_values):
        raise ValueError("codes must fit signed INT8")
    if any(scale <= 0 for scale in scales):
        raise ValueError("scales_q24 must be positive")
    return [_round_shift_signed(code * scale, 8) for code, scale in zip(code_values, scales, strict=True)]


def _wrap_signed(value: int, width: int) -> int:
    mask = (1 << width) - 1
    unsigned = value & mask
    sign = 1 << (width - 1)
    return unsigned - (1 << width) if unsigned & sign else unsigned


def serial_weight_accumulate(
    activation_codes: Iterable[Any],
    activation_scales_q24: Iterable[Any],
    weight_codes: Iterable[Any],
) -> tuple[int, list[int]]:
    """Accumulate one output row exactly in ascending input-index order."""

    activations = _require_integer_sequence(activation_codes, "activation_codes")
    scales = _require_integer_sequence(activation_scales_q24, "activation_scales_q24")
    weights = _require_integer_sequence(weight_codes, "weight_codes")
    if not activations or len(activations) != len(scales) or len(activations) != len(weights):
        raise ValueError("activation codes, scales, and weight codes must have the same non-zero length")
    if any(code < -128 or code > 127 for code in activations + weights):
        raise ValueError("activation and weight codes must fit signed INT8")
    if any(scale <= 0 for scale in scales):
        raise ValueError("activation scales must be positive")
    accumulator = 0
    terms = []
    for index in range(len(activations)):
        term = activations[index] * scales[index] * weights[index]
        terms.append(term)
        accumulator = _wrap_signed(accumulator + term, 64)
    return accumulator, terms


def float_to_fixed(
    values: Iterable[Any], fractional_bits: int, width: int, *, signed: bool = True
) -> list[int]:
    """Materialization rule: finite binary value, nearest ties-to-even, clamp."""

    if fractional_bits < 0 or width <= 0:
        raise ValueError("fractional_bits and width are invalid")
    lower = -(1 << (width - 1)) if signed else 0
    upper = (1 << (width - (1 if signed else 0))) - 1
    result = []
    for value in values:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise ValueError("fixed-point inputs must be numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("non-finite fixed-point input")
        rounded = round(numeric * (1 << fractional_bits))
        result.append(max(lower, min(upper, rounded)))
    return result


def _authenticate_sources(reference_root: Path) -> tuple[str, list[dict[str, str]]]:
    sources = []
    for relative, expected in EXPECTED_SOURCES.items():
        path = reference_root / relative
        if not path.is_file():
            raise SemanticsAuthenticationError("source_missing", f"missing {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise SemanticsAuthenticationError(
                "source_hash_mismatch", f"{relative}: {actual} != {expected}"
            )
        sources.append({"path": relative, "sha256": actual})
    license_text = (reference_root / "LICENSE").read_text(encoding="utf-8")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text or "Version 3" not in license_text:
        raise SemanticsAuthenticationError("license_mismatch", "reference is not AGPL version 3")
    try:
        revision = subprocess.run(
            ["git", "-C", str(reference_root), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        selected_status = subprocess.run(
            ["git", "-C", str(reference_root), "status", "--porcelain", "--", *EXPECTED_SOURCES],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise SemanticsAuthenticationError("git_identity_unavailable", error.stderr.strip()) from error
    if revision != EXPECTED_GIT_REVISION:
        raise SemanticsAuthenticationError("git_revision_mismatch", f"{revision} != {EXPECTED_GIT_REVISION}")
    if selected_status:
        raise SemanticsAuthenticationError("source_worktree_dirty", selected_status)
    return revision, sources


def _load_reference_modules(reference_root: Path) -> tuple[Any, Any]:
    root = str(reference_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    integer_reference = importlib.import_module("tinystories.int_reference")
    hardware_reference = importlib.import_module("tinystories.hardware_reference")
    if Path(integer_reference.__file__).resolve() != (reference_root / "tinystories/int_reference.py").resolve():
        raise SemanticsAuthenticationError("module_origin_mismatch", str(integer_reference.__file__))
    if Path(hardware_reference.__file__).resolve() != (reference_root / "tinystories/hardware_reference.py").resolve():
        raise SemanticsAuthenticationError("module_origin_mismatch", str(hardware_reference.__file__))
    return integer_reference, hardware_reference


def _profile_conflict(integer_reference: Any, hardware_reference: Any) -> dict[str, Any]:
    floating = integer_reference.IntegerGPTNeo.__new__(integer_reference.IntegerGPTNeo)
    floating.activation_scales = {"probe": np.asarray([1.0], dtype=np.float32)}
    floating_code = int(floating._a8_codes(np.asarray([0.5], dtype=np.float32), "probe")[0][0])
    fixed = hardware_reference.FixedGPTNeo.__new__(hardware_reference.FixedGPTNeo)
    fixed.activation_scales = {"probe": np.asarray([512], dtype=np.int64)}
    fixed_code = int(fixed._activation_codes(np.asarray([1], dtype=np.int64), "probe")[0])
    if (floating_code, fixed_code) != (0, 1):
        raise SemanticsAuthenticationError("rounding_probe_mismatch", f"{floating_code}, {fixed_code}")
    return {
        "rounding_witness": {
            "mathematical_ratio": "positive_one_half",
            "floating_integer_reference_code": floating_code,
            "fixed_hardware_reference_code": fixed_code,
        },
        "accumulator_witness": {
            "frozen_contract": "signed INT32",
            "floating_integer_reference": "ordered float64 scaled-product reduction",
            "fixed_hardware_reference": "signed INT64",
            "synthesizable_gemv": "signed 64-bit serial accumulator",
        },
        "activation_scale_granularity_witness": {
            "frozen_contract": "symmetric per-tensor INT8",
            "package_and_both_executable_references": "97 per-channel scale vectors",
        },
    }


def _payload(value: np.ndarray, shape: Sequence[int]) -> dict[str, Any]:
    array = np.asarray(value, dtype=np.int64)
    if tuple(array.shape) != tuple(shape):
        raise SemanticsAuthenticationError("oracle_shape_mismatch", f"{array.shape} != {tuple(shape)}")
    payload = {"shape": list(shape), "dtype": "signed_q16.16", "values": array.tolist()}
    return {**payload, "sha256": canonical_sha256(payload)}


def _fixed_oracle(hardware_reference: Any, package: Path, prompt_tokens: list[int]) -> dict[str, Any]:
    """Observe the fixed runtime without reproducing its transformer logic."""

    model = hardware_reference.FixedGPTNeo(package)
    layernorm_calls: list[tuple[np.ndarray, np.ndarray]] = []
    gelu_calls: list[np.ndarray] = []
    gemv_outputs: dict[str, np.ndarray] = {}
    original_layernorm = hardware_reference.fixed_layer_norm
    original_gelu = hardware_reference.fixed_gelu
    original_gemv = model._gemv

    def trace_layernorm(values: np.ndarray, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
        output = original_layernorm(values, gamma, beta)
        layernorm_calls.append((np.array(values, copy=True), np.array(output, copy=True)))
        return output

    def trace_gelu(values: np.ndarray) -> np.ndarray:
        output = original_gelu(values)
        gelu_calls.append(np.array(output, copy=True))
        return output

    def trace_gemv(values: np.ndarray, weight: str, bias: str | None,
                   module: str, output_quantized: bool = True) -> np.ndarray:
        output = original_gemv(values, weight, bias, module, output_quantized)
        gemv_outputs[module] = np.array(output, copy=True)
        return output

    hardware_reference.fixed_layer_norm = trace_layernorm
    hardware_reference.fixed_gelu = trace_gelu
    model._gemv = trace_gemv
    try:
        logits = model.forward(prompt_tokens)
    finally:
        model._gemv = original_gemv
        hardware_reference.fixed_gelu = original_gelu
        hardware_reference.fixed_layer_norm = original_layernorm

    if len(layernorm_calls) < 3 or not gelu_calls:
        raise SemanticsAuthenticationError("oracle_trace_incomplete", "fixed runtime hooks did not fire")
    block = "transformer.h.0"
    last = -1
    values: dict[str, np.ndarray] = {
        "block.input": layernorm_calls[0][0][last],
        "block.ln_1.output": layernorm_calls[0][1][last],
        "block.attention.q": gemv_outputs[f"{block}.attn.attention.q_proj"][last].reshape(16, 4),
        "block.attention.k": gemv_outputs[f"{block}.attn.attention.k_proj"][last].reshape(16, 4),
        "block.attention.v": gemv_outputs[f"{block}.attn.attention.v_proj"][last].reshape(16, 4),
        "block.attention.output": gemv_outputs[f"{block}.attn.attention.out_proj"][last],
        "block.residual.attention": layernorm_calls[1][0][last],
        "block.ln_2.output": layernorm_calls[1][1][last],
        "block.mlp.fc_in": gemv_outputs[f"{block}.mlp.c_fc"][last],
        "block.mlp.activation": gelu_calls[0][last],
        "block.mlp.fc_out": gemv_outputs[f"{block}.mlp.c_proj"][last],
        "block.output": layernorm_calls[2][0][last],
    }
    checkpoints = {
        name: _payload(values[name], shape) for name, shape in CHECKPOINT_SHAPES.items()
    }
    oracle: dict[str, Any] = {
        "status": "runtime_authenticated_not_board_checkpoint_authenticated",
        "profile": "fixed_hardware_reference",
        "block_index": 0,
        "token_index": len(prompt_tokens) - 1,
        "prompt_tokens": prompt_tokens,
        "next_token": int(np.argmax(logits[-1])),
        "checkpoint_order": list(CHECKPOINT_SHAPES),
        "checkpoints": checkpoints,
    }
    oracle["sha256"] = oracle_sha256(oracle)
    return oracle


def build_receipt(reference_root: Path, contract_path: Path, package: Path) -> dict[str, Any]:
    reference_root = Path(reference_root)
    contract_path = Path(contract_path)
    package = Path(package)
    revision, sources = _authenticate_sources(reference_root)
    if not contract_path.is_file() or _sha256(contract_path) != EXPECTED_CONTRACT_SHA256:
        raise SemanticsAuthenticationError("contract_identity_mismatch", str(contract_path))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    package_identity = contract.get("package", {})
    for name, expected in package_identity.get("files", {}).items():
        path = package / name
        if not path.is_file() or _sha256(path) != expected:
            raise SemanticsAuthenticationError("package_identity_mismatch", name)
    integer_reference, hardware_reference = _load_reference_modules(reference_root)
    conflict = _profile_conflict(integer_reference, hardware_reference)
    prompt = list(contract["reference"]["prompt_tokens"])
    oracle = _fixed_oracle(hardware_reference, package, prompt)
    if oracle["next_token"] != contract["reference"]["tokens"][0]:
        raise SemanticsAuthenticationError(
            "oracle_token_mismatch",
            f"fixed runtime token {oracle['next_token']} != frozen {contract['reference']['tokens'][0]}",
        )
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    activation_scales = manifest["activation_scales"]
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "incomplete",
        "selected_profile": None,
        "identity": {
            "contract_sha256": _sha256(contract_path),
            "package_manifest_sha256": _sha256(package / "manifest.json"),
            "package_weights_sha256": _sha256(package / "weights.bin"),
            "package_scales_sha256": _sha256(package / "scales.bin"),
        },
        "authority": {
            "kind": "content_authenticated_local_agpl_reference",
            "git_revision": revision,
            "selected_sources_clean_at_generation": True,
            "license": {"spdx": "AGPL-3.0-only", "sha256": EXPECTED_SOURCES["LICENSE"]},
            "sources": sources,
            "host_role": "transport_and_tokenizer_only",
            "host_inference_statement": "FPGA inference is not emulated by the host client",
        },
        "profiles": {
            "floating_integer_reference": {
                "role": "package_quality_and_regression_reference",
                "activation_conversion": {
                    "input_dtype": "float32",
                    "scale_dtype": "little-endian float32",
                    "rounding": "nearest_ties_to_even_via_numpy_rint",
                    "clamp": [-128, 127],
                    "zero_point": 0,
                    "dequantized_dtype": "float32",
                },
                "non_finite_policy": "not_explicitly_rejected_by_reference_runtime",
                "accumulation": {
                    "product": "signed_int8_code_product_promoted_to_int32",
                    "scaling": "per-input-channel_activation_scale_float64_before_reduction",
                    "reduction": "numpy_sum_float64_last_axis",
                    "weight_scale_application": "per-output-channel_float64_after_reduction",
                },
            },
            "fixed_hardware_reference": {
                "role": "synthesizable_datapath_reference",
                "parameter_materialization": {
                    "value_format": "signed_q16.16_int32",
                    "scale_format": "unsigned_q8.24_u24",
                    "source_scale_format": "little-endian_float32",
                    "byte_order": "little",
                    "rounding": "nearest_ties_to_even",
                },
                "activation_conversion": {
                    "input": "signed_q16.16_int32",
                    "scale": "per-channel_unsigned_q8.24_u24",
                    "rounding": "nearest_ties_away_from_zero",
                    "clamp": [-128, 127],
                    "zero_point": 0,
                    "dequantization": "signed_int8_code_times_q8.24_scale_then_signed_half_away_shift_by_8",
                    "result": "signed_q16.16_int32",
                },
                "activation_boundaries": {
                    "count": len(activation_scales),
                    "widths": sorted({len(values) for values in activation_scales.values()}),
                    "scale_interpretation": "one positive scale per last-dimension channel",
                    "placement": "module_input_and_module_output_except_lm_head_input_only",
                    "names_sha256": canonical_sha256(sorted(activation_scales)),
                },
                "accumulation": {
                    "term": "activation_code_i_times_activation_scale_q24_i_times_weight_code_output_i",
                    "input_order": "ascending_input_index",
                    "logical_width_bits": 64,
                    "overflow": "twos_complement_wrap",
                },
                "weight_scale": {
                    "axis": "output_channel",
                    "application": "signed_int64_accumulator_times_unsigned_q8.24_scale",
                    "rounding": "nearest_ties_away_from_zero_by_signed_shift_32",
                    "bias_order": "add_signed_q16.16_bias_after_weight_scale",
                },
                "non_finite_policy": "reject_before_fixed_point_materialization",
                "execution_domain": "integers_only_after_materialization",
            },
        },
        "profile_conflict": conflict,
        "candidate_oracle": oracle,
        "incomplete_reasons": [
            {
                "code": "reference_profile_not_selected_by_frozen_contract",
                "missing_authority": (
                    "The frozen contract names tinystories/int_reference.py but does not content-bind it "
                    "or designate the distinct fixed hardware profile as compiler semantics."
                ),
            },
            {
                "code": "accumulator_width_conflict",
                "missing_authority": (
                    "The frozen contract says signed INT32; the fixed executable reference and "
                    "synthesizable GEMV use a signed 64-bit accumulator."
                ),
            },
            {
                "code": "activation_scale_granularity_conflict",
                "missing_authority": (
                    "The frozen contract says per-tensor activation INT8; the authenticated package "
                    "and executable references use 97 per-channel scale vectors."
                ),
            },
            {
                "code": "oracle_not_board_checkpoint_authenticated",
                "missing_authority": (
                    "The host exposes final tokens and only a small debug snapshot, not the full "
                    "12-checkpoint block trace needed to bind this runtime oracle to board execution."
                ),
            },
        ],
    }
    receipt["receipt_sha256"] = receipt_sha256(receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = build_receipt(args.reference_root, args.contract, args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
