# Dedicated hardware backend for the first exact fixed-point slice

## Status

Accepted for the bounded TinyStories-1M compiler-salvage investigation.

## Context

The preceding serial-GEMV route completed three bounded attempts without an
observed generated-SV trace. It established durable inputs: an authenticated
TinyStories-1M block-0 Q-projection fixture, a structurally verified
`llm2fpga.fixed` schema, a narrow Calyx lowerer, signed arithmetic cells, and a
known working Calyx-to-Verilator external-memory probe. The missing evidence
is execution of real fixture data through generated hardware.

## Decision

Build a dedicated compiler-owned hardware backend for exactly the captured
block-0 Q-projection `GEMV -> requantization` contract. It consumes only the
verified Task-2 schema receipt and Task-1 fixture. It emits Calyx/SystemVerilog
and a generated Verilator harness that initializes external fixture memories,
observes trace/result memories, and compares them to the fixture bit-for-bit.

The work is divided into independently reviewable gates:

1. One output, 64 ordered signed MACs, and one observed accumulator value.
2. All four rows and 64 outputs, with the full 256-entry accumulator trace.
3. Standalone exact signed requantization using captured scale and saturation.
4. Composition of full GEMV and requantization, with result and trace writes.

Each gate must have a generated-SV testbench result. Python may calculate
fixture expectations but never provides the observed hardware trace. A Calyx
or Yosys structural pass alone is not acceptance.

## Constraints

- The authenticated eager PyTorch fixture remains semantic authority; expected
  source, prompt, tensor names, byte lengths, and SHA-256 values are validated
  before lowering.
- For each ascending `k=0..63`, generated hardware forms
  `signed_i8(activation_code[row][k]) * input_scale_q8_24[k]` and accumulates
  that signed scaled value times `signed_i8(weight_code[output][k])` with
  signed 64-bit two's-complement wrapping. It must not substitute rounded
  `activation_q16_16` values for this accumulator boundary. Q8.24/Q16.16
  rules and per-output scales come solely from the verified schema.
- Requantization is signed-magnitude half-up rounding then signed i8
  saturation. Any other rounding, width, or saturation is rejected first.
- No claim concerns full-model/token inference, boards, DDR3, PCIe,
  Representative Core, arbitrary PyTorch, generic-SCF, or copied kev-gpt RTL.
- Development commands return an artifact or useful diagnostic within 30
  minutes; a complete backend gate is capped at two hours.

## Fresh quit points and pre-mortem

Likely failures are incorrect external-memory timing, signedness/wrap-width
mismatch, loading an incorrect generated-memory shape, and recreating an
oracle rather than observing hardware. The mitigations are a one-output gate,
a separate signed-MAC trace gate, direct fixture-hash checks in harness
generation, and test assertions that require simulator-produced values.

Stop and write an evidence report if either condition holds:

1. Two evidence-backed Gate-1 implementations cannot produce the expected
   first accumulator through generated SV; or
2. Two bounded diagnostics cannot localize an SV mismatch to memory timing,
   MAC arithmetic, or harness observation.

The report retains commands/durations, source and fixture hashes, first
mismatch, generated Futil/SV/harness paths, and a recommendation. It is
evidence about this backend only; it does not decide the wider project.

## Consequences

The first deliverable is smaller than token generation but is real hardware
execution of exact model data. Passing Gate 4 makes the earlier compiler work
a verified fixed-point backend foundation. Failing a quit point gives a
reproducible reason to stop this route without structural-only success claims.
