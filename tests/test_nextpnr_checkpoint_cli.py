"""Public CLI tests; set both environment paths to the pinned Nix artifacts."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = os.environ.get("NEXTPNR_CHECKPOINT_TOOL")
CHIPDB = os.environ.get("NEXTPNR_CHECKPOINT_CHIPDB")


@unittest.skipUnless(TOOL and CHIPDB, "requires explicit pinned nextpnr and Kintex chipdb paths")
class NextpnrCheckpointCliTest(unittest.TestCase):
    def run_checkpoint(self, design, original_fasm=None):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            target = Path(directory) / "output.json"
            source.write_text(json.dumps(design))
            command = [TOOL, "--chipdb", CHIPDB, "--json", str(source),
                       "--no-pack", "--no-place", "--no-route", "--write", str(target)]
            if original_fasm is not None:
                fasm = Path(directory) / "original.fasm"
                fasm.write_text(original_fasm)
                command += ["--checkpoint-fasm", str(fasm)]
            result = subprocess.run(command,
                                    capture_output=True, text=True, timeout=30)
            output = json.loads(target.read_text()) if target.exists() else None
            return result, output

    def fixture(self, name="kintex-routed-clock-pipids.json"):
        return json.loads((ROOT / "tests/fixtures/nextpnr" / name).read_text())

    def pip_names(self, design):
        result = {}
        for name, net in design["modules"]["top"]["netnames"].items():
            fields = net["attributes"]["ROUTING"].split(";")
            result[name] = sorted(fields[i] for i in range(1, len(fields), 3) if fields[i])
        return result

    def postroute_lut_fixture(self):
        # Actual routed LUT2 $377777: physical A1 shares O6, but only
        # A3/I0 and A4/I1 participate in the FASM truth table.
        cell = {
            "type": "SLICE_LUTX", "parameters": {"INIT": "0100"},
            "attributes": {"NEXTPNR_BEL": "SLICE_X75Y280/A6LUT",
                "X_ORIG_TYPE": "LUT2", "X_ORIG_PORT_A3": "I0",
                "X_ORIG_PORT_A4": "I1", "X_ORIG_PORT_O6": "O"},
            "port_directions": {"A1": "input", "A3": "input", "A4": "input", "O6": "output"},
            "connections": {"A1": [4], "A3": [2], "A4": [3], "O6": [4]}}
        cells = {"actual_lut": cell}
        for name, bit in (("source0", 2), ("source1", 3)):
            cells[name] = {"type": "SLICE_LUTX", "parameters": {}, "attributes": {},
                "port_directions": {"O": "output"}, "connections": {"O": [bit]}}
        return {"modules": {"top": {"attributes": {"top": "1"}, "ports": {},
            "settings": {"route": "00000000000000000000000000000001"}, "cells": cells,
            "netnames": {"source0": {"bits": [2], "attributes": {}},
                         "source1": {"bits": [3], "attributes": {}},
                         "feedback": {"bits": [4], "attributes": {}}}}}}

    def test_postroute_unused_shared_lut_input_does_not_create_false_loop(self):
        design = self.postroute_lut_fixture()
        result, output = self.run_checkpoint(design)
        self.assertEqual(result.returncode, 0, result.stderr)
        cell = output["modules"]["top"]["cells"]["actual_lut"]
        self.assertEqual(cell["connections"]["A1"], cell["connections"]["O6"])
        self.assertEqual(cell["parameters"]["INIT"], "0100")

    def test_postroute_logical_feedback_is_still_rejected(self):
        design = self.postroute_lut_fixture()
        design["modules"]["top"]["cells"]["actual_lut"]["attributes"]["X_ORIG_PORT_A1"] = "I0"
        result, output = self.run_checkpoint(design)
        self.assertGreater(result.returncode, 0)
        self.assertIsNone(output)
        self.assertIn("timing analysis failed", result.stderr)

    def test_unrouted_lut_feedback_is_not_exempted(self):
        design = self.postroute_lut_fixture()
        design["modules"]["top"]["settings"] = {}
        result, output = self.run_checkpoint(design)
        self.assertGreater(result.returncode, 0)
        self.assertIsNone(output)
        self.assertIn("timing analysis failed", result.stderr)

    def test_physical_a6_feedback_is_not_exempted_by_missing_logical_mapping(self):
        # A6 can select between paired LUT5/LUT6 functions. Its physical
        # dependency must not disappear merely because its mapping is absent.
        design = self.postroute_lut_fixture()
        cell = design["modules"]["top"]["cells"]["actual_lut"]
        cell["connections"]["A6"] = cell["connections"].pop("A1")
        cell["port_directions"]["A6"] = cell["port_directions"].pop("A1")
        design["modules"]["top"]["cells"]["paired_lut5"] = {
            "type": "SLICE_LUTX", "parameters": {"INIT": "00"},
            "attributes": {"NEXTPNR_BEL": "SLICE_X75Y280/A5LUT", "X_ORIG_TYPE": "LUT1",
                "X_ORIG_PORT_A3": "I0", "X_ORIG_PORT_O5": "O"},
            "port_directions": {"A3": "input", "A6": "input", "O5": "output"},
            "connections": {"A3": [2], "A6": [4], "O5": [5]}}
        design["modules"]["top"]["netnames"]["paired_output"] = {"bits": [5], "attributes": {}}
        result, output = self.run_checkpoint(design)
        self.assertGreater(result.returncode, 0)
        self.assertIsNone(output)
        self.assertIn("timing analysis failed", result.stderr)

    def test_incomplete_postroute_logical_mapping_cannot_hide_feedback(self):
        for attr in ("X_ORIG_PORT_A4", "X_ORIG_PORT_O6", "X_ORIG_TYPE"):
            with self.subTest(missing=attr):
                design = self.postroute_lut_fixture()
                del design["modules"]["top"]["cells"]["actual_lut"]["attributes"][attr]
                result, output = self.run_checkpoint(design)
                self.assertGreater(result.returncode, 0)
                self.assertIsNone(output)
                self.assertIn("timing analysis failed", result.stderr)

    def test_distinct_clock_selectors_survive_two_roundtrips(self):
        result, output = self.run_checkpoint(self.fixture())
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {"noninverted_selector": ["PIPID/CLBLL_R_X25Y184/148"],
                    "inverted_selector": ["PIPID/CLBLL_R_X25Y184/368"]}
        self.assertEqual(self.pip_names(output), expected)
        result, second = self.run_checkpoint(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pip_names(second), expected)

    def test_alternative_parallel_pip_is_not_replaced_by_first_match(self):
        design = self.fixture()
        attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
        attrs["ROUTING"] = attrs["ROUTING"].replace("/148;", "/149;")
        result, output = self.run_checkpoint(design)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pip_names(output)["noninverted_selector"], ["PIPID/CLBLL_R_X25Y184/149"])

    def test_ambiguous_legacy_clock_name_fails_closed(self):
        design = self.fixture()
        attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
        attrs["ROUTING"] = attrs["ROUTING"].replace("PIPID/CLBLL_R_X25Y184/148",
            "SITEWIRE/SLICE_X36Y184/CLK->SITEWIRE/SLICE_X36Y184/CLKINV_OUT")
        result, _ = self.run_checkpoint(design)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ambiguous wire-to-wire PIP", result.stderr)

    def test_invalid_pip_identity_is_rejected_without_abort(self):
        for identity in ("PIPID/NO_SUCH_TILE/148", "PIPID/CLBLL_R_X25Y184/-1",
                         "PIPID/CLBLL_R_X25Y184/99999999", "PIPID/CLBLL_R_X25Y184/148junk"):
            with self.subTest(identity=identity):
                design = self.fixture()
                attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
                attrs["ROUTING"] = attrs["ROUTING"].replace("PIPID/CLBLL_R_X25Y184/148", identity)
                result, _ = self.run_checkpoint(design)
                self.assertGreater(result.returncode, 0)
                self.assertIn("PIPID", result.stderr)

    def legacy_clock_fixture(self, selector, site="SLICE_X36Y184"):
        design = self.fixture()
        attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
        attrs["ROUTING"] = attrs["ROUTING"].replace("PIPID/CLBLL_R_X25Y184/148",
            "SITEWIRE/SLICE_X36Y184/CLK->SITEWIRE/SLICE_X36Y184/CLKINV_OUT")
        design["modules"]["top"]["settings"] = {f"checkpoint/selector/{site}/CLKINV": selector}
        return design

    def test_explicit_clock_selection_recovers_both_parallel_pips(self):
        for selector, index in (("CLK", 148), ("CLK_B", 149)):
            with self.subTest(selector=selector):
                result, output = self.run_checkpoint(self.legacy_clock_fixture(selector))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                 [f"PIPID/CLBLL_R_X25Y184/{index}"])
                result, second = self.run_checkpoint(output)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pip_names(second), self.pip_names(output))

    def test_invalid_or_wrong_site_selection_cannot_authorize_recovery(self):
        for selector, site in (("INVALID", "SLICE_X36Y184"), ("CLK", "SLICE_X37Y184")):
            with self.subTest(selector=selector, site=site):
                result, _ = self.run_checkpoint(self.legacy_clock_fixture(selector, site))
                self.assertGreater(result.returncode, 0)
                self.assertIn("Ambiguous wire-to-wire PIP", result.stderr)

    def test_evidenced_bufg_ignore1_selection_preserves_requested_pip(self):
        for selection, index in (("IGNORE1", 141), ("IGNORE1_B", 142)):
            with self.subTest(selection=selection):
                design = self.fixture()
                design["modules"]["top"]["settings"] = {
                    "checkpoint/selector/BUFGCTRL_X0Y14/IGNORE1INV": selection}
                attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
                attrs["ROUTING"] = ("SITEWIRE/BUFGCTRL_X0Y14/IGNORE1INV_OUT;"
                    "SITEWIRE/BUFGCTRL_X0Y14/IGNORE1->SITEWIRE/BUFGCTRL_X0Y14/IGNORE1INV_OUT;1;"
                    "SITEWIRE/BUFGCTRL_X0Y14/IGNORE1;;1")
                result, output = self.run_checkpoint(design)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                 [f"PIPID/CLK_BUFG_BOT_R_X155Y204/{index}"])

    def test_unambiguous_legacy_arrows_are_still_accepted(self):
        result, output = self.run_checkpoint(self.fixture("kintex-routed-arrow.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        for names in self.pip_names(output).values():
            self.assertTrue(names)
            self.assertTrue(all(name.startswith("PIPID/") for name in names))

    def test_real_io_site_variant_resolves_iused_without_guessing(self):
        design = self.fixture()
        attrs = design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]
        attrs["ROUTING"] = ("SITEWIRE/IOB_X0Y174/I;"
            "SITEWIRE/IOB_X0Y174/INBUF_EN_OUT->SITEWIRE/IOB_X0Y174/I;1;"
            "SITEWIRE/IOB_X0Y174/INBUF_EN_OUT;;1")
        # Without placement evidence, neither site-variant PIP may be guessed.
        result, _ = self.run_checkpoint(design)
        self.assertGreater(result.returncode, 0)
        design["modules"]["top"]["cells"]["clock0"] = {
            "type": "IOB33_INBUF_EN", "parameters": {},
            "attributes": {"NEXTPNR_BEL": "IOB_X0Y174/IOB33/INBUF_EN"},
            "port_directions": {"OUT": "output"}, "connections": {"OUT": [2]}}
        result, output = self.run_checkpoint(design)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.pip_names(output)["noninverted_selector"],
                         ["PIPID/LIOB33_X0Y173/62"])

    def interconnect_alias_fixture(self):
        design = self.fixture()
        design["modules"]["top"]["netnames"]["noninverted_selector"]["attributes"]["ROUTING"] = (
            "INT_R_X19Y149/IMUX31;INT_L_X20Y149/WL1BEG3->INT_R_X19Y149/IMUX31;1;"
            "INT_L_X20Y149/WL1BEG3;;1")
        return design

    def test_original_dsp_control_and_clock_choices_survive_import(self):
        for pin, normal, inverted in (("INMODE0", 423, 424), ("OPMODE6", 419, 420),
                                     ("ALUMODE2", 421, 422), ("CARRYIN", 435, 436), ("CLK", 445, 446)):
            for selection, index in ((pin, normal), (pin + "_B", inverted)):
                with self.subTest(pin=pin, selection=selection):
                    design = self.fixture()
                    module = design["modules"]["top"]
                    module["settings"] = {f"checkpoint/selector/DSP48_X5Y98/{pin}INV": selection}
                    module["netnames"]["noninverted_selector"]["attributes"]["ROUTING"] = (
                        f"SITEWIRE/DSP48_X5Y98/{pin}INV_OUT;"
                        f"SITEWIRE/DSP48_X5Y98/{pin}->SITEWIRE/DSP48_X5Y98/{pin}INV_OUT;1;"
                        f"SITEWIRE/DSP48_X5Y98/{pin};;1")
                    result, output = self.run_checkpoint(design)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                     [f"PIPID/DSP_L_X54Y245/{index}"])

    def test_actual_mmcm_control_choices_survive_import(self):
        for pin, normal, inverted in (("CLKINSEL", 174, 175), ("RST", 166, 167),
                                     ("PWRDWN", 168, 169), ("PSEN", 172, 173), ("PSINCDEC", 170, 171)):
            for selection, index in ((pin, normal), (pin + "_B", inverted)):
                with self.subTest(pin=pin, selection=selection):
                    design = self.fixture()
                    module = design["modules"]["top"]
                    module["settings"] = {f"checkpoint/selector/MMCME2_ADV_X0Y3/{pin}INV": selection}
                    module["netnames"]["noninverted_selector"]["attributes"]["ROUTING"] = (
                        f"SITEWIRE/MMCME2_ADV_X0Y3/{pin}INV_OUT;"
                        f"SITEWIRE/MMCME2_ADV_X0Y3/{pin}->SITEWIRE/MMCME2_ADV_X0Y3/{pin}INV_OUT;1;"
                        f"SITEWIRE/MMCME2_ADV_X0Y3/{pin};;1")
                    result, output = self.run_checkpoint(design)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                     [f"PIPID/CMT_TOP_R_LOWER_B_X8Y165/{index}"])

    def test_real_bram_clock_pair_requires_explicit_polarity(self):
        for selection, index in (("CLKARDCLK", 376), ("CLKARDCLK_B", 377)):
            with self.subTest(selection=selection):
                design = self.fixture()
                module = design["modules"]["top"]
                module["settings"] = {
                    "checkpoint/selector/RAMB18_X2Y87/CLKARDCLKINV": selection}
                module["netnames"]["noninverted_selector"]["attributes"]["ROUTING"] = (
                    "SITEWIRE/RAMB18_X2Y87/CLKARDCLKINV_OUT;"
                    "SITEWIRE/RAMB18_X2Y87/CLKARDCLK->SITEWIRE/RAMB18_X2Y87/CLKARDCLKINV_OUT;1;"
                    "SITEWIRE/RAMB18_X2Y87/CLKARDCLK;;1")
                result, output = self.run_checkpoint(design)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                 [f"PIPID/BRAM_L_X26Y215/{index}"])
                module["settings"] = {}
                result, _ = self.run_checkpoint(design)
                self.assertGreater(result.returncode, 0)

    def test_placed_lower_bram18_and_bram36_variants_preserve_clock_polarity(self):
        for site, original, pin, normal, inverted in (
                ("RAMB18_X2Y86", "RAMB18E1", "CLKARDCLK", 228, 229),
                ("RAMB36_X2Y43", "RAMB36E1", "CLKARDCLKL", 794, 795)):
            for selection, index in ((pin, normal), (pin + "_B", inverted)):
                with self.subTest(site=site, selection=selection):
                    design = self.fixture()
                    module = design["modules"]["top"]
                    module["cells"]["weight_rom"] = {
                        "type": f"{original}_{original}", "parameters": {},
                        "attributes": {"NEXTPNR_BEL": f"{site}/{original}"},
                        "port_directions": {pin: "input"}, "connections": {pin: [2]}}
                    module["settings"] = {f"checkpoint/selector/{site}/{pin}INV": selection}
                    module["netnames"]["noninverted_selector"]["attributes"]["ROUTING"] = (
                        f"SITEWIRE/{site}/{pin}INV_OUT;"
                        f"SITEWIRE/{site}/{pin}->SITEWIRE/{site}/{pin}INV_OUT;1;"
                        f"SITEWIRE/{site}/{pin};;1")
                    result, output = self.run_checkpoint(design)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                     [f"PIPID/BRAM_L_X26Y215/{index}"])

    def test_original_fasm_selects_either_interconnect_switch_explicitly(self):
        for feature, index in (("INT_R_X19Y149.IMUX31.WL1END3", 3422),
                               ("INT_R_X19Y149.IMUX31.WR1END_S1_0", 3537)):
            with self.subTest(feature=feature):
                result, output = self.run_checkpoint(self.interconnect_alias_fixture(), feature + "\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.pip_names(output)["noninverted_selector"],
                                 [f"PIPID/INT_R_X19Y149/{index}"])

    def test_absent_conflicting_or_disabled_switch_evidence_is_rejected(self):
        first = "INT_R_X19Y149.IMUX31.WL1END3"
        second = "INT_R_X19Y149.IMUX31.WR1END_S1_0"
        for features in ("", first + "\n" + second + "\n", first + " = 0\n"):
            with self.subTest(features=features):
                result, _ = self.run_checkpoint(self.interconnect_alias_fixture(), features)
                self.assertGreater(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
