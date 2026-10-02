# TinyStories-1M short-prompt CLI: host and board result

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

## Physical board comparison

The YPCB/HS3 board was reserved exclusively with
`flock -n /tmp/llm2fpga-ypcb.lock`. The accepted full16 image was loaded into
SRAM using `openFPGALoader -m` on serial `210299BF3824`; the command exited
successfully in 150.76 seconds. Its image SHA-256 is
`bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f`.
The [programming receipt](../../artifacts/board-captures/2026-10-02-short-prompt-cli/programming-receipt.json)
binds the [raw programming log](../../artifacts/board-captures/2026-10-02-short-prompt-cli/program.log)
(SHA-256 `ff980b973374db544136b9e400e32ec4bfd2c70387f9039e060bc3b6b88966b6`)
to that image and serial. The board was isolated from the Thunderbolt/PCIe path
for these JTAG runs.

The first attempt to run the CLI failed before JTAG because `libftdi1.so` was
absent from the runtime loader path. Its [receipt and summary](../../artifacts/board-captures/2026-10-02-short-prompt-cli/summary.json)
are retained. A standalone `ctypes.CDLL("libftdi1.so")` check failed in the
default Nix shell and passed when `LD_LIBRARY_PATH` included the installed
libftdi library. The same programmed SRAM image was then used for both prompt
checks with that path set; no reprogramming occurred between them.

| Prompt | Board result | First mismatch | Board continuation | Run time |
| --- | --- | ---: | --- | ---: |
| `Once upon a day` | 16/16 exact-model match | none | `, there was a little girl named Lily. She was very happy to play with` | 66.42 s |
| `The little girl went` | mismatch | 3 (fourth output) | ` to explore the forest. She saw a small, a small, green tree.` | 66.40 s |

The [first board receipt](../../artifacts/board-captures/2026-10-02-short-prompt-cli/transport-retry/prompt0-board.json)
and [comparison](../../artifacts/board-captures/2026-10-02-short-prompt-cli/transport-retry/prompt0-comparison.json)
show the exact match. The [second board receipt](../../artifacts/board-captures/2026-10-02-short-prompt-cli/transport-retry/prompt1-board.json)
and [comparison](../../artifacts/board-captures/2026-10-02-short-prompt-cli/transport-retry/prompt1-comparison.json)
show board token `8222` where the exact model selected `11376`; later tokens
also diverge. The prompt echo and transport checks passed, and each receipt
contains one START and all 16 indexed reads. A [repeat of the second prompt](../../artifacts/board-captures/2026-10-02-short-prompt-cli/prompt1-repeat/comparison.json)
returned the same 16 board IDs and the same first mismatch at index 3. The
cause of that reproducible model/FPGA difference has not been established.

The terminal entry point was also invoked directly with `--prompt "Once upon a
day"` and `--receipt`. It exited 0, printed prompt IDs
`7454 2402 257 1110` and the continuation in the table, and took 66.37
seconds. Its [receipt](../../artifacts/board-captures/2026-10-02-short-prompt-cli/cli-invocation.json)
also [compares 16/16](../../artifacts/board-captures/2026-10-02-short-prompt-cli/cli-invocation-comparison.json)
with the authenticated exact model.

The CLI is transport-functional for four-token prompts on this image. Exact
software/FPGA equivalence is observed for `Once upon a day` and the archived
frozen prompt; it is false for `The little girl went`. Broader prompt
equivalence and chat-like use are not established by these runs.

## Clone-local command verification

After bundling the accepted bitstream, tokenizer, and JTAG transport in the
CLI branch, the documented `nix develop -c python ... --program --prompt
"Once upon a day"` command completed on the YPCB. The pinned shell resolved
`libftdi1.so` and `openFPGALoader` without an explicit store path. Programming
completed in 150.78 seconds and the 16-token readback in 66.35 seconds. The
printed continuation matched the row above, and the receipt compared 16/16
with the authenticated fixed-point model. The new run's programming log had
SHA-256 `ff980b973374db544136b9e400e32ec4bfd2c70387f9039e060bc3b6b88966b6`,
matching the earlier accepted-image programming log. This verifies the
worktree-local command on the current machine; another person still needs the
specified board and HS3 cable.
