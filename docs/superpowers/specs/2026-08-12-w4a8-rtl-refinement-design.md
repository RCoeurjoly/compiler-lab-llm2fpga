# W4A8 compiler oracle and manual RTL refinement

Date: 2026-08-12

## Purpose

Build a fully on-chip W4A8 representative-core inference implementation that
fits, places, and routes on `xc7k480tffg1156-1`. The existing compiler route
remains the semantic authority: it first produces functionally validated W4A8
RTL, after which a manually optimized, memory-centric implementation is refined
against that RTL.

This design responds to the mapped W8A8 baseline. Although the frozen model is
only vocabulary 6, hidden size 2, and two layers, its generated implementation
requires 776,182 `SLICE_LUTX` sites against 597,200 available. Model dimensions
alone therefore do not explain the failure. The immediate problem is the
spatial expansion of computation and control into LUT logic, with no block RAM
used for learned tensors. The new implementation will serialize and reuse
compute while making learned storage explicit.

The first milestone contains no DDR3 controller and performs no DDR3 traffic.
DDR3 remains a later scaling mechanism under ADR 0005.

## Semantic refinement chain

The evidence chain is:

```text
frozen PyTorch W4A8 model
          |
          | numerical differential tests
          v
compiler-generated W4A8 RTL oracle
          |
          | transaction-level refinement
          v
manual memory-centric W4A8 RTL
          |
          | mapped synthesis and constrained P&R
          v
XC7K480T implementation evidence
```

W4A8 is a new frozen numerical contract. The existing W8A8 RTL cannot be its
bit-exact oracle. Quantized tensors, zero points, scales, rounding, saturation,
accumulator widths, logits, and lowest-index argmax behavior must be frozen and
recorded before the W4A8 generated RTL is accepted as the reference.

The manually optimized implementation may differ arbitrarily in latency,
internal state, memory layout, and scheduling. Its public behavior must match
the oracle at transaction boundaries after an ordered reset.

## Ownership boundaries

The compiler pipeline owns:

- PyTorch model construction and W4A8 quantization;
- frozen tensor and quantization provenance;
- compiler lowering and generated reference RTL;
- PyTorch-to-generated-RTL simulation;
- the canonical external inference transaction.

The hardware refinement layer owns:

- the versioned W4 packing and memory-layout manifest;
- synthesis-visible initialized weight memories;
- shared arithmetic engines and local storage;
- the explicit layer, operation, and token sequencer;
- optimized-RTL differential and formal harnesses;
- synthesis and place-and-route evidence.

Both sides expose a latency-insensitive request/result contract containing
reset, request acceptance, the fixed token context, completion, six signed
logits, and lowest-index argmax. Backpressure and input-stability rules are
declared by the wrapper rather than inferred from either implementation.

## Reproducible artifacts

Every authoritative stage is a cacheable Nix derivation. `/tmp` may hold build
scratch but is never the only copy of a model, manifest, RTL file, memory image,
test result, proof result, or implementation report.

The frozen W4A8 bundle records at least:

- source model identity and revision;
- complete model geometry and input contract;
- every quantized tensor and its logical shape;
- signedness, bit width, scale, zero point, rounding, and saturation rules;
- accumulator range assumptions and selected width;
- packed-memory format, order, padding, and checksums;
- PyTorch export, compiler, simulator, Yosys, and nextpnr provenance;
- hashes linking PyTorch data, compiler RTL, optimized RTL, and memory images.

One machine-readable manifest is consumed by the Python reference, image
packer, simulation harnesses, and optimized RTL generation or parameters. A
schema version prevents silent interpretation drift.

Unlike the earlier synthesis probe, the fitting milestone must not discard
`initial` weight loading with `--ignore-initial`. Yosys must either infer
initialized block RAM from a supported representation or instantiate an
equivalent initialized 7-series memory structure. Simulation and synthesis
must consume byte-identical packed data.

## W4A8 compiler baseline

The first checkpoint changes weight precision to signed W4 while retaining
signed A8 activations and the existing tiny serving contract. It uses the
current lowering path without manual RTL optimization, so it establishes a
clean semantic oracle and measures what precision reduction alone changes.

Acceptance requires:

1. Frozen PyTorch inference with deterministic reset and inputs.
2. Successful lowering to W4A8 SystemVerilog through the current pipeline.
3. PyTorch versus generated-RTL agreement on context 0, the frozen-four suite,
   and the ordered reset sequence.
4. Exhaustive agreement over all `6^8 = 1,679,616` legal contexts before a
   universal finite-domain equivalence claim is made.
5. A mapped Yosys and nextpnr baseline, whether it fits or fails, with resource,
   runtime, memory, failure-stage, and timing-frontier evidence.

Any quantization or lowering defect is fixed before manual optimization starts;
the optimized implementation must not compensate for an unstable oracle.

## Manual microarchitecture

The initial optimized design is intentionally simple:

- signed W4 weights packed into initialized `RAMB36E1`-inferable memories;
- signed A8 activation storage in registers or block RAM as dictated by size;
- one shared, sequential W4-by-A8 GEMV engine;
- range-proven accumulators, initially favoring clarity over minimum width;
- exact shared requantization, saturation, and nonlinear operations;
- on-chip activation, scratch, and context or KV state;
- a small explicit sequencer that schedules layers and token operations;
- the common latency-insensitive request/result wrapper.

