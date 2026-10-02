# TinyStories-1M short-prompt board CLI

Status: implemented and physically compared; one new prompt matches and one reproducibly diverges

## Objective

Let a person enter short text in a terminal, tokenize it with the authenticated
TinyStories-1M GPT-2 tokenizer, run the accepted compiler-generated 16-token
YPCB image once, and see its decoded continuation. This goal uses a separate
worktree and branch based on Task 4 commit `0a3aecc`, so Task 5 scaling work can
continue independently.

## Acceptance

- The CLI accepts a text prompt whose authenticated encoding is exactly four
  token IDs and rejects other lengths before opening JTAG or resetting the FPGA.
- It verifies the tokenizer identity from the checked-in exact-input contract,
  writes and reads back all four prompt IDs, starts the core once, reads all 16
  generated IDs, and prints the decoded continuation.
- The frozen prompt remains a regression: its IDs and 16 board tokens match the
  accepted Task 4 evidence. Two additional four-token text prompts are
  compared token by token with the exact fixed-point software model and the
  same board image. Equivalence claims name only the prompts actually tested.
- Host-only tests cover input validation, tokenizer identity, JTAG failures,
  token readback, and terminal output without a connected FPGA. Physical board
  tests use exclusive board access and retain receipts.

## Boundaries

The first CLI is one-shot and runs an already programmed board image. Each
invocation starts a fresh 16-token continuation. It does not add variable-length
prompts, multi-turn state, rolling context, image programming, model-size
selection, DDR3, or a chat-assistant claim. Its board behavior is still subject
to the Task 4 timing-coverage limitation.

Spec: `docs/superpowers/specs/2026-10-02-tinystories-short-prompt-cli-design.md`.
Plan: `docs/superpowers/plans/2026-10-02-tinystories-short-prompt-cli.md`.
Result: `docs/results/2026-10-02-tinystories-short-prompt-cli.md`.
