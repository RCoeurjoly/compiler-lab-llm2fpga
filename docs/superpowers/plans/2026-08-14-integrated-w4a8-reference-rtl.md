# Integrated W4A8 Reference RTL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Produce and qualify one reproducible compiler-generated SystemVerilog design whose single invocation performs the frozen W4A8 prefill and two cached greedy-decode phases exactly against PyTorch/PT2E.

**Architecture:** A new integrated PyTorch module owns the complete prompt-to-three-phase dataflow, including tensor-cache continuity and lowest-index argmax feedback. It is exported once as one PT2E ExportedProgram, lowered once through the existing Calyx-native-SV route, exposed through a generated narrow transaction/readback shell, and simulated as one continuously executing RTL instance. Existing phase graphs and RTL are never composed into it; phase observations and qparams remain the frozen numerical oracle.

**Tech Stack:** Python 3, PyTorch/PT2E torch.export, Hugging Face Transformers, Nix, MLIR/Calyx, SystemVerilog, Verilator, pytest, JSON receipts, GNU time.

## Global Constraints

- Target the frozen V=6, width-2, two-layer, one-head, prompt-length-8 W4A8 representative core and prefill-8, decode-8, and decode-9 semantics.
- One accepted RTL transaction performs all three phases in one RTL instance. Host orchestration and three-SV composition do not qualify.
- The canonical export is exactly one ExportedProgram and one behavioral generated design beneath the narrow ABI shell.
- Decode caches and tokens come from the preceding computation in the same invocation. Argmax uses lowest-index tie breaking.
- Prompt tokens are runtime-loadable. Weights and inference state remain on chip. DDR3 is excluded.
- Tokens, raw logits, and all four flattened cache leaves are observable at every phase boundary.
- /tmp is scratch only. Authoritative programs, RTL, manifests, vectors, receipts, and logs are Nix outputs with hashes.
- Semantics-preserving exporter/lowering repairs require focused red-green regression tests.
- Yosys, nextpnr-xilinx, formal proof, manual optimization, and board execution are outside this plan.
- Preserve unrelated dirty files, including TinyStories/rc_serving_direct_export.py and survey/.

---

## File map

- TinyStories/rc_serving_w4a8_integrated_contract.py: observation schema, readback map, validation, and JSON serialization.
- TinyStories/rc_serving_w4a8_integrated.py: eager stateful module, integrated PT2E export, exact comparison, and bundle materialization.
- scripts/pipeline/materialize_rc_serving_w4a8_integrated.py: bundle CLI.
- nix/rc-serving-w4a8-integrated-system.nix: integrated reference, export, SV, and equivalence derivations.
- scripts/pipeline/generate_rc_serving_w4a8_integrated_shell.py: narrow ABI shell generation.
- scripts/pipeline/run_rc_serving_w4a8_integrated_sv.py: Verilator comparison and reset/reuse campaign.
- tests/test_rc_serving_w4a8_integrated_*.py: focused contract, export, Nix, shell, and simulation tests.
- flake.nix: public package registration without extending the phase registry.
- docs/results/2026-08-14-integrated-w4a8-reference-rtl.md: qualification report.

---

### Task 1: Freeze the integrated observation and readback contract

**Files:**
- Create: TinyStories/rc_serving_w4a8_integrated_contract.py
- Create: tests/test_rc_serving_w4a8_integrated_contract.py

**Interfaces:**
- Consumes: PHASE_NAMES and tensor records from TinyStories.rc_serving_w4a8_contract.
- Produces: OBSERVATION_SCHEMA, IntegratedObservation, build_readback_manifest, validate_readback_manifest, and write_integrated_observation.

- [ ] **Step 1: Write failing deterministic-address tests**

~~~python
def test_readback_manifest_is_dense_and_phase_ordered():
    shapes = {
        name: {"token": [], "logits": [6], "cache": [[2, 1, n, 1]] * 4}
        for name, n in (("prefill-8", 8), ("decode-8", 9), ("decode-9", 10))
    }
    manifest = contract.build_readback_manifest(shapes)
    assert [w["address"] for w in manifest["words"]] == list(range(len(manifest["words"])))
    assert [r["phase"] for r in manifest["regions"]] == list(contract.PHASE_NAMES)
    assert manifest["argmax_tie_break"] == "lowest-index"
