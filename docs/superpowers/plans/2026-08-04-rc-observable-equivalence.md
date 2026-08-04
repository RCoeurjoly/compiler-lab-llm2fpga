# RC Observable-Equivalence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Establish a strict four-context PT2E-to-Verilator gate, then emit and merge complete deterministic evidence for all 6^8 = 1,679,616 fixed-RC token contexts.

**Architecture:** A Python PT2E oracle writes compact lexical shard payloads. A compiled-once SystemVerilog fixture derives each token context from its payload ordinal, restores all mutable external memory before every launch, and rejects anything except bounded done plus stable final logits. Python records durable result/counterexample receipts, and a merger proves exact shard coverage.

**Tech Stack:** Python 3 standard library plus PyTorch/TorchAO in Nix, SystemVerilog, Verilator 5.022+, GNU make, Nix, unittest.

## Global Constraints

- PT2E exported.pt2 is the only numerical acceptance authority; do not introduce a hand-written arithmetic oracle.
- Preserve raw generated SV, PT2E export, image bytes/manifest, W8A8 arithmetic, and the one-cycle external-memory response protocol.
- Use V=6, context length 8, output [0, 7, :], all six signed int8 codes, and lowest-index argmax exactly.
- Enumerate lexical base-six contexts with half-open ranges over [0, 1679616).
- A passing equivalence mode must reject early-output diagnostics, timeout, missing final-address writes, immutable-memory writes, and malformed records.
- Derive memory classes from actual generated SV. The current ABI must clear mutable ports 26 and 46..145 before every transaction.
- Preserve all pre-existing dirty worktree changes. Stage and commit only files owned by the completed task.
- Treat temporary directories, cached binaries, and unmerged partial shards as diagnostics only. Durable evidence is a Nix output or checked-in artifact with hashes.

---

### Task 1: Add deterministic PT2E oracle shards

**Files:**

- Create: scripts/pipeline/build_rc_observable_oracle.py
- Create: tests/test_rc_observable_oracle.py

**Interfaces:**

- Produces context_from_index(index: int) -> list[int] and index_from_context(tokens: Sequence[int]) -> int.
- Produces pack_record(codes: Sequence[int], token_id: int) -> str and unpack_record(word: str) -> tuple[list[int], int].
- Produces generate, verify, and merge-oracle CLI subcommands. A payload line is exactly one 16-character lowercase hexadecimal word plus newline.

- [ ] **Step 1: Write the failing pure-format tests**

