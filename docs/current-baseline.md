# Current Baseline

## Representative-core W4A8, TOSA no-handshake Calyx-SV

Recorded on 2026-07-08.

- Repository commit: `f02fdee3132071d31ef9a1b9d64ff09b98ab0765`
- Worktree before baseline build: clean
- Target package: `tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv`
- Baseline command:
  `nix build .#tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv --no-link --print-out-paths -L`
- Companion shorter command:
  `nix build .#tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx --no-link --print-out-paths -L`

## Pipeline

The intended active pipeline is:

1. PyTorch representative-core W4A8 exported program
2. `torch-mlir`
3. TOSA
4. TOSA-to-Linalg
5. SCF
6. Flat SCF
7. Calyx
8. Calyx-SV

This is the baseline to debug from for the resource-minimization work. It is
not yet a resource result for the board, because the current run fails before
Calyx or SystemVerilog generation.

## Outcome

- Status: failed
- Last known good stage: TOSA
- First failing stage: TOSA-to-Linalg
- Failing derivation:
  `/nix/store/s6zcbra5n806px73igjck314gfrkx6bd-tinystories-representative-core-w4a8-linalg.mlir.drv`
- Failing input artifact reported by the build:
  `/nix/store/29h9i8j4hv93chiyjd6jgz1mzny3nfgh-tinystories-representative-core-w4a8-tosa.mlir`

The TOSA-to-Linalg stage rejects many quantized `tosa.add` operations with
`i8` operands and `i8` results. The first reported failure was:

```mlir
%187 = tosa.add %186, %45 : (tensor<1x1x2xi8>, tensor<1x1x1xi8>) -> tensor<1x1x2xi8>
```

The verifier message says the operand/result data types do not align with a
supported TOSA profile or extension and suggests the supported add profile is
`i32, i32, i32`.

## Warnings Before The Failure

The PyTorch export stage reaches an exported program, but reports that
`torch.export.export_for_training` is deprecated.

The Torch MLIR stage reaches MLIR, but PyTorch warns about non-writable buffers
while loading state.

The TOSA stage succeeds, but warns:

```text
Partially traced quantized operands. This op will remain in QDQ form.
```

Those warnings appear around quantized `torch.aten.matmul` sites.

## Interpretation

This baseline is a compiler-legality blocker, not yet a hardware-resource
measurement. Clean upstream torch-mlir plus the current representative-core W4A8
adapter can emit TOSA, but the emitted TOSA is not legal for the current
TOSA-to-Linalg lowering because quantized additions remain as `i8` `tosa.add`.

No textual MLIR rewrite is allowed as the fix. Acceptable fix classes are:

- Defensible PyTorch quantization or model expression changes that preserve an
  equivalence-testing story.
- Upstream/tool-supported TOSA legalization.
- A real MLIR/CIRCT pass, if the transformation belongs in the compiler
  pipeline and can be tested as such.

## Next Debug Steps

1. Preserve this baseline as the known starting point for task 6.
2. Minimize the failing `i8` `tosa.add` pattern from the TOSA artifact.
3. Decide whether the correction belongs in PyTorch quantization, TOSA
   legalization, or a dedicated MLIR pass.
4. Add a diagnostic or failing test that catches illegal quantized `tosa.add`
   before the long Calyx-SV build.
5. After the legality blocker is fixed, rerun the same Calyx-SV package and
   record the next baseline.

## Direct-Linalg No-Handshake Follow-Up

The TOSA failure is avoided by changing frontend dialects, not by rewriting
MLIR text. The direct torch-to-Linalg no-handshake variant is exposed as:

```text
tinystories-representative-core-w4a8-via-linalg-no-handshake
```

The `linalg`, `scf`, and `flat-scf` stages build for this variant. The
`flat-scf` blocker was minimized in:

```text
reproducers/flat-scf-expand-shape-materialization/input.mlir
```

The fix is to use upstream MLIR `mlir-opt --flatten-memref` for the flat-SCF
stage instead of CIRCT `circt-opt --flatten-memref`.

Current verified flat-SCF output for the original direct-Linalg W4A8
representative-core route:

```text
/nix/store/mhyl0plx7qsq655bpvs2829ndwkjq6hh-tinystories-representative-core-w4a8-flat-scf
```

The same route now builds a Calyx-stage diagnostic directory:

```text
/nix/store/aghpvrlvjbflc0y4zwp8s3m03nkirx1v-tinystories-representative-core-w4a8-calyx
```

Its `manifest.json` has `status: failed`, because `--lower-scf-to-calyx` does
not produce `model.calyx.mlir` for this original PT2E route. The next
direct-Linalg Calyx-SV frontier is therefore no longer flat-SCF. It is the
pre-Calyx float/math path:

```text
Unhandled operation during BuildOpGroups()
math.rsqrt
```

The generated `float-frontier.json` now records this as a machine-readable
unsupported Calyx float frontier:

```json
{
  "status": "has-unsupported-calyx-float-frontier",
  "total_float_ops": 809,
  "total_unsupported_ops": 5,
  "unsupported_ops": {"math.rsqrt": 5}
}
```

The Calyx-stage `manifest.json` also carries this compact summary under
`float_frontier`, so the failing package can be triaged without parsing the full
sample report.

The constant `arith.truncf` blocker was fixed by adding a checked-in MLIR pass
plugin, `llm2fpga-fold-constant-truncf`, and running it before Calyx lowering.
The pass folds constant floating-point truncations in the compiler pipeline
instead of rewriting MLIR text.

The direct-Linalg route previously failed at `calyx` on memref view/port
legality:

```text
Unhandled operation during BuildOpGroups()
memref.reinterpret_cast
```

The same Calyx attempt also reports:

```text
input memory dimension must be empty or one
```

The current normalized input no longer contains the earlier
`memref.extract_strided_metadata` crash pattern, because no-handshake
bufferization now requests identity-layout function boundaries and the flat-SCF
stage lowers affine index expressions after flattening.

Static memref view and ranked-port failures are minimized in:

```text
reproducers/calyx-memref-view-port/
```

The current compiler-pipeline fix is a checked-in MLIR pass plugin,
`llm2fpga-lower-static-memref-views-for-calyx`, which presents static
identity-layout function memrefs as one-dimensional Calyx memories and rewrites
loads, stores, and copies through static views. `cf.assert` failures are
minimized in:

```text
reproducers/calyx-cf-assert/
```

The current compiler-pipeline fix is
`llm2fpga-drop-calyx-unsupported-asserts`, which drops asserts under the valid
input-domain contract. This is only acceptable for generated guards that are
already guaranteed by the exported model's shape/value domain.

After those fixes, the direct-Linalg route reached:

```text
Unhandled operation during BuildOpGroups()
math.roundeven
```

The first reduced reproducer is:

```text
reproducers/calyx-math-roundeven/input.mlir
```

That is now handled by the checked-in
`llm2fpga-lower-roundeven-for-calyx` MLIR pass. The pass lowers scalar `f32`
round-to-nearest-even into explicit arith operations before Calyx lowering,
under the finite `i32`-range contract used by the quantization pattern.

After `roundeven` is lowered, the direct-Linalg representative-core route
reaches the next Calyx blocker:

```text
Unhandled operation during BuildOpGroups()
math.rsqrt
```

The reduced reproducer is:

```text
reproducers/calyx-math-rsqrt/input.mlir
```

The same normalized representative-core input also contains other `math`
dialect operations, including `math.exp`, `math.fpowi`, and `math.tanh`. This
makes a one-off floating-point workaround insufficient for getting
representative-core to SV. The most promising route is to move the
representative-core quantized model toward explicit integer hardware-core
semantics, matching the existing `patterns/*/adapter_w4a8_core.py` direction,
instead of trying to make Calyx accept floating-point quantization scaffolding.

The direct CIRCT Calyx-to-HW/SV route still fails on memory primitives:

```text
'calyx.seq_mem' op couldn't convert to core primitive
```

The failure is not limited to external memories. A reduced documented
`calyx.memory` case is tracked in:

```text
reproducers/calyx-memory-sv/input.mlir
```

That reproducer also fails with:

```text
'calyx.memory' op couldn't convert to core primitive
```

That backend issue needs an official Calyx/CIRCT lowering path, the packaged
native Calyx compiler route, or an
actual CIRCT pass. Textual Calyx MLIR editing is not acceptable.

A memory-free Calyx smoke test is tracked in:

```text
reproducers/calyx-register-sv/input.mlir
```

It emits SystemVerilog with this official CIRCT sequence:

```text
--calyx-remove-groups --lower-calyx-to-hw --lower-hw-to-sv --lower-seq-to-sv --export-verilog
```