~~~

Also remove one cache leaf and assert validate_readback_manifest raises ValueError containing four cache leaves.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated_contract.py**

Expected: FAIL because the contract module is absent.

- [ ] **Step 3: Implement the contract**

Define immutable schema names ending in -v1 and:

~~~python
@dataclass(frozen=True)
class IntegratedObservation:
    prompt_token_ids: Sequence[int]
    phase_tokens: tuple[int, int, int]
    phase_logits: tuple[Sequence[int], Sequence[int], Sequence[int]]
    phase_cache_leaves: Sequence[Sequence[torch.Tensor]]
~~~

Assign dense addresses in PHASE_NAMES order; within a phase use token, vocabulary-indexed logits, then cache leaves 0..3 in row-major order. Record width, signedness, shape, phase, kind, leaf, and flat index. Require prompt length 8, vocabulary length 6, four cache leaves, sequence lengths 8/9/10, and lowest-index argmax.

Implement build_readback_manifest(phase_shapes) to return the complete manifest,
validate_readback_manifest(raw) to return None or raise ValueError, and
write_integrated_observation(path, observation, manifest) to validate first and
then write sorted, indented JSON with a trailing newline.

- [ ] **Step 4: Run pytest -q tests/test_rc_serving_w4a8_integrated_contract.py tests/test_rc_serving_w4a8_contract.py**

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add TinyStories/rc_serving_w4a8_integrated_contract.py tests/test_rc_serving_w4a8_integrated_contract.py
git commit -m "feat: freeze integrated W4A8 observation contract"
~~~

---

### Task 2: Build one eager stateful module and compare every boundary

**Files:**
- Create: TinyStories/rc_serving_w4a8_integrated.py
- Create: tests/test_rc_serving_w4a8_integrated.py

**Interfaces:**
- Consumes: build_w4a8_source_model, flatten_dynamic_cache, reconstruct_dynamic_cache, frozen trace, and Task 1 types.
- Produces: IntegratedW4A8Module, run_integrated_eager returning IntegratedObservation, and assert_integrated_observation_equal.

- [ ] **Step 1: Write failing token-feedback and cache-continuity tests**

Use a recording model with tied maxima and unique cache sentinels. Assert the three seen inputs are prompt, token 1, token 2; the seen cache sentinels are None, 8, 9; and the flat output has 18 tensors: three tokens plus three groups of logits and four cache leaves.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated.py -k 'feedback or continuity'**

Expected: FAIL because the integrated module is absent.

- [ ] **Step 3: Implement the complete eager forward**

IntegratedW4A8Module.forward(prompt) makes exactly three model calls with use_cache=True. For each, select logits[:, -1, :], compute torch.argmax along vocabulary with keepdim=True, flatten four returned cache leaves, and pass those returned tensors into the next call through reconstruct_dynamic_cache.

Return exactly:

~~~text
token_8, token_9, token_10,
logits_8, cache8_leaf0, cache8_leaf1, cache8_leaf2, cache8_leaf3,
logits_9, cache9_leaf0, cache9_leaf1, cache9_leaf2, cache9_leaf3,
logits_10, cache10_leaf0, cache10_leaf1, cache10_leaf2, cache10_leaf3
~~~

Do not insert recorded tokens or cache tensors between calls.

- [ ] **Step 4: Add the real frozen-trace differential test**

Run the integrated eager module and existing ordered three-phase source reference under torch.no_grad(). Compare prompt, all token IDs, every raw last-token logit, and every cache tensor using torch.equal. Diagnostics name phase, tensor, shape, and first flat mismatch.

Run: pytest -q tests/test_rc_serving_w4a8_integrated.py

Expected: PASS, or a durable numerical mismatch that blocks Task 3 without changing expected data.

- [ ] **Step 5: Commit**

~~~bash
git add TinyStories/rc_serving_w4a8_integrated.py tests/test_rc_serving_w4a8_integrated.py
git commit -m "feat: add integrated W4A8 eager serving oracle"
~~~

