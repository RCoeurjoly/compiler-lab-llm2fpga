// Simulation-only harness. Production adapter, backend, main and arbiter are
// supplied separately, unchanged. This is not a PCIe/DDR PHY simulation.
module command_integration_wrapper (
  input logic clk, reset, clear, prompt_valid, start, token_ready,
  input logic [15:0] prompt_token,
  output wire prompt_ready, token_valid, busy, error,
  output wire [15:0] token_id,
  output wire [7:0] error_code,
  output wire [31:0] request_count,
  output logic [63:0] requests, responses
);
  localparam integer LINES = 258545;
  wire wb_cyc, wb_stb, wb_we;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  wire wb_accept = wb_cyc && wb_stb;
  logic wb_ack = 0;
  wire wb_err = 0;
  logic [127:0] wb_rdata = 0;
  logic pending = 0;
  logic [31:0] pending_addr = 0;
  logic [127:0] image [0:LINES-1];
  string image_path;
  initial begin
    if (!$value$plusargs("IMAGE=%s", image_path))
      $fatal(1, "IMAGE argument required");
    $readmemh(image_path, image);
  end
  tinystories_1m_ddr3_command_adapter dut (.*);
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 0;
      wb_ack <= 0;
      requests <= 0;
      responses <= 0;
    end else begin
      wb_ack <= pending;
      if (pending) wb_rdata <= image[pending_addr];
      pending <= wb_accept;
      if (wb_accept) begin
        if (wb_we || wb_sel != 16'hffff || wb_addr >= LINES)
          $fatal(1, "invalid model read addr=%0d we=%0d sel=%h", wb_addr, wb_we, wb_sel);
        if (requests != responses)
          $fatal(1, "more than one outstanding model read");
        pending_addr <= wb_addr;
        requests <= requests + 1;
      end
      if (wb_ack) begin
        if (requests != responses + 1)
          $fatal(1, "unmatched response");
        responses <= responses + 1;
      end
    end
  end
endmodule
