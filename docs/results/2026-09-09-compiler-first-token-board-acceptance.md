# Compiler-generated TinyStories-1M: first-token board acceptance

The full compiler-generated TinyStories-1M design produced the authenticated
first token on YPCB after three independent SRAM configurations of the same
bitstream. It uses on-chip BRAM/LUTRAM, the unchanged 30 MHz clock, and JTAG.
Neither DDR3 nor PCIe is involved. BPI flash was not written.

| Configuration | Exact token | Host-observed inference time |
| --- | --- | --- |
| 1 | 11 | 3.226360842 s |
| 2 | 11 | 3.218367886 s |
| 3 | 11 | 3.181494943 s |

Each run loaded and read back the frozen prompt `[7454, 2402, 257, 640]`, sent
one START, observed exact done status, and read token 11. No completion-zero
status retry was needed. These times include host polling/readback overhead;
they are not cycle-accurate latency measurements or throughput characterization.

## What was fixed

The prompt ABI uses command bits `[17:16]` for the word index and `[15:0]` for
the value, avoiding the previous overlap. The successful raw transactions
independently verify all four words, not merely their host-side encoding.

The later inference mismatch was localized to embedding arithmetic: the
original synthesized design zero-extended two signed products to 64 bits.
Applying those exact 40-bit/24-bit zero extensions reproduced all 64 captured
hardware values, including all 50 mismatches. The unchanged pre-native-mapping
full-model simulation matched all eight transformer blocks and token 11.

Commit `92810018af589d17739489f20e066abe242c1b05` added the documented Yosys
DSP-packing workaround and red/green mapped-arithmetic tests. It retains DSP
multiplier inference while disabling the faulty register/adder packing; no
accelerator RTL was replaced. The rebuilt netlist retains both sign extensions.
The small mapped regressions cover 4,096 arithmetic cases plus reset/idle checks;
they are not full-model formal equivalence. The optional post-ABC full-netlist
simulation cut was inconclusive and is not counted as passing evidence.

Commit `a9a7cad2127cea7fdb2da08536f84c61e2a4fc7f` repaired an independently
observed host completion/status race. All 12 inference/USER1 tests pass, but
none of these three hardware runs needed that retry.

## Evidence and limitations

The tracked aggregate is
[the acceptance receipt](../../artifacts/reference/tinystories-1m-first-token-board-acceptance-2026-09-09.json).
Its self-hash is
`14dc7772a361ecb9eb3445527b2195a4fc04471accb73af51846687bb0cc6b4f`.

The bitstream SHA-256 is
`2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a`.
The authenticated oracle SHA-256 is
`31fbd1e3f5b13d7b07466a72e9c6a551ffc00bd4fee375241f095ba5b5cda677`.
The compiler-generated Calyx source SHA-256 is
`e422c0093658d376e23510dea1a8375a87c0df10292d9a237454c862dc49fecc`;
the generated SystemVerilog source SHA-256 is
`7e359dfd4ea1e78bdd141eeba52cc779d3698fb38b279def96e72a72188fc8b5`.

Local bitstream, route archive, raw programming logs, raw inference receipts,
and the acceptance audit are preserved under the ignored directory
`result-compiler-first-token-signext-20260909/`. Earlier failing-image capture
and localization evidence remains under
`result-compiler-first-token-failed-20260909/`.

Each inference receipt intentionally says
`independent_reconfiguration_verified: false`: that checker does not program
the FPGA. The aggregate binds three separately observed successful programming
processes to their subsequent inference processes and raw logs; it does not
claim that a JSON self-hash alone proves physical reconfiguration.

Routing completed legally at fixed seed 15 with final covered-path accelerator
Fmax **30.53 MHz**, passing the unchanged 30 MHz requirement. The route audit
verified all 955 BRAM instances and 142,557 source parameters. **BRAM/DSP timing
coverage remains incomplete: this result is not full timing qualification.**

This closes the first-token goal only. Frozen 16-token autoregressive
generation, broader prompts/models, and full timing qualification are not
demonstrated here. This work and its documentation used LLM assistance; no
claim about funder acceptance is made.

## Repeat the board check

Use the archived bitstream whose hash is above. For each independent run,
program SRAM with `openFPGALoader -c digilent_hs3 --ftdi-serial 210299BF3824 -m
--file-type bit BITSTREAM`, then run the checker inside Nix:

```sh
nix develop . -c env \
  LD_LIBRARY_PATH=/nix/store/giikxmmn66cadlpql43w4515wwik9fs1-libftdi-1.5/lib \
  python scripts/pipeline/infer_tinystories_first_token_jtag.py \
  --transport-dir /home/roland/LLM2FPGA/scripts/task6 \
  --timeout 300 --output RUN_RECEIPT.json
```

The library and transport paths describe this machine's verified environment,
not a portable installation interface. Preserve each programming log and exit
status separately. Never count a checker pass as proof of reconfiguration.
