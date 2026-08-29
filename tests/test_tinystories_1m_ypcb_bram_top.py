import unittest
import json
from pathlib import Path


class TinyStoriesTopContractTests(unittest.TestCase):
    def test_bram_top_exposes_kev_gpt_shell_and_core_handshake(self):
        source = Path("rtl/tinystories_1m_ypcb_bram_top.sv").read_text()
        for token in (
            "module tinystories_1m_ypcb_bram_top",
            "SYS_CLK",
            "SYS_RSTN",
            "prompt_valid",
            "prompt_ready",
            "requested_tokens",
            "token_valid",
            "token_id",
            "BRAM_ONLY",
        ):
            self.assertIn(token, source)

    def test_core_contract_is_explicit_blackbox(self):
        source = Path("rtl/llm2fpga_tinystories_1m_core_contract.sv").read_text()
        self.assertIn("(* blackbox *)", source)
        self.assertIn("module llm2fpga_tinystories_1m_core", source)
        self.assertIn("parameter integer BRAM_ONLY", source)

    def test_shell_has_no_out_of_scope_transport_or_ddr(self):
        source = Path("rtl/tinystories_1m_ypcb_bram_top.sv").read_text().lower()
        self.assertNotIn("ddr3", source)
        self.assertNotIn("pcie", source)

    def test_machine_readable_shell_manifest(self):
        manifest = json.loads(Path("artifacts/comparison/tinystories-1m-ypcb-bram-shell-contract.json").read_text())
        self.assertEqual(manifest["top_module"], "tinystories_1m_ypcb_bram_top")
        self.assertFalse(manifest["storage"]["external_memory"])
        self.assertEqual(manifest["core_module"], "llm2fpga_tinystories_1m_core")
        for reference in manifest["reference_tops"]:
            self.assertTrue(Path(reference).exists(), reference)


if __name__ == "__main__":
    unittest.main()
