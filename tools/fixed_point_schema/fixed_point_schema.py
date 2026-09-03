#!/usr/bin/env python3
"""Out-of-tree generic-MLIR schema for one exact fixed-point GEMV/QDQ slice."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from TinyStories.model_adapter_exact_package import Q_SCALE, Q_VALUE, activation_qdq, round_shift_signed, serial_gemv

SCHEMA = "llm2fpga-fixed-point-gemv-requantize-schema-v1"


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("schema") != "tinystories-1m-fixed-point-gemv-requantize-slice-v1" or value.get("receipt_sha256") != canonical(payload):
        raise ValueError("Task1 fixture authority mismatch")
    return value


def _t(value: dict[str, Any], name: str) -> torch.Tensor:
    return torch.tensor(value["tensors"][name]["values"], dtype=torch.int64)


def _record(value: torch.Tensor) -> dict[str, object]:
    value = value.detach().cpu().contiguous().to(torch.int64)
    raw = value.numpy().astype("<i8", copy=False).tobytes()
    return {"little_endian_int64_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def fixture_output_hashes(path: Path) -> dict[str, dict[str, object]]:
    value = load_fixture(path)
    return {name: {key: value["tensors"][name][key] for key in ("little_endian_int64_sha256", "bytes")}
            for name in ("gemv_accumulator_i64", "requantized_codes_i8", "requantized_q16_16")}


def _requantize_attrs(value: dict[str, Any]) -> dict[str, object]:
    return {"scale": value["tensors"]["output_scale_q8_24"]["little_endian_int64_sha256"],
            "scale_format": "per_channel_unsigned_q8_24_i64",
            "rounding": "nearest_ties_away_from_zero", "signedness": "signed",
            "saturation": [-128, 127], "width": 8}


def build_schema(fixture: Path) -> dict[str, Any]:
    value = load_fixture(fixture)
    req = _requantize_attrs(value)
    mlir = '''module {
  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>
  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>
  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %acc = "fixed.gemv"(%activation, %input_scale, %weight, %weight_scale) {accumulator = "signed_i64_twos_complement_wrap", rows = 4 : i64, inputs = 64 : i64, outputs = 64 : i64} : (tensor<4x64xi64>, tensor<64xi64>, tensor<64x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
  %result = "fixed.requantize"(%acc) {scale = "PER_CHANNEL_Q8_24", rounding = "nearest_ties_away_from_zero", signedness = "signed", saturation = [-128, 127], width = 8 : i64} : (tensor<4x64xi64>) -> tensor<4x64xi64>
}'''
    result = {"schema": SCHEMA, "fixture_receipt_sha256": value["receipt_sha256"],
              "logical_ssa": {"activation": "tensor<4x64xi64>", "input_scale": "tensor<64xi64>", "weight": "tensor<64x64xi64>", "weight_scale": "tensor<64xi64>", "accumulator": "tensor<4x64xi64>", "requantized": "tensor<4x64xi64>"},
              "gemv": {"rows": 4, "inputs": 64, "outputs": 64, "accumulator": "signed_i64_twos_complement_wrap"},
              "requantize": req, "mlir": mlir, "expected_output_hashes": fixture_output_hashes(fixture)}
    result["receipt_sha256"] = canonical(result)
    return result


def verify_schema(schema: dict[str, Any], fixture: Path) -> None:
    value = load_fixture(fixture)
    required = _requantize_attrs(value)
    if schema.get("schema") != SCHEMA or schema.get("fixture_receipt_sha256") != value["receipt_sha256"]:
        raise ValueError("schema fixture authority mismatch")
    if schema.get("requantize") != required:
        raise ValueError("requantize attributes mismatch")
    if '"fixed.gemv"' not in schema.get("mlir", "") or '"fixed.requantize"' not in schema["mlir"]:
        raise ValueError("logical SSA generic MLIR missing")
    payload = {key: item for key, item in schema.items() if key != "receipt_sha256"}
    if schema.get("receipt_sha256") != canonical(payload):
        raise ValueError("schema self-hash mismatch")
    if evaluate_schema(schema, fixture) != fixture_output_hashes(fixture):
        raise ValueError("schema evaluation hash mismatch")


def evaluate_schema(schema: dict[str, Any], fixture: Path) -> dict[str, dict[str, object]]:
    value = load_fixture(fixture)
    activation = _t(value, "activation_q16_16")
    input_codes, _ = activation_qdq(activation, _t(value, "input_scale_q8_24"))
    accumulator = serial_gemv(input_codes * _t(value, "input_scale_q8_24"), _t(value, "weight_codes_i8"))
    real_q16 = round_shift_signed(accumulator * _t(value, "weight_scale_q8_24"), 2 * Q_SCALE - Q_VALUE)
    output_codes, output_q16 = activation_qdq(real_q16, _t(value, "output_scale_q8_24"))
    return {"gemv_accumulator_i64": _record(accumulator), "requantized_codes_i8": _record(output_codes), "requantized_q16_16": _record(output_q16)}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--fixture", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--mlir-output", type=Path); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_schema(json.loads(args.output.read_text()), args.fixture)
    else:
        value = build_schema(args.fixture)
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        if args.mlir_output is not None:
            args.mlir_output.parent.mkdir(parents=True, exist_ok=True); args.mlir_output.write_text(value["mlir"] + "\n")


if __name__ == "__main__": main()