That sequence is not yet sufficient for the generated integer-core pattern:
`--calyx-remove-groups` currently asserts on the full pattern Calyx artifact,
while direct `--lower-calyx-to-hw` reports the clearer `calyx.seq_mem`
legalization failure. The most promising short route to SV is therefore to keep
debugging on the small integer-core pattern, using this reduced assertion
target:

```text
reproducers/calyx-remove-groups-invoke-memory/input.mlir
```

A smaller memory-free assertion target is:

```text
reproducers/calyx-remove-groups-invoke-ref/input.mlir
```

That shows the assertion is caused by `calyx.invoke` with reference-cell
bindings, not by memory ports specifically. After that assertion is fixed or
avoided by an official pass sequence, address Calyx memory lowering or the
external-memory ABI with an official pass sequence or a real CIRCT pass.

The repo now has a checked-in CIRCT pass plugin home for that work:

```text
tools/circt-passes/
```

The first pass, `llm2fpga-calyx-pipeline-sanity`, is intentionally a no-op. It
exists to prove that a pass plugin built against the same CIRCT/MLIR 23 stack as
`circt-opt` can be packaged by Nix and loaded by the backend tool. Semantic
fixes for the `calyx.invoke`/reference-cell assertion or Calyx memory lowering
should be added there as real CIRCT passes, not as textual Calyx MLIR edits.

## Native Calyx Backend Follow-Up

The direct CIRCT Calyx-to-HW route is not the only official compiler route. The
small integer no-handshake pattern now reaches SystemVerilog through:

```text
CIRCT Calyx MLIR -> circt-translate --export-calyx -> native Calyx Verilog
```

The native Calyx compiler is packaged as `.#calyx` from the official `calyx`
crate version `0.7.1`. The no-handshake `calyx-sv` stage runs native Calyx with
`--synthesis` and disables only the `papercut` checker. That checker rejects
CIRCT-exported memory groups before native Calyx adds default assignments, while
the same program still compiles to Verilog and to the native resource report.

Verified package:

```text
pattern-linear-w4a8-core-via-tosa-no-handshake-calyx-sv
```

Verified output path:

```text
/nix/store/gjjn09hzjsvlhv9lprhb32kd3sl4dxyl-pattern-linear-w4a8-core-calyx-sv
```

The artifact contains:

```text
model.futil
sv/main.sv
sources.f
resources.csv
resources.json
logs/native-calyx-resources.log
```

Native Calyx resource estimate for this small integer pattern:

```json
{"estimated_internal_bits": 364, "estimated_external_bits": 3744}
```

Verified Yosys `stat` output:

```text
/nix/store/ar3qid4h3d5ll89w47pbg811f81cvz2v-pattern-linear-w4a8-core-yosys.stat
```

Yosys summary:

```json
{"num_cells": 6378, "num_memories": 19, "num_memory_bits": 3748}
```

The integer embedding core also reaches Yosys `stat` through the same
no-handshake Calyx-SV backend:

```text
/nix/store/v90mhzli45lrk3bribr4ilr7ba24x4rf-pattern-embedding-w4a8-core-yosys.stat
```

Yosys summary:

```json
{"num_cells": 1623, "num_memories": 6, "num_memory_bits": 578}
```

The integer layernorm core also reaches native Calyx SV after the pre-Calyx
MLIR pass flattens static identity-layout memref globals in addition to
function-boundary and view memrefs.

Verified package:

```text
pattern-layernorm-w4a8-core-via-tosa-no-handshake-calyx-sv
```

Verified output path:

```text
/nix/store/qsdhnv9n9irsynxk8dsb12jm6fj5762m-pattern-layernorm-w4a8-core-calyx-sv
```

Native Calyx resource estimate for this integer layernorm pattern:

```json
{"estimated_internal_bits": 236, "estimated_external_bits": 1056}
```

Verified Yosys `stat` output:

```text
/nix/store/g0qgqvibixz6d0fgicb0l6a8p76aalhr-pattern-layernorm-w4a8-core-yosys.stat
```

Yosys summary:

```json
{"num_cells": 5985, "num_memories": 21, "num_memory_bits": 1058}
```

