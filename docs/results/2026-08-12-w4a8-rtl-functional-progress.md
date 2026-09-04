# W4A8 RC RTL functional progress

Status: the canonical prefill-8, decode-8, and decode-9 SystemVerilog closures
all pass bit-exactly against their frozen PT2E references. This completes the
user-narrowed three-phase compiler-lowering and RTL-simulation gate. It is not
synthesis or FPGA-fit evidence; those activities are explicitly deferred.

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

## Prefill-8 completion and mismatch

Prefill native export completed successfully after about 100 minutes of
single-threaded Calyx backend work. Read-only process samples observed a peak
of at least 30,216,268 KiB RSS (93.0% of host RAM) before completion. Its
immutable inputs are:

- native SV:
  `/nix/store/assf2zarkj7w8rvwvaxi3f8v6wimq1ig-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-calyx-native-sv`;
- flat-SCF ABI and globals:
  `/nix/store/hnrx9lj23ay9vrd2glxn8msc7ak3yh81-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-flat-scf`;
- frozen PT2E oracle: the same `aqisbg...` bundle recorded for decode-9.

The prefill ABI contains 32 inputs and five outputs. Four inputs are legitimate
zero-extent float buffers represented by CIRCT with placeholder i64 address
ports; the fixture now models each with one inert SystemVerilog word instead of
incorrectly deriving a `2^64`-word array. Prefill produces all 48 token logits,
whereas the oracle records only the final token's six logits, so comparison
correctly selects the six-word suffix only for that output.

With those fixture defects corrected, RTL execution completed in 545,149
cycles. Verilator compilation took 550.50 seconds at `-j2` and simulation took
604.64 seconds. All 20 externalized globals were initialized, but all five
outputs mismatch:

| output | elements compared | maximum absolute error | mean absolute error |
| --- | ---: | ---: | ---: |
| final-token logits | 6 | 0.0519332476 | 0.0223150673 |
| layer 0 key cache | 16 | 0.0620839559 | 0.0182838875 |
| layer 0 value cache | 16 | 0.0563787408 | 0.0165891654 |
| layer 1 key cache | 16 | 0.0462513333 | 0.0152232575 |
| layer 1 value cache | 16 | 0.0452499185 | 0.0116998931 |

The cache outputs are nonzero, while the final six words of the 48-word logits
memory are zero. The next localization boundary is therefore the final logits
write path and its upstream LM-head input, followed by the first cache
divergence if that zero is merely a downstream symptom. The full temporary
receipt is `/tmp/w4a8-prefill8-globals-fixed-report.json`.

### Prefill LM-head localization and Calyx backend defect

End-of-run dumps are safe for the final LM-head scratch memories because they
are the last computation and are not reused afterward. They establish:

- port 158 (`alloc_238`, 48 i32 LM-head accumulators) is all zero;
- port 159 (`alloc_239`, 48 dequantized f32 logits) is all zero;
- port 160 (`alloc_241`, 48 quantized i8 logits) is all zero.

The exact MAC operands are nevertheless nonzero. Port 73 contains the final
normalized activations
`81 7f 7d 8a 7f 7f 93 6d 80 80 7f 7f 80 7f 3f 7f`, and port 157 contains the
transposed LM-head weights
`fa 01 ff 01 fe 04 03 00 fe 02 fc 07`. Signed software reconstruction of the
8-by-2 times 2-by-6 MAC yields 48 nonzero accumulators (for example the first
row is `1143, -127, -127, 127, -254, 381`). Thus zero is not mathematically
plausible and neither operand memory is missing.

The generated Futil group `bb0_4755` correctly specifies:

```text
arg_mem_158.write_data = std_add_1551.out;
```

but native Calyx's emitted SV instead contains:

```text
bb0_4755_go_out ? std_add_1560_out : 'x;
```

