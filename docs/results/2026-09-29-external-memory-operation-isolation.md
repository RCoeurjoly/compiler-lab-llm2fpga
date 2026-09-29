# Compiler external-memory operation isolation

## Failure and correction

The accepted compiler-generated full16 TinyStories-1M design was externalized
to 86 weight/scale memory ports. The prompt and small GELU/exp lookup tables
remain local. Complete host image load/readback passed, and all 9,276 returned
Wishbone words matched the authenticated image, but 21 of 256 embedding values
were wrong.

Every wrong embedding operand consumed the preceding packed token-weight word.
The first divergence was row 1, column 8: the current local index was 2833,
but the completed request belonged to 2832. Token code -13 replaced -84;
token scale and position operands were correct. The same pattern explained
all 21 errors across token-weight banks 0 and 1.

The external-memory primitive reissued after a response while the generated
completion join still waited for other banks. The duplicate transaction could
complete in the next read phase. The compiler externalizer now opts recognized
completion-joined phases into `ONCE_PER_ENABLE`: issue once, wait for the
response, and rearm only after enable drops. Generic streaming instances retain
their original repeated-read behavior. This is a compiler/backend correction,
not a handwritten accelerator replacement or transport change.

## Evidence

- Native Icarus regression fails against the original externalizer with
  `completed join operand reissued before phase ended`, then passes against the
  corrected externalizer. It covers request backpressure, staggered responses,
  consecutive different-address phases, a fresh same-address operation, and
  reset/rearm. The Nix output preserves both externalizers, test source, and logs.
- Sixteen relevant tests pass, including actual generic streaming RTL tests;
  two additional registered-request tests pass, including the Yosys structural
  capture-enable check. These do not constitute a green repository-wide suite.
- The corrected real full accelerator, unchanged 86-port arbiter, registered
  Wishbone pipeline and production owner mux pass complete 4,002,704-byte host
  load/readback and the first embedding checkpoint.
- All 256 observed operand records match the accepted BRAM reference. The 2,048
  embedding bytes match the authenticated PyTorch checkpoint exactly, SHA-256
  `1d6a6b51026506667795de7fd0c4b5d94646aa066b4f7cfe37e69b28829bbcde`.
- All 6,760 ordered response records match image bytes; requests and responses
  balance at the checkpoint, reached after 69,556 inference cycles. The positive
  run took 9.85 seconds including image load/readback. A corrupted host write
  still fails readback at line 17, word 0.
- Exactly 85 memories opt in; the direct-completion position-code memory and
  generic standalone/streaming memories retain the default behavior. The image
  remains unchanged, SHA-256
  `5aa5232db4b5423ea829484da580ec68b45827c4c11dd8ed39c4d692f580b83a`.

Durable Nix artifacts:

| Artifact | Store output |
|---|---|
| Original first-divergence localization | `/nix/store/iq1awnmh468lvhyyyidzfqjj4zvd5190-compiler-full16-first-stale-completion-localization` |
| Native original/fixed red-green regression | `/nix/store/4jynj69lxhy66lzm4aapfrv44w9s4acm-compiler-joined-memory-operation-native-red-green` |
| Corrected compiler externalization | `/nix/store/m9d58k28vlq0j8rvrsfv1hbcndbxng9k-compiler-accepted-full16-ddr-weights-preflight` |
| Actual full-accelerator checkpoint | `/nix/store/6j0h9p3ic8d0hdb2q3ly1imn1xjcnqgf-compiler-full16-86-port-loaded-image-embedding-diagnostic` |

## Limits and next gate

This is transaction-level external-memory simulation. It does not validate
PCIe ingress, DDR3 calibration/PHY, first-token inference, synthesis, routing,
or external-memory board inference. The accepted BRAM board baseline was not
reprogrammed or changed. Next validate later architectural checkpoints and
first-token output before undertaking another physical implementation.

Repository-wide verification is not green: initial pytest attempts used
insufficient environments (missing repository import path, then missing Torch;
a Torch-compatible Python 3.11 attempt could not parse a Python 3.12 f-string
in `test_rc_observable_driver.py`). These are recorded as verification gaps,
not dismissed as passing tests. A bounded Python 3.12 repository-wide unittest
run reached its 180-second limit (exit 124), with errors/failures observed and
no final suite summary. Its log includes Nix cache write-permission failures
and historical command/interface mismatches; the exact error attribution is
incomplete. No repository-wide pass is claimed. Committing this checkpoint
requires the repository's explicit diagnostic-commit approval.

A wider 14-test external-memory run also fails three native subcases of
`test_external_memory_static_schedule.StaticExternalReadTest.test_consumers_wait_for_each_external_read_window`:
`attention_exp_lut_q1_20` and `prompt_tokens` issue two requests where the test
expects one; `gelu_lut_q12` reports lookup address 32600. Rerunning the unchanged
test with the original immutable externalizer reproduces all three identical
failure payloads and simulation times. These are demonstrated pre-existing
failures, not regressions introduced by operation isolation. Their tables remain
local in this accepted candidate; this does not excuse the red tests or prove
their externalization correct. Other methods in that wider run pass.
