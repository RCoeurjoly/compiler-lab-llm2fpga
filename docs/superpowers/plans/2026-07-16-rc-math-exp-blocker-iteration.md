# RC `math.exp` Blocker Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a reusable, evidence-backed first blocker iteration for the frozen quantized TinyStories representative core: demonstrate exactly which ordinary RC float forms can bind through the pinned Calyx/HardFloat stack, screen the complete local FPGA-LLM corpus for the actual `math.exp` Softmax blocker, and publish a truthful blocker packet without changing model semantics.

**Architecture:** The complete frozen RC remains the only system-level driver. A small set of scalar MLIR MRCs mirrors ordinary forms mechanically observed in its flat-SCF artifact; they provide fast capability and binding evidence, while the full RC rerun remains the advancement gate. A separate native-Futil fixture proves that the pinned Calyx package can elaborate every relevant HardFloat wrapper. The paper screen runs as a Nix-packaged command against the external read-only cache and emits metadata, hash, term/page, and candidate information only—never PDF or extracted-text content.

**Tech Stack:** Python 3.11 standard library, MLIR/CIRCT, Calyx 0.7.1, Berkeley HardFloat-1, Calyx/Morty native Verilog backend, `yosys-slang`, Nix flakes, Poppler `pdftotext`, Python `unittest`.

## Global Constraints

- The DUT is exactly `tinystories-w8a8-rc-study-mask9-vocab6-width2`: static XNNPACK PT2E W8A8, vocabulary 6, two layers, context length 8, hidden width 2, one attention head, seed 0. Do not create or substitute a look-alike model.
- The frozen PT2E W8A8 reference image remains the numerical authority. Its four cases are a fast smoke oracle. A local transform can become canonical only after valid SV and exhaustive RC observable functional equivalence over all `6^8 = 1,679,616` length-eight V=6 contexts, comparing six final raw int8 codes and the lowest-index argmax token ID after deterministic reset; this iteration does not make that claim.
- PT2E is the sole acceptance oracle. Any exhaustive expected-output table or shard must be generated directly from the frozen PT2E evaluator and record evaluator, graph, image, enumeration, and shard hashes; a hand-written integer or hardware-style reference can diagnose but cannot accept a route.
- If a later local `math.exp` implementation uses an approximation, passing that exhaustive gate may admit it only as an RC-observationally equivalent implementation. It must publish its source, numerical contract, range assumptions, and result; it does not establish operation-level or Full TinyStories equivalence.
- The exhaustive image-backed SV gate is repeated after every semantics-affecting RC change, including base lowering, local math implementation, and memory externalization. DDR3/board validation is a separate physical-service gate and never substitutes for this numerical gate.
- A canonical candidate must expose the eight token inputs and all six raw codes plus token ID through a documented testbench-accessible SV interface, with deterministic reset, launch, completion, and sampling semantics. Done-only or internally probed SV is resource-scout evidence only.
- Use the frozen four-case PT2E oracle for each rapid experiment. Require the full `6^8` sweep before calling any route canonical, adopting it as the next baseline, or claiming RC observable functional equivalence; label it provisional until then.
- Implement any future full sweep as deterministic durable base-six lexical context-range shards with result digests and a final manifest proving disjoint complete `[0, 6^8)` coverage. Temporary files are not proof artifacts.
- Treat one raw-code or token-ID mismatch, invalid completion sequence, or timeout as candidate rejection. Emit a durable counterexample packet with context/index, PT2E/SV outputs, provenance hashes, declared timing contract, and replayable cycle/handshake trace before changing the route.
- Every future testable candidate declares a versioned conservative worst-case SV cycle bound from launch to sampling. Record observed latency/max in smoke and full-sweep artifacts; timeout beyond the bound rejects it, while PyTorch is never treated as a cycle-timing oracle.
- For every new blocker, investigate in order: existing upstream semantics-preserving dialect/pass/library route; established published/open implementation; local implementation only as last resort. Every tier still needs the same RC smoke, interface, timing, and exhaustive-promotion gates.
- Work one independent blocker family at a time: record the full-RC blocker, make its MRC/evidence, integrate only its selected route and documented dependencies, then rerun full RC before touching another family such as `math.tanh` or `math.fpowi`.
- A future canonical RC route also passes a durable deterministic vertical-slice prompt fixture: tiny V=6 host tokenizer, eight-token SV invocation with the frozen image, six raw codes/token ID, and host detokenization. It demonstrates one generated token at reproducible latency but never substitutes for the exhaustive token-level gate.
- Defer DDR3 externalization. First lower, verify, and test the complete baseline-memory V=6 RC on FPGA; only then introduce external memory, whose image-backed SV fixture must consume the exact versioned packed byte image and address map intended for the DDR3 driver.
- The baseline board checkpoint needs a reproducible XC7K480T bitstream and board-captured six raw codes/token ID from the vertical-slice fixture, compared against frozen PT2E with latency and bitstream/P&R/constraint/host/fixture/tool provenance. Build, configuration, or `done` alone is not evidence.
- A census of floating operations is informational source provenance, never a pass/fail lowering gate. A source form is acceptable when it has a named, reproducible hardware path.
- Do not modify the PT2E graph, calibration, quantization parameters, model source, memory layout, host software, DDR3 driver, or board design in this iteration.
- Do not add `lower-scout-math-for-calyx`, textual substitution of `math.exp`, `tosa.table`, polynomial, LUT, clamp, range-reduction, or other approximation to the canonical RC pipeline.
- Preserve the pinned Calyx revision `5a4303847392609cad83dda6f4bdffc8cc0e5c89` and HardFloat hash `sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs=`. This work investigates their current capability; it does not update dependencies.
- `/home/roland/LLM-inference-on-FPGA-papers/papers/` is an external, ignored research cache. Read PDFs locally only. Do not copy, Nix-import, embed, commit, or redistribute PDFs or their extracted text.
- Use Nix packages/apps for durable tool environments. Nix derivations and checked-in result documents are durable artifacts; temporary process files must be under a derivation output directory and removed by that derivation.
- Treat an MLIR `error:` diagnostic as a rejected lowering even when a tool exits zero and leaves a non-empty partial file.
- Do not make SystemVerilog, Yosys resource, DDR3, host, timing, board, bitstream, or functional-equivalence claims from a primitive MRC or Futil library closure.

## File Structure

