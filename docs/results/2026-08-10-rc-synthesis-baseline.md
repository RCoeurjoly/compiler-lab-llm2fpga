# RC Kintex-7 synthesis and placement baseline

Date completed: 2026-08-12

## Outcome

The functionally validated RC SystemVerilog maps successfully for Kintex-7,
but this implementation does **not** fit `xc7k480tffg1156-1`. After a tested
distributed-RAM compatibility transform, nextpnr-xilinx packs 776,182
`SLICE_LUTX` cells against 597,200 available (129%) and fails during analytic
placement:

```text
ERROR: Failed to expand region (0, 0) |_> (309, 416) of 776182 SLICE_LUTXs
```

FF, DSP, carry, BRAM, and I/O resources are below their individual limits;
LUT sites are the first authoritative physical limit. Because no legal
placement exists, nextpnr cannot route the design and there is no valid Fmax
or critical path. The timing evidence is therefore: target 12 MHz (83.333333
ns), post-place/post-route timing unavailable, and an empty critical-path
set. Reporting an Fmax from this failed implementation would be invalid.

This result supports the architectural order “fully on-chip inference first,
DDR3 later for scaling,” but rejects this particular RC instance as the first
on-chip candidate. A smaller model or materially more LUT-efficient mapping is
required before board integration.

## Reproduction

The complete flow is now four cacheable Nix derivations:

```sh
nix build .#tinystories-w8a8-rc-xc7k480t-normalized-sv \
  --no-link --print-out-paths -L
nix build .#tinystories-w8a8-rc-xc7k480t-mapped \
  --no-link --print-out-paths -L
nix build .#tinystories-w8a8-rc-xc7k480t-dram-compatible \
  --no-link --print-out-paths -L
nix build .#tinystories-w8a8-rc-xc7k480t-nextpnr-evidence \
  --no-link --print-out-paths -L
```

Recorded outputs:

- normalized SV: `/nix/store/9b6m3wzv8a4npw7119d9h8s7985wn6k8-tinystories-w8a8-rc-xc7k480t-normalized-sv`
- mapped Yosys bundle: `/nix/store/f40bc67dbi2984q98xlfyljxmppd9rrq-tinystories-w8a8-rc-xc7k480t-mapped`
- compatible mapped bundle: `/nix/store/cqy16yxvzyd6b8wpinari1y0qa9g44j7-tinystories-w8a8-rc-xc7k480t-dram-compatible`
- nextpnr evidence: `/nix/store/ckpy0pamav07k8hd4d29bxqzvqw27ayb-tinystories-w8a8-rc-xc7k480t-nextpnr-evidence`

Each bundle retains receipts, scripts, hashes, GNU `time -v` output, and
compressed verbose logs. The mapped bundles retain their complete JSON
netlists. The final evidence derivation succeeds as a Nix artifact while
preserving nextpnr's exit status 255 in `nextpnr-exit-status.txt` and the
failure/timing frontier in `timing-status.json`.

## Provenance and validation boundary

- Validated generated closure:
  `/nix/store/5qm739maxpd9cvg5jwkdm316s8kr7g35-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv-no-synthesis`
- Validated source SV SHA-256:
  `2262298433271af636683517bba9c7641d02097de314b3dac4f4e3c0843e83f7`
- Checked-in compressed source snapshot SHA-256:
  `fd9efb93f43a270e84a38a03e81c7577b40bc96259a204e4734efd32e6601105`
- Normalized SV SHA-256:
  `f6ea6c64dd33dff5fd2ab50de14b1e32b369e32ea6d6b2e18b6da9e4d1e3bd82`
- Normalization receipt SHA-256:
  `7ddecee01f58f0b547b783e1362e4c00399df3f41f815bbbd3a957fc5d1981f2`
- Normalizer repairs: 2,050 assertion blocks, one request declaration, and
  one duplicate `sqrtOpOut` declaration (2,052 total).

