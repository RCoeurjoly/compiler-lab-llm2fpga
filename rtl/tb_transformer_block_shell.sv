`timescale 1ns/1ps
module tb_transformer_block_shell;
 reg clk=0,rst=1,start=0; reg [4:0] position=0;
 reg [2047:0] input_q16=0,ln1_gamma=0,ln1_beta=0,ln2_gamma=0,ln2_beta=0;
 reg [65535:0] keys_q16=0,values_q16=0; reg [1535:0] q_in_scales=0,q_out_scales=0,k_in_scales=0,k_out_scales=0,v_in_scales=0,v_out_scales=0;
 reg [32767:0] q_weights=0,k_weights=0,v_weights=0; reg [1535:0] q_weight_scales=0,k_weight_scales=0,v_weight_scales=0; reg [2047:0] q_bias=0,k_bias=0,v_bias=0;
 reg [1535:0] attn_in_scales=0,attn_weight_scales=0,attn_out_scales=0; reg [32767:0] attn_weights=0; reg [2047:0] attn_bias=0;
 reg [1535:0] fc_in_input_scales=0; reg [131071:0] fc_in_weights=0; reg [6143:0] fc_in_weight_scales=0,fc_in_output_scales=0; reg [8191:0] fc_in_bias=0;
 reg [6143:0] fc_out_input_scales=0; reg [131071:0] fc_out_weights=0; reg [1535:0] fc_out_weight_scales=0,fc_out_output_scales=0; reg [2047:0] fc_out_bias=0;
 wire done,busy; wire [2047:0] output_q16;
 llm2fpga_transformer_block_tensor #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem"),.GELU_FILE("/tmp/gptneo_gelu.mem")) dut(.*);
 always #5 clk=~clk;
 initial begin repeat(2) @(posedge clk); rst<=0; repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk); $display("LLM2FPGA_TRANSFORMER_SHELL_LIVENESS_PASS"); $finish; end
endmodule
