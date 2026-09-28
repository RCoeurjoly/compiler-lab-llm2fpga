import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/diagnostics/prepare_legacy_clock_recovery.py"


class LegacyClockRecoveryTest(unittest.TestCase):
    def fixture(self, inverted="0", original_type="FDCE"):
        return {"modules": {"top": {"settings": {"seed": "15"}, "cells": {
            "ff": {"type": "SLICE_FFX", "parameters": {"IS_CLK_INVERTED": inverted},
                   "attributes": {"NEXTPNR_BEL": "SLICE_X36Y184/AFF", "X_ORIG_TYPE": original_type}}},
            "netnames": {"clk": {"attributes": {"ROUTING": "wire;pip;1"}}}}}}

    def run_fixture(self, design=None, feature="CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV"):
        design = design or self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, fasm, grid, output, receipt = [root / n for n in ("input.json", "input.fasm", "grid.json", "output.json", "receipt.json")]
            source.write_text(json.dumps(design))
            fasm.write_text(feature + "\n")
            grid.write_text(json.dumps({"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}}}))
            result = subprocess.run([sys.executable, str(SCRIPT), "--json", str(source), "--fasm", str(fasm),
                "--tilegrid", str(grid), "--output", str(output), "--receipt", str(receipt)],
                text=True, capture_output=True, timeout=10)
            return result, json.loads(output.read_text()) if output.exists() else None, json.loads(receipt.read_text()) if receipt.exists() else None

    def test_noninverted_clock_recovery_preserves_cells_and_routes(self):
        original = self.fixture()
        result, output, receipt = self.run_fixture(original)
        self.assertEqual(result.returncode, 0, result.stderr)
        module = output["modules"]["top"]
        self.assertEqual(module["cells"], original["modules"]["top"]["cells"])
        self.assertEqual(module["netnames"], original["modules"]["top"]["netnames"])
        self.assertEqual(module["settings"]["seed"], "15")
        self.assertEqual(module["settings"]["checkpoint/selector/SLICE_X36Y184/CLKINV"], "CLK")
        self.assertEqual(receipt["validated_sites"], 1)
        self.assertFalse(receipt["historical_pip_identity_proven"])

    def test_inverted_clock_selects_clk_b(self):
        result, output, _ = self.run_fixture(self.fixture("1"), "CLBLL_R_X25Y184.SLICEL_X0.CLKINV")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["modules"]["top"]["settings"]["checkpoint/selector/SLICE_X36Y184/CLKINV"], "CLK_B")

    def test_negative_edge_type_implies_inversion(self):
        result, _, _ = self.run_fixture(self.fixture("0", "FDCE_1"), "CLBLL_R_X25Y184.SLICEL_X0.CLKINV")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_conflicting_or_mismatching_fasm_is_rejected(self):
        for features in ("", "CLBLL_R_X25Y184.SLICEL_X0.CLKINV",
                         "CLBLL_R_X25Y184.SLICEL_X0.CLKINV\nCLBLL_R_X25Y184.SLICEL_X0.NOCLKINV",
                         "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV = 0"):
            with self.subTest(features=features):
                result, output, receipt = self.run_fixture(feature=features)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(output)
                self.assertIsNone(receipt)

    def test_nonboolean_parameter_and_unsupported_cell_are_rejected(self):
        for fixture in (self.fixture("10"), self.fixture("x"), self.fixture("0", "UNREVIEWED_FF")):
            result, output, _ = self.run_fixture(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(output)

    def test_conflicting_existing_selector_is_rejected(self):
        design = self.fixture()
        design["modules"]["top"]["settings"]["checkpoint/selector/SLICE_X36Y184/CLKINV"] = "CLK_B"
        result, output, _ = self.run_fixture(design)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)

    def test_conflicting_cells_in_same_site_are_rejected(self):
        design = self.fixture()
        second = self.fixture("1")["modules"]["top"]["cells"]["ff"]
        second["attributes"]["NEXTPNR_BEL"] = "SLICE_X36Y184/BFF"
        design["modules"]["top"]["cells"]["second"] = second
        result, output, _ = self.run_fixture(design)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)


if __name__ == "__main__":
    unittest.main()
