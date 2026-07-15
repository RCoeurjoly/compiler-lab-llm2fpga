# Glossary

- **FTS** — Full TinyStories model and pipeline, using the 50,257-token
  vocabulary configuration.
- **RC** — Representative core, the reduced TinyStories-derived model used for
  rapid experimentation; current minimum shape uses vocabulary 32, hidden size
  2, two layers, one attention head, and four positions.
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
  calibration and a recorded converted graph.
- **SmoothQuant W8A8** — A separate scale-migration variant that may be applied
  before PT2E W8A8; it is not part of the primary reference by default.
- **Test target** — One of the full-model, representative-core, or isolated
  component scopes used to evaluate an optimization claim.
