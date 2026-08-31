#!/usr/bin/env python3
"""Semantic regressions for the exact static memref.subview extension."""

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
REPRODUCERS = (
    ROOT / "reproducers/tinystories-1m-exact-static-subview-extension"
)
TASK3_EXACT = (
    ROOT
    / "reproducers/tinystories-1m-exact-flat-scf-memref"
    / "task3-earliest-remaining/input.mlir"
)
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
BASELINE_PLUGIN = Path(
    "/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-"
    "llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so"
)

DYNAMIC_CONTROL = """module {
  func.func @unsupported_dynamic(%source: memref<64x64xi64>, %offset: index, %i0: index, %i1: index) -> i64 {
    %view = memref.subview %source[%offset, 0] [16, 8] [2, 2]
      : memref<64x64xi64> to memref<16x8xi64, strided<[128, 2], offset: ?>>
    %loaded = memref.load %view[%i0, %i1]
      : memref<16x8xi64, strided<[128, 2], offset: ?>>
    return %loaded : i64
  }
}
"""

NON_STATIC_LAYOUT_CONTROL = """module {
  func.func @unsupported_non_static_layout(%source: memref<64x64xi64>, %i0: index, %i1: index) -> i64 {
    %view = memref.subview %source[1, 0] [16, 8] [2, 2]
      : memref<64x64xi64> to memref<16x8xi64, strided<[?, ?], offset: ?>>
    %loaded = memref.load %view[%i0, %i1]
      : memref<16x8xi64, strided<[?, ?], offset: ?>>
    return %loaded : i64
  }
}
"""

COPY_CONTROL = """module {
  func.func @static_subview_copy(%source: memref<64x64xi64>, %target: memref<64x64xi64>) {
    %source_view = memref.subview %source[1, 0] [16, 8] [2, 2]
      : memref<64x64xi64> to memref<16x8xi64, strided<[128, 2], offset: 64>>
    %target_view = memref.subview %target[0, 0] [16, 8] [1, 1]
      : memref<64x64xi64> to memref<16x8xi64, strided<[64, 1]>>
    memref.copy %source_view, %target_view
      : memref<16x8xi64, strided<[128, 2], offset: 64>> to memref<16x8xi64, strided<[64, 1]>>
    return
  }
}
"""


@dataclass(frozen=True)
class AffineExpr:
    offset: int
    coefficients: tuple[int, ...]

    def add(self, other: "AffineExpr") -> "AffineExpr":
        return AffineExpr(
            self.offset + other.offset,
            tuple(
                left + right
                for left, right in zip(self.coefficients, other.coefficients)
            ),
        )

    def scale(self, factor: int) -> "AffineExpr":
        return AffineExpr(
            self.offset * factor,
            tuple(coefficient * factor for coefficient in self.coefficients),
        )

    def constant_value(self) -> int | None:
        if any(self.coefficients):
            return None
        return self.offset


def resolve_plugin() -> Path:
    candidates = []
    if configured := os.environ.get("LLM2FPGA_MLIR_PASS_PLUGIN"):
        candidates.append(Path(configured))
    candidates.extend(
        [
            ROOT / "result/lib/LLM2FPGAMLIRPasses.so",
            BASELINE_PLUGIN,
        ]
    )
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


