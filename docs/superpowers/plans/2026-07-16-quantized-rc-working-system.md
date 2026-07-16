# Quantized Representative-Core Working-System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Turn the fixed V=6 PT2E W8A8 TinyStories representative core into a reproducible, equivalence-tested working system through generated SV, packed external memory, the proven DDR3/PCIe transport, and a deterministic host tokenizer.

**Architecture:** The plan adds one stable RC contract shared by five gates. Gate 1 validates actual generated SV against PT2E. Gate 2 changes only immutable tensor storage to a manifest-backed image fixture. Gate 3 audits and pins the existing LLM2FPGA/UberDDR3 transport, Gate 4 attaches the proven transport to the RC and validates the board, and Gate 5 adds host text/control without changing the oracle. Each gate consumes the prior gate’s immutable reference/image artifacts and produces one machine-readable result.

**Tech Stack:** Python 3.11, PyTorch ExportedProgram/PT2E XNNPACK W8A8, Torch-MLIR, MLIR/CIRCT/Calyx, SystemVerilog, Verilator, Nix flakes, Yosys/nextpnr-xilinx side reports, UberDDR3, existing LLM2FPGA PCIe loader.

## Global Constraints

- The DUT is exactly the already measured `tinystories-w8a8-rc-study-mask9-vocab6-width2` export: vocabulary 6, two layers, max positions 9, context 8, window 256, hidden width 2, one head, seed 0. `tinystories-w8a8-rc-working` is a human-facing package alias only; it must resolve to that existing export, never rebuild a look-alike model.
- The frozen PT2E W8A8 export is the oracle. Compare final-position six int8 codes, output qparams, dequantized logits, and lowest-index argmax token ID. Do not require equality to FP32 eager output.
- Gate 1 begins with the direct Linalg/no-Handshake lane. Do not add TOSA or approximate math rewrites to an equivalence result.
- The image fixture is an external-memory regression fixture only. Do not call it DDR3 simulation or DDR3 validation.
- Preserve all values, byte order, qparams, read/write ordering, and errors across externalization. Do not blackbox memories or manufacture read data.
- Use Nix derivations or checked-in fixtures for every durable artifact. Do not use a mutable temporary directory as an artifact handoff.
- Pin LLM2FPGA and UberDDR3 as immutable flake inputs before compiling board integration. Do not use the dirty local checkouts as build inputs.
- Board programming, PCIe access, and other physical hardware mutation require explicit user approval immediately before execution. Producing a bitstream and a dry-run board command is in scope before that approval.
- Keep existing staged changes outside this plan untouched. Every commit command below names only files created or changed by its task.

## File Structure

### New contract and reference files

- Create: TinyStories/rc_working_contract.py — constants, corpus parsing, qparam validation, result schema, and deterministic argmax.
- Create: TinyStories/rc_working_corpus.json — four fixed eight-token prompt cases.
- Create: scripts/pipeline/build_rc_working_reference.py — emits reference.json from the fixed PT2E exported program.
- Create: scripts/pipeline/pack_rc_working_image.py — emits rc-image.bin and rc-image-manifest.json.
- Create: scripts/pipeline/verify_rc_working_image.py — reconstructs PT2E state solely from the image.
- Create: tests/test_rc_working_contract.py and tests/test_rc_working_image.py.

### New generated-SV and external-memory files

- Create: tools/mlir-passes/MaterializeRcIoBuffers.cpp — narrow MLIR pass for the fixed [1,8] token input and [1,8,6] int8 output.
- Modify: tools/mlir-passes/CMakeLists.txt and nix/pipeline.nix — register and invoke the pass only for the RC working model.
- Create: reproducers/rc-working-io/input.mlir and README.md — minimized top-level result/input ABI reproducer.
- Create: scripts/pipeline/audit_rc_sv_interface.py — rejects a done-only SV top.
- Create: rtl/rc-working/rc_argmax6.sv — deterministic signed int8 argmax with lowest-index ties.
- Create: scripts/pipeline/generate_rc_gate1_harness.py, sim/rc-working/rc_gate1_tb.sv, and scripts/pipeline/compare_rc_working_result.py.
- Create: scripts/pipeline/audit_rc_memory_provenance.py, build_rc_memory_map.py, and generate_rc_memory_adapter.py.
- Create: rtl/rc-working/rc_image_memory_fixture.sv and sim/rc-working/rc_gate2_tb.sv.
- Create: tests/test_rc_working_io_abi.py, tests/test_rc_gate1_harness.py, tests/test_rc_memory_provenance.py, and tests/test_rc_gate2_fixture.py.

### New DDR3/board and host files

- Create: nix/rc-working-system.nix — Nix derivations for the reference bundle and Gates 1–4.
- Modify: flake.nix and flake.lock — register immutable LLM2FPGA and UberDDR3 inputs, an alias to the existing RC export, and public packages.
- Create: scripts/pipeline/audit_rc_ddr3_compatibility.py — compares RC memory contract to pinned transport contract.
- Create: rtl/rc-working/rc_ddr3_adapter.sv and rtl/rc-working/rc_ddr3_top.sv — adapter and board top after a compatible audit.
- Create: scripts/board/rc_ddr3_board_gate.py — dry-run and hardware gate runner.
- Create: scripts/host/rc_working.py — reference and board backends with six-token tokenizer.
- Create: tests/test_rc_ddr3_compatibility.py, tests/test_rc_ddr3_adapter_contract.py, and tests/test_rc_host.py.
- Create: docs/results/2026-07-16-quantized-rc-working-system.md — concise gate evidence written only after each build result exists.

