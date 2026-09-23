module resetful_reference #(
    parameter WIDTH = 32,
    parameter SIZE = 16,
    parameter IDX_SIZE = 4,
    parameter INIT_FILE = "",
    parameter EXT_BASE_ADDR = 0
) (
   input wire logic clk,
   input wire logic reset,
   input wire logic [IDX_SIZE-1:0] addr0,
   input wire logic content_en,
   output logic done,
   output logic [WIDTH-1:0] read_data,
   input wire logic [WIDTH-1:0] write_data,
   input wire logic write_en,
   output wire ext_req_valid,
   input wire ext_req_ready,
   output wire [31:0] ext_req_addr,
   input wire ext_rsp_valid,
   input wire [63:0] ext_rsp_data
);
  logic pending;
  logic request_queued;
  logic [31:0] queued_address;
  logic [IDX_SIZE-1:0] request_index;
  // A DDR3 response supplies one 64-bit lane.  Narrow elements may start at
  // any byte offset within that lane, so retain the request offset until the
  // one-cycle response arrives.
  logic [2:0] response_byte_offset;
  // Emit one response pulse for every enabled read, including repeated
  // same-address reads, matching native generated seq_mem semantics.
  // Cut the measured context-token/scheduler/address-to-arbiter timing path.
  // Once captured, a read is irrevocable until accepted (or reset). Keep its
  // identity and byte offset with it, not with the client's changing inputs.
  assign ext_req_valid = request_queued;
  assign ext_req_addr = queued_address;
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      request_queued <= 1'b0;
      queued_address <= '0;
      request_index <= '0;
      response_byte_offset <= '0;
      done <= 1'b0;
      read_data <= '0;
    end else begin
      done <= pending && ext_rsp_valid;
      // Sample the payload whenever the local slot is empty. On the enqueue
      // edge both payload and valid capture the same client inputs; queued/
      // pending then freeze the payload until the transaction has completed.
      // Keep the address mux and duplicate comparison out of the wide
      // payload-register enable cone measured in the integrated design.
      if (!pending && !request_queued) begin
        queued_address <= EXT_BASE_ADDR + (addr0 * (WIDTH / 8));
        request_index <= addr0;
      end
      if (pending && ext_rsp_valid) begin
        read_data <= ext_rsp_data >> (response_byte_offset * 8);
        pending <= 1'b0;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
        request_queued <= 1'b0;
        response_byte_offset <= ext_req_addr[2:0];
      end else if (content_en && !write_en && !pending && !request_queued &&
                   1'b1) begin
        request_queued <= 1'b1;
      end
    end
  end
endmodule
