#!/usr/bin/env python3
"""Semantic regressions for exact static strided unit collapses."""

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
REPRODUCERS = ROOT / "reproducers/tinystories-1m-exact-strided-unit-collapse"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REVIEWED_PLUGIN = Path(
    "/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-"
    "llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so"
)

WRONG_RESULT_STRIDE_CONTROL = """module {
  func.func @wrong_result_stride(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[1]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[1]>>
    return %loaded : i64
  }
}
"""

WRONG_RESULT_OFFSET_CONTROL = """module {
  func.func @wrong_result_offset(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }
}
"""

DYNAMIC_CONTROL = """module {
  func.func @dynamic_offset(%source: memref<64x64xi64>, %offset: index, %i: index) -> i64 {
    %sub = memref.subview %source[%offset, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: ?>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: ?>> into memref<64xi64, strided<[64], offset: ?>>
    %loaded = memref.load %flat[%i]
      : memref<64xi64, strided<[64], offset: ?>>
    return %loaded : i64
  }
}
"""

OTHER_REASSOCIATION_CONTROL = """module {
  func.func @other_reassociation(%source: memref<4x64x64xi64>, %i: index, %j: index) -> i64 {
    %sub = memref.subview %source[0, 0, 0] [4, 64, 1] [1, 1, 1]
      : memref<4x64x64xi64> to memref<4x64x1xi64, strided<[4096, 64, 1]>>
    %flat = memref.collapse_shape %sub [[0], [1, 2]]
      : memref<4x64x1xi64, strided<[4096, 64, 1]>> into memref<4x64xi64, strided<[4096, 64]>>
    %loaded = memref.load %flat[%i, %j]
      : memref<4x64xi64, strided<[4096, 64]>>
    return %loaded : i64
  }
}
"""

ZERO_N_CONTROL = """module {
  func.func @zero_n(%source: memref<8x8xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [0, 1] [1, 1]
      : memref<8x8xi64> to memref<0x1xi64, strided<[8, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<0x1xi64, strided<[8, 1]>> into memref<0xi64, strided<[8]>>
    %loaded = memref.load %flat[%i] : memref<0xi64, strided<[8]>>
    return %loaded : i64
  }
}
"""

NONPOSITIVE_STRIDE_CONTROL = """module {
  func.func @nonpositive_stride(%source: memref<8x8xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [8, 8] [1, 1]
      : memref<8x8xi64> to memref<8x8xi64, strided<[8, 1]>>
    %strided = memref.reinterpret_cast %sub to
      offset: [0], sizes: [8, 1], strides: [0, 1]
      : memref<8x8xi64, strided<[8, 1]>> to memref<8x1xi64, strided<[0, 1]>>
    %flat = memref.collapse_shape %strided [[0, 1]]
      : memref<8x1xi64, strided<[0, 1]>> into memref<8xi64, strided<[0]>>
    %loaded = memref.load %flat[%i] : memref<8xi64, strided<[0]>>
    return %loaded : i64
  }
}
"""

MIXED_SIBLING_CONTROL = """module {
  func.func @mixed_sibling(%source: memref<64x64xi64>, %dynamic: index, %i: index) -> i64 {
    %supported_sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %supported_flat = memref.collapse_shape %supported_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %supported_value = memref.load %supported_flat[%i]
      : memref<64xi64, strided<[64]>>
    %unsupported_sub = memref.subview %source[%dynamic, 0] [1, 1] [1, 1]
      : memref<64x64xi64> to memref<1x1xi64, strided<[64, 1], offset: ?>>
    %unsupported_value = memref.load %unsupported_sub[%i, %i]
      : memref<1x1xi64, strided<[64, 1], offset: ?>>
    %sum = arith.addi %supported_value, %unsupported_value : i64
    return %sum : i64
  }
}
"""

