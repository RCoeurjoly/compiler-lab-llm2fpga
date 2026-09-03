#!/usr/bin/env python3
"""Generate and run the authenticated exact fixed-point GELU hardware gate."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CalyxArtifact:
    futil: str
    provenance: dict[str, Any]


def _capture_module():
    path = ROOT / "TinyStories/capture_fixed_point_mlp_crossing_slice.py"
    spec = importlib.util.spec_from_file_location(
        "fixed_point_mlp_crossing_capture_for_calyx", path
    )
    if spec is None or spec.loader is None:
        raise ValueError("authenticated MLP fixture verifier unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _checked_gelu_fixture(fixture_path: Path) -> dict[str, Any]:
    """Authenticate every fixture record before consuming GELU memories."""
    fixture = _capture_module().verify_fixture(fixture_path)
    if fixture["arithmetic"].get("gelu") != "exact_q12_8192_entry_lut_linear_interpolation":
        raise ValueError("fixture GELU arithmetic authority mismatch")
    expected = {
        "gelu_input_q16_16": ([4, 256], 8192),
        "gelu_lut_q12": ([8192], 65536),
        "gelu_output_q16_16": ([4, 256], 8192),
    }
    for name, (shape, byte_count) in expected.items():
        record = fixture["tensors"][name]
        if record["shape"] != shape or record["bytes"] != byte_count:
            raise ValueError(f"fixture GELU memory contract mismatch: {name}")
    return fixture


def _fixture_authority(fixture: dict[str, Any]) -> dict[str, Any]:
    """Bind generated artifacts to the complete authenticated fixture content."""
    return {
        "receipt_sha256": fixture["receipt_sha256"],
        "tensor_fixture_receipt_sha256": fixture[
            "tensor_fixture_receipt_sha256"
        ],
        "identity": fixture["identity"],
        "arithmetic": fixture["arithmetic"],
        "tensors": {
            name: {
                "shape": record["shape"],
                "dtype": record["dtype"],
                "bytes": record["bytes"],
                "canonical_sha256": record["canonical_sha256"],
                "little_endian_int64_sha256": record[
                    "little_endian_int64_sha256"
                ],
            }
            for name, record in sorted(fixture["tensors"].items())
        },
    }


def _gelu_kernel_futil() -> str:
    """Emit the exact 1,024-entry LUT/interpolated GELU datapath."""
    return '''// Generated exact fixed-point GELU gate from authenticated fixture authority.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";

component main(@go go: 1) -> (@done done: 1) {
  cells {
    @external gelu_input_q16_16 = seq_mem_d1(64, 1024, 10);
    @external gelu_lut_q12 = seq_mem_d1(64, 8192, 13);
    @external gelu_q16_16 = seq_mem_d1(64, 1024, 10);

    entry_counter = std_reg(11);
    entry_lt = std_lt(11);
    increment_entry = std_add(11);
    entry_address = std_slice(11, 10);

    input_negative = std_slt(64);
    input_negate = std_ssub(64);
    input_abs = std_mux(64);
    rounding_bias = std_sadd(64);
    magnitude_shift = std_rsh(64);
    rounded_negate = std_ssub(64);
    rounded = std_mux(64);
    negative_q12_min = std_ssub(64);
    rounded_lt_min = std_slt(64);
    rounded_gt_max = std_sgt(64);
    lower_clamp = std_mux(64);
    q12_clamp = std_mux(64);
    q12 = std_reg(64);

    biased_q12 = std_sadd(64);
    index_shift = std_rsh(64);
    index_slice = std_slice(64, 13);
    fraction_slice = std_slice(64, 3);
    index_is_last = std_eq(13);
    index_increment = std_add(13);
    upper_index = std_mux(13);
    index = std_reg(13);
    upper = std_reg(13);
    fraction = std_reg(3);

    lower_lut = std_reg(64);
    interpolation_delta = std_ssub(64);
    fraction_pad = std_pad(3, 64);
    interpolation_product = std_smult_pipe(64);
    interpolation_shift = std_srsh(64);
    interpolation_sum = std_sadd(64);
    result_shift = std_slsh(64);
  }
  wires {
    entry_address.in = entry_counter.out;

    group init_entry {
      entry_counter.in = 11'd0;
      entry_counter.write_en = 1'd1;
      init_entry[done] = entry_counter.done;
    }
    group read_input {
      gelu_input_q16_16.addr0 = entry_address.out;
      gelu_input_q16_16.content_en = 1'd1;
      read_input[done] = gelu_input_q16_16.done;
    }
    group round_and_clamp_q12 {
      input_negative.left = gelu_input_q16_16.read_data;
      input_negative.right = 64'd0;
      input_negate.left = 64'd0;
      input_negate.right = gelu_input_q16_16.read_data;
      input_abs.cond = input_negative.out;
      input_abs.tru = input_negate.out;
      input_abs.fal = gelu_input_q16_16.read_data;
      rounding_bias.left = input_abs.out;
      rounding_bias.right = 64'd8;
      magnitude_shift.left = rounding_bias.out;
      magnitude_shift.right = 64'd4;
      rounded_negate.left = 64'd0;
      rounded_negate.right = magnitude_shift.out;
      rounded.cond = input_negative.out;
      rounded.tru = rounded_negate.out;
      rounded.fal = magnitude_shift.out;
      negative_q12_min.left = 64'd0;
      negative_q12_min.right = 64'd32768;
      rounded_lt_min.left = rounded.out;
      rounded_lt_min.right = negative_q12_min.out;
      rounded_gt_max.left = rounded.out;
      rounded_gt_max.right = 64'd32767;
      lower_clamp.cond = rounded_lt_min.out;
      lower_clamp.tru = negative_q12_min.out;
      lower_clamp.fal = rounded.out;
      q12_clamp.cond = rounded_gt_max.out;
      q12_clamp.tru = 64'd32767;
      q12_clamp.fal = lower_clamp.out;
      q12.in = q12_clamp.out;
      q12.write_en = 1'd1;
      round_and_clamp_q12[done] = q12.done;
    }
    group latch_lookup_coordinates {
      biased_q12.left = q12.out;
      biased_q12.right = 64'd32768;
      index_shift.left = biased_q12.out;
      index_shift.right = 64'd3;
      index_slice.in = index_shift.out;
      fraction_slice.in = biased_q12.out;
      index_is_last.left = index_slice.out;
      index_is_last.right = 13'd8191;
      index_increment.left = index_slice.out;
      index_increment.right = 13'd1;
      upper_index.cond = index_is_last.out;
      upper_index.tru = 13'd8191;
      upper_index.fal = index_increment.out;
      index.in = index_slice.out;
      index.write_en = 1'd1;
      upper.in = upper_index.out;
      upper.write_en = 1'd1;
      fraction.in = fraction_slice.out;
      fraction.write_en = 1'd1;
      latch_lookup_coordinates[done] = (index.done & upper.done & fraction.done) ? 1'd1;
    }
    group read_lower_lut {
      gelu_lut_q12.addr0 = index.out;
      gelu_lut_q12.content_en = 1'd1;
      read_lower_lut[done] = gelu_lut_q12.done;
    }
    group latch_lower_lut {
      lower_lut.in = gelu_lut_q12.read_data;
      lower_lut.write_en = 1'd1;
      latch_lower_lut[done] = lower_lut.done;
    }
    group read_upper_lut {
      gelu_lut_q12.addr0 = upper.out;
      gelu_lut_q12.content_en = 1'd1;
      read_upper_lut[done] = gelu_lut_q12.done;
    }
    group multiply_interpolation {
      interpolation_delta.left = gelu_lut_q12.read_data;
      interpolation_delta.right = lower_lut.out;
      fraction_pad.in = fraction.out;
      interpolation_product.left = interpolation_delta.out;
      interpolation_product.right = fraction_pad.out;
      interpolation_product.go = 1'd1;
      multiply_interpolation[done] = interpolation_product.done;
    }
    group write_result {
      interpolation_shift.left = interpolation_product.out;
      interpolation_shift.right = 64'd3;
      interpolation_sum.left = lower_lut.out;
      interpolation_sum.right = interpolation_shift.out;
      result_shift.left = interpolation_sum.out;
      result_shift.right = 64'd4;
      gelu_q16_16.addr0 = entry_address.out;
      gelu_q16_16.content_en = 1'd1;
      gelu_q16_16.write_data = result_shift.out;
      gelu_q16_16.write_en = 1'd1;
      write_result[done] = gelu_q16_16.done;
    }
    group increment_entry_counter {
      increment_entry.left = entry_counter.out;
      increment_entry.right = 11'd1;
      entry_counter.in = increment_entry.out;
      entry_counter.write_en = 1'd1;
      increment_entry_counter[done] = entry_counter.done;
    }
    comb group entry_condition {
      entry_lt.left = entry_counter.out;
      entry_lt.right = 11'd1024;
    }
  }
  control {
    seq {
      init_entry;
      while entry_lt.out with entry_condition {
        seq {
          read_input;
          round_and_clamp_q12;
          latch_lookup_coordinates;
          read_lower_lut;
          latch_lower_lut;
          read_upper_lut;
          multiply_interpolation;
          write_result;
          increment_entry_counter;
        }
      }
    }
  }
}
'''


def generate_gelu_kernel(fixture_path: Path) -> CalyxArtifact:
    """Authenticate the MLP fixture and generate the GELU-only Calyx main."""
    fixture = _checked_gelu_fixture(fixture_path)
    futil = _gelu_kernel_futil()
    return CalyxArtifact(
        futil=futil,
        provenance={
            "generated": "fixed-point-mlp-crossing-gelu-sv-v1",
            "fixture_receipt_sha256": fixture["receipt_sha256"],
            "authority": _fixture_authority(fixture),
            "futil_sha256": hashlib.sha256(futil.encode("utf-8")).hexdigest(),
            "host_preload_memories": ["gelu_input_q16_16", "gelu_lut_q12"],
            "calyx_disabled_passes": ["cell-share"],
            "memory_shapes": {
                "gelu_input_q16_16": [1024, 64],
                "gelu_lut_q12": [8192, 64],
                "gelu_q16_16": [1024, 64],
            },
            "kernel": {
                "entries": 1024,
                "round": "signed_magnitude_half_up_shift_4",
                "clamp": [-32768, 32767],
                "lookup": "8192_entry_q12_linear_interpolation_3_fraction_bits",
                "result": "signed_q12_left_shift_4_to_q16_16",
            },
        },
    )


def _cpp_values(values: list[int]) -> str:
    return ", ".join(str(int(value)) for value in values)


def _generated_gelu_harness(fixture: dict[str, Any]) -> str:
    """Preload only authenticated GELU source input and LUT memories."""
    gelu_input = [
        value
        for row in fixture["tensors"]["gelu_input_q16_16"]["values"]
        for value in row
    ]
    gelu_lut = fixture["tensors"]["gelu_lut_q12"]["values"]
    return f'''// Generated harness: preload only authenticated GELU input and LUT.
#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>

static const std::int64_t kGeluInput[1024] = {{{_cpp_values(gelu_input)}}};
static const std::int64_t kGeluLut[8192] = {{{_cpp_values(gelu_lut)}}};

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
  for (unsigned i = 0; i < 1024; ++i) {{
    root->main__DOT__gelu_input_q16_16__DOT__mem[i] =
        static_cast<std::uint64_t>(kGeluInput[i]);
    root->main__DOT__gelu_q16_16__DOT__mem[i] = 0;
  }}
  for (unsigned i = 0; i < 8192; ++i)
    root->main__DOT__gelu_lut_q12__DOT__mem[i] =
        static_cast<std::uint64_t>(kGeluLut[i]);
  model.reset = 1;
  model.go = 0;
  for (unsigned i = 0; i < 3; ++i) tick(model);
  model.reset = 0;
  model.go = 1;
  unsigned cycles = 0;
  while (!model.done && cycles < 100000) {{
    tick(model);
    ++cycles;
  }}
  const bool complete = model.done && cycles > 1024;
  std::cout << "{{\\\"status\\\":\\\"" << (complete ? "ok" : "mismatch")
            << "\\\",\\\"gelu_q16_16\\\":[";
  for (unsigned i = 0; i < 1024; ++i) {{
    if (i) std::cout << ',';
    std::cout << static_cast<std::int64_t>(
        root->main__DOT__gelu_q16_16__DOT__mem[i]);
  }}
  std::cout << "],\\\"cycles\\\":" << cycles << "}}\\n";
  return complete ? 0 : 1;
}}
'''


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
        raise RuntimeError(
            f"unable to build pinned Calyx tool: {completed.stderr.strip()}"
        )
    paths = [Path(line) for line in completed.stdout.splitlines() if line]
    if len(paths) != 1 or not (paths[0] / "bin/calyx").is_file():
        raise RuntimeError("pinned Calyx package did not yield one executable installation")
    return paths[0]


def _little_endian_i64_sha256(values: list[int]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(int(value).to_bytes(8, byteorder="little", signed=True))
    return digest.hexdigest()


def run_gelu_sv(
    artifact: CalyxArtifact, fixture_path: Path
) -> dict[str, object]:
    """Re-authenticate, compile, and observe every GELU hardware result word."""
    if artifact.provenance.get("generated") != "fixed-point-mlp-crossing-gelu-sv-v1":
        raise ValueError("unrecognized generated-SV GELU artifact provenance")
    fixture = _checked_gelu_fixture(fixture_path)
    if (
        artifact.provenance.get("fixture_receipt_sha256")
        != fixture["receipt_sha256"]
        or artifact.provenance.get("authority") != _fixture_authority(fixture)
    ):
        raise ValueError("generated-SV GELU fixture authority mismatch")
    if artifact.provenance.get("futil_sha256") != hashlib.sha256(
        artifact.futil.encode("utf-8")
    ).hexdigest():
        raise ValueError("generated-SV GELU Futil authority mismatch")

    artifact_dir = Path(tempfile.mkdtemp(prefix="fixed-point-mlp-gelu-sv-"))
    futil_path = artifact_dir / "gelu.futil"
    sv_path = artifact_dir / "main.sv"
    harness_path = artifact_dir / "harness.cpp"
    futil_path.write_text(artifact.futil, encoding="utf-8")
    harness_path.write_text(_generated_gelu_harness(fixture), encoding="utf-8")

    calyx = _calyx_install()
    calyx_command = [
        str(calyx / "bin/calyx"),
        str(futil_path),
        "-l",
        str(calyx / "share/calyx"),
        "-d",
        "cell-share",
        "-b",
        "verilog",
        "-o",
        str(sv_path),
    ]
    calyx_run = subprocess.run(
        calyx_command,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if calyx_run.returncode != 0 or not sv_path.is_file():
        raise RuntimeError(f"Calyx-to-SV failed: {calyx_run.stderr.strip()}")

    verilator_dir = artifact_dir / "verilator"
    verilator_run = subprocess.run(
        [
            "verilator",
            "--cc",
            "--exe",
            "--build",
            "--top-module",
            "main",
            "--public-flat-rw",
            "--Mdir",
            str(verilator_dir),
            "-CFLAGS",
            "-std=c++17",
            "-o",
            "fixed_point_mlp_gelu_harness",
            str(sv_path),
            str(harness_path),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    executable = verilator_dir / "fixed_point_mlp_gelu_harness"
    if verilator_run.returncode != 0 or not executable.is_file():
        raise RuntimeError(f"Verilator build failed: {verilator_run.stderr.strip()}")

    simulated = subprocess.run(
        [str(executable)],
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if simulated.returncode != 0:
        raise RuntimeError(
            "generated-SV GELU harness failed: "
            f"{simulated.stdout.strip()} {simulated.stderr.strip()}"
        )
    try:
        observed = json.loads(
            next(
                line
                for line in reversed(simulated.stdout.splitlines())
                if line.startswith("{")
            )
        )
    except (json.JSONDecodeError, StopIteration) as error:
        raise RuntimeError(
            f"generated-SV GELU harness did not emit JSON: {simulated.stdout!r}"
        ) from error
    values = observed.get("gelu_q16_16")
    if (
        observed.get("status") != "ok"
        or not isinstance(values, list)
        or len(values) != 1024
        or not all(isinstance(value, int) for value in values)
        or not isinstance(observed.get("cycles"), int)
    ):
        raise RuntimeError(f"generated-SV GELU observation is invalid: {observed}")

    artifact.provenance["generated_sv_artifacts"] = {
        "directory": str(artifact_dir),
        "futil": str(futil_path),
        "sv": str(sv_path),
        "harness": str(harness_path),
        "executable": str(executable),
    }
    artifact.provenance["calyx_command"] = calyx_command
    return {
        "gelu_q16_16": values,
        "little_endian_int64_sha256": _little_endian_i64_sha256(values),
        "cycles": observed["cycles"],
    }