`std_add_1560` belongs to later floating-point rounding logic. Many unrelated
SV mux branches also collapse onto this same last adder output, so this is not
a one-off LM-head wiring error. The native backend log contains two warnings:
`Data path infer did not converge after 5 iterations`, but the derivation still
reports success. The demonstrated cause is therefore a native Calyx data-path
mux inference failure at this design scale, after correct Futil export and
before any llm2fpga SV simulation or synthesis normalizer.

The required repair surface is systematic: reconstruct each affected emitted
mux branch from the corresponding named Futil group assignment, validate the
rewritten branch count and absence of contradictory drivers, then regenerate
the immutable closure and rerun all three phases. Hard-coding port 158 would
leave the other collapsed branches corrupt and is not acceptable.

#### `infer-data-path` exclusion experiment

Disabling only Calyx 0.7.1's `infer-data-path` pass is not a repair. A complete
Nix rebuild produced the immutable closure
`/nix/store/bm6zl9q6j9y18bcwmdsz62cw7adf2in8-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-calyx-native-sv`
with SV SHA-256
`9c7efa1fa6daef20117843f143864a078bd6909971e918d35a709ad87f49ef58`.
The rebuild took 1:50:08 wall time. Host samples observed essentially all
30 GiB RAM occupied plus about 5 GiB swap; `/usr/bin/time` measured only the
Nix client, not the daemon-side builder, so its 439,516 KiB maximum RSS is not
the builder peak and must not be reported as such.

The non-convergence warning disappeared, but Calyx cell sharing still mapped
`bb0_4755` onto `std_add_1560`. More importantly, that shared adder's operand
muxes select floating-point registers during `bb0_4755`, not the Futil group's
`load_542_reg.out` and `muli_494_reg.out`. The dedicated W4A8 harness completed
545,149 cycles after 406.45 seconds of Verilator compilation and 618.25 seconds
of simulation. All five comparisons reproduce the original mismatch exactly,
including every actual SHA-256 and error metric. This falsifies
`infer-data-path` exclusion as a sufficient fix and moves the next controlled
experiment to the `cell-share` pass that creates the invalid shared datapath.

#### Targeted accumulator protection

A global `-d cell-share` diagnostic was not viable: it ran for roughly 90
minutes while host samples showed essentially all 30 GiB RAM and about 6 GiB
swap occupied, then terminated without an output SV file or `/usr/bin/time`
completion footer. Kernel OOM records were unavailable to the unprivileged
session, so this is recorded conservatively as an external/resource-limit
termination rather than a proven OOM-killer event.

Inspection of pinned Calyx revision `5a4303847392609cad83dda6f4bdffc8cc0e5c89`
showed that `cell-share` excludes cells carrying `@protected`. Optimizer-only
experiments localized the minimum protected path for `bb0_4755`: the
`std_add_1551` adder plus `load_542_reg` and `muli_494_reg`. Protecting only the
adder was insufficient because cell sharing renamed its two operands to
`mulf_89_reg` and `addf_81_reg`; protecting all three retained the original
Futil assignments after `pre-opt`:

```
arg_mem_158_write_data = std_add_1551.out;
std_add_1551.left = load_542_reg.out;
std_add_1551.right = muli_494_reg.out;
```

The pipeline experiment marked every structurally analogous memory write fed
by a two-input cell, together with that cell's two operand cells, as protected.
On the frozen prefill Futil this protected 48 cells while retaining sharing
everywhere else. The resulting immutable closure was
`/nix/store/6a50w0406b3kwf2qd5b6a8ncixcsvbjc-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-calyx-native-sv`;
its SV SHA-256 was
`a21922a4552678af6b97765272eff48d8a62c251a4f23da619bccba0938e1211`.
The full Nix invocation completed successfully in 5:38:53 wall time. Host
samples showed about 30 GiB resident memory and 5.4 GiB swap use at the Calyx
backend plateau; `/usr/bin/time` again measured only the Nix client and its
439,100 KiB maximum RSS is not the builder peak.