---

### Task 1: Freeze the RC contract and corpus

**Files:**
- Create: TinyStories/rc_working_contract.py
- Create: TinyStories/rc_working_corpus.json
- Create: tests/test_rc_working_contract.py

**Interfaces:**
- Produces: RC_WORKING_SOURCE_MODEL_KEY, RC_WORKING_PIPELINE_ALIAS, CONTEXT_LENGTH, VOCAB_SIZE, load_corpus(path), tokenize(text), decode_token_ids(ids), validate_output_tensor(tensor), argmax_lowest(codes), and canonical_result(...).
- Consumes: no compiler or board artifact; this task must run with Python standard library plus torch only where output validation is tested.

- [ ] **Step 1: Write contract tests before implementation**

Create tests for all four exact corpus strings, rejection of seven/nine tokens and tok6, lowest-index tie behavior, and a positive output scale requirement.

    def test_tokenize_round_trip(self):
        self.assertEqual(
            tokenize("tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1"),
            [0, 1, 2, 3, 4, 5, 0, 1],
        )

    def test_argmax_prefers_lowest_tied_index(self):
        self.assertEqual(argmax_lowest([-5, 7, 7, 1, 0, -2]), 1)

    def test_tokenize_rejects_unknown_or_wrong_length(self):
        with self.assertRaises(ValueError):
            tokenize("tok0 tok1 tok2")
        with self.assertRaises(ValueError):
            tokenize("tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok6")

Run:

    python3 -m unittest discover -s tests -p test_rc_working_contract.py -v

Expected: FAIL because the contract module does not exist.

- [ ] **Step 2: Add the immutable JSON corpus**

Create TinyStories/rc_working_corpus.json with schema_version 1 and these cases:

    {
      "schema_version": 1,
      "context_length": 8,
      "vocabulary": ["tok0", "tok1", "tok2", "tok3", "tok4", "tok5"],
      "cases": [
        {"id": "ascending", "text": "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1"},
        {"id": "descending", "text": "tok5 tok4 tok3 tok2 tok1 tok0 tok5 tok4"},
        {"id": "zeros", "text": "tok0 tok0 tok0 tok0 tok0 tok0 tok0 tok0"},
        {"id": "alternating", "text": "tok0 tok5 tok0 tok5 tok0 tok5 tok0 tok5"}
      ]
    }

- [ ] **Step 3: Implement the contract module**

Implement these exact invariants:

    RC_WORKING_SOURCE_MODEL_KEY = "tinystories-w8a8-rc-study-mask9-vocab6-width2"
    RC_WORKING_PIPELINE_ALIAS = "tinystories-w8a8-rc-working-via-linalg-no-handshake"
    CONTEXT_LENGTH = 8
    VOCAB_SIZE = 6

    def argmax_lowest(values: Sequence[int]) -> int:
        if len(values) != VOCAB_SIZE:
            raise ValueError("expected six logits")
        return max(range(VOCAB_SIZE), key=lambda index: (values[index], -index))

    def validate_output_qparams(scale: float, zero_point: int) -> None:
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("output scale must be finite and positive")
        if not isinstance(zero_point, int):
            raise ValueError("output zero_point must be an integer")

canonical_result must include schema_version, case_id, token_ids, output_qparams, output_codes_i8, logits, and token_id. It must reject any output whose final vocabulary dimension is not six.

- [ ] **Step 4: Re-run focused contract tests**

Run:

    python3 -m unittest discover -s tests -p test_rc_working_contract.py -v

Expected: PASS.

- [ ] **Step 5: Commit only the contract task**

Run:

    git add TinyStories/rc_working_contract.py TinyStories/rc_working_corpus.json tests/test_rc_working_contract.py
    git commit --only TinyStories/rc_working_contract.py TinyStories/rc_working_corpus.json tests/test_rc_working_contract.py -m "feat: freeze quantized RC working contract"

Expected: one commit containing only Task 1 files.

### Task 2: Build the PT2E reference and packed image with CPU replay

**Files:**
- Create: scripts/pipeline/build_rc_working_reference.py
- Create: scripts/pipeline/pack_rc_working_image.py
- Create: scripts/pipeline/verify_rc_working_image.py
- Create: tests/test_rc_working_image.py
- Modify: TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py only if an explicit exported-program loader helper is needed.

**Interfaces:**
- Consumes: exported.pt2, manifest.json, and TinyStories/rc_working_corpus.json.
- Produces: reference.json, rc-image.bin, rc-image-manifest.json, and image-replay.json.
- Contract: image segments are 64-byte aligned, little-endian, SHA-256 checked, lexicographically ordered by source category then tensor name.

- [ ] **Step 1: Write failing image tests**

Test an int8 tensor and a float qparam tensor packed at aligned offsets, deterministic repeated packing, a modified byte failing the hash check, and CPU replay rejecting a missing state item.

    def test_packer_aligns_and_hashes_segments(self):
        manifest, payload = pack_named_tensors(
            {"constants/a": tensor_i8, "state/b": tensor_f32}
        )
        self.assertEqual(manifest["segments"][1]["offset"] % 64, 0)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), manifest["image_sha256"])

    def test_replay_rejects_missing_exported_state(self):
        with self.assertRaises(ValueError):
            reconstruct_state(exported, manifest_without_one_tensor, image_bytes)

