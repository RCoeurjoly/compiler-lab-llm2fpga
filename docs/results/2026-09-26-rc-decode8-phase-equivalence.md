# RC decode-8 compiler-generated RTL equivalence

Status: passed for the independently lowered `decode-8` phase; this is not
yet an integrated three-phase or board result.

The phase was rebuilt through the pinned PyTorch → MLIR → SCF → flat-SCF →
Calyx → SystemVerilog pipeline and simulated with
`scripts/pipeline/run_rc_serving_w4a8_sv.py` inside `nix develop`.  The frozen
reference and all runtime memories came from the authenticated phase export;
no handwritten accelerator RTL was used.

## Artifacts

| artifact | SHA-256 |
| --- | --- |
| generated `main.sv` | `05dde596f14194bcbb5c67cdf71634b3adff93e310438d581c2f478ffeef354a` |
| flat-SCF input | `9f18a5be6525d33047cb01e60f5ca007957fa7a24dc53e5c646dd48ee684e433` |
| simulation receipt | `4203944db6da2be91f8625d56e59a326da712d334cbb79b06f4527f5836f471c` |

The Verilator compile took 304.81 seconds and simulation took 71.07 seconds.
The phase exposed 37 semantic memories and 165 RTL memory ports.

## Exact comparisons

All five outputs matched with zero error:

| output | shape | output hash |
| --- | --- | --- |
| logits | `[1,1,6]` | `3ee0fc78b10d76b3ec11700f33f2dc8a4fd359aab98e9ef25b39611afb4e109e` |
| cache leaf 0 | `[1,1,9,2]` | `aaaf2a1d3cd30606e1c3fd5d674f32db47053ba7bf59253fa1ef0681c19c0d38` |
| cache leaf 1 | `[1,1,9,2]` | `b84fc8bd4be4e8ca5fd7d4f6687212ae8e3d6f90f87472a64e28e1cb8cef992d` |
| cache leaf 2 | `[1,1,9,2]` | `df8078a1387c99eb07312ff8850875fb31dcacb8e76af815de4b0f66ea7b9fc3` |
| cache leaf 3 | `[1,1,9,2]` | `2432491c0ce43027192cc58366fb23f3e04e515773c69d73bcae8d027f31a089` |

This proves the `decode-8` compiler phase independently. It does not prove
phase composition, PCIe ingress, UberDDR3 calibration, P&R, bitstream
generation, or board inference.
