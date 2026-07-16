# Quantized RC Nonlinear Lowering Frontier Design

## Status and purpose

**Status:** approved design.

This investigation determines whether the frozen TinyStories representative
core can cross its nonlinear compiler frontier through established upstream
representations and passes.  It does not modify the model, quantization
configuration, numerical oracle, or board design.

The fixed unit under test remains:

```text
tinystories-w8a8-rc-study-mask9-vocab6-width2
```

It is the static XNNPACK PT2E W8A8 export with vocabulary 6, two layers,
context length 8, hidden width 2, one attention head, and seed 0.

## Non-negotiable trust boundary

The frozen PT2E W8A8 export is the numerical authority.  Its corpus inputs,
six final raw int8 codes, output qparams, dequantized logits, and lowest-index
argmax token ID remain the reference for every later claim.

This work must not quietly replace the model with a hand-authored
"hardware-semantic" PyTorch model.  A later approximation study is possible,
but only after this investigation has shown that an established, standard route
cannot carry the canonical model and after a separate decision records a new
fidelity contract.

## Problem statement

The no-Handshake Direct-Linalg route reaches pre-Calyx MLIR but currently
encounters `math.exp`.  The same RC frontier contains `math.tanh` and
constant-exponent `math.fpowi` operations.  These are likely constituents of
attention Softmax and tanh-approximate GELU, but the investigation must prove
that provenance from the actual exported/lowered program rather than infer it
from model folklore.

`math.sqrt` is not presumed a blocker: upstream SCF-to-Calyx lists it as a
supported operation.  It is retained as a control case to distinguish an
unsupported nonlinear from an accepted floating-point nonlinear.

The separate CIRCT diagnostic-status defect is recorded as an upstream
candidate: direct `circt-opt` can emit an error for unsupported `math.exp`,
write partial output, and return zero.  Local pipeline acceptance must never
trust that result.

## Established-route hypothesis

The first hypothesis is not that all nonlinear arithmetic is inherently
unlowerable.  It is that the existing PT2E/XNNPACK W8A8 conversion leaves
some nonlinear regions floating-point because its upstream quantized operator
coverage is narrower than the entire Transformer graph.

The investigation therefore distinguishes three layers:

1. **Canonical PT2E semantics.**  The fixed W8A8 export is unchanged.
2. **Standard representation/lowering.**  Torch-MLIR, TOSA, upstream MLIR
   transforms, and CIRCT are tested as they are, with documented versions.
3. **Approximation research.**  TOSA table forms and literature such as I-BERT
   are catalogued as possible later directions, but are not applied to the RC
   in this work.

TOSA is specifically useful to investigate because it standardizes
`tosa.table`, `tosa.rescale`, reductions, and integer-oriented table forms for
some nonlinear operations.  However, a TOSA operation or a table form is not
evidence of bit-exact equivalence to the PT2E float island.  Each candidate
must be tested against the frozen oracle before it can advance the working
system.

## Established sources

