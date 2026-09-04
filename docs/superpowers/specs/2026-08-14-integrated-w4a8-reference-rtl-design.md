# Integrated W4A8 stateful reference RTL

Date: 2026-08-14

## Decision

Create one deliberately unoptimized, compiler-generated W4A8 RTL design as an
executable reference for subsequent manual RTL refinement. One accepted
transaction must run the complete frozen three-phase serving sequence in one
RTL instance:

```text
runtime prompt[8]
  -> prefill
  -> phase-8 logits and cache
  -> lowest-index argmax and token feedback
  -> cached decode-8
  -> phase-9 logits and cache
  -> lowest-index argmax and token feedback
  -> cached decode-9
  -> phase-10 logits and cache
```

The entire sequence is expressed as one PyTorch module, exported as one PT2E
program, lowered once through the existing compiler pipeline, and emitted as
one SystemVerilog top. The generated result may be large, slow, structurally
duplicated, and unsuitable for the target FPGA. Correctness and reproducible
provenance take priority over area, timing, or compilation cost for this
reference milestone.

This design narrows and supersedes the compiler-baseline portion of
`2026-08-12-w4a8-rtl-refinement-design.md`. Yosys, nextpnr-xilinx, formal
equivalence, manual RTL optimization, DDR3 integration, and board execution
are later goals.

## Correction to the existing evidence boundary

The earlier static W8A8 RC is one generated RTL design, but one invocation is a
fixed-context forward pass with `use_cache=False`. Its context-0, frozen-four,
and ordered-reset simulations establish repeated forward-pass behavior, not a
stateful prefill/decode sequence.

The current W4A8 serving result contains three separately exported and lowered
designs: `prefill-8`, `decode-8`, and `decode-9`. Each phase was checked against
its corresponding PT2E/PyTorch result, but decode cache inputs were produced by
the software reference. This is valid phase-local RTL evidence. It does not
prove that an RTL-produced cache crosses either phase boundary, that hardware
token feedback is correct, or that one RTL instance completes the sequence.

The existing phase artifacts remain frozen diagnostic evidence. They cannot be
called an integrated W4A8 RTL reference and their graphs/RTL cannot be composed
into the canonical implementation. Their quantization parameters remain frozen
and the prefill observation remains an exact cross-check. Their decode
observations are not an end-to-end oracle because those phase programs received
FP32-produced caches rather than the W4A8-produced cache of an integrated run.

## Alternatives considered

### Wholesale integrated lowering — selected

Lower one whole stateful program through the compiler. This keeps all serving
semantics, cache continuity, and token selection inside the compiler-derived
reference. It may expose exporter or lowering defects and may have high build
cost, but those defects are in scope for this milestone.

### Hand-written wrapper around the three phase RTLs — rejected as canonical

A controller could join the existing phase designs and implement cache transfer
and argmax. It could be a useful diagnostic if wholesale lowering fails, but
the most important stateful behavior would then depend on new hand-written RTL.
It therefore cannot become the canonical compiler-generated reference.

### Manual stateful implementation without a generated reference — rejected

This would shorten the path to fine-grained RTL iteration but would entangle
the first implementation with its correctness oracle. It does not provide the
independent executable RTL specification required for later optimization.

## Numerical and stateful contract

The frozen W4A8 PT2E numerical contract remains authoritative: signed W4
weights, signed A8 activations, recorded scales and zero points, exact rounding
and saturation, and lowest-index tie-breaking for argmax. Separately, the
integrated FP32 source module must use the same frozen model, prompt, and phase
semantics as the accepted ordered native trace. W4A8 PT2E tensors are never
required to equal unquantized FP32 tensors bit-for-bit.

One invocation starts from reset-cleared inference state. It consumes eight
runtime-loadable token IDs, executes prefill followed by two greedy cached
decode steps, and retains all intermediate KV-cache state on chip. The second
and third model calls must consume cache tensors produced by the preceding call
within that same invocation. Token inputs for both decode calls must come from
the integrated lowest-index argmax result, not from a recorded test vector.

Weights are immutable for the frozen reference. Prompt tokens are runtime
inputs. No DDR3 controller, external memory protocol, or host-managed phase
transition is part of this contract.

## Top-level RTL interface

The emitted design is exposed through one narrow synthesizable top-level ABI:

- clock and deterministic reset;
- indexed write interface for the eight prompt tokens;
- `go`, `busy`, and `done` transaction control;
- `protocol_error` for launch, prompt-write, or readback operations that violate
  the declared state rules;
- indexed readback request and response for phase observations.