Run:

    python3 -m unittest discover -s tests -p test_rc_working_image.py -v

Expected: FAIL because the packing functions do not exist.

- [ ] **Step 2: Emit the oracle from the serialized PT2E program**

build_rc_working_reference.py must:

1. load exported.pt2 after importing torch.ao.quantization.quantize_pt2e;
2. load the corpus with load_corpus;
3. execute every case under torch.no_grad;
4. require a single int8 output tensor with shape [1, 8, 6];
5. extract the terminal output qparams from the graph’s trailing quantize_per_tensor node;
6. emit canonical_result records for output[0, 7, :];
7. include SHA-256 of exported.pt2, the copied model manifest, the exact source model key, and the working pipeline alias passed by the Nix derivation.

The main entry point must be:

    def build_reference(
        exported_program_dir: Path,
        corpus_path: Path,
        source_model_key: str,
        pipeline_alias: str,
    ) -> dict[str, object]:

- [ ] **Step 3: Implement exact tensor packing and replay**

pack_rc_working_image.py must enumerate exported.state_dict and exported.constants, classify them as state or constants, reject duplicate names, serialize each contiguous CPU tensor through tensor.numpy().tobytes(order="C"), and write a manifest record:

    {
      "name": "state_dict.transformer...",
      "source_category": "state",
      "dtype": "int8",
      "shape": [6, 2],
      "offset": 128,
      "byte_length": 12,
      "sha256": "...",
      "quantization": {"scheme": "...", "scale": ..., "zero_point": ...}
    }

verify_rc_working_image.py must reload exported.pt2, reconstruct every state tensor from the image bytes with the manifest dtype/shape, bind that reconstructed state to a copied exported program, execute all corpus cases, and compare raw codes and token IDs exactly to reference.json.

- [ ] **Step 4: Make both tools deterministic**

Run the reference and packer twice against the same exported program, then compare SHA-256 values for reference.json, rc-image.bin, and rc-image-manifest.json. The test must assert byte-identical outputs.

- [ ] **Step 5: Re-run focused tests**

Run:

    python3 -m unittest discover -s tests -p test_rc_working_image.py -v

Expected: PASS.

- [ ] **Step 6: Commit the oracle/image task**

Run:

    git add TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py scripts/pipeline/build_rc_working_reference.py scripts/pipeline/pack_rc_working_image.py scripts/pipeline/verify_rc_working_image.py tests/test_rc_working_image.py
    git commit --only TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py scripts/pipeline/build_rc_working_reference.py scripts/pipeline/pack_rc_working_image.py scripts/pipeline/verify_rc_working_image.py tests/test_rc_working_image.py -m "feat: add PT2E RC reference and image bundle"

Expected: one commit containing only Task 2 files.

### Task 3: Register the stable working model and Nix evidence bundle

**Files:**
- Create: nix/rc-working-system.nix
- Modify: flake.nix
- Create: tests/test_rc_working_nix_wiring.py

**Interfaces:**
- Consumes: existing registered study adapter and no-Handshake pipeline registry.
- Produces: `tinystories-w8a8-rc-working-via-linalg-no-handshake-pytorch-exported`, `tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx-native-sv`, and `tinystories-w8a8-rc-reference-image`.
- Contract: the working aliases point to `tinystories-w8a8-rc-study-mask9-vocab6-width2`; their exported-program store path and SHA-256 must match the existing candidate exactly. The metadata records vocab 6, layers 2, max positions 9, window 256, hidden size 2, heads 1, context length 8, PT2E static W8A8, and frozen structural calibration.

- [ ] **Step 1: Write Nix wiring tests**

Assert the working alias points to the existing structural finalist, its exported-program stage is the finalist's existing stage rather than a new exporter command, the alias uses Linalg/no-Handshake rather than TOSA, and the public reference-image package is registered.

    self.assertIn('model = "tinystories-w8a8-rc-study-mask9-vocab6-width2"', flake_text)
    self.assertIn("frontend = \"linalg\"", flake_text)
    self.assertIn("tinystories-w8a8-rc-reference-image", flake_text)

Run:

    python3 -m unittest discover -s tests -p test_rc_working_nix_wiring.py -v

Expected: FAIL.

- [ ] **Step 2: Add a stable alias to the existing finalist**

Do not add a second `registerRcStudyCore` invocation and do not change
`nix/models.nix`. In `flake.nix`, make the working pipeline alias refer directly
to `tinystories-w8a8-rc-study-mask9-vocab6-width2`. The reference bundle must
consume that alias's `pytorch-exported` stage and record both the source model
key and the alias. Its output must include `source-exported-path.txt` and
`source-exported-sha256.txt`; the latter must equal the existing candidate's
`exported.pt2` SHA-256.

- [ ] **Step 3: Add the Linalg/no-Handshake alias and reference-image derivation**

In flake.nix add a pipeline alias named tinystories-w8a8-rc-working-via-linalg-no-handshake using `pipelineStagePackagesNoHandshake`, `noHandshakeLinalgStages`, and model `tinystories-w8a8-rc-study-mask9-vocab6-width2`.

