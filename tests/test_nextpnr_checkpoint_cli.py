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
    def run_checkpoint(self, design):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            target = Path(directory) / "output.json"
            source.write_text(json.dumps(design))
            result = subprocess.run([TOOL, "--chipdb", CHIPDB, "--json", str(source),
                                     "--no-pack", "--no-place", "--no-route", "--write", str(target)],
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

    def test_unambiguous_legacy_arrows_are_still_accepted(self):
        result, output = self.run_checkpoint(self.fixture("kintex-routed-arrow.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        for names in self.pip_names(output).values():
            self.assertTrue(names)
            self.assertTrue(all(name.startswith("PIPID/") for name in names))


if __name__ == "__main__":
    unittest.main()
