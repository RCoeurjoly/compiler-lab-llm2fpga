# Task 4 SSA boundary investigation

Scope: read-only audit of the first feed-forward GEMV-to-GEMV chain in the
authenticated portable Torch MLIR.  No lowering was attempted.

Input: `tiny-stories-1m-kev-gpt-exact-serial-gemv-successor-torch.mlir`,
SHA-256 `44464a97a3cfb4dcd6be64d33e8b0eab3822cbed53e1f1188761d5759bded57c`.

## First useful crossing

The first adjacent feed-forward pair is at Torch MLIR lines 3453 and 3563:

1. `%3321 = llm2fpga.serial_gemv(%3319, %3320)` has descriptor
   `rows=4, outputs=256, inputs=64, mac_order=ascending_i64_wrap`, with
   operand/result types `tensor<4x64xi64>`, `tensor<256x64xi64>`, and
   `tensor<4x256xi64>`.
2. `%3322 = torch_c.from_builtin_tensor(%3321)` restores
   `!torch.vtensor<[4,256],si64>`.
3. `%3323` through `%3428` are the exact integer SSA chain.  They include
   per-channel multiply/divide/remainder/negative-rounding logic, bias add,
   clamp to `[-128,127]`, view/index-based GELU lookup/interpolation, shifts,
   and a second per-channel requantization.  The next GEMV activation is
   `%3429 = torch_c.to_builtin_tensor(%3428)` with type `tensor<4x256xi64>`.
4. `%3431 = llm2fpga.serial_gemv(%3429, %3430)` has descriptor
   `rows=4, outputs=64, inputs=256, mac_order=ascending_i64_wrap`; `%3430`
   is `tensor<64x256xi64>`, and the result is `tensor<4x64xi64>`.

There are no `quantize_per_*` or `dequantize_per_*` operations in this
legalized Torch MLIR.  Q/DQ has already been decomposed into the named `si64`
integer arithmetic above.  The bridge types and constants make the precise
fixed-point boundary observable, but the scale/rounding semantics are not
summarized in any GEMV descriptor.

## Representation audit

The C++ legalizer only replaces a recognized raw GEMV with
`to_builtin_tensor -> llm2fpga.serial_gemv -> from_builtin_tensor`, preserving
the surrounding SSA uses.  Its descriptor carries only rows, outputs, inputs,
and `ascending_i64_wrap`.

The Python Calyx lowerer parses only those descriptor fields and emits generic
signed-i64 activation/weight/result memories plus an i64 MAC schedule.  It has
no IR representation for the bridge value identity, per-channel scale,
rounding/remainder rule, clamp, bias, GELU lookup, view/index chain, or a
non-GEMV operation.  Therefore the current legalizer/lowerer does **not** have
a defined representation for this first crossing.

## First evidenced frontier

The minimal required new compiler contract is not merely a connection between
two result/activation memories: it must encode the entire `%3321 -> %3429`
SSA chain, including the fixed-point Q/DQ decomposition and non-GEMV operators.
Until such a contract exists, composition must remain diagnostic and must not
run translation/synthesis.
