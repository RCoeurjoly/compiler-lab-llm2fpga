import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory


TESTBENCH = r'''module tb;
  localparam int PORTS = 4;
  logic clk = 0;
  always #5 clk = ~clk;
  logic rst = 1;
  wire reset = rst;
  logic [PORTS-1:0] req_valid;
  logic [PORTS-1:0] req_ready;
  logic [PORTS*32-1:0] req_addr;
  logic [PORTS-1:0] rsp_valid;
  logic [PORTS*64-1:0] rsp_data;
  logic [PORTS-1:0] done;
  logic [PORTS*8-1:0] read_data;
  logic active = 1;
  logic saw_group_done = 0;
  wire operation_go_in = active && !operation_done_out;
  wire operation_go_out = operation_go_in;
  wire operation_done_out = operation_done_in;
  wire operation_done_in;
  wire bank_0_done = done[0];
  wire bank_1_done = done[1];
  wire bank_2_done = done[2];
  wire bank_3_done = done[3];
  logic wb_cyc, wb_stb, wb_accept, wb_ack = 0, wb_err = 0;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata;
  logic wb_ack_pending = 0;

  assign wb_accept = wb_cyc && wb_stb;
  assign operation_done_in = bank_0_done & bank_1_done & bank_2_done & bank_3_done;

  always_ff @(posedge clk) begin
    if (rst) begin
      wb_ack_pending <= 0;
      wb_ack <= 0;
      wb_rdata <= 0;
    end else begin
      wb_ack <= wb_ack_pending;
      wb_ack_pending <= wb_accept;
      if (wb_accept) begin
        case (wb_addr)
          32'd0: wb_rdata <= {64'd1, 64'd0};
          32'd1: wb_rdata <= {64'd3, 64'd2};
          default: wb_rdata <= '0;
        endcase
      end
    end
  end

  llm_external_memory_arbiter #(.PORTS(PORTS)) arbiter (.*);

  for (genvar i = 0; i < PORTS; i++) begin : memories
    seq_mem_d1_external #(
      .WIDTH(8), .SIZE(4), .IDX_SIZE(2), .EXT_BASE_ADDR(i * 8)
    ) memory (
      .clk(clk), .reset(rst), .addr0(2'd0), .content_en(operation_go_out),
      .done(done[i]), .read_data(read_data[i*8 +: 8]),
      .write_data(8'd0), .write_en(1'b0),
      .ext_req_valid(req_valid[i]), .ext_req_ready(req_ready[i]),
      .ext_req_addr(req_addr[i*32 +: 32]), .ext_rsp_valid(rsp_valid[i]),
      .ext_rsp_data(rsp_data[i*64 +: 64])
    );
  end

  initial begin
    repeat (2) @(posedge clk);
    rst = 0;
    repeat (128) begin
      @(posedge clk);
      #1;
      if (operation_done_in) begin
        saw_group_done = 1;
        active = 0;
      end
    end
    if (!saw_group_done)
      $fatal(1, "four held bank reads never reached the generated all-done barrier");
    if (read_data != 32'h03020100)
      $fatal(1, "bank data was not held at the completed request addresses: %h", read_data);
    $display("PASS: all bank responses remain available at the grouped completion barrier");
    $finish;
  end
endmodule
'''


class ExternalMemoryCompletionGroupTest(unittest.TestCase):
    def test_all_banked_responses_can_satisfy_generated_and_done_barrier(self):
        verilator = shutil.which("verilator")
        self.assertIsNotNone(verilator, "Verilator is required for the RTL behavior test")
        arbiter = Path(__file__).parents[1] / "rtl/memory/llm_external_memory_arbiter.sv"

        with tempfile.TemporaryDirectory(prefix="external-memory-group-") as temp_dir:
            temp = Path(temp_dir)
            (temp / "tb.sv").write_text(
                externalize_compiler_memory._EXTERNAL_MODULE
                + "\n"
                + arbiter.read_text(encoding="utf-8")
                + "\n"
                + externalize_compiler_memory.latch_external_memory_completion_joins(
                    TESTBENCH, [f"bank_{index}" for index in range(4)]
                ),
                encoding="utf-8",
            )
            built = subprocess.run(
                [verilator, "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run(
                [str(temp / "obj_dir" / "Vtb")],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: all bank responses remain available", ran.stdout)


if __name__ == "__main__":
    unittest.main()
