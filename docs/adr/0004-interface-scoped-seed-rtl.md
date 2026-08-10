# Interface-scoped behavioral seed RTL

EQY optimization will compare candidate RTL against a behavioral seed RTL only at an explicit architectural contract: clock/reset, input protocol, output protocol, and externally visible memory transactions. Internal hierarchy, state encoding, pipeline structure, and scratch layout remain outside the contract so RTL optimization does not become tied to the first compiler-produced implementation; PyTorch equivalence remains a separate gate for qualifying the seed and promoted candidates.

The seed qualification bar is the one-input smoke gate plus the frozen-four gate, with reset-isolation evidence and semantic-checkpoint agreement. Broader 24-context and 64-context campaigns remain required for stronger confidence, but do not delay establishing the EQY workflow.

The first EQY milestone uses deterministic abstract synchronous memories and verifies UberDDR3/vendor-memory transport separately against the same memory contract. This keeps compute optimization independent of the DDR3 controller's formal state space.

The first proof is cycle-accurate at the architectural interface: candidate values, handshakes, memory requests, and completion timing must match the seed on every cycle. Latency-insensitive or retimed equivalence is deferred to a separate phase so protocol redesign is not conflated with datapath optimization.

The seed is scoped to one RC model/configuration for the initial workflow. Later models may reuse the ABI and memory contracts, but each requires independent PyTorch qualification before supporting a generality claim.

Within that configuration, EQY must quantify over every legal architectural input, reset, handshake, and abstract-memory trace. The finite PyTorch context suite establishes the seed's semantics; it is not a substitute for universal RTL-to-RTL equivalence.

The qualified seed is materialized by a reproducible Nix derivation containing the RTL source closure, tool inputs, contract, and qualification evidence. Its identity is content-addressed; changing any of those inputs creates a new seed that must pass qualification again.

EQY runs use a staged budget: bounded sanity proofs provide early structural feedback, followed by a full universal proof under declared wall-time and memory limits. A timeout, OOM, or other inconclusive solver result is reported as inconclusive and cannot be promoted to a pass.

Promotion has a three-candidate calibration phase: each of the first three candidates must pass EQY and the full PyTorch gates. Thereafter, EQY-only promotion is allowed only while the seed derivation and architectural/memory/toolchain contracts remain unchanged; any such change restarts PyTorch qualification.

The recursive optimization loop is measurement-driven. Every candidate must produce reproducible area, timing/critical-path, cycle-latency, throughput, memory-traffic/utilization, and DDR3-capacity evidence. These measurements classify the bottleneck as compute-bound or memory-bound and support scaling estimates for RC and the largest model that fits the target FPGA plus DDR3.

Every candidate must also emit a machine-readable optimization receipt containing derivation identities, transformation and tool provenance, measurements, memory evidence, bottleneck classification, and EQY/PyTorch status. An incomplete receipt makes the candidate ineligible for promotion.

Bottleneck classification must be quantitative: derive it from operation counts, achieved compute rate, bytes transferred, achieved bandwidth, and applicable FPGA/DDR3 ceilings in a roofline-style comparison, recording counter sources and assumptions in the receipt.

Candidate selection maintains a Pareto frontier over area, timing, latency, throughput, and DDR3 capacity. Target-board feasibility, correctness, and declared tool-resource limits are hard constraints; workload goals choose among non-dominated candidates rather than an opaque weighted score.

Instrumentation has two required planes: static FPGA reports for area, timing, and critical paths, plus dynamic simulation/trace counters for cycles, operations, stalls, memory traffic, and bandwidth on the same candidate and workload.

The largest model that fits the target is measured through a staged size sweep using the generated RTL, synthesis/resource reports, and DDR3-capacity accounting, followed by search to narrow the feasible boundary. Extrapolation is a fallback only after a recorded tool or resource limit prevents direct probing.

Board validation is gated: a candidate must first pass PyTorch-backed RTL simulation, Yosys, nextpnr-xilinx, and target resource-fit checks. Only then is it executed on hardware to measure physical timing, throughput, and DDR3 behavior.

The workflow distinguishes `RTL-qualified` (host simulation, EQY where applicable, synthesis, place-and-route, and fit) from `hardware-qualified` (all of those plus successful target-board execution and recorded physical DDR3/timing/throughput measurements).

Hardware validation must flash and exercise the exact content-addressed RTL-qualified derivation, recording the Nix/store identity plus bitstream and source-closure hashes; manual rebuilds or edited bitstreams are not valid evidence.

Claims about achieved board clock, DDR3 bandwidth, or end-to-end throughput require measurements from that exact hardware-qualified artifact. Host simulation, Yosys, and nextpnr estimates are screening evidence only.

Hardware receipts must report repeated runs under fixed workloads, clock/reset settings, and initialization conditions, including run-to-run variance and relevant board conditions.

The first campaign optimizes RC as the fast search target, using TinyStories-1M as a transfer and scale probe for the largest practical model and board/resource boundary. TinyStories-1M need not gate every RC iteration.

This optimization workflow is blocked until a baseline RC artifact completes end-to-end inference and passes the RTL-qualified gate. EQY and performance instrumentation apply only after the functional contract has been established.

The immediate engineering priority is therefore baseline RC functional qualification: reproduce and fix the inference path first, then implement EQY and the measurement-driven optimization loop.

The first diagnostic is one deterministic input with internal semantic-checkpoint and scratch-boundary traces, alongside final outputs, so the earliest divergence can be localized before running a broad context campaign.

Baseline acceptance requires exact agreement with the frozen PyTorch oracle for all six observable logits and the selected token under the completion contract. Tolerances, altered oracles, and approximate acceptance do not qualify the baseline.

Qualification declares a deterministic RTL cycle deadline separately from host wall-time, memory, and process limits. Exceeding the cycle deadline is a functional liveness failure; host exhaustion is reported as a tooling/resource result.

## Considered options

- Treat the complete seed RTL structure as the EQY contract. Rejected because it would unnecessarily lock optimization to compiler artifacts.
- Use only top-level input/output values and ignore memory behavior. Rejected because DDR3-backed designs expose meaningful transaction ordering and latency assumptions at the memory boundary.
