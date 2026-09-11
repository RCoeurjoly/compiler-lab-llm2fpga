module \$_DFF_PP0_ (input D, C, R, output Q);
  FDCE #(.INIT(1'b0)) _TECHMAP_REPLACE_(.D(D), .Q(Q), .C(C), .CE(1'b1), .CLR(R));
endmodule
module \$_DFF_P_ (input D, C, output Q);
  FDRE #(.INIT(1'b0)) _TECHMAP_REPLACE_(.D(D), .Q(Q), .C(C), .CE(1'b1), .R(1'b0));
endmodule
