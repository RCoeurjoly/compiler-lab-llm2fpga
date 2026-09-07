`timescale 1ns/1ps

// Minimal YPCB JTAG CSR bridge for the compiler-generated BRAM kernel.
//
// The bridge deliberately uses a fixed 64-bit transaction rather than the
// kev-gpt packet stream: this keeps the compiler milestone small and makes the
// board ABI independently testable.  A transaction is shifted LSB-first:
//   command[63:60] op, command[5:4] prompt index, command[15:0] value.
//   1 = load prompt word, 2 = start, 3 = status, 4 = select/read token.
// Responses are captured from response_word with status in [63:60] and the
// selected token in [15:0].  Model weights remain immutable BRAM init data.
module tinystories_1m_jtag_csr #(
    parameter integer PROMPT_WORDS = 4
) (
    input  wire        sys_clk,
    input  wire        sys_rst,
    output reg         core_start,
    output reg         core_reset,
    output wire        core_valid,
    output reg  [0:0]  core_token_index,
    input  wire [15:0] core_token_id,
    input  wire        core_done,
    output reg  [63:0] response_word
`ifdef BSCAN_SIM
    ,input wire        scan_drck,
    input  wire        scan_reset,
    input  wire        scan_sel,
    input  wire        scan_shift,
    input  wire        scan_capture,
    input  wire        scan_update,
    input  wire        scan_tdi,
    output wire        scan_tdo
`endif
);
`ifndef BSCAN_SIM
  wire scan_drck, scan_reset, scan_sel, scan_shift, scan_capture, scan_update;
  wire scan_tdi, scan_tdo;
  BSCANE2 #(.JTAG_CHAIN(1)) bscan (
      .CAPTURE(scan_capture), .DRCK(scan_drck), .RESET(scan_reset),
      .RUNTEST(), .SEL(scan_sel), .SHIFT(scan_shift), .TCK(),
      .TDI(scan_tdi), .TDO(scan_tdo), .UPDATE(scan_update));
`endif

  reg [63:0] scan_shift_reg;
  /* verilator lint_off UNUSEDSIGNAL */
  reg [63:0] command_word;
  /* verilator lint_on UNUSEDSIGNAL */
  reg        command_toggle;
  reg        command_toggle_q1, command_toggle_q2;
  reg        run_active;
  reg [15:0] prompt_words [0:PROMPT_WORDS-1];
  integer i;

  assign core_valid = run_active;
  assign scan_tdo = scan_shift_reg[0];

  // JTAG clock domain: capture a response and shift/update one command.
  always @(posedge scan_drck) begin
    if (scan_reset) begin
      scan_shift_reg <= 64'd0;
      command_word <= 64'd0;
      command_toggle <= 1'b0;
    end else if (scan_capture) begin
      scan_shift_reg <= response_word;
    end else if (scan_sel && scan_shift) begin
      scan_shift_reg <= {scan_tdi, scan_shift_reg[63:1]};
    end else if (scan_update) begin
      command_word <= scan_shift_reg;
      command_toggle <= ~command_toggle;
    end
  end

  // System clock domain: synchronize the update event and execute the CSR.
  always @(posedge sys_clk) begin
    if (sys_rst) begin
      command_toggle_q1 <= 1'b0;
      command_toggle_q2 <= 1'b0;
      core_start <= 1'b0;
      core_reset <= 1'b0;
      core_token_index <= 1'b0;
      run_active <= 1'b0;
      response_word <= 64'd0;
      for (i = 0; i < PROMPT_WORDS; i = i + 1) prompt_words[i] <= 16'd0;
    end else begin
      command_toggle_q1 <= command_toggle;
      command_toggle_q2 <= command_toggle_q1;
      core_start <= 1'b0;
      core_reset <= 1'b0;
      if (core_done) begin
        run_active <= 1'b0;
        response_word <= {4'h0, 12'd0, 16'd0, 16'd0, 16'd0};
      end
      if (command_toggle_q2 != command_toggle_q1) begin
        case (command_word[63:60])
          4'h1: begin
            prompt_words[command_word[5:4]] <= command_word[15:0];
            response_word <= {4'h0, 12'd0, 16'd0, 16'd0, command_word[15:0]};
          end
          4'h2: begin
            core_start <= 1'b1;
            run_active <= 1'b1;
            response_word <= {4'h1, 12'd0, 48'd0};
          end
          4'h5: begin
            core_reset <= 1'b1;
            run_active <= 1'b0;
            response_word <= {4'h0, 60'd0};
          end
          4'h3: begin
            response_word <= {4'h2, 10'd0, run_active, core_done, 32'd0, prompt_words[0]};
          end
          4'h4: begin
            core_token_index <= command_word[0];
            response_word <= {4'h0, 12'd0, 16'd0, 16'd0, core_token_id};
          end
          default: response_word <= {4'hf, 60'd0};
        endcase
      end
    end
  end
endmodule
