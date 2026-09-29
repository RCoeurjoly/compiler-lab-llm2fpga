# Accepted full16 compiler artifact: DDR3 board binding

The board build now has explicit packages for the accepted compiler-generated
TinyStories-1M artifact rather than silently selecting the historical
240-port model:

```sh
nix build --impure --offline --no-link .#compiler-full16-ddr3-board-source
nix build --impure --offline --no-link .#compiler-full16-ddr3-board-elaboration
```

These packages import immutable accepted Nix outputs; they do not re-run the
PyTorch-to-Calyx compiler. The `--impure` requirement follows the existing
repository convention for `builtins.storePath` evidence inputs. This is an
explicit snapshot binding, not a portable reconstruction of all historical
compiler derivations.

The bound generated `main` is byte-identical to the passing first-token
transaction simulation candidate:
`/nix/store/g67jq7vcsw5mdyf2psbiwr9m668135vk-compiler-accepted-full16-ddr-weights-preflight`.
Its semantic receipt is the successful `gf6f2r4y1fp5cc8jzchlanbzkblbxbz0`
Nix output documented in
[the transformer checkpoint report](2026-09-29-external-memory-transformer-checkpoints.md).
The source binding checks receipt/artifact agreement, image contents, balanced
memory records and exact first-token/checkpoint acceptance. A negative build
using the retained failed `f95fhyn0vh64v7gkqlkxbvphfn66bjma` semantic receipt
fails at its status assertion, as required.

## Transport-only adaptation

The parameterized backend now supports the accepted 86 indexed memory ports
and four-bit token-result index. The command adapter holds compiler go/valid
through generation, drops them at full completion, then drains all sixteen
stored result slots. Each subsequent index settles for one clock before its
word is captured. Words remain stable until accepted; no generated token or
intermediate model state is supplied by the host or wrapper.

CLEAR resets the core and its registered memory boundary as well as the
adapter. Accepted START resets the result index, including when the stored
prompt is reused without CLEAR. Duplicate START during generation/readout is
ignored. Legacy 240-port, one-bit, one-result defaults remain available.

The existing 32-bit to 25-bit DDR line-address truncation is now explicit in
the top rather than an implicit resized module connection. PCIe, UberDDR3,
the arbiter, the Wishbone pipeline, clocks and constraints are unchanged.
No compiler arithmetic, model storage/feedback logic, or kev-gpt RTL was
added or edited.

## Native verification and limits

- The new test first failed because the adapter lacked the required ABI
  parameters. A further behavioral test failed because restart retained
  result index 15; resetting the index on START makes that test pass.
- Native framing simulation checks sixteen distinct high-bit words, ordered
  readout, backpressure, clear/reset, duplicate START and prompt reuse. A
  second test connects the actual asynchronous PCIe token CDC/collector and
  verifies all sixteen words in its PCIe-domain slots with no extra token.
- Native backend simulation issues a last-port read through the actual arbiter
  and Wishbone pipeline with stalls/delayed acknowledgement, checking the
  line address, full response word, exact request count and result-index
  width for both 240/1 and 86/4 configurations.
- The legacy one-result adapter's delayed-memory/backpressure simulation
  passes. These compute fixtures isolate transport behavior; they are not
  inference implementations or proof of sixteen-token DDR3 arithmetic.
- Actual accepted generated RTL elaborates under Icarus with the 86/4/16
  adapter configuration without port padding/pruning warnings. Icarus emits
  its existing conservative `always_*` sensitivity notice for the arbiter.

The immutable source binding is
`/nix/store/hnll5zyz5gg33l1rdy2j9my41d19cg31-compiler-full16-ddr3-board-source`;
it includes the three retained local initialization images. Final complete
board elaboration is
`/nix/store/l5wkxq3c8anqjdysn358acvb846y3ql4-compiler-ddr3-trace-replay-elaboration`.
Yosys completes in 43.96 seconds with 541.06 MB peak memory, without the
previous compiler interface/address-port resize warnings. However, `check`
reports **3,476 problems**, so this is not clean implementation qualification.
Of these undriven-bit reports, 3,464 are in generated `main` and 12 in the
platform; prominent main groups are immutable memory write-data signals.
Their full consequences have not been established, and they are not waived
by successful process exit or the first-token simulation.

The repository-wide Nix-Python unittest run timed out after 180 seconds
(exit 124), without a final suite count. Observed failures/errors include
`test_bram_bank_geometry` production provenance, the database-overlay case in
`test_compiler_replay_route`, continuation/runtime lifecycle cases,
`test_exact_pipeline_source_closure`, and the three static external-read
schedule cases. These are recorded failures, not a claim that every one is
unrelated to this change. The raw run is retained in the execution ledger's
`current16-revalidated/late-congestion/full16-board-wrapper-broad.log`.

No synthesis, routing, new bitstream, programming or physical DDR3 inference
was performed for this binding. The existing board compiler clock is the
83.33 MHz DDR controller clock; the accepted on-chip 30 MHz timing report
does not qualify it. The original on-chip acceptance and board baseline are
preserved. Next gates remain implementation diagnostics/timing, production
DDR calibration/BIST and exact-image PCIe load/readback, followed by actual
compiler accelerator first-token and multi-token hardware inference.