Functional equivalence had already passed Verilator context 0, frozen-four,
and the ordered reset sequence. This is strong regression evidence for the
selected cases, not exhaustive formal equivalence.

The Nix stage deliberately consumes the validated compressed snapshot rather
than regenerating SV from the worktree. During bring-up, regeneration produced
SHA-256 `fe1d28e2...`, partly because an unrelated dirty source file is present;
that unvalidated output was rejected rather than silently substituted.

## Toolchain and target

- Yosys: 0.66, git `7f8fdfd8d7bc08c749a2a969388d3425d4f369d5`
- Yosys/Slang plugin:
  `/nix/store/x21ifbv5q2b9a3z1s72x35ykr35zby0g-yosys-slang/share/yosys/plugins/slang.so`
- nextpnr-xilinx: `stable-backports`, pinned source revision
  `4ef2518428b33f160ff93d38c781f08cc3a41566`
- nextpnr executable:
  `/nix/store/rfyfw1kylhhcj171mrmaymm4q2s14dg7-nextpnr-xilinx-0.8.2/bin/nextpnr-xilinx`
- chip database:
  `/nix/store/6la31fg71mbjaw6wpwj2pddwbs93y2j7-nextpnr-xilinx-chipdb-0.8.2/xc7k480tffg1156.bin`
- chipdb SHA-256:
  `56c46da98f375b14e12cd6df44dede11b576eba33266cd5a8465fb6fe328baad`
- target: Kintex-7 `xc7k480tffg1156-1`
- probe I/O: `clk`, `reset`, `go`, and `done` on `AA28`, `R28`, `P30`, and
  `M30`, all `LVCMOS18`

The XDC is a P&R-only probe, not a board-functional interface.

## Mapped Yosys utilization

Yosys exited 0 and produced 619,758 mapped cells. The following are direct
primitive counts before nextpnr physical packing:

| Resource | Count |
|---|---:|
| LUT1–LUT6 sum | 526,401 |
| FF (`FDCE` + `FDRE` + `FDSE`) | 35,090 |
| `RAMB18E1` / `RAMB36E1` | 0 / 0 |
| `DSP48E1` | 245 |
| `CARRY4` | 34,528 |
| `MUXF7` / `MUXF8` | 5,734 / 2,688 |
| `RAM32M` | 237 |
| `RAM64X1S` / `RAM128X1S` | 440 / 97 |

LUT breakdown: 4,756 LUT1, 176,870 LUT2, 177,036 LUT3, 44,149 LUT4,
40,396 LUT5, and 83,194 LUT6. The mapped JSON SHA-256 is
`88b32d56d65e563955dd8d8da5b9fba46d9c430be60ff827fec7c1589da32316`;
the mapped-stat JSON SHA-256 is
`78a85467430c1d9269c0a0a5af2d9384d741fb88cc52cf2dc5805c03cddc1096`.

The controlled synthesis script omits two pathological optimizations while
retaining the generated sequential/arithmetic behavior:

- FSM extraction is omitted. The stock pass spent approximately 18 h 06 m
  reconstructing the enormous `main_1_instance.fsm0.out` FSM before manual
  interruption (exit 130, observed host usage about 24 GiB RAM).
- The standalone SAT-based `share` pass is omitted. A no-FSM run spent
  approximately 4 h 46 m 38 s there before manual interruption (exit 130,
  observed usage about 10–11 GiB). Ordinary lightweight `OPT_SHARE` inside
  `opt` remains enabled.

These omissions are synthesis-runtime controls and may make the result larger
than an ideal mapper capable of completing those optimizations.

## Distributed-RAM compatibility stage

The pinned nextpnr source recognizes `RAM64X1S` and `RAM128X1S`, but explicitly
rejects them as unsupported during DRAM packing. A one-cell reproducer first
confirmed that failure. The tested transform represents each single-port RAM
as the supported dual-port `RAM64X1D`/`RAM128X1D`, mirrors the same address onto
the unused extra read port, and leaves that output unused.

