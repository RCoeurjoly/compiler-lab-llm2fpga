# RC Pre-Morty Source-Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox \`- [ ]\` syntax for tracking.

**Goal:** Make the V=6 PT2E W8A8 equivalence DUT a reproducible Calyx pre-Morty SystemVerilog source closure, then use it for the strict Verilator frozen-four gate and eventual complete deterministic shard evidence.

**Architecture:** A small Calyx patch emits the raw Verilog before any Morty work. A producer materializes the generated source plus an explicit ordered Calyx/HardFloat closure and a hash-bound generation receipt. Strict equivalence accepts only that closure manifest, privately stages and verifies every compiler input, and carries the complete closure identity through cache validation, results, frozen reduction, and later shard merging.

**Tech Stack:** Rust/Calyx 0.7.1 source patch, Nix, Bash, Python 3 standard library, SystemVerilog, HardFloat, Verilator 5.022, existing PT2E observable oracle.

## Global Constraints

- Preserve unrelated dirty and staged work in the shared main checkout. Do not reset, clean, broadly stage, or commit it.
- Use apply_patch for persistent edits. Keep disposable compiler experiments under /tmp.
- The direct DUT is named a Calyx pre-Morty source closure. Do not call it byte-identical to a Morty bundle and do not change the legacy bundled artifact.
- The Calyx flag is visible as --emit-pre-morty. It bypasses the entire Morty setup, including syntax-tree construction, not only do_pickle.
- The initial closure has exactly these ordered compilation units: memories/seq.sv; mulFN.sv; intToFp.sv; fpToInt.sv; divSqrtFN.sv; compareFN.sv; addFN.sv; core.sv; binary_operators.sv; HardFloat_primitives.v; HardFloat_rawFN.v; addRecFN.v; compareRecFN.v; divSqrtRecFN_small.v; fNToRecFN.v; iNToRecFN.v; isSigNaNRecFN.v; mulRecFN.v; recFNToFN.v; recFNToIN.v; RISCV/HardFloat_specialize.v; and generated pre-morty-calyx.sv.
- The only ordered include roots are the staged HardFloat source root containing HardFloat_consts.vi and HardFloat_localFuncs.vi, then its RISCV root containing HardFloat_specialize.vi.
- Do not concatenate HDL, glob inputs, retain store paths in the compiler contract, allow ambient include paths, or accept undeclared macros. The first macro policy is exactly defines=[] and undefines=[VERILATOR].
- Only the generated top source may receive the existing continuous-assignment paging normalizer. Primitive and include bytes remain exact.
- The producer and runner must share one normalizer implementation and identity. The manifest hash must bind the producer receipt through an explicit relative path and SHA-256; the runner must never discover it ambiently.
- Strict source-closure mode requires the three flags --sv-filelist, --sv-root, and --sv-closure-manifest. Legacy --sv remains a non-strict one-file diagnostic adapter and is rejected in strict mode.
- Bump STRICT_CACHE_SCHEMA_VERSION from 8 to 9, STRICT_RESULT_SCHEMA from rc-observable-verilator-shard-v3 to v4, and FROZEN_FOUR_SCHEMA from rc-observable-frozen-four-v3 to v4. Leave STRICT_FIXTURE_SCHEMA unchanged unless its byte content is intentionally changed.
- Preserve every existing strict property: exact six signed int8 logit codes, lowest-index argmax, image/oracle provenance, immutable-memory checks, external-memory binding receipt, ABI validation, reset/completion lifecycle, and isolated cached runtime snapshot.
- Do not launch any all-domain workload before the direct source closure passes bundled-vs-direct MRC parity, strict [0,1) smoke, and frozen four fresh-versus-sequential reduction.

---

## File Structure

