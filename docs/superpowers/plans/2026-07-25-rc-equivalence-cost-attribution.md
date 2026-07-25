# RC equivalence cost-attribution and deblocking plan

## Objective

Demonstrate exact PyTorch-versus-SV equivalence for the frozen V=6 PT2E W8A8 representative core while making compilation and simulation costs measurable and reducible.

## Contract

- Smoke gate: one frozen query, exact six logits and token ID, target under 60 seconds after compilation.
- Full gate: all four frozen queries, exact six logits and token ID, target under 10 minutes after compilation.
- Compilation happens once per SV artifact and is reused for all queries.
- The frozen PT2E W8A8 outputs remain the numerical oracle.
- No structural DUT transformation is accepted without rerunning the same gate.
- All durable artifacts are produced by Nix derivations; no `/tmp` result is evidence.

## Tasks

- [x] Inspect the existing generated SV: module counts, line/byte sizes, HardFloat usage, FSM/control structure, memory ports, and wide expressions.
- [x] Build a Nix baseline profile for the exact existing SV, fixture, image, and pinned Verilator.
- [ ] Measure SV normalization, Verilator translation, C++ compilation, peak memory, simulator startup, cycles/second, first memory request, first output, and terminal `done`.
- [ ] Inspect Verilator C++ partitions and identify the largest/slowest translation units and symbols.
- [ ] Run the one-query smoke gate using the cached binary.
- [ ] Run the four-query full gate using the same cached binary.
- [ ] Select only the largest measured cost center for the first optimization.
- [ ] Re-run the baseline profile and both gates; retain the change only if cost improves and exact outputs remain equal.
- [ ] Repeat one change at a time until the latency targets are met or a reproducible verification-scalability blocker is documented.

## Non-goals

- No Yosys, nextpnr, DDR3, host-tokenizer, or board-validation work before this equivalence path is characterized.
- No weakening exact equality to tolerances, sampled contexts, or component-only evidence.