Implement nix/rc-working-system.nix as a focused derivation factory. Its referenceImage derivation must run, in order:

    build_rc_working_reference.py
    pack_rc_working_image.py
    verify_rc_working_image.py

It must copy the three canonical artifacts, image-replay.json,
source-exported-path.txt, and source-exported-sha256.txt to its output, and fail
if replay status is not pass.

- [ ] **Step 4: Run local wiring tests and Nix evaluation**

Run:

    python3 -m unittest discover -s tests -p test_rc_working_nix_wiring.py -v
    nix flake check -L
    nix build .#tinystories-w8a8-rc-reference-image -L --no-link --print-out-paths

Expected: tests pass, flake evaluation passes, and the output contains reference.json, rc-image.bin, rc-image-manifest.json, and image-replay.json.

- [ ] **Step 5: Commit Nix registration**

Run:

    git add nix/rc-working-system.nix flake.nix tests/test_rc_working_nix_wiring.py
    git commit --only nix/rc-working-system.nix flake.nix tests/test_rc_working_nix_wiring.py -m "feat: register working quantized RC evidence bundle"

Expected: one commit containing only Task 3 files.

### Task 4: Materialize an observable RC input/output ABI before Calyx

**Files:**
- Create: tools/mlir-passes/MaterializeRcIoBuffers.cpp
- Modify: tools/mlir-passes/CMakeLists.txt
- Modify: nix/pipeline.nix
- Create: reproducers/rc-working-io/input.mlir
- Create: reproducers/rc-working-io/README.md
- Create: scripts/pipeline/audit_rc_sv_interface.py
- Create: tests/test_rc_working_io_abi.py

**Interfaces:**
- Consumes: the actual RC flat-SCF MLIR. Before implementation, capture its exact public-entry signature in the reproducer; it must contain one static eight-token i64 input path and one static `[1,8,6]` i8 result path, whether the observed representation is tensor or memref.
- Produces: a top-level Calyx-compatible function with an input memref of eight i64 token IDs and an output memref of six i8 codes. It returns no scalar/tensor result.
- Contract: the pass only accepts the exact fixed static shapes and rejects every other function signature with a diagnostic. The output is final position 7 only.

- [ ] **Step 1: Capture the actual ABI and write reproducer tests**

Build the existing finalist through `flat-scf`, copy the smallest exact public
entry signature and return sequence into `reproducers/rc-working-io/input.mlir`,
and record the source artifact hash in its README. The test must prove the
current upstream top-level behavior loses a scalar return, then prove the new
bridge rewrites only that recorded fixed RC shape. If the observed entry is not
the fixed static i64/[1,8,6] i8 form, emit a blocked ABI report rather than
guessing a conversion.

    self.assertIn("memref<8xi64>", bridged_mlir)
    self.assertIn("memref<6xi8>", bridged_mlir)
    self.assertNotIn("-> tensor<1x8x6xi8>", bridged_signature)
    self.assertIn("calyx.component @main", calyx_mlir)
    self.assertIn("%out", calyx_mlir)

Run:

    python3 -m unittest discover -s tests -p test_rc_working_io_abi.py -v

Expected: FAIL before the pass exists.

- [ ] **Step 2: Implement the narrow MLIR pass for the captured representation**

Register llm2fpga-materialize-rc-io-buffers in the existing plugin. The pass must:

1. verify the exact input and result types captured in Step 1, representing one rank-2 i64 input with static shape 1 by 8 and one rank-3 i8 result with static shape 1 by 8 by 6;
2. append input memref<8xi64> and output memref<6xi8> function arguments;
3. load eight token values into the captured original input path;
4. extract output[0, 7, i] for i from 0 through 5 and store each code into the output memref;
5. remove the original function result.

Do not generalize dynamic shapes, different dtypes, or arbitrary tensor returns.

- [ ] **Step 3: Apply the pass only to the working RC**

In `nix/pipeline.nix`, define a small immutable policy map from the exact source
model name `tinystories-w8a8-rc-study-mask9-vocab6-width2` to
`rc-static-io-v1`. Thread the selected policy through `mkNoHandshakePipeline`
to `mkScfToCalyxDerivation`, and insert the plugin pass before
`lower-scf-to-calyx` only for that map entry. Do not add a second model
registration. All existing model routes retain their current pass pipeline
byte-for-byte.

- [ ] **Step 4: Add SV interface audit**

audit_rc_sv_interface.py must parse the emitted top module and write interface.json with these assertions:

    required_inputs = ["clk", "reset", "go"]
    input_token_transport = "memref-or-explicit-buffer"
    result_transport = "memref-or-explicit-buffer"
    functional_output_observable = true

It must fail on a done-only module and list exact missing signals. Use the real source file list rather than assuming one monolithic main.sv.

- [ ] **Step 5: Run ABI tests and a targeted derivation**

Run:

    python3 -m unittest discover -s tests -p test_rc_working_io_abi.py -v
    nix build .#tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx -L --no-link --print-out-paths
    nix build .#tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx-native-sv -L --no-link --print-out-paths

Expected: either a real SV bundle with interface.json passing all assertions, or one derivation result whose manifest says blocked and identifies the first lowerer operation. Do not use a math approximation to cross a blocker.

- [ ] **Step 6: Commit the ABI gate**

