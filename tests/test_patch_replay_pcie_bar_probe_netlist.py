import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/pipeline/patch_replay_pcie_bar_probe_netlist.py"
BASELINE = Path(
    "/nix/store/iwy6sw36cskqqywj58jpg3f71c84qcm1-"
    "compiler-ddr3-trace-replay-synthesis-screen/replay.json"
)


def load_tool():
    spec = importlib.util.spec_from_file_location("bar_probe_patch", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayPcieBarProbeNetlistPatchTest(unittest.TestCase):
    def test_patch_changes_only_authenticated_existing_cells(self):
        tool = load_tool()
        original = json.loads(BASELINE.read_text())
        patched, receipt = tool.patch_document(copy.deepcopy(original))
        before = original["modules"][tool.TOP]
        after = patched["modules"][tool.TOP]
        changed = {name for name in before["cells"]
                   if before["cells"][name] != after["cells"][name]}
        self.assertEqual(changed, set(receipt["changed_existing_cells"]))
        self.assertEqual(set(after["cells"]) - set(before["cells"]), set())
        self.assertEqual(set(after["netnames"]) - set(before["netnames"]), set())
        self.assertEqual(receipt["added_cells"], [])
        self.assertEqual(receipt["added_netnames"], [])
        self.assertEqual(len(receipt["probe"]["changed_consumer_ports"]), 14)

    def test_patch_repoints_consumers_but_not_driver(self):
        tool = load_tool()
        patched, _ = tool.patch_document(json.loads(BASELINE.read_text()))
        module = patched["modules"][tool.TOP]
        input_uses = []
        output_uses = []
        for name, cell in module["cells"].items():
            for port, bits in cell.get("connections", {}).items():
                if tool.TX_LIVE_BIT in bits:
                    (output_uses if port == "O" else input_uses).append([name, port])
        self.assertEqual(input_uses, [])
        self.assertEqual(len(output_uses), 1)

    def test_wrong_hash_fails_closed(self):
        tool = load_tool()
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
