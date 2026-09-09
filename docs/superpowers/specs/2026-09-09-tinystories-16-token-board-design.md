# TinyStories-1M autonomous 16-token board inference

## Approved scope

Implement the active user-approved goal: full compiler-generated TinyStories-1M,
on-chip BRAM/LUTRAM, 30 MHz, JTAG, one autonomous 16-token continuation, exact
simulation/reference agreement and three independent SRAM configurations under
300 seconds each. Two-token board inference is the first checkpoint, not the
completion criterion. No DDR3, PCIe, general-prompt CLI, or unrelated performance
optimization. Keep incomplete BRAM/DSP timing coverage explicit.

## Preserved baseline and authority

- Baseline commit: `f8d3019c17abc75d5b9b93e2efee70cfe03a40e0`.
- Passing first-token image SHA-256:
  `2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a`.
- Preserve both ignored result directories ending `first-token-signext-20260909`
  and `first-token-failed-20260909`; do not overwrite their artifacts.
- Preserve the fixed model, quantization, arithmetic order/wrapping, tokenizer,
  parameter banks, and source-only weight initialization.
- Prompt: `[7454, 2402, 257, 640]`.
- Full continuation: `[11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375,
  6151, 284, 711, 2354, 287, 262]`.
- Existing authority: `artifacts/reference/tinystories-1m-exact-generation.json`,
  authenticated artifact hash
  `9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3`.
  Its verifier passed again during planning. Constants in this document are
  comparisons only; they must not become candidate token/intermediate inputs.

## Architecture

Retain the existing compiler-owned shared transformer datapath and full-context
recomputation schedule. A single START runs every requested generation step.
The generated greedy token is written to output storage and appended to the
next context entirely on FPGA. Do not introduce KV caching in this goal.

The existing production generator accepts one or two steps, allocates eight
rows, and has a one-bit token output index. Reuse the two-step mode unchanged
for the first board checkpoint, with the proven signed-DSP synthesis policy.

For sixteen steps, centralize generation geometry in the compiler. Preserve
eight rows for the legacy modes; allocate twenty rows for sixteen steps. Real
inference lengths are 4 through 19; the final append requires storage for 20.
Use widths derived from limits, including a five-bit generation counter capable
of representing terminal value 16 and a four-bit output index. Resize dependent
attention, activation, address, copy-loop, and context structures consistently.
Non-power-of-two row capacity must be tested explicitly; never silently wrap,
truncate the context, drop layers, or substitute a reduced model to fit.

Keep the immutable two-step checkpoint fixture and capture authority intact.
Create a successor 16-step fixture from the same authenticated model and the
existing sixteen canonical predecessor steps. Record per-step contexts,
selected tokens, semantic checkpoint hashes, and source/provenance bindings.
The new verifier must reject token, context, tensor-hash, and identity mutations.

The board wrapper remains a transport adapter. Parameterize its output-index
width while retaining the current prompt encoding and default legacy width.
No host writes to generated context or intermediate states after START. A new
generation checker reads all output indices without resetting or restarting
the core. Retain the existing first-token checker and baseline evidence.

## Verification and build discipline

1. Revalidate the existing two-step production tests and authenticated authority.
2. Build and simulate the two-step candidate, then prove `[11, 612]` on board,
   including compiler/simulation evidence of actual generated-token feedback.
3. Capture and verify the successor 16-step fixture without replacing authority.
4. Validate compiler geometry and exact generated-SV token/checkpoint sequence.
5. Build the sixteen-step full model with the proven synthesis policy, fixed
   seed 15, unchanged XDC and 30 MHz clock. Require legal routing and covered-path
   timing pass. Preserve the partial timing disclaimer.
6. Program the same bitstream independently three times; verify all prompt
   words, one START, exact sixteen outputs, done status, and <=300 s per run.

Use Python inside Nix. Every expensive stage has a process handle, a deadline,
and a preserved log. Do not restart a live job because its output is quiet.
Initial physical bounds: 40 minutes for routing and 12 minutes for frame
conversion, informed by the passing baseline. Bound generation/compilation and
simulation separately, at no more than two hours per stage. Record actual
elapsed durations and zero/nonzero exits; output existence alone is not success.

For a mismatch, retain the exact image/run and localize the first divergent
checkpoint before making an evidence-backed change. For resource or timing
failure, report the responsible structures/path before changing implementation.
Do not relax clock/constraints or alter quantization to satisfy acceptance.

## Completion and exclusions

Completion requires the full sixteen tokens, not merely the two-token checkpoint,
and separate observed programming processes bound to their inference receipts.
Document build/source/image hashes, resource/timing reports, simulation evidence,
latencies, and known limitations. Retain LLM-assisted provenance disclosure.
Usable arbitrary-prompt CLI behavior and full timing qualification remain later
work; neither can be claimed from this frozen-sequence acceptance.
