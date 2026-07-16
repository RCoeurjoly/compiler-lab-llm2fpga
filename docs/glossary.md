# Glossary

- **FTS** — Full TinyStories model and pipeline, using the 50,257-token
  vocabulary configuration.
- **RC** — Representative core, the reduced TinyStories-derived model used for
  rapid experimentation. The current frozen quantized RC is
  `tinystories-w8a8-rc-study-mask9-vocab6-width2`: vocabulary 6, hidden size
  2, two layers, one attention head, and eight-token context.
- **Fast compiler loop** — The model/frontend through MLIR, Calyx, and RTLIL,
  stopping before Yosys technology mapping and FPGA synthesis.
- **RTLIL** — The hardware-oriented intermediate representation used as the
  fast-loop success boundary and as input to the deferred synthesis stages.
- **Deferred validation** — Full Yosys/Xilinx synthesis run on selected fast
  loop outputs to measure resource utilization and final hardware behavior.
- **Validated optimization claim** — A change whose semantic behavior,
  resource effect, and iteration cost are all measured and reported.
- **Calyx-external memory** — A Calyx memory cell marked `@external(1)` and
  moved to the generated top-level wrapper. This creates an explicit memory-port
  boundary around the compute component, but does not imply off-chip DDR memory.
- **Memory-blackbox diagnostic** — A synthesis ablation that preserves a memory
  module's interface while omitting its implementation to isolate storage-driven
  compiler cost and retained shell logic. It is not a completed external-memory
  optimization claim.
- **External-memory architecture** — A realizable mapping from logical model
  memories onto a bounded physical memory service, including protocol, port
  scheduling, storage placement, bandwidth, latency, and retained on-chip
  buffering. DDR3 is one possible implementation of that service.
- **PT2E W8A8** — The primary Task 6 numerical reference: PyTorch PT2E static
  quantization configured for 8-bit weights and activations, with frozen
  calibration and a recorded converted graph. For the frozen RC it is the sole
  acceptance oracle; any exhaustive expected-output shards are derived directly
  from it rather than from a hand-written integer model.
- **SmoothQuant W8A8** — A separate scale-migration variant that may be applied
  before PT2E W8A8; it is not part of the primary reference by default.
- **Test target** — One of the full-model, representative-core, or isolated
  component scopes used to evaluate an optimization claim.
- **Frozen-oracle smoke conformance** — Equality of the frozen reference
  cases' six raw int8 output codes and lowest-index argmax token IDs. It is a
  fast regression gate, not general functional equivalence.
- **RC observable functional equivalence** — For the fixed V=6, context-8 RC,
  exhaustive equality of six raw int8 output codes and the lowest-index argmax
  token ID for all `6^8 = 1,679,616` token contexts after deterministic reset.
  It proves observable behavior only at that fixed RC interface. A local
  approximation that passes this gate is RC-observationally equivalent, not
  thereby operation-semantic or Full TinyStories equivalent.
- **Image-backed SV fixture** — A deterministic SV memory service that supplies
  the frozen RC model image. It enables exhaustive numerical comparison after
  lowering or memory externalization; it is distinct from DDR3-controller and
  board validation.
- **Testable RC SV implementation** — Generated SV with documented,
  testbench-accessible eight-token inputs; six raw output codes and token-ID
  outputs; and deterministic clock, reset, launch, completion, and sampling
  semantics. A `done`-only or internally probed module is not testable RC SV.
- **Provisional RC candidate** — A testable experimental route that has passed
  only the four-case frozen PT2E smoke oracle. It cannot be called canonical or
  RC observably functionally equivalent until it passes the full `6^8` sweep.
- **RC exhaustive-sweep manifest** — The durable record that hashes and joins
  deterministic base-six context-range shards, proving disjoint complete
  coverage of the `6^8` RC inputs and recording reference/DUT provenance.
- **RC counterexample packet** — A durable mismatch or timeout record with its
  token context, PT2E and SV outputs, provenance hashes, timing contract, and
  cycle/handshake trace. It rejects the candidate but is a reusable research
  result.
- **RC timing contract** — A versioned conservative maximum number of SV cycles
  from documented launch to documented output sampling. The verifier records
  observed latency and rejects completion beyond this bound; it does not try to
  match PyTorch cycle timing.
