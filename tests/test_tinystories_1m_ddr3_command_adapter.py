from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "tinystories_1m_ddr3_command_adapter.sv"


class TinyStoriesDdr3CommandAdapterContractTest(unittest.TestCase):
    def test_assembles_prompt_and_holds_core_run(self):
        source = RTL.read_text(encoding="utf-8")
        self.assertIn("prompt_words [0:3]", source)
        self.assertIn("prompt_count == 3'd4", source)
        self.assertIn("assign prompt_ready = !run_active", source)
        self.assertIn(".start(run_active), .valid(run_active)", source)

    def test_exposes_transport_neutral_result_and_wishbone(self):
        source = RTL.read_text(encoding="utf-8")
        for name in ("token_valid", "token_ready", "token_id", "request_count", "wb_cyc", "wb_ack", "wb_rdata"):
            self.assertIn(name, source)


if __name__ == "__main__":
    unittest.main()
