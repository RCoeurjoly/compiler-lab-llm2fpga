# RC Observable Equivalence Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the proven float-memory ABI misbinding and the independent `fptosi` latency bug, then obtain an evidence-backed pass for the frozen four-context PyTorch-to-SV gate.

**Architecture:** The strict fixture will derive a canonical external-memory binding receipt from exact `dense_resource` bytes in the source flat-SCF file and the ordered `memref.get_global` sequence in pre-Calyx MLIR. It will reject unsupported, stale, malformed, or ABI-incompatible inputs and materialize ports 27–45 exclusively from that receipt. Separately, CIRCT's `fptosi` lowering will wait for the registered Calyx primitive's `done` before latching its output, protected by a real MLIR→Calyx→SV→Verilator MRC.

**Tech Stack:** Python 3 stdlib, MLIR text and dense-resource payloads, Nix, CIRCT/MLIR, Calyx 0.7.1, SystemVerilog, Verilator.

## Global Constraints

- Preserve unrelated dirty/staged work; do not reset, clean, commit, or rewrite user changes in the shared `main` checkout.
- Use `apply_patch` for persistent edits; temporary experiments may live under `/tmp`.
- Strict equivalence remains fail-closed: no tolerance, output shortcut, simulator bypass, `--disable-verify`, or unproven source-name/shape ordering.
- Do not decode a textual f32 with Python/host floating point. Read f32 words only from validated `dense_resource` bytes; permit the current scalar port 27 only as exact `dense<0.000000e+00>`/`dense<0.0>` zero.
- Source and pre-Calyx f32 shapes must be either identical or an explicitly recorded contiguous flatten: the lowered shape is exactly `[product(source_shape)]`. Reject every other equal-element-count reshape; retain both shapes and the transform in the receipt.
- The binding receipt must retain exact hashes for flat-SCF, pre-Calyx MLIR, image, image manifest, and SV memory ABI; its canonical SHA must bind fixture compilation, cached run-only validation, and results. In run-only mode, the rebuilt receipt SHA, cached receipt, cached configuration SHA, cached artifact SHA, and `external-memory-bindings.json` bytes must all agree exactly. Every derivable fixture input actually consumed by the cached binary—normalized SV, testbench, ABI receipt, and `mem0.hex` through `mem45.hex`—must byte-match a fresh materialization from the current exact raw SV/image/manifest/ABI/binding receipt, rather than merely a mutable cache hash.
- Identical raw image payloads are recorded as sorted aliases, never presented as a fabricated unique source segment name.
- The `fpToInt.sv` primitive interface is unchanged. The minimal repair is only `FpToIntOpIEEE754` lowering; `IntToFpOpIEEE754` retains unconditional result-register write enable.
- Do not launch exhaustive `6^8` shards until the frozen-four strict target passes.

---

## File Structure

- Modify: `scripts/pipeline/run_rc_sv_equivalence.py` — build/validate the binding receipt, materialize float ports from it, carry it through strict cache/result provenance, and require the two source IR paths in strict mode.
- Modify: `tests/test_rc_sv_equivalence_fixture.py` — unit tests for raw-byte binding construction, materialization, aliases, rejection conditions, and CLI requirements.
- Modify: `tests/test_rc_observable_driver.py` — strict compile-identity/cache tests for binding receipt changes.
- Modify: `diagnostics/rc-observable-equivalence.nix` and `flake.nix` — pass the exact source flat-SCF and pre-Calyx MLIR artifacts to every strict compile/run invocation.
- Create: `reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.sv` — a four-case behavioral MRC testbench.
- Create: `diagnostics/rc-calyx-fptosi-regression.nix` — lower the MRC, emit Calyx SV, build/run Verilator, and write a pass receipt.
- Create: `patches/circt/0002-wait-for-fptosi-result.patch` — patch CIRCT lowering and its two FileCheck expectations.
- Modify: `flake.nix` — apply the CIRCT patch and expose the behavioral regression package.

### Task 1: Fail-closed external-memory binding receipt

**Files:**
- Modify: `tests/test_rc_sv_equivalence_fixture.py`
- Modify: `scripts/pipeline/run_rc_sv_equivalence.py`

**Interfaces:**
- Consumes: `flat_scf: bytes`, `pre_calyx: bytes`, `image: bytes`, parsed image `manifest: dict`, and `abi: dict[int, MemoryPort]`.
- Produces: `_build_calyx_memory_bindings(*, flat_scf, pre_calyx, image, manifest, abi) -> dict` and `_validate_calyx_memory_bindings_receipt(receipt: object) -> dict`.
- Receipt schema: `rc-calyx-external-memory-bindings-v1`, with canonical JSON and SHA-256. Each ordered row has `port`, `ordinal`, `global`, `source_shape`, `lowered_shape`, `shape_transform` (`identity` or `contiguous-flatten`), `word_count`, `words_u32`, `raw_sha256`, and `image_segment_aliases`.