Prompt writes are legal only while idle and before launch. `go` is accepted
only after all eight prompt positions have been written exactly once. A new
transaction is not accepted while busy. `done` indicates that all three phases
and their observation snapshots are complete. Results remain stable until
reset or the next legally accepted transaction.

The readback address space exposes, for every phase boundary:

- the selected token ID;
- every raw output logit code required by the frozen RC contract;
- every flattened KV-cache leaf and its shape/index mapping.

The interface is intentionally narrow even when observation storage is large.
Testbenches must not depend on hierarchical access to generated internal
signals. A versioned manifest defines readback regions, element widths,
signedness, shapes, flattening order, and phase names.

## Artifact and provenance design

The authoritative chain is:

```text
frozen three-phase PyTorch trace
            |
            v
integrated FP32 eager PyTorch module
            |
            v
single integrated PT2E ExportedProgram
            |
            v
single compiler-generated SystemVerilog top
```

Every authoritative artifact is produced or captured by a Nix derivation.
`/tmp` may be used for scratch space but is never the only location of source,
RTL, vectors, receipts, manifests, or logs. Receipts record input and output
hashes, model identity, quantization manifest, tool versions, commands, exit
status, runtime, and peak memory. A changed artifact hash denotes a new
reference candidate requiring complete requalification.

The single exported program and single generated SV closure are required
structural invariants. A bundle of phase programs, an SV wrapper instantiating
the three existing closures, or a host-orchestrated sequence fails this gate
even if final tokens agree.

## Verification gates

Qualification proceeds in four ordered gates.

### 1. Integrated FP32 stateful equivalence

Execute the integrated FP32 eager module once and compare its phase-8, phase-9,
and phase-10 tokens, logits, and flattened caches exactly with the frozen
ordered native FP32 trace. This proves stateful composition and cache
continuity before quantization. The first mismatching phase and tensor index is
reported.

### 2. Integrated PT2E equivalence

Convert and export one integrated W4A8 program. Require every per-phase
quantize/dequantize parameter and the complete prefill observation to match the
frozen phase evidence exactly. The integrated decode observations necessarily
become the new stateful W4A8 oracle because they consume the W4A8-produced
cache; the old decode phase observations consumed FP32-produced caches and are
non-compositional. Save and reload the one program and require all observations
to match the accepted converted eager execution exactly. Graph inspection and
the artifact receipt must confirm that there is one `ExportedProgram`
containing the whole sequence. No gate requires W4A8 PT2E tensors to equal FP32
source tensors.

### 3. Generated RTL equivalence

Lower that single program through the existing compiler pipeline and simulate
one generated RTL instance from reset through `done`. Read all observations
through the public readback ABI and compare them bit-for-bit with PT2E. A
timeout or failure to expose all observations is a failure, not partial
qualification.

### 4. Reset and reuse isolation

Run at least the frozen prompt, a distinct prompt, and the frozen prompt again
through the same simulator process with the declared reset sequence. Each run
must equal a fresh-process result, proving that cache, token, and observation
state do not leak between invocations.

Passing these finite gates qualifies the artifact only for the declared frozen
model, prompts, state protocol, and observations. It is not a universal formal
proof or a Full TinyStories claim.

## Failure policy

Exporter, compiler, or lowering defects encountered while producing the single
integrated reference are in scope. Repairs must be semantics-preserving and
must retain the one-program and one-top invariants. Every failed attempt keeps a
durable receipt identifying the exact stage, command, exit status, first useful
diagnostic, wall time, peak RSS, and artifact hashes available at failure.

If wholesale lowering reaches a demonstrated tool-resource frontier, the goal
remains incomplete. A wrapper around phase RTLs may be built only as explicitly
labelled diagnostic evidence; it cannot silently replace the integrated
reference or relax the acceptance gates.

## Completion criteria

This milestone is complete only when all of the following are true:

- one integrated FP32 eager module exactly matches the frozen ordered native
  FP32 trace at every boundary;
- one integrated W4A8 PT2E program exactly preserves the frozen per-phase
  qparams and prefill observation, freezes its W4A8-cache-chained decode
  observations, and matches them after save/reload;
- that one program is lowered wholesale into one compiler-generated SV top;
- one RTL instance executes prefill and both cached decodes with internal cache
  continuity and internal lowest-index token feedback;
- public readback shows exact phase tokens, logits, and cache snapshots;
- reset/reuse isolation passes;
- all authoritative artifacts and receipts are reproducible Nix outputs with
  recorded hashes;
- documentation calls the older three RTLs phase-local evidence, never the
  integrated reference.

Resource fit is deliberately not a completion requirement. Once this reference
is frozen, manual RTL candidates can replace computation, control, and storage
at much finer granularity and much shorter iteration times while being checked
against an independent executable RTL specification and the PyTorch oracle.
