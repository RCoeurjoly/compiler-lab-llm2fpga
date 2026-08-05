# RC Exponential Table Equivalence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the currently unsupported/unbounded `math.exp` lowering for the Representative Core (RC) with a measured, oracle-backed finite table, demonstrate PyTorch↔SV equivalence for selected inputs, and only then benchmark DDR3 placement and approximate alternatives.

**Architecture:** Treat exponential evaluation as an explicit ABI component. First measure the exact post-lowering input domain and required output quantization; generate immutable table bytes from a PyTorch/ high-precision oracle; bind those bytes and their address/latency contract to the generated RTL; then compare the SV trace with the oracle. DDR3 is an alternate table backing store, not a semantic change. Approximate polynomial/shift-add implementations remain separate candidates.

**Tech Stack:** PyTorch, Python, generated SystemVerilog, Verilator, existing RC equivalence harness, host DDR3 model/UberDDR3-compatible interface, JSON/Markdown receipts, Git.

## Global Constraints

- Do not call the result “equivalent” unless the compared input/output domains, rounding, saturation, reset, and latency contract are recorded.
- Keep the exact table implementation separate from PEANO/QUARK-style approximations.
- Use the pinned paper corpus only for strategy selection and cite local PDFs.
- Every repository change gets a focused commit; do not commit generated Nix result links or caches.
- All host-side work must run without FPGA hardware.

---

### Task 1: Measure RC exponential domain

**Files:**
- Create: `docs/results/2026-08-05-rc-exp-domain.json`
- Create: `docs/results/2026-08-05-rc-exp-domain.md`
- Modify: existing RC probe/oracle script identified by `rg -l "math\.exp|exp\(" scripts tests src`
- Test: the new probe and its JSON schema

**Interfaces:**
- Consumes: one RC model configuration, deterministic calibration/equivalence inputs, and the PyTorch reference graph.
- Produces: `input_min`, `input_max`, sample count, output precision, rounding mode, saturation behavior, and a reproducible input seed/list.

- [ ] **Step 1: Locate the RC exp call site and existing oracle/probe entry points.** Record the exact tensor/op name and whether softmax max-subtraction has already happened.
- [ ] **Step 2: Add a deterministic probe that records every exp input and reference output.** Include ordinary, boundary, and adversarial inputs; preserve raw serialized values rather than only summary statistics.
- [ ] **Step 3: Run the probe and emit the JSON receipt.** Verify the observed domain is finite and that no NaN/Inf or unexpected dtype conversion is silently discarded.
- [ ] **Step 4: Document the selected conservative interval.** Expand the observed min/max by one quantization bin or an explicitly recorded safety margin; do not silently clip values.
- [ ] **Step 5: Run the probe twice and compare hashes.** The receipts must be byte-identical for the same source/model/input hashes.
- [ ] **Step 6: Commit.**

```bash
git add docs/results/2026-08-05-rc-exp-domain.*
git commit -m "Measure RC exponential input domain"
```

Gate: no table work starts until the interval, dtype, quantization, and rounding contract are recorded.

### Task 2: Generate an oracle-backed finite table

**Files:**
- Create: `tools/exp_table/generate_rc_exp_table.py`
- Create: `tools/exp_table/table_format.py`
- Create: `tests/exp_table/test_generate_rc_exp_table.py`
- Create: `docs/results/2026-08-05-rc-exp-table.json`
- Create: `artifacts/rc_exp_table.bin` (or the repository’s established artifact location)

**Interfaces:**
- `generate_table(domain_receipt: Path, output: Path, address_bits: int, output_format: str) -> dict`
- Table header fields: magic, version, input encoding, output encoding, domain min/max, entry count, rounding mode, and SHA-256 of payload.
- `decode_table(path: Path) -> TableSpec` validates header and payload length.

- [ ] **Step 1: Write failing tests for endpoint inclusion, monotonicity, deterministic bytes, header validation, and out-of-domain rejection.**
- [ ] **Step 2: Implement the explicit fixed-point address mapping and oracle evaluation.** Use the same PyTorch dtype/reference operation documented in Task 1; make rounding and saturation code explicit.
- [ ] **Step 3: Generate the table and receipt.** Record source hashes, table hash, address width, entry count, and max oracle quantization error.
- [ ] **Step 4: Run unit tests and a Python oracle self-check over all table entries.**
- [ ] **Step 5: Commit.**

