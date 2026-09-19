`timescale 1ns/1ps
// A testbench for hand-written temporary diagnostic logic only.
module compiler_ddr3_trace_replay_tb;
  reg clk=0; always #5 clk=~clk;
  reg reset=1, replay_reset=0, calib_complete=1;
  reg [31:0] s_axi_awaddr=0, s_axi_wdata=0, s_axi_araddr=0;
  reg [3:0] s_axi_wstrb=15;
  reg s_axi_awvalid=0, s_axi_wvalid=0, s_axi_bready=0;
  reg s_axi_arvalid=0, s_axi_rready=0;
  wire s_axi_awready, s_axi_wready, s_axi_bvalid, s_axi_arready, s_axi_rvalid;
  wire [1:0] s_axi_bresp, s_axi_rresp;
  wire [31:0] s_axi_rdata;
  wire wb_cyc, wb_stb, wb_we;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  reg wb_stall=1, wb_ack=0, wb_err=0;
  reg [127:0] wb_rdata=0;
`ifdef TEST_OWNER_MUX
  wire replay_cyc, replay_stb, replay_we, replay_stall, replay_ack, replay_err;
  wire [31:0] replay_addr;
  wire [15:0] replay_sel;
  wire [127:0] replay_rdata;
  wire host_ack, host_err;
  compiler_ddr3_trace_replay_csr dut (
    .wb_cyc(replay_cyc), .wb_stb(replay_stb), .wb_we(replay_we), .wb_addr(replay_addr),
    .wb_sel(replay_sel), .wb_stall(replay_stall), .wb_ack(replay_ack), .wb_err(replay_err),
    .wb_rdata(replay_rdata), .*);
  task6_wishbone_owner_mux #(.ADDR_BITS(32), .DATA_BITS(128), .DIRECT_ACCELERATOR_OWNER(1'b0)) mux (
    .clk(clk), .rst(reset), .accelerator_enable(1'b1),
    .host_cyc(1'b0), .host_stb(1'b0), .host_we(1'b0), .host_addr(32'd0),
    .host_write_data(128'd0), .host_sel(16'd0), .host_stall(), .host_ack(host_ack),
    .host_err(host_err), .host_read_data(),
    .accelerator_cyc(replay_cyc), .accelerator_stb(replay_stb), .accelerator_we(replay_we),
    .accelerator_addr(replay_addr), .accelerator_write_data(128'd0), .accelerator_sel(replay_sel),
    .accelerator_stall(replay_stall), .accelerator_ack(replay_ack), .accelerator_err(replay_err),
    .accelerator_read_data(replay_rdata), .memory_cyc(wb_cyc), .memory_stb(wb_stb),
    .memory_we(wb_we), .memory_addr(wb_addr), .memory_write_data(), .memory_sel(wb_sel),
    .memory_stall(wb_stall), .memory_ack(wb_ack), .memory_err(wb_err), .memory_read_data(wb_rdata),
    .owner_active(), .accelerator_owned());
  always @(posedge clk) if(!reset && (host_ack || host_err)) $fatal(1,"owner mux leaked replay response to host");
`else
  compiler_ddr3_trace_replay_csr dut (.*);
`endif
  task tick; @(posedge clk); #1; endtask
  // Split AW from W deliberately; hold BREADY low to catch duplicate writes.
  task write_csr(input [31:0] address, input [31:0] value, input [1:0] response=0,
                 input bit data_first=0);
    if(data_first) begin
      @(negedge clk); s_axi_wdata=value; s_axi_wvalid=1;
      do begin @(posedge clk); end while (!s_axi_wready);
      @(negedge clk); s_axi_wvalid=0;
      repeat(2) tick();
      @(negedge clk); s_axi_awaddr=address; s_axi_awvalid=1;
      do begin @(posedge clk); end while (!s_axi_awready);
      @(negedge clk); s_axi_awvalid=0;
    end else begin
      @(negedge clk); s_axi_awaddr=address; s_axi_awvalid=1;
      do begin @(posedge clk); end while (!s_axi_awready);
      @(negedge clk); s_axi_awvalid=0;
      repeat(2) tick();
      @(negedge clk); s_axi_wdata=value; s_axi_wvalid=1;
      do begin @(posedge clk); end while (!s_axi_wready);
      @(negedge clk); s_axi_wvalid=0;
    end
    while (!s_axi_bvalid) tick();
    repeat(3) begin
      if (!s_axi_bvalid || s_axi_bresp!==response) $fatal(1,"CSR write response/backpressure");
      tick();
    end
    @(negedge clk); s_axi_bready=1;
    tick(); @(negedge clk); s_axi_bready=0;
  endtask
  task read_csr(input [31:0] address, output [31:0] value);
    @(negedge clk); s_axi_araddr=address; s_axi_arvalid=1;
    do begin @(posedge clk); end while (!s_axi_arready);
    @(negedge clk); s_axi_arvalid=0;
    while (!s_axi_rvalid) tick();
    value=s_axi_rdata;
    repeat(3) begin
      if (!s_axi_rvalid || s_axi_rresp || s_axi_rdata!==value) $fatal(1,"CSR read response/backpressure");
      tick();
    end
    @(negedge clk); s_axi_rready=1;
    tick(); @(negedge clk); s_axi_rready=0;
  endtask
  task expect_csr(input [31:0] address, input [31:0] want);
    reg [31:0] got;
    read_csr(address,got);
    if(got!==want) $fatal(1,"CSR %h expected %h got %h",address,want,got);
  endtask
  task stage(input [31:0] address, input [127:0] data);
    write_csr('h910,address);
    write_csr('h914,data[31:0]); write_csr('h918,data[63:32]);
    write_csr('h91c,data[95:64]); write_csr('h920,data[127:96]);
  endtask
  task push(input [31:0] address, input [127:0] data);
    stage(address,data); write_csr('h924,1);
  endtask
  task fresh(input [31:0] count);
    write_csr('h908,2); expect_csr('h928,0); expect_csr('h944,0);
    expect_csr('h934,0); expect_csr('h970,0);
    write_csr('h90c,count);
  endtask
  task request(input [31:0] address);
    while(!wb_stb) tick();
    repeat(4) begin
      if(!wb_cyc || !wb_stb || wb_we || wb_sel!==16'hffff || wb_addr!==address)
        $fatal(1,"request order/stability expected %h got %h",address,wb_addr);
      tick();
    end
    @(negedge clk); wb_stall=0;
    tick(); @(negedge clk); wb_stall=1;
    repeat(3) begin
      if(!wb_cyc || wb_stb) $fatal(1,"single outstanding response association");
      tick();
    end
  endtask
  task respond(input [127:0] data, input bit error=0);
    @(negedge clk); wb_ack=!error; wb_err=error; wb_rdata=data;
    tick(); @(negedge clk); wb_ack=0; wb_err=0;
    repeat(3) tick();
  endtask
  task failed(input [31:0] error_bits);
    expect_csr('h928,3); expect_csr('h944,error_bits);
    if(wb_cyc || wb_stb) $fatal(1,"terminal FAIL issued traffic");
  endtask
  reg [31:0] value;
  integer i;
  localparam [127:0] LANES=128'hffeeddcc_bbaa9988_77665544_33221100;
  initial begin
    repeat(3) tick(); @(negedge clk); reset=0;
    expect_csr('h900,32'h52504c59); expect_csr('h904,1);
    // Exact order includes repeated addresses with distinct response values.
    fresh(5);
    push(7,LANES); push(7,128'h1234); push(2,128'h9876); push(11,128'hfedc); push(7,128'habcd);
    expect_csr('h934,5); expect_csr('h930,5);
    write_csr('h908,4); write_csr('h908,1);
    request(7); respond(LANES); request(7); respond('h1234);
    request(2); respond('h9876); request(11); respond('hfedc); request(7); respond('habcd);
    expect_csr('h928,2); expect_csr('h934,5); expect_csr('h938,5);
    expect_csr('h93c,5); expect_csr('h940,5); expect_csr('h930,0);
    if(wb_cyc) $fatal(1,"PASS still owns bus");

    // A seventeenth PUSH must not complete until a FIFO entry retires.
    fresh(17); for(i=0;i<16;i=i+1) push(100+i,128'(i));
    stage(116,16); write_csr('h908,1);
    fork
      write_csr('h924,1);
      begin
        repeat(30) tick();
        if(s_axi_bvalid) $fatal(1,"FIFO-full PUSH acknowledged before space");
        request(100); respond(0);
      end
    join
    write_csr('h908,4);
    for(i=1;i<17;i=i+1) begin request(100+i); respond(128'(i)); end
    expect_csr('h928,2); expect_csr('h934,17); expect_csr('h940,17);

    fresh(3); push(8,12); push(9,LANES); push(10,128'h5555); write_csr('h908,1);
    request(8); respond(12);
    request(9); respond(128'habcdef01_23456789_13579bdf_2468ace0);
    failed(1); expect_csr('h948,1); expect_csr('h94c,9);
    expect_csr('h950,32'h33221100); expect_csr('h954,32'h77665544);
    expect_csr('h958,32'hbbaa9988); expect_csr('h95c,32'hffeeddcc);
    read_csr('h960,value);
    if(value!==32'h2468ace0) $fatal(1,"first failure actual not captured atomically");
    respond(128'h9999); // Deliberate second bad response cannot replace first failure.
    expect_csr('h948,1); expect_csr('h94c,9);
    read_csr('h960,value);
    if(value!==32'h2468ace0) $fatal(1,"first failure actual changed after second mismatch");
    expect_csr('h964,32'h13579bdf); expect_csr('h968,32'h23456789); expect_csr('h96c,32'habcdef01);
    @(negedge clk); replay_reset=1; calib_complete=0;
    repeat(3) tick(); @(negedge clk); replay_reset=0; calib_complete=1;
    failed(1); expect_csr('h960,32'h2468ace0);

    fresh(1); push(3,0); write_csr('h908,1); request(3); respond(0,1);
    failed(2); expect_csr('h93c,1); expect_csr('h940,0);
    fresh(1); push(4,0); write_csr('h908,1); request(4);
    @(negedge clk); replay_reset=1; tick(); @(negedge clk); replay_reset=0;
    failed(8); respond(0); failed(8);
    fresh(1); push(4,0); write_csr('h908,1);
    @(negedge clk); calib_complete=0; tick(); @(negedge clk); calib_complete=1;
    failed(4);
    fresh(1); @(negedge clk); calib_complete=0;
    write_csr('h908,1); failed(16); @(negedge clk); calib_complete=1;
    fresh(0); write_csr('h908,1); failed(16);

    // Temporary empty FIFO is not EOF. FINISH makes a short stream terminal.
    fresh(2); write_csr('h908,1); repeat(10) tick();
    expect_csr('h928,1); if(wb_cyc) $fatal(1,"starvation invented request");
    push(8,42); request(8); respond(42); expect_csr('h928,1);
    write_csr('h908,4); failed(32);
    fresh(1); push(1,1); push(2,2); failed(64);
    fresh(1); write_csr('h924,1,2); failed(128); // Incomplete staging.
    fresh(1); s_axi_wstrb=1; write_csr('h910,123,2); s_axi_wstrb=15;
    failed(128);
    fresh(1); write_csr('h000,1,2); expect_csr('h928,0); // No loader aliases.
    push(5,5); write_csr('h908,1); write_csr('h908,2); failed(8);
    fresh(1); push(6,6); write_csr('h908,4); write_csr('h908,1);
    // Same-cycle acceptance/ACK must not be lost.
    while(!wb_stb) tick(); @(negedge clk); wb_stall=0; wb_ack=1; wb_rdata=6;
    tick(); @(negedge clk); wb_stall=1; wb_ack=0; repeat(4) tick();
    expect_csr('h928,2); expect_csr('h938,1); expect_csr('h940,1);
    // Count equality alone is insufficient: FINISH must authenticate EOF.
    fresh(1); write_csr('h90c,1,0,1); push(20,20); write_csr('h908,1);
    request(20); respond(20); expect_csr('h928,1); expect_csr('h940,1);
    write_csr('h908,4); expect_csr('h928,2);
    push(21,21); failed(64); // Trailing data cannot preserve a previous PASS.
    fresh(1); expect_csr('h948,32'hffffffff); expect_csr('h960,0);
    $display("PASS: diagnostic replay and CSR contract"); $finish;
  end
  initial begin #2000000; $fatal(1,"replay test timed out"); end
endmodule