| Path | Responsibility |
| --- | --- |
| `reproducers/calyx-rc-basic-float-mrcs/*.mlir` | Checked-in scalar MRCs that preserve ordinary f32 and conversion signatures observed in the frozen RC. |
| `reproducers/calyx-rc-basic-float-mrcs/README.md` | States the provenance boundary and the distinction between capability evidence and an RC equivalence result. |
| `reproducers/calyx-rc-basic-float-bindings/input.futil` | Native Calyx fixture instantiating all relevant f32 HardFloat wrapper primitives. |
| `reproducers/calyx-rc-basic-float-bindings/README.md` | Describes the fixture’s library-closure scope and explicit limits. |
| `scripts/pipeline/run_rc_calyx_hardfloat_bindings.py` | Builds the source inventory, runs MRCs through CIRCT/Calyx/SV, and emits a durable machine-readable binding report. |
| `tests/test_rc_calyx_hardfloat_bindings.py` | Unit tests for source-form observation, diagnostic rejection, Futil/SV binding classification, and non-gating policy. |
| `scripts/pipeline/screen_fpga_llm_math_exp_corpus.py` | Hash-validates the external corpus, searches each locally cached PDF page-by-page, and writes only metadata/count/page evidence. |
| `tests/test_fpga_llm_math_exp_corpus.py` | Tests corpus schema validation, cache integrity checks, page-level matching, stable output, and non-retention of source text. |
| `flake.nix` | Exposes the native HardFloat closure self-test, RC binding evidence derivation, and paper-screen app without importing PDFs into Nix. |
| `tests/test_calyx_float_nix_package.py` | Extends existing package assertions to cover every basic wrapper and the new evidence package. |
| `docs/results/2026-07-16-rc-calyx-hardfloat-binding.md` | Human-readable result from the Nix binding derivation. |
| `docs/results/2026-07-16-rc-math-exp-fpga-corpus.md` | Curated, page-cited result from the complete local paper screen and deep reading. |
| `docs/results/2026-07-16-rc-math-exp-blocker-packet.md` | Complete first-blocker packet joining full-RC, MRC, tool/library, literature, and next-frontier evidence. |

---

### Task 1: Define RC-derived basic-float MRCs and the non-gating inventory contract

**Files:**
- Create: `reproducers/calyx-rc-basic-float-mrcs/addf-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/subf-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/mulf-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/divf-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/cmpf-ugt-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/sitofp-i32-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/uitofp-i1-f32.mlir`
- Create: `reproducers/calyx-rc-basic-float-mrcs/README.md`
- Create: `tests/test_rc_calyx_hardfloat_bindings.py`
- Create: `scripts/pipeline/run_rc_calyx_hardfloat_bindings.py`

**Interfaces:**
- Consumes: `flat.scf.mlir` from `tinystories-w8a8-rc-study-mask9-vocab6-width2-flat-scf`, scalar MRC files, and later CIRCT/Calyx tool paths.
- Produces: `observe_rc_forms(flat_scf: Path) -> dict[str, object]`, `run_command(...) -> dict[str, object]`, and a report with source SHA-256, operation counts, representative source lines, MRC signatures, and non-gating policy text.
- Contract: the script must require that the frozen RC still contains the eight declared observed forms; it must record unknown float forms but never reject an RC solely because such a form exists or because any float count is nonzero.

- [ ] **Step 1: Write the failing inventory and diagnostic-classification tests**

Create `tests/test_rc_calyx_hardfloat_bindings.py`. Import the script by file path so the pure functions are testable without Nix. Use this fixture, which deliberately includes an unknown operation:

```python
SAMPLE_FLAT_SCF = """
module {
  func.func @main(%i32: i32, %i1: i1, %a: f32, %b: f32) {
    %0 = arith.addf %a, %b : f32
    %1 = arith.subf %a, %b : f32
    %2 = arith.mulf %a, %b : f32
    %3 = arith.divf %a, %b : f32
    %4 = arith.cmpf ugt, %a, %b : f32
    %5 = arith.sitofp %i32 : i32 to f32
    %6 = arith.fptosi %a : f32 to i8
    %7 = arith.uitofp %i1 : i1 to f32
    %8 = math.exp %a : f32
    %9 = math.sin %a : f32
    return
  }
}
"""
```

Implement these assertions:

```python
report = module.observe_rc_forms(path)
self.assertEqual(report["policy"], module.NON_GATING_POLICY)
self.assertEqual(report["forms"]["arith.addf.f32"]["count"], 1)
self.assertEqual(report["forms"]["arith.fptosi.f32-to-i8"]["count"], 1)
self.assertEqual(report["forms"]["arith.uitofp.i1-to-f32"]["count"], 1)
self.assertIn("math.exp", report["unclassified_float_operations"])
self.assertIn("math.sin", report["unclassified_float_operations"])
self.assertEqual(module.MRC_SPECS["addf-f32"]["form_id"], "arith.addf.f32")
self.assertEqual(module.MRC_SPECS["fptosi-f32-i8"]["expected_wrapper"], "std_fpToInt")
module.require_observed_forms(report)
```

Add a second test using an executable fake tool that writes `partial` to the requested `-o` path, prints `error: unsupported`, and exits zero. Assert that `run_command` returns `status == "rejected"`, `diagnostic_error is True`, and `output_exists is True`.

Add a third test for `binding_status` with these three exact cases:

```python
self.assertEqual(module.binding_status({"status": "rejected"}, False, set()), "not-attempted")
self.assertEqual(module.binding_status({"status": "accepted"}, False, set()), "native-export-rejected")
self.assertEqual(
    module.binding_status(
        {"status": "accepted"}, True, {"std_addFN", "addRecFN", "fNToRecFN"}
    ),
    "accepted-with-hardfloat-binding",
)
```

- [ ] **Step 2: Run the test to verify the missing module is red**

Run:

```bash
python3 -m unittest tests.test_rc_calyx_hardfloat_bindings -v
```

Expected: import failure because `run_rc_calyx_hardfloat_bindings.py` does not yet exist.

- [ ] **Step 3: Add source-signature-faithful MRCs**

Create each MRC with `func.func @main`, one-element ranked memrefs, a load, the observed scalar operation, a store, and `return`. The operation and signature must exactly be the following table; use a pair of `memref<1xf32>` input operands for binary float operations.

| Filename | Required operation line | Output memref |
| --- | --- | --- |
| `addf-f32.mlir` | `%result = arith.addf %lhs, %rhs : f32` | `memref<1xf32>` |
| `subf-f32.mlir` | `%result = arith.subf %lhs, %rhs : f32` | `memref<1xf32>` |
| `mulf-f32.mlir` | `%result = arith.mulf %lhs, %rhs : f32` | `memref<1xf32>` |
| `divf-f32.mlir` | `%result = arith.divf %lhs, %rhs : f32` | `memref<1xf32>` |
| `cmpf-ugt-f32.mlir` | `%result = arith.cmpf ugt, %lhs, %rhs : f32` | `memref<1xi1>` |
| `sitofp-i32-f32.mlir` | `%result = arith.sitofp %value : i32 to f32` | input `memref<1xi32>`, output `memref<1xf32>` |
| `fptosi-f32-i8.mlir` | `%result = arith.fptosi %value : f32 to i8` | input `memref<1xf32>`, output `memref<1xi8>` |
| `uitofp-i1-f32.mlir` | `%result = arith.uitofp %value : i1 to f32` | input `memref<1xi1>`, output `memref<1xf32>` |