Run:

    git add tools/mlir-passes/MaterializeRcIoBuffers.cpp tools/mlir-passes/CMakeLists.txt nix/pipeline.nix reproducers/rc-working-io scripts/pipeline/audit_rc_sv_interface.py tests/test_rc_working_io_abi.py flake.nix
    git commit --only tools/mlir-passes/MaterializeRcIoBuffers.cpp tools/mlir-passes/CMakeLists.txt nix/pipeline.nix reproducers/rc-working-io scripts/pipeline/audit_rc_sv_interface.py tests/test_rc_working_io_abi.py flake.nix -m "feat: expose quantized RC IO through Calyx"

Expected: one commit containing only Task 4 files.

### Task 5: Implement Gate 1 real-SV equivalence

**Files:**
- Create: rtl/rc-working/rc_argmax6.sv
- Create: scripts/pipeline/generate_rc_gate1_harness.py
- Create: sim/rc-working/rc_gate1_tb.sv
- Create: scripts/pipeline/compare_rc_working_result.py
- Create: tests/test_rc_gate1_harness.py
- Modify: nix/rc-working-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: Gate 1 SV source list, interface.json, reference.json, and four corpus cases.
- Produces: tinystories-w8a8-rc-sv-equivalence/result.json.
- Contract: a simulation mismatch, timeout, missing signal, or nonzero simulator exit makes the Nix derivation fail after retaining result.json and logs.

- [ ] **Step 1: Write harness tests**

Test exact signed comparison and lowest-index ties in rc_argmax6, generated testbench inclusion of every case, and comparator rejection of one changed output byte.

    self.assertEqual(run_argmax([-128, 3, 3, -2, 1, 0]), 1)
    self.assertIn("ascending", generated_tb_data)
    self.assertEqual(compare_case(expected, observed_changed)["status"], "mismatch")

Run:

    python3 -m unittest discover -s tests -p test_rc_gate1_harness.py -v

Expected: FAIL.

- [ ] **Step 2: Implement the shared six-way argmax module**

rc_argmax6.sv must expose six signed 8-bit inputs and a 3-bit token output. It must initialize best_index to zero and update only on strict greater-than so ties retain the lower index.

    always_comb begin
      best_value = logit0;
      best_index = 3'd0;
      if (logit1 > best_value) begin best_value = logit1; best_index = 3'd1; end
      if (logit2 > best_value) begin best_value = logit2; best_index = 3'd2; end
      if (logit3 > best_value) begin best_value = logit3; best_index = 3'd3; end
      if (logit4 > best_value) begin best_value = logit4; best_index = 3'd4; end
      if (logit5 > best_value) begin best_value = logit5; best_index = 3'd5; end
    end

- [ ] **Step 3: Generate and run the Task-2-style testbench**

generate_rc_gate1_harness.py must load reference.json, write a SystemVerilog data include, select each corpus input, drive the actual generated RC interface, wait for done with a fixed MAX_CYCLES parameter, read six output bytes, compute the hardware argmax through rc_argmax6, and print one JSON object per case.

compare_rc_working_result.py must parse those objects and require exact expected_codes_i8 and expected_token_id for all cases.

- [ ] **Step 4: Wire the Gate 1 Nix package**

Extend nix/rc-working-system.nix with a derivation using pkgs.verilator, the exact generated sources.f, rc_argmax6.sv, generated testbench data, and rc_gate1_tb.sv. Expose:

    tinystories-w8a8-rc-sv-equivalence

The output must contain result.json, simulator.log, interface.json, reference.json, and a copied sources.f.

- [ ] **Step 5: Verify Gate 1**

Run:

    python3 -m unittest discover -s tests -p test_rc_gate1_harness.py -v
    nix build .#tinystories-w8a8-rc-sv-equivalence -L --no-link --print-out-paths

Expected: PASS only if all four cases have six exact code matches and exact token IDs. If the lowerer is blocked before SV, record the existing first frontier rather than create a fake SV test target.

- [ ] **Step 6: Commit Gate 1**

Run:

    git add rtl/rc-working/rc_argmax6.sv scripts/pipeline/generate_rc_gate1_harness.py scripts/pipeline/compare_rc_working_result.py sim/rc-working/rc_gate1_tb.sv tests/test_rc_gate1_harness.py nix/rc-working-system.nix flake.nix
    git commit --only rtl/rc-working/rc_argmax6.sv scripts/pipeline/generate_rc_gate1_harness.py scripts/pipeline/compare_rc_working_result.py sim/rc-working/rc_gate1_tb.sv tests/test_rc_gate1_harness.py nix/rc-working-system.nix flake.nix -m "feat: add RC PyTorch to SV equivalence gate"

Expected: one commit containing only Task 5 files.

### Task 6: Establish memory provenance before externalizing the RC

**Files:**
- Create: scripts/pipeline/audit_rc_memory_provenance.py
- Create: scripts/pipeline/build_rc_memory_map.py
- Create: tests/test_rc_memory_provenance.py
- Modify: nix/rc-working-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: exported.pt2, rc-image-manifest.json, RC Calyx MLIR, generated SV sources.f, and interface.json.
- Produces: memory-provenance.json and rc-memory-map.json.
- Contract: every immutable model byte accessed by generated SV has one image segment, an exact address formula, width, byte order, and source tensor. Unmapped memory fails the gate.

