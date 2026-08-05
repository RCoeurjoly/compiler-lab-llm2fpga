# `bb0_1652` multiply slice laboratory

The Nix provenance artifact `mulf-provenance` identifies the candidate
pre-Calyx operation at line 5189 of `pre-calyx.mlir`:

```text
scf.for i = 0..8
  scf.for j = 0..2
    q = memref.load input[i*2+j] : i8
    q32 = arith.extsi q : i8 to i32
    shifted = arith.subi q32, -126 : i32
    qf32 = arith.sitofp shifted : f32
    product = arith.mulf qf32, 2.44140625e-4 : f32
    memref.store product, output[i*2+j]
```

This is structurally correlated with Calyx `mulf_36` and group `bb0_1652`.
The MLIR location metadata needed for a direct source location was not
preserved by the lowering, so the derivation records the resource-order
hypothesis explicitly.

## First upstream variant comparison

The Nix derivation `mulf-slice-variants` ran the pinned Torch-MLIR optimizer
with two standard pipelines:

| Variant | SCF loops | `arith.mulf` | IR bytes |
|---|---:|---:|---:|
| canonicalize + CSE | 2 | 1 | 785 |
| LICM + canonicalize + CSE | 2 | 1 | 783 |

LICM does not materially change this slice. The scale is already invariant,
and the multiply remains inside the two loop nests. This is a useful negative
result: the next candidate must change loop scheduling or component structure,
not merely perform scalar cleanup.

## Structured parallel representation

The same independent 16-element computation was also expressed as an upstream
`linalg.generic` with a `parallel` iterator and identity indexing over
`memref<16xi8>`/`memref<16xf32>`. This is a legal standard MLIR
representation; the initial `scf.parallel` spelling was rejected by the pinned
optimizer because that version requires a reduction terminator, so it was not
used as evidence.

The pinned Torch-MLIR optimizer accepted the linalg form:

| Variant | SCF loops | Linalg generic | Parallel iterators | `arith.mulf` | IR bytes |
|---|---:|---:|---:|---:|
| canonicalize + CSE | 2 | 0 | — | 1 | 785 |
| LICM + canonicalize + CSE | 2 | 0 | — | 1 | 783 |
| linalg.generic, parallel iterator, canonicalize + CSE | 0 | 1 | 1 | 1 | 594 |

The 618-byte result is therefore a representation-size observation, not yet a
Calyx cycle or resource improvement. The pinned CIRCT optimizer does not
register a linalg-to-loops pass, so this candidate currently stops at a
standard MLIR representation boundary. It must either be converted by a
pinned upstream MLIR tool before CIRCT, or be recorded as a toolchain
boundary; it is not evidence that the full RC schedule improved.

The matching pinned LLVM 21 `mlir-opt` does provide
`--convert-linalg-to-parallel-loops`, and the resulting artifact is valid
`scf.parallel` with two independent dimensions. The next diagnostic is
implemented in `diagnostics/mulf-slice-calyx.nix`, which attempts the baseline
and parallel forms with the same `lower-scf-to-calyx` invocation and records
both exit status and generated output. The first attempt exposed a runtime
closure mismatch for the standalone CIRCT binary (its glibc 2.42 interpreter
was absent from the ordinary derivation environment); this is an environment
failure, not a lowering result, and must be resolved before comparing Calyx
control structure.

## Calyx boundary measurements

The baseline slice reaches Calyx successfully:

| Candidate | CIRCT result | Calyx groups | Interpretation |
|---|---|---:|---|
| nested `scf.for` baseline | success | 18 | reference control structure |
| `scf.parallel` | aborts while loading affine dialect | — | pinned CIRCT failure |
| affine-loop unroll factor 2 → lower-affine → Calyx | success | 28 | worse than baseline |
| affine-loop unroll factor 8 / full unroll | valid MLIR, same partial unroll shape | — | no additional replication or measured schedule improvement |
| affine-parallelize → affine-parallel-unroll → Calyx | rejected for multiple writes | — | unsupported by the Calyx parallel-unroll legality check |
| Calyx go-insertion + GICM + control compilation | rejected on generated invoke/control form | — | not a valid post-lowering optimization for this component shape |
| Calyx GICM alone | success | 18 | no scheduling reduction |
| Calyx remove-comb-groups | success | 18 | no scheduling reduction |
| Calyx remove-groups | assertion failure in pinned CIRCT | — | not usable on this generated component |
| memory-banking factor 2 → affine-parallel-unroll | rejected for multiple writes | — | banking does not make the current affine-parallel legality check succeed |
| affine parallel unparallelize → Calyx | no valid component | — | supported fallback does not produce a usable artifact |

The affine-unrolled form is exact at the operation level but expands control
from 18 to 28 groups, so it is not a winner. The parallel forms are not
candidates for full-RC promotion: they have no valid Calyx artifact under the
pinned toolchain. The smaller MLIR forms must not be described as a scheduling
improvement.

## Surviving explanation

The latency diagnosis and slice experiments are consistent with one shared
HardFloat multiply resource being driven by serialized Calyx control. Scalar
cleanup cannot change that. Static unrolling can expose another multiply in
MLIR, but the resulting Calyx control remains sequential and grows from 18 to
28 groups. Actual overlap would require a valid parallel-to-Calyx lowering
that either replicates or banks the resource and emits parallel control; the
pinned CIRCT routes tested here do not provide that artifact.

This is now a precise upstream/toolchain boundary, with reproducible Nix
artifacts in `mulf-provenance`, `mulf-variants`, and `mulf-calyx`. It is not
evidence that the full RC should receive an unvalidated scheduling change.

No full-RC transformation or equivalence claim has been made from this
experiment.
