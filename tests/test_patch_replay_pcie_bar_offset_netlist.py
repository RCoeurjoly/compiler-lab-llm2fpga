"""Fail-closed tests for BAR-relative replay CSR decode in the pinned netlist."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/pipeline/patch_replay_pcie_bar_offset_netlist.py"
BASELINE = Path(
    "/nix/store/iwy6sw36cskqqywj58jpg3f71c84qcm1-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)
RESET_PATCHED = Path(
    "/nix/store/wh8wymbb4a6n9zfkawz0pkpkns5wyg1l-"
    "compiler-ddr3-trace-replay-reset-patched/replay.json"
)


def load_tool():
    if not TOOL.exists():
        raise AssertionError("BAR-offset netlist patch tool is missing")
    spec = importlib.util.spec_from_file_location("bar_offset_patch", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayPcieBarOffsetNetlistPatchTest(unittest.TestCase):
    def test_nix_route_chains_bar_offset_after_reset_patch(self):
        text = (ROOT / "nix/task6-board-shell.nix").read_text()
        self.assertIn("replayBarOffsetPatched =", text)
        self.assertIn("patch_replay_pcie_bar_offset_netlist.py", text)
        offset = text.split("replayBarOffsetPatched =", 1)[1].split("replayBarObserverResetPatched =", 1)[0]
        self.assertIn("${replayResetPatched}/replay.json", offset)
        route = text.split("replayRoute =", 1)[1].split("replayBarObserverRoute =", 1)[0]
        self.assertIn("${replayBarOffsetPatched}/replay.json", route)

    def test_accepts_authenticated_reset_patched_predecessor(self):
        tool = load_tool()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.json"
            receipt = Path(directory) / "receipt.json"
            tool.patch_file(RESET_PATCHED, output, receipt)
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(receipt.read_text())["source_sha256"],
                             "bcf7027888c52b9724d6d18c21d816cddd2e91995f07735437134ad8c8bf2ea9")

    def test_patch_zeros_only_authenticated_high_address_consumers(self):
        tool = load_tool()
        original = json.loads(BASELINE.read_text())
        patched, receipt = tool.patch_document(copy.deepcopy(original))
        before = original["modules"][tool.TOP]
        after = patched["modules"][tool.TOP]

        self.assertEqual(set(after["cells"]), set(before["cells"]))
        self.assertEqual(set(after["netnames"]), set(before["netnames"]))
        self.assertEqual(receipt["changed_consumer_ports"], 80)
        self.assertEqual(receipt["added_cells"], [])
        self.assertEqual(receipt["added_netnames"], [])

        high_bits = set()
        for name in ("replay_bridge.awaddr", "replay_bridge.araddr"):
            high_bits.update(before["netnames"][name]["bits"][12:])
        for cell in after["cells"].values():
            for port, bits in cell.get("connections", {}).items():
                if cell.get("port_directions", {}).get(port) != "output":
                    self.assertTrue(high_bits.isdisjoint(bits))

        for bit in high_bits:
            before_drivers = tool.output_sites(before, bit)
            after_drivers = tool.output_sites(after, bit)
            self.assertEqual(after_drivers, before_drivers)
            self.assertEqual(len(after_drivers), 1)

    def test_wrong_hash_and_consumer_structure_fail_closed(self):
        tool = load_tool()
        original = json.loads(BASELINE.read_text())
        broken = copy.deepcopy(original)
        bit = broken["modules"][tool.TOP]["netnames"]["replay_bridge.awaddr"]["bits"][12]
        for cell in broken["modules"][tool.TOP]["cells"].values():
            for port, bits in cell.get("connections", {}).items():
                if cell.get("port_directions", {}).get(port) != "output" and bit in bits:
                    cell["connections"][port] = ["0" if item == bit else item for item in bits]
                    with self.assertRaisesRegex(ValueError, "consumer"):
                        tool.patch_document(broken)
                    break
            else:
                continue
            break

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
