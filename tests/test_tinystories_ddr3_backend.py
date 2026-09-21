from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "tinystories_1m_ddr3_backend.sv"


class TinyStoriesDdr3BackendContractTest(unittest.TestCase):
    def test_backend_preserves_compiler_memory_vector_and_wishbone_boundary(self):
        source = RTL.read_text()
        self.assertIn("module tinystories_1m_ddr3_backend", source)
        self.assertIn("[239:0] ext_mem_req_valid", source)
        self.assertIn("[7679:0] ext_mem_req_addr", source)
        self.assertIn("[15359:0] ext_mem_rsp_data", source)
        self.assertRegex(source, r"llm_external_memory_arbiter #\(\s*\.PORTS\(240\)")
        self.assertIn(".WB_DATA_BITS(128)", source)

    def test_backend_exposes_accepted_control_contract(self):
        source = RTL.read_text()
        for port in ("start", "valid", "prompt_0", "prompt_1", "prompt_2", "prompt_3", "token_index", "done", "token_id"):
            self.assertRegex(source, rf"\b{port}\b")

    def test_compiler_and_transport_boundaries_request_preserved_hierarchy(self):
        source = RTL.read_text()
        self.assertRegex(source, r"\(\*\s*keep_hierarchy\s*=\s*\"yes\"\s*\*\)\s*main\s+compiler_core")
        self.assertRegex(source, r"\(\*\s*keep_hierarchy\s*=\s*\"yes\"\s*\*\)\s*llm_external_memory_arbiter")


if __name__ == "__main__":
    unittest.main()