The structural repair did not change behavior. Verilator compilation took
384.21 seconds, simulation took 616.30 seconds, and the design completed in
545,149 cycles. Every one of the five actual output SHA-256 values was
byte-identical to the pre-repair run, with status `mismatch`. A throwaway
hierarchical trace then observed `bb0_4755` execute 96 writes: all 96 write-data
values were nonzero, 48 left operands were nonzero, and 88 right operands were
nonzero. For example, address zero accumulated `0 + 0x2fa = 0x2fa`, followed
by `0x2fa + 0x17d = 0x477`.

This falsifies the claimed accumulator-mux failure: the shared registers'
static names were misleading, but their live values were correct. Targeted
`@protected` annotations are therefore not a functional repair and must not
remain in the production pipeline. Localization must move earlier than the
final integer accumulator and use dynamic first-divergence evidence.

#### Dynamic LM-head and final-normalization boundary

An address-for-address comparison against intermediates captured with a
`torch.fx.Interpreter` established a sharper boundary. The PT2E LM-head input
is the signed-int8 tensor
`[[-127,127], [127,-127], [-126,126], [-104,104], [-65,65], [21,-21],
[-128,127], [-122,122]]`; the weight is
`[[-6,3], [1,0], [-1,-2], [1,2], [-2,-4], [4,7]]`. The RTL accumulator's
first six final sums match the PT2E integer dot products exactly, but address
6 is the first mismatch (`-1104` versus `-1143`). Thus the final signed
multiplication, weight layout, and accumulation are functional for matching
inputs, while the activation at token position 1 is already wrong.

A second throwaway Verilator trace captured the physical 16-word float memory
at the final LayerNorm centering write. The diagnostic build took 11:13.68
wall time and 15,400,124 KiB maximum RSS; simulation took 10:15.20 and 11,444
KiB maximum RSS, completing normally in 545,149 cycles. Comparing its IEEE-754
words with `dequantize_per_tensor_95 - mean(dequantize_per_tensor_95)` from
PT2E shows indices 0 and 1 bit-exact:

```
index 0: -0.016493970528244972
index 1:  0.01649397239089012
```

The first divergence is index 2: RTL `0.016230067238211632` versus PT2E
`0.016493970528244972`; indices 2 through 15 all differ. This proves the bad
value is present before the final LayerNorm reciprocal-root and quantization
steps and moves localization into the final residual stream. End-of-run
contents of compiler-allocated memories must not be assigned logical tensor
identities without operation-qualified write tracing because Calyx reuses
those memories.

An operation-qualified trace of the exact Calyx group implementing PT2E
`add_11` (`bb0_4565`) then split the final residual into its two operands.
The diagnostic build completed in 11:14.93 wall time with 15,399,980 KiB
maximum RSS. Simulation completed normally in 10:17.53, used 11,340 KiB
maximum RSS, and again took 545,149 cycles. All 16 floating operand pairs and
sums were compared bitwise with PT2E. The left operand
`dequantize_per_tensor_76` first differs at index 2: RTL
`-0.012405932880938053` versus PT2E `-0.011086152866482735`. At that same
index the right/MLP operand `dequantize_per_tensor_94` is still bit-exact at
`0.000244140625`. The right operand first differs later, at index 4. Therefore
the earliest known divergence is not introduced by final residual addition or
the second block's final MLP projection; it is already present in the
`quantize_per_tensor_49` stream feeding both `dequantize_per_tensor_75` and
`dequantize_per_tensor_76`. Localization now moves to the two operands of the
preceding PT2E `add_8`.

The dequantized left-operand trace can be inverted exactly through
`dequantize_per_tensor_76`'s scale `0.00026395602617412806` and zero point 42.
The expected `quantize_per_tensor_49` codes are
`[-128,-4,0,-123,10,117,84,116,-12,1,127,123,-96,67,27,99]`; RTL supplies
`[-128,-4,-5,-123,7,117,79,116,-19,2,125,123,-101,67,25,99]`. All odd
indices except 9 are exact, while every even index from 2 through 14 differs.
This structured feature-lane pattern is evidence against random floating-point
noise and points toward one operand or lane of the preceding `add_8` stream.