For example, `addf-f32.mlir` is exactly:

```mlir
module {
  func.func @main(%lhs_mem: memref<1xf32>, %rhs_mem: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %lhs = memref.load %lhs_mem[%c0] : memref<1xf32>
    %rhs = memref.load %rhs_mem[%c0] : memref<1xf32>
    %result = arith.addf %lhs, %rhs : f32
    memref.store %result, %output[%c0] : memref<1xf32>
    return
  }
}
```

For `cmpf-ugt-f32.mlir`, use the same three-argument shape and only substitute the output type and required `arith.cmpf` line. For the conversion MRCs, use one input memref and one output memref.

Create the README with this exact scope statement:

```markdown
# RC basic float MRCs

These scalar MRCs preserve signatures observed in the frozen
`tinystories-w8a8-rc-study-mask9-vocab6-width2` flat-SCF artifact. They are
capability and binding probes, not a replacement model, a numerical oracle, or
an equivalence test. Their results may identify a route worth attempting in the
full RC; only a subsequent complete-RC rerun can show pipeline advancement.
```

- [ ] **Step 4: Implement the inventory and common command helpers**

Create `scripts/pipeline/run_rc_calyx_hardfloat_bindings.py` with these public constants and functions:

```python
NON_GATING_POLICY = (
    "informational source inventory only; float presence or count does not decide lowering acceptance"
)

FORM_SPECS = {
    "arith.addf.f32": ("arith.addf", r"\barith\.addf\b.*:\s*f32"),
    "arith.subf.f32": ("arith.subf", r"\barith\.subf\b.*:\s*f32"),
    "arith.mulf.f32": ("arith.mulf", r"\barith\.mulf\b.*:\s*f32"),
    "arith.divf.f32": ("arith.divf", r"\barith\.divf\b.*:\s*f32"),
    "arith.cmpf.ugt.f32": ("arith.cmpf", r"\barith\.cmpf ugt,.*:\s*f32"),
    "arith.sitofp.i32-to-f32": ("arith.sitofp", r"\barith\.sitofp\b.*i32 to f32"),
    "arith.fptosi.f32-to-i8": ("arith.fptosi", r"\barith\.fptosi\b.*f32 to i8"),
    "arith.uitofp.i1-to-f32": ("arith.uitofp", r"\barith\.uitofp\b.*i1 to f32"),
}

CALYX_WRAPPER_MODULES = {"std_addFN", "std_mulFN", "std_divSqrtFN", "std_compareFN", "std_intToFp", "std_fpToInt"}
HARDFLOAT_IMPLEMENTATION_MODULES = {"addRecFN", "mulRecFN", "divSqrtRecFNToRaw_small", "compareRecFN", "iNToRecFN", "recFNToIN", "fNToRecFN", "recFNToFN"}
MRC_SPECS = {
    "addf-f32": {"form_id": "arith.addf.f32", "expected_wrapper": "std_addFN"},
    "subf-f32": {"form_id": "arith.subf.f32", "expected_wrapper": "std_addFN"},
    "mulf-f32": {"form_id": "arith.mulf.f32", "expected_wrapper": "std_mulFN"},
    "divf-f32": {"form_id": "arith.divf.f32", "expected_wrapper": "std_divSqrtFN"},
    "cmpf-ugt-f32": {"form_id": "arith.cmpf.ugt.f32", "expected_wrapper": "std_compareFN"},
    "sitofp-i32-f32": {"form_id": "arith.sitofp.i32-to-f32", "expected_wrapper": "std_intToFp"},
    "fptosi-f32-i8": {"form_id": "arith.fptosi.f32-to-i8", "expected_wrapper": "std_fpToInt"},
    "uitofp-i1-f32": {"form_id": "arith.uitofp.i1-to-f32", "expected_wrapper": "std_intToFp"},
}

def sha256_file(path: Path) -> str: ...
def observe_rc_forms(flat_scf: Path) -> dict[str, object]: ...
def require_observed_forms(report: dict[str, object]) -> None: ...
def run_command(label: str, command: list[str], log_path: Path, output_path: Path | None) -> dict[str, object]: ...
def binding_status(circt_attempt: dict[str, object], native_sv_ok: bool, modules: set[str]) -> str: ...
```

`observe_rc_forms` must scan line-by-line, record `count`, first `line`, and first `text` for every entry in `FORM_SPECS`, then record every matching `arith.*f`, `arith.sitofp`, `arith.uitofp`, `arith.fptosi`, or `math.*` operation absent from the declared forms under `unclassified_float_operations`. It returns `source_sha256`, `source_path`, `policy`, `forms`, and `unclassified_float_operations`.

`require_observed_forms` raises `ValueError("frozen RC no longer contains observed form: <form-id>")` only for a declared form whose count is zero. It must not inspect the unclassified list.

`run_command` follows the existing nonlinear-matrix rule: it captures combined stdout/stderr in `log_path`, considers `(^|: )error:` a diagnostic error, and accepts only exit code zero, no diagnostic error, and a non-empty requested output file.

`binding_status` returns exactly `not-attempted` for a rejected CIRCT attempt, `native-export-rejected` for accepted CIRCT with no valid native SV, `accepted-with-hardfloat-binding` when valid native SV contains at least one member of `CALYX_WRAPPER_MODULES` and one member of `HARDFLOAT_IMPLEMENTATION_MODULES`, and `accepted-without-recorded-hardfloat-binding` otherwise.

- [ ] **Step 5: Re-run the unit test and validate the checked-in MRC syntax**

Run:

```bash
python3 -m unittest tests.test_rc_calyx_hardfloat_bindings -v
MLIR=$(nix build .#mlir --no-link --print-out-paths)
for mrc in reproducers/calyx-rc-basic-float-mrcs/*.mlir; do
  "$MLIR/bin/mlir-opt" "$mrc" --verify-each >/dev/null
done
```

Expected: all Python tests pass and every MRC parses successfully.

- [ ] **Step 6: Commit the MRC and inventory contract**

```bash
git add reproducers/calyx-rc-basic-float-mrcs \
  scripts/pipeline/run_rc_calyx_hardfloat_bindings.py \
  tests/test_rc_calyx_hardfloat_bindings.py
git commit -m "test: define RC Calyx float binding coverage"
```

### Task 2: Prove the pinned Calyx/HardFloat closure and run RC-derived binding probes

