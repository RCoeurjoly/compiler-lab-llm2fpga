`timescale 1ns/1ps
`default_nettype none

module task6_tinystories_token_collector (
  input  wire         clk,
  input  wire         rst,
  input  wire         clear,
  input  wire         start,
  input  wire         token_valid,
  output wire         token_ready,
  input  wire [15:0]  token_id,
  output logic [5:0]  token_count,
  output logic [511:0] tokens,
  output logic        overflow
);
  assign token_ready = 1'b1;

  always_ff @(posedge clk) begin
    if (rst || clear || start) begin
      token_count <= 6'd0;
      overflow <= 1'b0;
    end else if (token_valid) begin
      if (token_count < 6'd32) begin
        token_count <= token_count + 6'd1;
      end else begin
        overflow <= 1'b1;
      end
    end
  end

  // Payload contents are invalid whenever token_count is zero. Keeping these
  // flops off reset prevents the PCIe reset tree from acquiring 512 sinks;
  // each valid slot is overwritten before token_count exposes it.
  // Decode the slot explicitly.  A variable indexed part-select here creates
  // a 32-way wide mux on the PCIe clock; fixed lanes let synthesis retain the
  // collector as ordinary flops without putting that mux on the timing path.
  always_ff @(posedge clk) begin
    if (token_valid && token_count < 6'd32) begin
      case (token_count)
        6'd0:  tokens[15:0]    <= token_id;
        6'd1:  tokens[31:16]   <= token_id;
        6'd2:  tokens[47:32]   <= token_id;
        6'd3:  tokens[63:48]   <= token_id;
        6'd4:  tokens[79:64]   <= token_id;
        6'd5:  tokens[95:80]   <= token_id;
        6'd6:  tokens[111:96]  <= token_id;
        6'd7:  tokens[127:112] <= token_id;
        6'd8:  tokens[143:128] <= token_id;
        6'd9:  tokens[159:144] <= token_id;
        6'd10: tokens[175:160] <= token_id;
        6'd11: tokens[191:176] <= token_id;
        6'd12: tokens[207:192] <= token_id;
        6'd13: tokens[223:208] <= token_id;
        6'd14: tokens[239:224] <= token_id;
        6'd15: tokens[255:240] <= token_id;
        6'd16: tokens[271:256] <= token_id;
        6'd17: tokens[287:272] <= token_id;
        6'd18: tokens[303:288] <= token_id;
        6'd19: tokens[319:304] <= token_id;
        6'd20: tokens[335:320] <= token_id;
        6'd21: tokens[351:336] <= token_id;
        6'd22: tokens[367:352] <= token_id;
        6'd23: tokens[383:368] <= token_id;
        6'd24: tokens[399:384] <= token_id;
        6'd25: tokens[415:400] <= token_id;
        6'd26: tokens[431:416] <= token_id;
        6'd27: tokens[447:432] <= token_id;
        6'd28: tokens[463:448] <= token_id;
        6'd29: tokens[479:464] <= token_id;
        6'd30: tokens[495:480] <= token_id;
        6'd31: tokens[511:496] <= token_id;
        default: ;
      endcase
    end
  end
endmodule

`default_nettype wire