A candidate mapping of `add_8` to `bb0_4103` was explicitly falsified. The
instrumented group executed 64 times (the displayed completion pulse was high
for 24 sampled cycles) under an 8-by-8 control nest and produced values that
cannot represent the 16-element `add_8` ABI. Its diagnostic build took
11:16.21 wall time and 15,399,856 KiB maximum RSS; simulation took 10:19.47,
11,352 KiB maximum RSS, and 545,149 cycles. None of its values are used as
functional evidence. Proximity in generated block numbering is insufficient
for mapping flat-SCF operations through Calyx; the next trace must be derived
from loop extents and memory bindings.

Applying that structural rule found `bb0_3639` / `std_addFN_141`: it is in an
exact 8-by-2 control nest, reads two 16-word floating memories, and writes the
shared 16-word scratch memory. The trace emitted exactly 16 completed
additions, validating the ABI mapping. Its build took 11:16.87 wall time and
15,400,112 KiB maximum RSS; simulation took 10:17.44, used 11,312 KiB maximum
RSS, and completed in 545,149 cycles.

The trace proves the attention operand `dequantize_per_tensor_74` is the
earliest currently known divergence. At every even index RTL supplies exactly
`0.00048828125` while PT2E supplies `0.0009765625`; all eight odd indices are
bit-exact at `0.000244140625`. The incoming residual
`dequantize_per_tensor_56` is bit-exact at indices 0 and 1 and first diverges
at index 2. Thus `add_8` itself is correct, while the second block's attention
output has a systematic factor-of-two error on feature lane zero before the
residual addition. Localization moves through the identity `dropout_5` and
equal-scale `quantize_per_tensor_48` toward `linear_9` /
`quantize_per_tensor_47`.

Because `dropout_5` is disabled and q47/q48 share scale `0.000244140625` and
zero point -128, the accepted attention trace recovers the q47 codes exactly.
PT2E expects alternating `[-124,-127]`; RTL has `[-126,-127]`. Thus the
lane-zero error is already present at q47, not introduced by dropout or q48.

The structurally mapped `linear_9` bias-add group is `bb0_3523` /
`std_addFN_136`, also in an exact 8-by-2 nest. Its diagnostic build took
11:13.43 wall time and 15,399,872 KiB maximum RSS; simulation took 10:15.35,
used 11,408 KiB maximum RSS, completed in 545,149 cycles, and emitted exactly
16 projection results. Both lane biases are zero. RTL repeats pre-q47 floats
`[0.0004172982880845666, 0.00013681911514140666]`; PT2E repeats
`[0.000900440732948482, 0.00028646501596085727]`. Therefore q47 correctly
quantizes its input, but the scaled two-term integer dot product feeding
`linear_9` is already wrong. Localization moves into the integer accumulator,
activation zero-point subtraction, weight layout, or product scale of the
second attention output projection.

An operand-level trace of the structurally corresponding integer accumulator
(`bb0_3512` / `std_add_1164`) rules out its sequencing, address generation,
weight layout, and downstream product scale. The diagnostic build took
11:14.29 wall time and 15,400,016 KiB maximum RSS; simulation took 10:14.78,
used 11,416 KiB maximum RSS, completed normally in 545,149 cycles, and emitted
the expected 32 accumulator writes (8 positions by 2 outputs by 2 reduction
terms). For each even output address, RTL accumulates `224 + 264 = 488`; for
each odd address it accumulates `160 + 0 = 160`. With the frozen signed-int8
weight rows `[7, -8]` and `[5, 0]`, these products prove that the centered RTL
activation is `[32, -33]`, hence its pre-subtraction q46 codes are `[42, -23]`
at zero point 10. PT2E instead supplies q46 `[77, -63]`, whose correct integer
dots are `1053` and `335`. The accumulator correctly computes the values it is
given and the observed post-scale floats are consistent with dots 488 and 160.
The first known defect therefore moves upstream to the producer of q46; no
accumulator or projection-scale fix is justified by the evidence.

