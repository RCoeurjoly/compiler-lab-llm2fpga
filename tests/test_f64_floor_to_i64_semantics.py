#!/usr/bin/env python3
"""Regression tests for the exact f64 floor-to-i64 Calyx legalization."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "reproducers/calyx-math-floor/f64-floor-to-i64.mlir"
ORACLE_PATH = ROOT / "scripts/pipeline/verify_f64_floor_to_i64_semantics.py"
PASS_PIPELINE = "builtin.module(llm2fpga-lower-exact-math-for-calyx)"


def load_oracle():
    spec = importlib.util.spec_from_file_location("f64_floor_oracle", ORACLE_PATH)
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


def lowered_fixture() -> str:
    mlir_opt = os.environ.get("MLIR_OPT") or shutil.which("mlir-opt")
    if not mlir_opt:
        raise unittest.SkipTest("mlir-opt is unavailable")
    plugin = reviewed_plugin()
    completed = subprocess.run(
        [
            mlir_opt,
            f"--load-pass-plugin={plugin}",
            f"--pass-pipeline={PASS_PIPELINE}",
            str(FIXTURE),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def function_body(module: str, name: str) -> str:
    marker = f"func.func @{name}"
    start = module.index(marker)
    next_function = module.find("  func.func @", start + len(marker))
    return module[start:] if next_function == -1 else module[start:next_function]


class F64FloorToI64SemanticsTest(unittest.TestCase):
    def test_host_oracle_matches_floor_on_the_original_defined_domain(self) -> None:
        # Removing the `< float(trunc)` correction is the production mutation
        # this test catches, especially for negative fractions.
        for label, value in ORACLE.contract_cases():
            if ORACLE.in_original_defined_domain(value):
                with self.subTest(label=label):
                    self.assertEqual(ORACLE.floor_to_i64(value), math.floor(value))

    def test_host_oracle_classifies_originally_undefined_inputs(self) -> None:
        outside = {
            label
            for label, value in ORACLE.contract_cases()
            if not ORACLE.in_original_defined_domain(value)
        }
        self.assertEqual(
            outside,
            {
                "i64-max-outside",
                "i64-min-next-down-outside",
                "nan",
                "positive-infinity",
                "negative-infinity",
            },
        )
        self.assertEqual(ORACLE.floor_to_i64(-0.0), 0)

    def test_oracle_cli_reports_defined_and_outside_cases(self) -> None:
        completed = subprocess.run(
            [shutil.which("python") or "python3", str(ORACLE_PATH)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = {entry["label"]: entry for entry in json.loads(completed.stdout)}
        self.assertEqual(report["negative-fraction"]["lowered"], -2)
        self.assertEqual(report["nan"]["classification"], "outside-original-defined-domain")

    def test_fixture_declares_the_positive_and_nonmatching_boundaries(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        for name in (
            "@main",
            "@standalone_f64_floor",
            "@two_use_f64_floor",
            "@f64_floor_to_i32",
            "@f32_floor_to_i32",
            "@f64_ceil_rsqrt",
        ):
            with self.subTest(name=name):
                self.assertIn(name, fixture)
        self.assertIn("memref<5xf64>", fixture)
        self.assertIn("arith.divf", fixture)
        self.assertIn("math.floor %positive_ratio : f64", fixture)
        self.assertIn("math.floor %value : f32", fixture)
        self.assertIn("math.ceil %ceil_input : f64", fixture)
        self.assertIn("math.rsqrt %rsqrt_input : f64", fixture)

    def test_plugin_rewrites_only_the_f64_floor_i64_pairs(self) -> None:
        # Keeping math.floor in @main is the production failure this test
        # catches: before the fused f64/i64 rewrite, the current plugin only
        # legalizes f32 math.floor operations.
        lowered = lowered_fixture()
        main = function_body(lowered, "main")
        self.assertNotIn("math.floor", main)
        self.assertEqual(main.count("arith.fptosi"), 5)
        self.assertEqual(main.count("arith.sitofp"), 5)
        self.assertEqual(main.count("arith.cmpf olt"), 5)
        self.assertEqual(main.count("arith.select"), 5)
        self.assertEqual(main.count("arith.addi"), 5)
        self.assertEqual(main.count("arith.divf"), 5)

        self.assertIn("math.floor", function_body(lowered, "standalone_f64_floor"))
        two_use = function_body(lowered, "two_use_f64_floor")
        self.assertIn("math.floor", two_use)
        self.assertEqual(two_use.count("arith.fptosi"), 2)
        self.assertIn("math.floor", function_body(lowered, "f64_floor_to_i32"))
        f32 = function_body(lowered, "f32_floor_to_i32")
        self.assertIn("arith.fptosi", f32)
        self.assertIn("math.ceil", function_body(lowered, "f64_ceil_rsqrt"))
        self.assertIn("math.rsqrt", function_body(lowered, "f64_ceil_rsqrt"))


if __name__ == "__main__":
    unittest.main()