These are Calyx/Yosys resource estimates, not placed FPGA utilization results.
The native Calyx SV bundles are now synthesis-ingested by Yosys with the official
primitive SV files plus generated definitions for official inline `compile.futil`
primitives. Hardware-bound integer core models use single-shot slang ingestion;
the per-file extern mode made generated Calyx memory and primitive modules
invisible to `main.sv`.

The current reproducible aggregate baseline is exposed as:

```text
resource-baseline-yosys-stat-matrix
```

Verified output path:

```text
/nix/store/7fiwg27zzj7lsz05nc9g2z4x51mhjqrq-resource-baseline-yosys-stat-matrix
```

It contains `summary.json` and `summary.md`. The current summary table is:

| alias | frontend | backend | status | cells | memories | memory bits |
| --- | --- | --- | --- | ---: | ---: | ---: |
| pattern-linear-w4a8-core-via-tosa-no-handshake | tosa | calyx-sv | ok | 6378 | 19 | 3748 |
| pattern-embedding-w4a8-core-via-tosa-no-handshake | tosa | calyx-sv | ok | 1623 | 6 | 578 |
| pattern-layernorm-w4a8-core-via-tosa-no-handshake | tosa | calyx-sv | ok | 5985 | 21 | 1058 |
| tinystories-representative-core-w4a8-integer-via-linalg-no-handshake | linalg | calyx-sv | ok | 41652 | 85 | 4580 |
| tinystories-representative-core-w4a8-integer-via-tosa-no-handshake | tosa | calyx-sv | ok | 43269 | 86 | 4644 |

## Fixed-LayerNorm Representative-Core Follow-Up

The experimental direct-Linalg route:

```text
tinystories-representative-core-w4a8-fixed-layernorm-via-linalg-no-handshake-calyx-sv
```

now gets past the earlier Calyx `math.rsqrt`, `math.exp`, `math.fpowi`, and
`math.tanh` blockers by making those model-core assumptions explicit:

- fixed-point LayerNorm bridge for the representative hidden size
- singleton-token attention identity instead of softmax and attention matmuls
- quadratic arithmetic-only GELU approximation

The singleton-token attention phase now returns the value tensor directly under
the one-query/one-key/no-mask contract. Rebuilding
`tinystories-representative-core-w4a8-fixed-layernorm-via-linalg-no-handshake-linalg`
after that change no longer reports the earlier torch-mlir warnings for
attention `torch.aten.matmul` sites remaining in QDQ form. The Linalg artifact
still contains float QDQ arithmetic such as `arith.sitofp`, `arith.fptosi`,
`arith.mulf`, `arith.divf`, `arith.addf`, `arith.cmpf`, and `math.roundeven`.

Dropout modules are now replaced with `torch.nn.Identity()` before export
because the representative core is exported in eval mode. This removed dropout
from the exported graph and reduced the Linalg op-stat surface from 424 to 404
`linalg.generic` operations and from 60 to 55 `math.roundeven` operations. It
does not remove the remaining SoftFloat dependency, because the dominant QDQ
islands are still around linear/requantization/residual paths.

The Calyx stage now writes `float-frontier.json` next to `model.calyx.mlir`.
For the current fixed-LayerNorm route, the Calyx stage succeeds:

```text
/nix/store/1pxnywss7xqr82w6q9ygc8az4w1b52yc-tinystories-representative-core-w4a8-fixed-layernorm-calyx
```

Its `manifest.json` is:

```json
{"stage":"calyx","status":"ok","artifact":"model.calyx.mlir"}
```

The post-cleanup, post-pre-Calyx-pass float frontier is:

```json
{
  "status": "has-float-frontier",
  "total_float_ops": 883,
  "total_unsupported_ops": 0,
  "unsupported_ops": {},
  "arith.addf": 63,
  "arith.cmpf": 330,
  "arith.divf": 50,
  "arith.fptosi": 110,
  "arith.mulf": 83,
  "arith.sitofp": 192,
  "arith.subf": 55
}
```

This is the machine-readable target for the next real lowering step. It should
shrink as model/core integerization or MLIR lowering passes remove QDQ islands.

The pre-Calyx MLIR pass also now materializes f32 `dense_resource` memref
globals into ordinary dense globals before Calyx lowering. That fixed an unnamed
CIRCT `--lower-scf-to-calyx` segfault in `DenseElementsAttr::getNumElements`.
The regression input is tracked in:

```text
reproducers/calyx-unnamed-crash/
```

