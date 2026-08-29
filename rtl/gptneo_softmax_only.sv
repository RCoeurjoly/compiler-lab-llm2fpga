`timescale 1ns/1ps

// Baseline compiler-facing softmax component.  It consumes one causal score
// row (Q8.8 codes), applies the authenticated Q1.20 exponential LUT, and
// emits probabilities.  The division is intentionally behavioral for this
// first ABI slice; replace it with the validated iterative divider after
// functional equivalence is established.
module gptneo_softmax_only #(
    parameter integer TMAX = 32,
    parameter EXP_FILE = "gptneo_exp.mem"
) (
    input wire clk, input wire rst,
    input wire start,
    input wire [4:0] position,
    input wire in_valid,
    output wire in_ready,
    input wire signed [31:0] in_score,
    output reg out_valid,
    input wire out_ready,
    output reg [4:0] out_index,
    output reg [20:0] out_probability,
    output wire busy
);
    localparam [1:0] IDLE=2'd0, LOAD=2'd1, OUT=2'd2;
    reg [1:0] state;
    reg [4:0] count;
    reg [4:0] row_position;
    reg signed [31:0] score_mem [0:TMAX-1];
    reg [20:0] exp_mem [0:TMAX-1];
    reg [63:0] denominator;
    reg [20:0] exp_lut [0:4095];
    integer i;
    integer signed maximum;
    integer signed delta;
    integer signed current_score;
    integer lut_index;
    initial $readmemh(EXP_FILE, exp_lut);

    assign in_ready = (state == LOAD);
    assign busy = (state != IDLE);

    always @(posedge clk) begin
        out_valid <= 1'b0;
        if (rst) begin
            state <= IDLE; count <= 0; out_index <= 0;
            denominator <= 0; out_probability <= 0;
        end else begin
            case (state)
              IDLE: if (start) begin
                  count <= 0; row_position <= position; state <= LOAD;
              end
              LOAD: if (in_valid) begin
                  score_mem[count] <= in_score;
                  if (count == row_position || count == TMAX-1) begin
                      maximum = (count == 0) ? in_score : score_mem[0];
                      for (i = 1; i < TMAX; i = i + 1)
                        if (i <= count) begin
                            current_score = (i == count) ? in_score : score_mem[i];
                            if (current_score > maximum) maximum = current_score;
                        end
                      denominator = 0;
                      for (i = 0; i < TMAX; i = i + 1) begin
                          if (i <= count) begin
                              current_score = (i == count) ? in_score : score_mem[i];
                              delta = current_score - maximum;
                              if (delta >= 0) lut_index = 4095;
                              else if (delta < -4096) lut_index = 0;
                              else lut_index = 4096 + delta;
                              exp_mem[i] <= (delta >= 0) ? 21'd1048576 : exp_lut[lut_index];
                              denominator = denominator + ((delta >= 0) ? 21'd1048576 : exp_lut[lut_index]);
                          end else exp_mem[i] <= 0;
                      end
                      out_index <= 0; state <= OUT;
                  end else count <= count + 1'b1;
              end
              OUT: begin
                  out_valid <= 1'b1;
                  out_probability <= (denominator == 0) ? 0 : ((exp_mem[out_index] * (64'd1 << 20)) / denominator);
                  if (out_ready) begin
                      if (out_index == row_position) state <= IDLE;
                      else out_index <= out_index + 1'b1;
                  end
              end
            endcase
        end
    end
endmodule