---

### Task 3: Export exactly one integrated PT2E program

**Files:**
- Modify: TinyStories/rc_serving_w4a8_integrated.py
- Modify: tests/test_rc_serving_w4a8_integrated.py
- Create: scripts/pipeline/materialize_rc_serving_w4a8_integrated.py

**Interfaces:**
- Consumes: Task 2 module and accepted W4/A8 quantizer definitions.
- Produces: convert_integrated_w4a8_program returning one ExportedProgram and materialize_integrated_bundle.

- [ ] **Step 1: Write failing export tests**

Assert materialization writes exactly one root exported.pt2, observation.json, readback-manifest.json, graph.txt, and receipt.json. Assert no phase subdirectory contains exported.pt2. Load the program and require 18 tensor outputs.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated.py -k export**

Expected: FAIL because conversion is absent.

- [ ] **Step 3: Implement integrated capture, calibration, conversion, and save**

Capture and convert IntegratedW4A8Module as one graph using the accepted W4-weight/A8-activation quantizer. Calibrate with the frozen prompt. The receipt records program and graph SHA-256, model/trace hashes, PyTorch version, quantizer configuration, output order, and exported_program_count equal to 1.

If integrated conversion derives qparams different from the frozen phase oracle, seed corresponding observers from recorded phase qparams and assert every scale/zero point. Never alter expected numerical outputs.

- [ ] **Step 4: Add the exact PT2E gate**

Compare all 18 converted outputs with the frozen three-phase W4A8 PT2E oracle,
canonicalizing cache leaves by semantic path. Save and reload the one integrated
program, then compare its outputs exactly with the accepted converted eager
execution. Do not compare quantized tensors with Task 2's unquantized FP32
tensors. Inspect graph dataflow to require argmax/cache outputs feed later
model-call inputs and are not lifted constants.

Run: pytest -q tests/test_rc_serving_w4a8_integrated.py

Expected: PASS.

- [ ] **Step 5: Add and validate the CLI**

The CLI accepts --model-path, --trace, and --out-dir; refuses an existing output directory; calls materialize_integrated_bundle; and prints the bundle path.

Run: python -m py_compile TinyStories/rc_serving_w4a8_integrated.py scripts/pipeline/materialize_rc_serving_w4a8_integrated.py

Expected: exit 0.

- [ ] **Step 6: Commit**

~~~bash
git add TinyStories/rc_serving_w4a8_integrated.py scripts/pipeline/materialize_rc_serving_w4a8_integrated.py tests/test_rc_serving_w4a8_integrated.py
git commit -m "feat: export one integrated W4A8 serving program"
~~~

---

### Task 4: Make the integrated artifacts reproducible Nix outputs

**Files:**
- Create: nix/rc-serving-w4a8-integrated-system.nix
- Create: tests/test_rc_serving_w4a8_integrated_nix.py
- Modify: flake.nix

**Interfaces:**
- Consumes: frozen model/trace packages and Task 3 CLI.
- Produces: rc-serving-w4a8-integrated-reference and rc-serving-w4a8-integrated-pytorch-exported packages.

- [ ] **Step 1: Write failing Nix-wiring tests**

Assert the new Nix system invokes the integrated materializer, exposes one export package, hashes frozen inputs, and never consumes prefill8PytorchExported, decode8PytorchExported, decode9PytorchExported, or rcServingW4A8Registry.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated_nix.py**

Expected: FAIL because the system is absent.

- [ ] **Step 3: Implement reference and export derivations**

Pass model and trace store paths explicitly; set preferLocalBuild=true and allowSubstitutes=false. Install observations, manifest, graph, program, and receipts. Never copy from /tmp.

- [ ] **Step 4: Verify**

~~~bash
pytest -q tests/test_rc_serving_w4a8_integrated_nix.py
nix eval .#packages.x86_64-linux.rc-serving-w4a8-integrated-pytorch-exported.name
nix build -L .#rc-serving-w4a8-integrated-pytorch-exported
~~~

Expected: tests PASS; build exits 0; result/receipt.json records one export and passing eager/PT2E gates.

- [ ] **Step 5: Commit**