Tracing q46's quantization loop (`bb0_3440` through `bb0_3468`) separates the
quantizer from its floating input. A first diagnostic confirmed that it emits
alternating codes `[42, -23]` consistently, but its displayed `42.0` and
`-23.0` values were post-rounding, zero-point-adjusted intermediates rather
than source activations. That build took 11:13.74 wall time and 15,399,920 KiB
maximum RSS; simulation took 10:13.71, used 11,428 KiB maximum RSS, and
completed in 545,149 cycles.

The corrected probe at `bb0_3443` captured the actual 16 float values entering
q46's division by scale `0.00028605051920749247`. Its build took 11:14.54 wall
time and 15,400,004 KiB maximum RSS; simulation took 10:25.41, used 11,432 KiB
maximum RSS, and completed normally in 545,149 cycles. Every source activation
is already wrong. RTL alternates approximately `+0.00922/-0.00933`, while
PT2E `view_7` alternates approximately `+0.01913/-0.02088`; for example index
0 is RTL `0x3c170a4b` (`0.0092187626`) versus PT2E `0x3c9cd14e`
(`0.0191427730`). The q46 quantization division, rounding, zero-point addition,
clamping, projection accumulation, and projection scaling are therefore all
downstream of the first known defect. Localization moves through the no-op
`view_7`/`permute_7` layout chain to the attention-value computation that
produces these floats.

The exact `matmul_3` implementation is the 8-by-2-by-8 floating MAC at
`bb0_3424` through `bb0_3435`. Its diagnostic build took 11:16.83 wall time
and 15,399,920 KiB maximum RSS; simulation took 10:12.23, used 11,452 KiB
maximum RSS, completed in 545,149 cycles, and emitted exactly 128 multiplies
and 128 accumulator additions. The first product has both operands bit-exact:
probability `0x3e003f0e` and value `0x3d11fd68`. The first material divergence
is the next value operand: RTL reads `-0.0325427502` (`0xbd054b8c`) where PT2E
`cat_3` requires `-0.0353321284` (`0xbd10b86c`). Later RTL values form a
scrambled/stale-looking sequence, with only some reduction positions exact.
The probability stream is exact for the first term and differs by only one
ULP on subsequent terms (`0x3dffedfc` versus PT2E `0x3dffedfd`), which cannot
explain the roughly factor-of-two result error. Each traced add correctly uses
the prior sum and current product. Therefore the dominant first known defect
is in the `cat_3` value tensor or its construction/address mapping before
`matmul_3`, not in the MAC datapath.

An address-qualified producer trace proves the value buffer is already wrong
when written by q42 dequantization (`bb0_3220`), before `matmul_3` reads it.
The diagnostic build took 11:15.31 wall time and 15,400,020 KiB maximum RSS;
simulation took 10:10.90, used 11,452 KiB maximum RSS, and completed normally
in 545,149 cycles. It emitted 16 sequential writes at addresses 0 through 15.
Addresses 0 and 1 are bit-exact with PT2E `dequantize_per_tensor_68`, but
address 2 is RTL `0xbd054b8c` (the PT2E value expected at address 7) instead of
`0xbd10b86c`; address 3 repeats PT2E address 0 instead of containing
`0x3d1eaf45`. Later addresses are likewise mixed, with a subset exact. Thus
the bad value sequence is not created by the matmul read-side address
linearization. `bb0_3220` only converts and stores q42, so localization moves
upstream to `quantize_per_tensor_42` / its `permute_6` input.

The q42 source/code trace (`bb0_3172` and `bb0_3197`) clears the quantizer.
Its diagnostic build took 11:15.04 wall time and 15,400,072 KiB maximum RSS;
simulation took 10:10.99, used 11,436 KiB maximum RSS, and completed normally
in 545,149 cycles. All 16 q42 codes are the correct rounded/clamped results for
the float values supplied. Those source floats, however, already equal the
mixed sequence later observed in the dequantized value buffer: indices 0 and 1
match PT2E, while index 2 is `0xbd054b8c` instead of `0xbd10b86c` and index 3
repeats `0x3d11fd68` instead of `0x3d1eaf45`. The q42 quantization and
dequantization paths are therefore correct. The earliest known defect is now
the tensor entering q42, structurally corresponding to PT2E `permute_6`.

