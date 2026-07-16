# RC Blocker-Driven Lowering Design

## Status and purpose

**Status:** approved design.

This design makes the frozen TinyStories representative core the driver for
compiler and hardware work.  Rather than declaring floating-point operations
globally unacceptable, it repeatedly lowers the complete core through the
intended open pipeline, investigates the first real semantic blocker, and
integrates a candidate only when its evidence supports the frozen oracle.

The fixed unit under test is exactly:

```text
tinystories-w8a8-rc-study-mask9-vocab6-width2
```

It is the static XNNPACK PT2E W8A8 export with vocabulary 6, two layers,
context length 8, hidden width 2, one attention head, and seed 0.

## Trust boundary

The frozen PT2E W8A8 export and its four-case reference image remain the
numerical authority.  The comparison boundary is six final raw int8 output
codes and the lowest-index argmax token ID for each case.

The project must not require a zero-float MLIR program.  A float operation is
acceptable when it has a named, reproducible implementation path to hardware.
The meaningful gate is semantic lowerability and later oracle agreement, not
an operation census.

No candidate may silently replace canonical PT2E semantics with a hand-made
hardware PyTorch model, a scout transform, or an approximation.  If a
literature-derived approximation eventually becomes necessary, it requires a
separate decision and a separately stated fidelity contract.

## Existing starting evidence

The Direct-Linalg, no-handshake route for the fixed RC reaches flat-SCF and
then stops at `math.exp` during CIRCT `--lower-scf-to-calyx`.  No valid Calyx
artifact or SystemVerilog is produced by that RC run.

The project already packages a pinned Calyx float primitive library and
Berkeley HardFloat source closure.  Its native-Calyx float-library self-test
proves that library packaging and source resolution work for a small fixture.
It does not prove that the blocked RC reached Calyx Futil imports or exercised
HardFloat: CIRCT stopped before that stage.  Earlier F32/handshake work and
the library self-test are useful implementation evidence, but not substitute
evidence for this frozen RC.

## Selected iterative architecture

The full RC is the only driver of the iteration sequence:

```text
frozen V=6 W8A8 RC
  -> intended complete lowering pipeline
  -> first validly captured blocker
  -> source-context extraction and minimized reproducer
  -> tooling/library plus local-paper-corpus investigation
  -> candidate tests and semantic classification
  -> guarded pipeline integration
  -> rerun complete RC
  -> repeat until valid SV and RC oracle comparison
```

The process is intentionally sequential at the full-RC boundary: it does not
pretend that a hand-authored primitive or a reduced subgraph is the model.
Primitive cases make a blocker inspectable and fast to test; full-RC reruns
establish whether an intervention actually advances the intended system.

### Per-blocker evidence packet

Every discovered blocker produces a durable packet containing:

1. The full-RC command, input hashes, diagnostic, exit status, and artifact
   validity state.  A zero exit plus an MLIR error diagnostic is a rejected
   result, never a successful lowering.
2. The mechanically derived RC source context: source SHA-256, operation
   range, operand/result types, constants, shapes, and retained external
   values.
3. A minimal reproducer that preserves the observed scalar signature or
   operation form.  It is capability evidence only unless a dedicated
   reference check makes it an executable semantic test.
4. A toolchain/library evidence table covering CIRCT, Calyx Futil, HardFloat,
   MLIR, Torch-MLIR, TOSA, and checked-in local compatibility passes.  Local
   transformations must be labelled local rather than presented as upstream
   support.
5. A literature evidence table drawn from the local FPGA-LLM paper corpus.
6. Candidate classification, integration result, and the next full-RC
   frontier.

## Literature evidence method

`/home/roland/LLM-inference-on-FPGA-papers` contains the local 49-PDF corpus
for the query used by this project.  The PDFs are an external research cache;
they must be read locally but neither copied into this repository nor
redistributed.

For each blocker family, the investigation screens the complete corpus using
its catalog metadata and full-text search terms derived from the actual
operation.  For `math.exp`, these include `exp`, `softmax`, maximum
subtraction, normalization, lookup table, polynomial, piecewise, and floating
point.  It then deeply reads only the papers whose full text supplies an
implementation claim relevant to the blocker.