- [ ] **Step 1: Write failing binding tests**

Add small text fixtures whose two-element zero/one resource globals are intentionally named and manifest-ordered opposite to their `memref.get_global` order. Assert the desired API produces port 29 words `[0x3f800000, 0x3f800000]` and port 30 words `[0, 0]`:

```python
receipt = module._build_calyx_memory_bindings(
    flat_scf=flat_scf.encode(), pre_calyx=pre_calyx.encode(),
    image=image, manifest=manifest, abi=abi,
)
rows = {row["port"]: row for row in receipt["ports"]}
self.assertEqual(rows[29]["words_u32"], [0x3F800000, 0x3F800000])
self.assertEqual(rows[30]["words_u32"], [0, 0])
self.assertEqual(rows[29]["image_segment_aliases"], ["state/one-a", "state/one-b"])
```

Add a positive regression for a source `memref<2x2xf32>` lowered only to `memref<4xf32>`; it must record `source_shape: [2, 2]`, `lowered_shape: [4]`, and `shape_transform: "contiguous-flatten"`. Add individual rejection tests for: malformed `0x04000000` resource framing; resource payload length not equal to `4 * element_count`; non-f32 global; unsupported inline nonzero decimal; missing/reordered `get_global`; unsupported source/pre-Calyx reshape (for example `[2]` to `[1, 2]`); missing byte-identical image segment; and a 32-bit ABI port with insufficient depth. Add a canonical/hash validation test that mutates a row after computing its canonical JSON.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m unittest tests.test_rc_sv_equivalence_fixture.RcSvEquivalenceFixtureTest.test_external_float_bindings_follow_get_global_order -v
```

Expected: FAIL because `_build_calyx_memory_bindings` does not exist (or because the current sorted-name mapping produces the zero/one reversal).

- [ ] **Step 3: Implement the minimal raw-byte builder and validator**

In `run_rc_sv_equivalence.py`:

```python
CALYX_MEMORY_BINDINGS_SCHEMA = "rc-calyx-external-memory-bindings-v1"

def _build_calyx_memory_bindings(*, flat_scf, pre_calyx, image, manifest, abi):
    source = flat_scf.decode("utf-8")
    lowered = pre_calyx.decode("utf-8")
    globals_by_symbol = _parse_flat_scf_f32_globals(source)
    ordered = _parse_pre_calyx_f32_get_globals(lowered)
    if len(ordered) != 19:
        raise RuntimeError("pre-Calyx must externalize exactly 19 f32 globals")
    rows = []
    for ordinal, (symbol, lowered_shape) in enumerate(ordered):
        port = 27 + ordinal
        raw = _source_global_raw_f32(globals_by_symbol[symbol])
        source_shape = globals_by_symbol[symbol]["shape"]
        source_count = math.prod(source_shape)
        if len(raw) != 4 * source_count:
            raise RuntimeError("source f32 shape disagrees with source bytes")
        if lowered_shape == source_shape:
            shape_transform = "identity"
        elif lowered_shape == [source_count]:
            shape_transform = "contiguous-flatten"
        else:
            raise RuntimeError("unsupported source/pre-Calyx f32 shape transform")
        abi_port = abi[port]
        if abi_port.width != 32 or abi_port.depth < len(raw) // 4:
            raise RuntimeError("SV ABI cannot hold external f32 global")
        aliases = _matching_image_f32_aliases(raw, image, manifest)
        if not aliases and port != 27:
            raise RuntimeError("external f32 global has no byte-identical image segment")
        rows.append({
            "port": port, "ordinal": ordinal, "global": symbol,
            "source_shape": source_shape, "lowered_shape": lowered_shape,
            "shape_transform": shape_transform, "word_count": len(raw) // 4,
            "words_u32": [int.from_bytes(raw[i:i + 4], "little")
                          for i in range(0, len(raw), 4)],
            "raw_sha256": _sha256_bytes(raw),
            "image_segment_aliases": aliases,
        })
    return _canonical_calyx_memory_bindings(rows, flat_scf, pre_calyx, image, manifest, abi)