~~~bash
git add nix/rc-serving-w4a8-integrated-system.nix tests/test_rc_serving_w4a8_integrated_nix.py flake.nix
git commit -m "build: package integrated W4A8 reference export"
~~~

---

### Task 5: Lower the one program wholesale to one generated SV design

**Files:**
- Modify: nix/rc-serving-w4a8-integrated-system.nix
- Modify: tests/test_rc_serving_w4a8_integrated_nix.py
- Modify when a defect is reproduced: smallest relevant scripts/pipeline helper and focused test
- Modify: flake.nix

**Interfaces:**
- Consumes: Task 4 exported.pt2 and existing flat-SCF, Calyx, normalization, and native-SV stages.
- Produces: rc-serving-w4a8-integrated-flat-scf, rc-serving-w4a8-integrated-calyx, and rc-serving-w4a8-integrated-calyx-native-sv.

- [ ] **Step 1: Extend failing wiring tests**

Require one model key, one source program, the three named stages, no PHASE_NAMES map, and store-path chaining from each stage to the next.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated_nix.py**

Expected: FAIL because lowering stages are absent.

- [ ] **Step 3: Register one route and build in order**

~~~bash
nix build -L .#rc-serving-w4a8-integrated-flat-scf
nix build -L .#rc-serving-w4a8-integrated-calyx
nix build -L .#rc-serving-w4a8-integrated-calyx-native-sv
~~~

Keep verbose output in Nix logs. Record store path, closure hash, wall time, peak RSS when available, and failure stage.

- [ ] **Step 4: Repair only reproduced lowering defects**

For each failure, first add a minimal fixture reproducing the exact invalid IR/SV or mismatch, observe its focused test fail, apply the smallest semantics-preserving repair, rerun the test, then restart the failed stage. Do not bypass operations, insert constants, split the export, or instantiate phase closures.

- [ ] **Step 5: Verify single-design invariants**

Require exported_program_count=1, one Calyx entry component, one behavioral generated top, all stage hashes, and no phase store paths. Run git diff --check and all focused tests for modified helpers.

- [ ] **Step 6: Commit only scoped files**

~~~bash
git add flake.nix nix/rc-serving-w4a8-integrated-system.nix tests/test_rc_serving_w4a8_integrated_nix.py
git commit -m "feat: lower integrated W4A8 reference to SystemVerilog"
~~~

Add any demonstrated helper repair and its focused test explicitly after inspecting git status --short.

---

### Task 6: Generate the narrow public RTL shell

**Files:**
- Create: scripts/pipeline/generate_rc_serving_w4a8_integrated_shell.py
- Create: tests/test_rc_serving_w4a8_integrated_shell.py
- Modify: nix/rc-serving-w4a8-integrated-system.nix

**Interfaces:**
- Consumes: Task 1 manifest and Task 5 behavioral SV.
- Produces: generate_shell(manifest, generated_top) and reference-top.sv module rc_serving_w4a8_integrated_reference.

- [ ] **Step 1: Write failing shell tests**

Require clock, reset, prompt index/data/write, go, busy, done, protocol_error, readback address/request, response-valid, and response-data ports. Require sticky protocol_error for prompt writes while busy, duplicate indices, early/concurrent go, and out-of-range reads.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated_shell.py**

Expected: FAIL because the generator is absent.

- [ ] **Step 3: Implement deterministic shell generation**

Generate synthesizable SV with an eight-bit prompt-written mask, one active transaction, stable completed observation storage, and one-cycle read response. Connect arrays using the compiler interface manifest. The shell performs protocol adaptation only: no phase scheduling, cache copying, argmax, or arithmetic. Reject missing or duplicate port mappings. Record shell/manifest hashes.

- [ ] **Step 4: Verify**

Run the shell tests, rebuild the native-SV package, and run Verilator lint on reference-top.sv plus closure sources. Expected: one resolved public top and no fatal width/latch/module errors.

- [ ] **Step 5: Commit**

~~~bash
git add scripts/pipeline/generate_rc_serving_w4a8_integrated_shell.py tests/test_rc_serving_w4a8_integrated_shell.py nix/rc-serving-w4a8-integrated-system.nix
git commit -m "feat: expose integrated W4A8 RTL transaction ABI"
~~~

