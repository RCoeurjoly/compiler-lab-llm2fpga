`timescale 1ns/1ps
// Compare every core register and bus output at zero offset, including inactive
// request contents and all FIFO entries. No command-overlay latency allowance.
module compiler_ddr3_trace_replay_equivalence_tb;
  reg clk=0; always #5 clk=~clk;
  reg reset=1, replay_reset=0, calib_complete=1;
  reg clear=0, start=0, finish=0, configure=0, protocol_error=0, push=0;
  reg [31:0] configured_count=0, push_address=0;
  reg [127:0] push_expected=0, wb_rdata=0;
  reg wb_stall=1, wb_ack=0, wb_err=0;
  wire push_ready, sealed, starved, wb_cyc, wb_stb, wb_we;
  wire [1:0] state;
  wire [4:0] fifo_level;
  wire [31:0] expected_count, pushed_count, accepted_count, response_count;
  wire [31:0] checked_count, error_bits, first_index, first_address, wb_addr;
  wire [127:0] first_expected, first_actual;
  wire [15:0] wb_sel;
  compiler_ddr3_trace_replay dut (.*);
  compiler_ddr3_trace_replay_reference reference (
    .clk(clk), .reset(reset), .replay_reset(replay_reset), .calib_complete(calib_complete),
    .clear(clear), .start(start), .finish(finish), .configure(configure),
    .protocol_error(protocol_error), .configured_count(configured_count),
    .push(push), .push_address(push_address), .push_expected(push_expected),
    .wb_stall(wb_stall), .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata));
  localparam [127:0] A=128'hffeeddcc_bbaa9988_77665544_33221100;
  localparam [127:0] B=128'h01234567_89abcdef_13579bdf_2468ace0;
  integer cycles=0;
  `define SAME(field) if(dut.field !== reference.field) $fatal(1,"zero-offset %s at cycle %0d", `"field`",cycles);
  task compare;
    integer j;
    `SAME(state) `SAME(sealed) `SAME(fifo_level)
    `SAME(expected_count) `SAME(pushed_count) `SAME(accepted_count)
    `SAME(response_count) `SAME(checked_count) `SAME(error_bits)
    `SAME(first_index) `SAME(first_address) `SAME(first_expected) `SAME(first_actual)
    `SAME(active_address) `SAME(active_expected) `SAME(active) `SAME(pending)
    `SAME(read_pointer) `SAME(write_pointer)
    `SAME(wb_cyc) `SAME(wb_stb) `SAME(wb_addr) `SAME(wb_we) `SAME(wb_sel)
    `SAME(push_ready) `SAME(starved) `SAME(failure)
    for(j=0;j<16;j=j+1) begin
      if(dut.fifo_address[j] !== reference.fifo_address[j] ||
         dut.fifo_expected[j] !== reference.fifo_expected[j])
        $fatal(1,"zero-offset FIFO contents at cycle %0d slot %0d",cycles,j);
    end
  endtask
  always @(posedge clk) begin
    if(cycles!=0) compare();
    #1; cycles=cycles+1; compare();
  end
  `undef SAME
  task tick; @(posedge clk); #2; endtask
  task quiet;
    replay_reset=0; calib_complete=1; clear=0; start=0; finish=0;
    configure=0; protocol_error=0; push=0; wb_stall=1; wb_ack=0; wb_err=0;
  endtask
  task fresh(input [31:0] count);
    @(negedge clk); quiet(); reset=1; tick();
    @(negedge clk); reset=0; configure=1; configured_count=count; tick();
    @(negedge clk); configure=0;
  endtask
  task enqueue(input [31:0] address, input [127:0] data);
    push=1; push_address=address; push_expected=data; tick();
    @(negedge clk); push=0;
  endtask
  task launch;
    start=1; tick(); @(negedge clk); start=0;
    if(state!=1 || dut.active) $fatal(1,"launch edge changed");
  endtask
  task ready_load(input [31:0] count);
    fresh(count); enqueue(32'h02000019,A); launch();
    if(fifo_level!=1 || dut.active_address!=0) $fatal(1,"load setup");
  endtask
  task load_request;
    tick(); @(negedge clk);
    if(!wb_stb || wb_addr!=32'h02000019 || dut.active_expected!=A)
      $fatal(1,"request bundle load");
  endtask
  task reply(input [127:0] data, input bit err, input bit ack);
    wb_stall=0; wb_ack=ack; wb_err=err; wb_rdata=data; tick();
    @(negedge clk); wb_stall=1; wb_ack=0; wb_err=0; wb_rdata=~data;
  endtask
  task inject(input integer which);
    case(which)
      0: replay_reset=1;
      1: clear=1;
      2: calib_complete=0;
      3: protocol_error=1;
      4: configure=1;
      5: start=1;
      6: finish=1;
      7: push=1;
      8: begin replay_reset=1; clear=1; calib_complete=0;
               protocol_error=1; configure=1; start=1; finish=1; push=1; end
    endcase
  endtask
  function [31:0] failure_code(input integer which);
    case(which)
      0,1,8: failure_code=8;
      2: failure_code=4;
      3,4: failure_code=128;
      5: failure_code=16;
      6: failure_code=32;
      7: failure_code=64;
      default: failure_code=0;
    endcase
  endfunction
  task frozen_failure(input [31:0] code, input [31:0] index,
                      input [31:0] address, input [127:0] expected, input [127:0] actual);
    if(state!=3 || error_bits!=code || first_index!=index || first_address!=address ||
       first_expected!=expected || first_actual!=actual || wb_cyc)
      $fatal(1,"first failure record/priority");
    // Further errors/commands and changed bus data must not overwrite evidence.
    @(negedge clk); quiet(); wb_ack=1; wb_err=1; wb_rdata=~actual;
    start=1; configure=1; finish=1; push=1; protocol_error=1;
    repeat(3) tick();
    if(state!=3 || error_bits!=code || first_index!=index || first_address!=address ||
       first_expected!=expected || first_actual!=actual) $fatal(1,"first record changed in FAIL");
    @(negedge clk); quiet();
  endtask
  integer i, j;
  reg [127:0] mismatch;
  initial begin
    tick();
    // Every control failure and priority collision on the otherwise-load edge.
    for(i=0;i<9;i=i+1) begin
      ready_load(i==7 ? 1 : 2); wb_ack=1; wb_err=1; wb_rdata=B; inject(i); tick();
      if(dut.active_address!=0 || dut.active_expected!=0 || accepted_count!=0 || response_count!=0)
        $fatal(1,"control failure loaded inactive bundle");
      frozen_failure(failure_code(i),0,0,0,B);
    end
    // Cold reset wins even over a load and all simultaneous faults.
    ready_load(2); reset=1; inject(8); wb_rdata=B; tick();
    if(state!=0 || error_bits!=0 || dut.active_address!=0) $fatal(1,"cold-reset precedence");

    // The inactive/load edge ignores arbitrary data and unsolicited ACK/ERR.
    for(i=0;i<4;i=i+1) begin
      ready_load(1); wb_ack=i[0]; wb_err=i[1]; wb_rdata=B; load_request();
      wb_ack=0; wb_err=0; wb_rdata=~B; repeat(3) tick();
      @(negedge clk); reply(A,0,1);
      if(accepted_count!=1 || response_count!=1 || checked_count!=1 || state!=1)
        $fatal(1,"same-edge accept/ACK or missing FINISH");
    end

    // Every one-bit data mismatch; same-edge and delayed acceptance alternate.
    for(i=0;i<128;i=i+1) begin
      ready_load(2); load_request();
      if(i[0]) begin
        wb_stall=0; tick(); @(negedge clk); wb_stall=1;
        repeat(2) tick(); @(negedge clk);
      end
      mismatch=A ^ (128'd1<<i); reply(mismatch,0,1);
      if(accepted_count!=1 || response_count!=1 || checked_count!=1) $fatal(1,"mismatch counts");
      frozen_failure(1,0,32'h02000019,A,mismatch);
    end
    // ERR dominates mismatch and ACK+ERR never increments checked_count.
    for(i=0;i<2;i=i+1) begin
      ready_load(1); load_request(); reply(B,1,i[0]);
      if(accepted_count!=1 || response_count!=1 || checked_count!=0) $fatal(1,"ERR counts");
      frozen_failure(2,0,32'h02000019,A,B);
    end
    // Responses coincident with every control class, including cycle suppression.
    for(i=0;i<9;i=i+1) begin
      ready_load(i==7 ? 1 : 2); load_request(); inject(i);
      wb_stall=0; wb_ack=1; wb_rdata=B; tick();
      j=(i==0 || i==2 || i==8) ? 0 : 1;
      if(accepted_count!=j || response_count!=j || checked_count!=j) $fatal(1,"collision counts");
      frozen_failure(failure_code(i),0,32'h02000019,A,B);
    end

    // Empty enqueue, simultaneous enqueue/load, stalled active request, refill,
    // repeated address/distinct expected data and no reload on response edge.
    fresh(3); launch(); repeat(3) tick(); @(negedge clk);
    if(!starved || wb_cyc) $fatal(1,"FIFO starvation");
    enqueue(7,A);
    if(dut.active || dut.active_address!=0) $fatal(1,"empty enqueue loaded too soon");
    enqueue(7,B);
    if(dut.active_address!=7 || dut.active_expected!=A || fifo_level!=2) $fatal(1,"enqueue/load");
    repeat(3) tick(); @(negedge clk);
    push=1; push_address=9; push_expected=~A; reply(A,0,1); push=0;
    if(dut.active || dut.active_expected!=A || fifo_level!=2) $fatal(1,"reloaded response edge");
    tick(); @(negedge clk);
    if(dut.active_address!=7 || dut.active_expected!=B) $fatal(1,"paired expected load");
    reply(B,0,1); tick(); @(negedge clk);
    if(dut.active_address!=9 || dut.active_expected!=~A) $fatal(1,"FIFO refill ordering");
    reply(B,0,1); frozen_failure(1,2,9,~A,B);

    // FINISH before, at, after final ACK, or absent: PASS retains exact edge.
    for(i=0;i<4;i=i+1) begin
      ready_load(1); load_request();
      if(i==0) begin finish=1; tick(); @(negedge clk); finish=0; end
      if(i==1) finish=1;
      reply(A,0,1); finish=0;
      if(state!=1) $fatal(1,"early PASS on final response");
      if(i<2) begin tick(); @(negedge clk); if(state!=2) $fatal(1,"late PASS"); end
      else begin
        repeat(3) tick(); @(negedge clk);
        if(state!=1) $fatal(1,"PASS without FINISH");
        if(i==2) begin
          finish=1; tick(); @(negedge clk); finish=0;
          if(state!=1) $fatal(1,"early PASS on FINISH");
          tick(); @(negedge clk); if(state!=2) $fatal(1,"PASS after FINISH");
        end
      end
    end
    // Exercise wrap/full FIFO through multiple refills under periodic stalls.
    fresh(40);
    for(i=0;i<16;i=i+1) enqueue(32'(i),128'(i));
    launch();
    for(i=0;i<40;i=i+1) begin
      tick(); @(negedge clk);
      if(wb_addr!=32'(i) || dut.active_expected!=128'(i)) $fatal(1,"FIFO wrap ordering");
      repeat(2) tick(); @(negedge clk); reply(128'(i),0,1);
      if(i<24) enqueue(32'(i+16),128'(i+16));
    end
    finish=1; tick(); @(negedge clk); finish=0; tick();
    if(state!=2 || checked_count!=40) $fatal(1,"refill PASS/counts");
    $display("PASS: zero-offset replay equivalence, %0d cycles", cycles); $finish;
  end
  initial begin #2000000; $fatal(1,"equivalence timeout"); end
endmodule
