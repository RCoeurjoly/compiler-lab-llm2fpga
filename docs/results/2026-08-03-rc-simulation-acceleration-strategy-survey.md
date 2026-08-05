# RC simulation and compilation acceleration strategy survey

## Decision summary

For the current V=6 PT2E W8A8 representative core, prioritize shrinking and
regularizing generated compute/control over a new memory hierarchy or sparse
attention engine. The evidence is a 9.95 MB native Calyx SV module, enormous
generated FSM expressions, and a first-output trace with equal memory request
and completion counts. In that observed pre-output window, the execution is
not stalled waiting for the fixture's external memory service; it is advancing
through a serialized static schedule that includes repeated floating-point
work. This is not yet a complete wall-clock attribution across Calyx emission,
Verilator translation, C++ compilation, and runtime.

The safe immediate work is simulator engineering: reuse one quiet compiled
fixture, preserve live runtime controls, use only conservative simulation-side
expression rewrites, and time Verilator code generation separately from
generated-C++ build and runtime.  That removed a fixture bug which had caused
all frozen cases to start together and made watchdog controls ineffective. It
also removes avoidable iteration cost and yields a credible baseline, but it
cannot remove the Calyx-to-SV generation cost or serialized datapath latency.

The first structural experiment should be an exact reusable linear or
attention kernel with a compact counter/stride scheduler. It must preserve
operand order, Q/DQ behavior, memory ABI, and the frozen raw-logit gate. Only
then should static causal-mask specialization and fusion/direct addressing be
considered. Approximate nonlinear units, retraining-based sparsity, or a
lower-precision model are valuable research branches, but not optimizations of
the canonical exact W8A8 claim.

The papers motivate these architecture directions; they do not establish a
speedup for this Calyx/Verilator pipeline. Each projected benefit below is a
measured hypothesis until its generated artifact and acceptance results exist.

## What the current measurements imply

| Evidence | Consequence |
|---|---|
| Native SV is about 9.95 MB and contains a 6,993-arm priority ternary plus an 8,854-term scalar OR. | Elaborator and generated-C++ function size are concrete targets. Bounded continuous pages are a conservative simulation-side hypothesis; the synthetic four-state check validates the rewrite class, while the real-DUT compile/run must measure its effect. |
| A 340-second cached run reached 304,265 cycles with 20,983 memory requests and completions, and still had no first output. | There is no observed missing-response or external-memory-stall diagnosis. A memory broker is not the first optimization to assume. |
| The dominant traced region includes `std_mulFN_36` inside a repeated Calyx loop. | This proves a serialized floating-point multiply region, not its tensor provenance. Attribute it before selecting a compact control kernel or an integer path. |
| A fresh native Calyx-to-SV build remained in single-core emission for more than 38 minutes before the bounded probe was stopped, without reaching Verilator. | Verilator-only changes cannot cure all iteration cost. Structural lowering must reduce static-control expansion too. |

The request/completion result is a bounded first-output diagnosis, not proof
that memory is never a bottleneck. It determines experiment order only.

## Live Verilator compilation structure

The historical cold baseline used `--output-split 100` and
`--output-split-cfuncs 50`. It produced 18,694 C++ files (136,070,102 bytes)
and four headers (6,669,019 bytes); 18,466 of those C++ files (98.8%) were
smaller than 16 KiB. Make compiles each generated unit independently, so this
is a C++ process/fan-out problem as much as a source-volume problem.  The
canonical reusable fixture therefore now uses coarse `10000/10000` splitting
with eight model threads, where the repaired dynamic fixture produced 381 C++
files (197,053,017 bytes).  Its one-cycle watchdog finishes in about 0.01 s;
the earlier no-watchdog runs were confounded by dead-code-eliminated plusargs,
not valid evidence about the split setting.

The controlled matrix compares coarse threaded and single-thread points with a
`500/250` threaded point.  It does not treat the `100/50` outcome as a valid
runtime baseline, though that point remains useful as compilation-fan-out
evidence.

The runner intentionally keeps Verilator's own `-O3` separate from the
generated-C++ optimization choice. Its current `-CFLAGS -O3` is the final GCC
optimization flag, overriding Verilator's fast-path `-Os`; a controlled
`-O1/-O2/-O3` C++ optimization sweep is consequently a high-value next
experiment, with build time and runtime both measured. These are local
artifact facts and proposed experiments, not claims drawn from the papers.

