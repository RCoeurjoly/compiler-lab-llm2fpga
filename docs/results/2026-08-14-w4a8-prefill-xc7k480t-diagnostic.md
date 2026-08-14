# W4A8 prefill-8 XC7K480T phase-only diagnostic

Status: mapped Yosys succeeded for the independently generated `prefill-8`
RTL, but nextpnr-xilinx could not place it on Kintex-7
`xc7k480tffg1156-1`. This result is intentionally preserved as a diagnostic;
it is **not** a fit result for an integrated prefill/decode accelerator.

## Why this experiment stopped after prefill

The frozen three-phase reference had been lowered as three separate,
shape-specialized compiler graphs: `prefill-8`, `decode-8`, and `decode-9`.
Each closure was independently bit-exact against its corresponding frozen
PT2E phase, but no single RTL instance passed cache state from prefill through
both decode steps. After this distinction was identified, decode-8 synthesis
was cancelled shortly after startup and decode-9 synthesis was not started.

The correct follow-on target is one stateful RTL instance with persistent
on-chip token/KV-cache state and shared compute across the ordered
`prefill-8 -> decode-8 -> decode-9` sequence.

## Immutable provenance

- Evidence closure:
  `/nix/store/lqly4kzj5q2c3qqjx2z0svz7vcnr7j78-prefill-8-xc7k480t-evidence`
- Verified source SV SHA-256:
  `1657b663c6b3631c94fb2fe25d4ba0612acd57ad3664bc93fdb43884c8d28004`
- Synthesis-normalized SV SHA-256:
  `042aca5e86b8dd72aaaace22d8aa0e521aa069874b90b9712bee42f718c4f36f`
- Evidence receipt SHA-256:
  `4cfd6c76200da0cb3fdffc7ff3073eccfe626d5f5ec5ae7c9d4e88cd49063adc`
- Mapped JSON SHA-256:
  `14335ec8534e7a59629c17387ea4c57ccb606b770646bd60853045e4d5f24dfb`
- nextpnr-input JSON SHA-256:
  `3d40efa99fe7cf2c18b4dfa53c6d7b88ffa659e2f08f580c9a36d8b723bd5845`

The synthesis-only normalizer made two frontend repairs. Its receipt records
the verified source hash and normalized output hash. The source is the
deterministic repository snapshot, so synthesis-side edits cannot regenerate
the PyTorch/MLIR/Calyx pipeline.

## Toolchain and target

- Yosys 0.66, git `7f8fdfd8d7bc08c749a2a969388d3425d4f369d5`.
- nextpnr-xilinx `stable-backports`.
- Device: `xc7k480tffg1156-1`.
- Chip database:
  `/nix/store/6la31fg71mbjaw6wpwj2pddwbs93y2j7-nextpnr-xilinx-chipdb-0.8.2/xc7k480tffg1156.bin`.
- Chip database SHA-256:
  `56c46da98f375b14e12cd6df44dede11b576eba33266cd5a8465fb6fe328baad`.
- Probe target frequency: 12 MHz.

## Resource evidence

| Resource | Mapped Yosys | nextpnr packed | Device capacity | Packed use |
| --- | ---: | ---: | ---: | ---: |
| LUT | 531,682 | 783,671 `SLICE_LUTX` | 597,200 | 131% |
| FF | 35,681 | 35,681 `SLICE_FFX` | 597,200 | 5% |
| BRAM18 | 0 | 0 | 1,910 | 0% |
| BRAM36 | 0 | 0 | 955 | 0% |
| DSP48E1 | 251 | 251 | 1,920 | 13% |

Mapped and packed LUT counts are different metrics: nextpnr expands and packs
the mapped primitive network into its physical `SLICE_LUTX` representation.
The physical count is the decisive capacity result.

nextpnr exited 255 during placement with:

```text
Failed to expand region (0, 0) |_> (309, 416) of 783671 SLICE_LUTXs
```

Legal placement and routing therefore did not complete. No Fmax or critical
path is available, and no timing claim is made.

## Runtime and memory

| Stage | Exit | Wall time | Peak RSS |
| --- | ---: | ---: | ---: |
| mapped Yosys | 0 | 1:19:21 | 8,602,308 KiB |
| nextpnr-xilinx | 255 | 5:17.50 | 7,134,228 KiB |
| outer Nix client | 0 | 1:25:11 | 390,508 KiB |

The outer RSS measures only the Nix client and must not be interpreted as
builder memory. The per-tool GNU-time receipts are authoritative for Yosys
and nextpnr memory.

## Bounded conclusion

The compiler-generated `prefill-8` phase alone does not fit the XC7K480T:
packed LUT demand is 131% of capacity. Instantiating all three phase-specific
engines side by side would be architecturally wrong and cannot improve this
result. This diagnostic motivates, but does not itself verify, a single
stateful shared-compute inference RTL design.

The same facts are retained in
`docs/results/2026-08-14-w4a8-prefill-xc7k480t-diagnostic.json`.
