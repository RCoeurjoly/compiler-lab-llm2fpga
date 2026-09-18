// Bind only into the abstract reference harness, never production RTL.
bind command_integration_wrapper reference_memory_trace memory_trace (
  .clk(clk), .reset(reset),
  .request_accept(wb_cyc && wb_stb && wb_accept),
  .response_valid(wb_ack), .request_addr(wb_addr),
  .response_data(wb_rdata)
);