## Recommended strategy ladder

| Priority | Strategy and paper evidence | Why it fits this RC | Exact W8A8 status | First experiment |
|---:|---|---|---|---|
| 0 | Quiet reusable fixture, conservative continuous paging, split Verilator/codegen/C++ timing. | Eliminates log traffic and recompiles for corpus selection; attributes the build cost before a design change. | Full integration still required: pages are stable-value equivalent after combinational settling, but add delta cycles. | Cached binary: bounded progress probe, one-case smoke, then four-case raw-logit gate. |
| 1 | Parameterized reusable compute/control kernels and compact scheduling; LoopLynx and FlightLLM. | Directly attacks cloned/static schedule expansion that makes Calyx emission and Verilator elaboration expensive. | Potentially exact if arithmetic order, handshakes, visible latency assumptions, and memory ordering remain unchanged. | First attribute `std_mulFN_36`; replace only the proven source region with counter/stride control. |
| 2 | Integer linear datapaths and explicit requantization; FQ-BERT and the integer-only transformer study. | W8A8 graph regions still carry floating Q/DQ and f32 nonlinear work. Proven integer regions can avoid generic floating multiply machinery. | Conditional: match scale, zero point, rounding, saturation, reduction order, and every frozen raw code. W8A8 does not prove integer-only equivalence. | Implement one `i8 × i8 -> i32` projection/MLP path against a reference test. |
| 3 | Fixed-`S=8` causal-mask specialization; FlightLLM. | A causal `8 × 8` score matrix has 28 masked and 36 valid positions. It could shrink score/softmax/value work but not Q/K projections. | Potentially exact only after inspecting the actual lowered mask slice, `where`, max, exp, and reduction semantics in each attention region. | Census the concrete mask paths; generate a triangular schedule only if it preserves the reduction contract. |
| 4 | Fuse short-lived activations and use direct addressing; LoopLynx, FlightLLM, and integer-only address mapping. | Fewer materialized arrays, state machines, and control groups reduce emitted-SV size even when memory is not stalled. | Potentially exact; do not reassociate f32 reductions. | Fuse one proven producer-consumer pair inside the priority-1 kernel. |
| 5 | Lossless weight packing and wider/batched memory operations; MEADOW. | May shrink wrapper/control and request count, but the current trace does not identify memory latency as critical. | Potentially exact if byte layout, collisions, read-after-write, and response timing are preserved. | Measure one packed-read path only after priorities 1--4. |
| 6 | KV-cache/dataflow reuse for multi-token decode. | The current adapter has `use_cache=False`; this changes the model/interface regime and cannot fix the first forward pass. | Exact in principle, but adds a stateful interface and test regime. | Defer until first-output behavior is tractable. |

## Separate numerical-model tracks

These are not general operation-level or Full TinyStories equivalence
optimizations. A candidate may still be investigated for this frozen RC, but
can become canonical only through the complete RC observable-equivalence gate;
until then it is an explicitly scoped provisional branch.

| Strategy | Why it is not a canonical exact optimization |
|---|---|
| LUT/PWL/polynomial `exp`, approximate reciprocal/sqrt, approximate layer norm or GELU | PEANO-ViT and QUARK intentionally trade numerical behavior for cheaper nonlinear hardware. A polynomial-exp candidate is not a general PyTorch-to-SV equivalence proof. |
| Structured N:M pruning or Top-k/sparse attention | The N:M and length-adaptive sparse-attention papers depend on pruned weights or an altered attention algorithm and normally report accuracy rather than raw-logit identity. |
| W4/BFP/ternary/binary/vector-quantized/block-circulant models | These alter model, calibration, or representation and belong to a retrain/distill/calibrate branch. |

## Measurement and promotion protocol

Treat iteration time as
`T_Calyx + T_normalize + T_Verilate + T_C++ + N_cases × T_run`.
Keep SV, image, reference, and semantic simulator options invariant. For every
point record generated-SV and C++ bytes, front-end time, C++ build time,
binary size, bounded-run cycles/second, and memory where available. Vary one
configuration factor at a time; treat kernel changes as separate design
experiments.

Promotion is strict:

