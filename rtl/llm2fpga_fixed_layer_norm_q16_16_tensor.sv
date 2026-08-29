`timescale 1ns/1ps

// Packed compiler ABI for fixed LayerNorm. Each tensor<64xi32> is represented
// as 64 little-endian 32-bit lanes in a packed vector.
module llm2fpga_fixed_layer_norm_q16_16_tensor #(
    parameter integer D = 64
) (
    input  wire clk, input wire rst, input wire start,
    input  wire [D*32-1:0] input_values,
    input  wire [D*32-1:0] gamma_values,
    input  wire [D*32-1:0] beta_values,
    output reg done, output wire busy,
    output reg [D*32-1:0] output_values
);
  localparam LOAD=2'd0, START=2'd1, RUN=2'd2;
  reg [1:0] state;
  reg [6:0] load_index;
  reg armed;
  wire core_in_ready, core_out_valid;
  wire [5:0] core_out_index;
  wire signed [31:0] core_out_y;
  wire core_busy;
  wire core_start = (state == START);
  wire core_in_valid = (state == LOAD) && armed && (load_index < D) && core_in_ready;
  wire signed [31:0] core_x = input_values[load_index*32 +: 32];
  wire signed [31:0] core_gamma = gamma_values[load_index*32 +: 32];
  wire signed [31:0] core_beta = beta_values[load_index*32 +: 32];

  gptneo_layernorm #(.D(D)) core (
      .clk(clk), .rst(rst), .in_valid(core_in_valid), .in_ready(core_in_ready),
      .in_x(core_x), .in_gamma(core_gamma), .in_beta(core_beta),
      .start(core_start), .out_valid(core_out_valid), .out_ready(1'b1),
      .out_index(core_out_index), .out_y(core_out_y), .busy(core_busy),
      .debug_status()
  );

  assign busy = (state != LOAD) || (load_index != 0);
  always @(posedge clk) begin
    done <= 1'b0;
    if (rst) begin
      state <= LOAD; load_index <= 0; armed <= 0; output_values <= 0;
    end else begin
      case (state)
        LOAD: begin
          // A command start arms the stable packed tensors.  Loading is then
          // deterministic and the core launches immediately after lane D-1.
          if (start && load_index == 0) armed <= 1'b1;
          if (armed && load_index == D) state <= START;
          else if (core_in_valid) load_index <= load_index + 1'b1;
        end
        START: begin state <= RUN; end
        RUN: if (core_out_valid) begin
          output_values[core_out_index*32 +: 32] <= core_out_y;
          if (core_out_index == D-1) begin
            done <= 1'b1; state <= LOAD; load_index <= 0;
          end
        end
        default: state <= LOAD;
      endcase
    end
  end
endmodule
