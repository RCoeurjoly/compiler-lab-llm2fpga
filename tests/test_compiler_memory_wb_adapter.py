import shutil
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "rtl/memory/llm_compiler_memory_wb_adapter.sv"
ARBITER = ROOT / "rtl/memory/llm_external_memory_arbiter.sv"


def test_compiler_memory_adapter_returns_wishbone_read_to_requesting_port(tmp_path):
    verilator = shutil.which("verilator")
    assert verilator, "verilator is required for the adapter behavior test"
    tb = tmp_path / "tb.sv"
    template = textwrap.dedent(
            """
            module tb;
              logic clk = 0; always #1 clk = ~clk;
              logic rst = 1;
              logic [1:0] req_valid = 0;
              logic [2*32-1:0] req_addr = 0;
              logic [1:0] req_ready;
              logic [1:0] rsp_valid;
              logic [127:0] rsp_data;
              logic wb_cyc, wb_stb, wb_accept = 0, wb_ack = 0, wb_err = 0;
              logic [31:0] wb_addr;
              logic [15:0] wb_sel;
              logic [127:0] wb_rdata = 0;
              llm_compiler_memory_wb_adapter #(.PORTS(2), .REGISTER_REQUESTS(`REGISTERED)) dut (.*);
              integer cycles = 0;
              always @(posedge clk) begin
                cycles = cycles + 1;
                if (cycles == 100) $fatal(1, "adapter handshake timeout");
              end
              initial begin
                repeat (3) @(posedge clk);
                rst <= 0;
                @(posedge clk); req_valid[1] <= 1; req_addr[63:32] <= 32'd40;
                repeat (4) @(posedge clk); req_valid[1] <= 0;
                wait (wb_cyc && wb_stb); wb_accept <= 1;
                @(posedge clk); wb_accept <= 0; wb_rdata <= 128'h112233445566778899aabbccddeeff00;
                wait (wb_cyc && !wb_stb); wb_ack <= 1;
                @(posedge clk); wb_ack <= 0;
                wait (rsp_valid[1]);
                if (rsp_data[127:64] !== 64'h1122334455667788 || rsp_valid[0]) $fatal(1);
                $display("COMPILER_MEMORY_WB_ADAPTER_PASS");
                $finish;
              end
            endmodule
            """
        )
    for registered in (0, 1):
        case = tmp_path / f"registered-{registered}"
        case.mkdir()
        tb = case / "tb.sv"
        tb.write_text(f"`define REGISTERED {registered}\n" + template)
        build = subprocess.run(
            [verilator, "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", str(tb), str(ADAPTER), str(ARBITER)],
            cwd=case,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert build.returncode == 0, build.stderr + build.stdout
        run = subprocess.run([str(case / "obj_dir/Vtb")], cwd=case, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr + run.stdout
        assert "COMPILER_MEMORY_WB_ADAPTER_PASS" in run.stdout
