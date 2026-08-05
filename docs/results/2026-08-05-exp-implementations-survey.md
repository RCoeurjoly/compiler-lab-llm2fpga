# How the FPGA papers handle `exp`

This is a focused survey of the pinned corpus in
[`LLM-inference-on-FPGA-papers`](../../LLM-inference-on-FPGA-papers/), rather
than a survey of arbitrary math libraries.  The question is how papers make
`exp` (usually as part of softmax, GELU, or SiLU) synthesizable and fast.

## Executive conclusion

The papers almost never implement IEEE `exp` as an unconstrained floating-point
primitive.  They first exploit model structure (softmax subtracts its maximum,
so inputs are non-positive), then choose one of three hardware forms:

| strategy | representative corpus evidence | what is actually guaranteed |
| --- | --- | --- |
| bounded LUT/table, often with interpolation | FlightLLM stores Softmax/SiLU/GELU lookup tables in DDR; PEANO-ViT stores fractional powers of two | deterministic finite-domain approximation; error depends on address width and interpolation |
| range reduction + polynomial/rational approximation | PEANO-ViT uses a degree-(2,2) Padé approximation and clamps values below -3; QUARK splits base-2 exponent into integer and fractional parts | fast, bounded approximation over an explicitly selected interval, not exact PyTorch `exp` |
| integer-only shift/add and shared subcircuits | QUARK approximates `log2(e)` with shifts, uses a second-order fractional polynomial, and time-multiplexes exponent/log hardware across Softmax, GELU, and LayerNorm | model-level accuracy after quantization/calibration; not bit- or fp-exact equivalence |

The survey papers also describe dedicated SFUs for softmax and layer norm, but
usually do not specify the exponential approximation.  “Supports softmax” is
therefore not evidence that a synthesizable `math.exp` lowering exists.

## What the detailed papers do

**PEANO-ViT** ([PDF](../../LLM-inference-on-FPGA-papers/papers/2406.14854v2.pdf))
uses softmax max-subtraction, then a Padé `[2,2]` rational approximation to
`e^x`.  The paper reports that it is very accurate on approximately `[-3, 2]`;
values below `-3` are set to zero after the range transformation.  Fractional
powers of two are represented by a small precomputed table.  This is a useful
blueprint for FPGA cost, but its reported criterion is model accuracy (at most
0.5% degradation for the cited DeiT-B experiment), not equality to PyTorch.

**QUARK** ([PDF](../../LLM-inference-on-FPGA-papers/papers/2511.06767v2.pdf))
rewrites `exp(x)` as `2^(x log2 e)`.  It approximates `log2(e)` by shifts,
extracts an integer exponent for a shift, and evaluates the fractional part
with a second-order polynomial.  It similarly approximates logarithm and uses
the shared operators to remove softmax division; the same hardware is reused
for GELU and LayerNorm.  The design is explicitly integer-only and calibrated
for quantized models.  On ZCU102 it reports 20--80% LUT reduction and about
70% FF reduction versus conventional nonlinear implementations, plus large
speedups, but those results include the quantized model and do not establish
floating-point functional equivalence.

**FlightLLM** ([PDF](../../LLM-inference-on-FPGA-papers/papers/2401.03868v2.pdf))
places lookup tables for softmax, SiLU, and GELU in DDR, while a special
function unit performs the miscellaneous operations.  The important lesson
for our DDR3 plan is architectural: nonlinear constants need not consume
on-chip BRAM, but the table ABI, address calculation, initialization image,
and read latency become part of the proof obligation.

**Qwen2.5 on KV260** ([PDF](../../LLM-inference-on-FPGA-papers/papers/2504.17376v1.pdf))
pushes nonlinear operations to the processing system (the accumulated result
is transferred to the PS for nonlinear computation).  This avoids synthesizing
`exp` in PL, but is a different system boundary and is not a solution for a
self-contained SV accelerator.

## Implications for our pipeline

1. Keep exactness and approximation as separate products.  A Padé or shift/add
   implementation can be an excellent performance candidate, but it cannot be
   called equivalent to the input PyTorch graph without a specified tolerance.
2. Make the domain explicit before lowering.  For softmax, subtract the maximum
   and record the resulting fixed-point range.  For GELU/SiLU, record the
   calibrated activation range.  This turns `exp` into a finite, testable
   function rather than an open-ended floating-point operation.
3. First build an exact-reference table for the observed RC domain.  Generate
   entries from the PyTorch oracle, define quantization/rounding and saturation,
   and lower it as ROM or DDR-backed data.  Compare SV against the same table
   and then against PyTorch.  This gives a practical equivalence milestone
   before trying a polynomial.
4. Treat table placement as part of the DDR3 work: hash the table image, bind
   it to the generated RTL, and test address/order/read-valid behavior in the
   host simulation.
5. Only after the exact table path works, evaluate PEANO/QUARK-style
   approximations as alternatives.  Measure max/mean error, output-token
   agreement, cycles, LUT/FF/DSP, and DDR bandwidth in one reproducible report.

## Recommended next experiment

Instrument the RC PyTorch model to dump the actual `exp` input distribution and
the required output precision.  Select a conservative finite interval, generate
an oracle-backed table, and run one-input then multi-input SV equivalence.  If
the table is too large for on-chip storage, put the same bytes in the host DDR3
model.  This directly tests the paper-supported strategy while preserving a
clear path to later approximation and formal proofs.

The corpus does **not** provide evidence that Calyx HardFloat itself supplies
`math.exp`; it supplies floating-point arithmetic building blocks.  An exp
algorithm, table, or system-level offload must therefore be made explicit in
the lowering.
