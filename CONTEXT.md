# LLM2FPGA Verification Context

This context defines the terms used to establish trustworthy correspondence between the quantized PyTorch model and generated FPGA RTL.

## Verification

**Equivalence gate**:
A finite, reproducible test that accepts the generated implementation only when it exactly matches the frozen PyTorch reference for every required output in the agreed query set.
_Avoid_: similarity check, spot check, approximate validation

**Frozen reference**:
The immutable PT2E W8A8 model state, calibration-derived graph, inputs, expected six logits, and expected token IDs used as the numerical oracle.
_Avoid_: current PyTorch model, live reference

**Representative core**:
A deliberately small TinyStories model instance used as the working unit for end-to-end compiler, simulation, and hardware experiments, subject to its own stated predictive-validity evidence.
_Avoid_: toy model, handwritten model

**Smoke gate**:
The one-query form of the equivalence gate used for rapid diagnosis and iteration.
_Avoid_: informal test, partial equivalence

**First-result smoke bound**:
The 600,000-cycle limit for a direct-source-closure RC smoke run to produce all six observable logits, which must record their exact write cycles.
_Avoid_: arbitrary wall-clock timeout, unbounded smoke run

**Frozen-four gate**:
The four-query form of the equivalence gate used as the reproducible RC regression gate; it does not establish universal equivalence.
_Avoid_: full proof, universal claim

**Exhaustive gate**:
The equivalence gate over every V^8 valid context of the representative core, required for a universal RC-equivalence claim.
_Avoid_: full gate, benchmark run

**High-confidence campaign**:
A documented, coverage-driven Verilator test campaign designed to find mismatches and support a bounded confidence claim, without asserting universal equivalence.
_Avoid_: equivalence proof, random spot check

**Semantic checkpoint**:
A read-only observation at a named model boundary with an explicit PyTorch-to-SV representation map, compared exactly to identify the earliest divergence.
_Avoid_: acceptance output, implementation probe

**Counterexample packet**:
A durable record of the first failing context, exact expected and observed values, semantic-checkpoint trace, and provenance needed to reproduce and minimize a mismatch.
_Avoid_: transient failure log, flaky test report

**Counterexample minimization**:
A deterministic reduction procedure that retains the earliest failing semantic checkpoint, minimizes token changes from the original failing context, and breaks ties lexicographically.
_Avoid_: arbitrary alternate failing context, output-only shrinking

**Reset isolation**:
Evidence that each context produces the same result in the long-lived campaign process as it does in a fresh process and after a distinct predecessor context.
_Avoid_: assumed reset behavior, process-per-input campaign

**Liveness failure**:
Failure to produce all six observable logits by the 600,000-cycle deadline, reported with the last FSM state, memory activity, and run provenance rather than as an undifferentiated wall-clock timeout.
_Avoid_: timeout, simulation hang

**Performance receipt**:
A comparable record for an equivalence-qualified candidate containing its source-closure identity, compile time, peak memory, simulation cycles per second, first-logit timing, and per-context time.
_Avoid_: isolated benchmark number, unqualified speedup

**Timing corpus**:
The frozen-four contexts used for performance receipts: one cold compile and three warm simulation runs reported with median and range, while functional tiers remain single deterministic evidence runs.
_Avoid_: repeated high-confidence campaign, one-off timing

**Timing environment**:
The recorded host resources, tool versions, build flags, and trace state for a performance receipt; timings from a different environment are not claimed as a speedup.
_Avoid_: unqualified benchmark comparison, machine-independent timing

**Trusted-result wall time**:
The primary performance target: source-closure generation and compile time amortized across the campaign, plus simulation through an equivalence-qualified result. Compile time and RTL cycles-to-result remain separate guardrails.
_Avoid_: raw cycles per second, one-time compile timing

**Service objectives**:
Same-host wall-time budgets of at most ten minutes for a fresh smoke run, ninety minutes for the 24-context bug screen, and four hours for the 64-context high-confidence tier. A correct run exceeding its budget is a performance regression to investigate.
_Avoid_: correctness-only success, unbounded campaign

**Optimization ladder**:
The required order for measured candidates: direct source closure and harness improvements, local semantics-preserving plugins or passes, alternative dialect or lowering branches, then upstream changes only when a minimal reproducer proves them unavoidable.
_Avoid_: upstream-first fix, unmeasured rewrite

**Generated-C++ optimization sweep**:
The first no-RTL experiment after the direct-closure baseline: compare `-O1`, `-O2`, and `-O3` under an unchanged coarse Verilator split to measure the build-time versus simulation-speed tradeoff.
_Avoid_: presumed compiler optimum, SV transformation