- Create: patches/calyx/0001-emit-pre-morty-verilog.patch — pinned Calyx source patch exposing the raw-emission switch.
- Modify: nix/calyx.nix — apply the Calyx patch without changing Cargo or flake locks.
- Create: scripts/pipeline/rc_sv_normalizer.py — shared safe Verilator normalizer and its identity.
- Create: scripts/pipeline/rc_sv_source_closure.py — canonical manifest validation, secure closure loading, exact staging, include scanning, and closure digests.
- Create: scripts/pipeline/materialize_calyx_pre_morty_closure.py — producer-side fixed Calyx/HardFloat closure and provenance receipt writer.
- Modify: scripts/pipeline/calyx_to_sv_no_handshake.sh — explicit optional bundled or pre-morty producer mode; legacy five-argument behavior remains bundled.
- Modify: scripts/pipeline/run_rc_sv_equivalence.py — strict closure CLI, Verilator command construction, cache validation, v4 results, and frozen reducer identity.
- Create: diagnostics/calyx-pre-morty-flag.nix — small Calyx switch/default/raw deterministic regression.
- Create: diagnostics/rc-calyx-pre-morty-parity.nix — direct-versus-bundled behavioral MRC parity target.
- Create: scripts/pipeline/run_calyx_pre_morty_mrc_parity.py — all-wrapper MRC testbench and transcript parity driver.
- Modify: diagnostics/rc-observable-equivalence.nix — named direct-closure compile, smoke, fresh, sequential, and reducer invocations.
- Modify: flake.nix — separate pre-Morty producer and explicitly named proof targets; leave legacy bundle aliases intact.
- Create: tests/test_rc_sv_source_closure.py — pure closure/normalizer/canonicalization/staging tests.
- Create: tests/test_calyx_pre_morty_closure.py — materializer and producer-receipt tests.
- Create: tests/test_rc_calyx_pre_morty_parity.py — MRC vector/transcript parser tests.
- Modify: tests/test_calyx_float_nix_package.py — Calyx patch, switch selftest, and legacy producer-isolation assertions.
- Modify: tests/test_calyx_export_normalization.py — assert the new producer preserves the existing normalized-Futil chain.
- Modify: tests/test_rc_observable_driver.py — strict CLI, cache, receipt, and frozen-reducer closure tests.
- Modify: tests/test_rc_sv_equivalence_fixture.py — legacy adapter and ordered Verilator-command tests.
- Create: scripts/pipeline/merge_rc_observable_results.py and tests/test_rc_observable_results.py — closure-aware v4 shard-plan, probe, and full-coverage merger.
- Modify: docs/superpowers/specs/2026-08-05-rc-pre-morty-source-closure-design.md — mark the design implemented only after its acceptance ladder passes.

### Task 1: Share the normalizer and define a fail-closed source-closure library

**Files:**
- Create: scripts/pipeline/rc_sv_normalizer.py
- Create: scripts/pipeline/rc_sv_source_closure.py
- Create: tests/test_rc_sv_source_closure.py
- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_sv_equivalence_fixture.py

**Interfaces:**
- Produces normalize_sv_text(source: str) -> str and normalization_metrics(raw: str, normalized: str) -> dict[str, int].
- Produces load_source_closure(*, root: Path, filelist: Path, manifest: Path) -> SourceClosure.
- Produces stage_source_closure(closure: SourceClosure, stage_root: Path) -> StagedSourceClosure.
- SourceClosure exposes top_module, top_source_raw, source rows, include-root rows, producer_receipt, canonical_sha256, raw_aggregate_sha256, and compiled_aggregate_sha256.

- [ ] **Step 1: Write the failing pure-unit tests**

Create compact synthetic sources and an exact manifest in test_rc_sv_source_closure.py. Cover a valid two-source closure with a literal include, a generated main_1 source requiring paging, and an unmodified helper source. Assert source order, include-root order, staged fixed names, and the absence of any procedural normalizer output:

~~~~python
closure = closure_module.load_source_closure(
    root=root,
    filelist=root / "sources.f",
    manifest=root / "closure.json",
)
staged = closure_module.stage_source_closure(closure, root / "cache" / "sv")
self.assertEqual(
    [path.name for path in staged.sources],
    ["0000.sv", "0001.sv"],
)
self.assertIn("-UVERILATOR", staged.verilator_flags)
self.assertNotIn("always_comb", staged.sources[1].read_text(encoding="utf-8"))
self.assertEqual(
    staged.sources[0].read_bytes(),
    (root / "sources" / "helper.sv").read_bytes(),
)
~~~~

Add one failure assertion for each contract: noncanonical JSON, wrong schema, altered manifest SHA, filelist/manifest order mismatch, empty filelist, blank/comment/flag filelist line, unsupported suffix, absolute/escaping/backslash path, duplicate/colliding path, symlink or nonregular member, raw byte/hash/length mismatch, undeclared literal include, macro-computed include, include cycle, duplicate top module, absent top module, and top module defined by include material.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_sv_source_closure -v
~~~~

Expected: FAIL because neither the shared closure library nor the normalizer module exists.

- [ ] **Step 3: Implement canonicalization, scanning, and staging**

Move the current lexical and continuous-assignment paging functions from run_rc_sv_equivalence.py into rc_sv_normalizer.py without semantic changes. Publish one explicit identity:

~~~~python
NORMALIZER_SCHEMA = "rc-sv-continuous-pages-v1"

def normalized_sv_text(source: str) -> str:
    lexical = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    lexical = re.sub(r"//[^\n]*", "", lexical)
    lexical = normalize_large_or_assignments(lexical)
    return lexical.replace(";", ";\n").replace(" | ", " |\n")
~~~~

In rc_sv_source_closure.py, serialize the payload without canonical_sha256 using UTF-8 JSON with sorted keys and separators=(",", ":"). Compute canonical_sha256 as SHA-256 of the domain prefix rc-sv-source-closure-v1 followed by a NUL byte and the serialized payload. Require the on-disk manifest bytes to equal the canonical rendered document.

Accept only this manifest shape:

~~~~json
{
  "schema": "rc-sv-source-closure-v1",
  "top_module": "main_1",
  "sources": [],
  "include_roots": [],
  "defines": [],
  "undefines": ["VERILATOR"],
  "verilator_arguments": ["--top-module", "tb"],
  "producer_receipt": {
    "logical_path": "producer-receipt.json",
    "sha256": "64 lowercase hex characters"
  },
  "canonical_sha256": "64 lowercase hex characters"
}
~~~~

Require each source row to give ordinal, logical_path, language, bytes, raw_sha256, normalized_sha256, and normalization. Permit only sv and v source suffix/language pairs. Permit identity-v1 for helpers and calyx-generated-main-v1 only for the unique top source. Recursively scan only quoted literal include directives; resolve them against declared ordered include roots; reject all other include syntax and every unlisted or ambiguous dependency. Stage files exclusively from the in-memory validated snapshot under sv/0000.ext through sv/0021.ext, sv/includes/00, sv/includes/01, sources.f, closure.json, and producer-receipt.json.

Use an explicit sibling-directory insertion before importing rc_sv_normalizer from runner code so importlib-based existing tests do not rely on the current working directory. Re-export existing underscored normalizer helpers from the runner for compatibility with current tests.

- [ ] **Step 4: Run focused library and legacy-normalizer tests**

Run:

~~~~bash
python3 -m unittest tests.test_rc_sv_source_closure tests.test_rc_sv_equivalence_fixture -v
python3 -m py_compile scripts/pipeline/rc_sv_normalizer.py scripts/pipeline/rc_sv_source_closure.py scripts/pipeline/run_rc_sv_equivalence.py
~~~~

Expected: closure validation and the pre-existing four-state normalizer tests pass.

- [ ] **Step 5: Checkpoint**

Inspect only the paths in this task with git diff --check. Record the normalizer schema and the focused test output in the SDD ledger; do not commit the shared checkout.

### Task 2: Patch Calyx to emit pre-Morty Verilog durably

**Files:**
- Create: patches/calyx/0001-emit-pre-morty-verilog.patch
- Modify: nix/calyx.nix
- Create: diagnostics/calyx-pre-morty-flag.nix
- Modify: flake.nix
- Modify: tests/test_calyx_float_nix_package.py

**Interfaces:**
- Calyx accepts --emit-pre-morty only for the Verilog backend with a float special-library import.
- Default Verilog behavior still executes its original Morty bundle path.
- The Nix check exposes calyx-pre-morty-flag-selftest.

- [ ] **Step 1: Write the failing package and source-contract tests**

Extend test_calyx_float_nix_package.py to require the checked-in patch, the nix/calyx.nix patches list, a named selftest derivation, and a distinct package export. Assert the legacy five-argument producer still writes only its bundled sv/main.sv and root sources.f path.

The Nix selftest must execute these cases:

~~~~bash
calyx --help
calyx float-input.futil -l <library> -b verilog --synthesis --nested -d papercut -o bundled.sv
calyx float-input.futil -l <library> -b verilog --synthesis --nested -d papercut --emit-pre-morty -o raw-a.sv
calyx float-input.futil -l <library> -b verilog --synthesis --nested -d papercut --emit-pre-morty -o raw-b.sv
calyx integer-input.futil -l <library> -b verilog --emit-pre-morty -o invalid.sv
~~~~

Require help to name the flag; bundled output to contain a HardFloat definition; raw output to contain the generated top but not bundled HardFloat definitions; raw-a.sv and raw-b.sv to compare byte-for-byte; and the integer call to fail with the stable raw-mode diagnostic.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_calyx_float_nix_package -v
nix eval .#packages.x86_64-linux.calyx-pre-morty-flag-selftest.drvPath --raw
~~~~

Expected: the Python source-contract assertion and the Nix evaluation fail until the patch/check are wired.

- [ ] **Step 3: Implement the minimal Calyx patch**

Patch the pinned upstream paths src/cmdline.rs, calyx/ir/src/context.rs, src/main.rs, and calyx/backend/src/verilog.rs. The key behavior is:

~~~~rust
// src/cmdline.rs
#[argh(switch, long = "emit-pre-morty")]
pub emit_pre_morty: bool;

// calyx/ir/src/context.rs
pub emit_pre_morty: bool,

// src/main.rs
emit_pre_morty: opts.emit_pre_morty,

// calyx/backend/src/verilog.rs
if ctx.bc.emit_pre_morty && !check_library_needed(ctx) {
    return Err(Error::misc(
        "--emit-pre-morty requires a float special-library import",
    ));
}
...
if check_library_needed(ctx) && !ctx.bc.emit_pre_morty {
    // Existing build_library_bundle, derive_file_list,
    // morty::build_syntax_tree, and morty::do_pickle block unchanged.
}
~~~~

Reject use of the switch with any non-Verilog backend before backend dispatch so it cannot silently do nothing. Add the patch via nix/calyx.nix:

~~~~nix
patches = [
  ../patches/calyx/0001-emit-pre-morty-verilog.patch
];
~~~~

Do not edit Cargo.lock, the flake lock, Morty source, or default Verilog behavior.

- [ ] **Step 4: Add and expose the selftest**

