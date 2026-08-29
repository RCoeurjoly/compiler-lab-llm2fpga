// Structural contract for the compiler-generated TinyStories-1M core.
// This declaration is intentionally a blackbox: it makes shell elaboration
// deterministic without pretending that token-level inference exists yet.
(* blackbox *)
module llm2fpga_tinystories_1m_core #(
    parameter integer BRAM_ONLY = 1
) (
    input wire clk, input wire rst, input wire clear,
    input wire prompt_valid, output wire prompt_ready,
    input wire [15:0] prompt_token, input wire start,
    input wire [5:0] requested_tokens,
    output wire token_valid, input wire token_ready,
    output wire [15:0] token_id, output wire busy, output wire error,
    output wire [7:0] error_code,
    output wire [62:0] debug_status,
    output wire [95:0] debug_embedding,
    output wire [95:0] debug_layernorm
);
endmodule