**Files:**
- Create: `reproducers/calyx-rc-basic-float-bindings/input.futil`
- Create: `reproducers/calyx-rc-basic-float-bindings/README.md`
- Modify: `flake.nix:188-241`
- Modify: `flake.nix:2174-2253`
- Modify: `tests/test_calyx_float_nix_package.py`
- Modify: `scripts/pipeline/run_rc_calyx_hardfloat_bindings.py`
- Modify: `tests/test_rc_calyx_hardfloat_bindings.py`

**Interfaces:**
- Consumes: the pinned `calyx`, `hardfloat`, `circt`, `yosysPkg`, `yosysSlang`, RC flat-SCF package, MRCs from Task 1, and `calyx_to_sv_no_handshake.sh`.
- Produces: `packages.<system>.calyx-rc-basic-float-bindings-selftest` and `packages.<system>.tinystories-w8a8-rc-calyx-hardfloat-bindings`.
- Contract: the Futil closure package must instantiate every listed wrapper. The RC binding evidence package must always emit `report.json`, even when individual MRCs reject; a rejected MRC is evidence, not a derivation failure.

- [ ] **Step 1: Extend the package test before adding the fixture**

Add a test named `test_basic_float_binding_fixture_covers_every_rc_wrapper` to `tests/test_calyx_float_nix_package.py`. It must assert that `input.futil` imports all of:

```python
(
    "primitives/float/addFN.futil",
    "primitives/float/mulFN.futil",
    "primitives/float/divSqrtFN.futil",
    "primitives/float/compareFN.futil",
    "primitives/float/intToFp.futil",
    "primitives/float/fpToInt.futil",
)
```

It must assert the fixture instantiates `std_addFN(8, 24, 32)`, `std_mulFN(8, 24, 32)`, `std_divSqrtFN(8, 24, 32)`, `std_compareFN(8, 24, 32)`, `std_intToFp(32, 8, 24, 32)`, and `std_fpToInt(8, 24, 32, 8)`. It must also assert the README includes `not numerical-equivalence evidence`.

Add `test_hardfloat_binding_derivation_is_declared` that checks for the two package strings, `run_rc_calyx_hardfloat_bindings.py`, all eight MRC filenames, `calyx_to_sv_no_handshake.sh`, and `yosysSlang` in `flake.nix`.

- [ ] **Step 2: Run the expanded package test to prove the new assertions are red**

Run:

```bash
python3 -m unittest tests.test_calyx_float_nix_package -v
```

Expected: failure because the basic binding fixture and its derivation do not exist.

- [ ] **Step 3: Add one native-Calyx fixture covering all ordinary wrappers**

Create `reproducers/calyx-rc-basic-float-bindings/input.futil`. Import `core.futil` and the six primitive files named in Step 1. Instantiate these cells with f32 parameters:

```futil
add = std_addFN(8, 24, 32);
sub = std_addFN(8, 24, 32);
mul = std_mulFN(8, 24, 32);
div = std_divSqrtFN(8, 24, 32);
sqrt = std_divSqrtFN(8, 24, 32);
cmp = std_compareFN(8, 24, 32);
int_to_fp = std_intToFp(32, 8, 24, 32);
fp_to_int = std_fpToInt(8, 24, 32, 8);
```

Create one group per cell and sequence them in this exact order: `add`, `sub`, `mul`, `div`, `sqrt`, `cmp`, `int_to_fp`, `fp_to_int`. Drive each `go` high, each group’s `[done]` from its cell’s `done`, and supply IEEE-754 constants `32'h3f800000` and `32'h40000000` as operands. Set `add.subOp = 1'b0`, `sub.subOp = 1'b1`, `div.sqrtOp = 1'b0`, `sqrt.sqrtOp = 1'b1`, arithmetic `control = 1'b0`, and arithmetic `roundingMode = 3'b000`. Drive `cmp.signaling = 1'b0`, `int_to_fp.in = 32'd1`, `int_to_fp.signedIn = 1'b1`, `fp_to_int.in = 32'h3f800000`, and `fp_to_int.signedOut = 1'b1`.

Create the README with this exact limit paragraph:

```markdown
This is a Calyx/Morty library-closure and SystemVerilog parser test for the
pinned f32 HardFloat wrappers. It demonstrates that the named primitive files
and HardFloat implementation modules elaborate together. It is not
numerical-equivalence evidence, does not show that CIRCT selects these
wrappers for the frozen RC, and does not show that the complete RC reaches
Calyx or SystemVerilog.
```

The complete `input.futil` must be:

```futil
import "primitives/core.futil";
import "primitives/float/addFN.futil";
import "primitives/float/mulFN.futil";
import "primitives/float/divSqrtFN.futil";
import "primitives/float/compareFN.futil";
import "primitives/float/intToFp.futil";
import "primitives/float/fpToInt.futil";

component main(@go go: 1) -> (@done done: 1) {
  cells {
    add = std_addFN(8, 24, 32);
    sub = std_addFN(8, 24, 32);
    mul = std_mulFN(8, 24, 32);
    div = std_divSqrtFN(8, 24, 32);
    sqrt = std_divSqrtFN(8, 24, 32);
    cmp = std_compareFN(8, 24, 32);
    int_to_fp = std_intToFp(32, 8, 24, 32);
    fp_to_int = std_fpToInt(8, 24, 32, 8);
  }

  wires {
    group add_group {
      add.go = 1'b1;
      add.control = 1'b0;
      add.subOp = 1'b0;
      add.left = 32'h3f800000;
      add.right = 32'h40000000;
      add.roundingMode = 3'b000;
      add_group[done] = add.done;
    }
    group sub_group {
      sub.go = 1'b1;
      sub.control = 1'b0;
      sub.subOp = 1'b1;
      sub.left = 32'h40000000;
      sub.right = 32'h3f800000;
      sub.roundingMode = 3'b000;
      sub_group[done] = sub.done;
    }
    group mul_group {
      mul.go = 1'b1;
      mul.control = 1'b0;
      mul.left = 32'h3f800000;
      mul.right = 32'h40000000;
      mul.roundingMode = 3'b000;
      mul_group[done] = mul.done;
    }
    group div_group {
      div.go = 1'b1;
      div.control = 1'b0;
      div.sqrtOp = 1'b0;
      div.left = 32'h40000000;
      div.right = 32'h3f800000;
      div.roundingMode = 3'b000;
      div_group[done] = div.done;
    }
    group sqrt_group {
      sqrt.go = 1'b1;
      sqrt.control = 1'b0;
      sqrt.sqrtOp = 1'b1;
      sqrt.left = 32'h40000000;
      sqrt.right = 32'h3f800000;
      sqrt.roundingMode = 3'b000;
      sqrt_group[done] = sqrt.done;
    }
    group cmp_group {
      cmp.go = 1'b1;
      cmp.left = 32'h3f800000;
      cmp.right = 32'h40000000;
      cmp.signaling = 1'b0;
      cmp_group[done] = cmp.done;
    }
    group int_to_fp_group {
      int_to_fp.go = 1'b1;
      int_to_fp.in = 32'd1;
      int_to_fp.signedIn = 1'b1;
      int_to_fp_group[done] = int_to_fp.done;
    }
    group fp_to_int_group {
      fp_to_int.go = 1'b1;
      fp_to_int.in = 32'h3f800000;
      fp_to_int.signedOut = 1'b1;
      fp_to_int_group[done] = fp_to_int.done;
    }
  }

  control {
    seq {
      add_group;
      sub_group;
      mul_group;
      div_group;
      sqrt_group;
      cmp_group;
      int_to_fp_group;
      fp_to_int_group;
    }
  }
}
```

