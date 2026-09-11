# Physical BSCAN timing qualification

Status: active

## Objective

Isolate and fix the YPCB physical `BSCANE2` capture/shift response alignment
without changing the TinyStories model, accelerator, 64-bit JTAG ABI, or
validated 30 MHz implementation constraints. Use a separately validated
CSR-only sentinel with recognizable response patterns and counters for
CAPTURE, SHIFT, and UPDATE. Exercise it through the canonical HS3/MPSSE
transport and record raw TDO bits while sweeping only scan-edge mode, TCK rate,
TDO extraction bit, and capture length. Reproduce the measured TAP vector in
`BSCAN_SIM`, identify the first physical-vs-simulation divergence, and apply
one minimal evidence-backed RTL correction.

## Acceptance gates

1. The existing BSCAN sentinel still passes through the canonical transport.
2. The CSR-only sentinel produces a stable, explainable raw-bit offset/pattern.
3. Simulation reproduces the measured raw sequence.
4. One corrected CSR image passes reset, status, prompt write/readback, and
   START on hardware twice without reprogramming between commands.
5. Only after those gates pass, return to the TinyStories image and run the
   two-token, then 16-token, acceptance protocol.

No host-side bit shifting or ABI change is an acceptable substitute for the
RTL/physical timing correction.

## Initial control result (2026-09-11)

The existing sentinel was reprogrammed through the HS3 and read with the
canonical MPSSE transport at 1024 bits. It passed (`magic_ok=true`, magic
`0x54364a44`, version `1`), confirming that the cable, programmer, USER1
selection, and host TDO extraction path are operational before CSR-specific
experiments.

The physical sweep also passed at capture lengths 64, 65, 66, and 1024 bits.
TDO extraction bit 7 decoded correctly while bit 0 did not. With bit 7, the
sentinel remained valid at 100 kHz, 1 MHz, 6 MHz, and 12 MHz MPSSE rates; its
counter advanced on every read. Thus generic BSCAN capture/shift timing and
host sampling are stable. The `0x07`/`0x0f` TinyStories result is localized to
the CSR response path or its interaction with the system clock, not the cable,
TDO bit, scan length, or global JTAG rate.

The first CSR-only top elaborates, but its inert core-side constants are
constant-folded by Yosys and leave an unplaceable asynchronous FF form in
nextpnr. This is a diagnostic-top synthesis issue, not evidence about
physical BSCAN behavior; the fixture needs observable, non-constant inputs.

An explicit temporary map converts the remaining async FFs to `FDCE`/`FDRE`,
but nextpnr then rejects a generated FF with no resolvable `C` direction. The
diagnostic image is therefore not programmed; the production toolchain's exact
FF mapping sequence must be reused before hardware CSR conclusions are drawn.

Using the production `synth_xilinx` flow, the CSR-only image routed and was
programmed successfully (bitstream SHA-256
`c990a0d56bb792469c96d4e8c9d5283608a946157946a0fa7de0ab834e55b6b5`). The
canonical CSR harness then failed on the first command: reset returned
`0x00000000000000ab` instead of zero. The sentinel's token value is `0xab`, so
the command opcode is being misdecoded as a token-read operation before any
TinyStories logic exists. This is the first hardware-vs-simulation divergence
at the CSR command boundary.

The targeted bit-60 reconstruction was simulated, routed, and programmed
(bitstream SHA-256
`1439d2e66bcd5b759eefd2c8595e8a2c41c63f67dfe1c05ef39871be6b957e39`). The
opcode-loopback probe still returned `0x6000000000000000` for an opcode-7
command. The single-bit-at-UPDATE hypothesis is rejected; the remaining issue
involves transaction framing or command/response timing beyond that bit.

The minimal command correction was built and programmed (bitstream SHA-256
`5e9a3ce4bb37e270ab93a4bab9f73f20f08e68963b0da5c918df49fcb0cc17d9`). Hardware
reset now returns zero, proving the opcode MSB is restored. The following
status command still returns zero instead of `0x2800000000000000`; command
integrity is fixed, while the remaining mismatch is response/event CDC timing.

## Raw-vector sweep (2026-09-11)

`scripts/pipeline/capture_bscan_raw_sweep.py` captured the complete TDO vector
for the CSR-only loopback pattern `0x7123456789abcdef` at 100 kHz, 1 MHz,
6 MHz, and 12 MHz, using 64-, 65-, and 66-bit scans, three repetitions per
case, and TDO extraction bits 7 and 0. The raw receipt is
`/tmp/bscan-raw-sweep.json`.

