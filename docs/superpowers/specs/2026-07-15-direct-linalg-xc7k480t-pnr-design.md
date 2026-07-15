# Direct-Linalg XC7K480T Mapping and P&R Design

## Goal

Produce reproducible FPGA resource evidence for the current small integer
Direct-Linalg route:

```text
torch -> linalg -> scf -> flat-scf -> Calyx -> native SV -> RTLIL
```

The existing RTLIL top is `main(clk, reset, go, done)`.  The new flow must
first map that exact RTLIL through the established staged XC7 Yosys mapper,
then give its mapped JSON to pinned `nextpnr-xilinx` for XC7K480T pack,
place, and route.  Its outputs must include LUT/FF/BRAM/DSP mapping estimates
and a persistent nextpnr utilization report.

## Context and constraints

- Target: `xc7k480tffg1156-1` (Kintex-7 480T), using the existing pinned
  nextpnr-xilinx fork and chip database in `task3-main`.
- The source is the existing Direct-Linalg no-handshake RTLIL derivation, not
  a reconstructed model and not the full W8A8 TinyStories frontier.
- The Direct-Linalg native-SV source list has been verified under the current
  Calyx source pin.  Its RTLIL top is `main`, not Task 3's W8A8-specific
  `main_1`.
- The run is a resource/P&R probe.  It does not establish numerical
  equivalence, a board-ready application interface, timing closure, DDR3
  externalization, or a full-model W8A8 result.
- Durable outputs must be Nix derivations or checked-in files; do not depend
  on an ad-hoc `/tmp` route directory.  Do not garbage-collect existing Nix
  artifacts or rerun the known full W8A8 native-SV frontier for this task.

## Alternatives considered

### A. Map and route the raw `main` core directly (chosen)

Give the staged mapper the existing Direct-Linalg RTLIL with `topName =
"main"`.  Constrain `clk`, `reset`, `go`, and `done` directly to known
package pins used by the repository's Kintex board probe:

| Core port | Probe pin | Direction |
| --- | --- | --- |
| `clk` | `AA28` | input |
| `reset` | `R28` | input |
| `go` | `P30` | input |
| `done` | `M30` | output |

All use `LVCMOS18`.  `go`'s assignment exists only to make the unconstrained
core legal for P&R; this is not a claim that the board can drive a useful
runtime protocol on that pin.  This option preserves a one-to-one source
relationship between the mapped resource report and the placed design.

### B. Add a board wrapper

A wrapper could convert `SYS_CLK`/`SYS_RSTN` into Calyx control and display
`done` on LEDs.  It would make a nicer board demonstration, but it would add
logic and state to the placed design.  That makes the first measurement less
direct and does not help the immediate question of whether the existing
Direct-Linalg RTLIL can be mapped and routed.

### C. Route with no pin constraints

This might yield a packing result but would not exercise the actual package
interface or support a defensible XC7K480T placement result.  It is rejected.

## Design

1. Extend the nested `task3-main` library with a reusable
   `mkTask3XilinxPnrReport` derivation.  It consumes a mapped Yosys JSON and
   XDC, invokes pinned `nextpnr-xilinx` with the existing chip database, and
   stores FASM, complete logs, exit status, and parsed utilization in one Nix
   output directory.
2. The P&R derivation records a failure frontier rather than throwing away its
   log when nextpnr exits nonzero.  A successful result is explicit: zero exit
   status plus a generated FASM.  A non-successful result is never presented
   as routed utilization.
3. Add a small parser for nextpnr's `Device utilisation` table.  It retains
   every parsed resource row rather than guessing a fixed set of aliases, so
   the raw log remains the source of truth if a tool version changes wording.
4. In the root flake, instantiate existing
   `mkTask3XilinxUtilization` with the current Direct-Linalg `.il`, `main`,
   and the established XC7K480T capacities.  Export its mapped report and JSON.
5. Feed that exact mapped JSON and a checked-in/direct Nix XDC into
   `mkTask3XilinxPnrReport`.  Export a root package named
   `tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-nextpnr-utilization`.
6. Build the mapper, then build the P&R package without an arbitrary short
   cutoff.  Record the actual result in a dated document, bounded to this
   Direct-Linalg resource probe.

## Acceptance criteria

- The root package derives from the pre-existing Direct-Linalg no-handshake
  RTLIL and maps top `main` through the existing staged mapper.
- Its mapper output has a machine-readable LUT/FF/BRAM/DSP utilization summary
  against XC7K480T capacities.
- The P&R derivation uses the pinned `nextpnr-xilinx`, the `xc7k480tffg1156`
  chip database, and the same mapped JSON.
- The P&R output contains `nextpnr.log`, stdout/stderr captures, exit status,
  parsed utilization JSON, and FASM on success.
- A report states whether the design actually completed pack/place/route; it
  never turns a failure/partial result into a utilization claim.
- Focused tests and `nix flake check` pass; the user's unrelated
  `docs/glossary.md` work is preserved unstaged.