A paired write trace of `dequantize_per_tensor_67` (`bb0_3164`) and the
generated `permute_6` copy (`bb0_3168`) falsifies permutation lowering as the
cause. The diagnostic build took 11:16.23 wall time and 15,400,136 KiB maximum
RSS; simulation took 10:17.31, used 11,372 KiB maximum RSS, and completed in
545,149 cycles. Both stages wrote addresses 0 through 15 in order, and every
address/data pair matched bit-for-bit. The mixed sequence is already present
in `dequantize_per_tensor_67`; `permute_6` preserves it exactly. Localization
therefore moves upstream through q41 and the layout-only `view_6` to the value
projection producing q41.

Tracing q36 at the `linear_8` boundary (`bb0_3116` source and `bb0_3141`
write) proves the projection is already wrong and q36 correctly quantizes it.
The diagnostic build took 11:13.86 wall time and 15,399,664 KiB maximum RSS;
simulation took 10:23.26, used 11,456 KiB maximum RSS, and completed normally
in 545,149 cycles. RTL `linear_8` begins with the expected q36-equivalent
values/codes at indices 0 and 1 (`115`, `-126`), but index 2 produces code
`-105` rather than PT2E `-114`, and later values reproduce the same mixed
sequence seen downstream. All emitted codes match quantization of their traced
RTL floats. The first known defect therefore lies in `linear_8` or its inputs,
not q36, q41, q42, their dequantizations, or the intervening view/permutation.

### `linear_8` integer boundary clears the W4 multiply and local accumulator

A focused trace of generated `linear_8` blocks `bb0_2832` through `bb0_2850`
completed in 545,149 cycles. The Verilator build took 11:14.11 and
15,399,752 KiB peak RSS; simulation took 10:16.71 and 11,300 KiB peak RSS.
All 16 accumulator addresses are explicitly initialized to zero, exactly two
signed products are accumulated per output, and the result is rescaled by
`cst_5 = 0x37d6b335` (2.559423774073366e-05). This is the correctly rounded
float32 product of q33 activation scale 0.007759554777294397 and
`_frozen_param7` weight scale 0.0032984158024191856.

The frozen W4 weight codes are `[[-6, 5], [7, -5]]`. For token zero, PT2E q33
codes are `[-127, 127]`; RTL produces products 762 and 635 and the correct
accumulator 1397. For token one, PT2E requires `[126, -126]` and first-output
accumulator -1386. RTL instead produces products -738 and -535, proving that
its activation pair at this boundary is `[123, -107]`; it then correctly
accumulates the supplied pair to -1273. Its second-output products 861 and
535 independently establish the same erroneous activation pair with the
second weight row.

This clears `linear_8` indexing, signed W4 multiplication, accumulator
initialization, integer addition, and product rescaling. The preceding
statement that the first defect could be inside `linear_8` is therefore
superseded. The first demonstrated divergence is already present in the
activation tensor copied into `arg_mem_136`, whose semantic source is q33
after the second block's first layer normalization. The next trace boundary
is q33/layer-norm-2 production.

### Superseded zero-seed diagnosis

The q33 diagnostic correctly proved that q33 quantizes and copies the float
values supplied to it, but the conclusion that zero-seed aliasing caused those
bad floats was false. A fresh immutable lowering materialized 12 statically
zero-seeded copies as destination fills. Its prefill simulation reproduced the
same q33 bytes and all five prior mismatching outputs exactly. The zero-seed
normalizer remains an auditable semantic-preservation measure, but it is not
the functional repair for this failure.

The decisive trace captured the second LayerNorm mean path. Its reduction sums
were correct, but the divider result used for row broadcasts changed only on
every third invocation. The generated `std_divSqrtFN` wrapper accepted requests
directly from level-sensitive `go`, guessed completion with a fixed-delay
`done_buf`, and could reuse a stale HardFloat result across successive Calyx
invocations. This exactly explained the observed three-row stale-mean pattern.

