`default_nettype none

// Adapt the PCIe rowstream TinyStories command stream to the generated
// compiler core's four-word prompt and held start/valid contract.  This module
// owns no model state and does not alter the DDR3 or PCIe transport.
module tinystories_1m_ddr3_command_adapter #(
  parameter integer WB_ADDR_BITS = 32,
  parameter integer WB_DATA_BITS = 128
) (
  input wire clk,
  input wire reset,
  input wire clear,
  input wire prompt_valid,
  output wire prompt_ready,
  input wire [15:0] prompt_token,
  input wire start,
  output wire token_valid,
  input wire token_ready,
  output wire [15:0] token_id,
  output wire busy,
  output wire error,
  output wire [7:0] error_code,
  output wire [31:0] request_count,
  output wire wb_cyc,
  output wire wb_stb,
  output wire wb_we,
  output wire [WB_ADDR_BITS-1:0] wb_addr,
  output wire [WB_DATA_BITS/8-1:0] wb_sel,
  input wire wb_accept,
  input wire wb_ack,
  input wire wb_err,
  input wire [WB_DATA_BITS-1:0] wb_rdata
);
  reg [15:0] prompt_words [0:3];
  reg [2:0] prompt_count;
  reg run_active;
  reg token_valid_q;
  reg [15:0] token_id_q;
  reg error_q;
  reg [7:0] error_code_q;
  reg [31:0] request_count_q;
  wire core_done;
  wire [15:0] core_token_id;
  wire core_wb_cyc;
  wire core_wb_stb;
  wire core_wb_we;
  wire [WB_ADDR_BITS-1:0] core_wb_addr;
  wire [WB_DATA_BITS/8-1:0] core_wb_sel;

  assign prompt_ready = !run_active && !token_valid_q && prompt_count < 3'd4;
  assign token_valid = token_valid_q;
  assign token_id = token_id_q;
  assign busy = run_active || token_valid_q;
  assign error = error_q;
  assign error_code = error_code_q;
  assign request_count = request_count_q;
  assign wb_cyc = core_wb_cyc;
  assign wb_stb = core_wb_stb;
  assign wb_we = core_wb_we;
  assign wb_addr = core_wb_addr;
  assign wb_sel = core_wb_sel;

  tinystories_1m_ddr3_backend core (
    .clk(clk), .reset(reset),
    .start(run_active), .valid(run_active), .token_index(1'b0),
    .prompt_0(prompt_words[0]), .prompt_1(prompt_words[1]),
    .prompt_2(prompt_words[2]), .prompt_3(prompt_words[3]),
    .done(core_done), .token_id(core_token_id),
    .wb_cyc(core_wb_cyc), .wb_stb(core_wb_stb), .wb_we(core_wb_we),
    .wb_addr(core_wb_addr), .wb_sel(core_wb_sel),
    .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err),
    .wb_rdata(wb_rdata)
  );

  always @(posedge clk) begin
    if (reset || clear) begin
      prompt_count <= 3'd0;
      run_active <= 1'b0;
      token_valid_q <= 1'b0;
      token_id_q <= 16'd0;
      error_q <= 1'b0;
      error_code_q <= 8'd0;
      request_count_q <= 32'd0;
      prompt_words[0] <= 16'd0;
      prompt_words[1] <= 16'd0;
      prompt_words[2] <= 16'd0;
      prompt_words[3] <= 16'd0;
    end else begin
      if (prompt_valid && prompt_ready) begin
        prompt_words[prompt_count] <= prompt_token;
        prompt_count <= prompt_count + 3'd1;
      end
      if (start && !run_active && !token_valid_q) begin
        if (prompt_count == 3'd4)
          run_active <= 1'b1;
        else begin
          error_q <= 1'b1;
          error_code_q <= 8'h01; // start before four prompt words
        end
      end
      if (run_active && core_wb_cyc && core_wb_stb && wb_accept)
        request_count_q <= request_count_q + 32'd1;
      if (run_active && core_done) begin
        run_active <= 1'b0;
        token_valid_q <= 1'b1;
        token_id_q <= core_token_id;
      end
      if (token_valid_q && token_ready)
        token_valid_q <= 1'b0;
    end
  end
endmodule

`default_nettype wire
