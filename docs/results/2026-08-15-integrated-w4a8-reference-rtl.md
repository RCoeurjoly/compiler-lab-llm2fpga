# Integrated W4A8 reference RTL qualification

Date: 2026-08-15

Status: **unqualified**. The compiler pipeline now emits one integrated,
stateful three-phase W4A8 design and a transaction shell, but this host cannot
complete Verilator elaboration of the generated closure. Consequently no
PyTorch-versus-RTL comparison or reset replay has run, and this result must not
be described as functionally verified RTL.

## What this artifact is

This candidate is a single PT2E `ExportedProgram` covering prefill, decode at
context 8, and decode at context 9. It has 18 outputs: three selected tokens
and, for each phase, logits plus four cache tensors. The decode phases consume
the caches produced by the preceding phase in the same exported computation.
The export contains 489 quantize/dequantize nodes and preserves the frozen
phase quantization parameters.

The frozen prefill result agrees with the earlier phase-specific W4A8 PT2E
oracle. The integrated chained decode is the authoritative reference for this
candidate: the older phase-specific decode fixtures consumed floating-point
caches and therefore did not specify the intended quantized, stateful boundary.

The originally validated exported-program serialization had SHA-256
`8f8dcc4925836d91c23d9d166b0bfbf39d7db1ed8fd09ae249c1fc487eadf21a`.
The authoritative shell rebuild receipt records
`e7221995e59fb92e65a013d88b226fabde89dc01df94cb1f9d1e2fcdaddc0145`.
PyTorch serialization is not byte-stable across these rebuilds, so these are
provenance hashes, not a claim that serialized bytes are a semantic identity.

## Wholesale compiler lowering

The full integrated program was lowered through the existing
PT2E -> Torch MLIR -> Linalg -> SCF -> flattened SCF -> Calyx -> native
SystemVerilog route. This is not a hand-written behavioral substitute.

Three in-scope lowering defects had to be corrected:

- one-dimensional `memref.copy` operations were not lowered;
- static non-identity `memref.collapse_shape` stride mappings were rejected;
- nested `memref.reinterpret_cast` offsets were accumulated twice, although
  the nested offset is already absolute.

The default optimized nested Calyx route exhausted the machine after roughly
56 minutes at approximately 30.4 GB resident memory (RAM and swap exhausted).
The reproducible bounded route is `compile-repeat`, `no-opt`, synthesis mode,
with non-nested emission. It completed in 22 minutes 18 seconds with
13,802,996 KB peak resident memory.

Native generated SystemVerilog artifact:

- authoritative store path:
  `/nix/store/9959pm7dvmfppk5caapz7m0j6ck8pr1x-tinystories-w4a8-rc-serving-integrated-calyx-native-sv`
- `sv/main.sv`: 50,861,718 bytes and 1,657,616 lines
- SHA-256:
  `7ccdfaa3e4ddff061e4476b6e5dfa66f9ee43b254c42cd4f5c7a128c3447fafb`
- manifest status: `ok`; receipts include floating-point constant bits and
  div/sqrt handshake checks.

## Integrated transaction shell

The generated `main_1` module exposes 382 Calyx memory interfaces. The
flattened semantic ABI contains 74 memories: inputs 0--55, prompt memory 55,
and the 18 results in memories 56--73. The public shell
`rc_serving_w4a8_integrated_reference` owns all 382 memories and provides:

- clock and reset;
- indexed prompt writes;
- `go`, `busy`, and `done` transaction control;
- sticky `protocol_error` reporting;
- addressed result readback with request/valid handshake.

The manifest exposes 237 result words across all 18 semantic outputs. Exactly
77 frozen input/global memories are initialized from hexadecimal files; the
prompt, result, and scratch memories are explicitly zero-initialized. Focused
unit tests verify the ABI mapping, initialization coverage, result manifest,
and protocol guards.

The authoritative Nix build completed successfully at commit `099d0c5`:

- store path:
  `/nix/store/9qcz1fgpkgh6x2lbs4c9f5bqhv7aknzc-tinystories-w4a8-rc-serving-integrated-shell`
- receipt schema/status: `rc-serving-w4a8-integrated-shell-v1` / `ok`
- shell SHA-256:
  `73bcbdbde16bd2a460b9741d55d36d3db1294cd9f71dc86c67dd137dc8491c20`
- receipt counts: 382 RTL memories, 74 semantic memories, 77 initialized
  memories, 18 output memories, and 237 readback words
- filesystem cross-check: 77 `mem*.hex` files and 77 `$readmemh` calls.

## Verilator qualification attempt

Raw non-nested SystemVerilog first failed on a generated expression containing
more than 40,000 preprocessor tokens; the parser exhausted memory at about
1.76 GB. Applying the synthesis-frontend normalizer before the simulation
normalizer removed 8,057 assertion blocks, one duplicate square-root wire, and
one duplicate request declaration, and split the giant generated ternaries.

The normalized full closure then parsed and reached Verilator elaboration, but
the operating system killed both attempts:

| Attempt | Result | Elapsed | Peak RSS |
|---|---:|---:|---:|
| Flat Verilator lint | signal 9 | 3:48.88 | 29,327,480 KB |
| `--hierarchical` lint | signal 9 | 3:50.75 | 30,392,760 KB |

Only timescale warnings preceded the kills; no source-language error was
reported. This is nevertheless a hard qualification blocker on the available
32 GB host.

## Qualification boundary

The following evidence exists:

- integrated eager and PT2E oracle agreement;
- frozen prefill compatibility with the earlier W4A8 phase reference;
- successful wholesale lowering to one generated SystemVerilog design;
- a deterministic shell ABI with focused generator/unit tests.

The following required evidence does **not** exist:

- completed Verilator build of the integrated closure;
- cycle-level simulation against the frozen PT2E/PyTorch 18-output manifest;
- ordered reset A/B/A replay on RTL;
- an RTL equivalence receipt.

Therefore this candidate is a generated integrated RTL **reference candidate**,
not yet the verified RTL reference needed for subsequent manual optimization.
The earlier W8A8 result and the three separate W4A8 phase checks do not close
this gap. The next qualification attempt needs either a higher-memory build
host or a structure-preserving partition/compilation strategy whose assembled
simulation still exercises this one transaction and the same 18-output oracle.
