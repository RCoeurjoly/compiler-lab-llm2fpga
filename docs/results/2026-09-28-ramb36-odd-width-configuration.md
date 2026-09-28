# RAMB36 odd-width configuration correction

## Evidence and scope

The unchanged compiler-generated two-token YPCB image returns `[11,1375]`,
not the authenticated `[11,612]`. Physical snapshots localize active embedding
product mismatches to parity-lane coefficient bits at odd packed addresses.
The selected initialization bit is present in the mapped parameters, original
FASM, decoded bitfile, and live FPGA. Missing weight initialization is not the
explanation for this selected bit.

[Project X-Ray's RAMB36 documentation](https://f4pga.readthedocs.io/_/downloads/prjxray/en/latest/pdf/)
(PDF page 58) requires a RAMB36-specific mode feature for widths 1 and 9,
in addition to each RAMB18 half's width. The original nextpnr writer emitted
only the half widths. All 754 production RAMB36 `READ_WIDTH_A=9` instances
lacked the required feature, and their original encoded mode bits were zero.
For the sensitized `core.token_weight_codes_packed_b1.mem.0.1`, the missing
feature is `BRAM_L_X26Y150.RAMB36.BRAM36_READ_WIDTH_A_1`, encoded at
frame `0x00400d1b`, word 5, bit 24.

The accepted first-token image's retained frames also have no enabled
RAMB36 odd-width macro features. Its original mapped width inventory is no
longer available, so this does not establish which baseline instances required
them. Passing token 11 is not proof of complete memory-read correctness.

The correction is isolated in `nextpnr-kintex-bram-mode-fix`, layered on the
pinned checkpoint diagnostic. Patch 0045 emits each port's macro feature only
for RAMB36 widths 1 or 9. It changes neither INIT data, compiler RTL, model,
arithmetic, placement, routing, clocks nor constraints. Existing packages and
the accepted image remain unchanged. This work is LLM-assisted.

## Executed red/green regression

`tests/test_nextpnr_bram_mode_cli.py` invokes the actual public nextpnr CLI
with placed RAMB36/RAMB18 fixtures and reads its emitted configuration.
The original executable fails all eight odd-width read/write-port cases
because the required macro features are absent. Even-width and RAMB18
negative controls pass. No mocked writer or source-text grep is involved.

The corrected executable passes both mode tests, including the half-width
checks and absence of unexpected macro features:

```sh
nix build --impure .#checks.x86_64-linux.nextpnr-kintex-bram-mode \
  --no-link --max-jobs 1 --cores 2
```

Tool: `/nix/store/wwmfz02wyiy4gvav7n76jmhnpiyfj3q9-nextpnr-xilinx-kintex-bram-mode-fix-0.8.2`.
Check: `/nix/store/5zdqlcnww6vbzcks43f0dsjmbsdnkkp8-nextpnr-kintex-bram-mode`.
The existing checkpoint public-CLI regressions also complete successfully
against the corrected executable.

The first Nix attempt stopped before compilation because the patch hunk's
declared added-line count was incorrect. The corrected patch builds and runs
the regression; this packaging error is not an accelerator failure.

## Verification limits

The repository-wide command `nix develop --impure -c python -m unittest
discover -s tests -v` was bounded to 180 seconds and exited 124 while executing
`test_full_pinned_loader_shell_bar_fixture`. It has no final suite result;
the repository suite is not claimed green.

Configuration-only full-checkpoint regeneration completes successfully.
All 132,911 cell records (including parameters, BELs, ports and connections)
and all 334,332 net-bit aliases are unchanged. All 3,314,716 sorted routed
wire/PIP/strength triples match. Serialization order differs for 123,279 nets;
no routed resource differs. The old generic route checker initially rejects
the retained writer's single-space encoding for an unrouted alias. The direct
comparison strips whitespace only for empty routes and validates every
nonempty triple; it does not choose substitute PIPs or tolerate route changes.

The complete FASM line-set comparison preserves all 2,774,525 prior entries,
adds exactly the 754 required macro features, and removes none. This entry
count treats an INIT vector assignment as one entry, not 256 expanded bits.
Detailed receipts are `bram-mode-fix/checkpoint-identity.json` and
`bram-mode-fix/fasm-delta.json`; executed diagnostic checkers are retained in
`mapped-cproj-cone/check-fixed-bram-{checkpoint,fasm}.py`.

The first direct prjxray invocation stops immediately on a missing `fasm`
Python dependency. Bitstream conversion is now running in the existing
`task3-main` Nix development environment, which supplies the pinned prjxray
Python dependencies. Corrected-bitstream programming and board inference
have not yet been verified. Do not equate fixing the documented configuration
omission with proving the cause of token 1375.

The user explicitly authorizes this diagnostic checkpoint despite incomplete
repository-wide verification and pending hardware revalidation. It is not
two-token, sixteen-token, or full timing acceptance.

The retained diagnostics are under
`.superpowers/sdd/2026-09-09-tinystories-16-token-board/checkpoint-recovery-20260928/`,
particularly `mapped-cproj-cone/` and `bram-mode-fix/`. Physical inference must
pass before this is described as an accelerator correction. Full sixteen-token
board acceptance and PCIe/DDR3 integration remain outstanding.

The pinned Kintex chipdb has no cell-timing tile types; LUT/carry delays fall
back to estimates and BRAM/DSP internal timing remains omitted. Regeneration
without routing does not repair or expand this timing coverage. Neither a
passing tool regression nor functional board success proves full timing
qualification.