After those fixes, CIRCT emits Calyx and `circt-translate --export-calyx`
emits Futil. The `calyx-sv` stage now checks the exported imports before
running native Calyx and reports that CIRCT emitted SoftFloat-style primitive
imports that are not present in the packaged native Calyx 0.7.1 library, for
example:

```text
primitives/float.futil
primitives/float/addFN.futil
primitives/float/divSqrtFN.futil
```

Current failed Calyx-SV diagnostic output:

```text
/nix/store/xyxzd4sa0ljdqk1dmnfjz1gvk8hn23hv-tinystories-representative-core-w4a8-fixed-layernorm-calyx-sv
```

Native Calyx also rejects CIRCT's exported float constants:

```text
cst_38 = std_float_const(0, 32, 0.000000);
```

The minimal native-Calyx reproducer is:

```text
reproducers/calyx-native-float-const/
```

This is the current frontier for this route. It is after Calyx MLIR generation
but before native Calyx SV generation, so representative-core resource
measurement is still blocked. Do not fix it with textual Futil rewriting.
Replacing only float constants is insufficient because the generated Futil still
depends on missing float primitive files. Acceptable next fixes are to remove the
remaining float path from the model/core semantics, version-align native Calyx
with CIRCT's exporter, or fix the exporter/backend through an actual
compiler/backend change.

## Explicit-Integer Representative-Core Slice

The first representative-core-shaped route that reaches Calyx-SV is now a
separate explicit-integer hardware slice:

```text
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-calyx-sv
tinystories-representative-core-w4a8-integer-via-tosa-no-handshake-calyx-sv
```

This variant is not the PT2E QDQ graph. It is an intentionally explicit integer
core with token/position lookup, fixed-point normalization, integer linear
requantization, integer activation, and residual clamp. It exists to make the
compiler pipeline reach SV without textual rewrites or floating-point Futil
patches, and to provide a concrete target for later equivalence testing against
the quantized TinyStories subgraph.

Verified direct-Linalg output:

```text
/nix/store/kzfamfbxkp61ri2ng8gba630ch21iin0-tinystories-representative-core-w4a8-integer-calyx-sv
```

Native Calyx resource estimate:

```json
{"estimated_internal_bits": 652, "estimated_external_bits": 4576}
```

The same direct-Linalg route now reaches RTLIL and Yosys `stat` through the
no-handshake alias:

```text
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-il
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat
```

Verified RTLIL output:

```text
/nix/store/y633w90aa1qrqf39n0gvs6zh51szvqkj-tinystories-representative-core-w4a8-integer.il
```

Verified Yosys `stat` output:

```text
/nix/store/093g854ypln2zfwnr6x7lpjv8i648bdj-tinystories-representative-core-w4a8-integer-yosys.stat
```

Yosys summary:

```json
{"num_cells": 41652, "num_memories": 85, "num_memory_bits": 4580}
```

Verified TOSA output:

```text
/nix/store/v383f760ylzg6xpg5zld6gz7cfvr379z-tinystories-representative-core-w4a8-integer-calyx-sv
```

Native Calyx resource estimate:

```json
{"estimated_internal_bits": 696, "estimated_external_bits": 4640}
```

Verified TOSA Yosys `stat` output:

```text
/nix/store/hnbv22sc5za4p7ynwb6b11gambf8jk0p-tinystories-representative-core-w4a8-integer-yosys.stat
```

Yosys summary:

```json
{"num_cells": 43269, "num_memories": 86, "num_memory_bits": 4644}
```

Both frontend routes produce a clean Calyx-stage float frontier:

```json
{"float_type_lines": 0, "op_counts": {}, "status": "ok", "total_float_ops": 0}
```

The native Calyx SV bundle now includes generated `compile.sv` definitions for
the official inline `compile.futil` primitives used by the emitted design:
`undef`, `std_wire`, `std_add`, and `std_reg`. The no-handshake Calyx-SV stage
also asks native Calyx for nested assignments, and the Yosys/slang scripts raise
`--max-parse-depth` to handle generated Calyx expressions. These are packaging
and frontend-ingestion fixes, not textual rewrites of model IR or Futil.

This validates the route choice: moving the representative core toward explicit
integer hardware semantics removes the SoftFloat import blocker and allows the
existing no-handshake Calyx-SV backend to emit `sv/main.sv`. The remaining work
is to tighten the equivalence story against the quantized model and then expand
this slice toward the full representative-core computation.
