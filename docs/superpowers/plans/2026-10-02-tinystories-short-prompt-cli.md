# TinyStories-1M Short-Prompt CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one 16-token TinyStories-1M FPGA story continuation from exactly four text-encoded prompt tokens and show the decoded text.

**Architecture:** Reuse the accepted USER1/JTAG generation client with an explicit no-oracle readback mode. A separate one-shot CLI authenticates and applies the package tokenizer, validates input before board access, invokes that client, and renders/records the result. Software and board comparisons remain a separate acceptance gate.

**Tech Stack:** Python 3, existing `transformers`/tokenizers Nix environment, FTDI/HS3 USER1 transport, `unittest`, authenticated fixed-point model.

**Spec:** `docs/superpowers/specs/2026-10-02-tinystories-short-prompt-cli-design.md`

## Global Constraints

- Base branch `codex/short-prompt-cli` on Task 4 commit `0a3aecc`; leave Task 5's worktree untouched.
- Reuse the programmed 16-token image and existing four-word USER1/JTAG ABI; no RTL, synthesis, programming, or model-size changes.
- Require tokenizer SHA-256 `f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5` and exactly four IDs in `[0, 50257)` before opening FTDI.
- Read exactly 16 IDs after one START; the host supplies no generated token or intermediate state.
- A successful unverified transport run must not be described as exact-model equivalence.
- Keep physical FPGA access exclusive; host-only tests may run while Task 5 operates.

## Review Focus

- Prompt text that encodes to three or five IDs must fail before any JTAG reset or open (Task 2 test).
- A tokenizer with matching names but changed bytes must fail its digest check (Task 2 test).
- A generated ID outside `[0, 50257)` must fail with a retained receipt, rather than decode silently (Task 2 test).
- A transient zero STATUS read may be retried once without a second START; persistent bad status fails (Task 1 test).
- A completed transport run with no oracle comparison must say `token_check=none`, never `verified` (Tasks 1 and 2 tests).

---

### Task 1: General 16-token JTAG readback

**Files:**
- Modify: `scripts/pipeline/infer_tinystories_generation_jtag.py`
- Modify: `tests/test_tinystories_generation_jtag.py`

**Interfaces:**
- Consumes: existing `infer_generation` delayed-response USER1 transaction code.
- Produces: `infer_generation(..., expected_tokens=None, generation_steps=16, ...) -> dict`; existing calls with `expected_tokens` remain valid. Receipt adds `token_check` with values `exact_oracle` or `none`.

- [ ] **Step 1: Add failing tests.** Exercise a non-frozen four-ID prompt, no `expected_tokens`, exactly 16 indexed reads and one START; assert `token_check == "none"`, `tokens` are returned, and the frozen checker still compares every expected ID. Add a transient-zero STATUS case and a persistent-bad-status case for unverified mode.
- [ ] **Step 2: Run the focused test file.** `python -m unittest tests.test_tinystories_generation_jtag -v`; expect the new unverified-mode tests to fail before implementation.
- [ ] **Step 3: Extend `infer_generation` minimally.** In `scripts/pipeline/infer_tinystories_generation_jtag.py`, accept `expected_tokens=None` only with `generation_steps=16`, read indices `0..15`, and mark `token_check=none`; preserve the existing exact-check path, 300-second deadline, reset/echo checks, and single START.
- [ ] **Step 4: Run the focused test file.** `python -m unittest tests.test_tinystories_generation_jtag -v`; expect all tests to pass.
- [ ] **Step 5: Commit the verified change.** Commit the script and focused test as `feat: support unverified sixteen-token JTAG readback`.

### Task 2: Authenticated text CLI

**Files:**
- Create: `scripts/pipeline/prompt_tinystories_generation_jtag.py`
- Create: `tests/test_tinystories_short_prompt_cli.py`
- Modify: `docs/tinystories-1m-ypcb-jtag-interface.md`

**Interfaces:**
- Consumes: Task 1 `infer_generation(..., expected_tokens=None, generation_steps=16, ...)`.
- Produces: `load_tokenizer(tokenizer_dir: Path) -> PreTrainedTokenizerFast`, `encode_prompt(text: str, tokenizer: PreTrainedTokenizerFast) -> list[int]`, `run_prompt(text: str, tokenizer_dir: Path, transport_dir: Path, serial: str, timeout: float, receipt_path: Path | None = None) -> dict[str, object]`, and the command-line interface from the spec.

