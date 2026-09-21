// Small XC7 legalization map used after ABC emits Yosys' internal inverter.
// nextpnr-xilinx consumes the native INV primitive, not $_NOT_.
module \$_NOT_ (input A, output Y);
  INV _TECHMAP_REPLACE_ (.I(A), .O(Y));
endmodule
