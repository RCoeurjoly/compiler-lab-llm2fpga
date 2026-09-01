#!/usr/bin/env python3
"""Regression tests for exact scalar-i64 math.absi sign-mask legalization."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "reproducers/calyx-math-absi/i64-signmask.mlir"
ORACLE_PATH = ROOT / "scripts/pipeline/verify_i64_absi_signmask_semantics.py"
PASS_PIPELINE = "builtin.module(llm2fpga-lower-exact-math-for-calyx)"
MAIN_ONLY_PASS_PIPELINE = (
    "builtin.module(llm2fpga-lower-exact-math-for-calyx,symbol-dce)"
)


def load_oracle():
    spec = importlib.util.spec_from_file_location("i64_absi_oracle", ORACLE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ORACLE = load_oracle()


def reviewed_plugin() -> Path:
    configured = os.environ.get("LLM2FPGA_MLIR_PASS_PLUGIN")
    if configured:
        return Path(configured)
    completed = subprocess.run(
        ["nix", "build", "--no-link", "--print-out-paths", ".#llm2fpgaMlirPasses"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()) / "lib/LLM2FPGAMLIRPasses.so"


def lowered_fixture(pass_pipeline: str = PASS_PIPELINE) -> str:
    mlir_opt = os.environ.get("MLIR_OPT") or shutil.which("mlir-opt")
    if not mlir_opt:
        raise unittest.SkipTest("mlir-opt is unavailable")
    completed = subprocess.run(
        [
            mlir_opt,
            f"--load-pass-plugin={reviewed_plugin()}",
            f"--pass-pipeline={pass_pipeline}",
            str(FIXTURE),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def function_body(module: str, name: str) -> str:
    symbol = f"@{name}"
    symbol_start = module.index(symbol)
    start = module.rfind("  func.func", 0, symbol_start)
    assert start != -1
    next_function = module.find("\n  func.func", symbol_start + len(symbol))
    return module[start:] if next_function == -1 else module[start:next_function]


class I64AbsISignmaskSemanticsTest(unittest.TestCase):
    def test_independent_oracle_matches_signed_absolute_value_for_contract_patterns(self) -> None:
        # Removing the xor or replacing signed shift with logical shift makes
        # this equation fail on negative encodings.
        for label, bits in ORACLE.contract_patterns():
            with self.subTest(label=label):
                self.assertEqual(
                    ORACLE.lowered_absi_bits(bits), ORACLE.expected_absi_bits(bits)
                )

    def test_independent_oracle_rejects_non_i64_encodings(self) -> None:
        for bits in (-1, ORACLE.MASK + 1):
            with self.subTest(bits=bits):
                with self.assertRaises(ValueError):
                    ORACLE.lowered_absi_bits(bits)

    def test_oracle_cli_reports_deterministic_boundary_and_random_patterns(self) -> None:
        completed = subprocess.run(
            [shutil.which("python") or "python3", str(ORACLE_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = {entry["label"]: entry for entry in json.loads(completed.stdout)}
        self.assertEqual(report["i64-min"]["expected"], "0x8000000000000000")
        self.assertEqual(report["negative-one"]["lowered"], "0x0000000000000001")
        self.assertEqual(len([label for label in report if label.startswith("random-")]), 128)

    def test_plugin_rewrites_only_scalar_i64_absi_to_unflagged_signmask_arithmetic(self) -> None:
        # Before this legalization, @main retains math.absi. This catches a
        # missing registration, wrong shift, overflow flags, and wider match.
        lowered = lowered_fixture()
        main = function_body(lowered, "main")
        self.assertNotIn("math.absi", main)
        self.assertEqual(main.count("arith.shrsi"), 1)
        self.assertEqual(main.count("arith.xori"), 1)
        self.assertEqual(main.count("arith.subi"), 1)
        self.assertIn("63 : i64", main)
        self.assertNotIn("overflow<", main)
        self.assertNotIn("arith.cmpi", main)
        self.assertNotIn("arith.select", main)
        self.assertNotIn("cf.", main)
        self.assertNotIn("arith.addf", main)
        self.assertNotIn("arith.subf", main)

        self.assertIn("math.absi", function_body(lowered, "scalar_i32"))
        self.assertIn("math.absi", function_body(lowered, "vector_i64"))

    def test_memory_backed_scalar_i64_path_lowers_to_integer_calyx_primitives(self) -> None:
        # Before this legalization, CIRCT rejects the retained math.absi.
        circt_opt = os.environ.get("CIRCT_OPT") or shutil.which("circt-opt")
        if not circt_opt:
            self.skipTest("circt-opt is unavailable")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temp:
            lowered_path = Path(temp) / "lowered.mlir"
            calyx_path = Path(temp) / "model.calyx.mlir"
            lowered_path.write_text(
                lowered_fixture(MAIN_ONLY_PASS_PIPELINE), encoding="utf-8"
            )
            completed = subprocess.run(
                [
                    circt_opt,
                    str(lowered_path),
                    "--lower-scf-to-calyx=top-level-function=main",
                    "-o",
                    str(calyx_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            calyx = calyx_path.read_text(encoding="utf-8")
        self.assertTrue(calyx.strip())
        self.assertIn("calyx.std_srsh", calyx)
        self.assertIn("calyx.std_xor", calyx)
        self.assertIn("calyx.std_sub", calyx)
        self.assertNotIn("math.absi", calyx)
        self.assertNotIn("calyx.std_slt", calyx)
        self.assertNotIn("calyx.std_mux", calyx)


if __name__ == "__main__":
    unittest.main()