- [ ] **Step 1: Write failing provenance tests**

Use synthetic MLIR/SV fixtures to cover a mapped int8 tensor, a mapped 32-bit qparam, duplicated physical range rejection, and an untraceable generated memory rejection.

    self.assertEqual(report["status"], "pass")
    self.assertEqual(report["regions"][0]["tensor_name"], "state.weight")
    self.assertRaises(ValueError, build_memory_map, duplicate_segments)
    self.assertEqual(unmapped_report["status"], "blocked-memory-provenance")

Run:

    python3 -m unittest discover -s tests -p test_rc_memory_provenance.py -v

Expected: FAIL.

- [ ] **Step 2: Implement provenance and map generation**

The audit must start from named PT2E state/constants, preserve those names through the available Torch/Linalg/SCF/Calyx locations or symbols, and reject a missing link. It must never infer mapping only from size equality.

rc-memory-map.json must use this record shape:

    {
      "logical_memory": "in17",
      "access_kind": "read",
      "address_width_bits": 12,
      "data_width_bits": 8,
      "image_segment": "state.transformer...",
      "segment_offset_bytes": 256,
      "logical_to_image": "segment_offset_bytes + logical_address"
    }

- [ ] **Step 3: Build the real provenance artifact**

Add tinystories-w8a8-rc-memory-provenance to nix/rc-working-system.nix. It must depend on the reference-image bundle and actual Gate 1 compiler artifacts, not a hand-authored model.

- [ ] **Step 4: Run the audit**

Run:

    python3 -m unittest discover -s tests -p test_rc_memory_provenance.py -v
    nix build .#tinystories-w8a8-rc-memory-provenance -L --no-link --print-out-paths

Expected: either pass with every immutable logical memory mapped, or a blocked-memory-provenance JSON naming the first missing provenance link. Do not continue to Gate 2 if the audit is blocked.

- [ ] **Step 5: Commit provenance gate**

Run:

    git add scripts/pipeline/audit_rc_memory_provenance.py scripts/pipeline/build_rc_memory_map.py tests/test_rc_memory_provenance.py nix/rc-working-system.nix flake.nix
    git commit --only scripts/pipeline/audit_rc_memory_provenance.py scripts/pipeline/build_rc_memory_map.py tests/test_rc_memory_provenance.py nix/rc-working-system.nix flake.nix -m "feat: audit RC external memory provenance"

Expected: one commit containing only Task 6 files.

### Task 7: Implement Gate 2 image-backed external-memory equivalence

**Files:**
- Create: scripts/pipeline/generate_rc_memory_adapter.py
- Create: rtl/rc-working/rc_image_memory_fixture.sv
- Create: sim/rc-working/rc_gate2_tb.sv
- Create: tests/test_rc_gate2_fixture.py
- Modify: nix/rc-working-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: passing rc-memory-map.json, rc-image.bin, generated RC SV, and reference.json.
- Produces: external-memory adapter SV, Gate 2 result.json, transaction log, and copied map/image hashes.
- Contract: the fixture implements only the adapter protocol generated from the real RC memory contract; all reads come from rc-image.bin and all writes/error paths are checked.

- [ ] **Step 1: Write failing fixture tests**

Test a read from a known aligned image address, a narrow read that extracts the correct little-endian bytes, an invalid address response, and an image hash mismatch.

    self.assertEqual(read_word(image, 64, 2), 0x1234)
    self.assertEqual(read_word(image, 65, 1), 0x12)
    self.assertEqual(service.invalid_accesses, 1)

Run:

    python3 -m unittest discover -s tests -p test_rc_gate2_fixture.py -v

Expected: FAIL.

- [ ] **Step 2: Generate the RC-specific adapter**

generate_rc_memory_adapter.py must consume rc-memory-map.json and emit a single adapter that handles every listed generated logical memory port. It may serialize accesses but must:

1. preserve ready/valid and completion ordering;
2. convert each generated address to image byte address by the map formula;
3. split wider reads into aligned fixture reads and reassemble them in little-endian order;
4. reject writes to immutable segments;
5. emit a transaction log containing logical memory, logical address, image address, width, and result.

- [ ] **Step 3: Implement the image fixture**

rc_image_memory_fixture.sv must initialize from a file path provided by the Nix derivation, expose only the adapter request/response protocol, enforce declared image bounds, and never synthesize a fallback data pattern. It is a test fixture and must be named image fixture in logs and result JSON.

- [ ] **Step 4: Wire and run Gate 2**

Expose:

    tinystories-w8a8-rc-external-image-sv-equivalence

Its derivation compiles the real generated SV, generated adapter, image fixture, rc_argmax6, and rc_gate2_tb.sv. It must run all four cases and require the same exact result comparison as Gate 1.

Run:

    python3 -m unittest discover -s tests -p test_rc_gate2_fixture.py -v
    nix build .#tinystories-w8a8-rc-external-image-sv-equivalence -L --no-link --print-out-paths

Expected: PASS only after Gate 1 and memory provenance pass. The result JSON must label physical_ddr3_attempted as false.

- [ ] **Step 5: Commit Gate 2**

