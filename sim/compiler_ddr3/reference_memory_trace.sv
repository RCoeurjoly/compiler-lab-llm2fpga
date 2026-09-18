// Test-only observer for the single-outstanding accelerator memory boundary.
module reference_memory_trace (
  input wire clk,
  input wire reset,
  input wire request_accept,
  input wire response_valid,
  input wire [31:0] request_addr,
  input wire [127:0] response_data
);
  string trace_path;
  integer trace_file;
  reg [63:0] requests = 0, responses = 0;
  reg [31:0] pending_addr = 0;
  initial begin
    if (!$value$plusargs("TRACE_FILE=%s", trace_path))
      $fatal(1, "FAIL: reference trace requires TRACE_FILE");
    trace_file = $fopen(trace_path, "w");
    if (!trace_file) $fatal(1, "FAIL: cannot open reference trace");
  end
  always @(posedge clk) begin
    if (reset) begin
      requests <= 0;
      responses <= 0;
      pending_addr <= 0;
    end else begin
      if (request_accept) begin
        if (requests != responses)
          $fatal(1, "FAIL: overlapping reference request");
        $fdisplay(trace_file, "Q %0d %08h", requests, request_addr);
        pending_addr <= request_addr;
        requests <= requests + 1;
      end
      if (response_valid) begin
        if (requests != responses + 1)
          $fatal(1, "FAIL: unmatched reference response");
        $fdisplay(trace_file, "R %0d %08h %032h", responses, pending_addr, response_data);
        responses <= responses + 1;
      end
    end
  end
  final begin
    if (trace_file) $fclose(trace_file);
  end
endmodule