```

`_parse_flat_scf_f32_globals` accepts only `dense_resource<RESOURCE>` f32 declarations plus the port-27 scalar `dense<0.000000e+00>`/`dense<0.0>`. `_source_global_raw_f32` rejects any resource whose decoded bytes do not begin with `b"\x04\x00\x00\x00"` or whose length is not four framing bytes plus `4 * product(shape)`. `_matching_image_f32_aliases` accepts only state/float32 manifest segments with exact raw bytes and returns names in lexical order. Replace the sorted candidate loop in `_materialize_fixture_memories` with a required validated binding receipt and write `mem27.hex` through `mem45.hex` from each row's `words_u32`.

- [ ] **Step 4: Run focused tests and the fixture module**

Run:

```bash
python3 -m unittest tests.test_rc_sv_equivalence_fixture -v
python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
```

Expected: all fixture tests pass, including the zero/one reversal and every rejection test.

- [ ] **Step 5: Checkpoint**

Do not commit the shared dirty checkout. Record changed paths and test output in the SDD ledger.

### Task 2: Bind the receipt to strict compile/run provenance

**Files:**
- Modify: `tests/test_rc_observable_driver.py`
- Modify: `tests/test_rc_sv_equivalence_fixture.py`
- Modify: `scripts/pipeline/run_rc_sv_equivalence.py`
- Modify: `diagnostics/rc-observable-equivalence.nix`
- Modify: `flake.nix`

**Interfaces:**
- Strict CLI consumes required `--flat-scf PATH` and `--pre-calyx PATH`.
- `_compile_identity(args, *, f32_constant_bits_sha256, calyx_memory_bindings_sha256) -> dict` includes the binding SHA.
- Strict cache metadata (new schema version) and receipts contain the validated `calyx_memory_bindings` object.

- [ ] **Step 1: Write failing strict-cache and CLI tests**

Extend strict test argument fixtures with `flat_scf` and `pre_calyx`. Add a test that changes one binding row/hash while keeping SV/image/manifest constant and requires cache rejection:

```python
self.assertNotEqual(
    module._compile_identity(args, f32_constant_bits_sha256="a" * 64,
                             calyx_memory_bindings_sha256="b" * 64),
    module._compile_identity(args, f32_constant_bits_sha256="a" * 64,
                             calyx_memory_bindings_sha256="c" * 64),
)
```

Add a CLI test that strict mode rejects missing `--flat-scf` or `--pre-calyx`, and assert generated `tb.sv`, `external-memory-bindings.json`, compile metadata, and strict result receipt share the binding SHA.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m unittest tests.test_rc_observable_driver tests.test_rc_sv_equivalence_fixture -v
```

Expected: FAIL because strict mode has no source-IR CLI arguments or binding identity.

- [ ] **Step 3: Implement strict integration**

During strict preflight, read and hash both IR files, build and validate one receipt against `_memory_abi(raw_sv)`, and write its canonical JSON to `external-memory-bindings.json`. Pass it into `_strict_fixture`; embed its SHA in the fixture's localparams. Include the receipt in `_strict_receipt_base`, `_strict_failure_receipt_base`, compiled metadata, and the strict cache artifact validation. Bump `STRICT_FIXTURE_SCHEMA` and cache metadata schema version.

Require both flags only in strict mode. Extend `_input_hashes` for strict inputs and make run-only rebuild/validate the receipt before accepting cached metadata. Fail if the cached configuration/artifact binding SHA differs from that rebuilt receipt SHA, or if the cached binding file bytes are not exactly the rebuilt receipt's canonical JSON. In a temporary directory, regenerate the deterministic strict fixture from current exact inputs and byte-compare normalized SV, testbench, ABI receipt, and all loaded memory files before executing a cached binary. In `diagnostics/rc-observable-equivalence.nix`, pass the exact flat artifact and `${calyx}/pre-calyx.mlir` to compile and all run-only calls. In `flake.nix`, pass the source flat-SCF derivation and `rcPolynomialExpCalyx` into that diagnostic import.

- [ ] **Step 4: Run Python and Nix wiring checks**

Run:

```bash
python3 -m unittest tests.test_rc_observable_driver tests.test_rc_sv_equivalence_fixture -v
python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
git diff --check
nix eval .#packages.x86_64-linux.tinystories-w8a8-rc-observable-equivalence-build.drvPath --raw
```

Expected: all tests pass, no whitespace errors, and Nix evaluation names every required artifact.

- [ ] **Step 5: Checkpoint**

Do not commit the shared dirty checkout. Record changed paths and test output in the SDD ledger.

### Task 3: Behavioral `fptosi` latency regression (RED)

**Files:**
- Create: `reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.sv`
- Create: `diagnostics/rc-calyx-fptosi-regression.nix`
- Modify: `flake.nix`

**Interfaces:**
- The testbench instantiates generated top `main`, drives its two memories, and fails nonzero unless each signed f32 input converts toward zero to the expected i8 result.
- The Nix package `rc-calyx-fptosi-latency` runs CIRCT lowering, `circt-translate --export-calyx`, Calyx SV generation, `verilator --binary --timing --top-module tb`, then `obj_dir/Vtb`.

- [ ] **Step 1: Write the behavioral MRC and Nix target**

