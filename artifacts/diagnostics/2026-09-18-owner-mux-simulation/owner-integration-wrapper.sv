// Simulation-only boundary test. No accelerator or transport implementation
// is replaced. Memory below models transactions, not a DDR3 controller/PHY.
module command_integration_wrapper (
  input logic clk, reset, clear, prompt_valid, start, token_ready,
  input logic [15:0] prompt_token,
  output wire prompt_ready, token_valid, busy, error,
  output wire [15:0] token_id,
  output wire [7:0] error_code,
  output wire [31:0] request_count,
  output logic [63:0] requests, responses,
  input logic host_cyc, host_stb, host_we,
  input logic [24:0] host_addr,
  input logic [127:0] host_write_data,
  output wire host_stall, host_ack, host_err,
  output wire [127:0] host_read_data
);
  localparam integer LINES = 258545;
  wire wb_cyc, wb_stb, wb_we;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  wire wb_accept, wb_ack, wb_err, accelerator_stall;
  wire [127:0] wb_rdata;
  wire memory_cyc, memory_stb, memory_we;
  wire [24:0] memory_addr;
  wire [127:0] memory_write_data;
  wire [15:0] memory_sel;
  logic memory_ack = 0;
  logic [127:0] memory_read_data = 0;
  logic pending = 0;
  logic pending_we = 0;
  logic [24:0] pending_addr = 0;
  logic [127:0] pending_data = 0;
  logic [127:0] image [0:LINES-1];
  logic [7:0] phase = 0;
  wire memory_stall = pending || memory_ack || (phase[2:0] == 0);
  wire memory_accept = memory_cyc && memory_stb && !memory_stall;
  assign wb_accept = !accelerator_stall;

  tinystories_1m_ddr3_command_adapter dut (.*);
  task6_wishbone_owner_mux #(
    .ADDR_BITS(25), .DATA_BITS(128), .DIRECT_ACCELERATOR_OWNER(1'b0)
  ) owner_mux (
    .clk(clk), .rst(reset), .accelerator_enable(1'b1),
    .host_cyc(host_cyc), .host_stb(host_stb), .host_we(host_we),
    .host_addr(host_addr), .host_write_data(host_write_data), .host_sel(16'hffff),
    .host_stall(host_stall), .host_ack(host_ack), .host_err(host_err),
    .host_read_data(host_read_data),
    .accelerator_cyc(wb_cyc), .accelerator_stb(wb_stb), .accelerator_we(wb_we),
    .accelerator_addr(wb_addr[24:0]), .accelerator_write_data(128'd0),
    .accelerator_sel(wb_sel), .accelerator_stall(accelerator_stall),
    .accelerator_ack(wb_ack), .accelerator_err(wb_err), .accelerator_read_data(wb_rdata),
    .memory_cyc(memory_cyc), .memory_stb(memory_stb), .memory_we(memory_we),
    .memory_addr(memory_addr), .memory_write_data(memory_write_data),
    .memory_sel(memory_sel), .memory_stall(memory_stall), .memory_ack(memory_ack),
    .memory_err(1'b0), .memory_read_data(memory_read_data),
    .owner_active(), .accelerator_owned()
  );

  always_ff @(posedge clk) begin
    if (reset) begin
      phase <= 0;
      pending <= 0;
      memory_ack <= 0;
      requests <= 0;
      responses <= 0;
    end else begin
      phase <= phase + 1;
      memory_ack <= pending;
      pending <= memory_accept;
      if (pending) begin
        if (pending_we) image[pending_addr] <= pending_data;
        else memory_read_data <= image[pending_addr];
      end
      if (memory_accept) begin
        if (memory_addr >= LINES || memory_sel != 16'hffff)
          $fatal(1, "invalid memory access addr=%0d sel=%h", memory_addr, memory_sel);
        pending_addr <= memory_addr;
        pending_we <= memory_we;
        pending_data <= memory_write_data;
      end
      if (wb_cyc && wb_stb && wb_accept) begin
        if (wb_we || wb_sel != 16'hffff || wb_addr >= LINES)
          $fatal(1, "invalid compiler model read");
        if (requests != responses)
          $fatal(1, "more than one outstanding compiler request");
        requests <= requests + 1;
      end
      if (wb_ack) begin
        if (requests != responses + 1)
          $fatal(1, "unmatched compiler response");
        responses <= responses + 1;
      end
      if (host_ack && wb_ack) $fatal(1, "response delivered to both owners");
    end
  end
endmodule
