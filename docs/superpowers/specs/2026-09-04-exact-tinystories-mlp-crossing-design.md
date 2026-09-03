# Exact TinyStories-1M block-0 MLP Crossing Design

## Goal

Prove the real block-0 MLP path of the authenticated TinyStories-1M fixed
point model in generated Calyx/SystemVerilog: four frozen-prompt rows through
`c_fc (64 -> 256)`, fixed GELU, `c_proj (256 -> 64)`, and every Q/DQ boundary.

## Contract

The fixture is produced only by the exact adapter and uses prompt tokens
`[7454, 2402, 257, 640]`. It records authenticated source/package identity,
all values as canonical JSON and raw little-endian signed-int64 bytes, and a
self-hash. The required tensors are:

- `c_fc` input codes, input scales, input Q16.16 values, 4x256 signed i64
  accumulators, rescaled-plus-bias Q16.16 values, output codes/scales/Q16.16;
- the block-0 fixed-GELU input and output Q16.16 values, plus the exact 8192
  entry Q12 LUT identity and values;
- `c_proj` input codes/scales/Q16.16, 4x64 signed i64 accumulators,
  rescaled-plus-bias Q16.16 values, output codes/scales/Q16.16;
- both weight-code matrices, per-output Q8.24 weight scales, and Q16.16
  biases.

For each GEMV, the hardware executes ascending input-index signed 64-bit
two's-complement wrapping MAC terms:
`signed_i8(code) * input_scale_q8_24 * signed_i8(weight_code)`. It then uses
the existing exact contract: signed-magnitude half-up `(acc * weight_scale) >>
32`, add Q16.16 bias, and activation Q/DQ with signed i8 saturation.

GELU is not an approximation: it is the exact adapter algorithm. Clamp
`round_shift_signed(input_q16, 4)` to signed Q12 `[-32768, 32767]`, calculate
`index=(q12+32768)>>3`, `fraction=(q12+32768)&7`,
`upper=min(index+1,8191)`, and return
`(lut[index] + ((lut[upper]-lut[index])*fraction >> 3)) << 4`.

## Architecture

One generated Calyx `main` owns all external immutable fixture memories and
all intermediate hardware memories. Its control is strictly:

`c_fc GEMV -> c_fc rescale/bias/QDQ -> GELU -> c_proj input QDQ -> c_proj GEMV -> c_proj rescale/bias/QDQ`.

The generated Verilator harness may preload only source inputs, weights,
scales, biases, and GELU LUT. It must zero and then observe intermediate and
final memories; it may not preload an accumulator/GELU/output result or run a
host arithmetic stage between components. Reuse the demonstrated Task-3
explicit pipeline latches and disable Calyx `cell-share` only for this staged
arithmetic kernel.

## Acceptance

Generated SV must match every fixture value/hashes for both GEMV accumulators,
both post-GEMV Q/DQ outputs, GELU output, and final c_proj output. The runner
writes a canonical self-hashed receipt binding fixture/schema authority,
execution dimensions/cycles, each observed raw-byte hash, and content SHA-256
of Futil, simulator SV, synthesis SV, and harness. Yosys must stat synthesis
SV generated from the exact same Futil.

## Scope and limits

This is only a frozen-prompt block-0 MLP slice. It makes no claim about full
model/token generation, board deployment, DDR3, PCIe, Representative Core,
generic-SCF/arbitrary PyTorch, or copied RTL.

Two evidence-backed implementations are allowed for the first complete
composed generated-SV run. If both fail, stop and write a report containing
fixture/source hashes, exact commands/timings, earliest mismatch, generated
artifacts, and a recommendation. A schema redesign after a passing c_fc/GELU
partial gate is also a stop point rather than incremental scope growth.
