# Task 3 report: compiler-generated defined serial-GEMV Calyx component

## Outcome

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
