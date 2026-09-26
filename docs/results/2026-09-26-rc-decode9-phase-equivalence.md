# RC decode-9 compiler-generated RTL equivalence

Status: passed for the independently lowered `decode-9` phase; this is not
yet an integrated three-phase or board result.

The phase was compiled through the pinned PyTorch → MLIR → SCF → flat-SCF →
Calyx → SystemVerilog pipeline and simulated with
`scripts/pipeline/run_rc_serving_w4a8_sv.py` inside `nix develop`.  The frozen
reference, cache inputs, and immutable memories came from the authenticated
phase export. No handwritten accelerator RTL was used.

## Artifacts

| artifact | SHA-256 |
| --- | --- |
| generated `main.sv` | `371133ea7a03a0ff4a38a53118203df0efd10671b5284e8ac1879f4568a350b8` |
| flat-SCF input | `658baaa766a565904b25cfaff1577f6e11ada3dd5550bd7c6d9f200cb409b4fa` |
| simulation receipt | `6f4bc95c096e14ae4582dac31f16cb4e33016ac35009c01136c2e3f31bc7b977` |

The Verilator compile took 306.12 seconds and simulation took 73.43 seconds.
The phase exposed 37 semantic memories and 165 RTL memory ports.

## Exact comparisons

All five outputs matched with zero error:

| output | shape | output hash |
| --- | --- | --- |
| logits | `[1,1,6]` | `cb5bd32a289aba8b5644e536c2a6600b0587a0d7fbeb0838c2b5689fa27d4577` |
| cache leaf 0 | `[1,1,10,2]` | `2057919e2eb9b4f6cef6c1a8dc65ce611abab17056fc12377ec8861b5106af12` |
| cache leaf 1 | `[1,1,10,2]` | `d39bd665bf051288fec683fd91bb015e9be4584691011917dbe3bcd56ef82f11` |
| cache leaf 2 | `[1,1,10,2]` | `4ee37d3cc4e463d029860561fceea4ce174c045a21056632112ea5b66ca0bfba` |
| cache leaf 3 | `[1,1,10,2]` | `604a7407e185188844f2f084da3d76ef15c14291b2f43d1ccd99a73638c1bb12` |

This proves the `decode-9` compiler phase independently. It does not prove
phase composition, PCIe ingress, UberDDR3 calibration, P&R, bitstream
generation, or board inference.
