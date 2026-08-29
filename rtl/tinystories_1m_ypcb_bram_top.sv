`timescale 1ns/1ps

// BRAM-only YPCB shell for the compiler-generated TinyStories-1M core.
//
// The core is intentionally a separate compilation boundary: the compiler
// must provide llm2fpga_tinystories_1m_core with the kev-gpt sequencer-side
// handshake below. This shell owns board reset/LED plumbing and reserves the
// BRAM-only contract; external memory and host-link paths are intentionally
// absent from this milestone shell.
module tinystories_1m_ypcb_bram_top #(
    parameter integer BRAM_ONLY = 1
) (
    input  wire SYS_CLK,
    input  wire SYS_RSTN,
    output wire [2:0] LED
);
  localparam integer BRAM_ONLY_CONTRACT = 1;
  wire reset = !SYS_RSTN;

  wire prompt_valid, prompt_ready, start;
  wire [15:0] prompt_token;
  wire [5:0] requested_tokens;
  wire token_valid, token_ready;
  wire [15:0] token_id;
  wire busy, error;
  wire [7:0] error_code;
  wire [62:0] debug_status;
  wire [95:0] debug_embedding, debug_layernorm;

  // Temporary structural tie-offs keep this shell elaboratable before the
  // kev-gpt packet controller is instantiated. They are deliberately not an
  // inference implementation; the controller adapter is the next step.
  assign prompt_valid = 1'b0;
  assign prompt_token = 16'd0;
  assign start = 1'b0;
  assign requested_tokens = 6'd0;
  assign token_ready = 1'b1;

  // The board transport/controller is supplied by the selected kev-gpt shell
  // (self-test or interactive). Keeping these as explicit ports makes the
  // compiler-core ABI testable without pretending the compiler has generated
  // a transport implementation.
  llm2fpga_tinystories_1m_core #(.BRAM_ONLY(BRAM_ONLY_CONTRACT)) core (
      .clk(SYS_CLK), .rst(reset), .clear(1'b0),
      .prompt_valid(prompt_valid), .prompt_ready(prompt_ready),
      .prompt_token(prompt_token), .start(start),
      .requested_tokens(requested_tokens),
      .token_valid(token_valid), .token_ready(token_ready),
      .token_id(token_id), .busy(busy), .error(error),
      .error_code(error_code), .debug_status(debug_status),
      .debug_embedding(debug_embedding), .debug_layernorm(debug_layernorm));

  assign LED = {error, busy, SYS_CLK};
endmodule
