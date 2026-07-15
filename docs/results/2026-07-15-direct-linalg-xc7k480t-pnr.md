# Direct-Linalg representative core: XC7K480T mapping and P&R

Date: 2026-07-15

## Outcome

The existing Direct-Linalg, no-handshake representative-core RTLIL now has a
reproducible staged mapping result and a successful `nextpnr-xilinx`
pack/place/route result for `xc7k480tffg1156-1`.  The router exited with status
zero and emitted a nonempty FASM.

This is the first actual XC7K480T P&R utilization report for this route.  It
uses the existing
`tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-il`
input and top module `main`; it is not a full TinyStories model fit result.

Reproduce it with:

```sh
nix build \
  .#tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-nextpnr-utilization \
  -L --no-link --print-out-paths
```

The recorded output was:

```text
/nix/store/nfjf3qjdhrsv4g81k67m5mx0ivm25qma-tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-nextpnr-utilization
```

Its `route.json` records `status: success`, `exit_status: 0`, and a present
`design.fasm`.  The pinned nextpnr-xilinx source is the `stable-backports`
revision `4ef2518428b33f160ff93d38c781f08cc3a41566`.

## Measured configuration

- Device: Xilinx Kintex-7 `xc7k480tffg1156-1`.
- Mapper: the existing staged Task 3 `synth_xilinx -family xc7` route.
- P&R: pinned nextpnr-xilinx using the `xc7k480tffg1156.bin` chip database.
- Top: `main`.
- Probe ports: `clk`, `reset`, `go`, and `done` only.
- Probe pins: `AA28`, `R28`, `P30`, and `M30`, all `LVCMOS18`.

The XDC is deliberately P&R-only.  It constrains the raw core without a
wrapper and is not a board interface or equivalence-test interface.

## Staged mapper estimate

The mapper counts boxed Xilinx primitive modules as leaves, rather than
descending into their simulation bodies.  Its resource estimate is therefore
the mapped primitive count, before physical packing.

| Resource | Used | XC7K480T capacity | Estimate |
|---|---:|---:|---:|
| CLB LUTs | 4,192 | 298,600 | 1.40% |
| CLB FFs | 645 | 597,200 | 0.11% |
| Slice lower bound | 524 | 74,650 | 0.70% |
| DSP48E1 | 0 | 1,920 | 0.00% |
| RAMB36E1 equivalent | 0 | 955 | 0.00% |

The largest mapped leaves are 1,442 `LUT6`, 949 `LUT2`, 645 `FDRE`, 686
`MUXF7`, 254 `MUXF8`, and 38 `CARRY4` instances.

## Actual nextpnr pack/place/route utilization

`nextpnr-xilinx` completed P&R and reported the following device resources:

| nextpnr resource | Used | Available |
|---|---:|---:|
| `SLICE_LUTX` | 5,323 | 597,200 |
| `SLICE_FFX` | 645 | 597,200 |
| `CARRY4` | 38 | 74,650 |
| `RAMB18E1` | 0 | 1,910 |
| `RAMB36E1` | 0 | 955 |
| `DSP48E1` | 0 | 1,920 |
| `BUFGCTRL` | 1 | 32 |
| `PAD` | 4 | 946 |

The packed design has 5,323 `SLICE_LUTX` cells: 1,131 `LUT1`, 949 `LUT2`,
617 `LUT3`, 572 `LUT4`, 612 `LUT5`, and 1,442 `LUT6`.  It has 645 `FDRE`
cells and 940 `SELMUX2_1` cells from 686 `MUXF7` plus 254 `MUXF8` instances.
The post-route log reports 100.03 MHz for its `main_1_instance_clk` domain and
a pass at the 12 MHz probe constraint.

The mapper's 4,192 CLB-LUT estimate and nextpnr's 5,323 `SLICE_LUTX` count
are intentionally reported as different metrics.  nextpnr packs mapped
carry/mux support into physical slice resources and reports a different
resource denominator; its placed/routed table is the authoritative result for
this exact implementation run.

## Boundary of the claim

This result establishes that the selected representative core can be mapped
and routed on the target device with the stated probe constraints.  It does
not establish any of the following:

- functional equivalence to PyTorch or to the PT2E W8A8 reference;
- a usable board-level input/output protocol;
- full-model TinyStories weight and activation memory fit, DDR3 traffic, or
  external-memory correctness;
- timing closure for a production clock or board implementation; or
- a comparable replacement for the earlier full F32 resource result.

In particular, zero BRAM/DSP here describes this emitted representative core,
not a proof that all TinyStories memories have been externalized or that the
full model fits the XC7K480T.
