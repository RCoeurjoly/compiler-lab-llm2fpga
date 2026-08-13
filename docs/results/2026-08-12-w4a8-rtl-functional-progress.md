# W4A8 RC RTL functional progress

Status: decode-8 and decode-9 pass bit-exactly; prefill-8 validation is in
progress. This is not synthesis or fit evidence and does not yet satisfy the
three-phase W4A8 completion gate.

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

## Integer-to-float handshake experiment

Static inspection found that CIRCT-exported `sitofp` groups wrote their result
register unconditionally while the packaged `std_intToFp` wrapper advertises a
two-cycle completion interval. Commit `fa2e0fa` generalized the existing
FP-to-int handshake normalizer to gate both conversion directions with the
converter `done` signal. The regenerated reproducible decode-8 closure is:

`/nix/store/8s7207dgrj6s6s8n7gk8klx9amxpcdfa-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-calyx-native-sv`

Its normalizer checked 3,408 Calyx groups and verified 335 gated floating-point
conversion handshakes, including 207 `sitofp` captures and no remaining
unconditional `sitofp` captures. Native Calyx-to-SV export consumed about 36
minutes of single-threaded CPU time. This repair increased decode execution
from 63,289 to 66,587 cycles, but did not change any observable output byte.
The Verilator build took 339.41 seconds and simulation took 70.95 seconds.
Therefore the handshake defect is real protocol debt but is not the cause of
the current numerical mismatch.

An isolated simulation of the exact generated `std_intToFp` module also passed:
signed integer 45 produced IEEE-754 `0x42340000` (45.0), with the expected
`go`/`done` timing.

## Corrected zero localization

Final scratch-memory contents are unsafe for tracing because Calyx reuses each
external scratch port many times. An initial end-of-run dump showed port 95 as
`0x0a, 0x0a` while its dequantized port 100 ended as zero. Cycle-local tracing
of FSM states 992 through 994 corrected that interpretation:

- At cycles 7,652 and 7,670, the two port-95 reads see `0xdd` (signed -35), not
  the later final value `0x0a`.
- The shared load register captures `0xdd` and sign-extends it to
  `0xffffffdd`.
- The dequantization zero point is also `0xffffffdd` (-35), so the shared
  subtractor correctly produces zero.
- `std_intToFp` consequently receives zero, produces zero, and port 100 is
  written with `0x00000000` for both lanes.

The sequential external-memory fixture matches Calyx's packaged `seq_mem_d1`
contract: registered read data and `done` update together, followed by the
split load-register state. The first wrong boundary is therefore upstream of
this dequantization: the key-projection quantizer writes its zero point into
port 95. The next diagnostic must trace the floating projection value entering
the FP-to-int quantization that produces those `0xdd` words; neither the memory
fixture nor `std_intToFp` should be changed based on the end-of-run scratch
dump.

## First key-projection MAC localization

Two further cycle-local traces followed the first layer-0 key value backward
through its repeated QDQ and initial quantization. The Calyx allocation numbers
below are aggressively reused scratch memories, so these observations are tied
to the named FSM intervals rather than final memory contents.

- FSM states 908 through 923 read `arg_mem_93[0:1]` as
  `0x00000000, 0x00000000`, divide by the layer-0 key scale, and write
  `arg_mem_95[0:1]` as `0xdd, 0xdd` (-35 in signed i8). Thus the first key
  quantizer receives exact float zero; the later QDQ path is not losing a
  nonzero value.
- FSM states 696 through 707 read the initial key-quantized buffer
  `arg_mem_72[0:1]` as `0xdd, 0xdd`, correctly subtract -35, and write
  `arg_mem_93[0:1]` as float zero. This proves the zero already exists at the
  initial key projection quantizer.
- FSM states 630 through 684 cover that projection's 2-by-2 signed-int8 MAC,
  i32-to-f32 conversion, scaling, and first quantizer. `arg_mem_92[0:1]`, the
  two i32 accumulators, is initialized to zero and every one of its four MAC
  writes stores zero. `arg_mem_71[0:1]` consequently receives float zero and
  the first quantizer writes `arg_mem_72[0:1] = 0xdd, 0xdd`.

The earliest demonstrated bad boundary is now the layer-0 key projection's
i8-by-i8 MAC, before all floating-point conversion and quantization. The next
diagnostic is to capture both signed operands and the multiply/add result for
the four accumulator writes. That will distinguish zero/corrupt activation or
weight inputs from integer multiply/add lowering or scheduling failure.

Disposable trace logs from this investigation are
`/tmp/w4a8-tracekey-run.log` and `/tmp/w4a8-tracekeydot-run.log`; the generated
SV remains the immutable Nix closure recorded above. The temporary paths are
diagnostic breadcrumbs, not required durable inputs.

## Root cause and bit-exact decode-8 result

Operand-level tracing proved that the key-projection weights were nonzero
(`0xfd, 0x07, 0x05, 0x03`) while both activation operands were zero. Following
the activation backward showed that layer normalization computed valid
approximately +/-0.983 values, but then multiplied them by an all-zero gamma
memory and added an all-zero beta memory.

The generated Calyx module externalizes every memory, including 19
`memref.global` constants placed immediately after the 37 semantic function
ports. The original W4A8 fixture initialized only the 32 phase inputs and
zero-filled every remaining external memory. In decode-8, global ordinals 15
and 16 map to ports 52 and 53, exactly the beta and gamma memories observed as
zero in the trace. This was a simulation-fixture ABI defect, not an arithmetic
lowering defect.

The fixture now parses `memref.get_global` order from the exact flat-SCF input,
extracts exact f32 dense-resource payloads, supports the inline f32 sentinel
and dense i64 shape constant, validates each binding against the RTL width and
depth, writes its memory image, and emits the binding list in the result
receipt. Regression coverage requires both binding order and fixture preload
behavior.

With all 19 global memories initialized, decode-8 passed bit-exactly against
the frozen PT2E oracle:

- 66,587 cycles;
- 437.08 seconds Verilator build time at `-j2`;
- 69.97 seconds simulation time;
- logits: 6/6 words bit-exact, maximum absolute error 0;
- four cache leaves: 72/72 words bit-exact, maximum absolute error 0.

The full temporary receipt is
`/tmp/w4a8-decode8-globals-fixed-report.json`. Its authoritative inputs remain
the immutable Nix closures listed above; the temporary result will be followed
by the durable three-phase receipt set.

## Bit-exact decode-9 result

The same corrected fixture passed decode-9 without further RTL or harness
changes. Its immutable inputs are:

- native SV:
  `/nix/store/0p8l2wb6ds8jra3x769phy39iznknz8v-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-calyx-native-sv`;
- flat-SCF ABI and globals:
  `/nix/store/qakr720c5xcfjfw8lwj3isc14vk39izz-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-flat-scf`;
- frozen PT2E oracle:
  `/nix/store/aqisbg3vq3zahd9snx7f97gf6zg9ih8r-tinystories-w4a8-rc-serving-mask10-vocab6-width2-frozen-bundle`.

Results:

- 522.06 seconds Verilator build time at `-j2`;
- 74.33 seconds simulation time;
- logits: 6/6 words bit-exact, maximum absolute error 0;
- four ten-token cache leaves: 80/80 words bit-exact, maximum absolute error 0;
- all five actual-output SHA-256 values equal their expected-output values.

The full temporary receipt is
`/tmp/w4a8-decode9-globals-fixed-report.json`. As with decode-8, the Nix store
paths above are the authoritative reproducible inputs. Prefill-8 remains the
only unvalidated phase before mapped synthesis can begin.