The repository already contained a tested state-machine repair in
`scripts/pipeline/fix_sv_divsqrt_handshake.py`: one HardFloat request is issued
per Calyx invocation, completion follows `outValid`, the result is captured
once, and the wrapper waits for `go` to deassert before accepting another
request. Commit `d2eab81` enables that repair in every native-Calyx SV
derivation. A test-first Nix regression failed before the wiring change and the
focused W4A8 Nix plus wrapper suite then passed 9/9 tests.

## Canonical repaired three-phase result

Each immutable closure contains `divsqrt-handshake-receipt.json` with
`repair_count: 1`; in every case the receipt's output SHA-256 equals the actual
`sv/main.sv` SHA-256. All runs used the dedicated W4A8 driver and Verilator
5.022 at `-j4`. An attempted prefill compile at `-j16` was rejected as a safe
operating point after `cc1plus` was OOM-killed at 15,752,772 KiB process-tree
peak RSS; `-j4` completed all canonical simulations.

| phase | native-SV closure | SV SHA-256 | Nix build wall time | cycles | Verilator compile | simulation | peak RSS | result |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| prefill-8 | `/nix/store/xx13r1a2mijdymyifnpah8bwmj2rb3qy-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-calyx-native-sv` | `1657b663c6b3631c94fb2fe25d4ba0612acd57ad3664bc93fdb43884c8d28004` | 1:48:23 | 524,816 | 412.66 s | 580.66 s | 15,777,248 KiB | pass, 5/5 bit-exact |
| decode-8 | `/nix/store/vlza9rqig7yj6wasmb60yi0szan454b1-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-calyx-native-sv` | `62255f24c12c11b699c972b824fb2cb4119d94f733d57124117b9c00a5e18fa6` | 44:03.87 | 64,044 | 348.61 s | 66.47 s | 11,647,584 KiB | pass, 5/5 bit-exact |
| decode-9 | `/nix/store/xjgs6vissy8f803j48cgn1dp9pyv98vd-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-calyx-native-sv` | `1285316e5d743067a69447879fd51e3834c08e86344696bfb4854b6f879e7207` | 43:28.86 | 65,852 | 347.73 s | 69.38 s | 11,735,320 KiB | pass, 5/5 bit-exact |

For all fifteen phase/output comparisons, `actual_sha256 == expected_sha256`,
`bit_exact == true`, and maximum and mean absolute error are both `0.0`.

Canonical semantic inputs are:

- prefill-8 exported PT2E:
  `/nix/store/b6ywnhs5b1b8rx2ixp0dglj5a5dxh7gb-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-pytorch-exported`;
- prefill-8 flat-SCF:
  `/nix/store/g5r6di77i2s2wbfzslz7a041w510n5w5-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-flat-scf`;
- decode-8 exported PT2E:
  `/nix/store/lilf26wxc1n2d75lnv0yk2qhvnrp9f9l-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-pytorch-exported`;
- decode-8 flat-SCF:
  `/nix/store/gvjg2jrjypsds2hl80vawfm236apjc9s-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-flat-scf`;
- decode-9 exported PT2E:
  `/nix/store/9rp9k0vz4gqwg213640ayz5sc24vvjph-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-pytorch-exported`;
- decode-9 flat-SCF:
  `/nix/store/yzx93g7bnwhadavnzg27jwq1rhsrhag0-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-flat-scf`.

The native Calyx resource reports estimate 69,104 external plus 5,328
internal bits for prefill-8, 20,618 external plus 3,062 internal bits for
decode-8, and 21,780 external plus 3,102 internal bits for decode-9. These are
backend estimates only, not mapped FPGA utilization.

The three-phase compiler/RTL functional milestone is complete. Per the user's
scope decision, mapped Yosys, nextpnr-xilinx, formal equivalence, manual RTL
sharing/BRAM refinement, and DDR3 work are deferred to later goals.