**TDCC state-encoding sweep**:
The first structural candidate after the selected-input DDR3-backed RC campaign and generated-C++ sweep: vary only Calyx's `tdcc.one-hot-cutoff` control-state encoding and measure it against the unchanged binary-encoding baseline before custom kernels or alternative dialects.
_Avoid_: combined pass sweep, custom RTL first

**Closed-loop optimization**:
A controlled cycle of proposing a bounded candidate, building it, collecting equivalence and performance receipts, then promoting or rejecting it against immutable gates. Candidate generation may be automated, but the gates and accepted baseline are not bypassed.
_Avoid_: autonomous canonical rewrite, benchmark-only search

**Whitelisted optimization space**:
The initial closed-loop search space: named Verilator settings, TDCC state encoding, and named local passes, with one change per candidate. Arbitrary RTL/MLIR edits and memory-layout changes are out of bounds.
_Avoid_: unconstrained code generation, multi-change candidate

**Lexicographic candidate ranking**:
The closed-loop order of preference: exact functional and liveness acceptance first; then the applicable implementation gate, such as complete non-oversubscribed P&R; then trusted-result wall time; then resource slack. Performance never compensates for a failed correctness gate.
_Avoid_: weighted correctness tradeoff, fastest failing candidate

**Human-gated optimization control**:
The loop may auto-run approved candidates in isolated workspaces, but explicit user approval is required to alter an oracle, acceptance gate, DDR3 map, board constraint, or the whitelisted optimization space.
_Avoid_: self-modifying verifier, unapproved design-space expansion

**Experiment ledger**:
A durable, searchable collection of receipts for every candidate, including passes, mismatches, timeouts, and OOM frontiers. Only a promoted candidate changes the current baseline.
_Avoid_: discarded failures, mutable benchmark history

**Deterministic closed-loop foundation**:
The first closed-loop implementation supplies candidate manifests, an executor, receipts, a scorer, and an experiment ledger with rule-based candidate selection. LLM-driven proposal/search is deferred until this baseline data exists.
_Avoid_: agent-first optimizer, unverifiable proposal history

**Multi-fidelity promotion**:
Every candidate receives smoke-gate and timing-corpus screening; the 24-context regression is reserved for candidates that beat the baseline or remove a blocker, and the 64-context tier is reserved for a prospective baseline.
_Avoid_: full-tier screening, benchmark-only promotion

**Exact division policy**:
Floating-point division semantics remain exact in the canonical route. Control compaction may proceed now; parallel execution of independent elements is a later separately gated branch, and reciprocal or approximate division is out of scope.
_Avoid_: reciprocal substitution, approximate divider

**Exact requantization lowering**:
The first new local pass after the TDCC sweep: match only a non-escaping `roundeven → integer zero-point add → clamp → i8` pattern and lower it to exact round-to-nearest-even conversion plus integer clamp.
_Avoid_: generic round rewrite, escaping-intermediate optimization

**Static causal-mask folding**:
The next local pass folds only proven static causal-mask setup and addressing while retaining the existing floating-point select and multiply operations, preserving NaN and signed-zero behavior.
_Avoid_: multiply-by-zero elimination, generic attention rewrite

**Serial static-FP-map kernel**:
A later structural experiment that replaces only proven static 8×2 and 8×8 floating-point maps with a compact counter/stride scheduler, preserving per-element operation order, divider handshakes, and memory-write order. It adds no parallelism.
_Avoid_: generic loop rewrite, concurrent-element scheduler

**Diagnostic surrogate**:
A faster model or simulator used only to investigate behavior or prioritize work; it cannot satisfy the canonical equivalence gate, which requires direct raw-SV Verilator evidence.
_Avoid_: proof model, acceptance simulator

**Coverage corpus**:
A deterministic sparse sequence of contexts selected from the finite RC input domain to cover every token-position combination, maximize token-pair coverage, and include numerical-risk cases.
_Avoid_: prompt list, random sample

**Numerical-risk context**:
A context selected because its frozen PyTorch result approaches a quantization, saturation, rounding, or argmax-tie boundary.
_Avoid_: representative prompt, random outlier

**Bug screen**:
The 24-context first tier of the coverage corpus, intended to find high-leverage mismatches quickly.
_Avoid_: smoke gate, confidence campaign

**High-confidence tier**:
The 64-context second tier of the coverage corpus, run only after the bug screen passes.
_Avoid_: universal proof, exhaustive gate

