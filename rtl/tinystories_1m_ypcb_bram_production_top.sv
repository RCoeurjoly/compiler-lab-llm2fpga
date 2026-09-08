`timescale 1ns/1ps

// JTAG-controlled YPCB top for the compiler-generated BRAM production kernel.
// Model memories are initialized by the bitstream; the JTAG CSR supplies the
// start/reset/read-token control plane without introducing DDR3 or PCIe.
module tinystories_1m_ypcb_bram_production_top (
    input wire clk,
    output wire [2:0] led
`ifdef BSCAN_SIM
    ,input wire scan_drck, input wire scan_reset, input wire scan_sel,
    input wire scan_shift, input wire scan_capture, input wire scan_update,
    input wire scan_tdi, output wire scan_tdo
`endif
);
  wire start, valid, reset, done;
  wire [0:0] token_index;
  (* keep *) wire [15:0] token_id;
  wire [15:0] prompt_0, prompt_1, prompt_2, prompt_3;
  (* keep *) wire [63:0] response_word;
  wire csr_reset;
  wire csr_done = done;
  wire csr_valid = valid;
  // All immutable source memories are initialized by the configured image's
  // synthesis-time $readmemh initializers.  There is no runtime weight load
  // transaction in this BRAM-only milestone.
  wire model_init_done = 1'b1;
  // BSCAN reset only resets the scan clock domain.  The CSR shadow state is
  // in the board clock domain, so give it a deterministic FPGA power-up
  // reset before accepting the first JTAG command.  The initial value maps
  // to the normal Xilinx flip-flop INIT bit and needs no board reset pin.
  (* keep *) reg [1:0] powerup_reset = 2'b11;
  always @(posedge clk) powerup_reset <= {powerup_reset[0], 1'b0};
  wire sys_reset = powerup_reset[1];

  tinystories_1m_jtag_csr csr (
      .sys_clk(clk), .sys_rst(sys_reset), .core_start(start), .core_reset(csr_reset),
      .core_valid(valid), .core_token_index(token_index),
      .prompt_0(prompt_0), .prompt_1(prompt_1), .prompt_2(prompt_2), .prompt_3(prompt_3),
      .core_token_id(token_id), .core_done(csr_done),
      .model_init_done(model_init_done)
`ifdef BSCAN_SIM
      , .scan_drck(scan_drck), .scan_reset(scan_reset), .scan_sel(scan_sel),
      .scan_shift(scan_shift), .scan_capture(scan_capture), .scan_update(scan_update),
      .scan_tdi(scan_tdi), .scan_tdo(scan_tdo)
`endif
      ,
      .response_word(response_word));
  assign reset = csr_reset;
  (* keep_hierarchy *) main core (
      .clk(clk),
      .reset(reset),
      .start(start),
      .valid(csr_valid),
      .prompt_0(prompt_0), .prompt_1(prompt_1), .prompt_2(prompt_2), .prompt_3(prompt_3),
      .token_index(token_index),
      .token_id(token_id),
      .done(done));
  assign led = {done, valid, clk};
endmodule
