module compiler_ddr3_cpp_wrapper (
  input logic clk, input logic reset, input logic start, input logic valid,
  input logic [15:0] prompt_0, prompt_1, prompt_2, prompt_3,
  output logic done, output logic [15:0] token_id,
  output logic [63:0] wb_req_count, output logic [63:0] wb_rsp_count
);
  localparam integer PORTS = 240;
  localparam integer LINES = 258545;
  wire [PORTS-1:0] req_valid, req_ready, rsp_valid;
  wire [PORTS*32-1:0] req_addr;
  wire [PORTS*64-1:0] rsp_data;
  wire wb_cyc, wb_stb, wb_accept;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  logic wb_ack = 0, wb_err = 0;
  logic [127:0] wb_rdata = 0;
  logic wb_pending = 0;
  logic [31:0] wb_pending_addr = 0;
  logic [127:0] image [0:LINES-1];
  initial $readmemh("/tmp/compiler-ddr3-current.2Z9Mo4/tinystories-ddr3-lines.hex", image);

  main dut (
    .start(start), .valid(valid), .token_index(1'b0),
    .prompt_0(prompt_0), .prompt_1(prompt_1), .prompt_2(prompt_2), .prompt_3(prompt_3),
    .done(done), .token_id(token_id), .clk(clk), .reset(reset),
    .ext_mem_req_valid(req_valid), .ext_mem_req_ready(req_ready),
    .ext_mem_req_addr(req_addr), .ext_mem_rsp_valid(rsp_valid),
    .ext_mem_rsp_data(rsp_data)
  );
  llm_external_memory_arbiter #(.PORTS(PORTS)) arbiter (
    .clk(clk), .rst(reset), .req_valid(req_valid), .req_ready(req_ready),
    .req_addr(req_addr), .rsp_valid(rsp_valid), .rsp_data(rsp_data),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_addr(wb_addr), .wb_sel(wb_sel),
    .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata)
  );
  assign wb_accept = wb_cyc && wb_stb;
  always_ff @(posedge clk) begin
    if (reset) begin
      wb_ack <= 1'b0;
      wb_pending <= 1'b0;
      wb_req_count <= '0;
      wb_rsp_count <= '0;
    end else begin
      wb_ack <= wb_pending;
      if (wb_pending) wb_rdata <= image[wb_pending_addr];
      wb_pending <= wb_cyc && wb_stb;
      if (wb_cyc && wb_stb) begin
        wb_pending_addr <= wb_addr;
        wb_req_count <= wb_req_count + 1'b1;
      end
      if (wb_ack) wb_rsp_count <= wb_rsp_count + 1'b1;
    end
  end
endmodule