Implement diagnostics/calyx-pre-morty-flag.nix with the existing float and integer reproducible Futil inputs. Use the patched Calyx package and a small Python assertion to inspect modules rather than fragile shell pattern matching. Import it in flake.nix near the existing Calyx selftests and expose both a package and a check named calyx-pre-morty-flag-selftest.

- [ ] **Step 5: Verify the compiler boundary**

Run:

~~~~bash
python3 -m unittest tests.test_calyx_float_nix_package -v
nix build .#calyx-pre-morty-flag-selftest -L
git diff --check
~~~~

Expected: default bundle and raw output tests pass, and no source outside the Calyx patch/Nix selftest changed for this task.

### Task 3: Materialize the explicit Calyx/HardFloat closure in a separate producer artifact

**Files:**
- Create: scripts/pipeline/materialize_calyx_pre_morty_closure.py
- Create: tests/test_calyx_pre_morty_closure.py
- Modify: scripts/pipeline/calyx_to_sv_no_handshake.sh
- Modify: tests/test_calyx_export_normalization.py
- Modify: tests/test_calyx_float_nix_package.py
- Modify: flake.nix

**Interfaces:**
- materialize_calyx_pre_morty_closure.py receives raw generated SV, a Calyx library root, an output directory, a declared top module, normalized/raw Futil paths, f32 receipt, Calyx MLIR, Calyx executable, and the exact Calyx argv/log.
- It writes source-closure/sources.f, source-closure/closure.json, source-closure/producer-receipt.json, sources/0000 through sources/0021, and the two sealed include roots.
- calyx_to_sv_no_handshake.sh accepts an optional sixth positional mode: bundled or pre-morty. Omitted mode is bundled.

- [ ] **Step 1: Write failing materializer tests**

In test_calyx_pre_morty_closure.py, construct a fake Calyx library tree containing all declared primitive and HardFloat filenames plus a generated top source. Assert the exact 22-entry source order and exact include order. Require generated top normalized_sha256 to differ only when the safe normalizer changes it; require every helper source normalized_sha256 to equal raw_sha256.

Assert the producer receipt binds all of these bytes and values:

~~~~python
required = {
    "raw_futil_sha256",
    "normalized_futil_sha256",
    "f32_constant_bits_sha256",
    "calyx_mlir_sha256",
    "calyx_executable_sha256",
    "calyx_argv",
    "normalizer_schema",
    "raw_generated_sv_sha256",
}
self.assertTrue(required <= set(receipt["provenance"]))
self.assertEqual(
    manifest["producer_receipt"]["sha256"],
    hashlib.sha256((out / "producer-receipt.json").read_bytes()).hexdigest(),
)
~~~~

Add failures for a missing named library file, an extra unlisted file, a changed staged byte, a symlink, a top mismatch, and an argv that lacks --emit-pre-morty.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_calyx_pre_morty_closure tests.test_calyx_export_normalization -v
~~~~

Expected: FAIL because the materializer and optional producer mode do not yet exist.

- [ ] **Step 3: Implement the materializer and producer receipt**

Use the shared closure library to write canonical source-closure data. The materializer has one literal ordered table, not directory enumeration:

~~~~python
CALYX_PRE_MORTY_SOURCES = (
    ("primitives/memories/seq.sv", "seq.sv"),
    ("primitives/float/mulFN.sv", "mulFN.sv"),
    ("primitives/float/intToFp.sv", "intToFp.sv"),
    ("primitives/float/fpToInt.sv", "fpToInt.sv"),
    ("primitives/float/divSqrtFN.sv", "divSqrtFN.sv"),
    ("primitives/float/compareFN.sv", "compareFN.sv"),
    ("primitives/float/addFN.sv", "addFN.sv"),
    ("primitives/core.sv", "core.sv"),
    ("primitives/binary_operators.sv", "binary_operators.sv"),
    ("primitives/float/HardFloat-1/source/HardFloat_primitives.v", "HardFloat_primitives.v"),
    ("primitives/float/HardFloat-1/source/HardFloat_rawFN.v", "HardFloat_rawFN.v"),
    ("primitives/float/HardFloat-1/source/addRecFN.v", "addRecFN.v"),
    ("primitives/float/HardFloat-1/source/compareRecFN.v", "compareRecFN.v"),
    ("primitives/float/HardFloat-1/source/divSqrtRecFN_small.v", "divSqrtRecFN_small.v"),
    ("primitives/float/HardFloat-1/source/fNToRecFN.v", "fNToRecFN.v"),
    ("primitives/float/HardFloat-1/source/iNToRecFN.v", "iNToRecFN.v"),
    ("primitives/float/HardFloat-1/source/isSigNaNRecFN.v", "isSigNaNRecFN.v"),
    ("primitives/float/HardFloat-1/source/mulRecFN.v", "mulRecFN.v"),
    ("primitives/float/HardFloat-1/source/recFNToFN.v", "recFNToFN.v"),
    ("primitives/float/HardFloat-1/source/recFNToIN.v", "recFNToIN.v"),
    ("primitives/float/HardFloat-1/source/RISCV/HardFloat_specialize.v", "HardFloat_specialize.v"),
)
~~~~

