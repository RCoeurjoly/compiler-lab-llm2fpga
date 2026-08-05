// Explicit, source-bound lookup closure for the RC exponential table.
// The generated hex image is a support file, not an implicit simulator asset.
module rc_exp_table_lookup #(
    parameter int ADDR_W = 8,
    parameter int DATA_W = 32,
    parameter string INIT_FILE = "rc_exp_table.hex"
) (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 req_valid,
    input  logic [ADDR_W-1:0]    req_addr,
    output logic                 resp_valid,
    output logic [DATA_W-1:0]   resp_data
);
    logic [DATA_W-1:0] table_mem [0:(1 << ADDR_W)-1];
    initial $readmemh(INIT_FILE, table_mem);

    always_ff @(posedge clk) begin
        if (rst) begin
            resp_valid <= 1'b0;
            resp_data <= '0;
        end else begin
            resp_valid <= req_valid;
            if (req_valid)
                resp_data <= table_mem[req_addr];
        end
    end
endmodule