With extraction bit 7, every rate, length, and repetition returned the same
LSB-first vector, decoding as `0xe2468acf13579bde`. With extraction bit 0,
the 64-bit scan decoded as `0x23456789abcdef7f`, while 65/66-bit scans
changed between repetitions (`0x123456789abcdef7`, `...f7d`, `...f7c`).
This is a stable TDO-pin selection result, not a frequency-dependent timing
failure: bit 7 is the valid HS3 TDO sample and bit 0 is invalid/noisy.

The same endpoint was then captured at 1 MHz with MPSSE negative-edge and
positive-edge drive. Both modes produced the identical raw vector
`0111101111011001111010101100100011110011010100010110001001000111` in all
three repetitions (`0xe2468acf13579bde`). Thus MPSSE drive-edge selection is
not the source of the offset either.

The remaining experiment is therefore an explicit `BSCAN_SIM` TAP replay of
the recorded TMS/TDI sequence, including the final Shift-DR clock and UPDATE
edge. Until that replay identifies the first differing event, no further
response preload or command-bit correction is justified.

## TAP replay comparison (2026-09-11)

`sim/bscan_csr_tap_replay_tb.sv` replays the same 64-bit capture/shift/update
sequence used by the HS3 probe. With system reset held through a clock edge,
the simulation produces a zero first capture and then a loopback response of
`0x7000000000000001` on the following status transaction. The physical CSR
image instead produced `0xe2468acf13579bde` on the first transaction and
`0x6000000000000000` on the next one. This is the first evidenced divergence:
the physical endpoint's capture contents and command/response transaction
framing differ before any accelerator or model logic is involved.

The simulation replay also exposed that the standalone CSR-only sentinel had
no system-clock reset (`sys_rst=0`), allowing unknown state in simulation. The
replay ties reset to the TAP reset for faithful comparison; the production
top already provides the corresponding synchronized reset. The next minimal
experiment is to add observable CAPTURE/SHIFT/UPDATE counters and a fixed
response pattern to the CSR-only top, then determine whether the physical
capture begins one transaction late or whether UPDATE is occurring on a
different event.

The diagnostic counter image was synthesized, routed, and programmed at the
unchanged 30 MHz constraint (bitstream SHA-256
`b7fcf9879c5f4cdd88c8b67b96e701499ac742292c16ea298644fcf37104a41e`). A
hardware sequence of reset, status, status, loopback, status returned
`a000000000000000`, `6000000000000000`, `6000000000000000`,
`e000000000000002`, `6000000000000000`, identical to the pre-counter image.
The proposed one-position command reconstruction therefore had no observable
effect and was reverted; it is not an accepted RTL correction. The counters
are retained for the next diagnostic protocol, which must expose them through
a response pattern that cannot itself be misdecoded as opcode 6.

The fixed-pattern counter-capture image (SHA-256
`94cf5dd89c23376496b24f2de08d68e7aea1f18b5f9d749db361f6cc0eb632f7`) also
failed to expose its `d3...c0de5a17` marker: three direct 64-bit captures
again returned `0xe2468acf13579bde`. This means the diagnostic CAPTURE branch
is not being observed by the physical endpoint at all (or the board is not
executing that image), and is a stronger blocker than a simple response-word
alignment. The next check must verify the programmed image identity and
observe CAPTURE/SHIFT activity without relying on a CSR command response.

An A/B programming check ruled out a stale image. The known-good sentinel was
programmed first and immediately returned its expected magic `0x54364a44`;
the fixed-pattern diagnostic image was then programmed in a fresh FTDI session
and still returned `0xe2468acf13579bde`, never its `d3...c0de5a17` capture
marker. The next experiment must therefore validate the selected USER1 chain
and primitive configuration independently of the CSR module, using a direct
BSCANE2-to-TDO constant/shift sentinel.

The custom probes were also found to select instruction `0x06`, whereas the
canonical reader and the proven sentinel select USER1 instruction `0x02`.
Both probes now use `0x02` (commit `0ebd42a`). Repeating the primitive-only
sentinel with the corrected instruction still returned
`0xe2468acf13579bde`, so the instruction mismatch was a real test defect but
does not explain the remaining physical result.

A controlled `JTAG_CHAIN=2` variant was also built, routed, programmed, and
read with both USER1 (`0x02`) and USER2 (`0x04`); both returned zero and neither
exposed the TDO control. Chain-number inversion is therefore ruled out. The
direct sentinel source was restored to the validated `JTAG_CHAIN=1` setting.