These tests catch reversed enumeration, int8 sign loss, non-lowest tied argmax, and invalid reserved bits.

    def test_context_index_round_trip_uses_rightmost_token_as_fastest(self):
        self.assertEqual(context_from_index(0), [0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(context_from_index(1), [0, 0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(context_from_index(6), [0, 0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(index_from_context([5] * 8), 1_679_615)

    def test_record_round_trip_preserves_signed_codes_and_argmax(self):
        word = pack_record([-128, -1, 0, 127, 7, 7], 3)
        self.assertEqual(word, "000307077f00ff80")
        self.assertEqual(unpack_record(word), ([-128, -1, 0, 127, 7, 7], 3))

    def test_unpack_record_rejects_reserved_bits_and_invalid_token(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            unpack_record("0100000000000000")
        with self.assertRaisesRegex(ValueError, "token"):
            unpack_record("0006000000000000")

- [ ] **Step 2: Verify RED**

Run: python3 -m unittest tests.test_rc_observable_oracle -v

Expected: FAIL because the module and its fixed record/enumeration interfaces do not exist.

- [ ] **Step 3: Implement fixed enumeration and record format**

Implement the exact layout: six two's-complement bytes at bits 0..47, token ID at bits 48..55, and zero at bits 56..63.

    VOCAB_SIZE = 6
    CONTEXT_LENGTH = 8
    TOTAL_CONTEXTS = VOCAB_SIZE ** CONTEXT_LENGTH

    def pack_record(codes: Sequence[int], token_id: int) -> str:
        if len(codes) != 6 or any(not -128 <= value <= 127 for value in codes):
            raise ValueError("record requires six signed int8 codes")
        if not 0 <= token_id < VOCAB_SIZE:
            raise ValueError("record token ID outside vocabulary")
        value = sum((code & 0xff) << (8 * lane) for lane, code in enumerate(codes))
        value |= token_id << 48
        return f"{value:016x}"

unpack_record must validate length/lowercase hexadecimal, require value >> 56 == 0, sign-extend each code, and require token 0..5. context_from_index must reject bools and indexes outside the exact half-open domain.

- [ ] **Step 4: Write failing real-file generator tests**

Use a temporary payload directory and a small injected batch-one evaluator. Test the real writer, payload SHA-256, exact 17-byte line count, and reference preflight discrepancy.

    def test_generate_shard_streams_payload_and_records_digest(self):
        receipt = generate_shard(
            evaluator=DeterministicEvaluator(), start=4, stop=6,
            output_dir=self.path, receipt=self.receipt,
        )
        self.assertEqual(receipt["enumeration"]["start"], 4)
        self.assertEqual(receipt["payload"]["records"], 2)
        self.assertEqual((self.path / "shard-4-6.hex").read_text().splitlines(), [
            "0000000504030201", "0000000504030201",
        ])

- [ ] **Step 5: Verify RED, implement PT2E generation, then verify GREEN**

Run first: python3 -m unittest tests.test_rc_observable_oracle -v

Expected: FAIL because generate_shard does not exist.

Implement generate by loading torch.export.load(exported_dir / "exported.pt2").module() once, evaluating batch-one torch.long [1, 8] inputs under torch.inference_mode(), validating output shape/dtype through the RC contract, and deriving argmax via the existing lowest-index helper. Before writing any payload, evaluate every row in reference.json through the same module and reject a raw-code or token mismatch.

Stream packed lines and SHA-256; only write metadata after reopening and validating record count, 17-byte line size, field legality, file size, and payload digest. Include export/reference/image/image-manifest/generator/contract hashes, Python/PyTorch versions, thread configuration, enumeration, record format, payload digest/count/bytes, and elapsed seconds.

Run: python3 -m unittest tests.test_rc_observable_oracle -v

Expected: PASS.

- [ ] **Step 6: Implement and test oracle merge**

Write a merger that sorts metadata by start and rejects changed receipt, schema, record format, payload hash/count, incomplete status, duplicate, overlap, or gap. It writes coverage.complete true only for exactly [0, 1679616).

Run:

    python3 -m unittest tests.test_rc_observable_oracle -v
    python3 -m py_compile scripts/pipeline/build_rc_observable_oracle.py
    git diff --check

Expected: PASS.

Commit only task-owned files:

    git add scripts/pipeline/build_rc_observable_oracle.py tests/test_rc_observable_oracle.py
    git commit -m "feat: generate durable RC observable oracle shards"

### Task 2: Derive and enforce the SV memory ABI

**Files:**

- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_sv_equivalence_fixture.py
- Create: tests/fixtures/rc_memory_abi.sv if inline fixtures become unreadable.

**Interfaces:**

- Produces _memory_abi(source: str) -> dict[int, MemoryPort], where each port has width, depth, class, and write-enable digest.
- Produces canonical ABI JSON and an ABI SHA-256 bound into fixture and result receipts.
- Rejects missing ports, unsupported write-enable syntax, wrong token/output dimensions, changed static image-port set, and unclassified external ports.

- [ ] **Step 1: Write failing ABI tests**

These tests catch classifying a dynamic write enable as immutable, skipping a scratch reset, and accepting an ABI change as the frozen image.

    def test_memory_abi_marks_only_proven_zero_write_enables_immutable(self):
        abi = module._memory_abi(SV_WITH_ZERO_PORT_0_AND_DYNAMIC_PORT_46)
        self.assertEqual(abi[0].kind, "image")
        self.assertEqual(abi[25].kind, "token")
        self.assertEqual(abi[26].kind, "output")
        self.assertEqual(abi[46].kind, "scratch")

    def test_memory_abi_rejects_unknown_write_enable_form(self):
        with self.assertRaisesRegex(RuntimeError, "write-enable"):
            module._memory_abi(SV_WITH_UNSUPPORTED_WRITE_ENABLE)

    def test_fixture_resets_every_mutable_port_and_faults_on_image_write(self):
        tb = self._fixture_text_with_146_ports()
        self.assertIn("for (int i=0; i<64; i++) mem26[i] = '0;", tb)
        self.assertIn("for (int i=0; i<64; i++) mem145[i] = '0;", tb)
        self.assertIn("IMMUTABLE_WRITE port=0", tb)

- [ ] **Step 2: Verify RED**

Run: python3 -m unittest tests.test_rc_sv_equivalence_fixture -v

Expected: FAIL because the runner currently gives every memory the same service behavior and only clears input tokens between cases.

- [ ] **Step 3: Implement conservative classification**

Parse only module main_1 assignments named arg_mem_N_write_en. Mark a port immutable only if every result arm is an explicit one-bit zero literal and no dynamic value can reach the result. Mark dynamic or one-valued expressions mutable. Reject any other syntax.

Require exactly:

    IMAGE_PORTS = frozenset(range(25)) | frozenset(range(27, 46))
    TOKEN_PORT = 25
    OUTPUT_PORT = 26
    mutable == {OUTPUT_PORT, *range(46, 146)}
    immutable == IMAGE_PORTS | {TOKEN_PORT}

Require token (64, 8) and output (8, 64). Serialize sorted {number, width, depth, kind, write_enable_sha256} rows with sorted JSON and hash it.

- [ ] **Step 4: Render reset task and immutable guards**

Generate a SystemVerilog task automatic reset_transaction(input longint unsigned context_index). While reset is high, it zeroes mem26 and mem46..mem145 through their actual declared depths, clears response/counter/write-mask state, fills mem25 using repeated modulo/divide by six from right to left, then holds three reset clock edges.

Keep the existing one-cycle response model. Before a DUT request can store to an immutable port, fail it:

    if (a0_en && a0_we) begin
      $display("IMMUTABLE_WRITE port=0 addr=%0d", a0_addr);
      $fatal(1, "DUT attempted write to immutable port 0");
    end

Render equivalent guards for all immutable DUT ports. Direct fixture token assignments are not DUT writes.

- [ ] **Step 5: Verify GREEN and commit**

Run:

    python3 -m unittest tests.test_rc_sv_equivalence_fixture -v
    python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
    git diff --check

Expected: PASS. The 146-port fixture resets 26 and 46..145 and emits a canonical ABI receipt.

Commit only task-owned hunks/files:

    git add scripts/pipeline/run_rc_sv_equivalence.py tests/test_rc_sv_equivalence_fixture.py tests/fixtures/rc_memory_abi.sv
    git commit -m "fix: reset and audit RC SV memory transactions"

If the fixture stayed inline, omit its nonexistent path from git add. Do not stage pre-existing unrelated hunks.

### Task 3: Replace static cases with a strict generic shard driver

**Files:**

- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_sv_equivalence_fixture.py
- Create: tests/test_rc_observable_driver.py

**Interfaces:**

- Produces --equivalence-shard <oracle-json>; it accepts no early-output/trace controls.
- Sends +oracle_file, +shard_start, +shard_count, and +cycle_bound to a generic compiled fixture.
- Emits one CASE_PASS, CASE_FAIL, or SHARD_PASS terminal record per context/shard and turns it into a durable Python receipt.

- [ ] **Step 1: Write failing completion and CLI tests**

These catch treating an intermediate output write as completion, accepting unwritten final addresses, incorrect tie behavior, and enabling a diagnostic shortcut in equivalence mode.

    def test_equivalence_cli_rejects_early_output_diagnostic(self):
        with self.assertRaises(SystemExit):
            module.main_from_args([
                "--equivalence-shard", "oracle.json", "--stop-after-output",
            ])

    def test_fixture_requires_done_all_final_writes_and_stable_sampling(self):
        tb = self._strict_fixture_text()
        self.assertIn("final_write_mask == 6'b111111", tb)
        self.assertIn("TIMEOUT", tb)
        self.assertIn("LATE_FINAL_WRITE", tb)
        self.assertIn("repeat (2) @(posedge clk);", tb)

    def test_parser_rejects_zero_exit_without_case_pass(self):
        with self.assertRaisesRegex(RuntimeError, "missing CASE_PASS"):
            module._parse_shard_output("- tb.sv: $finish", expected_count=1)

- [ ] **Step 2: Verify RED**

Run: python3 -m unittest tests.test_rc_sv_equivalence_fixture tests.test_rc_observable_driver -v

Expected: FAIL because the fixture embeds reference.json rows and output-write diagnostics can reach a RESULT line.

- [ ] **Step 3: Implement runtime stream and lexical token drive**

Use $fopen/$fscanf to consume exactly one %h word from +oracle_file per ordinal. Reject missing file, scan failure, bad record padding, wrong count, and trailing word. Decode start + ordinal into mem25 within reset_transaction. Do not emit any expected codes/case names/input tokens from reference.json into tb.sv. Compile cache identity binds fixture source/configuration but never one shard payload.

- [ ] **Step 4: Implement strict completion, comparison, and output parser**

Track a six-bit write mask for mem26[42..47], immutable_write_seen, launch cycle, and done cycle. Deassert go on sampled done; wait two posedges; reject a final-address write during settling; require final_write_mask == 6'b111111; then compare all signed bytes and independently compare the stored token ID:

    if ($signed(mem26[42 + lane]) !== $signed(expected_record[8*lane +: 8])) begin
      $display("CASE_FAIL index=%0d reason=raw_code lane=%0d", context_index, lane);
      $fatal(1, "raw code mismatch");
    end

Find argmax with best_index = 0 and replacement only on strictly greater signed code. Emit lexical index, cycles, expected/observed codes, expected/observed token, and write mask. On failure Python writes counterexample.json before nonzero exit.

- [ ] **Step 5: Implement and test result receipt parsing**

The receipt binds oracle metadata/payload SHA-256, raw and normalized SV hashes, runner/fixture hash, ABI receipt, simulator/host versions, range/count, cycle bound, completion count, min/max latency, wall time, and status. Require contiguous CASE_PASS indexes; duplicate/missing/extra lines fail.

Run:

    python3 -m unittest tests.test_rc_sv_equivalence_fixture tests.test_rc_observable_driver -v
    python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
    git diff --check

Expected: PASS.

- [ ] **Step 6: Commit only Task 3 work**

    git add scripts/pipeline/run_rc_sv_equivalence.py tests/test_rc_sv_equivalence_fixture.py tests/test_rc_observable_driver.py
    git commit -m "feat: run strict generic RC observable shards"

### Task 4: Wire the frozen four-context strict gate through Nix

**Files:**

- Modify: flake.nix
- Create: diagnostics/rc-observable-equivalence.nix
- Create: tests/test_rc_observable_nix_wiring.py

**Interfaces:**

- Produces tinystories-w8a8-rc-observable-oracle-frozen-four with four named one-record lexical receipts.
- Produces tinystories-w8a8-rc-observable-equivalence-build with generic compiled fixture/cache evidence.
- Produces tinystories-w8a8-rc-observable-equivalence-frozen-four with four fresh-process results, a sequential-reset result, and strict summary.

- [ ] **Step 1: Write a failing Nix behavior test**

This catches accidentally reusing the old embedded fixture or an early-output diagnostic as the promotion gate.

    def test_flake_exposes_strict_observable_outputs(self):
        packages = eval_package_names()
        self.assertIn("tinystories-w8a8-rc-observable-oracle-frozen-four", packages)
        self.assertIn("tinystories-w8a8-rc-observable-equivalence-frozen-four", packages)
        source = (ROOT / "diagnostics/rc-observable-equivalence.nix").read_text()
        self.assertNotIn("--stop-after-output", source)

- [ ] **Step 2: Verify RED**

Run: python3 -m unittest tests.test_rc_observable_nix_wiring -v

Expected: FAIL because strict observable-equivalence outputs do not exist.

- [ ] **Step 3: Implement four lexical oracle receipts**

For ascending, descending, zeros, and alternating, calculate their exact lexical indexes, generate four one-record payload/metadata pairs through Task 1, and store each mapping case ID/tokens/index. Validate raw codes and token against existing immutable reference.json; do not create a new human oracle.

- [ ] **Step 4: Compile once and prove reset equivalence**

Build the generic fixture with documented coarse Verilator split/job settings. Verify cache hashes for every run. Execute four records as fresh processes, then execute the identical four in a single process. A reducer must compare case ID, index, all raw codes, token, done/completion status, bound status, and reset receipt exactly.

- [ ] **Step 5: Verify and commit**

Run:

    python3 -m unittest tests.test_rc_observable_nix_wiring -v
    nix-instantiate --parse flake.nix
    nix build .#tinystories-w8a8-rc-observable-equivalence-frozen-four -L

Expected: a status pass summary only after all four exact comparisons meet strict completion. If it times out or differs, preserve the durable negative artifact and do not relax the gate.

    git add flake.nix diagnostics/rc-observable-equivalence.nix tests/test_rc_observable_nix_wiring.py
    git commit -m "feat: add strict RC frozen observable equivalence gate"

### Task 5: Add throughput evidence, shard plan, and result merger

**Files:**

- Modify: scripts/pipeline/build_rc_observable_oracle.py
- Create: scripts/pipeline/merge_rc_observable_results.py
- Create: tests/test_rc_observable_results.py
- Modify: diagnostics/rc-observable-equivalence.nix
- Modify: flake.nix

**Interfaces:**

- Produces shard-plan.json with deterministic ordered half-open ranges and a SHA-256.
- Produces rc-observable-throughput.json from a bounded multi-record strict run.
- Produces rc-observable-coverage.json only when complete receipts cover [0, 1679616) exactly.

- [ ] **Step 1: Write failing merger/projection tests**

These catch gaps, overlap, changed provenance, failed-shard acceptance, and a fictitious performance projection.

    def test_merge_rejects_gap_and_overlap(self):
        with self.assertRaisesRegex(ValueError, "coverage"):
            merge_results([receipt(0, 2), receipt(3, 4)])
        with self.assertRaisesRegex(ValueError, "coverage"):
            merge_results([receipt(0, 3), receipt(2, 4)])

    def test_merge_rejects_different_candidate_provenance(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            merge_results([receipt(0, 2, sv="a"), receipt(2, 4, sv="b")])

    def test_projection_uses_actual_measured_rate(self):
        result = throughput_projection(contexts=8, seconds=2.0, total=1_679_616)
        self.assertEqual(result["contexts_per_second"], 4.0)
        self.assertEqual(result["projected_seconds"], 419_904.0)

- [ ] **Step 2: Verify RED**

Run: python3 -m unittest tests.test_rc_observable_results -v

Expected: FAIL because result receipts and deterministic plan merging do not exist.

- [ ] **Step 3: Implement strict planning and merging**

A plan records radix, context length, total, fixed shard size, ordered ranges, creator receipt, and its own hash. Do not select full-run shard width until Task 4 observes at least one strict completion.

Merge must validate plan hash, every oracle metadata/payload hash, ABI receipt, runner/fixture/raw/normalized-SV hashes, tool receipt, bound, status, range/count, and latency before sorting. It writes complete only for contiguous full coverage and reports aggregate context count, min/max latency, and summed wall time.

- [ ] **Step 4: Add a Nix throughput probe**

Run a bounded strict multi-record range with trace flags disabled. Persist candidate/SV/simulator/host provenance, range/count, wall seconds, contexts/s, cycles/context, latency extrema, and full-domain projection. It does not publish coverage. Freeze shard-plan.json only from this successful receipt.

- [ ] **Step 5: Verify and commit**

Run:

    python3 -m unittest tests.test_rc_observable_results -v
    python3 -m py_compile scripts/pipeline/build_rc_observable_oracle.py scripts/pipeline/merge_rc_observable_results.py
    nix build .#tinystories-w8a8-rc-observable-throughput -L

Expected: PASS only if the probe genuinely completes strict contexts. If not, retain the negative receipt and do not publish a promotion shard plan.

    git add scripts/pipeline/build_rc_observable_oracle.py scripts/pipeline/merge_rc_observable_results.py tests/test_rc_observable_results.py diagnostics/rc-observable-equivalence.nix flake.nix
    git commit -m "feat: merge RC observable equivalence evidence"

### Task 6: Execute and audit the full promotion gate

**Files:**

- Create: docs/results/2026-08-04-rc-observable-equivalence-throughput.md
- Create: docs/results/2026-08-04-rc-observable-equivalence-coverage.md only after complete coverage.
- Produce: a durable Nix output containing all oracle/result shards and the merged manifest; the coverage report records its exact store path and digest.

**Interfaces:**

- Consumes the fixed shard-plan.json, strict oracle shards, compiled cache receipt, and merger.
- Produces either a complete coverage manifest or a durable scalability/mismatch/timeout blocker. It never produces an equivalence claim from a partial run.

- [ ] **Step 1: Run and preserve throughput**

Run: nix build .#tinystories-w8a8-rc-observable-throughput -L

Record candidate/SV/tool hashes, completed count, wall seconds, contexts/s, cycles/context, maximum latency, and projection. Verify strict done/final-address completion, not a diagnostic output write.

- [ ] **Step 2: Generate and validate planned oracle shards**

Run every plan command and Task 1 verify command. Reject changed export/image/reference hashes before simulation.

- [ ] **Step 3: Run every strict SV shard**

Reuse only a verified compiled generic fixture. Parallel jobs require independent work directories and identical fixed provenance. On a failure, preserve the counterexample and stop producing a pass manifest.

- [ ] **Step 4: Merge and independently inspect exact coverage**

Run:

    python3 scripts/pipeline/merge_rc_observable_results.py --plan shard-plan.json --result-shard result-*.json --out coverage.json

Then require coverage.start == 0, coverage.stop == 1679616, coverage.complete is true, and every planned range/payload/result digest is present. Reject diagnostic mode, timeout, mismatch, incomplete count, or changed provenance.

- [ ] **Step 5: Run full verification and final repository checks**

Run:

    python3 -m unittest tests.test_rc_observable_oracle tests.test_rc_observable_driver tests.test_rc_observable_results tests.test_rc_observable_nix_wiring tests.test_rc_sv_equivalence_fixture -v
    nix-instantiate --parse flake.nix
    git diff --check
    scripts/agent/pre_final_check.sh

Expected: all checks pass and no task-owned changes remain uncommitted.

- [ ] **Step 6: Commit proof only after full success**

    git add docs/results/2026-08-04-rc-observable-equivalence-throughput.md docs/results/2026-08-04-rc-observable-equivalence-coverage.md
    git commit -m "test: prove RC observable equivalence exhaustively"

If a shard fails or the projection is impractical, do not make this equivalence-proof commit or mark the candidate equivalent. A completed, labelled negative result may be committed only after its diagnostic verification finishes.

## Plan self-review

- **Spec coverage:** Task 1 supplies the PT2E-only oracle and deterministic provenance; Task 2 supplies image/transaction safety; Task 3 supplies strict observables and counterexamples; Task 4 proves the frozen gate/reset equivalence; Tasks 5–6 deliver throughput, durable full-domain shards, and exact coverage.
- **Placeholder scan:** All interfaces, fixed values, record layout, test behaviors, commands, and acceptance conditions are explicit.
- **Type consistency:** Task 1 payload/metadata pairs feed Task 3. Task 2 ABI receipt feeds Task 3 result receipts. Task 3 receipts feed Task 5/6. Every interval is half-open integer [start, stop).

Plan complete and saved to docs/superpowers/plans/2026-08-04-rc-observable-equivalence.md. Execute inline in this session with task-level test/review checkpoints because each task modifies the shared runner/fixture boundary.
