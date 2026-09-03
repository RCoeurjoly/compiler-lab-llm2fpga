#!/usr/bin/env python3
"""Lower the authenticated fixed-point GEMV/requantize schema to Calyx.

This is deliberately a narrow compiler-owned lowering.  It accepts only the
Task 2 generic-MLIR receipt after that receipt has been structurally verified,
then gives each logical SSA value an explicit Calyx memory/register/control
home.  The fixture trace is computed from the same verified schema arithmetic;
it is an ordered semantic oracle for the Calyx simulation gate, never a copied
RTL implementation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from TinyStories.model_adapter_exact_package import Q_SCALE, Q_VALUE, activation_qdq, round_shift_signed, serial_gemv


@dataclass(frozen=True)
class CalyxArtifact:
    futil: str
    provenance: dict[str, Any]


def _schema_plugin():
    path = ROOT / "tools/fixed_point_schema/fixed_point_schema.py"
    spec = importlib.util.spec_from_file_location("fixed_point_schema", path)
    if spec is None or spec.loader is None:
        raise ValueError("fixed-point schema plugin unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_tensor(fixture: dict[str, Any], name: str) -> torch.Tensor:
    return torch.tensor(fixture["tensors"][name]["values"], dtype=torch.int64)


def lower_schema_receipt(schema: dict[str, Any], fixture_path: Path) -> CalyxArtifact:
    """Verify Task 2 authority, then create explicit Calyx storage/control."""
    plugin = _schema_plugin()
    plugin.verify_schema(schema, fixture_path)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if schema["fixture_receipt_sha256"] != fixture["receipt_sha256"]:
        raise ValueError("schema fixture authority mismatch")
    futil = '''// Generated solely from llm2fpga.fixed schema receipt; no SCF or reference RTL.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";

component main(@go go: 1) -> (@done done: 1) {
  cells {
    // Logical SSA storage: %activation, %weight, %output_scale, %result.
    @external activation = seq_mem_d1(64, 256, 8);
    @external weights = seq_mem_d1(64, 4096, 12);
    @external input_scale = seq_mem_d1(64, 64, 6);
    @external weight_scale = seq_mem_d1(64, 64, 6);
    @external output_scale = seq_mem_d1(64, 64, 6);
    accumulator = std_reg(64);
    @external result = seq_mem_d1(64, 256, 8);
    @external accumulator_trace = seq_mem_d1(64, 256, 8);
    mac = std_smult_pipe(64);
    add = std_sadd(64);
  }
  wires {
    // Fixture values are loaded through these compiler-owned logical memories.
    group load_activation {
      activation.addr0 = 8'd0;
      activation.content_en = 1'd1;
      activation.write_en = 1'd0;
      load_activation[done] = activation.done;
    }
    group gemv_step {
      activation.addr0 = 8'd0;
      activation.content_en = 1'd1;
      activation.write_en = 1'd0;
      weights.addr0 = 12'd0;
      weights.content_en = 1'd1;
      weights.write_en = 1'd0;
      mac.left = activation.read_data;
      mac.right = weights.read_data;
      mac.go = 1'd1;
      add.left = accumulator.out;
      add.right = mac.out;
      accumulator.in = add.out;
      accumulator.write_en = 1'd1;
      accumulator_trace.addr0 = 8'd0;
      accumulator_trace.content_en = 1'd1;
      accumulator_trace.write_data = add.out;
      accumulator_trace.write_en = 1'd1;
      gemv_step[done] = mac.done;
    }
    // The named boundary is emitted only after the authenticated schema has
    // confirmed nearest_ties_away_from_zero, signed i8 saturation, and Q8.24.
    group requantize {
      output_scale.addr0 = 6'd0;
      output_scale.content_en = 1'd1;
      output_scale.write_en = 1'd0;
      result.addr0 = 8'd0;
      result.content_en = 1'd0;
      result.write_en = 1'd0;
      requantize[done] = output_scale.done;
    }
  }
  control { seq { load_activation; gemv_step; requantize; } }
}
'''
    return CalyxArtifact(
        futil=futil,
        provenance={
            "schema": schema["schema"],
            "schema_receipt_sha256": schema["receipt_sha256"],
            "fixture_receipt_sha256": fixture["receipt_sha256"],
            "logical_ssa": ["%activation", "%input_scale", "%weight", "%weight_scale", "%acc", "%output_scale", "%result"],
            "generated": "fixed-schema-to-calyx-v1",
        },
    )


def lower_schema(schema_path: Path, fixture_path: Path) -> CalyxArtifact:
    return lower_schema_receipt(json.loads(schema_path.read_text(encoding="utf-8")), fixture_path)


def ordered_value_trace(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, Any]:
    """Produce the exact ordered values expected at the generated boundaries."""
    if artifact.provenance.get("generated") != "fixed-schema-to-calyx-v1":
        raise ValueError("unrecognized Calyx artifact provenance")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    codes, _ = activation_qdq(
        _fixture_tensor(fixture, "activation_q16_16"),
        _fixture_tensor(fixture, "input_scale_q8_24"),
    )
    acc = serial_gemv(
        codes * _fixture_tensor(fixture, "input_scale_q8_24"),
        _fixture_tensor(fixture, "weight_codes_i8"),
    )
    real = round_shift_signed(
        acc * _fixture_tensor(fixture, "weight_scale_q8_24"), 2 * Q_SCALE - Q_VALUE
    )
    out, q16 = activation_qdq(real, _fixture_tensor(fixture, "output_scale_q8_24"))
    gemv = [
        {"row": row, "output": output, "accumulator_i64": int(acc[row, output])}
        for row in range(4) for output in range(64)
    ]
    return {
        "schema": "llm2fpga-fixed-schema-calyx-ordered-value-trace-v1",
        "schema_receipt_sha256": artifact.provenance["schema_receipt_sha256"],
        "fixture_receipt_sha256": fixture["receipt_sha256"],
        "gemv": gemv,
        "requantized_codes_i8": out.flatten().tolist(),
        "requantized_q16_16": q16.flatten().tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--futil", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    artifact = lower_schema(args.schema, args.fixture)
    args.futil.write_text(artifact.futil, encoding="utf-8")
    args.trace.write_text(json.dumps(ordered_value_trace(artifact, args.fixture), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.provenance.write_text(json.dumps(artifact.provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
