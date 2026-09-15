`timescale 1ns/1ps

// Bounded integration-pressure shell.  It drives the audited adapter with a
// deterministic sequential address stream and models only the client-side
// controller handshake; it is not a DDR3 model and makes no functional claim.
module ddr3_controller_pressure_probe #(
  parameter int REQUESTS = 256,
  parameter int ADDRESS_WIDTH = 32
) (
  input  logic clk,
  input  logic rst,
  input  logic start,
  output logic done,
  output logic [31:0] responses,
  output logic wb_cyc,
  output logic wb_stb,
  output logic wb_we,
  output logic [ADDRESS_WIDTH-1:0] wb_addr,
  output logic [15:0] wb_sel,
  input  logic wb_accept,
  input  logic wb_ack,
  input  logic wb_err,
  input  logic [127:0] wb_rdata
);
  logic req_valid;
  logic resp_valid;
  logic resp_error;
  logic [31:0] resp_rdata;
  logic [31:0] issued;
  logic active;

  rc_ddr3_adapter adapter (
    .clk(clk), .rst(rst), .req_valid(req_valid), .req_write(1'b0),
    .req_byte_address(issued << 4),
    .resp_valid(resp_valid), .resp_error(resp_error), .resp_rdata(resp_rdata),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_we(wb_we), .wb_addr(wb_addr),
    .wb_sel(wb_sel), .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err),
    .wb_rdata(wb_rdata)
  );

  assign req_valid = active && issued < REQUESTS;

  always_ff @(posedge clk) begin
    if (rst) begin
      active <= 1'b0;
      issued <= '0;
      responses <= '0;
      done <= 1'b0;
    end else begin
      done <= 1'b0;
      if (start && !active) begin
        active <= 1'b1;
        issued <= '0;
        responses <= '0;
      end else if (active && resp_valid) begin
        responses <= responses + 1'b1;
        if (responses + 1'b1 == REQUESTS) begin
          active <= 1'b0;
          done <= 1'b1;
        end else begin
          issued <= issued + 1'b1;
        end
      end
    end
  end
endmodule
