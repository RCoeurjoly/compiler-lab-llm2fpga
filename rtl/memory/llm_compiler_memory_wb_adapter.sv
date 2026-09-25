`default_nettype none

// Transport-only adapter for compiler-generated memory ports.
//
// The generated RC exposes one read request per logical immutable memory.  The
// adapter keeps those ports independent at the compiler boundary, then uses
// the validated single-outstanding arbiter to present one 128-bit Wishbone
// read port to UberDDR3.  It contains no model arithmetic or copied
// accelerator RTL.
module llm_compiler_memory_wb_adapter #(
  parameter int PORTS = 55,
  parameter int ADDRESS_BITS = 32,
  parameter int DATA_BITS = 64,
  parameter int WB_DATA_BITS = 128,
  // Optional compiler-owned timing boundary. The default preserves the
  // validated direct handshake; RC shells can register requests before the
  // arbitration fan-in without changing the external ABI.
  parameter bit REGISTER_REQUESTS = 1'b0
) (
  input  logic clk,
  input  logic rst,
  input  logic [PORTS-1:0] req_valid,
  output logic [PORTS-1:0] req_ready,
  input  logic [PORTS*ADDRESS_BITS-1:0] req_addr,
  output logic [PORTS-1:0] rsp_valid,
  output logic [PORTS*DATA_BITS-1:0] rsp_data,
  output logic wb_cyc,
  output logic wb_stb,
  output logic [ADDRESS_BITS-1:0] wb_addr,
  output logic [WB_DATA_BITS/8-1:0] wb_sel,
  input logic wb_accept,
  input logic wb_ack,
  input logic wb_err,
  input logic [WB_DATA_BITS-1:0] wb_rdata
);
  logic [PORTS-1:0] arb_req_valid;
  logic [PORTS-1:0] arb_req_ready;
  logic [PORTS*ADDRESS_BITS-1:0] arb_req_addr;

  generate
    if (!REGISTER_REQUESTS) begin : gen_direct_requests
      assign arb_req_valid = req_valid;
      assign arb_req_addr = req_addr;
      assign req_ready = arb_req_ready;
    end else begin : gen_registered_requests
      logic [PORTS-1:0] pending_valid_q;
      logic [PORTS*ADDRESS_BITS-1:0] pending_addr_q;

      assign arb_req_valid = pending_valid_q;
      assign arb_req_addr = pending_addr_q;
      // A client may enqueue one request per port. The selected request is
      // retired on the arbiter's CAPTURE handshake; a new request is accepted
      // on a later cycle, keeping the boundary fully synchronous.
      assign req_ready = ~pending_valid_q;

      always_ff @(posedge clk) begin
        if (rst) begin
          pending_valid_q <= '0;
          pending_addr_q <= '0;
        end else begin
          pending_valid_q <=
            (pending_valid_q & ~arb_req_ready) | (req_valid & req_ready);
          for (int i = 0; i < PORTS; i = i + 1)
            if (req_valid[i] && req_ready[i])
              pending_addr_q[i*ADDRESS_BITS +: ADDRESS_BITS] <=
                req_addr[i*ADDRESS_BITS +: ADDRESS_BITS];
        end
      end
    end
  endgenerate

  llm_external_memory_arbiter #(
    .PORTS(PORTS),
    .ADDRESS_BITS(ADDRESS_BITS),
    .DATA_BITS(DATA_BITS),
    .WB_DATA_BITS(WB_DATA_BITS)
  ) arbiter (
    .clk(clk), .rst(rst),
    .req_valid(arb_req_valid), .req_ready(arb_req_ready), .req_addr(arb_req_addr),
    .rsp_valid(rsp_valid), .rsp_data(rsp_data),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_addr(wb_addr), .wb_sel(wb_sel),
    .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err),
    .wb_rdata(wb_rdata)
  );
endmodule

`default_nettype wire