Run:

    git add scripts/pipeline/generate_rc_memory_adapter.py rtl/rc-working/rc_image_memory_fixture.sv sim/rc-working/rc_gate2_tb.sv tests/test_rc_gate2_fixture.py nix/rc-working-system.nix flake.nix
    git commit --only scripts/pipeline/generate_rc_memory_adapter.py rtl/rc-working/rc_image_memory_fixture.sv sim/rc-working/rc_gate2_tb.sv tests/test_rc_gate2_fixture.py nix/rc-working-system.nix flake.nix -m "feat: validate RC external image equivalence"

Expected: one commit containing only Task 7 files.

### Task 8: Pin and audit the proven DDR3/PCIe transport

**Files:**
- Modify: flake.nix and flake.lock
- Create: scripts/pipeline/audit_rc_ddr3_compatibility.py
- Create: tests/test_rc_ddr3_compatibility.py
- Modify: nix/rc-working-system.nix

**Interfaces:**
- Consumes: rc-memory-map.json and pinned source trees from github:RCoeurjoly/LLM2FPGA at 5cae9d4c339e151affa43ee0f471da3ba289f3d0 and github:RCoeurjoly/UberDDR3 at 4a51b9671347130759c9980d6756918f084e2124.
- Produces: ddr3-source-manifest.json and ddr3-compatibility.json.
- Contract: source manifests hash all imported RTL and list the compatible controller user-port widths, command timing, byte ordering, clock domains, and error behavior.

- [ ] **Step 1: Write compatibility tests**

Test a compatible 128-bit read-only request profile, a required write rejected by a read-only port, a byte-order mismatch, and a missing source file.

    self.assertEqual(audit(compatible_contract, rc_reads_only)["status"], "compatible")
    self.assertEqual(audit(read_only_contract, rc_requires_write)["status"], "blocked")
    self.assertIn("byte_order", audit(swapped_contract, rc_contract)["mismatches"])

Run:

    python3 -m unittest discover -s tests -p test_rc_ddr3_compatibility.py -v

Expected: FAIL.

- [ ] **Step 2: Add immutable source inputs**

Add non-flake inputs named llm2fpga-ddr3-src and uberddr3-src using the public GitHub commits above. Do not use path inputs. Add a source manifest derivation that records the resolved store paths, Git revisions, hashes, and the exact imported files:

    rtl/ddr3_top.v
    rtl/ddr3_controller.v
    rtl/ddr3_phy.v
    rtl/ecc/ecc_dec.sv
    rtl/ecc/ecc_enc.sv
    fpga/rtl/task6_ypcb_uberddr3_user_port_probe_top.sv
    scripts/task6/task6_ddr3_rowstream_loader.py

- [ ] **Step 3: Implement the contract audit**

audit_rc_ddr3_compatibility.py must parse the selected controller/top source and the generated RC map. It must produce:

    {
      "status": "compatible" | "blocked",
      "rc_requirements": {...},
      "transport_capabilities": {...},
      "mismatches": [...],
      "selected_user_port": "...",
      "source_manifest_sha256": "..."
    }

The rowstream reader must be reported as a specialized historical client, not selected merely because it exists.

- [ ] **Step 4: Build the audit**

Run:

    python3 -m unittest discover -s tests -p test_rc_ddr3_compatibility.py -v
    nix build .#tinystories-w8a8-rc-ddr3-compatibility-audit -L --no-link --print-out-paths

Expected: either compatible with one explicit general user port, or blocked with exact width/protocol differences. A blocked result ends board-adapter work without changing DDR RTL.

- [ ] **Step 5: Commit pinned audit**

Run:

    git add flake.nix flake.lock scripts/pipeline/audit_rc_ddr3_compatibility.py tests/test_rc_ddr3_compatibility.py nix/rc-working-system.nix
    git commit --only flake.nix flake.lock scripts/pipeline/audit_rc_ddr3_compatibility.py tests/test_rc_ddr3_compatibility.py nix/rc-working-system.nix -m "feat: pin and audit RC DDR3 transport"

Expected: one commit containing only Task 8 files.

### Task 9: Build the RC DDR3 adapter and board-equivalence package

**Files:**
- Create: rtl/rc-working/rc_ddr3_adapter.sv
- Create: rtl/rc-working/rc_ddr3_top.sv
- Create: scripts/board/rc_ddr3_board_gate.py
- Create: tests/test_rc_ddr3_adapter_contract.py
- Modify: nix/rc-working-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: a compatible Gate 3 report, RC memory map, image, reference, and pinned UberDDR3/LLM2FPGA source.
- Produces: a board bitstream derivation, a dry-run board command, and after explicit hardware authorization a board result.json.
- Contract: the adapter preserves the audited port protocol and exposes six output codes plus token ID through a host-visible control/result aperture.

- [ ] **Step 1: Write adapter contract tests**

Use a cycle-level SV or Python model to test a read request, a split read, a backpressured acknowledgement, controller error propagation, and result-vector packing.

    self.assertEqual(pack_result([-1, 2, 3, 4, 5, 6], 5), bytes([255, 2, 3, 4, 5, 6, 0, 0, 5, 0, 0, 0]))
    self.assertEqual(model.error_code, ERROR_DDR_ACK)

Run:

    python3 -m unittest discover -s tests -p test_rc_ddr3_adapter_contract.py -v

Expected: FAIL.

- [ ] **Step 2: Implement only the audited adapter**

