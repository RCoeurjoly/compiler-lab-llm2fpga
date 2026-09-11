// CSR-only physical BSCAN diagnostic.  This deliberately omits the
// TinyStories core so CSR response timing can be qualified independently.
module tinystories_bscan_csr_sentinel_top (
    input  wire       clk,
    output wire [2:0] led
);
  wire core_start, core_reset, core_valid;
  wire [0:0] core_token_index;
  wire [15:0] prompt_0, prompt_1, prompt_2, prompt_3;
  wire [63:0] response_word;
  wire tap_reset;

  // Keep the core side inert but observable through the normal CSR ABI.
  wire [15:0] core_token_id = 16'd11;
  wire core_done = 1'b0;
  wire model_init_done = 1'b1;
  wire sys_rst = 1'b0;

  tinystories_1m_jtag_csr csr (
      .sys_clk(clk), .sys_rst(sys_rst), .core_start(core_start),
      .core_reset(core_reset), .core_valid(core_valid),
      .core_token_index(core_token_index), .prompt_0(prompt_0),
      .prompt_1(prompt_1), .prompt_2(prompt_2), .prompt_3(prompt_3),
      .core_token_id(core_token_id), .core_done(core_done),
      .model_init_done(model_init_done), .response_word(response_word),
      .tap_reset(tap_reset));

  assign led = {core_valid, core_start, tap_reset};
endmodule