COLLAPSED_COPY_CONTROL = """module {
  func.func @collapsed_copy(%source: memref<64x64xi64>, %target: memref<64x64xi64>) {
    %source_sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %source_flat = memref.collapse_shape %source_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64], offset: 7>>
    %target_sub = memref.subview %target[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %target_flat = memref.collapse_shape %target_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    memref.copy %source_flat, %target_flat
      : memref<64xi64, strided<[64], offset: 7>> to memref<64xi64, strided<[64]>>
    return
  }
}
"""

IDENTITY_COLLAPSE_CONTROL = """module {
  func.func @identity_collapse(%source: memref<8x8xi64>, %i: index) -> i64 {
    %flat = memref.collapse_shape %source [[0, 1]]
      : memref<8x8xi64> into memref<64xi64>
    %loaded = memref.load %flat[%i] : memref<64xi64>
    return %loaded : i64
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


def run_pass(input_path: Path) -> tuple[subprocess.CompletedProcess[bytes], str]:
    mlir_opt = resolve_mlir_opt()
    plugin = resolve_plugin()
    with tempfile.TemporaryDirectory(prefix="exact-strided-unit-collapse-") as raw:
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
    with tempfile.TemporaryDirectory(prefix="exact-strided-unit-control-") as raw:
        input_path = Path(raw) / "input.mlir"
        input_path.write_text(source, encoding="utf-8")
        return run_pass(input_path)


def _entry_arguments(generic_ir: str) -> list[str]:
    match = re.search(r"^\s*\^bb0\(([^)]*)\):", generic_ir, re.MULTILINE)
    if not match:
        raise AssertionError("generic post-pass IR has no entry block arguments")
    return re.findall(r"(%[A-Za-z0-9_]+)\s*:", match.group(1))


def _affine_accesses(
    generic_ir: str,
    *,
    variable_names: list[str],
    domains: list[dict[str, int | str]],
) -> list[dict[str, object]]:
    if len(variable_names) != len(domains):
        raise AssertionError("symbolic variables and domains differ in length")
    entry_arguments = _entry_arguments(generic_ir)
    variable_count = len(variable_names)
    expressions: dict[str, AffineExpr] = {
        variable_name: AffineExpr(
            0,
            tuple(
                1 if index == variable_index else 0
                for index in range(variable_count)
            ),
        )
        for variable_index, variable_name in enumerate(variable_names)
    }
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
            expressions[match.group(1)] = AffineExpr(
                int(match.group(2)), tuple(0 for _ in range(variable_count))
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
        if base not in entry_arguments:
            raise AssertionError(f"access base is not an entry argument in `{line.strip()}`")
        expression = expressions[index]
        accesses.append(
            {
                "operation": operation,
                "base_argument": entry_arguments.index(base),
                "base_role": role,
                "variables": [
                    {**domain, "ssa": variable_name}
                    for domain, variable_name in zip(domains, variable_names)
                ],
                "offset": expression.offset,
                "coefficients": list(expression.coefficients),
            }
        )
    return accesses


def _single_loop_domain(generic_ir: str) -> tuple[str, dict[str, int | str]]:
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
    if constants[step] != 1:
        raise AssertionError(f"copy loop step is {constants[step]}, not 1")
    return induction, {
        "name": "i",
        "lower": constants[lower],
        "upper_exclusive": constants[upper],
    }


class ExactStridedUnitCollapseTest(unittest.TestCase):
    maxDiff = None

    def assert_passes(self, source: str | Path) -> str:
        if isinstance(source, Path):
            completed, output = run_pass(source)
        else:
            completed, output = run_text(source)
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        return output

    def assert_supported_mapping(self, fixture: str, *, offset: int) -> None:
        output = self.assert_passes(REPRODUCERS / fixture)
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertIn("memref<4096xi64>", output)
        variable = _entry_arguments(output)[1]
        domain = {"name": "i", "lower": 0, "upper_exclusive": 64}
        expected = [
            {
                "operation": operation,
                "base_argument": 0,
                "base_role": role,
                "variables": [{**domain, "ssa": variable}],
                "offset": offset,
                "coefficients": [64],
            }
            for operation, role in (
                ("memref.store", "target"),
                ("memref.load", "source"),
            )
        ]
        self.assertCountEqual(
            _affine_accesses(
                output,
                variable_names=[variable],
                domains=[domain],
            ),
            expected,
        )

    def assert_explicit_or_verifier_rejected(
        self,
        source: str | Path,
        *,
        ranked_root: str,
        flattened_root: str,
        required_views: tuple[str, ...] = ("memref.subview", "memref.collapse_shape"),
    ) -> None:
        if isinstance(source, Path):
            completed, output = run_pass(source)
        else:
            completed, output = run_text(source)
        if completed.returncode != 0:
            self.assertIn("error:", completed.stderr.decode(errors="replace"))
            self.assertEqual(output, "")
            return
        for view in required_views:
            self.assertIn(view, output)
        self.assertIn(ranked_root, output)
        self.assertNotIn(flattened_root, output)

    def test_offset_zero_proves_64_i_over_the_complete_domain(self) -> None:
        self.assert_supported_mapping("offset-zero.mlir", offset=0)

    def test_offset_seven_proves_7_plus_64_i_over_the_complete_domain(self) -> None:
        self.assert_supported_mapping("offset-nonzero.mlir", offset=7)

    def test_collapsed_copy_lowers_both_roles_with_exact_maps(self) -> None:
        output = self.assert_passes(COLLAPSED_COPY_CONTROL)
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertNotIn("memref.copy", output)
        self.assertEqual(output.count("memref<4096xi64>"), 6)
        induction, domain = _single_loop_domain(output)
        self.assertCountEqual(
            _affine_accesses(
                output,
                variable_names=[induction],
                domains=[domain],
            ),
            [
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": [{**domain, "ssa": induction}],
                    "offset": 7,
                    "coefficients": [64],
                },
                {
                    "operation": "memref.store",
                    "base_argument": 1,
                    "base_role": "target",
                    "variables": [{**domain, "ssa": induction}],
                    "offset": 0,
                    "coefficients": [64],
                },
            ],
        )

    def test_identity_collapse_behavior_is_retained(self) -> None:
        output = self.assert_passes(IDENTITY_COLLAPSE_CONTROL)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertIn("memref<64xi64>", output)
        variable = _entry_arguments(output)[1]
        domain = {"name": "i", "lower": 0, "upper_exclusive": 64}
        self.assertEqual(
            _affine_accesses(
                output,
                variable_names=[variable],
                domains=[domain],
            ),
            [
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": [{**domain, "ssa": variable}],
                    "offset": 0,
                    "coefficients": [1],
                }
            ],
        )

    def test_nonunit_trailing_dimension_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            REPRODUCERS / "unsupported-nonunit.mlir",
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_wrong_result_stride_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            WRONG_RESULT_STRIDE_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_wrong_result_offset_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            WRONG_RESULT_OFFSET_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_dynamic_metadata_remains_explicit_with_ranked_root(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            DYNAMIC_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_other_reassociation_remains_explicit_with_ranked_root(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            OTHER_REASSOCIATION_CONTROL,
            ranked_root="memref<4x64x64xi64>",
            flattened_root="memref<16384xi64>",
        )

    def test_zero_leading_dimension_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            ZERO_N_CONTROL,
            ranked_root="memref<8x8xi64>",
            flattened_root="memref<64xi64>",
        )

    def test_nonpositive_leading_stride_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            NONPOSITIVE_STRIDE_CONTROL,
            ranked_root="memref<8x8xi64>",
            flattened_root="memref<64xi64>",
            required_views=(
                "memref.reinterpret_cast",
                "memref.collapse_shape",
            ),
        )

    def test_mixed_supported_and_unsupported_siblings_protect_root(self) -> None:
        output = self.assert_passes(MIXED_SIBLING_CONTROL)
        self.assertEqual(output.count('"memref.subview"'), 2)
        self.assertIn("memref.collapse_shape", output)
        self.assertIn("memref<64x64xi64>", output)
        self.assertNotIn("memref<4096xi64>", output)


if __name__ == "__main__":
    unittest.main()