- [ ] **Step 4: Add the native closure derivation**

Immediately after `calyxFloatLibrarySelftest` in `flake.nix`, define:

```nix
        calyxRcBasicFloatBindingsSelftest = pkgs.runCommand
          "calyx-rc-basic-float-bindings-selftest" {
            nativeBuildInputs = [ calyx yosysPkg python ];
          } ''
            mkdir -p "$out"
            ${calyx}/bin/calyx \
              ${./reproducers/calyx-rc-basic-float-bindings/input.futil} \
              -l ${calyx}/share/calyx \
              -b verilog --synthesis --nested -d papercut \
              -o "$out/main.sv" >"$out/calyx.log" 2>&1
            test -s "$out/main.sv"
            ${python}/bin/python3 - "$out/main.sv" <<'PY'
            import re
            import sys
            from pathlib import Path

            source = Path(sys.argv[1]).read_text(encoding="utf-8")
            required = (
                "std_addFN", "std_mulFN", "std_divSqrtFN", "std_compareFN",
                "std_intToFp", "std_fpToInt", "addRecFN", "mulRecFN",
                "divSqrtRecFNToRaw_small", "compareRecFN", "iNToRecFN",
                "recFNToIN", "fNToRecFN", "recFNToFN",
            )
            for module in required:
                if not re.search(r"module\s+" + re.escape(module) + r"\b", source):
                    raise SystemExit(f"missing module definition: {module}")
            PY
            ${yosysPkg}/bin/yosys \
              -m ${yosysSlang}/share/yosys/plugins/slang.so \
              -p "read_slang --threads 1 --no-proc --max-parse-depth 20000 --top main $out/main.sv; hierarchy -top main -check; stat" \
              >"$out/yosys-slang.log" 2>&1
          '';
```

Export it in `packages` as `"calyx-rc-basic-float-bindings-selftest"` and in `checks` as `"calyx-rc-basic-float-bindings"`.

- [ ] **Step 5: Complete the RC binding runner**

Extend `run_rc_calyx_hardfloat_bindings.py` with this CLI:

```text
--flat-scf PATH
--circt-opt PATH
--circt-translate PATH
--calyx-bin PATH
--calyx-lib PATH
--calyx-to-sv-script PATH
--yosys PATH
--yosys-slang-plugin PATH
--mrc ID=PATH                 (repeat exactly eight times)
--out-dir PATH
```

Reject duplicate MRC IDs and require exactly these IDs: `addf-f32`, `subf-f32`, `mulf-f32`, `divf-f32`, `cmpf-ugt-f32`, `sitofp-i32-f32`, `fptosi-f32-i8`, and `uitofp-i1-f32`.

For every MRC, write all outputs below `$out-dir/mrcs/<id>/`:

1. Run `circt-opt INPUT --lower-scf-to-calyx=top-level-function=main -o calyx/model.calyx.mlir`; record exit code, error-diagnostic state, output validity, command, and log.
2. Only for an accepted Calyx MLIR result, write `calyx/manifest.json` containing `{"stage":"calyx","status":"ok","artifact":"model.calyx.mlir"}` and invoke the existing `calyx_to_sv_no_handshake.sh` with the supplied CIRCT translator, Calyx binary/library, the MRC `calyx` directory, and `native-sv` directory.
3. When `native-sv/model.futil` exists, record its `import "...";` paths. When `native-sv/sv/main.sv` exists, parse `module <identifier>` names, run supplied `yosys` with the supplied Slang plugin and `--top main`, and record the log/output validity.
4. Use `binding_status` to classify each row. Never infer a HardFloat binding from a float operation alone: require both a valid native SV file and the emitted module names.

Write `$out-dir/report.json` with this top-level schema:

```json
{
  "schema_version": 1,
  "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
  "inventory": {},
  "mrcs": [],
  "limits": [
    "The inventory is not a lowering gate.",
    "MRC capability and binding results are not RC functional-equivalence evidence.",
    "The complete RC still determines the next compiler frontier."
  ]
}
```

Every MRC object must contain `id`, `input_sha256`, `circt`, `futil_imports`, `native_sv`, `yosys_slang`, `sv_modules`, and `binding_status`. The program returns zero after writing a schema-valid report even if every MRC is rejected; malformed input, missing tools, missing files, or missing declared RC source forms are hard failures.
Every MRC object must also contain `form_id`, `expected_wrapper`, and `expected_wrapper_observed`; the last field is true only when its exact `expected_wrapper` occurs in emitted SV module names.

- [ ] **Step 6: Add the RC binding evidence derivation**

Define `rcCalyxHardfloatBindings` in `flake.nix` after `quantizedRcNonlinearFrontier`:

```nix
        rcCalyxHardfloatBindings = pkgs.runCommand
          "tinystories-w8a8-rc-calyx-hardfloat-bindings" {
            nativeBuildInputs = [ circt calyx yosysPkg python pkgs.bash ];
          } ''
            set -euo pipefail
            ${python}/bin/python3 ${./scripts/pipeline/run_rc_calyx_hardfloat_bindings.py} \
              --flat-scf ${pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-flat-scf"}/flat.scf.mlir \
              --circt-opt ${circt}/bin/circt-opt \
              --circt-translate ${circt}/bin/circt-translate \
              --calyx-bin ${calyx}/bin/calyx \
              --calyx-lib ${calyx}/share/calyx \
              --calyx-to-sv-script ${./scripts/pipeline/calyx_to_sv_no_handshake.sh} \
              --yosys ${yosysPkg}/bin/yosys \
              --yosys-slang-plugin ${yosysSlang}/share/yosys/plugins/slang.so \
              --mrc addf-f32=${./reproducers/calyx-rc-basic-float-mrcs/addf-f32.mlir} \
              --mrc subf-f32=${./reproducers/calyx-rc-basic-float-mrcs/subf-f32.mlir} \
              --mrc mulf-f32=${./reproducers/calyx-rc-basic-float-mrcs/mulf-f32.mlir} \
              --mrc divf-f32=${./reproducers/calyx-rc-basic-float-mrcs/divf-f32.mlir} \
              --mrc cmpf-ugt-f32=${./reproducers/calyx-rc-basic-float-mrcs/cmpf-ugt-f32.mlir} \
              --mrc sitofp-i32-f32=${./reproducers/calyx-rc-basic-float-mrcs/sitofp-i32-f32.mlir} \
              --mrc fptosi-f32-i8=${./reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.mlir} \
              --mrc uitofp-i1-f32=${./reproducers/calyx-rc-basic-float-mrcs/uitofp-i1-f32.mlir} \
              --out-dir "$out"
            test -s "$out/report.json"
          '';
```

