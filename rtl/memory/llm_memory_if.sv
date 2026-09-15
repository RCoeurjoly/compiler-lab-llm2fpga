`timescale 1ns/1ps

// Compiler-owned logical memory boundary.  Addresses are byte addresses for
// the authenticated INT8 projection tables; responses retain request order.
interface llm_memory_if #(parameter int ADDRESS_WIDTH = 32,
                          parameter int DATA_WIDTH = 8);
  logic read_valid;
  logic [ADDRESS_WIDTH-1:0] read_address;
  logic response_valid;
  logic [ADDRESS_WIDTH-1:0] response_address;
  logic [DATA_WIDTH-1:0] response_data;
  logic response_error;
  modport client (output read_valid, read_address,
                  input response_valid, response_address, response_data,
                  response_error);
  modport backend (input read_valid, read_address,
                   output response_valid, response_address, response_data,
                   response_error);
endinterface
