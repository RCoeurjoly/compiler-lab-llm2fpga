# Quantized Representative-Core Working-System Design

## Status and objective

**Status:** approved design.

Treat the clean TinyStories PT2E W8A8 representative core as the project’s first
working model, not as a disposable benchmark or simulation-only fixture. It is
the unit under test through progressively more realistic integrations:

    PT2E RC → SV equivalence
            → packed external-image equivalence
            → real board DDR3 equivalence
            → host tokenizer/control equivalence
            → controlled scale-up

Every integration retains the same model, frozen numerical oracle, test corpus,
and comparison of all six final logits plus the chosen token ID. A stage cannot
pass merely because it synthesizes, loads an image, or returns a plausible token.

## Fixed unit under test and oracle

The unit under test is exactly
tinystories-w8a8-rc-study-mask9-vocab6-width2, built by
TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py.

| Property | Fixed value |
| --- | ---: |
| Quantization reference | static XNNPACK PT2E W8A8 |
| Vocabulary | 6 |
| Layers | 2 |
| Maximum positions | 9 |
| Input context | 8 tokens |
| Attention window | 256 |
| Hidden width | 2 |
| Heads | 1 |
| Seed | 0 |

It remains a native GPT-Neo configuration. No handwritten attention, embedding,
LayerNorm, GELU, residual, or substitute model is allowed in an equivalence
result.

The frozen PT2E W8A8 export is the numerical oracle. The exporter removes its
trailing output dequantization, so the canonical comparison value is the six raw
int8 output codes at final position [0, 7, 0:6], accompanied by the actual
output scale and zero point extracted from the PT2E graph. Each result also
records six dequantized logits, calculated as scale * (code - zero_point), and
the greedy token ID. Ties select the lowest token ID. FP32 eager output may be
recorded for quantization context but is not an equivalence pass condition.

The deterministic corpus is:

    tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1
    tok5 tok4 tok3 tok2 tok1 tok0 tok5 tok4
    tok0 tok0 tok0 tok0 tok0 tok0 tok0 tok0
    tok0 tok5 tok0 tok5 tok0 tok5 tok0 tok5

At the first two stages, token IDs may be supplied directly. The later host
tokenizer maps exactly tok0 through tok5 to IDs 0 through 5, accepts only eight
whitespace-separated tokens, and rejects all other input. It is a deterministic
host-ABI test, not an attempt to emulate GPT-2 BPE.

## Common evidence contract

All stages produce and consume a common Nix-built evidence bundle:

    reference.json
    rc-image.bin
    rc-image-manifest.json
    result.json

reference.json records the model configuration, PT2E-export hash,
calibration-input IDs, corpus inputs, output qparams, expected raw codes,
derived logits, token IDs, and hashes of the image and manifest.

rc-image.bin is a little-endian, 64-byte-aligned concatenation of every
post-PT2E tensor required by the exported program: parameters, buffers, and
tensor constants. rc-image-manifest.json records its format version, export and
image hashes, source category, tensor name, dtype, shape, byte offset, byte
length, quantization metadata, segment hash, and stable address map. Segments
are ordered lexicographically by source category and tensor name. An unsupported
state item fails the build rather than disappearing silently.

Before SV execution, a CPU image-backed reconstruction must recreate the
exported state only from the image and manifest and reproduce the PT2E raw codes
and token IDs exactly. All artifacts are Nix outputs or checked-in fixtures;
temporary directories and mutable untracked handoffs are prohibited.

Every result.json has model/export/image/manifest hashes, input text where
applicable, token IDs, expected and observed raw codes, qparams, derived logits,
expected and observed token ID, status, and the first failed boundary. Simulator
and board stages add cycle/transaction or board-run evidence.

## Gate 1: embedded-memory SV equivalence

Lower the exact fixed RC through one selected no-Handshake compiler lane to real
SV. The initial candidate is the existing Linalg frontend without adding TOSA as
a second variable. A final emitter may use Calyx only if it exposes a testable
functional interface; a done-only top fails this gate.

The SV wrapper accepts eight token IDs and exposes the six final output codes
plus the greedy token ID under the fixed tie rule. An explicit result buffer is
acceptable when direct output ports are unavailable. A tiny generated
output-buffer reproducer may establish that interface but cannot substitute for
the RC in the equivalence run.

Following Task 2’s fixed-vector method, a testbench runs real generated SV,
applies every corpus entry, waits for completion with a fixed timeout, and fails
on any one of the six code mismatches or a token mismatch. The intended
simulator is Verilator. Inability to simulate real generated SV is a documented
frontier, not permission to replace it with a behavioral model. No approximate
lowering of math.fpowi, nonlinear operations, or other RC arithmetic is allowed
in this equivalence lane.

Resource and timing reports may be collected as side evidence, but functional
equivalence is the Gate 1 acceptance criterion.

## Gate 2: packed external-image SV equivalence

Externalize the same RC’s immutable model tensors to rc-image.bin. The only
semantic change between Gates 1 and 2 is the source of those tensors: the
externalized SV reads bytes from the packed image rather than embedded or
on-chip initialized model storage.

