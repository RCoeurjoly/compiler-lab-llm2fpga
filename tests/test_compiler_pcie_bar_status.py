from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CompilerPcieBarStatusTest(unittest.TestCase):
    def test_payload_has_boundary_progress_and_stall_evidence(self):
        text = (ROOT / "rtl/diagnostics/compiler_pcie_bar_status_shift.sv").read_text()
        self.assertIn("32'h43504253", text)  # CPBS
        for name in ("arvalid_count_q", "ar_count_q", "rvalid_count_q", "r_count_q",
                     "last_araddr_q", "last_rdata_q", "sticky_q"):
            self.assertIn(name, text)
        self.assertIn("parameter integer WIDTH = 320", text)
        self.assertIn("JTAG_CHAIN = 4", text)

    def test_decoder_preserves_each_boundary_stage(self):
        path = ROOT / "scripts/pipeline/read_compiler_pcie_bar_status.py"
        spec = importlib.util.spec_from_file_location("bar_status", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = 0x43504253 | (2 << 32) | (0x7ff << 40)
        payload |= 11 << 56
        payload |= 12 << 80
        payload |= 13 << 112
        payload |= 14 << 144
        payload |= 15 << 176
        payload |= 0x24 << 208
        payload |= 0x54365043 << 240
        payload |= 0x7fff << 272
        payload |= 21 << 288
        decoded = module.decode(hex(payload))
        self.assertTrue(decoded["magic_ok"])
        self.assertEqual(decoded["version"], 2)
        self.assertEqual(decoded["clk_count"], 11)
        self.assertEqual(decoded["arvalid_cycles"], 12)
        self.assertEqual(decoded["ar_handshakes"], 13)
        self.assertEqual(decoded["rvalid_cycles"], 14)
        self.assertEqual(decoded["r_handshakes"], 15)
        self.assertEqual(decoded["last_rdata"], 0x54365043)
        self.assertEqual(decoded["sticky_word"], 0x7fff)
        self.assertEqual(decoded["reset_seen_cycles"], 21)


if __name__ == "__main__":
    unittest.main()