As a final primitive control, the direct sentinel was rebuilt with TDO wired
directly to `SEL` (no scan register or CAPTURE logic). The routed image passed
30 MHz implementation and was programmed (bitstream SHA-256
`7980441f631640bbe40a9a55deade6780ba4754788c285622a7dad1d35872d21`), but a
fresh USER1 scan still returned `0xe2468acf13579bde` rather than all ones.
This removes CSR, CDC, and scan-register behavior from the fault model: the
custom bitstream's user TDO path is not the path being observed physically.

Finally, the primitive-only image was tested with USER instruction values
`0x00, 0x01, 0x02, 0x03, 0x04, 0x06, 0x08, 0x10, 0x20, 0x3f`. None exposed
the programmed `d3...c0de5a17` marker; the observed values were unrelated
IDCODE/USER-register data (for example `0x2d97` at `0x01` and
`0xffffffff` at `0x08`). Thus the failure is not simply selecting the wrong
USER opcode. The physical BSCANE2 CAPTURE/TDO path or the generated primitive
mapping remains the unresolved boundary.

The known-good and custom `.bit` files were compared after the Xilinx sync
word. Both contain the same 18,734,956-byte configuration payload; only 30,096
bytes differ. This confirms the custom image is a distinct, fully generated
configuration rather than a stale upload. The remaining bitstream-level task
is to decode the BSCAN configuration frame(s) within that diff and compare
their chain/TDO routing bits directly.

## Bitstream conversion diagnosis (2026-09-11)

The direct-sentinel FASM was converted again using the Kintex-7 family database
and the exact `xc7k480tffg1156-2/part.yaml` with the canonical
`fasm2frames` → `xc7frames2bit --part_file ... --frm_file ... --output_file ...`
sequence. The repaired image `/tmp/repro.bit` has SHA-256
`5992cce7b197d56478aa1ec46336f65be882ff2a91743500718d2467a3c028d4` and
`bitread` decodes 880,384 set configuration bits. It was programmed on the
YPCB and the direct `BSCANE2.TDO=SEL` sentinel returned all ones for three
independent USER1 scans.

This reproduces the failure boundary: the previously programmed custom image
`/tmp/bscan-const.bit` (SHA-256
`7980441f631640bbe40a9a55deade6780ba4754788c285622a7dad1d35872d21`) has a
malformed bitstream header (`b` record length `0x1278` instead of the normal
one-byte null part record), and `bitread` decodes zero set configuration bits
from it. The image could report DONE while leaving the generated user-BSCAN
configuration absent. The FASM and nextpnr route are therefore not implicated
by the direct hardware test; the defect is in the prior bitstream conversion
invocation/artifact, not in CSR timing or the JTAG transport.

`scripts/pipeline/build_and_validate_xc7_bitstream.sh` now codifies the exact
conversion and rejects any output for which `bitread` finds no set
configuration bits, before programming. The remaining gate is to regenerate
the CSR-only sentinel through this validated path and rerun its hardware
protocol; only then can the TinyStories two-token gate be attempted.

## Validated CSR regeneration (2026-09-11)

The CSR-only FASM was regenerated with the same validated conversion script.
The resulting `/tmp/bscan-csr-fix-repaired.bit` has SHA-256
`21931f389b77bf856e8a9da99c8b6e719431b217f6c3b85f903e7ed27c57aeeb`, and
`bitread` reports 212,360 decoded configuration bits. After programming this
image, the canonical USER1 loopback probe completed three transactions with
the stable pairs `command_response=0x0000000000000000` and
`status_response=0x7800000000000000`. This is the first CSR hardware result
after a bitstream independently verified to contain configuration data.

The status value is not yet treated as the full CSR acceptance gate: the
reset/status/prompt-write/readback/START sequence still needs to be run twice
against this repaired image. The BSCAN bitstream-conversion blocker itself is
resolved for the direct sentinel and CSR image; TinyStories two-token testing
is deferred until that CSR protocol gate is recorded.

## CSR gate after valid conversion (2026-09-11)

The canonical two-run CSR checker was run after programming the repaired CSR
image, without reprogramming between transactions. It failed immediately on
the first status check: expected `0x2800000000000000`, observed
`0x0000000000000000`. A raw loopback probe on the same image returned a stable
`command_response=0x1000000000000000` followed by a response containing the
previous transaction's payload. This reproduces the remaining issue with a
bitstream that `bitread` independently validates and that has already passed
the direct BSCANE2 sentinel.

The active blocker is therefore the CSR sentinel's command/response
transaction alignment across the BSCANE2 UPDATE edge and system-clock CDC.
It is not a nextpnr/prjxray configuration omission, a stale upload, or an HS3
sampling problem. No RTL correction is accepted yet; the next experiment must
instrument or simulate this exact transaction boundary before any change. The
TinyStories two-token gate remains pending.