The full compatibility stage replaced exactly 440 `RAM64X1S` and 97
`RAM128X1S` cells. Every other primitive count remained unchanged. Its mapped
JSON SHA-256 is
`9375db4f9190c7bee573553b66aa5c769e88d07b2b94dda49527b5ba3a8f16da`.

Without this transform, nextpnr stopped during packing after 2:26.44, at
6.55 GiB peak RSS, with:

```text
ERROR: Cannot pack unsupported primitive: RAM64X1S
```

## nextpnr physical utilization and failure

| nextpnr resource | Used | Available | Reported use |
|---|---:|---:|---:|
| `SLICE_LUTX` | 776,182 | 597,200 | 129% |
| `SLICE_FFX` | 35,090 | 597,200 | 5% |
| `CARRY4` | 35,339 | 74,650 | 47% |
| `RAMB18E1` | 0 | 1,910 | 0% |
| `RAMB36E1` | 0 | 955 | 0% |
| `DSP48E1` | 245 | 1,920 | 12% |
| `SELMUX2_1` | 8,616 | 225,550 | 3% |
| `BUFGCTRL` | 1 | 32 | 3% |
| `PAD` | 4 | 946 | 0% |

Packing expanded the design to 773,018 ordinary `SLICE_LUTX` cells, then
distributed RAM raised the total to 776,182. It grouped 138,112 `MUXCY` and
138,112 `XORCY` cells into 10,088 chains, created 245 DSP cells, created
35,090 FF cells, and constrained 29,760 LUT/FF pairs. Analytic placement then
failed at the LUT capacity boundary. No FASM was produced.

## Timing and critical paths

The requested timing evidence is recorded explicitly, including its absence:

| Field | Evidence |
|---|---|
| Constraint | 12.0 MHz |
| Target period | 83.333333 ns |
| Placement | failed: LUT region cannot expand |
| Routing | not reached |
| Fmax | unavailable |
| Critical paths | none; empty set |

This is not a timing-closure failure. It is a resource-fit failure that occurs
before timing can be measured on a legal implementation.

## Runtime and memory

| Stage | Exit | Wall time | Peak RSS |
|---|---:|---:|---:|
| Nix mapped Yosys | 0 | 1:27:02 | 8,829,936 KiB (8.42 GiB) |
| Nix DRAM compatibility | 0 | 0:28.14 | 8,674,804 KiB (8.27 GiB) |
| Nix nextpnr evidence | 255 (recorded) | 5:51.49 | 7,196,776 KiB (6.86 GiB) |

An earlier successful exploratory mapping took 5:34:07 and peaked at
8,791,692 KiB; primitive statistics match the Nix result exactly. One initial
Nix attempt completed the expensive mapping work in 2:01:34 but failed while
writing artifacts because a quoted heredoc left `$out` literal in the Yosys
script. That derivation bug was covered by a regression test and corrected;
it is not a synthesis failure of the design.

## What fits before DDR3 integration

The arithmetic and state resources other than LUTs fit individually, but the
complete current RC does not fit because it needs at least 178,982 more
nextpnr LUT sites than the backend reports available. Therefore:

1. Keep the first architectural milestone DDR-free and fully on-chip.
2. Select or generate a smaller RC/model, or reduce LUT expansion enough to
   pass pack/place/route on this device.
3. Only after a fully on-chip candidate fits and runs should DDR3 be added for
   model scaling.

There is a second important limitation: synthesis reads the generated SV with
`--ignore-initial`. This avoids frontend problems but also ignores `$readmemh`
and other initialization blocks. The baseline measures storage and compute
structure; it does **not** prove that a bitstream would contain initialized
weights or perform autonomous board inference. A future fitting on-chip
candidate must include reproducible weight initialization and revalidate
functionality after that synthesis-visible representation is introduced.
