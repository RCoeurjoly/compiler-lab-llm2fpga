# Exact-input TinyStories-1M compiler design

**Status:** accepted

## Purpose

Determine what the existing LLM2FPGA compiler pipeline can actually lower when
its input is the exact TinyStories-1M quantized execution used by the proven
kev-gpt-derived accelerator. The observed compiler frontier, rather than an
assumed backend architecture, will determine the next implementation step.

The immediate objective is diagnostic and causal: remove model identity,
package layout, quantization, tokenizer, and arithmetic semantics as possible
explanations before debugging Torch-MLIR, CIRCT, Calyx, generated RTL, resource
use, or board integration.

## Scope

In scope:

- the exact TinyStories-1M model and tokenizer used by the proven accelerator;
- the complete authenticated kev-gpt package, including weights, scales,
  calibration inputs, layout, and hashes;
- an executable PyTorch representation of the same quantized/fixed-point
  computation;
- the existing PyTorch -> Torch-MLIR -> CIRCT/Calyx -> SystemVerilog pipeline;
- capture and classification of the first reproducible compiler frontier;
- evidence-driven selection of the next compiler or architecture change;
- eventual BRAM-only TinyStories-1M inference on the YPCB.

Out of scope until the exact-input frontier is established:

- arbitrary PyTorch models;
- other TinyStories sizes;
- the Representative Core as an active milestone;
- DDR3 or PCIe integration;
- speculative custom RTL kernels, new scheduling architectures, or backend
  substitutions;
- resource comparisons between semantically different models.

## Gate 0: exact executable identity

“Same model” means the same executable computation, not merely the same model
name or Hugging Face checkpoint. Gate 0 freezes and verifies:

- Hugging Face model ID and immutable revision;
- model configuration and architecture dimensions;
- kev-gpt source revision and any relevant working-tree patch;
- package manifest and every package-file hash;
- tensor names, shapes, offsets, layouts, and tied-weight rules;
- weight and activation quantization granularity;
- scale representation and application order;
- accumulator widths, rounding, saturation, overflow, and nonlinear semantics;
- tokenizer files and configuration;
- prompt token IDs, greedy-selection rule, expected 16 tokens, and named
  intermediate checkpoints.

The existing reference contract is not accepted unchanged. It currently says
that activation quantization is per-tensor while the package and executable
references contain 97 per-channel activation-scale vectors. Gate 0 must resolve
this and every similar conflict by tracing the package generator and executable
reference. Missing authority produces an explicit blocked result.

## Exact PyTorch input

The compiler input is an authenticated PyTorch program that executes the frozen
package semantics. Reconstructing floating-point weights from the package is
insufficient: the program must include the observable quantization,
dequantization, fixed-point conversion, rounding, saturation, accumulation,
LayerNorm, Softmax, GELU, residual, and token-selection behavior used by the
accelerator.

Before compiler lowering, the exported program must match the executable
kev-gpt reference for:

1. package and model identity;
2. the frozen prompt and 16 generated tokens;
3. named block-0 token-step checkpoints;
4. logits or their authenticated fixed-point equivalent at each selected
   token; and
5. deterministic repeated execution.

Failure here is an input-model problem, not a compiler problem.

## Current-pipeline experiment

Once Gate 0 passes, feed the authenticated exported program into the existing
pipeline:

```text
authenticated kev-gpt package + frozen model structure
        -> exact quantized PyTorch program
        -> torch.export
        -> Torch-MLIR
        -> existing Linalg/SCF normalization
        -> existing CIRCT/Calyx lowering
        -> existing SystemVerilog route
```

Only the authenticated input adapter and provenance wiring may change before
this experiment. Do not add external RTL primitives, replace nonlinear
operators, change quantization, or introduce a new scheduler merely to move the
frontier.

Every stage records its input and output hashes, tool revisions, command line,
operation census, diagnostics, and validity. Partial output after an upstream
diagnostic is not a successful lowering.

## Frontier classification

The first failure is classified at the earliest causal boundary:

- `identity_frontier`: the package or executable semantics remain ambiguous;
- `export_frontier`: the exact PyTorch computation cannot be exported;
- `torch_mlir_frontier`: Torch-MLIR cannot represent or lower an operation;
- `pre_calyx_frontier`: required normalization leaves unsupported IR;
- `calyx_frontier`: CIRCT/Calyx rejects or mis-lowers the valid input;
- `sv_frontier`: Calyx cannot emit valid synthesizable SystemVerilog;
- `functional_frontier`: generated RTL executes but differs from the oracle;
- `resource_frontier`: functionally correct RTL cannot fit;
- `timing_frontier`: fitting RTL does not meet constraints;
- `board_frontier`: timing-closed RTL fails deterministic board inference.

The frontier receipt must contain a minimal reproducer when practical and the
first mismatching checkpoint or diagnostic. Later cascading failures are not
reported as independent blockers.

## Post-frontier decision gate

No replacement architecture is selected in advance. The observed frontier
determines the smallest justified response:

- repair or add a compiler pass when the representation is sound but lowering
  is missing;
- define a bit-accurate compiler primitive when a supported TinyStories
  operation has no viable generic lowering;
- introduce scheduling, memory, streaming, or reuse abstractions when correct
  generated RTL is structurally too large or slow;
- introduce a stable autoregressive runtime boundary only when the tensor
  compiler output is correct but cannot express the complete token lifecycle.

StreamTensor is relevant precedent for the latter two cases: it treats
individual kernels as designed/generated components and compiles their tiling,
fusion, streaming, buffering, DMA, and runtime composition. It is not evidence
that arbitrary tensor semantics can be lowered mechanically into efficient RTL.

Any chosen change must be tied to the exact frontier, preserve the authenticated
input contract, and pass a before/after regression at that boundary.

## Validation ladder

1. **Identity gate:** exact source, package, tokenizer, and semantics are
   authenticated and internally consistent.
2. **Executable-input gate:** PyTorch/exported execution matches the kev-gpt
   oracle and frozen 16-token result.
3. **Stage-validity gate:** each current-pipeline stage either produces valid,
   hash-bound output or a precise frontier receipt.
4. **RTL functional gate:** if RTL is produced, simulation matches the earliest
   available oracle checkpoints before resource work begins.
5. **Implementation gate:** Yosys and constrained nextpnr report fit and timing
   without weakened constraints.
6. **Hardware gate:** BRAM-only YPCB inference matches the frozen 16 tokens on
   three cold starts.

Gates 4–6 are conditional on resolving the first observed frontier; they are
not assumed consequences of completing Gate 0.

## Required artifacts

- corrected exact-input contract and conflict-resolution report;
- complete package/source/tokenizer provenance manifest;
- executable quantized PyTorch adapter and exported-program hash;
- kev-gpt-versus-PyTorch checkpoint and token-equivalence receipt;
- per-stage current-pipeline manifests;
- first-frontier receipt and minimal reproducer;
- decision record for the evidence-backed next change;
- when reached, RTL simulation, synthesis, timing, and board evidence.

## Provenance and compliance

The exact package and kev-gpt executable are reference evidence. Their source
is not silently copied into compiler-generated deliverables. Any reference-
derived semantics or implementation choice is documented, and LLM assistance
remains disclosed. NLnet guidance is required before reference-derived work is
treated as a funded deliverable.
