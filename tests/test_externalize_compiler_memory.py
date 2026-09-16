import unittest

from scripts.analysis.externalize_compiler_memory import (
    externalize_memories,
    externalize_memory,
)


SOURCE = """module main(\n  input logic clk,\n  input logic reset\n);\nlogic [3:0] weights_addr;\nlogic weights_en;\nlogic weights_done;\nlogic [7:0] weights_data;\nseq_mem_d1_bram #(.IDX_SIZE(4), .SIZE(16), .WIDTH(8)) weights (\n  .addr0(weights_addr), .content_en(weights_en), .done(weights_done),\n  .read_data(weights_data), .clk(clk), .reset(reset),\n  .write_data(8'd0), .write_en(1'b0)\n);\nseq_mem_d1_bram #(.IDX_SIZE(2), .SIZE(4), .WIDTH(8)) other (\n  .addr0(weights_addr[1:0]), .content_en(weights_en), .done(),\n  .read_data(), .clk(clk), .reset(reset),\n  .write_data(8'd0), .write_en(1'b0)\n);\nendmodule\n"""


class ExternalizeCompilerMemoryTest(unittest.TestCase):
    def test_selected_memory_gets_external_request_response_port(self):
        result = externalize_memory(SOURCE, "weights")
        self.assertIn("output logic ext_mem_req_valid", result.source)
        self.assertIn("input logic ext_mem_rsp_valid", result.source)
        self.assertIn("seq_mem_d1_external", result.source)
        self.assertIn(".ext_req_valid(ext_mem_req_valid)", result.source)
        self.assertIn(".ext_rsp_data(ext_mem_rsp_data)", result.source)
        self.assertIn("seq_mem_d1_bram #(.IDX_SIZE(2), .SIZE(4), .WIDTH(8)) other", result.source)
        self.assertEqual(result.memory_name, "weights")
        self.assertEqual(result.memory_width, 8)

    def test_missing_memory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "memory instance"):
            externalize_memory(SOURCE, "missing")

    def test_multiple_memories_share_indexed_external_vectors(self):
        result = externalize_memories(SOURCE, ["weights", "other"], {"weights": 4096, "other": 8192})
        self.assertIn("output logic [1:0] ext_mem_req_valid", result.source)
        self.assertIn("input logic [1:0] ext_mem_rsp_valid", result.source)
        self.assertIn(".ext_req_valid(ext_mem_req_valid[0])", result.source)
        self.assertIn(".ext_req_valid(ext_mem_req_valid[1])", result.source)
        self.assertIn(".ext_rsp_data(ext_mem_rsp_data[63:0])", result.source)
        self.assertIn(".ext_rsp_data(ext_mem_rsp_data[127:64])", result.source)
        self.assertIn(".EXT_BASE_ADDR(4096)", result.source)
        self.assertIn(".EXT_BASE_ADDR(8192)", result.source)
        self.assertEqual(result.memory_names, ("weights", "other"))


if __name__ == "__main__":
    unittest.main()
