# Reference-guided TinyStories-1M compiler design

**Status:** proposed for implementation planning

## Purpose

Finish the active compiler-pipeline work for Tasks 4–6 by making the full
TinyStories-1M model the first faithful compiler target. The working
kev-gpt-derived TinyStories-1M accelerator is used as a behavioral and
high-level architectural reference, not as source to copy into compiler output
or submitted RTL.

## Scope

In scope:

- the pinned TinyStories-1M checkpoint and tokenizer;
- the existing compiler-generated TinyStories-1M RTL;
- one complete transformer-block token-step vertical slice;
- contract alignment, simulation equivalence, synthesis/resource comparison,
  and FPGA validation;
- later extension of the same backend to TinyStories-3M, 8M, 28M, and 33M.

Out of scope for this phase:

- arbitrary PyTorch models;
- TinyStories-1Layer-21M;
- DDR3 integration or reliability work;
- PCIe transport changes;
- treating the Representative Core as a milestone or acceptance gate.

## Reference contract

The first frozen contract contains:

- model, tokenizer, and source revisions plus hashes;
- exact quantization formats and scales;
- serialized weight/memory image format and hash;
- prompt token IDs and expected 16-token output;
- host/accelerator command interface;
- baseline timing, resource, latency, and throughput metadata.

The contract-alignment gate requires the compiler artifact and kev-gpt reference
to agree on checkpoint, tokenizer, operator semantics, quantization/scales,
tensor layouts, and one-block inputs/outputs before resource differences are
interpreted.

## Architecture and data flow

The compiler retains its staged pipeline:

```text
TinyStories-1M model/export
        -> TinyStories-specific IR
        -> scheduling and memory assignment
        -> parameterized RTL generation
        -> simulation and synthesis
        -> FPGA inference
```

The first implementation target is one complete transformer-block token step,
including weight lookup, quantized arithmetic, memory access, and an observable
checkpoint. The existing compiler RTL is analyzed first; regeneration or
compiler changes follow only after the comparison identifies a concrete waste
or contract defect.

kev-gpt supplies the behavioral oracle and high-level reference choices for
layouts, buffering, scheduling, and quantization. The compiler’s RTL and
templates remain independently maintained.

## Validation gates

1. **Contract alignment:** all model and representation fields match.
2. **Simulation:** the one-block token-step slice matches the reference at the
   agreed checkpoint and final output.
3. **Resource/timing comparison:** report LUT, FF, BRAM, DSP, memory bits,
   operator/buffer counts, Fmax, critical paths, cycles/token, and interface
   overhead for both implementations.
4. **Waste map:** map excess generated structures to compiler stages and source
   operations using provenance annotations.
5. **Full 1M FPGA gate:** exact frozen 16-token output on hardware, three
   matching cold starts, with timing/resource results reported separately.

## Required artifacts

- frozen TinyStories-1M reference manifest;
- existing compiler RTL and extracted slice manifest;
- reference/compiler checkpoint traces;
- synthesis and timing reports for both baselines;
- provenance-linked comparison report;
- machine-readable comparison JSON;
- hardware inference logs and hashes.

## Provenance and NLnet compliance

Existing LLM-assisted history is preserved and explicitly identified. New
substantive assistance is provenance-tracked. kev-gpt source is not copied into
compiler output or submitted RTL. Before reference-derived artifacts are
claimed as funded deliverables, NLnet guidance is requested and recorded.

## Deferred work

DDR3 integration, UberDDR3 reliability, larger-than-BRAM models, PCIe transport
changes, and arbitrary-model generality are separate follow-up work. They do
not block the on-chip TinyStories-1M compiler milestone.
