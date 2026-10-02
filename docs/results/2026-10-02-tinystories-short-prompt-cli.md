# TinyStories-1M short-prompt CLI: host result and board gate

The one-shot text CLI and exact-model comparison tool are implemented on
`codex/short-prompt-cli`. The CLI authenticates `tokenizer.json`, rejects text
that is not exactly four token IDs before opening JTAG, reads 16 generated IDs
from the already programmed board image, and decodes them. A completed JTAG run
is labeled `token_check=none` until separately compared with the exact model.

## Host verification

`python3 -m unittest tests.test_tinystories_short_prompt_comparison
tests.test_tinystories_short_prompt_cli tests.test_tinystories_generation_jtag
-q` passed 26 tests. The real package tokenizer was loaded in `nix develop`:
`Once upon a time` encoded to `[7454, 2402, 257, 640]`, matching the frozen
fixture. It also encoded both selected new prompts to four IDs.

The authenticated fixed-point model generated 16 greedy tokens for each new
prompt. The complete raw reference records are in
`artifacts/reference/tinystories-short-prompt-software-2026-10-02.json`
(SHA-256 `18d20da48dfab82696756271a7e61e72df25df2ec42cdd82fb779c3270fa9e37`).
Both records use model identity
`c187c2eb174bc5eadba742029915a7ba55a8cef66cd58f000db09c8ac9976233`.

| Text | Prompt IDs | Exact-model continuation IDs |
| --- | --- | --- |
| `Once upon a day` | `[7454, 2402, 257, 1110]` | `[11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 373, 845, 3772, 284, 711, 351]` |
| `The little girl went` | `[464, 1310, 2576, 1816]` | `[284, 7301, 262, 11376, 13, 1375, 2497, 257, 1263, 11, 4077, 15061, 13, 1375, 2227, 284]` |

The comparison tool replayed the frozen prompt against the archived Task 4
board receipt, its run-0 programming log, the accepted bitstream, and the
authenticated 16-token oracle: `status=passed`, `first_mismatch=null`. This is
an offline replay of existing evidence, not a new FPGA run.

## Physical acceptance still open

The board has not yet been run with either new prompt in this worktree. The
accepted Task 4 runner restored the earlier first-token image after its three
16-token demonstrations, so the full16 image must be reprogrammed before new
prompt checks. Each new run needs exclusive YPCB/HS3 access, an SRAM programming
log bound to image SHA-256
`bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f`,
a raw CLI receipt, and a 16/16 comparison with the exact-model tokens above.
Until these runs finish, only the host path and frozen archived replay have
passed; general new-prompt board correctness remains unclaimed.
