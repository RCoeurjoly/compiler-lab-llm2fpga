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
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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


def _checked_one_output_fixture(schema_path: Path, fixture_path: Path) -> dict[str, Any]:
    """Authenticate the Task-1 fixture and its Task-2 schema receipt.

    The narrow generated kernel has three full-shaped external memories.  Check
    their exact authenticated byte records before emitting either Futil or a
    simulator harness so a compatible-looking, but different, fixture cannot
    be substituted.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    plugin = _schema_plugin()
    plugin.verify_schema(schema, fixture_path)

    capture_path = ROOT / "TinyStories/capture_fixed_point_gemv_requantize_slice.py"
    capture_spec = importlib.util.spec_from_file_location("fixed_point_fixture_capture", capture_path)
    if capture_spec is None or capture_spec.loader is None:
        raise ValueError("fixed-point fixture verifier unavailable")
    capture = importlib.util.module_from_spec(capture_spec)
    sys.modules[capture_spec.name] = capture
    capture_spec.loader.exec_module(capture)
    fixture = capture.verify_fixture(fixture_path)

    expected = {
        "activation_codes_i8": ([4, 64], 2048),
        "input_scale_q8_24": ([64], 512),
        "activation_q16_16": ([4, 64], 2048),
        "weight_codes_i8": ([64, 64], 32768),
        "gemv_accumulator_i64": ([4, 64], 2048),
    }
    for name, (shape, byte_count) in expected.items():
        record = fixture["tensors"][name]
        if record["shape"] != shape or record["bytes"] != byte_count:
            raise ValueError(f"one-output kernel fixture memory shape mismatch: {name}")
        values = torch.tensor(record["values"], dtype=torch.int64).contiguous()
        raw = values.numpy().astype("<i8", copy=False).tobytes()
        if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != record["little_endian_int64_sha256"]:
            raise ValueError(f"one-output kernel fixture tensor bytes/hash mismatch: {name}")
    return fixture


def _one_output_kernel_futil() -> str:
    """Emit the fixed row-0/output-0, ordered 64-MAC Calyx kernel."""
    read_groups: list[str] = []
    scale_groups: list[str] = []
    multiply_groups: list[str] = []
    accumulate_groups: list[str] = []
    controls: list[str] = []
    for index in range(64):
        read_groups.append(
            f'''    group read_{index} {{
      activation.addr0 = 8'd{index};
      activation.content_en = 1'd1;
      input_scale.addr0 = 6'd{index};
      input_scale.content_en = 1'd1;
      weights.addr0 = 12'd{index};
      weights.content_en = 1'd1;
      read_{index}[done] = (activation.done & input_scale.done & weights.done) ? 1'd1;
    }}'''
        )
        scale_groups.append(
            f'''    group scale_activation_{index} {{
      activation_signed.in = activation.read_data;
      activation_scale.left = activation_signed.out;
      activation_scale.right = input_scale.read_data;
      activation_scale.go = 1'd1;
      scale_activation_{index}[done] = activation_scale.done;
    }}'''
        )
        multiply_groups.append(
            f'''    group multiply_{index} {{
      weight_signed.in = weights.read_data;
      mac.left = activation_scale.out;
      mac.right = weight_signed.out;
      mac.go = 1'd1;
      multiply_{index}[done] = mac.done;
    }}'''
        )
        accumulate_groups.append(
            f'''    group accumulate_{index} {{
      add.left = accumulator.out;
      add.right = mac.out;
      accumulator.in = add.out;
      accumulator.write_en = 1'd1;
      accumulate_{index}[done] = accumulator.done;
    }}'''
        )
        controls.extend((f"read_{index};", f"scale_activation_{index};", f"multiply_{index};", f"accumulate_{index};"))
    return f'''// Generated Task-1 exact fixed-point backend gate.
// It observes only row=0/output=0: ascending k=0..63 signed i64 wrapping MACs
// over authenticated signed-i8 codes, Q8.24 input scales, and signed-i8 weights.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";

component main(@go go: 1) -> (@done done: 1) {{
  cells {{
    @external activation = seq_mem_d1(8, 256, 8);
    @external input_scale = seq_mem_d1(64, 64, 6);
    @external weights = seq_mem_d1(8, 4096, 12);
    @external accumulator_trace = seq_mem_d1(64, 256, 8);
    accumulator = std_reg(64);
    activation_signed = std_signext(8, 64);
    weight_signed = std_signext(8, 64);
    activation_scale = std_smult_pipe(64);
    mac = std_smult_pipe(64);
    add = std_sadd(64);
  }}
  wires {{
    group init_accumulator {{
      accumulator.in = 64'd0;
      accumulator.write_en = 1'd1;
      init_accumulator[done] = accumulator.done;
    }}
{chr(10).join(read_groups)}
{chr(10).join(scale_groups)}
{chr(10).join(multiply_groups)}
{chr(10).join(accumulate_groups)}
    group write_accumulator_trace {{
      accumulator_trace.addr0 = 8'd0;
      accumulator_trace.content_en = 1'd1;
      accumulator_trace.write_data = accumulator.out;
      accumulator_trace.write_en = 1'd1;
      write_accumulator_trace[done] = accumulator_trace.done;
    }}
  }}
  control {{ seq {{ init_accumulator; {' '.join(controls)} write_accumulator_trace; }} }}
}}
'''


def generate_one_output_kernel(schema_path: Path, fixture_path: Path) -> CalyxArtifact:
    """Authenticate inputs and generate the single observed 64-MAC gate."""
    fixture = _checked_one_output_fixture(schema_path, fixture_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return CalyxArtifact(
        futil=_one_output_kernel_futil(),
        provenance={
            "generated": "fixed-schema-to-calyx-one-output-sv-v1",
            "schema_receipt_sha256": schema["receipt_sha256"],
            "fixture_receipt_sha256": fixture["receipt_sha256"],
            "memory_shapes": {"activation": [256, 8], "input_scale": [64, 64], "weights": [4096, 8], "accumulator_trace": [256, 64]},
            "kernel": {"row": 0, "output": 0, "ordered_macs": 64, "accumulator": "signed_i64_twos_complement_wrap"},
        },
    )


def _calyx_install() -> Path:
    completed = subprocess.run(
        ["nix", "build", "--no-link", "--print-out-paths", ".#calyx"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"unable to build pinned Calyx tool: {completed.stderr.strip()}")
    paths = [Path(line) for line in completed.stdout.splitlines() if line]
    if len(paths) != 1 or not (paths[0] / "bin/calyx").is_file():
        raise RuntimeError("pinned Calyx package did not yield one executable installation")
    return paths[0]


def _cpp_values(values: list[int]) -> str:
    return ", ".join(str(int(value)) for value in values)


def _generated_harness(fixture: dict[str, Any]) -> str:
    activation = [value for row in fixture["tensors"]["activation_codes_i8"]["values"] for value in row]
    input_scale = fixture["tensors"]["input_scale_q8_24"]["values"]
    weights = [value for row in fixture["tensors"]["weight_codes_i8"]["values"] for value in row]
    return f'''// Generated harness: fixture values are preload data, never an output oracle.
#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>

static const std::int64_t kActivation[256] = {{{_cpp_values(activation)}}};
static const std::int64_t kInputScale[64] = {{{_cpp_values(input_scale)}}};
static const std::int64_t kWeights[4096] = {{{_cpp_values(weights)}}};

static void tick(Vmain& model) {{
  model.clk = 0;
  model.eval();
  model.clk = 1;
  model.eval();
}}

int main(int argc, char** argv) {{
  Verilated::commandArgs(argc, argv);
  Vmain model;
  auto* root = model.rootp;
  for (unsigned i = 0; i < 256; ++i) {{
    root->main__DOT__activation__DOT__mem[i] = static_cast<std::uint8_t>(kActivation[i]);
    root->main__DOT__accumulator_trace__DOT__mem[i] = 0;
  }}
  for (unsigned i = 0; i < 64; ++i) {{
    root->main__DOT__input_scale__DOT__mem[i] = static_cast<std::uint64_t>(kInputScale[i]);
  }}
  for (unsigned i = 0; i < 4096; ++i) {{
    root->main__DOT__weights__DOT__mem[i] = static_cast<std::uint8_t>(kWeights[i]);
  }}
  model.reset = 1;
  model.go = 0;
  for (unsigned i = 0; i < 3; ++i) tick(model);
  model.reset = 0;
  model.go = 1;
  unsigned cycles = 0;
  while (!model.done && cycles < 2000) {{
    tick(model);
    ++cycles;
  }}
  const std::int64_t accumulator = static_cast<std::int64_t>(root->main__DOT__accumulator_trace__DOT__mem[0]);
  const bool complete = model.done && cycles > 64;
  std::cout << "{{\\\"status\\\":\\\"" << (complete ? "ok" : "mismatch")
            << "\\\",\\\"accumulator_i64\\\":" << accumulator
            << ",\\\"cycles\\\":" << cycles << "}}\\n";
  return complete ? 0 : 1;
}}
'''


def run_generated_sv(artifact: CalyxArtifact, fixture_path: Path, row: int, output: int) -> dict[str, int]:
    """Compile and execute the generated SV, returning its observed trace word."""
    if artifact.provenance.get("generated") != "fixed-schema-to-calyx-one-output-sv-v1":
        raise ValueError("unrecognized one-output generated-SV artifact provenance")
    if (row, output) != (0, 0):
        raise ValueError("Task-1 one-output kernel only supports row=0 and output=0")
    schema_receipt = artifact.provenance.get("schema_receipt_sha256")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("receipt_sha256") != artifact.provenance.get("fixture_receipt_sha256"):
        raise ValueError("generated-SV fixture authority mismatch")
    if not isinstance(schema_receipt, str) or len(schema_receipt) != 64:
        raise ValueError("generated-SV schema authority mismatch")
    activation = fixture["tensors"]["activation_codes_i8"]["values"]
    input_scale = fixture["tensors"]["input_scale_q8_24"]["values"]
    weights = fixture["tensors"]["weight_codes_i8"]["values"]
    if len(activation) != 4 or any(len(values) != 64 for values in activation) or len(input_scale) != 64 or len(weights) != 64 or any(len(values) != 64 for values in weights):
        raise ValueError("generated-SV fixture memory shape mismatch")

    artifact_dir = Path(tempfile.mkdtemp(prefix="fixed-point-calyx-sv-"))
    futil_path = artifact_dir / "one-output.futil"
    sv_path = artifact_dir / "main.sv"
    harness_path = artifact_dir / "harness.cpp"
    futil_path.write_text(artifact.futil, encoding="utf-8")
    harness_path.write_text(_generated_harness(fixture), encoding="utf-8")
    calyx = _calyx_install()
    calyx_run = subprocess.run(
        [str(calyx / "bin/calyx"), str(futil_path), "-l", str(calyx / "share/calyx"), "-b", "verilog", "-o", str(sv_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if calyx_run.returncode != 0 or not sv_path.is_file():
        raise RuntimeError(f"Calyx-to-SV failed: {calyx_run.stderr.strip()}")
    verilator_dir = artifact_dir / "verilator"
    verilator_run = subprocess.run(
        ["verilator", "--cc", "--exe", "--build", "--top-module", "main", "--public-flat-rw", "--Mdir", str(verilator_dir), "-CFLAGS", "-std=c++17", "-o", "fixed_point_harness", str(sv_path), str(harness_path)],
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    executable = verilator_dir / "fixed_point_harness"
    if verilator_run.returncode != 0 or not executable.is_file():
        raise RuntimeError(f"Verilator build failed: {verilator_run.stderr.strip()}")
    simulated = subprocess.run([str(executable)], text=True, capture_output=True, check=False, timeout=600)
    if simulated.returncode != 0:
        raise RuntimeError(f"generated-SV harness failed: {simulated.stdout.strip()} {simulated.stderr.strip()}")
    try:
        observed = json.loads(next(line for line in reversed(simulated.stdout.splitlines()) if line.startswith("{")))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"generated-SV harness did not emit JSON: {simulated.stdout!r}") from error
    except StopIteration as error:
        raise RuntimeError(f"generated-SV harness did not emit JSON: {simulated.stdout!r}") from error
    if observed.get("status") != "ok" or not isinstance(observed.get("accumulator_i64"), int) or not isinstance(observed.get("cycles"), int):
        raise RuntimeError(f"generated-SV harness observation is invalid: {observed}")
    artifact.provenance["generated_sv_artifacts"] = {
        "directory": str(artifact_dir),
        "futil": str(futil_path),
        "sv": str(sv_path),
        "harness": str(harness_path),
        "executable": str(executable),
    }
    return {"accumulator_i64": observed["accumulator_i64"], "cycles": observed["cycles"]}


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
