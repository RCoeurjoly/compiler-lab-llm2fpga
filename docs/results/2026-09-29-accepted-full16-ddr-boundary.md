# Accepted full16 compiler design: DDR3 integration boundary

The [three-run on-chip board acceptance](2026-09-29-compiler-full16-bram-board-acceptance.md)
is preserved. Subsequent DDR3 work starts from those exact compiler artifacts,
not from the old two-token DDR3 candidate or kev-gpt RTL.

## Existing integration is not directly compatible

The accepted design uses 25 packed 64-bit token-code banks and 25 scale banks.
Its token selector is four bits wide. The historical DDR3 backend explicitly
requires 240 memory ports and connects a one-bit selector; its command adapter
returns only token index zero. Reusing that wrapper unchanged would not expose
the accepted sixteen-token output contract.

The old 197-bank consolidation pass does not apply to this packed layout.
The earlier hardware trace replay covered the older 4,136,720-byte image and
its request sequence; it is not acceptance evidence for the new packed image
or full accelerator.

## Exact accepted image and externalization

The existing image packer reproduced a 4,002,704-byte, 89-table image from the
accepted static image. Its SHA-256 is
`5aa5232db4b5423ea829484da580ec68b45827c4c11dd8ed39c4d692f580b83a`.
The byte packing and 16-byte lexical table alignment are unchanged. This is
the accepted model's packed representation, not a different model or smaller
inference scope.

Applying the existing externalization pass to all 88 non-prompt tables is
rejected at `gelu_lut_q12`: the pass recognizes an older static schedule with
`early_reset_static_seq50_go_out`, whereas the accepted compiler emits
`early_reset_static_seq51_go_out`. No speculative schedule rewrite was made.

The weights-first placement allowed by the memory-placement design succeeds:
86 weight/scale memories are externalized, while the prompt and the small
GELU/attention-exponential lookup tables remain local. Runtime activations,
context, accumulators and token feedback remain local too. The full packed
image still includes all 89 tables so the loader has one reproducible image;
the external-memory addresses retain the complete image's original offsets.

The final preflight uses `model-static-init-normalized.sv`, not bare compiler
RTL: local lookup-table initialization must survive the conversion. It checks
the retained local instances and their INIT_FILE bindings. An earlier bare-RTL
preflight elaborated but lacked initialization and is not the simulation input.
No emitted accelerator arithmetic or control was hand-edited. The initialized
externalized output has SHA-256
`c12fbe8b50f3e590afb9fc41d36eef0509f3ad3c85cb4ae23c3db629ae0b4ccd`.

The final generated main passes native Verilator elaboration, with warnings.
Elaboration does not prove functional equivalence or timing.

## Bounded behavioral memory checks

Actual Icarus simulations exercise the external memory cell extracted from
that emitted RTL and the unchanged repository Wishbone arbiter. Expected
values are independently checked against the accepted per-table hex files;
responses come from the packed 128-bit image with request stalls and delayed
acknowledgements. The trace includes byte/lane, burst and row boundaries,
first/last addresses, distributed addresses and repeated same-address reads.

| Authenticated table | Width | Compared reads |
| --- | ---: | ---: |
| c_proj_weight_codes_i8 | 8 | 332 |
| c_proj_weight_scale_q8_24 | 32 | 297 |
| token_weight_codes_packed_b0 | 64 | 328 |

All 957 reads match, with one request/response per read. For each table, a
corrupted-response run fails at a value mismatch and a suppressed-response
run fails at a timeout. A Nix `--check` rebuild repeats these real simulations
and verifies deterministic output.

These checks use the arbiter's **one-port** configuration and a transaction
memory model preloaded with the actual image. They do not cover full
86-port concurrency, host image loading/readback, full model inference,
PCIe ingress, physical DDR3 calibration/PHY, synthesis, routing or hardware.
They are fast boundary evidence, not a substitute for those acceptance gates.

## Durable artifacts and next action

- Initialized 86-memory lowering and full packed image:
  `/nix/store/gb3g91x34bkqjszmn4yb3dsjysf28sc7-compiler-accepted-full16-ddr-weights-preflight`.
- Native generated-main elaboration:
  `/nix/store/j0ya2cm81gws1ixh8cqb2yaalib35bf0-compiler-accepted-full16-external-weights-verilator-lint`.
- Behavioral traces, emitted cell, arbiter, testbenches, positive/negative logs
  and checker:
  `/nix/store/w7ffb2vsgn56ycasmdb5x6b7qc8xk3l7-compiler-accepted-full16-external-memory-boundary`.
- Boundary derivation:
  `/nix/store/g1yac7n1v149rd8ibcmgl5fgakjjhd6p-compiler-accepted-full16-external-memory-boundary.drv`.

The next functional gate must connect the exact generated main to the
86-port arbiter and production owner boundary, load/read back the complete
image through the host interface, and compare the earliest generated
architectural checkpoints before paying for a complete inference simulation.
Then require first token 11 and exact sixteen-token generation in the external
memory mode. The transport wrapper must expose all sixteen indexed tokens,
without host feedback, and preserve the existing PCIe/UberDDR3 interface and
two-lane 333/83.33 MHz profile. No integrated bitstream was built or programmed
in this preflight; the board retains the restored first-token baseline.