The XC7K480T provides 7-series DSP48E1 blocks and BRAM, not the UltraScale+
DSP48E2 and UltraRAM used by kev-gpt. Its architectural lessons—resident packed
weights, explicit memory banking, shared GEMV, and serialized control—apply,
but its primitive packing and timing assumptions do not. The first GEMV may use
plain synthesizable arithmetic. A DSP48E1 mapping is introduced only after the
simple engine is bit-exact and its accumulator bounds are proven.

The first milestone excludes multi-stream batching, speculative decoding,
aggressive DSP packing, dual-cohort weight sharing, performance-oriented
operator fusion, and DDR3. Those optimizations are evaluated only after a legal
single-stream implementation exists.

## Incremental replacement strategy

Manual work proceeds one independently verifiable boundary at a time:

1. Freeze and validate compiler-generated W4A8 RTL.
2. Add the common wrapper and transaction-level differential harness.
3. Implement and verify a sequential W4-by-A8 GEMV.
4. Introduce packed, initialized BRAM weight storage.
5. Replace compiler-expanded linear operations with the shared engine.
6. Replace requantization and nonlinear operations with shared exact units.
7. Move activation, scratch, and context or KV state into explicit local
   memories where beneficial.
8. Integrate the complete layer/token sequencer.
9. Only then evaluate DSP48E1 mapping, lane count, scheduling, and throughput.

After each meaningful replacement, run its local verification gate, the
end-to-end frozen differential suite, mapped Yosys, and—when resource size is
plausible—nextpnr. This produces a resource curve that attributes gains or
regressions to individual architectural changes.

## Verification design

No single formal technique is required to span the entire latency-changing
rewrite. Three complementary layers are used.

### Simulation oracle

PyTorch and the compiler RTL must pass the established context-0, frozen-four,
and ordered-reset gates. The optimized RTL is then driven with the identical
transactions and compared against both recorded oracle results and, where
practical, a co-simulated generated RTL instance. Failures record the first
context, raw logits, argmax, handshake trace, and relevant internal checkpoint.

The finite `6^8` domain permits exhaustive differential simulation. Passing it
supports a universal claim only for the frozen input domain and reset/protocol
assumptions, not for arbitrary malformed transactions or unbounded state.

### EQY block equivalence

EQY is used where a generated operation and its replacement can be wrapped into
compatible, bounded interfaces with aligned or explicitly normalized latency.
Candidates include GEMV transactions, requantization, saturation, activation
functions, counters, and memory-address transformations. Whole-design EQY is
not a prerequisite because serialization substantially changes state and
latency.

### SBY properties and refinement

SBY proves local safety and protocol properties such as:

- ordered reset leaves no stale transaction or context state;
- requests are neither duplicated nor silently dropped;
- weight, activation, scratch, and KV addresses remain in range;
- accumulator values remain inside the declared mathematical bound;
- completion cannot occur before all required operations;
- results remain stable while valid and unconsumed;
- under the declared environment assumptions, an accepted request completes
  within a derived finite bound.

A top-level latency-insensitive refinement miter may run oracle and optimized
transactions with different schedules, store their completed results, and
assert equal logits and argmax once both finish. Its bounded or unbounded claim
must be stated exactly in the proof receipt.

## Failure handling and evidence

Every gate produces a receipt even on failure. It identifies the exact model
and RTL hashes, command, exit status, failed stage, wall time, peak RSS, and the
first useful diagnostic. Synthesis and P&R logs are retained in compressed
form rather than streamed interactively.

Arithmetic mismatch stops architectural substitution at the responsible
boundary. A formal timeout is reported as inconclusive, never as a pass. A
resource failure records mapped primitives and physical-site counts. A timing
failure records the constraint, achieved timing when legal, and reported
critical paths. No Fmax is claimed from an unplaced or unrouted design.

## Licensing and provenance

kev-gpt is an architectural reference for on-chip weights and shared compute.
The user reports direct confirmation from its author that it is GPL, although
the inspected upstream revision `d259733627e9315278cfa95b7545b7e30cfa91a2`
does not contain a visible license file. Before copying or adapting its source,
the project must record the applicable GPL version or obtain an upstream
license artifact and confirm repository compatibility.

Copied or adapted files must carry the required copyright, license, source,
and modification notices. Independently written modules may cite kev-gpt as
architectural inspiration without claiming code derivation. Until the license
version and compatibility are documented, implementation should study its
interfaces and organization but not import source text.

## Fit milestone and completion criteria

The first milestone prioritizes correctness and legal implementation over
throughput. It is complete only when all of the following hold:

- the frozen PyTorch W4A8 contract is fully recorded;
- generated W4A8 RTL passes the required PyTorch differential gates;
- optimized RTL passes the required refinement suite;
- local formal properties pass, with proof bounds and assumptions recorded;
- learned weights are present in synthesis-visible initialized on-chip memory;
- mapped Yosys reports LUT, FF, BRAM, DSP, and carry utilization;
- nextpnr successfully packs, places, and routes `xc7k480tffg1156-1`;
- a legal clock result and critical paths are recorded;
- tool runtimes and peak memory are recorded;
- no DDR3 controller or DDR3 token-loop traffic exists.

After this gate, optimization may explore DSP48E1 packing, additional GEMV
lanes, deeper pipelining, operation fusion, and higher throughput. DDR3 is
introduced later only to scale weights or state beyond the measured on-chip
capacity.
