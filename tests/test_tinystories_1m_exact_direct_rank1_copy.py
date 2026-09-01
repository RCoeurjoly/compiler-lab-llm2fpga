#!/usr/bin/env python3
"""Semantic and safety regressions for exact direct rank-one copies."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPRODUCERS = ROOT / "reproducers/tinystories-1m-exact-direct-rank1-copy"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
PASS_ONLY_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx)"
REVIEWED_PLUGIN = Path(
    "/nix/store/7nffqc9cn9da37py316ilmcarjpp9gbn-"
    "llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so"
)

SAME_BASE_CONTROL = """module {
  func.func @same_base(%value: i64) -> i64 {
    %buffer = memref.alloc() : memref<4xi64>
    %c0 = arith.constant 0 : index
    memref.store %value, %buffer[%c0] : memref<4xi64>
    memref.copy %buffer, %buffer : memref<4xi64> to memref<4xi64>
    %observed = memref.load %buffer[%c0] : memref<4xi64>
    return %observed : i64
  }
}
"""

DYNAMIC_ALLOC_CONTROL = """module {
  func.func @dynamic_alloc(%size: index, %value: i64) -> i64 {
    %source = memref.alloc(%size) : memref<?xi64>
    %target = memref.alloc(%size) : memref<?xi64>
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<?xi64>
    memref.copy %source, %target : memref<?xi64> to memref<?xi64>
    %observed = memref.load %target[%c0] : memref<?xi64>
    return %observed : i64
  }
}
"""

MISMATCHED_SIZE_CONTROL = """module {
  func.func @mismatched_size(%value: i64) -> i64 {
    %source = memref.alloc() : memref<1xi64>
    %target = memref.alloc() : memref<2xi64>
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<1xi64>
    memref.copy %source, %target : memref<1xi64> to memref<2xi64>
    %observed = memref.load %target[%c0] : memref<2xi64>
    return %observed : i64
  }
}
"""

MISMATCHED_ELEMENT_CONTROL = """module {
  func.func @mismatched_element() {
    %source = memref.alloc() : memref<4xi64>
    %target = memref.alloc() : memref<4xf64>
    memref.copy %source, %target : memref<4xi64> to memref<4xf64>
    return
  }
}
"""

RANK_ZERO_CONTROL = """module {
  func.func @rank_zero(%value: i64) -> i64 {
    %source = memref.alloc() : memref<i64>
    %target = memref.alloc() : memref<i64>
    memref.store %value, %source[] : memref<i64>
    memref.copy %source, %target : memref<i64> to memref<i64>
    %observed = memref.load %target[] : memref<i64>
    return %observed : i64
  }
}
"""

ZERO_EXTENT_CONTROL = """module {
  func.func @zero_extent() {
    %source = memref.alloc() : memref<0xi64>
    %target = memref.alloc() : memref<0xi64>
    memref.copy %source, %target : memref<0xi64> to memref<0xi64>
    return
  }
}
"""

NON_IDENTITY_LAYOUT_CONTROL = """module {
  func.func @non_identity_layout(%value: i64) -> i64 {
    %source = memref.alloc() : memref<4xi64, strided<[2]>>
    %target = memref.alloc() : memref<4xi64, strided<[2]>>
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<4xi64, strided<[2]>>
    memref.copy %source, %target
      : memref<4xi64, strided<[2]>> to memref<4xi64, strided<[2]>>
    %observed = memref.load %target[%c0] : memref<4xi64, strided<[2]>>
    return %observed : i64
  }
}
"""

ARGUMENT_BASE_CONTROL = """module {
  func.func @argument_bases(
      %source: memref<4xi64>, %target: memref<4xi64>, %value: i64) -> i64 {
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<4xi64>
    memref.copy %source, %target : memref<4xi64> to memref<4xi64>
    %observed = memref.load %target[%c0] : memref<4xi64>
    return %observed : i64
  }
}
"""

GLOBAL_BASE_CONTROL = """module {
  memref.global "private" @source : memref<4xi64> = dense<0>
  memref.global "private" @target : memref<4xi64> = dense<0>

  func.func @global_bases(%value: i64) -> i64 {
    %source = memref.get_global @source : memref<4xi64>
    %target = memref.get_global @target : memref<4xi64>
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<4xi64>
    memref.copy %source, %target : memref<4xi64> to memref<4xi64>
    %observed = memref.load %target[%c0] : memref<4xi64>
    return %observed : i64
  }
}
"""


@dataclass(frozen=True)
class AffineExpr:
    offset: int
    coefficient: int

    def add(self, other: "AffineExpr") -> "AffineExpr":
        return AffineExpr(
            self.offset + other.offset,
            self.coefficient + other.coefficient,
        )

    def scale(self, factor: int) -> "AffineExpr":
        return AffineExpr(self.offset * factor, self.coefficient * factor)

    def constant_value(self) -> int | None:
        if self.coefficient != 0:
            return None
        return self.offset


def resolve_plugin() -> Path:
    candidates = []
    if configured := os.environ.get("LLM2FPGA_MLIR_PASS_PLUGIN"):
        candidates.append(Path(configured))
    candidates.extend([ROOT / "result/lib/LLM2FPGAMLIRPasses.so", REVIEWED_PLUGIN])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "no pass plugin found; run `nix build .#llm2fpgaMlirPasses` or set "
        "LLM2FPGA_MLIR_PASS_PLUGIN"
    )


def resolve_mlir_opt() -> Path:
    configured = os.environ.get("MLIR_OPT")
    discovered = configured or shutil.which("mlir-opt")
    if not discovered:
        raise RuntimeError("mlir-opt is absent; run the test through `nix develop`")
    return Path(discovered).resolve()


def run_pass(
    input_path: Path, *, pipeline: str = PIPELINE
) -> tuple[subprocess.CompletedProcess[bytes], str]:
    mlir_opt = resolve_mlir_opt()
    plugin = resolve_plugin()
    with tempfile.TemporaryDirectory(prefix="exact-direct-rank1-copy-") as raw:
        output_path = Path(raw) / "output.mlir"
        completed = subprocess.run(
            [
                str(mlir_opt),
                str(input_path),
                f"--load-pass-plugin={plugin}",
                f"--pass-pipeline={pipeline}",
                "-mlir-print-op-generic",
                "-o",
                str(output_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if completed.returncode == 0:
            parsed = subprocess.run(
                [str(mlir_opt), str(output_path), "-o", "/dev/null"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if parsed.returncode != 0:
                raise AssertionError(
                    "post-pass output did not parse:\n"
                    + parsed.stderr.decode(errors="replace")
                )
        return completed, output


def run_text(
    source: str, *, pipeline: str = PIPELINE
) -> tuple[subprocess.CompletedProcess[bytes], str]:
    with tempfile.TemporaryDirectory(prefix="exact-direct-rank1-control-") as raw:
        input_path = Path(raw) / "input.mlir"
        input_path.write_text(source, encoding="utf-8")
        return run_pass(input_path, pipeline=pipeline)


def _single_loop_domain(generic_ir: str) -> tuple[str, dict[str, int]]:
    constants = {
        name: int(value)
        for name, value in re.findall(
            r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) '
            r'<\{value = (-?[0-9]+) : index\}>',
            generic_ir,
            re.MULTILINE,
        )
    }
    loops = re.findall(
        r'"scf\.for"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), '
        r'(%[A-Za-z0-9_]+)\) \(\{\s*\^bb[0-9]+\('
        r'(%[A-Za-z0-9_]+): index\)',
        generic_ir,
        re.DOTALL,
    )
    if len(loops) != 1:
        raise AssertionError(f"expected one copy loop, found {len(loops)}")
    lower, upper, step, induction = loops[0]
    if any(name not in constants for name in (lower, upper, step)):
        raise AssertionError("copy loop bounds are not literal index constants")
    return induction, {
        "lower": constants[lower],
        "upper_exclusive": constants[upper],
        "step": constants[step],
    }


def _rank_one_accesses(
    generic_ir: str, induction: str
) -> tuple[list[str], list[dict[str, object]]]:
    allocations = re.findall(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.alloc"\(',
        generic_ir,
        re.MULTILINE,
    )
    expressions: dict[str, AffineExpr] = {induction: AffineExpr(0, 1)}
    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) '
        r'<\{value = (-?[0-9]+) : index\}>'
    )
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.(addi|muli)"\('
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    load = re.compile(
        r'^\s*%[A-Za-z0-9_]+ = "memref\.load"\('
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    store = re.compile(
        r'^\s*"memref\.store"\(%[A-Za-z0-9_]+, '
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    accesses = []
    for line in generic_ir.splitlines():
        if match := constant.match(line):
            expressions[match.group(1)] = AffineExpr(int(match.group(2)), 0)
            continue
        if match := binary.match(line):
            result, operation, left_name, right_name = match.groups()
            if left_name not in expressions or right_name not in expressions:
                raise AssertionError(f"unresolved affine operands in `{line.strip()}`")
            left = expressions[left_name]
            right = expressions[right_name]
            if operation == "addi":
                expressions[result] = left.add(right)
            else:
                left_constant = left.constant_value()
                right_constant = right.constant_value()
                if left_constant is not None:
                    expressions[result] = right.scale(left_constant)
                elif right_constant is not None:
                    expressions[result] = left.scale(right_constant)
                else:
                    raise AssertionError(f"non-affine multiply in `{line.strip()}`")
            continue

        operation = "memref.load"
        match = load.match(line)
        if not match:
            operation = "memref.store"
            match = store.match(line)
        if not match:
            continue
        base, index = match.groups()
        if index not in expressions:
            raise AssertionError(f"unresolved access index in `{line.strip()}`")
        expression = expressions[index]
        accesses.append(
            {
                "operation": operation,
                "base": base,
                "offset": expression.offset,
                "coefficient": expression.coefficient,
            }
        )
    return allocations, accesses


class ExactDirectRankOneCopyTest(unittest.TestCase):
    maxDiff = None

    def assert_supported_copy(self, fixture: str, *, size: int, live_index: int) -> None:
        input_path = REPRODUCERS / fixture
        completed, output = run_pass(
            input_path,
            pipeline=PASS_ONLY_PIPELINE,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        self.assertNotIn("memref.copy", output)
        induction, domain = _single_loop_domain(output)
        self.assertEqual(
            domain,
            {"lower": 0, "upper_exclusive": size, "step": 1},
        )
        allocations, accesses = _rank_one_accesses(output, induction)
        self.assertEqual(len(allocations), 2)
        source, target = allocations
        self.assertCountEqual(
            accesses,
            [
                {
                    "operation": "memref.store",
                    "base": source,
                    "offset": live_index,
                    "coefficient": 0,
                },
                {
                    "operation": "memref.load",
                    "base": source,
                    "offset": 0,
                    "coefficient": 1,
                },
                {
                    "operation": "memref.store",
                    "base": target,
                    "offset": 0,
                    "coefficient": 1,
                },
                {
                    "operation": "memref.load",
                    "base": target,
                    "offset": live_index,
                    "coefficient": 0,
                },
            ],
        )
        integrated_completed, integrated_output = run_pass(input_path)
        self.assertEqual(
            integrated_completed.returncode,
            0,
            integrated_completed.stderr.decode(errors="replace"),
        )
        self.assertNotIn("memref.copy", integrated_output)

    def assert_copy_remains_explicit(self, source: str | Path) -> str:
        if isinstance(source, Path):
            completed, output = run_pass(source, pipeline=PASS_ONLY_PIPELINE)
        else:
            completed, output = run_text(source, pipeline=PASS_ONLY_PIPELINE)
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        self.assertIn("memref.copy", output)
        self.assertNotIn("scf.for", output)
        return output

    def assert_verifier_rejected(self, source: str, diagnostic: str) -> None:
        completed, output = run_text(source, pipeline=PASS_ONLY_PIPELINE)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(output, "")
        self.assertIn(diagnostic, completed.stderr.decode(errors="replace"))

    def test_size_one_lowers_with_exact_live_copy_direction(self) -> None:
        self.assert_supported_copy("size1.mlir", size=1, live_index=0)

    def test_size_sixty_four_lowers_with_exact_live_copy_direction(self) -> None:
        self.assert_supported_copy("size64.mlir", size=64, live_index=63)

    def test_same_base_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(SAME_BASE_CONTROL)

    def test_dynamic_alloc_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(DYNAMIC_ALLOC_CONTROL)

    def test_mismatched_size_copy_is_rejected_before_the_pass(self) -> None:
        self.assert_verifier_rejected(
            MISMATCHED_SIZE_CONTROL,
            "requires the same shape for all operands",
        )

    def test_mismatched_element_copy_is_rejected_before_the_pass(self) -> None:
        self.assert_verifier_rejected(
            MISMATCHED_ELEMENT_CONTROL,
            "requires the same element type for all operands",
        )

    def test_rank_zero_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(RANK_ZERO_CONTROL)

    def test_zero_extent_rank_one_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(ZERO_EXTENT_CONTROL)

    def test_non_identity_layout_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(NON_IDENTITY_LAYOUT_CONTROL)

    def test_function_argument_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(ARGUMENT_BASE_CONTROL)

    def test_global_copy_remains_explicit(self) -> None:
        self.assert_copy_remains_explicit(GLOBAL_BASE_CONTROL)

    def test_potential_alias_through_view_remains_explicit(self) -> None:
        output = self.assert_copy_remains_explicit(
            REPRODUCERS / "unsupported-alias.mlir"
        )
        self.assertIn("memref.cast", output)


if __name__ == "__main__":
    unittest.main()
