module rc_exp_table_tb;
    logic clk = 0;
    logic rst = 1;
    logic req_valid = 0;
    logic [7:0] req_addr = 0;
    logic resp_valid;
    logic [31:0] resp_data;
    rc_exp_table_lookup #(.INIT_FILE("rc_exp_table.hex")) dut (.*);
    always #1 clk = ~clk;
    initial begin
        repeat (2) @(posedge clk);
        rst = 0;
        req_addr = 8'd0; req_valid = 1;
        @(posedge clk); #0.1;
        if (!resp_valid || resp_data !== 32'h3f7fb00c) $fatal(1, "entry 0 mismatch: %h", resp_data);
        req_addr = 8'd255;
        @(posedge clk); #0.1;
        if (!resp_valid || resp_data !== 32'h3f800000) $fatal(1, "entry 255 mismatch: %h", resp_data);
        $display("RC_EXP_TABLE_EQUIVALENCE_PASS");
        $finish;
    end
endmodule
