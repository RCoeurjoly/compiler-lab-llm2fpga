# Current Baseline

## Full TinyStories PT2E W8A8, Task 3 pinned Calyx utilization frontier

Recorded on 2026-07-14.

- Target package: `tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization`
- Target device: XC7K480T
- Status: `frontier` at `native-sv-generation`
- Result: no mapped resource estimate
- Compact evidence: `completed_stages: []`; `resources: null`; FPGA fit remains unresolved.

The current source provenance is upstream Calyx pinned at
`5a4303847392609cad83dda6f4bdffc8cc0e5c89`; `0.7.1` is only its package-version
label. The package-level float closure succeeds, and the full route produced
Futil; native Calyx was killed during SV emission. No full-model SV, RTLIL, Yosys, mapping, FPGA utilization, nextpnr, board, equivalence, or SmoothQuant result exists. This is a compiler-execution frontier, not an out-of-context resource
estimate. See the [bounded Task 3 result report](results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md).

## Full TinyStories PT2E W8A8, TOSA Handshake scout

Recorded on 2026-07-13.

- Target: `tinystories-w8a8-via-tosa-yosys-stat`
- Route: `TOSA -> Linalg -> CF -> Handshake -> HW -> SV`
- Calyx: not used
- Last successful stage: Handshake external-memory preparation (`hs-ext`)
- First failing stage: `lower-handshake-to-hw` (`hw0`), killed with exit 137
- Largest observed compiler RSS: at least 27,373,360 KiB
- SV generated: no
- Yosys statistics generated: no

TOSA successfully rejoins the Task 3 Handshake backend, but CF-to-Handshake
expands the model from 33,326,877 bytes to 1,766,701,841 bytes and more than
30 million lines. Handshake-to-HW then exhausts host memory. This is a
Handshake scalability frontier, not a TOSA legality or Calyx frontier. See the
[full scout report](results/2026-07-13-full-tinystories-pt2e-w8a8-tosa-handshake-scout.md).

## Full TinyStories PT2E W8A8, TOSA no-handshake scout

Recorded on 2026-07-13.

The PT2E zero-point legalization now accepts quantized values with arbitrary
consumers: it no longer requires `hasOneUse()` or an immediate `i8 -> i32`
cast user. Producer provenance remains narrow: an `i8` result formed by adding
a float-derived cast and a splat zero-point constant. The validated TOSA
rewrites all 236 matching `i8 tosa.add` operations to saturating
`tosa.rescale`; zero illegal `i8 tosa.add` operations remain.

The full pipeline now succeeds through TOSA validation, Linalg, SCF, and
flat-SCF. Calyx lowering is the current frontier:

```text
Unhandled operation during BuildOpGroups()
math.floor
```

The flat-SCF input contains 5,922 float operations, including 478
`math.floor`, 478 `arith.fptosi`, and 17 `math.rsqrt`. No Calyx, SV, or Yosys
statistics were produced. This is therefore a compiler-frontier result, not a
hardware-resource result. See
[`docs/results/2026-07-13-full-tinystories-pt2e-w8a8-scout.md`](results/2026-07-13-full-tinystories-pt2e-w8a8-scout.md)
and
[`artifacts/full-tinystories-pt2e-w8a8-scout/result.json`](../artifacts/full-tinystories-pt2e-w8a8-scout/result.json).

## Representative-core W4A8, TOSA no-handshake Calyx-SV

Recorded on 2026-07-08.

**Scope: historical / pre-current-source-pin; pending-rerun.** This retained
baseline predates the repaired source-list path and is not current reproducible
output.

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

This is an archival baseline for the resource-minimization work. It is not a
resource result for the board and remains pending-rerun under the current source
pin.

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

## Direct-Linalg No-Handshake Follow-Up — Historical / pre-current-source-pin

**Scope: historical / pre-current-source-pin; pending-rerun.** This entire
section retains pre-current-source-pin direct-Linalg execution evidence. The
source-code descriptions identify architectural facts; recorded output paths,
diagnostics, and float-frontier counts are historical observations pending rerun
and do not establish current execution results.

In the historical route, the TOSA failure was avoided by changing frontend
dialects, not by rewriting MLIR text. The checked-in direct torch-to-Linalg
no-handshake route definition exposes:

```text
tinystories-representative-core-w4a8-via-linalg-no-handshake
```

In the historical run, the `linalg`, `scf`, and `flat-scf` stages built for this
variant. The `flat-scf` blocker was minimized in:

```text
reproducers/flat-scf-expand-shape-materialization/input.mlir
```

The checked-in route definition uses upstream MLIR `mlir-opt --flatten-memref`
for the flat-SCF stage instead of CIRCT `circt-opt --flatten-memref`; that is an
architectural source-code fact, not current execution evidence.

Historical verified flat-SCF output for the original direct-Linalg W4A8
representative-core route:

```text
/nix/store/mhyl0plx7qsq655bpvs2829ndwkjq6hh-tinystories-representative-core-w4a8-flat-scf
```

The same historical route produced a Calyx-stage diagnostic directory:

```text
/nix/store/aghpvrlvjbflc0y4zwp8s3m03nkirx1v-tinystories-representative-core-w4a8-calyx
```

Its recorded `manifest.json` had `status: failed`, because
`--lower-scf-to-calyx` did not produce `model.calyx.mlir` for this original PT2E
route. The recorded next direct-Linalg Calyx-SV frontier was therefore no longer flat-SCF; it was the pre-Calyx float/math path:

```text
Unhandled operation during BuildOpGroups()
math.rsqrt
```

The historical generated `float-frontier.json` recorded this as a
machine-readable unsupported Calyx float frontier:

```json
{
  "status": "has-unsupported-calyx-float-frontier",
  "total_float_ops": 809,
  "total_unsupported_ops": 5,
  "unsupported_ops": {"math.rsqrt": 5}
}
```

The historical Calyx-stage `manifest.json` also carried this compact summary
under `float_frontier`, so the failing package could be triaged without parsing
the full sample report.

The historical `arith.truncf` blocker was addressed with the checked-in MLIR
pass plugin `llm2fpga-fold-constant-truncf` before Calyx lowering. The plugin
encodes that source-code approach by folding constant floating-point truncations
in the compiler pipeline instead of rewriting MLIR text.

The historical direct-Linalg route failed at `calyx` on memref view/port
legality:

```text
Unhandled operation during BuildOpGroups()
memref.reinterpret_cast
```

The same historical Calyx attempt also reported:

```text
input memory dimension must be empty or one
```

The historical normalized input no longer contained the earlier
`memref.extract_strided_metadata` crash pattern, because no-handshake
bufferization requested identity-layout function boundaries and the flat-SCF
stage lowered affine index expressions after flattening.

Historical static memref view and ranked-port failures were minimized in:

```text
reproducers/calyx-memref-view-port/
```

The checked-in MLIR pass plugin
`llm2fpga-lower-static-memref-views-for-calyx` captured the historical route's
compiler-pipeline fix: it presented static
identity-layout function memrefs as one-dimensional Calyx memories and rewrote
loads, stores, and copies through static views. Historical `cf.assert` failures
were minimized in:

```text
reproducers/calyx-cf-assert/
```

The checked-in `llm2fpga-drop-calyx-unsupported-asserts` captured the
historical route's compiler-pipeline fix by dropping asserts under the valid
input-domain contract. This is only acceptable for generated guards that are
already guaranteed by the exported model's shape/value domain.

After those historical fixes, the direct-Linalg route reached:

```text
Unhandled operation during BuildOpGroups()
math.roundeven
```

The first reduced reproducer was:

```text
reproducers/calyx-math-roundeven/input.mlir
```

The checked-in `llm2fpga-lower-roundeven-for-calyx` MLIR pass handled that
historical blocker by lowering scalar `f32` round-to-nearest-even into explicit
arith operations before Calyx lowering, under the finite `i32`-range contract
used by the quantization pattern.

After `roundeven` was lowered, the historical direct-Linalg representative-core
route reached the next Calyx blocker:

```text
Unhandled operation during BuildOpGroups()
math.rsqrt
```

The reduced reproducer is:

```text
reproducers/calyx-math-rsqrt/input.mlir
```

The same historical normalized representative-core input contained other `math`
dialect operations, including `math.exp`, `math.fpowi`, and `math.tanh`. This
made a one-off floating-point workaround insufficient for getting
representative-core to SV. The historical conclusion was to move the
representative-core quantized model toward explicit integer hardware-core
semantics, matching the `patterns/*/adapter_w4a8_core.py` direction, instead of
trying to make Calyx accept floating-point quantization scaffolding.

The checked-in source exposes the direct CIRCT Calyx-to-HW/SV route as the
explicit `calyx-hw-sv` stage. This is an architectural route definition:

```text
CIRCT Calyx MLIR -> --calyx-remove-groups -> --lower-calyx-to-hw
-> --lower-seq-to-sv -> --lower-hw-to-sv -> --export-verilog
```

The recorded direct-CIRCT route failure was on memory primitives:

```text
'calyx.seq_mem' op couldn't convert to core primitive
```

The historical failure was not limited to external memories. A reduced
documented `calyx.memory` case was tracked in:

```text
reproducers/calyx-memory-sv/input.mlir
```

That reproducer also failed with:

```text
'calyx.memory' op couldn't convert to core primitive
```

That backend issue needs an official Calyx/CIRCT lowering path or an actual
CIRCT pass. Textual Calyx MLIR editing is not acceptable.

A memory-free Calyx smoke test remains tracked in:

```text
reproducers/calyx-register-sv/input.mlir
```

Its documented historical run emitted SystemVerilog with this official CIRCT
sequence:

```text
--calyx-remove-groups --lower-calyx-to-hw --lower-hw-to-sv --lower-seq-to-sv --export-verilog
```

For the historical generated integer-core pattern, that sequence was
insufficient: `--calyx-remove-groups` asserted on the full pattern Calyx
artifact, while direct `--lower-calyx-to-hw` reported the clearer
`calyx.seq_mem` legalization failure. The documented short route to SV was to
debug the small integer-core pattern using this reduced assertion target:

```text
reproducers/calyx-remove-groups-invoke-memory/input.mlir
```

A smaller memory-free assertion target is:

```text
reproducers/calyx-remove-groups-invoke-ref/input.mlir
```

That historical reproducer showed the assertion was caused by `calyx.invoke`
with reference-cell bindings, not by memory ports specifically. After that
assertion is fixed or avoided by an official pass sequence, address Calyx memory
lowering or the external-memory ABI with an official pass sequence or a real
CIRCT pass.

The repository contains a checked-in CIRCT pass plugin home for that work:

```text
tools/circt-passes/
```

The first pass, `llm2fpga-calyx-pipeline-sanity`, is intentionally a no-op. It
is a source-code fact that it proves a pass plugin built against the same
CIRCT/MLIR 23 stack as `circt-opt` can be packaged by Nix and loaded by the
backend tool; it is not current execution evidence for this historical route.
Semantic fixes for the `calyx.invoke`/reference-cell assertion or Calyx memory
lowering should be added there as real CIRCT passes, not as textual Calyx MLIR
edits.

## Calyx Backend Naming Split — Historical / pre-current-source-pin

**Scope: historical / pre-current-source-pin; pending-rerun.** The native-SV
resource observations in this section are preserved archival evidence. Their
counts have not been rerun on the repaired source-list path and must not be
treated as current reproducible output.

The native route used for these observations was named `calyx-native-sv` rather
than being treated as the only Calyx SV route. It lowers through:

```text
CIRCT Calyx MLIR -> circt-translate --export-calyx -> native Calyx Verilog
```

The historical native Calyx package label was `0.7.1`; it is not source
provenance. The current source provenance is the pinned upstream revision in the
full W8A8 frontier above. The historical no-handshake `calyx-native-sv` stage
ran native Calyx with `--synthesis` and disabled only the `papercut` checker.
That checker rejected CIRCT-exported memory groups before native Calyx added
default assignments, while the same program compiled to Verilog and to the
native resource report.

The legacy `calyx-sv` package name was kept as a compatibility alias for
`calyx-native-sv`. These route observations are pending-rerun; do not use them
to characterize the current full-model frontier.

Verified package:

```text
pattern-linear-w4a8-core-via-tosa-no-handshake-calyx-native-sv
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
In these archival bundles, Yosys synthesis ingested native Calyx SV with the
official primitive SV files plus generated `compile.sv` definitions for official
inline `compile.futil` primitives. Hardware-bound integer core models used
single-shot slang ingestion; the per-file extern mode made generated Calyx
memory and primitive modules invisible to `main.sv`.

The archival aggregate baseline was exposed as:

```text
resource-baseline-yosys-stat-matrix
```

Verified output path:

```text
/nix/store/7fiwg27zzj7lsz05nc9g2z4x51mhjqrq-resource-baseline-yosys-stat-matrix
```

It contains `summary.json` and `summary.md`. The retained historical summary
table is:

| alias | frontend | backend | status | cells | memories | memory bits |
| --- | --- | --- | --- | ---: | ---: | ---: |
| pattern-linear-w4a8-core-via-tosa-no-handshake | tosa | calyx-native-sv | ok | 6378 | 19 | 3748 |
| pattern-embedding-w4a8-core-via-tosa-no-handshake | tosa | calyx-native-sv | ok | 1623 | 6 | 578 |
| pattern-layernorm-w4a8-core-via-tosa-no-handshake | tosa | calyx-native-sv | ok | 5985 | 21 | 1058 |
| tinystories-representative-core-w4a8-integer-via-linalg-no-handshake | linalg | calyx-native-sv | ok | 41652 | 85 | 4580 |
| tinystories-representative-core-w4a8-integer-via-tosa-no-handshake | tosa | calyx-native-sv | ok | 43269 | 86 | 4644 |

## Fixed-LayerNorm Representative-Core Follow-Up

**Scope: historical / pre-current-source-pin; pending-rerun.** The
missing-float-import diagnosis and all observations in this section predate the
repaired source-list path; they are retained for context, not as the current
full-model cause.

The historical experimental direct-Linalg route:

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

The Calyx stage wrote `float-frontier.json` next to `model.calyx.mlir`. For the
historical fixed-LayerNorm route, the Calyx stage succeeded:

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

Historical failed Calyx-SV diagnostic output:

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

This was the historical frontier for this route, after Calyx MLIR generation
but before native Calyx SV generation. It remains pending-rerun. The current
pinned full W8A8 route has package-level float closure and produced Futil before
native Calyx was killed during SV emission; the historical missing-import claim
is not its current cause. Do not fix either route with textual Futil rewriting.

## Explicit-Integer Representative-Core Slice

**Scope: historical / pre-current-source-pin; pending-rerun.** Preserve the
following explicit-integer results and counts as archival observations. The direct-Linalg Yosys-stat route was rerun only as a source-closure regression check and observed 41,451 cells. That source-closure smoke has not been accepted or promoted as a durable current resource baseline; it does not replace or alter the archival 41,652-cell table value below.

The first representative-core-shaped route recorded as reaching Calyx-SV was a
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

Historical verified direct-Linalg output:

```text
/nix/store/kzfamfbxkp61ri2ng8gba630ch21iin0-tinystories-representative-core-w4a8-integer-calyx-sv
```

Native Calyx resource estimate:

```json
{"estimated_internal_bits": 652, "estimated_external_bits": 4576}
```

The historical direct-Linalg route reached RTLIL and Yosys `stat` through the
no-handshake alias:

```text
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-il
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat
```

Historical verified RTLIL output:

```text
/nix/store/y633w90aa1qrqf39n0gvs6zh51szvqkj-tinystories-representative-core-w4a8-integer.il
```

Historical verified Yosys `stat` output:

```text
/nix/store/093g854ypln2zfwnr6x7lpjv8i648bdj-tinystories-representative-core-w4a8-integer-yosys.stat
```

Yosys summary:

```json
{"num_cells": 41652, "num_memories": 85, "num_memory_bits": 4580}
```

Historical verified TOSA output:

```text
/nix/store/v383f760ylzg6xpg5zld6gz7cfvr379z-tinystories-representative-core-w4a8-integer-calyx-sv
```

Native Calyx resource estimate:

```json
{"estimated_internal_bits": 696, "estimated_external_bits": 4640}
```

Historical verified TOSA Yosys `stat` output:

```text
/nix/store/hnbv22sc5za4p7ynwb6b11gambf8jk0p-tinystories-representative-core-w4a8-integer-yosys.stat
```

Yosys summary:

```json
{"num_cells": 43269, "num_memories": 86, "num_memory_bits": 4644}
```

Both historical frontend routes produced a clean Calyx-stage float frontier:

```json
{"float_type_lines": 0, "op_counts": {}, "status": "ok", "total_float_ops": 0}
```

The archival native Calyx SV bundle included generated `compile.sv` definitions
for the official inline `compile.futil` primitives used by the emitted design:
`undef`, `std_wire`, `std_add`, and `std_reg`. The historical no-handshake
Calyx-SV stage asked native Calyx for nested assignments, and the Yosys/slang
scripts raised `--max-parse-depth` to handle generated Calyx expressions. These
were archival packaging and frontend-ingestion fixes, not textual rewrites of
model IR or Futil.

These historical observations supported the route choice: moving the
representative core toward explicit integer hardware semantics removed the
SoftFloat import blocker and allowed the then-existing no-handshake Calyx-SV
backend to emit `sv/main.sv`. They do not promote the archived counts or the
source-closure smoke to a current resource baseline.

## Explicit-Integer SV Equivalence Baseline

**Scope: historical / pre-current-source-pin; pending-rerun.** This equivalence
snapshot is retained as archival evidence and is not a current result under the
repaired source-list path.

The frozen direct-Linalg integer route had a first machine-readable equivalence
baseline package:

```text
tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-sv-equivalence
```

Verified output path:

```text
/nix/store/6gwxgv0y6v6c13wjkhb0l1l527igsqpm-tinystories-representative-core-w4a8-integer-sv-equivalence
```

It contains:

```text
reference.json
report.json
```

The historical report's PyTorch integer reference for its fixed input was:

```json
{
  "input_token_ids": [[3]],
  "pytorch_output_i8": [[[-2, 76]]],
  "pytorch_output_shape": [1, 1, 2]
}
```

The historical report recorded this status:

```json
{
  "status": "blocked-unobservable-sv-output",
  "sv": {
    "ports": {
      "inputs": ["clk", "reset", "go"],
      "outputs": ["done"]
    },
    "observable_functional_outputs": []
  }
}
```

This historical snapshot was not a passing equivalence result. In that report,
Calyx-SV emitted, but native Calyx generated a top-level module with only
control ports, so the harness could not compare PyTorch output against SV output
without either an observable result port, a stable generated memory ABI, or an
explicit test wrapper. Treat any future equivalence pass as invalid unless it
compares functional output data, not just `done`.
