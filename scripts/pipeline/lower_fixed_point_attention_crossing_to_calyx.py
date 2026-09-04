#!/usr/bin/env python3
"""Generate and run the exact fixed-point attention-crossing Calyx gates."""
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
FIXTURE_SCHEMA = "tinystories-1m-fixed-point-attention-crossing-slice-v1"
LN1_ARTIFACT_SCHEMA = "tinystories-1m-fixed-point-attention-ln1-generated-sv-v1"
LN1_SOURCE_MEMORIES = (
    "block_input_q16_16",
    "ln1_gamma_q16_16",
    "ln1_beta_q16_16",
)
LN1_HARDWARE_OWNED_MEMORIES = ("ln1_q16_16",)


@dataclass(frozen=True)
class CalyxArtifact:
    futil: str
    provenance: dict[str, Any]


def _capture_module():
    path = ROOT / "TinyStories/capture_fixed_point_attention_crossing_slice.py"
    spec = importlib.util.spec_from_file_location(
        "fixed_point_attention_crossing_capture_for_calyx", path
    )
    if spec is None or spec.loader is None:
        raise ValueError("authenticated attention fixture verifier unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_authority(fixture: dict[str, Any]) -> dict[str, Any]:
    """Bind generated artifacts to the complete authenticated fixture."""
    return {
        "schema": fixture["schema"],
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


def _checked_ln1_fixture(fixture_path: Path) -> dict[str, Any]:
    """Authenticate the fixture and the exact LayerNorm source-memory ABI."""
    fixture = _capture_module().verify_fixture(fixture_path)
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise ValueError("ln1 fixture schema authority mismatch")
    expected_arithmetic = (
        "truncating_mean_variance_plus_42950_restoring_isqrt_"
        "truncating_division_q16.16_affine"
    )
    if fixture.get("arithmetic", {}).get("layer_norm") != expected_arithmetic:
        raise ValueError("ln1 fixture arithmetic authority mismatch")
    expected = {
        "block_input_q16_16": ([4, 64], 2048),
        "ln1_gamma_q16_16": ([64], 512),
        "ln1_beta_q16_16": ([64], 512),
        "ln1_output_q16_16": ([4, 64], 2048),
    }
    for name, (shape, byte_count) in expected.items():
        record = fixture["tensors"].get(name)
        if (
            not isinstance(record, dict)
            or record.get("shape") != shape
            or record.get("dtype") != "int64"
            or record.get("bytes") != byte_count
        ):
            raise ValueError(f"ln1 fixture memory contract mismatch: {name}")
    return fixture


def _ln1_kernel_futil() -> str:
    """Emit four-row exact fixed LayerNorm with explicit staged state."""
    return '''// Generated exact block-0 ln_1 gate from authenticated fixture authority.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";

component main(@go go: 1) -> (@done done: 1) {
  cells {
    @external block_input_q16_16 = seq_mem_d1(64, 256, 8);
    @external ln1_gamma_q16_16 = seq_mem_d1(64, 64, 6);
    @external ln1_beta_q16_16 = seq_mem_d1(64, 64, 6);
    @external ln1_q16_16 = seq_mem_d1(64, 256, 8);

    row_counter = std_reg(3);
    row_lt = std_lt(3);
    increment_row = std_add(3);
    row_pad = std_pad(3, 8);
    row_shift = std_lsh(8);

    column_counter = std_reg(7);
    column_lt = std_lt(7);
    increment_column = std_add(7);
    column_address = std_slice(7, 6);
    column_pad = std_pad(6, 8);
    flat_address = std_add(8);

    row_sum = std_reg(64);
    sum_add = std_sadd(64);
    sum_negative = std_slt(64);
    sum_negate = std_ssub(64);
    sum_absolute = std_mux(64);
    mean_shift = std_rsh(64);
    mean_negate = std_ssub(64);
    mean_select = std_mux(64);
    mean = std_reg(64);

    delta_subtract = std_ssub(64);
    delta_square = std_smult_pipe(64);
    square_sum = std_reg(64);
    square_add = std_add(64);
    variance_shift = std_rsh(64);
    variance_epsilon = std_add(64);
    variance = std_reg(64);

    sqrt_remainder = std_reg(64);
    sqrt_root = std_reg(64);
    sqrt_bit = std_reg(64);
    sqrt_counter = std_reg(6);
    sqrt_lt = std_lt(6);
    sqrt_increment = std_add(6);
    sqrt_candidate = std_add(64);
    sqrt_take = std_ge(64);
    sqrt_subtract = std_sub(64);
    sqrt_root_shift = std_rsh(64);
    sqrt_root_add_bit = std_add(64);
    sqrt_remainder_select = std_mux(64);
    sqrt_root_select = std_mux(64);
    sqrt_bit_shift = std_rsh(64);

    numerator_shift = std_lsh(64);
    numerator_negative = std_slt(64);
    numerator = std_reg(64);
    numerator_negative_latch = std_reg(1);
    numerator_negate = std_ssub(64);
    numerator_absolute = std_mux(64);
    normalize_divide = std_div_pipe(64);
    quotient_negate = std_ssub(64);
    normalized_select = std_mux(64);
    affine_multiply = std_smult_pipe(64);
    affine_shift = std_srsh(64);
    affine_add = std_sadd(64);
  }
  wires {
    row_pad.in = row_counter.out;
    row_shift.left = row_pad.out;
    row_shift.right = 8'd6;
    column_address.in = column_counter.out;
    column_pad.in = column_address.out;
    flat_address.left = row_shift.out;
    flat_address.right = column_pad.out;

    group init_row {
      row_counter.in = 3'd0;
      row_counter.write_en = 1'd1;
      init_row[done] = row_counter.done;
    }
    group init_column {
      column_counter.in = 7'd0;
      column_counter.write_en = 1'd1;
      init_column[done] = column_counter.done;
    }
    group increment_column_counter {
      increment_column.left = column_counter.out;
      increment_column.right = 7'd1;
      column_counter.in = increment_column.out;
      column_counter.write_en = 1'd1;
      increment_column_counter[done] = column_counter.done;
    }
    group increment_row_counter {
      increment_row.left = row_counter.out;
      increment_row.right = 3'd1;
      row_counter.in = increment_row.out;
      row_counter.write_en = 1'd1;
      increment_row_counter[done] = row_counter.done;
    }
    comb group row_condition {
      row_lt.left = row_counter.out;
      row_lt.right = 3'd4;
    }
    comb group column_condition {
      column_lt.left = column_counter.out;
      column_lt.right = 7'd64;
    }

    group clear_row_sum {
      row_sum.in = 64'd0;
      row_sum.write_en = 1'd1;
      clear_row_sum[done] = row_sum.done;
    }
    group read_block_input {
      block_input_q16_16.addr0 = flat_address.out;
      block_input_q16_16.content_en = 1'd1;
      read_block_input[done] = block_input_q16_16.done;
    }
    group accumulate_row_sum {
      sum_add.left = row_sum.out;
      sum_add.right = block_input_q16_16.read_data;
      row_sum.in = sum_add.out;
      row_sum.write_en = 1'd1;
      accumulate_row_sum[done] = row_sum.done;
    }
    group latch_mean {
      sum_negative.left = row_sum.out;
      sum_negative.right = 64'd0;
      sum_negate.left = 64'd0;
      sum_negate.right = row_sum.out;
      sum_absolute.cond = sum_negative.out;
      sum_absolute.tru = sum_negate.out;
      sum_absolute.fal = row_sum.out;
      mean_shift.left = sum_absolute.out;
      mean_shift.right = 64'd6;
      mean_negate.left = 64'd0;
      mean_negate.right = mean_shift.out;
      mean_select.cond = sum_negative.out;
      mean_select.tru = mean_negate.out;
      mean_select.fal = mean_shift.out;
      mean.in = mean_select.out;
      mean.write_en = 1'd1;
      latch_mean[done] = mean.done;
    }

    group clear_square_sum {
      square_sum.in = 64'd0;
      square_sum.write_en = 1'd1;
      clear_square_sum[done] = square_sum.done;
    }
    group multiply_delta_square {
      delta_subtract.left = block_input_q16_16.read_data;
      delta_subtract.right = mean.out;
      delta_square.left = delta_subtract.out;
      delta_square.right = delta_subtract.out;
      delta_square.go = 1'd1;
      multiply_delta_square[done] = delta_square.done;
    }
    group accumulate_delta_square {
      square_add.left = square_sum.out;
      square_add.right = delta_square.out;
      square_sum.in = square_add.out;
      square_sum.write_en = 1'd1;
      accumulate_delta_square[done] = square_sum.done;
    }
    group latch_variance {
      variance_shift.left = square_sum.out;
      variance_shift.right = 64'd6;
      variance_epsilon.left = variance_shift.out;
      variance_epsilon.right = 64'd42950;
      variance.in = variance_epsilon.out;
      variance.write_en = 1'd1;
      latch_variance[done] = variance.done;
    }

    group init_sqrt {
      sqrt_remainder.in = variance.out;
      sqrt_remainder.write_en = 1'd1;
      sqrt_root.in = 64'd0;
      sqrt_root.write_en = 1'd1;
      sqrt_bit.in = 64'd4611686018427387904;
      sqrt_bit.write_en = 1'd1;
      sqrt_counter.in = 6'd0;
      sqrt_counter.write_en = 1'd1;
      init_sqrt[done] = (sqrt_remainder.done & sqrt_root.done & sqrt_bit.done & sqrt_counter.done) ? 1'd1;
    }
    group sqrt_step {
      sqrt_candidate.left = sqrt_root.out;
      sqrt_candidate.right = sqrt_bit.out;
      sqrt_take.left = sqrt_remainder.out;
      sqrt_take.right = sqrt_candidate.out;
      sqrt_subtract.left = sqrt_remainder.out;
      sqrt_subtract.right = sqrt_candidate.out;
      sqrt_root_shift.left = sqrt_root.out;
      sqrt_root_shift.right = 64'd1;
      sqrt_root_add_bit.left = sqrt_root_shift.out;
      sqrt_root_add_bit.right = sqrt_bit.out;
      sqrt_remainder_select.cond = sqrt_take.out;
      sqrt_remainder_select.tru = sqrt_subtract.out;
      sqrt_remainder_select.fal = sqrt_remainder.out;
      sqrt_root_select.cond = sqrt_take.out;
      sqrt_root_select.tru = sqrt_root_add_bit.out;
      sqrt_root_select.fal = sqrt_root_shift.out;
      sqrt_bit_shift.left = sqrt_bit.out;
      sqrt_bit_shift.right = 64'd2;
      sqrt_remainder.in = sqrt_remainder_select.out;
      sqrt_remainder.write_en = 1'd1;
      sqrt_root.in = sqrt_root_select.out;
      sqrt_root.write_en = 1'd1;
      sqrt_bit.in = sqrt_bit_shift.out;
      sqrt_bit.write_en = 1'd1;
      sqrt_increment.left = sqrt_counter.out;
      sqrt_increment.right = 6'd1;
      sqrt_counter.in = sqrt_increment.out;
      sqrt_counter.write_en = 1'd1;
      sqrt_step[done] = (sqrt_remainder.done & sqrt_root.done & sqrt_bit.done & sqrt_counter.done) ? 1'd1;
    }
    comb group sqrt_condition {
      sqrt_lt.left = sqrt_counter.out;
      sqrt_lt.right = 6'd32;
    }

    group read_output_operands {
      block_input_q16_16.addr0 = flat_address.out;
      block_input_q16_16.content_en = 1'd1;
      ln1_gamma_q16_16.addr0 = column_address.out;
      ln1_gamma_q16_16.content_en = 1'd1;
      ln1_beta_q16_16.addr0 = column_address.out;
      ln1_beta_q16_16.content_en = 1'd1;
      read_output_operands[done] = (block_input_q16_16.done & ln1_gamma_q16_16.done & ln1_beta_q16_16.done) ? 1'd1;
    }
    group latch_normalize_numerator {
      delta_subtract.left = block_input_q16_16.read_data;
      delta_subtract.right = mean.out;
      numerator_shift.left = delta_subtract.out;
      numerator_shift.right = 64'd16;
      numerator_negative.left = numerator_shift.out;
      numerator_negative.right = 64'd0;
      numerator.in = numerator_shift.out;
      numerator.write_en = 1'd1;
      numerator_negative_latch.in = numerator_negative.out;
      numerator_negative_latch.write_en = 1'd1;
      latch_normalize_numerator[done] = (numerator.done & numerator_negative_latch.done) ? 1'd1;
    }
    group divide_normalized {
      numerator_negate.left = 64'd0;
      numerator_negate.right = numerator.out;
      numerator_absolute.cond = numerator_negative_latch.out;
      numerator_absolute.tru = numerator_negate.out;
      numerator_absolute.fal = numerator.out;
      normalize_divide.left = numerator_absolute.out;
      normalize_divide.right = sqrt_root.out;
      normalize_divide.go = 1'd1;
      divide_normalized[done] = normalize_divide.done;
    }
    group multiply_affine {
      quotient_negate.left = 64'd0;
      quotient_negate.right = normalize_divide.out_quotient;
      normalized_select.cond = numerator_negative_latch.out;
      normalized_select.tru = quotient_negate.out;
      normalized_select.fal = normalize_divide.out_quotient;
      affine_multiply.left = normalized_select.out;
      affine_multiply.right = ln1_gamma_q16_16.read_data;
      affine_multiply.go = 1'd1;
      multiply_affine[done] = affine_multiply.done;
    }
    group write_ln1 {
      affine_shift.left = affine_multiply.out;
      affine_shift.right = 64'd16;
      affine_add.left = affine_shift.out;
      affine_add.right = ln1_beta_q16_16.read_data;
      ln1_q16_16.addr0 = flat_address.out;
      ln1_q16_16.content_en = 1'd1;
      ln1_q16_16.write_data = affine_add.out;
      ln1_q16_16.write_en = 1'd1;
      write_ln1[done] = ln1_q16_16.done;
    }
  }
  control {
    seq {
      init_row;
      while row_lt.out with row_condition {
        seq {
          clear_row_sum;
          init_column;
          while column_lt.out with column_condition {
            seq { read_block_input; accumulate_row_sum; increment_column_counter; }
          }
          latch_mean;
          clear_square_sum;
          init_column;
          while column_lt.out with column_condition {
            seq { read_block_input; multiply_delta_square; accumulate_delta_square; increment_column_counter; }
          }
          latch_variance;
          init_sqrt;
          while sqrt_lt.out with sqrt_condition { sqrt_step; }
          init_column;
          while column_lt.out with column_condition {
            seq {
              read_output_operands;
              latch_normalize_numerator;
              divide_normalized;
              multiply_affine;
              write_ln1;
              increment_column_counter;
            }
          }
          increment_row_counter;
        }
      }
    }
  }
}
'''


def generate_ln1_kernel(fixture_path: Path) -> CalyxArtifact:
    """Authenticate the attention fixture and generate the ln_1 Calyx main."""
    fixture = _checked_ln1_fixture(fixture_path)
    futil = _ln1_kernel_futil()
    return CalyxArtifact(
        futil=futil,
        provenance={
            "generated": LN1_ARTIFACT_SCHEMA,
            "fixture_receipt_sha256": fixture["receipt_sha256"],
            "authority": _fixture_authority(fixture),
            "futil_sha256": hashlib.sha256(futil.encode("utf-8")).hexdigest(),
            "host_preload_memories": list(LN1_SOURCE_MEMORIES),
            "hardware_owned_memories": list(LN1_HARDWARE_OWNED_MEMORIES),
            "calyx_disabled_passes": ["cell-share"],
            "memory_shapes": {
                "block_input_q16_16": [256, 64],
                "ln1_gamma_q16_16": [64, 64],
                "ln1_beta_q16_16": [64, 64],
                "ln1_q16_16": [256, 64],
            },
            "kernel": {
                "rows": 4,
                "width": 64,
                "mean": "signed_truncating_divide_by_64",
                "variance": "ascending_delta_square_sum_divide_by_64_plus_42950",
                "sqrt": "32_step_unsigned_restoring_floor",
                "normalize": "signed_truncating_division_q16_16",
                "affine": "signed_64_product_arithmetic_shift_16_plus_beta",
            },
        },
    )


def _cpp_values(values: list[int]) -> str:
    return ", ".join(str(int(value)) for value in values)


def _generated_ln1_harness(fixture: dict[str, Any]) -> str:
    """Preload only the authenticated block input and ln_1 affine parameters."""
    block_input = [
        value
        for row in fixture["tensors"]["block_input_q16_16"]["values"]
        for value in row
    ]
    gamma = fixture["tensors"]["ln1_gamma_q16_16"]["values"]
    beta = fixture["tensors"]["ln1_beta_q16_16"]["values"]
    return f'''// Generated harness: preload only block input and ln_1 gamma/beta.
#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>

static const std::int64_t kBlockInput[256] = {{{_cpp_values(block_input)}}};
static const std::int64_t kLn1Gamma[64] = {{{_cpp_values(gamma)}}};
static const std::int64_t kLn1Beta[64] = {{{_cpp_values(beta)}}};

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
    root->main__DOT__block_input_q16_16__DOT__mem[i] =
        static_cast<std::uint64_t>(kBlockInput[i]);
    root->main__DOT__ln1_q16_16__DOT__mem[i] = 0;
  }}
  for (unsigned i = 0; i < 64; ++i) {{
    root->main__DOT__ln1_gamma_q16_16__DOT__mem[i] =
        static_cast<std::uint64_t>(kLn1Gamma[i]);
    root->main__DOT__ln1_beta_q16_16__DOT__mem[i] =
        static_cast<std::uint64_t>(kLn1Beta[i]);
  }}
  model.reset = 1;
  model.go = 0;
  for (unsigned i = 0; i < 3; ++i) tick(model);
  model.reset = 0;
  model.go = 1;
  unsigned cycles = 0;
  while (!model.done && cycles < 1000000) {{
    tick(model);
    ++cycles;
  }}
  const bool complete = model.done && cycles > 256;
  std::cout << "{{\\\"status\\\":\\\"" << (complete ? "ok" : "mismatch")
            << "\\\",\\\"ln1_q16_16\\\":[";
  for (unsigned i = 0; i < 256; ++i) {{
    if (i) std::cout << ',';
    std::cout << static_cast<std::int64_t>(
        root->main__DOT__ln1_q16_16__DOT__mem[i]);
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


def run_ln1_sv(
    artifact: CalyxArtifact, fixture_path: Path
) -> dict[str, object]:
    """Re-authenticate, compile, and observe all 256 hardware-owned ln_1 words."""
    if artifact.provenance.get("generated") != LN1_ARTIFACT_SCHEMA:
        raise ValueError("unrecognized generated-SV ln1 artifact provenance")
    fixture = _checked_ln1_fixture(fixture_path)
    if (
        artifact.provenance.get("fixture_receipt_sha256")
        != fixture["receipt_sha256"]
        or artifact.provenance.get("authority") != _fixture_authority(fixture)
    ):
        raise ValueError("generated-SV ln1 fixture authority mismatch")
    if artifact.provenance.get("futil_sha256") != hashlib.sha256(
        artifact.futil.encode("utf-8")
    ).hexdigest():
        raise ValueError("generated-SV ln1 Futil authority mismatch")

    artifact_dir = Path(tempfile.mkdtemp(prefix="fixed-point-attention-ln1-sv-"))
    futil_path = artifact_dir / "ln1.futil"
    sv_path = artifact_dir / "main.sv"
    harness_path = artifact_dir / "harness.cpp"
    futil_path.write_text(artifact.futil, encoding="utf-8")
    harness = _generated_ln1_harness(fixture)
    harness_path.write_text(harness, encoding="utf-8")

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
            "fixed_point_attention_ln1_harness",
            str(sv_path),
            str(harness_path),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    executable = verilator_dir / "fixed_point_attention_ln1_harness"
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
            "generated-SV ln1 harness failed: "
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
            f"generated-SV ln1 harness did not emit JSON: {simulated.stdout!r}"
        ) from error
    flat = observed.get("ln1_q16_16")
    if (
        observed.get("status") != "ok"
        or not isinstance(flat, list)
        or len(flat) != 256
        or not all(isinstance(value, int) for value in flat)
        or not isinstance(observed.get("cycles"), int)
    ):
        raise RuntimeError(f"generated-SV ln1 observation is invalid: {observed}")

    artifact.provenance["generated_sv_artifacts"] = {
        "directory": str(artifact_dir),
        "futil": str(futil_path),
        "sv": str(sv_path),
        "harness": str(harness_path),
        "executable": str(executable),
        "harness_sha256": hashlib.sha256(harness.encode("utf-8")).hexdigest(),
        "sv_sha256": hashlib.sha256(sv_path.read_bytes()).hexdigest(),
    }
    artifact.provenance["calyx_command"] = calyx_command
    rows = [flat[index : index + 64] for index in range(0, 256, 64)]
    return {
        "ln1_q16_16": rows,
        "little_endian_int64_sha256": _little_endian_i64_sha256(flat),
        "cycles": observed["cycles"],
    }