Export it as `"tinystories-w8a8-rc-calyx-hardfloat-bindings"`. Do not put this evidence derivation in `checks`: its report is expected to contain rejected capability rows as the pinned compiler evolves.

- [ ] **Step 7: Verify the closure and evidence package**

Run:

```bash
python3 -m unittest \
  tests.test_calyx_float_nix_package \
  tests.test_rc_calyx_hardfloat_bindings -v
nix build .#calyx-rc-basic-float-bindings-selftest -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-calyx-hardfloat-bindings -L --no-link --print-out-paths
```

Expected: the closure self-test has native SV containing every required wrapper and HardFloat module, the evidence derivation writes `report.json`, and any rejected CIRCT MRC remains a recorded row rather than a false build success.

- [ ] **Step 8: Commit the binding evidence implementation**

```bash
git add flake.nix \
  reproducers/calyx-rc-basic-float-bindings \
  scripts/pipeline/run_rc_calyx_hardfloat_bindings.py \
  tests/test_calyx_float_nix_package.py \
  tests/test_rc_calyx_hardfloat_bindings.py
git commit -m "feat: package RC HardFloat binding evidence"
```

### Task 3: Screen the complete local paper corpus without importing or retaining PDFs

**Files:**
- Create: `scripts/pipeline/screen_fpga_llm_math_exp_corpus.py`
- Create: `tests/test_fpga_llm_math_exp_corpus.py`
- Modify: `flake.nix:2174-2265`

**Interfaces:**
- Consumes: a caller-supplied `--paper-root` containing `data/catalog.json` and ignored `papers/`, plus a caller-supplied `pdftotext` executable.
- Produces: deterministic JSON whose evidence is limited to catalog metadata, verified cache hashes, term counts, and 1-based page numbers.
- Contract: all catalog entries are represented; entries with absent or hash-invalid cache files are explicitly recorded and never searched. The JSON contains no extracted paper text, excerpts, or PDF bytes.

- [ ] **Step 1: Write corpus-screen tests before implementation**

Create `tests/test_fpga_llm_math_exp_corpus.py`. It must create a small schema-version-1 catalog with two keys, one verified PDF cache receipt and one missing receipt, then execute a fake `pdftotext` program that emits two pages separated by `\f`. Use this page content only in the test fixture:

```text
page one: Softmax uses maximum subtraction.
\f
page two: The exponential is implemented with a lookup table. NEVER_COPY_THIS_SENTENCE.
```

Assert all of the following:

```python
self.assertEqual(result["schema_version"], 1)
self.assertEqual(result["corpus"]["catalog_records"], 2)
self.assertEqual(result["corpus"]["verified_pdf_records"], 1)
self.assertEqual(result["papers"]["1111.11111v1"]["cache_status"], "verified")
self.assertEqual(result["papers"]["1111.11111v1"]["term_pages"]["exp"], [2])
self.assertTrue(result["papers"]["1111.11111v1"]["deep_read_candidate"])
self.assertEqual(result["papers"]["2222.22222v1"]["cache_status"], "missing")
self.assertNotIn("NEVER_COPY_THIS_SENTENCE", json.dumps(result))
```

Add a hash-mismatch test that changes the cache receipt digest and asserts `cache_status == "sha256-mismatch"`, no `term_pages` entries, and `deep_read_candidate is False`.

- [ ] **Step 2: Run the corpus test to verify it is red**

Run:

```bash
python3 -m unittest tests.test_fpga_llm_math_exp_corpus -v
```

Expected: import failure because `screen_fpga_llm_math_exp_corpus.py` does not yet exist.

- [ ] **Step 3: Implement a deterministic, no-text-retention corpus screen**

Create `scripts/pipeline/screen_fpga_llm_math_exp_corpus.py` with these exact term groups:

```python
SEMANTIC_TERMS = {
    "exp": r"\bexp(?:onential)?\b",
    "softmax": r"\bsoftmax\b",
    "maximum-subtraction": r"(?:subtract(?:ion)?[^\f]{0,80}maximum|maximum[^\f]{0,80}subtract)",
    "normalization": r"\b(?:layernorm|rmsnorm|normalization)\b",
}
IMPLEMENTATION_TERMS = {
    "lookup-table": r"\b(?:lookup table|lut)\b",
    "polynomial": r"\bpolynomial\b",
    "piecewise": r"\bpiecewise(?:[- ]linear)?\b",
    "range-reduction": r"\brange reduction\b",
    "floating-point": r"\bfloating[ -]point\b",
}
```

Implement `sha256_file(path: Path) -> str`, `load_catalog(path: Path) -> dict[str, object]`, `extract_pages(pdftotext: str, pdf: Path) -> list[str]`, `screen_paper(...) -> dict[str, object]`, and `screen_catalog(...) -> dict[str, object]`.

`load_catalog` requires `schema_version == 1` and a dictionary-valued `papers` field. `extract_pages` invokes:

```python
[pdftotext, "-enc", "UTF-8", "-layout", str(pdf), "-"]
```

and raises a descriptive error only when that program exits nonzero. It returns in-memory page strings split on form-feed and never writes them to disk.

For a verified PDF, `screen_paper` records a sorted `term_pages` mapping for every matching term and sets `deep_read_candidate` true only when it has at least one semantic-term page and at least one implementation-term page. It records `cache_status`, `arxiv_id`, `version`, `title`, `abs_url`, `pdf_url`, cache SHA-256, and byte count. It records neither page text nor excerpts.

For an absent cache record/file or digest mismatch, emit the paper metadata, an empty `term_pages` object, `deep_read_candidate: false`, and the precise `cache_status` (`missing-cache-receipt`, `missing`, or `sha256-mismatch`).

The CLI is:

```text
--paper-root PATH
--catalog PATH                 default: PAPER_ROOT/data/catalog.json
--papers-dir PATH              default: PAPER_ROOT/papers
--pdftotext PATH               default: pdftotext
--out-json PATH
```