Each literature row records paper identifier, title, evidence page or section,
model/operator context, implementation technique, precision, FPGA context,
and one of these classifications:

- **direct implementation evidence:** an implementation relevant to the
  observed semantics is described;
- **approximation or co-design evidence:** a changed algorithm, table,
  polynomial, model quantization, or accuracy tradeoff is described;
- **context only:** the paper mentions the operation but supplies no usable
  implementation detail.

Literature is design evidence, not a semantic proof.  A published Softmax or
activation approximation cannot be integrated under the canonical PT2E oracle
without a separate fidelity decision.

## Candidate routes and acceptance policy

Every blocker is investigated under three distinct classes:

1. **Direct lowerer/library route.**  A pinned upstream tool maps the source
   operation to a valid Calyx/Futil/HardFloat-supported form.  This includes
   direct CIRCT support and actual Calyx primitive binding.
2. **Named composition.**  A documented transformation maps the operation to
   already supported primitives.  Its floating-point behavior, special cases,
   rounding, and conversion rules must be examined; a mathematical identity is
   not automatically an exact route.
3. **Approximation or changed semantic contract.**  A paper, TOSA table,
   polynomial, LUT, clamp, or altered quantization scheme changes the numeric
   behavior.  It is recorded but not integrated into the canonical route
   without separate approval.

Calyx/HardFloat is a candidate provider, not a blanket exemption.  For
ordinary arithmetic, conversion, comparison, division, and square-root
operations, the evidence must show that the actual RC form reaches the
corresponding Calyx primitive and native SV closure.  For `math.exp`,
`math.tanh`, `math.fpowi`, `math.rsqrt`, `math.roundeven`, `math.floor`, and
`math.ceil`, the evidence must identify the actual operation-specific route
rather than infer support from generic floating-point availability.

## Integration and verification ladder

A candidate progresses through these gates in order:

1. **Capability gate:** its minimal reproducer produces a valid artifact;
   diagnostics and output validity agree with the recorded status.
2. **Binding gate:** where it claims Calyx/HardFloat support, emitted Calyx
   imports/primitives and native-SV source closure demonstrate that the
   selected implementation is actually consumed.
3. **Whole-RC advancement gate:** after integration, the fixed RC reruns from
   its frozen Torch-MLIR/flat-SCF source and reaches a strictly later frontier
   without masking the original blocker.
4. **Hardware-oracle gate:** once valid SV exists, an executable testbench
   compares all four reference cases against six raw output codes and the
   token ID.  No route is labelled exact before this gate passes.

Passing a primitive capability gate is not an equivalence result.  Passing a
whole-RC compiler boundary is not an equivalence result.  The final gate is
the only basis for a canonical functional-equivalence claim.

## First iteration: `math.exp`

The first evidence packet concerns the observed `math.exp` in the RC Softmax
path.  It begins from the existing full-RC diagnostic, scalar f32 MRC, and
mechanically derived attention-Softmax provenance fragments.

The investigation first determines whether any pinned upstream CIRCT, Calyx,
HardFloat, MLIR, Torch-MLIR, or TOSA path can carry the canonical operation.
In parallel it screens the complete local paper corpus for FPGA Softmax/exp
implementations and classifies their semantics.  A result that establishes
only an approximation remains useful evidence, but it does not unblock the
canonical pipeline.

## Explicit non-goals

- Do not use a count of remaining float operations as a pass/fail gate.
- Do not bypass the full RC with a hand-authored structural substitute.
- Do not integrate an approximation, scout pass, or model rewrite under the
  frozen PT2E oracle.
- Do not make SV, DDR3, host, board, timing, or resource claims until the
  relevant later gates are reached.
- Do not modify or redistribute the external PDF cache.
- Do not report a paper technique as exact unless its source establishes that
  claim and the project independently passes its own RC hardware-oracle gate.

## Success condition

The loop succeeds when the named frozen RC reaches valid, testable SV through
the intended open pipeline and passes the frozen raw-code-plus-token oracle.
It also succeeds incrementally whenever it produces a reproducible blocker
packet, advances the full-RC frontier, or establishes that a canonical route
requires an explicit new research or fidelity decision.
