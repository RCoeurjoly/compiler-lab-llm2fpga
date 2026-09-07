`timescale 1ns/1ps

// Resource/timing top for the compiler-generated BRAM production kernel.
// The transport-facing token shell is a separate integration milestone; this
// top intentionally drives the generated kernel autonomously so P&R measures
// the actual compiler datapath and all model memories.
module tinystories_1m_ypcb_bram_production_top (
    input wire clk,
    output wire [2:0] led
);
  wire done;
  main core (
      .clk(clk),
      .reset(1'b0),
      .start(1'b1),
      .valid(1'b1),
      .done(done));
  assign led = {done, 1'b0, clk};
endmodule