Create a testbench with four independent reset/launch cases:

```systemverilog
run_case(32'h40866666, 8'sd4,    "plus_4_2");
run_case(32'hbfd9999a, -8'sd1,  "minus_1_7");
run_case(32'h42fe0000, 8'sd127, "plus_127");
run_case(32'hc3000000, -8'sd128,"minus_128");
```

Each case writes `dut.mem_0.mem[0]`, releases reset, asserts `go`, waits for `done`, and calls `$fatal(1, ...)` if `$signed(dut.mem_1.mem[0])` differs. The target must emit `result.json` only after `Vtb` exits zero.

- [ ] **Step 2: Run the target against the current CIRCT and verify RED**

Run:

```bash
nix build .#rc-calyx-fptosi-latency -L
```

Expected: FAIL with at least `plus_4_2` observing `0` rather than `4`; retain the failed transcript under `/tmp` or the Nix log as evidence.

- [ ] **Step 3: Add the minimal CIRCT patch**

Create `patches/circt/0002-wait-for-fptosi-result.patch`. In `buildFpIntTypeCastOp`:

```c++
calyx::AssignOp::create(rewriter, loc, reg.getIn(), calyxOp.getOut());
if constexpr (std::is_same_v<TCalyxLibOp, calyx::FpToIntOpIEEE754>)
  calyx::AssignOp::create(rewriter, loc, reg.getWriteEn(), calyxOp.getDone());
else
  calyx::AssignOp::create(rewriter, loc, reg.getWriteEn(), c1);
```

`TCalyxLibOp` is a concrete template type, so a runtime `dyn_cast` cannot represent the non-`FpToInt` instantiation. The compile-time branch is the minimal type-correct expression of the same lowering contract.

Update `test/Conversion/SCFToCalyx/convert_simple.mlir` and `test/Dialect/Calyx/emit.mlir` expectations so `fptosi_0_reg.write_en` is `%std_fpToIntFN_0.done` / `std_fptointFN_0.done`, while the integer-to-float expectations remain `true`. Append the patch after `0001-export-calyx-float-constants-as-raw-bits.patch` in `flake.nix`.

- [ ] **Step 4: Run the MRC and structural tests (GREEN)**

Run:

```bash
nix build .#rc-calyx-fptosi-latency -L
nix build .#circt -L
```

Expected: the MRC prints/records all four expected conversions and CIRCT's patched source builds.

- [ ] **Step 5: Checkpoint**

Do not commit the shared dirty checkout. Record the exact CIRCT patch SHA, MRC target output, and source-test changes in the SDD ledger.

### Task 4: Rebuild evidence and run the frozen four gate

**Files:**
- No new source files unless a test exposes a concrete defect in Tasks 1–3.

**Interfaces:**
- `tinystories-w8a8-rc-observable-equivalence-build` produces a cache whose metadata includes matching f32 proof, binding receipt, memory ABI, fixture, normalized SV, and runtime-memory hashes.
- `tinystories-w8a8-rc-observable-equivalence-frozen-four` is the sole gate for the four fresh contexts plus one ordered reset sequence.
- The gate accepts exactly one DUT completion per case. Its reducer must compare cycles and the complete strict provenance identity (source/input hashes, f32 proof, binding receipt, ABI, fixture/configuration/cache identity) across each fresh and sequential case. A reducer failure must write a durable `counterexample.json` carrying the fresh/sequential evidence; per-run simulation-result counterexamples must carry binding, ABI, and cache hashes directly.

- [ ] **Step 1: Run the fast artifact-level strict fixture generation**

Run:

```bash
nix build .#tinystories-w8a8-rc-observable-equivalence-build -L
```

Inspect the generated `external-memory-bindings.json` and `mem29.hex`/`mem30.hex`; require exact one/zero ordering before a large Verilator rebuild.

- [ ] **Step 2: Run the frozen four gate**

Run:

```bash
nix build .#tinystories-w8a8-rc-observable-equivalence-frozen-four -L
```

Expected: `summary.json` status `pass`, all six raw i8 codes equal, lowest-index argmax equal, six output lanes written, one completion per case, and ordered-reset evidence equal to fresh runs.

- [ ] **Step 3: If the gate fails, preserve and diagnose rather than weaken it**

Read the produced `counterexample.json`; use its binding receipt, f32 proof, ABI, runtime memory hash, and transcript to isolate the next boundary. Do not amend output expectations or skip a lifecycle assertion.

- [ ] **Step 4: Completion audit**

Run:

```bash
python3 -m unittest tests.test_rc_sv_equivalence_fixture tests.test_rc_observable_driver -v
git diff --check
```

Only after this task passes may the all-`6^8` sharding/merged-manifest plan resume.
