"""Fail-closed tests for the timing-preserving PCIe reset netlist patch."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/pipeline/patch_replay_pcie_reset_netlist.py"
BASELINE = Path(
    "/nix/store/iwy6sw36cskqqywj58jpg3f71c84qcm1-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)
OBSERVER_BASELINE = Path(
    "/nix/store/3gn7a9p3p2j81z8g4czcn79rw1iy2716-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)
COMPACT_OBSERVER_BASELINE = Path(
    "/nix/store/nr91bgp1zb1ywk4ln8z0prfi0frv6iqj-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)
REUSED_USER1_OBSERVER_BASELINE = Path(
    "/nix/store/d7ay8253i2s3wwwpf9rcga9i4sdb24m5-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)


def load_tool():
    spec = importlib.util.spec_from_file_location("patch_replay_reset", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayPcieResetNetlistPatchTest(unittest.TestCase):
    def test_exact_patch_changes_only_authenticated_reset_cone(self):
        tool = load_tool()
        original = json.loads(BASELINE.read_text())
        patched, receipt = tool.patch_document(copy.deepcopy(original))
        module_before = original["modules"][tool.TOP]
        module_after = patched["modules"][tool.TOP]

        changed = {
            name for name in module_before["cells"]
            if module_before["cells"][name] != module_after["cells"].get(name)
        }
        added = set(module_after["cells"]) - set(module_before["cells"])
        self.assertEqual(changed, {tool.TRANSPORT_RESET_LUT})
        self.assertEqual(added, set())
        self.assertEqual(set(module_after["netnames"]) - set(module_before["netnames"]),
                         set())
        self.assertEqual(receipt["changed_existing_cells"], sorted(changed))
        self.assertEqual(receipt["added_cells"], [])
        self.assertEqual(receipt["added_netnames"], [])

    def test_transport_reset_is_independent_of_ddr_and_flush_state(self):
        tool = load_tool()
        for cfg_reset in (0, 1):
            for row_ready in (0, 1):
                for bar_ready in (0, 1):
                    for flush_nonzero in (0, 1):
                        reset = tool.transport_reset(
                            cfg_reset, row_ready, bar_ready, flush_nonzero)
                        self.assertEqual(reset, bool(cfg_reset))
        self.assertFalse(tool.transport_reset(0, 0, 1, 0))

    def test_authenticated_bar_observer_profile_changes_only_reset_lut(self):
        tool = load_tool()
        source = OBSERVER_BASELINE.read_bytes()
        profile = tool.PROFILES[tool.hashlib.sha256(source).hexdigest()]
        original = json.loads(source)
        patched, receipt = tool.patch_document(copy.deepcopy(original), profile)
        before = original["modules"][tool.TOP]["cells"]
        after = patched["modules"][tool.TOP]["cells"]
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, {profile["transport_reset_lut"]})
        self.assertEqual(receipt["source_sha256"], profile["source_sha256"])
        self.assertTrue(receipt["invariants"]["transport_reset_depends_only_on_raw_cfg_reset"])

    def test_authenticated_compact_observer_profile_changes_only_reset_lut(self):
        tool = load_tool()
        source = COMPACT_OBSERVER_BASELINE.read_bytes()
        profile = tool.PROFILES[tool.hashlib.sha256(source).hexdigest()]
        original = json.loads(source)
        patched, receipt = tool.patch_document(copy.deepcopy(original), profile)
        before = original["modules"][tool.TOP]["cells"]
        after = patched["modules"][tool.TOP]["cells"]
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, {profile["transport_reset_lut"]})
        self.assertEqual(after[profile["transport_reset_lut"]]["type"], "LUT1")
        self.assertEqual(receipt["source_sha256"], profile["source_sha256"])

    def test_authenticated_reused_user1_profile_changes_only_reset_lut(self):
        tool = load_tool()
        source = REUSED_USER1_OBSERVER_BASELINE.read_bytes()
        profile = tool.PROFILES[tool.hashlib.sha256(source).hexdigest()]
        original = json.loads(source)
        patched, receipt = tool.patch_document(copy.deepcopy(original), profile)
        before = original["modules"][tool.TOP]["cells"]
        after = patched["modules"][tool.TOP]["cells"]
        changed = {name for name in before if before[name] != after[name]}
        self.assertEqual(changed, {profile["transport_reset_lut"]})
        self.assertEqual(after[profile["transport_reset_lut"]]["type"], "LUT1")
        self.assertEqual(receipt["source_sha256"], profile["source_sha256"])

    def test_wrong_structure_and_wrong_input_hash_fail_closed(self):
        tool = load_tool()
        original = json.loads(BASELINE.read_text())
        broken = copy.deepcopy(original)
        broken["modules"][tool.TOP]["cells"][tool.TRANSPORT_RESET_LUT]["parameters"]["INIT"] = "0000"
        with self.assertRaisesRegex(ValueError, "transport reset LUT"):
            tool.patch_document(broken)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "output.json"
            receipt = Path(directory) / "receipt.json"
            source.write_text(BASELINE.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "source SHA-256"):
                tool.patch_file(source, output, receipt)
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
