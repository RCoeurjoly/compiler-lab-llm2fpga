"""Passive, authenticated PCIe configuration observer regression."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "scripts/pipeline/apply_task6_pcie_cfg_observer_overlay.py"
DECODER = ROOT / "scripts/analysis/decode_task6_pcie_status.py"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    candidates = sorted(Path("/nix/store").glob(f"*-iverilog-*/bin/{name}"))
    if not candidates:
        raise AssertionError(f"missing {name}")
    return str(candidates[-1])


class PcieCfgObserverTest(unittest.TestCase):
    def test_version_three_decoder_preserves_v2_and_decodes_observer(self):
        module = load(DECODER)
        payload = 0
        payload |= module.MAGIC
        payload |= 3 << 32
        payload |= 0x12345678 << 392
        payload |= 0x89ABCDEF << 744
        payload |= 17 << 360
        payload |= 5 << 328
        decoded = module.decode(f"{payload:x}", 1024)
        self.assertTrue(decoded["magic_ok"])
        self.assertEqual(decoded["version"], 3)
        self.assertEqual(decoded["tlp_debug"]["rx_beat_count"], 0x12345678)
        self.assertEqual(decoded["tlp_debug"]["first_tx_qword_hex"],
                         "0x89abcdef00000000")
        self.assertEqual(decoded["cfg_transactions"], {
            "counter_semantics": "wrapping_32_bit",
            "total_count": 17,
            "read_count": 12,
            "write_count": 5,
        })

        version_two = module.decode(f"{(2 << 32) | module.MAGIC:x}", 1024)
        self.assertNotIn("cfg_transactions", version_two)

        version_four_payload = payload & ~(0xff << 32)
        version_four_payload |= 4 << 32
        version_four_payload |= 23 << 520
        version_four_payload |= 19 << 552
        version_four_payload |= 7 << 584
        version_four_payload |= 0xf << 616
        version_four_payload |= 0x24 << 712
        version_four = module.decode(f"{version_four_payload:x}", 1024)
        self.assertEqual(version_four["bar_read_boundary"], {
            "arvalid_cycles": 23,
            "ar_handshakes": 19,
            "rvalid_cycles": 7,
            "r_handshake_seen": True,
            "last_araddr": 0x24,
            "last_rdata": 0x89ABCDEF,
        })

    def test_overlay_is_fail_closed_and_reuses_existing_counters(self):
        self.assertTrue(OVERLAY.exists(), "missing authenticated observer overlay")
        module = load(OVERLAY)
        fixture = module.test_fixture()
        outputs = module.transform_sources(fixture)
        self.assertEqual(set(outputs), {module.PCIE_PATH, module.TOP_PATH, module.STATUS_PATH})
        self.assertIn(b"output                                     cfg_transaction,", outputs[module.PCIE_PATH])
        self.assertIn(b".cfg_transaction                            (cfg_transaction)", outputs[module.PCIE_PATH])
        self.assertNotIn(b"task6_pcie_cfg_observer", outputs[module.STATUS_PATH])
        self.assertIn(b"if (cfg_transaction_i)", outputs[module.STATUS_PATH])
        self.assertIn(b"if (cfg_transaction_i && cfg_transaction_type_i)",
                      outputs[module.STATUS_PATH])
        self.assertIn(b"cfg_transaction_i(cfg_transaction)", outputs[module.TOP_PATH])
        self.assertIn(b"bar_arvalid_i(s_axi_arvalid)", outputs[module.TOP_PATH])
        self.assertIn(b"bar_rvalid_i(s_axi_rvalid)", outputs[module.TOP_PATH])
        self.assertIn(b"input  wire        bar_arvalid_i", outputs[module.STATUS_PATH])
        self.assertIn(b"if (bar_arvalid_i)", outputs[module.STATUS_PATH])
        self.assertIn(b"(bar_rvalid_i && bar_rready_i)", outputs[module.STATUS_PATH])
        for path, source in fixture.items():
            corrupted = dict(fixture)
            corrupted[path] = source + b"\n// drift"
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "hash|identity"):
                    module.transform_sources(corrupted)

    def test_nix_applies_observer_only_to_replay_source_closure(self):
        text = (ROOT / "nix/task6-board-shell.nix").read_text()
        self.assertIn("replayObserverSourceClosure", text)
        self.assertIn("apply_task6_pcie_cfg_observer_overlay.py", text)
        self.assertNotIn("task6_pcie_cfg_observer.sv", text)
        self.assertIn("sourceArgs =", text)
        self.assertIn("replayObserverSourceClosure", text[text.index("sourceArgs ="):])
        self.assertNotIn("compiler_pcie_bar_status_shift.sv", text)


if __name__ == "__main__":
    unittest.main()