The result schema is:

```json
{
  "schema_version": 1,
  "blocker": "math.exp",
  "terms": {"semantic": {}, "implementation": {}},
  "corpus": {
    "catalog_sha256": "",
    "catalog_records": 0,
    "verified_pdf_records": 0,
    "unavailable_pdf_records": 0
  },
  "papers": {}
}
```

Sort paper keys, term names, and page lists to make repeated runs byte-stable when the same archive is supplied.

- [ ] **Step 4: Package the screen as a Nix app, not a PDF-input derivation**

Define this binding in the `let` section of `flake.nix`:

```nix
        rcMathExpPaperScreen = pkgs.writeShellApplication {
          name = "rc-math-exp-paper-screen";
          runtimeInputs = [ python pkgs.poppler_utils ];
          text = ''
            exec ${python}/bin/python3 ${./scripts/pipeline/screen_fpga_llm_math_exp_corpus.py} "$@"
          '';
        };
```

Export it both as `packages."rc-math-exp-paper-screen"` and as:

```nix
        apps."rc-math-exp-paper-screen" = {
          type = "app";
          program = "${rcMathExpPaperScreen}/bin/rc-math-exp-paper-screen";
        };
```

Do not add `/home/roland/LLM-inference-on-FPGA-papers` as a Nix source or derivation input. The caller supplies it only at `nix run` time.

- [ ] **Step 5: Verify the screen and run it over the local archive**

Run:

```bash
python3 -m unittest tests.test_fpga_llm_math_exp_corpus -v
nix run .#rc-math-exp-paper-screen -- \
  --paper-root /home/roland/LLM-inference-on-FPGA-papers \
  --out-json docs/results/2026-07-16-rc-math-exp-paper-screen.json
```

Expected: the test passes; the JSON covers every catalog record, records the current catalog SHA-256, separates verified from unavailable cache entries, and contains no paper text.

- [ ] **Step 6: Commit the screen and its Nix entry point**

```bash
git add flake.nix \
  scripts/pipeline/screen_fpga_llm_math_exp_corpus.py \
  tests/test_fpga_llm_math_exp_corpus.py
git commit -m "feat: screen local FPGA LLM corpus for math exp"
```

### Task 4: Execute the evidence packet, deep-read candidates, and publish the next frontier

**Files:**
- Create: `docs/results/2026-07-16-rc-calyx-hardfloat-binding.md`
- Create: `docs/results/2026-07-16-rc-math-exp-fpga-corpus.md`
- Create: `docs/results/2026-07-16-rc-math-exp-blocker-packet.md`
- Create: `tests/test_rc_math_exp_blocker_packet.py`
- Modify: `docs/results/2026-07-16-rc-math-exp-paper-screen.json` (generated checked-in metadata evidence)

**Interfaces:**
- Consumes: the Task 2 Nix binding report, Task 3 paper-screen JSON, existing nonlinear provenance slices and frontier result, existing `calyx-math-exp-upstream-reproducer`, and the full RC Calyx stage manifest/log.
- Produces: a complete first-blocker packet and one decision: a named candidate is either a direct lowerer/library route, a named composition needing a semantics review, or an approximation/changed-contract route. No row may be labelled exact.
- Contract: the packet identifies the next full-RC action, and it makes no claim that a primitive probe, library closure, paper, compiler boundary, or four-case smoke result proves PT2E-to-SV equivalence. Any local candidate must name the later exhaustive RC observable-functional-equivalence gate.

- [ ] **Step 1: Write a documentation-claim guard**

Create `tests/test_rc_math_exp_blocker_packet.py` with these checks:

```python
class RcMathExpBlockerPacketTest(unittest.TestCase):
    def test_packet_keeps_the_canonical_boundary(self) -> None:
        packet = (ROOT / "docs/results/2026-07-16-rc-math-exp-blocker-packet.md").read_text(encoding="utf-8")
        self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", packet)
        self.assertIn("math.exp", packet)
        self.assertIn("not numerical-equivalence evidence", packet)
        self.assertIn("hardware-oracle gate has not run", packet)
        self.assertNotIn("math.exp is exact", packet.lower())

    def test_corpus_result_preserves_pdf_boundary(self) -> None:
        corpus = (ROOT / "docs/results/2026-07-16-rc-math-exp-fpga-corpus.md").read_text(encoding="utf-8")
        self.assertIn("PDFs were read locally and were not copied", corpus)
        self.assertIn("approximation or co-design evidence", corpus)
        self.assertNotIn("bit-exact route", corpus.lower())
```

- [ ] **Step 2: Run the claim guard to prove the result documents are absent**

Run:

```bash
python3 -m unittest tests.test_rc_math_exp_blocker_packet -v
```

Expected: `FileNotFoundError` for the first result document.

- [ ] **Step 3: Run the durable commands and preserve their output paths**

Run the following commands from the repository root. Record every resulting store path and the relevant output file hashes in the packet; do not copy store artifacts into `tmp`.

```bash
nix build .#calyx-math-exp-upstream-reproducer -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-nonlinear-slices -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-nonlinear-lowering-frontier -L --no-link --print-out-paths
nix build .#calyx-rc-basic-float-bindings-selftest -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-calyx-hardfloat-bindings -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx -L --no-link --print-out-paths
nix run .#rc-math-exp-paper-screen -- \
  --paper-root /home/roland/LLM-inference-on-FPGA-papers \
  --out-json docs/results/2026-07-16-rc-math-exp-paper-screen.json
```

Inspect `report.json`, `manifest.json`, `lower-scf-to-calyx.log`, the MRC logs, `model.futil` imports when present, `main.sv` module inventory when present, and the corpus JSON. A full-RC Calyx manifest with `status: "failed"` is an expected captured outcome when it names `math.exp`; do not fabricate an SV handoff.

- [ ] **Step 4: Deep-read exactly the screened candidate papers and write the corpus evidence**

Open only PDFs whose screen row has `deep_read_candidate: true`. For each candidate, inspect the screen-reported pages and any directly adjacent page needed to resolve a figure or sentence. Do not retain page images, extracted text, or quotations longer than needed for a short paraphrase.

Create `docs/results/2026-07-16-rc-math-exp-fpga-corpus.md` with these exact sections:

1. `# RC math.exp FPGA-LLM corpus evidence`.
2. `## Corpus boundary`, stating the catalog SHA-256, catalog-record count, verified-cache count, unavailable-cache count from the screen JSON, all eight search terms, and: `PDFs were read locally and were not copied into this repository or a Nix derivation.`
3. `## Candidate evidence`, a table with columns `Paper`, `Evidence page or section`, `Model/operator context`, `Implementation technique`, `Precision`, `FPGA context`, and `Classification`. Use one of exactly `direct implementation evidence`, `approximation or co-design evidence`, or `context only` in every row. Link `Paper` to the catalog `abs_url` and include its versioned arXiv key plus verified cache SHA-256 in the cell.
4. `## Interpretation for the canonical RC`, stating separately whether any paper describes a direct canonical `math.exp` route, whether it describes a named composition, and which rows change the semantic contract. State that literature evidence does not prove PT2E equivalence.

