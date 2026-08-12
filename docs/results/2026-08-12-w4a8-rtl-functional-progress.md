# W4A8 RC RTL functional progress

Status: functional mismatch under investigation. This is not synthesis or fit
evidence and does not satisfy the W4A8 completion gate.

## Durable inputs

- Frozen three-phase oracle: Nix package
  `tinystories-w4a8-rc-serving-mask10-vocab6-width2-frozen-bundle`.
- Decode-8 equivalence-math SV:
  `/nix/store/89mb8qhbdh0qg8vibbcc20w6ivvhssz7-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-calyx-native-sv`.
- Decode-8 semantic ABI:
  `/nix/store/h7ngmg8zax6hqhgx5k2v1lvijwy193k8-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-flat-scf`.
- Simulation driver: `scripts/pipeline/run_rc_serving_w4a8_sv.py`.

The driver parses the flat-SCF function ABI, verifies it against all generated
`main_1` memory ports, initializes persistent buffers and phase inputs from the
frozen ExportedProgram, services all external Calyx memories, and compares
logits and four cache leaves with `reference.json`.

## Decode-8 results

Both tested RTL variants completed normally. The provisional scout-math RTL
finished in 63,289 cycles; its Verilator build took 400.30 seconds and the
simulation took 60.71 seconds. The polynomial-exp/rational-tanh candidate
finished with the same observable values; its Verilator build took 392.40
seconds and simulation took 68.39 seconds.

| output | elements | maximum absolute error | mean absolute error |
| --- | ---: | ---: | ---: |
| logits | 6 | 0.0524210036 | 0.0167730726 |
| layer 0 key cache | 18 | 0.0418115631 | 0.0034986356 |
| layer 0 value cache | 18 | 0.0368652344 | 0.0032416450 |
| layer 1 key cache | 18 | 0.0354003906 | 0.0026177300 |
| layer 1 value cache | 18 | 0.0394406207 | 0.0040761752 |

The two distinct SV closures have different SHA-256 values, but produce
byte-identical phase outputs. Therefore changing exp/tanh lowering did not
address this mismatch.

## Localization

For every cache leaf, elements 0 through 15—the incoming eight-token cache—are
bit-exact. Only elements 16 and 17, the newly appended key/value pair, differ;
the RTL writes both as zero. The flat-SCF cache append is explicit and has the
correct destination offset: the post-normalization MLIR stores the two new
values at flattened indices 16 and 17 before copying all 18 words to the output
memory. Consequently, the remaining defect is upstream in the newly computed
key/value source buffers or their Calyx execution, not in the final output copy
and not in nonlinear softmax/tanh approximation.

Next action: trace the source buffers feeding those four append stores, add the
smallest reproducer for the first zero-producing operation, fix the responsible
lowering/handshake defect, and rerun decode-8 before prefill/decode-9 or mapped
synthesis.