```bash
git add tools/exp_table tests/exp_table docs/results/2026-08-05-rc-exp-table.json artifacts/rc_exp_table.bin
git commit -m "Generate deterministic RC exponential table"
```

Gate: table bytes must be reproducible and the quantized table oracle must be the reference used by SV equivalence.

### Task 3: Integrate the table into generated SV and prove equivalence

**Files:**
- Modify: RC lowering/template that currently emits or requests `math.exp`
- Create: `tests/equivalence/test_rc_exp_table_sv.py`
- Create: `docs/results/2026-08-05-rc-exp-sv-equivalence.json`
- Modify: RTL closure manifest/support-file manifest as needed

**Interfaces:**
- SV table module: `exp_table_lookup(input logic [ADDR_W-1:0] addr, output logic [DATA_W-1:0] data)` with documented read latency.
- Test runner accepts table hash, RTL closure manifest hash, reset cycles, timeout, and deterministic test vectors.

- [ ] **Step 1: Write a failing Verilator test for reset, endpoint lookup, one-input output, and multiple-input sequencing.**
- [ ] **Step 2: Lower the exp op to the table lookup and emit the table/module support file explicitly.** Do not rely on Morty discovery.
- [ ] **Step 3: Build the verified RTL closure with Verilator.** Record source order, include paths, compiler flags, and hashes.
- [ ] **Step 4: Compare cycle-aligned SV outputs with the quantized Python oracle.** Report first mismatch, address, expected/actual value, and cycle.
- [ ] **Step 5: Run one-input, several-input, boundary, and randomized tests.** A timeout is a failed liveness result, not equivalence.
- [ ] **Step 6: Commit.**

```bash
git add tests/equivalence docs/results/2026-08-05-rc-exp-sv-equivalence.json
git commit -m "Prove RC exponential table equivalence in Verilator"
```

Gate: all selected tests pass with no mismatches and a finite completion bound; otherwise stop and fix semantics/liveness before DDR3 work.

### Task 4: Move the same table to host-modeled DDR3

**Files:**
- Modify: host DDR3 transport/model adapter
- Create: `tests/ddr3/test_rc_exp_table_ddr3.py`
- Create: `docs/results/2026-08-05-rc-exp-ddr3-equivalence.json`

**Interfaces:**
- The RTL-visible table address maps to a named DDR3 base address.
- Transport receipt records table hash, base address, burst/read latency, initialization ordering, and returned bytes.

- [ ] **Step 1: Write a failing transport test for table image initialization and readback.**
- [ ] **Step 2: Load the exact table bytes into the host DDR3 model and connect the lookup path.**
- [ ] **Step 3: Re-run the Task 3 vector suite, including delayed reads and reset.**
- [ ] **Step 4: Compare the DDR3-backed SV outputs against the same oracle and table hash.**
- [ ] **Step 5: Commit.**

```bash
git add tests/ddr3 docs/results/2026-08-05-rc-exp-ddr3-equivalence.json
git commit -m "Verify DDR3-backed RC exponential table"
```

Gate: DDR3 backing must be semantically identical to local-table backing; differences are transport bugs, not approximation tolerance.

### Task 5: Evaluate PEANO/QUARK-style approximation candidates

**Files:**
- Create: `tools/exp_table/benchmark_approx_exp.py`
- Create: `tests/exp_table/test_approx_exp.py`
- Create: `docs/results/2026-08-05-rc-exp-approx-benchmark.md`

**Interfaces:**
- Candidate API: `approx_exp(x, format_spec) -> y` plus declared domain, error bound, and hardware operation count.
- Benchmark output includes max/mean absolute and relative error, model output/token agreement, cycles, LUT/FF/DSP estimates, and table/DDR bandwidth.

- [ ] **Step 1: Implement PEANO-like Padé/range-reduced and QUARK-like base-2 shift/add candidates as software references first.**
- [ ] **Step 2: Test each candidate against the Task 1 domain and reject candidates with undocumented clipping or overflow.**
- [ ] **Step 3: Integrate only selected candidates into isolated SV variants; never replace the exact table path in-place.**
- [ ] **Step 4: Produce a comparison report and recommendation based on measured equivalence tolerance and resource/runtime data.**
- [ ] **Step 5: Commit.**

```bash
git add tools/exp_table tests/exp_table docs/results/2026-08-05-rc-exp-approx-benchmark.md
git commit -m "Benchmark approximate RC exponential implementations"
```

Gate: approximation is a separate performance result and may not invalidate or overwrite the exact-table equivalence evidence.
