import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis.externalize_compiler_memory import (
    _BANKED_EXTERNAL_MODULE,
    consolidate_token_weight_banks,
    externalize_memories,
    externalize_memory,
    remove_static_initializers,
)


SOURCE = """module main(\n  input logic clk,\n  input logic reset\n);\nlogic [3:0] weights_addr;\nlogic weights_en;\nlogic weights_done;\nlogic [7:0] weights_data;\nseq_mem_d1_bram #(.IDX_SIZE(4), .SIZE(16), .WIDTH(8)) weights (\n  .addr0(weights_addr), .content_en(weights_en), .done(weights_done),\n  .read_data(weights_data), .clk(clk), .reset(reset),\n  .write_data(8'd0), .write_en(1'b0)\n);\nseq_mem_d1_bram #(.IDX_SIZE(2), .SIZE(4), .WIDTH(8)) other (\n  .addr0(weights_addr[1:0]), .content_en(weights_en), .done(),\n  .read_data(), .clk(clk), .reset(reset),\n  .write_data(8'd0), .write_en(1'b0)\n);\nendmodule\n"""


class ExternalizeCompilerMemoryTest(unittest.TestCase):
    def test_shared_controller_routes_one_bank_request_and_response(self):
        self.assertIsNotNone(__import__("shutil").which("verilator"))
        testbench = r'''
module tb;
  logic clk=0; always #5 clk=~clk;
  logic reset=1;
  logic [7:0] addr0=0;
  logic [1:0] content_en=0, write_en=0;
  wire [1:0] done;
  wire [15:0] read_data;
  logic [15:0] write_data=0;
  wire ext_req_valid;
  wire [31:0] ext_req_addr;
  logic ext_req_ready=0, ext_rsp_valid=0;
  logic [63:0] ext_rsp_data=0;
  seq_mem_d1_shared_banks #(
    .BANKS(2), .WIDTH(8), .SIZE(16), .IDX_SIZE(4),
    .BANK_BASES({32'd200, 32'd100})
  ) dut (.*);
  task tick; @(posedge clk); #1; endtask
  initial begin
    repeat (2) tick();
    @(negedge clk); reset=0; content_en=2'b01; addr0=8'h03;
    tick();
    if (!ext_req_valid || ext_req_addr != 32'd103)
      $fatal(1, "bank 0 request was not selected or based correctly");
    @(negedge clk); addr0=8'h0f; content_en=2'b00;
    repeat (2) begin
      tick();
      if (!ext_req_valid || ext_req_addr != 32'd103)
        $fatal(1, "request changed under backpressure");
    end
    @(negedge clk); ext_req_ready=1;
    tick();
    @(negedge clk); ext_req_ready=0;
    ext_rsp_data=64'ha500000000000000; ext_rsp_valid=1;
    tick();
    if (!done[0] || done[1] || read_data[7:0] != 8'ha5)
      $fatal(1, "bank 0 response was not routed");
    @(negedge clk); ext_rsp_valid=0; content_en=2'b10; addr0=8'h20;
    tick();
    if (!ext_req_valid || ext_req_addr != 32'd202)
      $fatal(1, "bank 1 request was not selected or based correctly");
    $display("PASS: shared bank request/response routing");
    $finish;
  end
  initial begin #1000; $fatal(1, "shared bank test timed out"); end
endmodule
'''
        with tempfile.TemporaryDirectory(prefix="shared-bank-controller-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(_BANKED_EXTERNAL_MODULE + testbench)
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vtb")], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: shared bank", run.stdout)

    def test_token_weight_banks_use_one_shared_request_controller(self):
        source = SOURCE.replace("weights", "token_weight_codes_i8_b0").replace(
            "other", "token_weight_codes_i8_b1"
        ).replace(".IDX_SIZE(2), .SIZE(4)", ".IDX_SIZE(4), .SIZE(16)")
        result = consolidate_token_weight_banks(
            source,
            ["token_weight_codes_i8_b0", "token_weight_codes_i8_b1"],
            {"token_weight_codes_i8_b0": 100, "token_weight_codes_i8_b1": 200},
        )
        self.assertIn("seq_mem_d1_shared_banks", result.source)
        self.assertEqual(result.source.count("seq_mem_d1_shared_banks"), 2)
        self.assertIn("ext_mem_req_valid[0]", result.source)
        self.assertIn("ext_mem_req_valid[1]", result.source)
        self.assertIn("BANK_BASES", result.source)
        self.assertEqual(result.source.count("seq_mem_d1_external #("), 1)

    def test_selected_memory_gets_external_request_response_port(self):
        result = externalize_memory(SOURCE, "weights")
        self.assertIn("output logic ext_mem_req_valid", result.source)
        self.assertIn("input logic ext_mem_rsp_valid", result.source)
        self.assertIn("seq_mem_d1_external", result.source)
        self.assertIn(".ext_req_valid(ext_mem_req_valid)", result.source)
        self.assertIn(".ext_rsp_data(ext_mem_rsp_data)", result.source)
        self.assertIn("!pending", result.source)
        self.assertIn("done <= pending && ext_rsp_valid", result.source)
        self.assertIn("seq_mem_d1_bram #(.IDX_SIZE(2), .SIZE(4), .WIDTH(8)) other", result.source)
        self.assertEqual(result.memory_name, "weights")
        self.assertEqual(result.memory_width, 8)

    def test_missing_memory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "memory instance"):
            externalize_memory(SOURCE, "missing")

    def test_dynamic_calyx_memory_can_be_bound_to_same_external_abi(self):
        dynamic = SOURCE.replace("seq_mem_d1_bram", "dyn_mem_d1", 1)
        result = externalize_memory(dynamic, "weights")
        self.assertIn("seq_mem_d1_external", result.source)
        self.assertNotIn("dyn_mem_d1 #(.IDX_SIZE(4)", result.source)

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

    def test_external_initializers_are_removed_without_touching_bram_state(self):
        static = ('$readmemh("image-weights.hex", weights.mem);\n'
                  '$readmemh("image-other.hex", other.mem);\n')
        result = remove_static_initializers(static, ["weights"])
        self.assertNotIn("weights.mem", result)
        self.assertIn("other.mem", result)

    def test_generated_data_path_read_and_write_initializers_are_removed(self):
        static = ('$readmemh({DATA, "/weights.dat"}, weights.mem);\n'
                  '$writememh({DATA, "/weights.out"}, weights.mem);\n'
                  '$readmemh({DATA, "/other.dat"}, other.mem);\n')
        result = remove_static_initializers(static, ["weights"])
        self.assertNotIn("weights.mem", result)
        self.assertIn("other.mem", result)

    def test_subword_response_selects_element_offset_within_ddr_lane(self):
        result = externalize_memory(SOURCE, "weights")
        self.assertIn("logic [2:0] response_byte_offset", result.source)
        self.assertIn("response_byte_offset <= ext_req_addr[2:0]", result.source)
        self.assertIn("ext_rsp_data >> (response_byte_offset * 8)", result.source)


if __name__ == "__main__":
    unittest.main()
