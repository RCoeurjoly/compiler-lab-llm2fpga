# Task 4: exact serial-GEMV composition frontier

## Result

Diagnostic frontier, not a structural TinyStories composition.  The pure Task
4 derivation consumes the portable Torch successor receipt and derives the
complete ordered serial-GEMV callsite map from its legalized Torch MLIR.  The
generated wrapper is intentionally stopped at Calyx because it has independent
per-callsite memories and does not preserve Torch SSA activation/weight/result
dataflow or the non-GEMV computation boundaries.

The generated composition contains exactly 49 ordered `calyx.invoke` sites.
Its callsite map has four exact reusable descriptor shapes:

- `64 x 64`
- `256 x 64`
- `64 x 256`
- `50257 x 64`

No generic SCF lowering or reference RTL is used.  The composition receipt
binds the Torch input, callsite map, and compiler-owned Calyx composition by
byte count and SHA-256.  The dataflow adequacy check runs immediately after
that generation; because it proves the absence of required dataflow, no
translation, SV, Yosys, command, tool-version, or elapsed-time artifact is
accepted.  The final frontier binds the generator/verifier and Task 3 gate.

## Portable provenance and Nix closure

The historical Task 2 receipt is retained unchanged.  Task 4 instead consumes
the portable successor provenance chain, which binds content hashes rather
than a local absolute Nix output path.  The Torch MLIR is an explicit command
dependency of the composition derivation, not a `buildInputs` item: data files
must not be sourced as shell setup hooks.

The current diagnostic derivation is:

`tiny-stories-1m-exact-serial-gemv-sv`

Its verified immutable output is:

`/nix/store/m048sw8xsvyv2h0cm8ar2cp3jx64ixxg-tiny-stories-1m-exact-serial-gemv-sv`

The frontier receipt SHA-256 is
The result is a `calyx_frontier` diagnostic with empty SV/synthesis stages.
The composition receipt SHA-256 is
`27786630afe38d576cd8479ca36e5b7b53cede6acbf27b5a7c3d9fd11630603c`.

## Verification

- 9 Python tests passed, including red/green mutations that reject a four-gate
  map and a changed source offset against the 49-callsite Torch boundary.
- `timeout 7200 nix build --no-link -L .#tiny-stories-1m-exact-serial-gemv-sv`
  passed.
- Both composition and final frontier receipts independently verified.
- `timeout 1800 nix flake check --no-build -L` passed.

The accepted composition output contains only `callsites.json`,
`model.calyx.mlir`, and `receipt.json`; the integration regression proves the
absence of parsed MLIR, Futil, SV, Yosys, commands, tools, and elapsed-time
files.  A future repair must preserve actual Torch dataflow and non-GEMV
semantics before any translation, SV/Yosys, or inference claim.
