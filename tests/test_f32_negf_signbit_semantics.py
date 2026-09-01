#!/usr/bin/env python3
"""Regression tests for exact scalar-f32 NegF sign-bit legalization."""

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
FIXTURE = ROOT / "reproducers/calyx-math-negf/f32-signbit.mlir"
ORACLE_PATH = ROOT / "scripts/pipeline/verify_f32_negf_signbit_semantics.py"
PASS_PIPELINE = "builtin.module(llm2fpga-lower-negf-for-calyx)"
MAIN_ONLY_PASS_PIPELINE = (
    "builtin.module(llm2fpga-lower-negf-for-calyx,symbol-dce)"
)


def load_oracle():
    spec = importlib.util.spec_from_file_location("f32_negf_oracle", ORACLE_PATH)
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


class F32NegFSignBitSemanticsTest(unittest.TestCase):
    def test_independent_oracle_toggles_only_the_sign_bit_for_contract_patterns(self) -> None:
        # This catches a mask with any exponent or mantissa bit set, including
        # payload-destroying NaN or signed-zero implementations.
        for label, bits in ORACLE.contract_patterns():
            with self.subTest(label=label):
                self.assertEqual(ORACLE.expected_negf_bits(bits), bits ^ 0x80000000)

    def test_independent_oracle_rejects_non_binary32_patterns(self) -> None:
        for bits in (-1, 0x1_0000_0000):
            with self.subTest(bits=bits):
                with self.assertRaises(ValueError):
                    ORACLE.expected_negf_bits(bits)

    def test_oracle_cli_reports_deterministic_special_and_random_patterns(self) -> None:
        completed = subprocess.run(
            [shutil.which("python") or "python3", str(ORACLE_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = {entry["label"]: entry for entry in json.loads(completed.stdout)}
        self.assertEqual(report["positive-zero"]["expected"], "0x80000000")
        self.assertEqual(report["negative-snan-payload"]["expected"], "0x7F812345")
        self.assertEqual(len([label for label in report if label.startswith("random-")]), 128)

    def test_plugin_rewrites_only_scalar_f32_negf_to_bitcasts_and_xor(self) -> None:
        # This catches a missing registration, a floating arithmetic lowering,
        # a wrong mask, and accidental f64/vector matching.
        lowered = lowered_fixture()
        main = function_body(lowered, "main")
        self.assertNotIn("arith.negf", main)
        self.assertEqual(main.count("arith.bitcast"), 2)
        self.assertEqual(main.count("arith.xori"), 1)
        self.assertIn("-2147483648 : i32", main)
        self.assertNotIn("arith.addf", main)
        self.assertNotIn("arith.subf", main)

        self.assertIn("arith.negf", function_body(lowered, "scalar_f64"))
        self.assertIn("arith.negf", function_body(lowered, "vector_f32"))

    def test_memory_backed_scalar_f32_path_lowers_to_integer_calyx_xor(self) -> None:
        # This catches accidentally retaining float negation or introducing a
        # floating add/sub datapath in the bounded Calyx probe.
        circt_opt = os.environ.get("CIRCT_OPT") or shutil.which("circt-opt")
        if not circt_opt:
            self.skipTest("circt-opt is unavailable")
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as temp:
            lowered_path = Path(temp) / "lowered.mlir"
            calyx_path = Path(temp) / "model.calyx.mlir"
            lowered_path.write_text(
                lowered_fixture(MAIN_ONLY_PASS_PIPELINE), encoding="utf-8"
            )
            subprocess.run(
                [
                    circt_opt,
                    str(lowered_path),
                    "--lower-scf-to-calyx=top-level-function=main",
                    "-o",
                    str(calyx_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            calyx = calyx_path.read_text(encoding="utf-8")
        self.assertTrue(calyx.strip())
        self.assertIn("calyx.std_xor", calyx)
        self.assertNotIn("arith.negf", calyx)
        self.assertNotIn("calyx.ieee754.add", calyx)
        self.assertNotIn("calyx.ieee754.sub", calyx)


if __name__ == "__main__":
    unittest.main()
