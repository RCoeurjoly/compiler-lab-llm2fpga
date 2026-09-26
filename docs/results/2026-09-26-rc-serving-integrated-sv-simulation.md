# Integrated RC generated-SV simulation diagnostic

The compiler-generated integrated Representative Core shell is now available
from the Nix target
`tinystories-w4a8-rc-serving-integrated-shell`.

Artifact receipt:

- store path: `/nix/store/2rq949b7n3rpmq1wsy0b1hzivfhsbss1-tinystories-w4a8-rc-serving-integrated-shell`
- generated top: `main_1`
- public shell: `rc_serving_w4a8_integrated_reference`
- semantic memories: 104
- RTL memories: 458
- initialized memories: 141
- readback words: 237
- generated-SV SHA-256: `e3928a14c7c6db61ab4cf93dc38ec95e9326bf544d2b00ae4822f4fca7820458`
- shell SHA-256: `450fd19bc2f001db4204ca952d6050d4cbb56d8d1a2bee7d1d5a8fdcfbd09f32`

The harness
`scripts/pipeline/run_rc_serving_w4a8_integrated_sv.py` drives all eight
prompt words through the generated public shell, starts the design, and reads
back all 237 authenticated token/logit/cache words for comparison with the
integrated PyTorch observation.

Two bounded attempts were made against the exact generated shell:

1. Verilator 5.022 with four jobs; front-end elaboration was killed by signal
   9 before simulation.
2. Verilator 5.022 with one job; front-end elaboration was again killed by
   signal 9 before simulation.

The generated file is approximately 1.43 million lines. No clock was
executed, so these attempts provide no functional pass or mismatch result.
They establish an implementation/tool resource blocker. The next action is
to reduce simulator memory pressure or add a staged compiler-generated
simulation route; do not alter the model, quantization, cache ABI, or declare
hardware success from this diagnostic.