Write producer-receipt.json first, canonicalize and hash it, then record its relative path and SHA in closure.json to avoid a hash cycle. The receipt records both raw and normalized Futil hashes, the raw generated source hash, normalizer schema/file hash, f32 receipt hash, Calyx MLIR hash, executable hash, visible argument vector, and all staged library hashes.

- [ ] **Step 4: Add the separate script mode and Nix artifact**

Keep the current five positional arguments valid. Parse a sixth bundled or pre-morty mode and reject every other value. In the pre-morty branch, write raw output below pre-morty/pre-morty-calyx.sv, invoke the literal --emit-pre-morty flag, invoke the materializer, and publish a branch-specific manifest. It must not write sv/main.sv or root sources.f.

Define rcPolynomialExpPreMortySv beside rcPolynomialExpSv in flake.nix. It uses the same Circt export, normalized Futil, constant proof, Calyx library, and flags, but passes the explicit pre-morty mode. Expose only a new named package:

~~~~text
tinystories-w8a8-rc-polynomial-exp-calyx-native-pre-morty-sv
~~~~

Do not change nix/pipeline.nix, nix/models.nix, or the existing bundled rcPolynomialExpSv derivation.

- [ ] **Step 5: Verify producer isolation**

Run:

~~~~bash
python3 -m unittest tests.test_calyx_pre_morty_closure tests.test_calyx_export_normalization tests.test_calyx_float_nix_package -v
nix build .#tinystories-w8a8-rc-polynomial-exp-calyx-native-pre-morty-sv -L
git diff --check
~~~~

Expected: the new artifact publishes source-closure/closure.json and producer-receipt.json, while the existing bundled artifact contract is unchanged.

### Task 4: Teach strict Verilator equivalence to consume and stage the closure

**Files:**
- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_sv_source_closure.py
- Modify: tests/test_rc_sv_equivalence_fixture.py
- Modify: tests/test_rc_observable_driver.py

**Interfaces:**
- Strict CLI consumes --sv-filelist PATH --sv-root DIR --sv-closure-manifest PATH and rejects --sv.
- _verilator_codegen_command accepts an ordered list of staged source files plus ordered include/define/undefine flags.
- _memory_abi derives only from the validated unique raw main_1 source.

- [ ] **Step 1: Write the failing strict CLI and command-order tests**

Add tests that strict equivalence rejects each missing closure flag, every partial triple, and any legacy/mixed --sv invocation. Retain a non-strict fixture-only test proving --sv still works.

Add a Verilator command assertion:

~~~~python
command = module._verilator_codegen_command(
    args,
    [Path("/cache/sv/0000.sv"), Path("/cache/sv/0001.v")],
    Path("/cache/tb.sv"),
    Path("/cache/obj_dir"),
    3,
    include_dirs=[Path("/cache/sv/includes/00"), Path("/cache/sv/includes/01")],
    defines=[],
    undefines=["VERILATOR"],
    manifest_arguments=["--top-module", "tb"],
)
self.assertLess(command.index("-UVERILATOR"), command.index("/cache/sv/0000.sv"))
self.assertLess(command.index("/cache/sv/0000.sv"), command.index("/cache/sv/0001.v"))
self.assertLess(command.index("/cache/sv/0001.v"), command.index("/cache/tb.sv"))
~~~~

Also require main_1 in a non-first top source to work, and main_1 from include material to reject before ABI parsing.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_sv_source_closure tests.test_rc_sv_equivalence_fixture tests.test_rc_observable_driver -v
~~~~

Expected: FAIL because strict mode still accepts a single --sv file and code generation takes one path.

- [ ] **Step 3: Implement strict preflight and staged code generation**

Add the three parser arguments and enforce this truth table:

~~~~text
strict equivalence:  exactly all three closure flags; --sv absent
non-strict diagnostic: --sv present; closure triple absent
any partial or mixed form: parser error
~~~~

At strict preflight, load the closure once into an immutable in-memory snapshot, require top_module == main_1, and derive the ABI from its raw top source. Copy only snapshot bytes into work-dir/sv. Compile from an empty work-dir/compile-cwd and invoke Verilator with staged include directories, -UVERILATOR, staged top units in ordinal order, then tb.sv. Never reopen the external closure during compilation.

Replace the raw single-SV normalization block with closure staging. Aggregate raw and compiled source hashes domain-separately over ordinal, logical path, length, and bytes. Preserve legacy non-strict code generation through a one-member adapter.

- [ ] **Step 4: Run focused behavior tests**

Run:

~~~~bash
python3 -m unittest tests.test_rc_sv_source_closure tests.test_rc_sv_equivalence_fixture tests.test_rc_observable_driver -v
python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
~~~~

Expected: all strict CLI, ABI selection, normalizer, and Verilator-argument tests pass without a long model build.