---

### Task 7: Verify one continuous RTL invocation and reset reuse

**Files:**
- Create: scripts/pipeline/run_rc_serving_w4a8_integrated_sv.py
- Create: tests/test_rc_serving_w4a8_integrated_sv.py
- Modify: nix/rc-serving-w4a8-integrated-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: Task 6 public top, manifest, and Task 3 vectors.
- Produces: rc-serving-w4a8-integrated-sv-equivalence with receipt.json, run.log, build.log, and hashes.

- [ ] **Step 1: Write failing runner tests**

With a tiny compatible fixture, require reset→A→go→read, reset→B→go→read, reset→A→go→read. Reject missing/duplicate words, signed-decoding errors, any phase/cache mismatch, protocol_error, cycle-bound violation, and A-after-B differing from fresh A.

- [ ] **Step 2: Run pytest -q tests/test_rc_serving_w4a8_integrated_sv.py**

Expected: FAIL because the runner is absent.

- [ ] **Step 3: Implement the quiet public-port runner**

Accept --sv-closure, --manifest, --vectors, --out-dir, and --max-cycles. Compile once, drive only public ports, await done, read every address, and compare raw integers. Redirect progress to logs. GNU time -v records build/run wall time and peak RSS. Receipt fields include run cycles, mismatch/success, reset order, tool versions, commands, and hashes.

- [ ] **Step 4: Verify**

~~~bash
pytest -q tests/test_rc_serving_w4a8_integrated_sv.py tests/test_rc_serving_w4a8_integrated_shell.py
nix build -L .#rc-serving-w4a8-integrated-sv-equivalence
~~~

Expected: unit tests PASS. The Nix build exits 0 only when all phase tokens, logits, caches, and A/B/A reset isolation match. Any failure remains a durable receipt and blocks qualification.

- [ ] **Step 5: Commit**

~~~bash
git add scripts/pipeline/run_rc_serving_w4a8_integrated_sv.py tests/test_rc_serving_w4a8_integrated_sv.py nix/rc-serving-w4a8-integrated-system.nix flake.nix
git commit -m "test: verify integrated W4A8 RTL against PT2E"
~~~

---

### Task 8: Publish and audit qualification evidence

**Files:**
- Create: docs/results/2026-08-14-integrated-w4a8-reference-rtl.md
- Modify only if terminology changes: CONTEXT.md and docs/glossary.md

**Interfaces:**
- Consumes: accepted Nix paths and receipts from Tasks 1–7.
- Produces: durable qualification or blocker report.

- [ ] **Step 1: Write the report from receipts**

Record model/trace/export/SV hashes, one-program/top evidence, ABI, observation shapes/counts, eager/PT2E/RTL results, A/B/A reset result, cycles, wall times, peak RSS, tools, store paths, and lowering repairs.

Include this boundary:

~~~text
static W8A8 RTL: one non-cached forward design
existing W4A8 phase RTL: three independently verified phase designs
new W4A8 reference RTL: one stateful integrated design, only if every gate passed
~~~

If a gate failed, mark the result unqualified and name the blocker.

- [ ] **Step 2: Run the final audit**

~~~bash
pytest -q tests/test_rc_serving_w4a8_integrated_contract.py tests/test_rc_serving_w4a8_integrated.py tests/test_rc_serving_w4a8_integrated_nix.py tests/test_rc_serving_w4a8_integrated_shell.py tests/test_rc_serving_w4a8_integrated_sv.py
nix build -L .#rc-serving-w4a8-integrated-sv-equivalence
git diff --check
~~~

Inspect result/receipt.json and require passing eager_equivalence, pt2e_equivalence, single_export, single_generated_design, rtl_equivalence, and reset_reuse before calling it qualified.

- [ ] **Step 3: Commit the report**

~~~bash
git add docs/results/2026-08-14-integrated-w4a8-reference-rtl.md
git commit -m "docs: qualify integrated W4A8 reference RTL"
~~~

Inspect git status --short and add terminology files only when intentionally changed.
