# Exact equivalence uses a three-tier acceptance ladder

The V=6 PT2E W8A8 representative core will make a universal functional-equivalence claim only after every `6^8` valid context produces exactly the same six raw signed int8 logits and lowest-index argmax token ID in PyTorch and SV. A one-query smoke gate and a four-query frozen regression gate are required iteration milestones, but neither substitutes for the exhaustive gate. Before changing the DUT, the existing Nix-managed SV and Verilator path must receive a baseline cost-attribution profile; subsequent optimizations are applied one at a time, remain Nix-reproducible, and must preserve the same exact contract.

## Consequences

Compilation and simulation latency are first-class blockers to characterize. If the exhaustive gate remains expensive, the project reports that limitation rather than weakening the numerical contract or replacing it with sampled or approximate checks.