- [ ] **Step 5: Checkpoint**

Inspect the exact command emitted by a synthetic strict fixture. It must list only cache-owned paths, two cache-owned include roots, -UVERILATOR, sources in ordinal order, then tb.sv.

### Task 5: Bind the closure through cache validation, results, and frozen reduction

**Files:**
- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_observable_driver.py
- Modify: tests/test_rc_sv_equivalence_fixture.py

**Interfaces:**
- Strict cache metadata schema is version 9 and contains a full validated sv_closure object.
- Strict result schema is rc-observable-verilator-shard-v4.
- Frozen summary schema is rc-observable-frozen-four-v4.

- [ ] **Step 1: Write failing cache mutation and reducer-identity tests**

Extend the existing synthetic strict-cache helper to create a two-source, two-include closure with a producer receipt. Mutate each item after compilation, including source bytes, include bytes, sources.f, closure.json, producer-receipt.json, source order, and macro policy. Recompute any attacker-controlled manifest/cache digest in the test and require run-only validation to reject before the simulator launches.

Add a frozen-reducer test whose outputs are otherwise identical but whose second receipt has a different producer receipt SHA or reordered source table:

~~~~python
changed = copy.deepcopy(sequential)
changed["sv_closure"]["producer_receipt"]["sha256"] = "f" * 64
with self.assertRaisesRegex(RuntimeError, "sv_closure differs"):
    module._frozen_four_summary(names, fresh, changed, proof_sha256)
~~~~

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_observable_driver tests.test_rc_sv_equivalence_fixture -v
~~~~

Expected: existing v3 scalar SV fields make these new closure mutations invisible or malformed.

- [ ] **Step 3: Implement v4 provenance and exact cache reconstruction**

Set:

~~~~python
STRICT_CACHE_SCHEMA_VERSION = 9
STRICT_RESULT_SCHEMA = "rc-observable-verilator-shard-v4"
FROZEN_FOUR_SCHEMA = "rc-observable-frozen-four-v4"
~~~~

Replace strict inputs.sv_sha256 with sv_closure_sha256, sv_filelist_sha256, sv_manifest_sha256, and sv_producer_receipt_sha256. Store the complete validated closure table in compile metadata, configuration identity, result/failure receipt, counterexample, and frozen reduction identity. Store source_closure_raw_sha256, source_closure_compiled_sha256, source_closure_manifest_sha256, and source_closure_producer_receipt_sha256 alongside existing fixture/binary/ABI/memory hashes.

Refactor strict expected-artifact reconstruction to stage a fresh closure snapshot into a temporary directory and byte-compare its exact tree with work-dir/sv: all numbered sources, include files, sources.f, closure.json, producer-receipt.json, and no extras or symlinks. Then retain the existing byte comparisons for tb.sv, memory-abi.json, external-memory-bindings.json, mem0.hex through mem45.hex, and the private binary/runtime snapshot. Cache metadata hashes remain integrity checks; fresh source reconstruction is the authorization check.

Make _strict_frozen_receipt_identity validate the canonical closure object, producer receipt hash, source tables, compiler aggregate hashes, and all existing ABI/binding/oracle fields. Make _frozen_four_summary compare that full reduced closure identity for every fresh and sequential receipt.

- [ ] **Step 4: Run strict receipt and cache tests**

Run:

~~~~bash
python3 -m unittest tests.test_rc_observable_driver tests.test_rc_sv_equivalence_fixture -v
python3 -m unittest discover -s tests -p 'test_rc_*' -v
python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
~~~~

Expected: every cache mutation fails before execution, while unmodified legacy non-strict tests and strict synthetic frozen receipts pass under v4.

- [ ] **Step 5: Checkpoint**

Run git diff --check. Inspect one emitted synthetic strict receipt: it must name a full sv_closure table rather than a single source hash.

### Task 6: Establish bundled-versus-direct behavioral parity on the float MRC corpus

**Files:**
- Create: scripts/pipeline/run_calyx_pre_morty_mrc_parity.py
- Create: diagnostics/rc-calyx-pre-morty-parity.nix
- Create: tests/test_rc_calyx_pre_morty_parity.py
- Modify: flake.nix
- Modify: reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.sv only if machine-readable lifecycle records are needed

**Interfaces:**
- The parity driver takes the eight existing MLIR MRCs, Circt tools, Calyx, the closure materializer, Verilator, and an output directory.
- It emits per-route durable transcripts and requires exact expected and observed words plus matching completion lifecycle across bundled and direct closures.
- The Nix package is named rc-calyx-pre-morty-parity.

- [ ] **Step 1: Write failing MRC-vector and transcript tests**

Define explicit integer bit-vector cases, never host-float calculations, for all existing MRC IDs:

~~~~python
MRC_CASES = {
    "addf-f32": ([0x3FC00000, 0x40100000], 0x40700000),
    "subf-f32": ([0x40600000, 0x3FC00000], 0x40000000),
    "mulf-f32": ([0x3FC00000, 0x40000000], 0x40400000),
    "divf-f32": ([0x40F00000, 0x40200000], 0x40400000),
    "cmpf-ugt-f32": ([0x40400000, 0x40000000], 0x1),
    "sitofp-i32-f32": ([0xFFFFFFF9], 0xC0E00000),
    "fptosi-f32-i8": ([0x40866666], 0x04),
    "uitofp-i1-f32": ([0x1], 0x3F800000),
}
~~~~

Test that the generated testbench resets for three cycles before every transaction, bounds completion, captures the appropriate generated memory output, and emits a normalized record containing MRC ID, input words, observed word, expected word, and cycles. Test the parser rejects missing records, mismatched expected/observed word, wrong ID/input, duplicate record, timeout, and lifecycle disagreement.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_calyx_pre_morty_parity -v
~~~~

Expected: FAIL because the direct/bundled parity driver does not exist.

- [ ] **Step 3: Implement a common behavioral parity driver**

For each MRC, lower once to Calyx MLIR and export Futil once. Emit the ordinary bundle with default Calyx flags and the raw design with --emit-pre-morty using the same synthesis/nested/papercut policy. Feed the raw design through the shared materializer; compile both routes using the same Verilator version, timing settings, testbench generator, and -UVERILATOR policy.

Persist per-route command, source closure identity, normalized transcript, return status, and each record. Require:

~~~~python
direct_records == bundled_records
all(record["observed"] == record["expected"] for record in direct_records)
all(record["completion_count"] == 1 for record in direct_records)
~~~~

Do not compare bundle bytes or timestamps. Retain the existing fptosi latency target as an independent regression rather than weakening it into parity-only evidence.

- [ ] **Step 4: Wire and run the Nix diagnostic**

Add diagnostics/rc-calyx-pre-morty-parity.nix and expose it in flake.nix. Supply all eight existing MRC files explicitly, no directory enumeration.

Run:

~~~~bash
python3 -m unittest tests.test_rc_calyx_pre_morty_parity tests.test_rc_calyx_hardfloat_bindings -v
nix build .#rc-calyx-fptosi-latency -L
nix build .#rc-calyx-pre-morty-parity -L
~~~~

Expected: the direct closure matches the default bundle for every declared MRC vector and preserves fptosi lifecycle behavior.

- [ ] **Step 5: Checkpoint**

Record the MRC receipt path and direct closure digest. Label it packaging/lifecycle parity only, not whole-RC functional equivalence.

### Task 7: Wire the named direct closure through the strict smoke and frozen-four gate

**Files:**
- Modify: diagnostics/rc-observable-equivalence.nix
- Modify: flake.nix
- Modify: tests/test_rc_observable_driver.py
- Modify: docs/superpowers/specs/2026-08-05-rc-pre-morty-source-closure-design.md

**Interfaces:**
- The strict diagnostic consumes preMortySv rather than bundled sv.
- strictBuild compiles the direct closure once; strictSmoke runs [0,1) from the verified cache; frozenFour performs the existing four fresh and one reset-separated sequential runs.
- New package names explicitly include pre-morty-source-closure.

- [ ] **Step 1: Write failing Nix-wiring assertions**

Add source-level assertions that diagnostics/rc-observable-equivalence.nix passes this exact closure triple to strictBuild and every run-only invocation:

~~~~text
--sv-filelist <preMortySv>/source-closure/sources.f
--sv-root <preMortySv>/source-closure
--sv-closure-manifest <preMortySv>/source-closure/closure.json
~~~~

Assert no strict invocation contains --sv. Assert the direct smoke depends on strictBuild and frozenFour depends on the smoke. Assert the existing heartbeat and Verilator configuration diagnostics remain on their legacy one-file inputs.

- [ ] **Step 2: Run the wiring tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_observable_driver tests.test_calyx_float_nix_package -v
nix eval .#packages.x86_64-linux.tinystories-w8a8-rc-pre-morty-source-closure-equivalence-build.drvPath --raw
~~~~

Expected: evaluation fails until the named producer and direct proof graph are exported.

- [ ] **Step 3: Implement the direct proof graph**

Change diagnostics/rc-observable-equivalence.nix to accept preMortySv and use its normalized Calyx MLIR, raw Futil, f32 constant-bit receipt, and closure triple. Add a strictSmoke derivation that copies strictBuild cache, runs the zeros oracle over [0,1), enables --verify-cache --run-only, and writes one v4 receipt.

In flake.nix, preserve rcPolynomialExpSv as the bundled output. Define a separate direct diagnostic object and export:

~~~~text
tinystories-w8a8-rc-pre-morty-source-closure-equivalence-build
tinystories-w8a8-rc-pre-morty-source-closure-equivalence-smoke
tinystories-w8a8-rc-pre-morty-source-closure-equivalence-frozen-four
~~~~

Do not silently repoint ambiguous legacy equivalence aliases. Add the existing normalizer-semantics package as an explicit input to direct strict build.

- [ ] **Step 4: Run the gate in dependency order**

