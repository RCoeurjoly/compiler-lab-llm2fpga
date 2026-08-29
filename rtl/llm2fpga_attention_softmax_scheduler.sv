`timescale 1ns/1ps
// Serialize compiler tensor<16x32xi32> storage through one softmax row core.
module llm2fpga_attention_softmax_scheduler #(
    parameter EXP_FILE = "gptneo_exp.mem"
) (
    input wire clk, input wire rst, input wire start,
    input wire [4:0] position,
    input wire [16*32*32-1:0] scores,
    output reg done,
    output reg [16*32*21-1:0] probabilities,
    output wire busy
);
  localparam IDLE=3'd0, START=3'd1, SEND=3'd2, WAIT=3'd3, FINAL=3'd4;
  reg [2:0] state; reg [3:0] head; reg [5:0] key; reg ack; wire core_ready, core_out_valid;
  reg [4:0] core_index; reg [20:0] core_probability; wire core_busy;
  wire signed [31:0] core_score = scores[(head*32+key)*32 +: 32];
  wire core_start = (state == START);
  wire core_valid = (state == SEND) && core_ready;
  wire core_out_ready = ack;
  gptneo_softmax_only #(.TMAX(32),.EXP_FILE(EXP_FILE)) core(
    .clk(clk),.rst(rst),.start(core_start),.position(position),.in_valid(core_valid),.in_ready(core_ready),.in_score(core_score),
    .out_valid(core_out_valid),.out_ready(core_out_ready),.out_index(core_index),.out_probability(core_probability),.busy(core_busy));
  assign busy = (state != IDLE);
  always @(posedge clk) begin
    done<=0;
    if (rst) begin state<=IDLE; head<=0; key<=0; ack<=0; probabilities<=0; end
    else case(state)
      IDLE: if(start) begin head<=0; key<=0; state<=START; end
      START: state<=SEND;
      SEND: begin
        if (core_ready) begin if (key==position) begin key<=0; state<=WAIT; end else key<=key+1'b1; end
      end
      WAIT: begin
        if(core_out_valid && !ack) begin
        // The row core registers probability while advancing its index, so
        // the value observed for index N>0 belongs to slot N-1.
        if (core_index == 0)
          probabilities[(head*32)*21 +: 21] <= core_probability;
        else
          probabilities[(head*32+core_index-1)*21 +: 21] <= core_probability;
          ack<=1;
        end else if (ack) begin
          ack<=0;
          if (core_index==position) begin
            // The final probability is produced on the edge that accepts
            // the last prior value; capture it one cycle later in FINAL.
            state<=FINAL;
          end
        end
      end
      FINAL: begin
        probabilities[(head*32+position)*21 +: 21] <= core_probability;
        if (head==15) begin done<=1; state<=IDLE; end
        else begin head<=head+1'b1; key<=0; state<=START; end
      end
    endcase
  end
endmodule
