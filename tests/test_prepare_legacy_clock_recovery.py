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

    def run_fixture(self, design=None, feature="CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV", grid_data=None):
        design = design or self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, fasm, grid, output, receipt = [root / n for n in ("input.json", "input.fasm", "grid.json", "output.json", "receipt.json")]
            source.write_text(json.dumps(design))
            fasm.write_text(feature + "\n")
            grid.write_text(json.dumps(grid_data or {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}}}))
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

    def test_preexisting_selector_without_cell_and_fasm_evidence_is_rejected(self):
        design = self.fixture()
        design["modules"]["top"]["settings"][
            "checkpoint/selector/MMCME2_ADV_X0Y3/RSTINV"] = "RST_B"
        result, output, receipt = self.run_fixture(design)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)
        self.assertIsNone(receipt)

    def test_conflicting_cells_in_same_site_are_rejected(self):
        design = self.fixture()
        second = self.fixture("1")["modules"]["top"]["cells"]["ff"]
        second["attributes"]["NEXTPNR_BEL"] = "SLICE_X36Y184/BFF"
        design["modules"]["top"]["cells"]["second"] = second
        result, output, _ = self.run_fixture(design)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)

    def test_lutram_only_slice_recovers_its_write_clock_without_a_flipflop(self):
        design = self.fixture()
        design["modules"]["top"]["cells"]["memory"] = {
            "type": "SLICE_LUTX", "parameters": {"IS_WCLK_INVERTED": "0"},
            "attributes": {"NEXTPNR_BEL": "SLICE_X122Y330/A6LUT", "X_ORIG_TYPE": "RAMD64E"},
            "connections": {"CLK": [2]}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "CLBLM_R_X81Y330": {"sites": {"SLICE_X122Y330": "SLICEM"}}}
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\nCLBLM_R_X81Y330.SLICEM_X0.NOCLKINV"
        result, output, receipt = self.run_fixture(design, features, grid)
        self.assertEqual(result.returncode, 0, result.stderr)
        key = "checkpoint/selector/SLICE_X122Y330/CLKINV"
        self.assertIn(key, output["modules"]["top"]["settings"])
        self.assertEqual(output["modules"]["top"]["settings"][key], "CLK")
        self.assertEqual(receipt["validated_lutram_clock_cells"], 1)
        design["modules"]["top"]["cells"]["memory"]["parameters"]["IS_WCLK_INVERTED"] = "1"
        result, output, _ = self.run_fixture(design, features, grid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)

    def test_constant_rom_clock_uses_original_physical_polarity_not_packing_inversion(self):
        design = self.fixture()
        module = design["modules"]["top"]
        module["cells"]["rom"] = {
            "type": "SLICE_LUTX", "parameters": {"IS_WCLK_INVERTED": "1"},
            "attributes": {"NEXTPNR_BEL": "SLICE_X122Y181/A6LUT", "X_ORIG_TYPE": "RAMD64E"},
            "connections": {"CLK": [3]}}
        module["netnames"]["$PACKER_VCC_NET"] = {"bits": [3], "attributes": {}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "CLBLM_R_X81Y181": {"sites": {"SLICE_X122Y181": "SLICEM"}}}
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\nCLBLM_R_X81Y181.SLICEM_X0.NOCLKINV"
        result, output, receipt = self.run_fixture(design, features, grid)
        self.assertEqual(result.returncode, 0, result.stderr)
        key = "checkpoint/selector/SLICE_X122Y181/CLKINV"
        self.assertIn(key, output["modules"]["top"]["settings"])
        self.assertEqual(output["modules"]["top"]["settings"][key], "CLK")
        self.assertEqual(receipt["validated_constant_lutram_clock_sites"], 1)
        result, output, _ = self.run_fixture(design, features.replace("SLICEM_X0.NOCLKINV", "SLICEM_X0.CLKINV"), grid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)

    def bufg_fixture(self):
        design = self.fixture()
        design["modules"]["top"]["cells"]["global_clock"] = {
            "type": "BUFGCTRL", "parameters": {"IS_IGNORE1_INVERTED": "1",
                "IS_CE1_INVERTED": "1", "IS_S1_INVERTED": "1"},
            "attributes": {"NEXTPNR_BEL": "BUFGCTRL_X0Y14/BUFGCTRL"}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "CLK_BUFG_BOT_R_X155Y204": {"sites": {
                    f"BUFGCTRL_X0Y{y}": "BUFGCTRL" for y in range(16)}}}
        prefix = "CLK_BUFG_BOT_R_X155Y204.BUFGCTRL.BUFGCTRL_X0Y14."
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\n" + "\n".join(
            prefix + f for f in ("IN_USE", "IS_IGNORE1_INVERTED", "ZINV_CE0", "ZINV_S0"))
        return design, grid, features

    def test_real_bufg_configuration_selects_all_six_inputs(self):
        design, grid, features = self.bufg_fixture()
        result, output, receipt = self.run_fixture(design, features, grid)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = output["modules"]["top"]["settings"]
        for bel, selection in (("IGNORE0INV", "IGNORE0"), ("IGNORE1INV", "IGNORE1_B"),
                               ("CE0INV", "CE0"), ("CE1INV", "CE1_B"),
                               ("S0INV", "S0"), ("S1INV", "S1_B")):
            self.assertIn(f"checkpoint/selector/BUFGCTRL_X0Y14/{bel}", settings)
            self.assertEqual(settings[f"checkpoint/selector/BUFGCTRL_X0Y14/{bel}"], selection)
        self.assertEqual(receipt["validated_bufg_sites"], 1)
        self.assertEqual(output["modules"]["top"]["cells"], design["modules"]["top"]["cells"])

    def test_bufg_mismatching_or_missing_in_use_fasm_is_rejected(self):
        design, grid, features = self.bufg_fixture()
        for changed in (features.replace("IS_IGNORE1_INVERTED", "IS_IGNORE0_INVERTED"),
                        features.replace(".IN_USE", ".UNREVIEWED")):
            result, output, _ = self.run_fixture(design, changed, grid)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(output)

    def bram_fixture(self, size):
        design = self.fixture()
        site = "RAMB18_X2Y87" if size == 18 else "RAMB36_X2Y43"
        original = f"RAMB{size}E1"
        design["modules"]["top"]["cells"]["weight_rom"] = {
            "type": f"{original}_{original}",
            "parameters": {"IS_CLKBWRCLK_INVERTED": "1"},
            "attributes": {"NEXTPNR_BEL": f"{site}/{original}", "X_ORIG_TYPE": original}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "BRAM_L_X26Y215": {"sites": {site: "RAMB18E1" if size == 18 else "RAMBFIFO36E1"}}}
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\n"
        for half in ((1,) if size == 18 else (0, 1)):
            prefix = f"BRAM_L_X26Y215.RAMB18_Y{half}."
            features += "\n".join(prefix + pin for pin in (
                "IN_USE", "ZINV_CLKARDCLK", "ZINV_ENARDEN", "ZINV_ENBWREN",
                "ZINV_RSTRAMARSTRAM", "ZINV_RSTRAMB", "ZINV_RSTREGARSTREG", "ZINV_RSTREGB")) + "\n"
        return design, grid, features, site

    def test_bram18_and_bram36_polarity_is_validated_against_each_physical_half(self):
        for size in (18, 36):
            design, grid, features, site = self.bram_fixture(size)
            result, output, receipt = self.run_fixture(design, features, grid)
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = output["modules"]["top"]["settings"]
            for suffix in (("",) if size == 18 else ("L", "U")):
                self.assertIn(f"checkpoint/selector/{site}/CLKARDCLK{suffix}INV", settings)
                self.assertEqual(settings[f"checkpoint/selector/{site}/CLKARDCLK{suffix}INV"],
                                 f"CLKARDCLK{suffix}")
                self.assertEqual(settings[f"checkpoint/selector/{site}/CLKBWRCLK{suffix}INV"],
                                 f"CLKBWRCLK{suffix}_B")
            self.assertEqual(receipt["validated_bram_cells"], 1)
            self.assertEqual(output["modules"]["top"]["cells"], design["modules"]["top"]["cells"])
            self.assertEqual(output["modules"]["top"]["netnames"], design["modules"]["top"]["netnames"])

    def test_bram_missing_or_disagreeing_fasm_cannot_authorize_recovery(self):
        design, grid, features, _ = self.bram_fixture(36)
        for changed in (features.replace("BRAM_L_X26Y215.RAMB18_Y1.ZINV_CLKARDCLK\n", ""),
                        features.replace("BRAM_L_X26Y215.RAMB18_Y0.IN_USE\n", "")):
            result, output, _ = self.run_fixture(design, changed, grid)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(output)

    def dsp_fixture(self):
        design = self.fixture()
        design["modules"]["top"]["cells"]["mac"] = {
            "type": "DSP48E1_DSP48E1", "parameters": {
                "IS_INMODE_INVERTED": "00101", "IS_INMODE[1]_INVERTED": "1",
                "IS_OPMODE_INVERTED": "1000000", "IS_OPMODE[3]_INVERTED": "1",
                "IS_CARRYIN_INVERTED": "1"},
            "attributes": {"NEXTPNR_BEL": "DSP48_X5Y98/DSP48E1", "X_ORIG_TYPE": "DSP48E1"}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "DSP_L_X54Y245": {"sites": {"DSP48_X5Y98": "DSP48E1"}}}
        # Hand-derived complement: INMODE bits 0,1,2 and OPMODE bits 3,6
        # are inverted; vector bits and packed per-bit overrides are ORed.
        prefix = "DSP_L_X54Y245.DSP48.DSP_0."
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\n" + "\n".join(prefix + name for name in (
            "ZIS_CLK_INVERTED", "ZIS_INMODE_INVERTED[3]", "ZIS_INMODE_INVERTED[4]",
            "ZIS_OPMODE_INVERTED[0]", "ZIS_OPMODE_INVERTED[1]", "ZIS_OPMODE_INVERTED[2]",
            "ZIS_OPMODE_INVERTED[4]", "ZIS_OPMODE_INVERTED[5]",
            "ZIS_ALUMODE_INVERTED[0]", "ZIS_ALUMODE_INVERTED[1]",
            "ZIS_ALUMODE_INVERTED[2]", "ZIS_ALUMODE_INVERTED[3]"))
        return design, grid, features

    def test_dsp_vector_and_packed_bit_overrides_select_physical_inputs(self):
        design, grid, features = self.dsp_fixture()
        result, output, receipt = self.run_fixture(design, features, grid)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = output["modules"]["top"]["settings"]
        for pin, selection in (("INMODE0", "INMODE0_B"), ("INMODE1", "INMODE1_B"),
                               ("INMODE2", "INMODE2_B"), ("INMODE3", "INMODE3"),
                               ("OPMODE3", "OPMODE3_B"), ("OPMODE6", "OPMODE6_B"),
                               ("ALUMODE0", "ALUMODE0"), ("CLK", "CLK"), ("CARRYIN", "CARRYIN_B")):
            key = f"checkpoint/selector/DSP48_X5Y98/{pin}INV"
            self.assertIn(key, settings)
            self.assertEqual(settings[key], selection)
        self.assertEqual(receipt["validated_dsp_cells"], 1)
        self.assertEqual(output["modules"]["top"]["cells"], design["modules"]["top"]["cells"])

    def test_dsp_mismatch_and_out_of_range_inversion_masks_are_rejected(self):
        design, grid, features = self.dsp_fixture()
        result, output, _ = self.run_fixture(design, features.replace("ZIS_INMODE_INVERTED[3]", "ZIS_INMODE_INVERTED[0]"), grid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(output)
        for value in ("100000", "x", -1):
            design["modules"]["top"]["cells"]["mac"]["parameters"]["IS_INMODE_INVERTED"] = value
            result, output, _ = self.run_fixture(design, features, grid)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(output)

    def test_actual_mmcm_input_configuration_preserves_clock_parameters(self):
        design = self.fixture()
        design["modules"]["top"]["cells"]["clock_generator"] = {
            "type": "MMCME2_ADV_MMCME2_ADV", "parameters": {
                "IS_RST_INVERTED": "1", "IS_PWRDWN_INVERTED": "1",
                "IS_PSEN_INVERTED": "1", "IS_PSINCDEC_INVERTED": "1",
                "CLKFBOUT_MULT_F": "30.0", "CLKOUT0_DIVIDE_F": "25.0"},
            "attributes": {"NEXTPNR_BEL": "MMCME2_ADV_X0Y3/MMCME2_ADV", "X_ORIG_TYPE": "MMCME2_ADV"}}
        grid = {"CLBLL_R_X25Y184": {"sites": {"SLICE_X36Y184": "SLICEL"}},
                "CMT_TOP_R_LOWER_B_X8Y165": {"sites": {"MMCME2_ADV_X0Y3": "MMCME2_ADV"}}}
        prefix = "CMT_TOP_R_LOWER_B_X8Y165.MMCME2_ADV."
        features = "CLBLL_R_X25Y184.SLICEL_X0.NOCLKINV\n" + "\n".join(prefix + name for name in (
            "IN_USE", "ZINV_RST", "ZINV_PWRDWN", "ZINV_PSEN", "ZINV_PSINCDEC"))
        result, output, receipt = self.run_fixture(design, features, grid)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = output["modules"]["top"]["settings"]
        for pin, selection in (("CLKINSEL", "CLKINSEL"), ("RST", "RST_B"),
                               ("PWRDWN", "PWRDWN_B"), ("PSEN", "PSEN_B"), ("PSINCDEC", "PSINCDEC_B")):
            key = f"checkpoint/selector/MMCME2_ADV_X0Y3/{pin}INV"
            self.assertIn(key, settings)
            self.assertEqual(settings[key], selection)
        self.assertEqual(output["modules"]["top"]["cells"], design["modules"]["top"]["cells"])
        self.assertEqual(receipt["validated_mmcm_cells"], 1)
        for changed in (features.replace(".IN_USE", ".UNREVIEWED"), features + "\n" + prefix + "INV_CLKINSEL"):
            result, output, _ = self.run_fixture(design, changed, grid)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(output)


if __name__ == "__main__":
    unittest.main()
