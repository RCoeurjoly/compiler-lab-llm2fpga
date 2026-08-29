# Packed softmax Calyx boundary

The authenticated softmax bridge previously stopped at a tensor-valued
`func.call`, which Calyx cannot lower.  The packed ABI (`i16384` scores and
result, `i32` position) is now converted to an explicit `hw.module.extern`
plus `calyx.primitive` component.  The resulting module exports successfully
to Futil with `circt-translate --export-calyx`.

The pinned Calyx Verilog backend and Yosys also accept the result and resolve
the external cell to `llm2fpga_attention_softmax_fixed_tensor`. Calyx warns
that this probe's packed data ports are not a wrapped simulation interface;
the full model top must provide that integration shell.

This is an integration-boundary result, not an inference or timing result. The
external primitive still requires the existing RTL implementation and a full
model top-level integration before board claims are possible.