- [ ] **Step 1: Add failing tokenizer tests.** With a fixture or injected tokenizer, assert frozen text encodes to `[7454, 2402, 257, 640]`, altered `tokenizer.json` bytes fail before JTAG access, and three-/five-ID inputs fail without truncation or padding.
- [ ] **Step 2: Run the tokenizer tests.** `python -m unittest tests.test_tinystories_short_prompt_cli -v`; expect the new tests to fail before implementation.
- [ ] **Step 3: Implement tokenizer loading and input validation.** Hash `tokenizer.json` against the exact-input contract, use local tokenizer files only, encode with no added special tokens, and enforce four IDs in `[0, 50257)`. Check the frozen text against the real authenticated tokenizer package in the Nix environment.
- [ ] **Step 4: Add failing CLI tests.** Mock the JTAG client and assert one 16-token run, preserved whitespace in decoded output, `token_check=none`, `--receipt` content, nonzero error exit, FTDI close, and receipt retention for an out-of-range output token.
- [ ] **Step 5: Run the CLI tests.** `python -m unittest tests.test_tinystories_short_prompt_cli -v`; expect the CLI behavior tests to fail before implementation.
- [ ] **Step 6: Implement `run_prompt` and `main`.** Parse the spec's arguments, validate before opening the device, call Task 1, decode with cleanup disabled, write an optional JSON receipt, print the result, and send errors to stderr. Document the command and fixed limits in the JTAG interface page.
- [ ] **Step 7: Run the focused suite.** `python -m unittest tests.test_tinystories_short_prompt_cli tests.test_tinystories_generation_jtag -v`; expect all tests to pass.
- [ ] **Step 8: Commit the verified change.** Commit the CLI, tests, and interface docs as `feat: add authenticated short-prompt board CLI`.

### Task 3: New-prompt functional gate and handoff

**Files:**
- Create: `scripts/pipeline/compare_tinystories_short_prompts.py`
- Create: `tests/test_tinystories_short_prompt_comparison.py`
- Create: `docs/results/2026-10-02-tinystories-short-prompt-cli.md` when observed results exist.
- Modify: `docs/goals/2026-10-02-tinystories-short-prompt-cli.md`

**Interfaces:**
- Consumes: Task 2 prompt/receipt format; authenticated fixed-point model loader in `TinyStories/model_adapter_exact_package.py` and accepted board image.
- Produces: a per-prompt comparison receipt with 16 exact software tokens, 16 board tokens, first mismatch index or `null`, and model/bitstream/tokenizer identities.

- [ ] **Step 1: Add failing comparison tests.** Assert exact 16/16 success, first-divergence reporting, rejection of mismatched prompt IDs or image/tokenizer identities, and no equivalence claim from a transport-only receipt.
- [ ] **Step 2: Run comparison tests.** `python -m unittest tests.test_tinystories_short_prompt_comparison -v`; expect failure before implementation.
- [ ] **Step 3: Implement offline comparison.** Load the authenticated fixed-point model with `load_successor_exact_model`, repeatedly select the smallest-ID maximum from `bundle.model(torch.tensor([context], dtype=torch.int64))[0, -1]`, and append it for 16 steps. Compare with a board receipt and emit a hashed result with the first mismatch. Require an external programming log that binds the board run to the accepted image; keep software output separate from FPGA inputs.
- [ ] **Step 4: Run host verification.** Run the comparison tests plus Task 1/2 tests, then replay the frozen prompt against archived Task 4 evidence. Expect all to pass.
- [ ] **Step 5: Run two non-frozen board prompts when the board is available.** Validate the spec's ordered text candidates and record the two selected four-ID prompts before board access. Reserve exclusive access, use the same accepted image, retain its programming log and raw JTAG receipts, compare all 16 IDs to the exact model, and record the result. Do not relabel an unrun or failing board comparison as passed.
- [ ] **Step 6: Commit results or a precise blocked-state report.** Update the goal and write the result page with observed evidence; commit only after verification. If board access or comparison fails, retain the truthful frontier and leave general-prompt acceptance open.

## Execution handoff

Review this spec and plan before implementation. The first two tasks are host-only and can run alongside Task 5. Task 3's physical runs require exclusive board access; they do not block host-only CLI development.
