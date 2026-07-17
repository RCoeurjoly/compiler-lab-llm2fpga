# Frozen RC Softmax candidate evaluation

## Scope

The frozen model is `tinystories-w8a8-rc-study-mask9-vocab6-width2`. The probe
loaded its PT2E export unchanged and observed both internal `aten.softmax.int`
sites through an FX interpreter for four deterministic token contexts. It did
not rewrite the graph or generate MLIR/SV.

The candidate evaluator then applied analysis-only exponent functions to the
observed stabilized Softmax rows and compared each candidate's Softmax values
with Python's `math.exp` reference.

## Results

| Candidate | Softmax max absolute error | Mean absolute error | Status |
|---|---:|---:|---|
| Streaming exact | 0 | 0 | numerical baseline only |
| 256-entry piecewise-linear LUT, domain `[-8,0]` | `1.6086791e-6` | `6.0281630e-7` | approximate candidate |
| Range-reduced fifth-order polynomial | 0 on these observed rows | 0 on these observed rows | insufficient coverage for acceptance |
| Fixed-iteration “CORDIC” stand-in | 0 on these observed rows | 0 on these observed rows | not a CORDIC implementation |

Both Softmax sites produced finite rows summing to one for all four contexts.
The exact streaming candidate is an algorithmic baseline, not proof that the
current compiler can lower the operation. The polynomial and CORDIC zero errors
are not acceptance: the observed RC rows were too narrow to distinguish the
approximations from the reference.

## Interpretation

The LUT candidate has a measurable, bounded error on actual frozen-RC internal
rows. The polynomial candidate is promising but requires broader input-domain
coverage and final-logit/token testing. The CORDIC entry must be replaced by a
real fixed-point or floating-point CORDIC construction before it can be called
a hardware candidate.

No candidate has yet passed the LLM2FPGA equivalence gate. In particular, this
experiment does not compare six final logits or token IDs, does not lower a
candidate through MLIR/CIRCT, and makes no SV/resource claim.

## Full frozen-model smoke gate

The probe was extended to intercept Softmax inside the unchanged exported
program, continue the original model execution, and compare the final output
tensor against an untouched baseline execution. For all four deterministic
contexts, all four candidates produced identical final tensors, including the
six output codes at the final position:

| Candidate | Full output tensor equality on 4 contexts |
|---|---|
| Streaming exact | pass |
| LUT-256 | pass |
| Polynomial-5 | pass |
| CORDIC-12 stand-in | pass |

This is a smoke equivalence result only. It is not exhaustive `6^8` coverage,
and it does not establish that the LUT, polynomial, or CORDIC candidate is
semantically valid for the full RC domain. The candidate implementation also
runs in PyTorch; no generated RTL participates in this gate.

## Reproducibility

- Probe: [`run_rc_softmax_candidates.py`](../../scripts/pipeline/run_rc_softmax_candidates.py)
- Candidate evaluator: [`evaluate_softmax_candidates.py`](../../scripts/pipeline/evaluate_softmax_candidates.py)
- Context fixture: [`rc-softmax-candidate-contexts.json`](../../reproducers/rc-softmax-candidate-contexts.json)
- Frozen source model: `tinystories-w8a8-rc-study-mask9-vocab6-width2`

The next gate is to feed a wider, measured frozen-RC row corpus into the
candidates, then run the complete model oracle comparison before selecting a
candidate for MLIR/CIRCT lowering.

That gate was widened to the first 64 lexical base-six contexts. All four
candidates again passed full output-tensor equality against the untouched
exported-program baseline for every context. This strengthens the smoke result,
but remains far short of exhaustive `6^8` coverage.

## Polynomial lowering probe

The fifth-order polynomial form was also instantiated as ordinary MLIR
`arith.mulf`/`arith.addf` operations in
[`reproducers/calyx-softmax-polynomial/input.mlir`](../../reproducers/calyx-softmax-polynomial/input.mlir).
The pinned CIRCT `--lower-scf-to-calyx='top-level-function=main'` route accepted
it, CIRCT exported valid Calyx/Futil, and the existing native Calyx-to-SV
script emitted `main.sv` (128,387 bytes). Calyx's structural resource report
for this scalar probe was:

```text
estimated internal bits: 196
estimated external bits: 64
std_mulFN: 8
std_addFN: 5
seq_mem_d1: 2 × 32-bit, one-slot memories
```

This proves that an arithmetic polynomial form can cross the current Calyx/SV
backend boundary. It is not yet an accepted model candidate: it is a scalar
probe, uses f32 HardFloat arithmetic, has no complete Softmax reduction, and
has not passed final-logit/token equivalence or Yosys/FPGA mapping.