**Baseline profile**:
A measurement of the unmodified Nix-managed equivalence path that separates artifact generation, compilation, simulator execution, schedule progress, and output comparison costs.
_Avoid_: wall-clock estimate, build impression

**Cost attribution**:
Evidence that assigns time, memory, or execution-rate cost to a specific generated SV, Verilator, C++, simulator, or schedule component.
_Avoid_: optimization guess, generic profiling

**Observable result**:
The six raw signed int8 logits and the lowest-index argmax token ID sampled after the SV completion contract is satisfied.
_Avoid_: approximate logits, formatted output

**Canonical equivalence route**:
A lowering, RTL, and simulation route eligible to support an exact equivalence claim because it is checked against the frozen reference by the equivalence gate.
_Avoid_: default pipeline, trusted backend

**Behavioral seed RTL**:
The first RTL implementation that has passed the agreed PyTorch equivalence gate and is retained as the behavioral reference for RTL-to-RTL optimization.
_Avoid_: golden source, permanently correct RTL, implementation template

The minimum qualification bar is the one-input smoke gate plus the frozen-four gate, reset-isolation evidence, and semantic-checkpoint agreement. The 24-context bug screen and 64-context high-confidence tier strengthen the seed's trust claim but are not prerequisites for building the initial EQY flow.

**Architectural contract**:
The externally observable clock/reset, input, output, and memory-transaction behavior that an optimized RTL implementation must preserve; it excludes internal hierarchy, state encoding, pipeline structure, and scratch layout.
_Avoid_: internal RTL shape, source-level structure, synthesis-preserved hierarchy

**Abstract memory model**:
A deterministic synchronous memory model used for the first EQY compute comparison, with explicit assumptions for legal contents, request, response, and completion behavior but no implementation commitment to on-chip RAM, DDR3, or a vendor model.
_Avoid_: DDR3 model, vendor memory, unconstrained memory black box

**Staged validation roadmap**:
The ordered program starts direct raw-SV closure and host-only DDR3 integration in parallel, reaches one exact DDR3-backed RC input, then its selected-input campaign, a bounded TinyStories-1M run through the same lowering, SV, Yosys, and nextpnr-xilinx path, and finally a deliberate choice between scaling and further RC optimization. A scale estimate is the fallback only when that direct probe reaches a recorded resource limit.
_Avoid_: scale-first rewrite, exhaustive-simulation prerequisite

**DDR3 externalization**:
Immediate host-only migration of selected immutable model constants, beginning with weights, from on-chip fixtures to DDR3 through UberDDR3 RTL and the manufacturer's memory model; it requires a new selected-input equivalence campaign.
_Avoid_: memory-model-only test, unchanged RC fixture

**Host-only DDR3 integration**:
Concurrent work on the direct raw-SV closure, UberDDR3 adapter, and manufacturer-model simulation path, requiring no physical board. Its first end-to-end milestone is one exact DDR3-backed RC result against frozen PyTorch.
_Avoid_: board-dependent bring-up, on-chip-only prerequisite

**ABI-preserving DDR3 adapter**:
A generated or parameterized layer that routes selected immutable learned-tensor ports from the generated RC's existing logical external-memory ABI onto UberDDR3's bounded user port while preserving address, byte, and completion-order semantics. It does not change the compiler's memory ABI.
_Avoid_: lowering ABI rewrite, handwired per-tensor DDR3 path

**DDR3 compatibility audit**:
An automated comparison of the RC external-memory ABI and UberDDR3 user-port contract that proves width, ordering, and outstanding-request assumptions before choosing the adapter's arbitration design.
_Avoid_: assumed compatible port, speculative arbiter

**Pinned DDR3 source closure**:
The UberDDR3 RTL, board wrapper, and manufacturer's DDR3 model are each identified by revision or content hash and included in every DDR3 receipt, never read from an ambient checkout.
_Avoid_: mutable local dependency, unproven simulation source

**Learned-tensor DDR3 boundary**:
The first DDR3-backed RC moves every learned tensor—embeddings, weights, biases, and positional tables—through UberDDR3. Scalar arithmetic, quantization, and mask constants, plus token input, mutable activations/scratch, and output buffers, remain local for a separate later experiment.
_Avoid_: partial-weight-only DDR3 path, all-memory DDR3 migration

**Split DDR3 memory service**:
The initial host-only adapter uses DDR3 only for immutable learned-tensor ports and retains existing local memories for token input, mutable scratch/activation state, and observable output buffers.
_Avoid_: all-ports adapter, off-chip output buffer