rc_ddr3_adapter.sv must be generated or parameterized solely by the compatible ddr3-compatibility.json. It must convert the RC adapter request stream to the selected UberDDR3 user port, preserve byte ordering and alignment, expose errors, and never substitute an unverified rowstream format.

rc_ddr3_top.sv must instantiate the exact pinned DDR3 controller, the RC core, rc_ddr3_adapter, rc_argmax6, and a host-visible input/result aperture. It must not contain model weights or an alternative computation implementation.

- [ ] **Step 3: Produce a reproducible bitstream and dry-run command**

The Nix package:

    tinystories-w8a8-rc-ddr3-board-equivalence

must build the board top, record bitstream/tool/source/image hashes, and write a board-command.json accepted by rc_ddr3_board_gate.py --dry-run. The derivation must not flash or program hardware.

- [ ] **Step 4: Verify locally before hardware**

Run:

    python3 -m unittest discover -s tests -p test_rc_ddr3_adapter_contract.py -v
    nix build .#tinystories-w8a8-rc-ddr3-board-equivalence -L --no-link --print-out-paths
    bundle=$(nix build .#tinystories-w8a8-rc-ddr3-board-equivalence --no-link --print-out-paths)
    python3 scripts/board/rc_ddr3_board_gate.py --dry-run --bundle "$bundle"

Expected: adapter tests pass, the bitstream bundle builds, and dry-run validates hashes, corpus, command sequence, and expected result layout.

- [ ] **Step 5: Stop for explicit board-programming approval**

Do not invoke the non-dry-run board command in this task. After the user authorizes programming, run it once per corpus case, retain the board result JSON, and require exact six-code/token agreement with reference.json.

- [ ] **Step 6: Commit the board integration**

Run:

    git add rtl/rc-working/rc_ddr3_adapter.sv rtl/rc-working/rc_ddr3_top.sv scripts/board/rc_ddr3_board_gate.py tests/test_rc_ddr3_adapter_contract.py nix/rc-working-system.nix flake.nix
    git commit --only rtl/rc-working/rc_ddr3_adapter.sv rtl/rc-working/rc_ddr3_top.sv scripts/board/rc_ddr3_board_gate.py tests/test_rc_ddr3_adapter_contract.py nix/rc-working-system.nix flake.nix -m "feat: add RC DDR3 board equivalence path"

Expected: one commit containing only Task 9 files.

### Task 10: Add the host tokenizer/control gate and evidence report

**Files:**
- Create: scripts/host/rc_working.py
- Create: tests/test_rc_host.py
- Create: docs/results/2026-07-16-quantized-rc-working-system.md
- Modify: nix/rc-working-system.nix
- Modify: flake.nix

**Interfaces:**
- Consumes: TinyStories/rc_working_corpus.json, reference bundle, and optionally a Gate 4 board bundle.
- Produces: reference-backend JSON and board-backend JSON with the common result schema.
- Contract: both backends accept all four fixed prompt strings; board mode must emit direct token IDs and board evidence before comparison.

- [ ] **Step 1: Write host tests**

Test tokenization, reference-backend JSON shape, board command construction, corpus iteration, and failure on a board response whose token IDs differ from the tokenizer.

    self.assertEqual(tokenize_prompt("tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1"), [0, 1, 2, 3, 4, 5, 0, 1])
    self.assertEqual(reference_result["token_id"], expected["token_id"])
    with self.assertRaises(ValueError):
        board_backend(fake_board_with_wrong_ids, prompt)

Run:

    python3 -m unittest discover -s tests -p test_rc_host.py -v

Expected: FAIL.

- [ ] **Step 2: Implement the two explicit backends**

The CLI must support:

    rc_working.py reference --prompt "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1" --bundle BUNDLE
    rc_working.py board --prompt "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1" --bundle BUNDLE

reference loads reference.json and returns the matching case. board invokes only the board gate’s documented command/result interface, validates image and bitstream hashes, and compares all six codes and token ID.

- [ ] **Step 3: Publish the gate evidence without inventing success**

The result document must list each gate, command, artifact hash, status, and first frontier. If Gate 4 has not been hardware-authorized or is blocked, state that exactly; do not call Gate 5 passed.

- [ ] **Step 4: Run regression and package checks**

Run:

    python3 -m unittest discover -s tests -p test_rc_host.py -v
    python3 -m unittest discover -s tests -v
    nix flake check -L
    nix build .#tinystories-w8a8-rc-host-e2e -L --no-link --print-out-paths

Expected: local tests and flake checks pass. The host package reports the current Gate 4 state honestly rather than bypassing it.

- [ ] **Step 5: Commit the host/evidence gate**

Run:

    git add scripts/host/rc_working.py tests/test_rc_host.py docs/results/2026-07-16-quantized-rc-working-system.md nix/rc-working-system.nix flake.nix
    git commit --only scripts/host/rc_working.py tests/test_rc_host.py docs/results/2026-07-16-quantized-rc-working-system.md nix/rc-working-system.nix flake.nix -m "feat: add RC host equivalence gate"

Expected: one commit containing only Task 10 files.

## Gate 6 follow-on

Do not enlarge the model inside this implementation plan. Gate 6 begins only after Gate 5 has a recorded pass. At that point, create a new design and implementation plan for one scale dimension, reusing the same contract, image format, DDR3 adapter, host command, and full six-logit/token equivalence suite.