def run_pass(input_path: Path) -> tuple[subprocess.CompletedProcess[bytes], str]:
    mlir_opt = resolve_mlir_opt()
    plugin = resolve_plugin()
    with tempfile.TemporaryDirectory(prefix="exact-subview-extension-") as raw:
        output_path = Path(raw) / "output.mlir"
        completed = subprocess.run(
            [
                str(mlir_opt),
                str(input_path),
                f"--load-pass-plugin={plugin}",
                f"--pass-pipeline={PIPELINE}",
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


def run_text(source: str) -> tuple[subprocess.CompletedProcess[bytes], str]:
    with tempfile.TemporaryDirectory(prefix="exact-subview-control-") as raw:
        input_path = Path(raw) / "input.mlir"
        input_path.write_text(source, encoding="utf-8")
        return run_pass(input_path)


def _arguments(generic_ir: str) -> list[str]:
    match = re.search(r"^\s*\^bb0\(([^)]*)\):", generic_ir, re.MULTILINE)
    if not match:
        raise AssertionError("generic post-pass IR has no entry block arguments")
    return re.findall(r"(%[A-Za-z0-9_]+)\s*:", match.group(1))


def _affine_accesses(
    generic_ir: str, domains: list[dict[str, int | str]]
) -> list[dict[str, object]]:
    arguments = _arguments(generic_ir)
    if len(arguments) < 3:
        raise AssertionError(f"expected a base and two symbolic indices: {arguments}")
    variable_names = arguments[1:3]
    expressions: dict[str, AffineExpr] = {
        variable_names[0]: AffineExpr(0, (1, 0)),
        variable_names[1]: AffineExpr(0, (0, 1)),
    }
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.(addi|muli)"\('
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) '
        r'<\{value = (-?[0-9]+) : index\}>'
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
            expressions[match.group(1)] = AffineExpr(
                int(match.group(2)), (0, 0)
            )
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

        role = None
        operation = None
        match = load.match(line)
        if match:
            role = "source"
            operation = "memref.load"
        else:
            match = store.match(line)
            if match:
                role = "target"
                operation = "memref.store"
        if not match:
            continue
        base, index = match.groups()
        if index not in expressions:
            raise AssertionError(f"unresolved access index in `{line.strip()}`")
        expression = expressions[index]
        accesses.append(
            {
                "operation": operation,
                "base_argument": arguments.index(base),
                "base_role": role,
                "variables": [
                    {
                        **domain,
                        "ssa": variable_name,
                    }
                    for domain, variable_name in zip(domains, variable_names)
                ],
                "offset": expression.offset,
                "coefficients": list(expression.coefficients),
            }
        )
    return accesses


class ExactStaticSubviewExtensionTest(unittest.TestCase):
    maxDiff = None

    def assert_passes(self, input_path: Path) -> str:
        completed, output = run_pass(input_path)
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        return output

    def assert_supported_mapping(
        self,
        fixture: str,
        *,
        coefficients: list[int],
        offset: int,
        upper_bounds: list[int],
    ) -> None:
        output = self.assert_passes(REPRODUCERS / fixture)
        self.assertNotIn("memref.subview", output)
        self.assertIn("memref<4096xi64>", output)
        domains = [
            {
                "name": f"i{dimension}",
                "lower": 0,
                "upper_exclusive": upper,
            }
            for dimension, upper in enumerate(upper_bounds)
        ]
        variables = _arguments(output)[1:3]
        expected_accesses = [
            {
                "operation": operation,
                "base_argument": 0,
                "base_role": role,
                "variables": [
                    {**domain, "ssa": variable}
                    for domain, variable in zip(domains, variables)
                ],
                "offset": offset,
                "coefficients": coefficients,
            }
            for operation, role in (
                ("memref.store", "target"),
                ("memref.load", "source"),
            )
        ]
        self.assertCountEqual(_affine_accesses(output, domains), expected_accesses)

    def test_task3_exact_reproducer_no_longer_changes_subview_argument_rank(self) -> None:
        output = self.assert_passes(TASK3_EXACT)
        self.assertNotIn("memref.subview", output)
        self.assertIn("memref<4096xi64>", output)

    def test_identity_subview_proves_64_i0_plus_i1_for_the_complete_domain(self) -> None:
        self.assert_supported_mapping(
            "identity-offset.mlir",
            coefficients=[64, 1],
            offset=0,
            upper_bounds=[64, 1],
        )

    def test_nonzero_subview_proves_64_plus_128_i0_plus_2_i1(self) -> None:
        self.assert_supported_mapping(
            "nonzero-offset-stride.mlir",
            coefficients=[128, 2],
            offset=64,
            upper_bounds=[16, 8],
        )

    def test_static_subview_copy_rewrites_before_dead_view_cleanup(self) -> None:
        completed, output = run_text(COPY_CONTROL)
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.copy", output)
        self.assertEqual(output.count('"scf.for"'), 2)
        self.assertIn('"memref.load"', output)
        self.assertIn('"memref.store"', output)
        self.assertEqual(output.count("memref<4096xi64>"), 6)

    def assert_unsupported_remains_explicit(self, source: str | Path) -> None:
        if isinstance(source, Path):
            output = self.assert_passes(source)
        else:
            completed, output = run_text(source)
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode(errors="replace"),
            )
        self.assertIn("memref.subview", output)
        self.assertIn("memref<64x64xi64>", output)
        self.assertNotIn("memref<4096xi64>", output)

    def test_rank_reducing_subview_remains_explicit(self) -> None:
        self.assert_unsupported_remains_explicit(
            REPRODUCERS / "unsupported-rank-reducing.mlir"
        )

    def test_dynamic_subview_remains_explicit(self) -> None:
        self.assert_unsupported_remains_explicit(DYNAMIC_CONTROL)

    def test_inconsistent_result_layout_fails_closed_before_legalization(self) -> None:
        completed, output = run_text(NON_STATIC_LAYOUT_CONTROL)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "mismatch of result layout",
            completed.stderr.decode(errors="replace"),
        )
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