**Receipt-derived DDR3 mapping**:
The adapter's learned-tensor port classification, logical address map, byte layout, and source hashes are generated from the existing `memory-abi.json` and `calyx_memory_bindings` receipts, with a deterministic manifest consumed by simulation and synthesis.
_Avoid_: hand-maintained tensor-port lists, unbound address map

**Layout-preserving DDR3 transport**:
The first DDR3-backed RC retains the frozen tensor image's logical addresses and byte layout verbatim and uses UberDDR3 as a read-only transport layer. Packing, caching, and address remapping are separate later optimization branches.
_Avoid_: simultaneous memory-layout rewrite, repacked baseline

**DDR3 transport contract**:
A deterministic UberDDR3 microcase that verifies exact data, address translation, and completion ordering against the manufacturer's DDR3 model before full RC simulation.
_Avoid_: full-model-first integration, waveform-only confidence

**DDR3 acceptance tiers**:
The DDR3-backed RC reuses the same one-input smoke, 24-context bug screen, 64-context high-confidence tier, and semantic checkpoint map as the on-chip RC. Its wall-time budgets are set only after measuring the first DDR3 smoke run.
_Avoid_: informal DDR3 prompts, copied on-chip timing budget

**TinyStories-1M scale probe**:
A bounded attempt to run TinyStories-1M through the same accepted pipeline as RC, emit SV, then obtain a Yosys/nextpnr-xilinx resource-utilization report. It records the last completed stage and resource use if it cannot finish.
_Avoid_: estimate-first scaling, unbounded build

**Bounded scale-probe receipt**:
A per-stage record with predeclared wall-time and memory limits, tool and input provenance, peak resource use, logs, and the last completed artifact. Timeout or OOM is a valid frontier measurement.
_Avoid_: abandoned build, indefinite process

**Scale-probe resource limits**:
The TinyStories-1M probe uses a 26 GiB per-process memory cap, a four-hour cap per stage, and a twelve-hour total cap, checkpointing every successful stage.
_Avoid_: host-OOM frontier, uncheckpointed overnight build

**Realizable DDR3 synthesis top**:
The TinyStories-1M resource probe synthesizes the accepted DDR3-backed top with a bounded UberDDR3 interface, rather than the historical compute-only `main_1` shell with thousands of logical memory ports.
_Avoid_: memory-port-shell utilization, compute-only FPGA claim

**DDR3 simulation/synthesis split**:
The manufacturer's DDR3 model is used only in simulation. Synthesis and P&R include synthesizable UberDDR3, the accelerator, and the board-level DDR3 interface and constraints; off-chip DRAM capacity is reported separately.
_Avoid_: synthesizing behavioral memory, controller-free DDR3 utilization

**Board-constrained DDR3 scale probe**:
The DDR3-backed TinyStories-1M resource probe targets the YPCB-00338-1P1 XC7K480T with its real DDR3 pin and clock constraints, not the existing four-pin P&R-only probe.
_Avoid_: generic-device utilization, probe-XDC fit claim

**Scale estimate**:
A fallback, measured extrapolation used only when the TinyStories-1M scale probe reaches a recorded resource limit. It reports assumptions, memory demand, generated-artifact size, compile and simulation cost, cycles per result, and projected throughput; it is not a scaled equivalence claim.
_Avoid_: scaling proof, size-only projection

**Deferred formal track**:
A later, separately scoped investigation of formal or compositional proof, which must first establish an extractable formal specification of the frozen PyTorch semantics. It does not block the Verilator evidence path.
_Avoid_: current acceptance gate, assumed PyTorch formal model

**Optimization branch**:
A candidate change intended to reduce cost or alter implementation structure, which remains exploratory until it passes the canonical equivalence route's acceptance gate.
_Avoid_: replacement pipeline, presumed-equivalent variant

**Promotion ladder**:
An optimization candidate needs a smoke-gate pass before performance profiling, the 24-context bug screen before becoming the working baseline, and the 64-context high-confidence tier before supporting a bounded confidence claim.
_Avoid_: benchmark-only promotion, smoke-only confidence claim

**Direct source closure**:
An explicitly ordered and hash-verified set of generated SV and required support sources supplied directly to Verilator, without Morty packaging.
_Avoid_: Morty bundle, implicit source set

**Compatibility normalization**:
A deterministic, hash-recorded, narrowly scoped source transformation needed solely for simulator compatibility and independently tested; any other transformation is an optimization branch subject to the full equivalence gate.
_Avoid_: silent patch, untracked RTL rewrite

**Historical Morty artifact**:
A previously generated bundled-SV artifact retained only as historical evidence, never as an input, oracle, control, or acceptance dependency of the canonical route.
_Avoid_: baseline, fallback, reference route
