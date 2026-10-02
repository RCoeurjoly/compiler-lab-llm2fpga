# TinyStories-1M YPCB host interface (Task 4, frozen board image)

This is the host-facing interface of the compiler-generated, BRAM/LUTRAM-only
TinyStories-1M board image accepted on 2026-09-29. It is defined by
[`tinystories_1m_jtag_csr.sv`](../rtl/tinystories_1m_jtag_csr.sv), the
[`production top`](../rtl/tinystories_1m_ypcb_bram_production_top.sv), and the
[`generation client`](../scripts/pipeline/infer_tinystories_generation_jtag.py).
It does **not** describe kev-gpt's packet protocol, PCIe, DDR3, or a general
chat interface.

## Physical and data contract

- YPCB-00338-1P1 Kintex-7; Digilent HS3 JTAG, USER1 instruction `2` in a
  six-bit IR, 64-bit data scans shifted least-significant bit first. The
  recorded client used HS3 serial `210299BF3824` and 1 MHz TCK.
- The FPGA core runs at the constrained 30 MHz clock. Immutable TinyStories-1M
  weights are initialized by the bitstream; there is no runtime weight-loader
  command. The generated top has four 16-bit prompt inputs. Production
  synthesis sets `TOKEN_INDEX_WIDTH=4`, selecting its 16 stored generated
  tokens; the RTL module's default parameter is not the production setting.
- Command bits `[63:60]` contain the opcode. Prompt index is `[17:16]`, value
  is `[15:0]`; token-read index is `[3:0]`. Other command bits are zero in the
  accepted client. This prompt-index encoding supersedes the old overlapping
  `[5:4]` version.
- A 64-bit scan captures the **previous** response while submitting the next
  command. To read a command's response, the host submits that command, then
  scans `STATUS`; to read current status, it scans `STATUS` twice. The
  [recorded transactions](../artifacts/task4/full16-board-2026-09-29/hardware/receipt.json)
  exercise this ordering.

| Opcode | Command | Effect / response on next scan |
| --- | --- | --- |
| `1` | `0x1... | (index << 16) | value` | Write prompt word 0–3; response low 16 bits echo the value. |
| `2` | `0x2000000000000000` | START one autonomous 16-token generation. Host sends this once. |
| `3` | `0x3000000000000000` | STATUS response: opcode nibble `2`; bit 59 model-image-ready, bit 58 done, bit 57 busy, bits `[15:0]` prompt word 0. |
| `4` | `0x4000000000000000 | index` | Select generated token 0–15; response low 16 bits contain that token. |
| `5` | `0x5000000000000000` | Reset core/control and clear prompt words; does not rewrite immutable model memory. |
| `6` | `0x6000000000000000 | (index << 16)` | Read stored prompt word 0–3; response low 16 bits contain its value. |

Opcode `7` is an RTL diagnostic loopback, not part of the accepted production
client. Unsupported opcodes return a response beginning with nibble `f`.
`model-image-ready` is tied high by this statically initialized board top; it
is **not** an independent checksum of the weight image.

The accepted client resets the TAP and CSR, checks idle status
`0x2800000000000000`, writes prompt `[7454, 2402, 257, 640]`, reads all four
words back, and checks idle status with prompt word 0 in the low bits. It then
issues one START, polls busy `0x2a00000000001d1e` until done
`0x2c00000000001d1e`, and reads token indices 0–15. The client tolerates one
transient zero status immediately after START, but rejects other status values
and a 300-second inference timeout. The core performs greedy token feedback
internally; the host neither supplies generated tokens nor intermediate
tensors. The frozen prompt has an accepted 16-token result. Subsequent
short-prompt comparisons are recorded in
`docs/results/2026-10-02-tinystories-short-prompt-cli.md`.

## Short text prompt client

From a clone of this repository, create and enter the CLI worktree:

```sh
git fetch origin codex/short-prompt-cli
git worktree add .worktrees/short-prompt-cli origin/codex/short-prompt-cli
cd .worktrees/short-prompt-cli
```

The accepted image, authenticated tokenizer, and JTAG transport
are committed in this branch. A pinned Nix development shell provides Python,
`libftdi1.so`, and `openFPGALoader`. With an HS3 cable attached to the YPCB,
program the accepted SRAM image and run one prompt:

```sh
nix develop -c python scripts/pipeline/prompt_tinystories_generation_jtag.py \
  --program --prompt "Once upon a day" \
  --receipt .local/tinystories-short-prompt/day.json
```

While the image remains programmed, omit `--program` on later invocations:

```sh
nix develop -c python scripts/pipeline/prompt_tinystories_generation_jtag.py \
  --prompt "Once upon a time" \
  --receipt .local/tinystories-short-prompt/time.json
```

The CLI validates the committed tokenizer, JTAG modules, and image against
their accepted SHA-256 digests. It rejects text that does not encode to exactly
four IDs before opening or programming the board. `--serial` defaults to
`210299BF3824`; `--timeout` defaults to 300 seconds. It holds a per-serial
lock under the user's XDG cache directory for programming and inference.
Receipts and programming logs in `.local/` stay in the worktree and are ignored
by Git. The 16-token image is held in SRAM and must be programmed again after
a reset, power cycle, or another bitstream load.

Each invocation starts a fresh continuation; the CLI does not retain context.
`status=passed` and `token_check=none` mean the board returned 16 IDs, not
that they match the fixed-point model for that text. The original generation
checker remains the frozen-prompt oracle acceptance path. See the
[short-prompt result](results/2026-10-02-tinystories-short-prompt-cli.md) for
the observed match and mismatch.
