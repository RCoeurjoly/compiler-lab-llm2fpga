# TinyStories-1M short-prompt CLI design

## Intent and evidence

The user wants to type a short text prompt and receive a continuation from the
already proven compiler-generated TinyStories-1M FPGA image while Task 5 tests
other model sizes in parallel. The accepted Task 4 image takes exactly four
16-bit token IDs, generates 16 tokens autonomously, and exposes indexed readback
over USER1/JTAG. Its three board runs used the same frozen prompt. The existing
`infer_tinystories_generation_jtag.py` requires expected tokens from that
frozen oracle, so it is an acceptance checker rather than a general-prompt
client. The package's `tokenizer.json` is external to this repo; its SHA-256 is
fixed by `artifacts/reference/tinystories-1m-exact-input-contract.json`.

## Scope and user contract

Provide a one-shot command in `scripts/pipeline/prompt_tinystories_generation_jtag.py`:

```text
python scripts/pipeline/prompt_tinystories_generation_jtag.py \
  --prompt "Once upon a time" \
  --tokenizer-dir /path/to/authenticated/tinystories-1m \
  --transport-dir /path/to/hs3-jtag-client
```

The command uses the currently programmed 16-token board image. It accepts
`--serial` (default `210299BF3824`), `--timeout` (default and maximum 300
seconds), and optional `--receipt PATH`. It prints the prompt token IDs and the
decoded 16-token continuation to stdout. A successful exit means the transport
and core completed; it does not, by itself, claim PyTorch equivalence for that
prompt. Errors go to stderr with a nonzero exit. A receipt records the input
text, prompt IDs, output IDs and decoded text, tokenizer digest, board serial,
transport/checker digests, JTAG transaction trace, elapsed time, and whether a
software-oracle comparison was performed. It must not say `verified` when no
oracle comparison occurred.

The tokenizer is the exact package's `tokenizer.json`, loaded locally with the
available Transformers/tokenizers stack. Hash the file before loading and
require SHA-256 `f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5`.
Encode without adding special tokens; decode the 16 generated IDs with cleanup
disabled so whitespace is preserved. The frozen text `Once upon a time` must
encode to `[7454, 2402, 257, 640]`. A prompt is eligible only if its encoding
has exactly four IDs, each in `[0, 50257)`. Reject empty, short, or long
encodings before opening the FTDI device. Do not truncate or pad prompts.

## Design choice and boundaries

Extend the existing generation JTAG function with an explicit unverified
16-token readback mode while preserving its exact-oracle checker path. The
current delayed-response protocol, reset, prompt echo, status polling, one
START, and indexed reads remain one implementation. The unverified mode returns
all 16 IDs and marks the result as `token_check=none`; the existing checker
keeps comparing each ID with the authenticated oracle. This is smaller and
safer than duplicating the JTAG protocol. Extending RTL for variable prompt
length is a separate hardware goal and would invalidate the accepted image.

The new text CLI owns tokenizer validation, argument handling, terminal
rendering, and optional receipt writing. The JTAG function owns only hardware
transactions. Neither component provides hidden model tokens or intermediate
state to the FPGA. The CLI must reject an unsupported output token ID before
decoding it, close the FTDI handle on every exit, and preserve a failed-run
receipt when `--receipt` was requested.

This is a story-continuation interface, with an independent fresh run per
invocation. It does not retain conversation state or promise instruction
following. The four-token input and 16-token output limits are visible in help
and length errors.

## Verification and parallel-work rule

Start from Task 4 commit `0a3aecc` in `codex/short-prompt-cli`; do not edit the
Task 5 worktree. Host-only tests mock the JTAG device and tokenizer file/path.
They prove frozen regression, a different four-ID prompt, one START, all 16
read indices, delayed-response behavior, tokenizer-hash failure, wrong token
count, timeout, bad prompt echo, malformed output ID, and receipt status.

An offline exact-model comparison for two non-frozen four-token prompts is the
functional gate for claiming those specific prompts work. Try `Once upon a day`
and `The little girl went` in that order; if either does not encode to four IDs,
select the first four-ID text from `Once upon a night` and `In a small town`.
Record the selected text and IDs before board access. Use the authenticated
fixed-point model and greedy selection for 16 steps from each prompt, then
compare all 16 board IDs. Preserve per-prompt model, tokenizer, programming
log, bitstream, and raw JTAG identities. The CLI alone cannot attest which
bitstream is programmed; the comparison receipt must bind an external
programming log to the accepted image. Passing two prompts establishes only
those two observations, not universal four-token equivalence. Board programming
and inference require exclusive access, scheduled around Task 5 hardware runs.
Host-only development can proceed concurrently; large synthesis or model jobs
should avoid competing for memory with Task 5.

No new synthesis, RTL, or model-size work is required for the host CLI.
Physical acceptance requires a fresh programming log that binds the tested
image. If new prompts diverge from the software model, report the first token
mismatch and keep the CLI labeled transport-functional for those prompts.