1. A quiet bounded probe reaches a heartbeat or produces a result.
2. The selected configuration passes a one-case raw-code smoke test.
3. It passes the unchanged four-case exact smoke gate: six signed int8 logits
   and lowest-index argmax per frozen context. This makes a
   semantics-affecting candidate provisional, not canonical.
4. Before a semantics-affecting candidate is adopted as canonical, it passes
   deterministic durable shards covering all `6^8 = 1,679,616` token
   contexts, with the same six raw codes and lowest-index argmax. The merged
   manifest must prove complete, non-overlapping coverage and preserve input,
   SV, runner, and reference provenance.

The synthetic four-state normalizer check validates only the lexical rewrite.
It cannot replace the full integration gate, especially because continuous
page nets introduce delta cycles.

## Current Calyx backend experiment order

There is no pinned-CIRCT switch that simply turns down static-control
expansion. The active native-Calyx invocation is `calyx ... -b verilog
--synthesis --nested -d papercut`. Two tempting alternatives are already
negative evidence: flattening rather than keeping `--nested` doubled SV from
9,955,404 to 18,894,272 bytes and then OOMed in Verilator; the no-synthesis
variant did not yield a usable artifact in a bounded run. Keep both current
options.

The smallest defensible backend sweep is therefore:

1. Emit a pass trace on existing Futil and record component/control size after
   `static-promotion`, `compile-static`, and `tdcc`.
2. Sweep Calyx `tdcc.one-hot-cutoff`. Its default is binary FSM encoding; a
   one-hot cutoff may trade a giant decode/priority expression for state bits.
   Do not predict a win—measure SV bytes, Calyx time, Verilator stages, and the
   exact gate for each point.
3. Only if the first sweep is promising, vary static-promotion/compile-static
   limits and compaction. These can structurally alter control, so they are
   not compile-only tweaks.

Do not promote `tdcc.early-transitions` (documented experimental), arbitrary
pass removal, verification disabling, or cell-share disabling as a canonical
speed setting. They may change stateful-group timing or enlarge the design.
The existing affine-unroll and group-removal slice experiments are also
negative/blocked evidence, not shortcuts around this schedule.

## Source evidence

- LoopLynx, pp. 3--4: reusable hybrid spatial/temporal dataflow kernels,
  [arXiv:2504.09561v1](https://arxiv.org/abs/2504.09561v1).
- FlightLLM, pp. 6--8: mask-aware computation, fusion, and mapping/compiler
  choices, [arXiv:2401.03868v2](https://arxiv.org/abs/2401.03868v2).
- *Understanding the Potential of FPGA-Based Spatial Acceleration for Large
  Language Model Inference*, pp. 2 and 13--14: temporal/spatial reuse tradeoff
  and reusable HLS kernels, [arXiv:2312.15159v2](https://arxiv.org/abs/2312.15159v2).
- FQ-BERT, pp. 1 and 3: quantized accelerator organization,
  [arXiv:2103.02800v1](https://arxiv.org/abs/2103.02800v1).
- *Integer-only Quantized Transformers for Embedded FPGA-based Time-series
  Forecasting in AIoT*, pp. 3--4: integer datapaths/address control,
  [arXiv:2407.11041v6](https://arxiv.org/abs/2407.11041v6).
- MEADOW, pp. 1--2: lossless packing and dataflow to reduce memory traffic,
  [arXiv:2503.11663v1](https://arxiv.org/abs/2503.11663v1).
- PEANO-ViT and QUARK: nonlinear approximation/sharing are numerical-model
  alternatives, [arXiv:2406.14854v2](https://arxiv.org/abs/2406.14854v2) and
  [arXiv:2511.06767v2](https://arxiv.org/abs/2511.06767v2).
- N:M sparse transformers and length-adaptive sparse attention,
  [arXiv:2208.06118v1](https://arxiv.org/abs/2208.06118v1) and
  [arXiv:2208.03646v2](https://arxiv.org/abs/2208.03646v2).
- Local Calyx-path negative evidence and backend constraints:
  [SV equivalence fixture study](2026-07-18-rc-sv-equivalence-fixture.md),
  [multiply-slice lowering lab](2026-07-26-mulf-slice-lowering-lab.md), and
  [current baseline](../current-baseline.md).
- Acceptance scope and the required exhaustive promotion contract:
  [local-pass observable-equivalence ADR](../adr/2026-07-16-local-pass-observable-equivalence.md).
