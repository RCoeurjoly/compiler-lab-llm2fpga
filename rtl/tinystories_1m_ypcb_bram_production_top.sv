`timescale 1ns/1ps

// JTAG-controlled YPCB top for the compiler-generated BRAM production kernel.
// Model memories are initialized by the bitstream; the JTAG CSR supplies the
// start/reset/read-token control plane without introducing DDR3 or PCIe.
module tinystories_1m_ypcb_bram_production_top (
    input wire clk,
    output wire [2:0] led
);
  wire start, valid, reset, done;
  wire [0:0] token_index;
  wire [15:0] token_id;
  wire [63:0] response_word;
  wire csr_reset;
  wire csr_done = done;
  wire csr_valid = valid;

  tinystories_1m_jtag_csr csr (
      .sys_clk(clk), .sys_rst(1'b0), .core_start(start), .core_reset(csr_reset),
      .core_valid(valid), .core_token_index(token_index),
      .core_token_id(token_id), .core_done(csr_done),
      .response_word(response_word));
  assign reset = csr_reset;
  main core (
      .clk(clk),
      .reset(reset),
      .start(start),
      .valid(csr_valid),
      .token_index(token_index),
      .token_id(token_id),
      .done(done));
  assign led = {done, valid, clk};
endmodule