- The [PyTorch/ExecuTorch XNNPACK quantization documentation](https://docs.pytorch.org/executorch/stable/backends/xnnpack/xnnpack-quantization.html)
  documents static 8-bit PT2E quantization and its supported quantized
  operator families.  It is the authority for the chosen reference flow, not
  a claim of end-to-end integer Transformer coverage.
- The [MLIR TOSA dialect documentation](https://mlir.llvm.org/docs/Dialects/TOSA/)
  and [TOSA 1.0.1 specification](https://www.mlplatform.org/tosa/tosa_spec_1_0_1.html)
  define the standard `tosa.table`/`tosa.rescale` representations and their
  integer semantics.
- The [MLIR math dialect documentation](https://mlir.llvm.org/docs/Dialects/MathOps/)
  defines the source `math.exp`, `math.tanh`, and `math.fpowi` operations and
  their floating-point nature.
- [I-BERT](https://proceedings.mlr.press/v139/kim21d.html) is a cited research
  precedent for integer-only GELU, Softmax, and LayerNorm.  It is explicitly a
  future comparison point, not a transformation authorized by this design.

## Deliverables

### 1. CIRCT upstream-candidate note

Create one concise result note that records:

- the pinned CIRCT revision and the inspected upstream-main revision;
- the existing minimal `math.exp` reproducer and exact command;
- expected behavior: nonzero result and no accepted partial artifact;
- observed behavior: error diagnostic, partial output, exit status zero;
- the fact that the RC's full run also reports a separate verifier error and
  is correctly marked failed locally;
- an upstream issue-ready title, expected result, actual result, and minimal
  attachment list.

The note is local evidence only.  It must not claim an upstream issue was
filed or that upstream acknowledged the defect.

### 2. Provenance-preserving MLIR MRC suite

Produce two complementary classes of minimized reproducible cases.

**Primitive MRCs** isolate exact scalar signatures and attributes observed in
the RC:

- `math.exp` f32;
- `math.tanh` f32;
- `math.fpowi` f32 with its observed constant integer exponent;
- `math.sqrt` f32 as a supported-control case.

**Composite provenance slices** are mechanically derived from the actual
frozen RC at a documented lowering boundary.  They preserve the surrounding
Q/DQ, types, constants, tensor shapes, and dataflow needed to identify the
source family:

- attention Softmax;
- tanh-approximate GELU;
- LayerNorm.

A slice must identify its source artifact SHA-256, source line/range or stable
operation identifier, extraction method, and retained external inputs.  It may
not be presented as an independently executable semantic replacement unless it
has an executable reference check.

### 3. Standard-pass evidence matrix

For each primitive and composite MRC, run only the pinned, named upstream
transformations that are potentially relevant:

```text
canonical PT2E export
  -> Torch-MLIR TOSA
  -> tosa-validate
  -> tosa-to-linalg-pipeline / tosa-to-arith

Direct-Linalg/flat-SCF
  -> applicable upstream math expansion or canonicalization pass
  -> CIRCT --lower-scf-to-calyx
```

The matrix must report, rather than assume:

- input and output dialect/opcode/type;
- whether the pass succeeds and retains a valid IR artifact;
- whether the result remains float, becomes a standard integer/table form, or
  is rejected;
- whether CIRCT accepts it;
- whether the route is semantically exact, specified-but-approximate, or
  undetermined relative to PT2E;
- source documentation or upstream implementation supporting that
  classification.

The matrix explicitly tests `math.fpowi` strength reduction rather than calling
it exact.  Floating-point rounding, special values, and target-dependent math
semantics make a source-level algebraic identity insufficient for a numerical
equivalence claim.

### 4. Boundary result and recommendation

Publish one result document that answers:

1. Does an existing, standard PT2E/Torch-MLIR/TOSA/MLIR/CIRCT route carry each
   RC nonlinear family to a Calyx-accepted form?
2. If it changes representation, does the fixed corpus retain all six raw
   output codes and token IDs versus the frozen PT2E oracle?
3. What is the first remaining unsupported operation or missing pass?
4. Is the next justified action an upstream issue/patch, a standard-route
   integration, or an explicitly separate approximation study?

## Explicit non-goals

- No changed PyTorch TinyStories model or alternate RC oracle.
- No use of the existing scout approximations (`1 + x` for exp, clamp for
  tanh, or algebraic power expansion) in an equivalence or working-system
  claim.
- No generated SV, Yosys, DDR3, host, or board work in this bounded
  investigation.
- No claim that TOSA alone makes the PT2E model integer-only.
- No upstream GitHub issue, patch, or dependency update without a separate
  approval.

## Decision rules

### Advance

Advance a standard route only when all of the following hold:

1. It is expressed or implemented by a named, reproducible upstream tool or
   specification.
2. Its output is valid at the documented boundary.
3. It has no opaque/unimplemented hardware placeholder at the point of the
   claim.
4. It passes the frozen PT2E corpus comparison at the agreed measurement
   boundary.

### Stop and document

Stop this investigation, write the negative result, and request a new design
decision when a required nonlinear has no applicable standard route, or every
available standard route changes canonical PT2E outputs.  The resulting choice
must be explicit: upstream compiler/hardware work for canonical floating
semantics, or a separately scoped approximation/fidelity study.

## Verification

The implementation must add focused tests for reproducibility metadata,
extraction provenance, pass-matrix result schemas, and rejection of an
approximate/scout result being labelled exact.  It must run the existing
`calyx-math-exp-upstream-reproducer` and retain its observed exit code and
diagnostic in the evidence bundle.
