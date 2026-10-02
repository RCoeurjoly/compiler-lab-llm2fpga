# Reproducible short-prompt runtime inputs

These exact files are committed so a clone of `codex/short-prompt-cli` can
program and prompt the accepted TinyStories-1M full16 YPCB image without a
second local checkout, a pre-existing Nix store path, or a remote model package.
The CLI checks each digest before board access.

| File | SHA-256 | Provenance |
| --- | --- | --- |
| `tokenizer/tokenizer.json` | `f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5` | Authenticated TinyStories-1M package; exact-input contract |
| `bitstream/model.bit` | `bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f` | Task 4 full16 two-ROM accepted board image |

The JTAG Python transport is in `third_party/llm2fpga-jtag/`. Its two file
digests are checked by the CLI. The source files were copied from the
LLM2FPGA Task 6 transport at revision
`2aed4823df51c0dc45825d9c0a3d39182182f93d`; their byte hashes match the
accepted short-prompt board receipts in
`artifacts/board-captures/2026-10-02-short-prompt-cli/`.
