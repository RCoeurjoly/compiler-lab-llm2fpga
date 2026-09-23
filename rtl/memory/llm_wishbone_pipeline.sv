`default_nettype none

// Registered Wishbone boundary between the compiler memory arbiter and the
// physical UberDDR3 owner.  The arbiter's logical request protocol is
// unchanged; this stage breaks the long compiler->owner->DDR-controller
// combinational route observed in the full accelerator implementation.
module llm_wishbone_pipeline #(
  parameter int ADDRESS_BITS = 32,
  parameter int DATA_BITS = 128,
  parameter int SEL_BITS = DATA_BITS / 8
) (
  input  logic                   clk,
  input  logic                   rst,
  input  logic                   m_cyc,
  input  logic                   m_stb,
  input  logic                   m_we,
  input  logic [ADDRESS_BITS-1:0] m_addr,
  input  logic [SEL_BITS-1:0]    m_sel,
  output logic                   m_accept,
  output logic                   m_ack,
  output logic                   m_err,
  output logic [DATA_BITS-1:0]   m_rdata,
  output logic                   s_cyc,
  output logic                   s_stb,
  output logic                   s_we,
  output logic [ADDRESS_BITS-1:0] s_addr,
  output logic [SEL_BITS-1:0]    s_sel,
  input  logic                   s_accept,
  input  logic                   s_ack,
  input  logic                   s_err,
  input  logic [DATA_BITS-1:0]   s_rdata
);
  logic pending_q;
  logic accepted_q;
  logic accept_q;
  logic ack_q;
  logic err_q;
  logic [DATA_BITS-1:0] rdata_q;

  assign s_cyc = pending_q;
  assign s_stb = pending_q && !accepted_q;
  assign s_we = pending_q ? m_we_q : 1'b0;
  assign s_addr = addr_q;
  assign s_sel = sel_q;
  assign m_accept = accept_q;
  assign m_ack = ack_q;
  assign m_err = err_q;
  assign m_rdata = rdata_q;

  logic m_we_q;
  logic [ADDRESS_BITS-1:0] addr_q;
  logic [SEL_BITS-1:0] sel_q;

  always_ff @(posedge clk) begin
    if (rst) begin
      pending_q <= 1'b0;
      accepted_q <= 1'b0;
      accept_q <= 1'b0;
      ack_q <= 1'b0;
      err_q <= 1'b0;
      rdata_q <= '0;
      m_we_q <= 1'b0;
      addr_q <= '0;
      sel_q <= '0;
    end else begin
      accept_q <= 1'b0;
      ack_q <= 1'b0;
      err_q <= 1'b0;
      if (!pending_q) begin
        if (m_cyc && m_stb) begin
          pending_q <= 1'b1;
          accepted_q <= 1'b0;
          m_we_q <= m_we;
          addr_q <= m_addr;
          sel_q <= m_sel;
        end
      end else if (!accepted_q) begin
        if (s_accept) begin
          accepted_q <= 1'b1;
          accept_q <= 1'b1;
        end
      end else if (s_ack || s_err) begin
        pending_q <= 1'b0;
        accepted_q <= 1'b0;
        ack_q <= s_ack;
        err_q <= s_err;
        rdata_q <= s_rdata;
      end
    end
  end
endmodule

`default_nettype wire