Run:

~~~~bash
nix build .#tinystories-w8a8-rc-sv-normalizer-semantics -L
nix build .#tinystories-w8a8-rc-pre-morty-source-closure-equivalence-build -L
nix build .#tinystories-w8a8-rc-pre-morty-source-closure-equivalence-smoke -L
nix build .#tinystories-w8a8-rc-pre-morty-source-closure-equivalence-frozen-four -L
~~~~

Expected: smoke emits one genuine completion with exact six-code/argmax evidence; frozen-four accepts exactly four fresh v4 receipts and one ordered sequential-reset v4 receipt with one identical closure identity.

- [ ] **Step 5: Update the design status only with evidence**

If all preceding commands pass, update the design document status to implemented and record the exact package names/receipt paths. If any command fails, preserve its counterexample and leave the status as approved direction with the failed ladder rung named.

### Task 8: Resume closure-aware throughput, sharding, and complete coverage only after frozen-four passes

**Files:**
- Create: scripts/pipeline/merge_rc_observable_results.py
- Create: tests/test_rc_observable_results.py
- Modify: diagnostics/rc-observable-equivalence.nix
- Modify: flake.nix

**Interfaces:**
- make-plan receives a successful direct v4 throughput receipt and writes a canonical ordered half-open shard plan.
- merge validates only successful v4 direct-closure result receipts and returns coverage.complete only for [0, 1679616).

- [ ] **Step 1: Write failing plan and merge tests**

Create synthetic v4 results whose closure table, producer receipt, f32 proof, ABI, bindings, image, manifest, runner, fixture, cache configuration, and simulator identities all match. Test sorting, full coverage, a gap, overlap, duplicate range, failed receipt, mismatched closure source row, mismatched producer receipt, and stale f32 proof:

~~~~python
merged = results.merge_receipts([second, first], expected_total=6**8)
self.assertTrue(merged["coverage"]["complete"])
with self.assertRaisesRegex(ValueError, "closure identity"):
    results.merge_receipts([first, changed_closure], expected_total=6**8)
~~~~

Also test make-plan rejects a receipt with fewer than two completed contexts or absent throughput timing, and requires its source receipt to name the direct closure schema.

- [ ] **Step 2: Run the tests to verify RED**

Run:

~~~~bash
python3 -m unittest tests.test_rc_observable_results -v
~~~~

Expected: FAIL because no result merger/planner exists.

- [ ] **Step 3: Implement measured planning and fail-closed merging**

Use the existing strict generic fixture for a multi-record direct throughput probe. Record count, completed count, wall seconds, contexts per second, cycles per context extrema, direct closure identity, and exact input provenance. Make a plan with fixed integer ranges in lexical base-six order; no adaptive/globbed shard discovery.

The merger must require contiguous ranges beginning at zero and ending at 1679616, each with status pass and completed count equal to its range length. It must reject any mismatched validated v4 identity before summing statistics. Its complete receipt includes every shard path/digest, plan digest, coverage bounds, closure table/digest, and aggregate timing; it never treats an unmerged partial run as proof.

- [ ] **Step 4: Verify planner and merger wiring**

Run:

~~~~bash
python3 -m unittest tests.test_rc_observable_results tests.test_rc_observable_driver -v
python3 -m py_compile scripts/pipeline/merge_rc_observable_results.py
git diff --check
~~~~

Then run one measured direct multi-record probe and generate its plan. Do not start the all-domain launch if the frozen-four package from Task 7 did not pass.

- [ ] **Step 5: Execute the deterministic shard protocol**

After a passing frozen-four summary and an accepted measured plan, generate each matching PT2E oracle shard, run each direct strict SV shard from the verified compiled cache, and merge only the resulting v4 receipts. A successful terminal condition is a durable complete coverage receipt with start=0, stop=1679616, complete=true, and one invariant pre-Morty source-closure identity. A failed terminal condition is a durable counterexample or scalability receipt; do not claim functional equivalence from samples.

## Self-Review

### Spec coverage

- Explicit raw Calyx emission and no Morty dependency are implemented in Task 2.
- The exact ordered source/include/macro/normalizer contract and hash-bound producer receipt are implemented in Tasks 1 and 3.
- Strict runner staging, cache rejection, source provenance, and reducer identity are implemented in Tasks 4 and 5.
- Bundled-versus-direct behavioral validation precedes whole-RC evidence in Task 6.
- The frozen direct closure gate is named and isolated in Task 7.
- Throughput, deterministic shards, and exact [0, 1679616) coverage are resumed only after that gate in Task 8.

### Placeholder scan

This plan contains explicit file paths, interface names, schema names, source order, error classes, test cases, and verification commands. It deliberately makes no source-code change in a task before its focused test is run red.

### Type and contract consistency

The producer writes rc-sv-source-closure-v1 plus a hash-bound producer receipt; SourceClosure validates and stages that contract; strict runner receipts retain the same full sv_closure identity; the frozen reducer and final merger compare that identity rather than a scalar source hash.
