# Task 3 report: compiler-generated defined serial-GEMV Calyx component

## Outcome

### Review repair round 1 (in progress)

The initial component was structurally valid but did not drive its memory
addresses/writeback or represent all descriptor rows.  The generator now emits
runtime row, output, and input-index loops; flat activation/weight/result
address registers and width slices; operand-read completion; an explicit
`std_mult_pipe` completion group before wrapping i64 accumulation; and result
data/write enable/address assignments.  A new rows=4, outputs=50,257,
inputs=64 regression checks all of those emitted operations and the emitted
control-bound trace summary.  This repair is not yet a completed provenance
gate: the next step is to export the declared-shape validation through flake
and bind the resulting artifact/receipt rather than relying on a manual run.

That gate is now exported as
`.#tinystories-1m-exact-serial-gemv-calyx-gate`.  Its self-hashed receipt
(`3ff6cc04079e8eea3989eb8b8b9fec3972a71ba113dbf24129ef5ca31f92efe2`)
binds Calyx MLIR, parsed MLIR, Futil, SV, Yosys stats, trace summary, and
provenance for 1x64x64, 1x256x64, 1x64x256, and actual 4x50257x64.  The
receipt is generated and independently verified inside the Nix derivation.
Repair round 2 binds each trace's emitted-control SHA-256 and first/last
schedule bounds to a recomputation from `model.calyx.mlir`; changing either
the Calyx control path or those trace claims and recomputing only the receipt
self-hash is rejected.

Implemented the bounded descriptor-to-Calyx lowerer.  It consumes only one
static legalized `llm2fpga.serial_gemv` descriptor, requires
`mac_order = "ascending_i64_wrap"`, and emits a compiler-generated wrapper
with a `calyx.invoke` plus a defined `@llm2fpga_serial_gemv_M_K` component.
It neither reads generic SCF nor imports, wraps, or copies kev-gpt RTL.

The generated component has compiler-owned activation, weight, and result
memories; explicit signed-i64 accumulator, input-index and output-index
registers; a pipelined i64 multiplication cell and i64 add cells; and nested
output/input `calyx.while` control.  The input loop condition is the declared
input count, so the schedule is ascending `k = 0 .. K-1` for each output.

## Evidence

- New lowerer: `scripts/pipeline/lower_exact_serial_gemv_to_calyx.py`.
- New exact 1x64 by 64x64 generated fixture:
  `reproducers/tinystories-1m-exact-serial-gemv/calyx-component.mlir`.
- New contract suite:
  `tests/test_tinystories_1m_serial_gemv_calyx.py`.
- The 64x64 ordered address/data trace contains 4,096 records and has canonical
  hash `75f9d4bea7667be6a897a2171dcb3a9f4563124cc112c05fd4b2e09f43e1b932`.
  The new streaming hash produces byte-identical canonical JSON without
  materializing a model-sized trace.
- The 50,257x64 LM-head trace hashes in 12.697 seconds with bounded memory:
  `2f87fc89252890a2fd3889f4cb63f0b9e5198b494c71ef08f56fab9e7fe64fe9`.
- Pinned CIRCT `/nix/store/b9p48l2nrw1c6zncc6f86jd9nr611x7z-circt-1.144.0g20260331_5dc62fe`
  parses the generated fixture.  The supported i64 multiplier is
  `calyx.std_mult_pipe`; `calyx.std_mult` is not a registered operation in this
  tool and was not used.
- Calyx 0.7.1 exports the 64x64 fixture to SV, and Yosys 0.66 accepts it with
  `read_verilog -sv; hierarchy -check; stat`.
- The same complete Calyx-to-SV/Yosys sequence passed for 256x64 and 64x256
  declarations.  It is capped at 1,800 seconds per command in the new Nix
  helper `mkExactSerialGemvCalyxDerivation`.
- The required 50,257x64 declared-shape gate passed in a clean bounded run:
  lowerer 24 seconds, CIRCT parse under one second, Calyx export under one
  second, native Calyx SV emission under one second, and Yosys syntax/stat
  under one second.  The generated trace-summary SHA-256 is
  `585dbc6f29729e008122a52e6c7fb0c9827c2af0e67e00c149c6a80c66e91ba4`;
  generated SV SHA-256 is
  `af7b58a3c859e0585224a4810e7e72151c55c928d806e3e7abf5d8d9968c6a82`.
- `timeout 1800 nix develop -c python -m unittest
  tests/test_tinystories_1m_serial_gemv_calyx.py -v`: PASS, 5/5.
- `nix flake check --no-build -L`: PASS.

## Bounded large-shape repair

The initial 50,257x64 check exposed the diagnostic trace itself as the problem:
a list of 3,216,448 Python dictionaries is not an acceptable development
artifact.  That path was replaced with the streaming canonical hash above, then
the exact large-head component was rerun through the full bounded
Calyx-to-SV/Yosys gate successfully.  This remains one descriptor component;
full-model composition and provenance closure are Task 4.  No full-model
compiler run was started.

## Scope retained

No DDR3, PCIe, Representative Core, arbitrary-PyTorch route, generic SCF path,
or reference-derived RTL was added.  This is a structural compiler-stage
artifact, not a claim of frozen 16-token or board inference equivalence.

## Fixed-point GEMV/requantize follow-on: diagnostic (2026-09-03)

This section records the distinct Task 3 follow-on from
`docs/superpowers/plans/2026-09-03-fixed-point-gemv-requantize-slice.md`.
It must not be confused with the descriptor-only structural gate above.

`scripts/pipeline/lower_fixed_point_schema_to_calyx.py` consumes the approved
Task 2 schema receipt only through `verify_schema`.  That structurally binds
the Task 1 fixture, five raw producer bindings, the exact 4x64/64x64 shapes,
and `nearest_ties_away_from_zero` / signed / saturating i8 requantization.
The generated Futil has explicit activation, weight, input-scale,
weight-scale, output-scale, and result memories plus accumulator, multiply,
add, and named `load_activation`, `gemv_step`, and `requantize` control.

TDD passed:

- the red test first failed because the new lowerer did not exist;
- `tests/test_tinystories_1m_fixed_point_schema_calyx.py` now passes 2/2;
- its ordered value trace reproduces all 256 captured accumulator values and
  both captured requantized arrays; and
- a forged `toward_zero` rounding rule is rejected before lowering.

The bounded compiler gate also passed using the dynamically resolved pinned
`.#calyx` package: Calyx 0.7.1 exported generated Futil to `main.sv` (39,397
bytes) and Yosys 0.66 accepted it with
`read_verilog -sv; hierarchy -top main -check; stat`.

This is intentionally a **diagnostic, not a semantic-Calyx success**.  The
ordered value trace is an exact schema oracle, not output observed from an SV
simulation.  The generated control currently reads one memory operand pair;
it does not yet materialize all fixture loads, the 4x64x64 ordered MAC loop,
wide signed requantization, saturation, or result-memory writeback.  A
Verilator/Calyx simulation would therefore have no valid fixture result to
compare and was not run or claimed.  The first functional frontier is to
lower those actual logical-SSA dataflows without reducing the widened
fixed-point arithmetic to the available 64-bit primitive.  No SCF, copied RTL,
DDR3, PCIe, or Representative Core path was introduced.