The Gate 2 testbench uses a simple image-backed memory fixture loaded from the
actual rc-image.bin. It must implement the exact external-memory adapter
interface and return only data present in the image. It is a fast
compiler/packer regression fixture, not a DDR3 model, performance model, or
DDR3 validation claim.

Gate 2 passes only if every corpus case is bit-exact at the six raw output codes
and token ID relative to reference.json. A mismatch localizes to image packing,
address mapping, external-memory adaptation, or the changed SV integration
rather than physical DDR3.

## Gate 3: DDR3 transport compatibility audit

Reuse the already validated ~/LLM2FPGA DDR3/PCIe transport as the board
integration target. Existing evidence shows its PCIe rowstream load, DDR3
readback, and output-head top-1 path ran on the target FPGA; DDR PHY bring-up is
therefore not the first uncertainty in this work.

Do not assume that its existing rowstream reader is the RC memory interface.
task6_ddr3_rowstream_wb_top1_reader is a sequential, row-oriented, 128-bit
Wishbone reader for a specific output-head layout. The audit must identify the
reusable general controller/user-port boundary and compare it with the
externalized RC’s actual demand:

- every read and write width;
- address alignment and byte ordering;
- read-response ordering and backpressure;
- concurrent logical memory requests;
- immutable parameter, input, result, and scratch regions;
- clock/reset and completion domains.

The audit emits a machine-readable compatibility report and selects one of two
outcomes: direct adaptation to the existing general user port, or a precisely
specified RC memory adapter. Reusing the output-head rowstream layout without
this proof is prohibited. An adapter may serialize accesses and reduce
throughput, but it must preserve values, ordering dependencies, write masks,
and error propagation. It must not alter RC arithmetic.

The required DDR3 source and revision must be an explicit, immutable Nix input
or vendored committed source. The working ~/LLM2FPGA checkout is evidence and a
reference, not an unpinned build-time dependency.

## Gate 4: real DDR3 board equivalence

Use the Gate 3 adapter with the proven board DDR3/PCIe transport. The host loads
the exact rc-image.bin, verifies the load with a manifest hash or deterministic
readback checksum, writes eight input token IDs, starts the RC, and reads an
observable six-code result vector plus token ID.

The board result is compared to the same reference.json used by Gates 1 and 2.
Top-1-only output is insufficient: all six codes/logits and the token ID must be
observable. The board report records bitstream hash, transport source revision,
image hash, load/readback evidence, per-prompt result vectors, timeouts or
faults, and final comparison status.

Passing Gate 4 establishes that this exact RC is a functioning hardware model
using the real target DDR3 path. It does not establish full TinyStories capacity,
bandwidth, or correctness.

## Gate 5: host tokenizer and control-path equivalence

Add a deterministic host command with reference and board backends. Both accept
every fixed six-token corpus prompt. The reference backend produces the
oracle-shaped result; the board backend tokenizes, loads or validates the image,
issues the board control transaction, reads six codes, and reports the same
comparison fields plus board evidence.

This gate fails if textual tokenization produces different IDs from the corpus
fixture or if the board outcome differs from direct-ID Gate 4. It thereby
isolates host text/control errors from compiler or DDR3 errors.

## Gate 6: controlled scale-up

Only after Gates 1 through 5 pass, scale from the working RC. Change one model
dimension or deployment property at a time, regenerate the reference and image
bundle, and rerun all prior gates. Candidate scale dimensions are context,
hidden width, vocabulary, layer count, and finally the full frozen PT2E W8A8
TinyStories model.

Each scale point reports image bytes, external-memory traffic, FPGA resource
results where available, latency, and its first failing gate. RC success must
never be presented as proof that the full model fits or meets DDR3 bandwidth.

## Diagnostic value and non-goals

| First mismatch | Likely boundary |
| --- | --- |
| PT2E vs CPU image reconstruction | packing or qparams |
| PT2E vs Gate 1 SV | lowering, arithmetic, or observable interface |
| Gate 1 vs Gate 2 | externalization, image mapping, or adapter |
| Gate 2 vs Gate 4 | board adapter, image loading, DDR3 transport, or board control |
| Direct IDs vs textual host input | tokenizer or host control |

The image-backed Gate 2 fixture is required for iteration speed but is never
called a DDR3 simulation result. Physical DDR3 evidence begins only at Gate 4.
This design does not claim equivalence to FP32 eager TinyStories, natural
language quality for the six-token RC, or full-model feasibility before the
corresponding scale-up gates succeed.

The intended Nix products are:

    tinystories-w8a8-rc-sv-equivalence
    tinystories-w8a8-rc-external-image-sv-equivalence
    tinystories-w8a8-rc-ddr3-compatibility-audit
    tinystories-w8a8-rc-ddr3-board-equivalence
    tinystories-w8a8-rc-host-e2e

Each must produce durable, machine-readable evidence or a documented first
frontier. No successful result can be inferred from a later gate when an earlier
gate was skipped.