The paper classification is a precise paraphrase of the paper’s own relevant claim, not an inference from the paper title or a keyword hit. A LUT, polynomial, range-reduced exponential, changed Softmax, altered quantization, or accuracy/fidelity tradeoff is classified `approximation or co-design evidence` even if the paper reports successful inference.

- [ ] **Step 5: Write the Calyx/HardFloat binding result**

Create `docs/results/2026-07-16-rc-calyx-hardfloat-binding.md` from the Task 2 report with these sections:

1. `# RC Calyx/HardFloat basic-float binding evidence`.
2. `## Unit under test`, with model key, flat-SCF SHA-256, and the informational-inventory policy verbatim.
3. `## Native library closure`, listing each of the six Futil wrappers and whether the standalone fixture’s `main.sv` contains its wrapper and the corresponding HardFloat module.
4. `## RC-derived MRC results`, a table with `RC form`, `MRC`, `CIRCT result`, `Futil imports`, `native SV/Yosys result`, and `Binding status`, copied from `report.json` without upgrading a rejected row to support.
5. `## Limits`, including: `This is not numerical-equivalence evidence. The full RC has not reached a valid Calyx artifact or SystemVerilog through this route.`

Use the emitted `model.futil` and SV module names, not a list of files merely present in the Calyx installation, to make a binding statement.

- [ ] **Step 6: Write the complete `math.exp` blocker packet**

Create `docs/results/2026-07-16-rc-math-exp-blocker-packet.md` with these exact sections and decision rules:

1. `# Frozen RC math.exp blocker packet`.
2. `## Full-RC observation`: command, model key, flat-SCF SHA-256, Calyx-stage manifest status, lowerer exit status, `error:`-diagnostic state, partial-artifact state, and the first diagnostic naming `math.exp`. Link the existing scalar MRC and attention-Softmax provenance slice by repository path.
3. `## Operation context`: identify `math.exp` as f32 in Softmax after maximum subtraction and before sum/normalization, using the mechanically derived provenance metadata. Record the source artifact SHA-256, source line range, retained external values, operand/result type, and any surrounding constants/shapes present in the existing attention-Softmax slice. Include the exact sentence: `The scalar MRC and native Futil closure are not numerical-equivalence evidence.`
4. `## Toolchain and library matrix`: one row each for direct CIRCT, Calyx Futil, HardFloat, MLIR `convert-math-to-funcs`, MLIR `convert-math-to-libm`, Torch-MLIR/TOSA, and checked-in local compatibility passes. For each, include observed result and whether it is upstream, local, or not applicable. Do not call generic HardFloat arithmetic an `exp` implementation.
5. `## Local paper corpus evidence`: link the corpus result and summarize its classification counts, not paper text.
6. `## Candidate decision`: list every candidate in exactly one of three classes: direct lowerer/library route; named composition; approximation or changed semantic contract. Mark a class with no candidates as `none observed in this iteration`. No candidate is `exact`; the hardware-oracle gate has not run. For a local candidate, explicitly state that four-case smoke conformance is insufficient and name the `6^8` exhaustive RC observable-functional-equivalence gate.
7. `## Next full-RC action`: if a direct route was observed and emits a concrete hardware implementation, state that it needs a separately reviewed integration-and-oracle plan before changing the pipeline. If that plan integrates a local transform, it must implement the deterministic-reset exhaustive `6^8` checker from `docs/adr/2026-07-16-local-pass-observable-equivalence.md`. If no direct route was observed, state that the canonical route remains blocked at `math.exp` and that the next decision is either upstream/compiler work for canonical semantics or separately approved approximation research. Do not integrate a paper technique in this task.

- [ ] **Step 7: Run all focused verification and inspect the clean tree**

Run:

```bash
python3 -m unittest \
  tests.test_calyx_float_nix_package \
  tests.test_rc_calyx_hardfloat_bindings \
  tests.test_fpga_llm_math_exp_corpus \
  tests.test_rc_math_exp_blocker_packet -v
nix build .#calyx-rc-basic-float-bindings-selftest -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-calyx-hardfloat-bindings -L --no-link --print-out-paths
git status --short
```

Expected: all tests pass, both named derivations emit their declared artifacts, the full-RC package has a truthful manifest rather than placeholder SV, and `git status --short` lists only the result/docs/test files intended for this task.

- [ ] **Step 8: Commit the first blocker packet and leave the tree clean**

```bash
git add docs/results/2026-07-16-rc-calyx-hardfloat-binding.md \
  docs/results/2026-07-16-rc-math-exp-paper-screen.json \
  docs/results/2026-07-16-rc-math-exp-fpga-corpus.md \
  docs/results/2026-07-16-rc-math-exp-blocker-packet.md \
  tests/test_rc_math_exp_blocker_packet.py
git commit -m "docs: record RC math exp blocker packet"
git status --short
```

Expected: the final status command prints no paths.

## Execution-boundary decision

This plan intentionally stops after the first evidence packet. Its direct-route outcome is data-dependent: a valid candidate must first establish what CIRCT/Calyx emits and what numerical contract it carries. If the packet identifies a route that can be integrated without changing canonical semantics, write a focused integration-and-oracle implementation plan before modifying the pipeline. A local integration plan must include the deterministic-reset exhaustive `6^8` RC observable-functional-equivalence gate recorded in `docs/adr/2026-07-16-local-pass-observable-equivalence.md`. If it identifies only approximations or no implementation route, keep the full RC blocked at `math.exp` and use the packet as the decision record for either upstream work or a separately approved fidelity contract.

## Self-review

- The approved design’s RC-as-driver requirement is implemented by the full-RC rerun and the rule that primitive results cannot advance the system alone.
- The approved Calyx/HardFloat request is covered by both the six-wrapper native Futil closure and emitted Futil/SV binding evidence for MRCs derived from actual RC source forms.
- The paper-archive requirement is covered by a complete catalog/cache screen, hash validation, local-only PDF reading, and a curated page-cited result that does not retain text or PDFs.
- The no-float-gate requirement is encoded in `NON_GATING_POLICY`, unknown-form recording, and tests that prove unknown floating operations do not cause source-inventory rejection.
- The PT2E trust boundary and no-approximation rule are enforced by the packet claim guard and by the explicit stop before integration.
- Names, command-line arguments, package names, result paths, and test module names are consistent across all four tasks.
