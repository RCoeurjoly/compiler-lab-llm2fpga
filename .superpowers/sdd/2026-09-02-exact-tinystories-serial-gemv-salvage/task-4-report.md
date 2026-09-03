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
binds the Torch input, callsite map, Calyx MLIR, SV, Yosys report, actual
command list, tool-version list, and elapsed-time record by byte count and
SHA-256.  The final frontier also binds the generator/verifier and Task 3 gate
in its compiler closure.

## Portable provenance and Nix closure

The historical Task 2 receipt is retained unchanged.  Task 4 instead consumes
the portable successor provenance chain, which binds content hashes rather
than a local absolute Nix output path.  The Torch MLIR is an explicit command
dependency of the composition derivation, not a `buildInputs` item: data files
must not be sourced as shell setup hooks.

The current diagnostic derivation is:

`tiny-stories-1m-exact-serial-gemv-sv`

Its verified immutable output is:

`/nix/store/mkl5svq1vv32ljqkq1f1cqj9fmdn97am-tiny-stories-1m-exact-serial-gemv-sv`

The frontier receipt SHA-256 is
`8f6263181aa6b408051c3f8c937d87583392d6a30f52910e143eb359caee4987`.
The composition receipt SHA-256 is
`9fc160b1709d30099ee51f89b950cb0cecb28973f4116bb8245d0f72a4e87f0a`.

## Verification

- 8 Python tests passed, including red/green mutations that reject a four-gate
  map and a changed source offset against the 49-callsite Torch boundary.
- `timeout 7200 nix build --no-link -L .#tiny-stories-1m-exact-serial-gemv-sv`
  passed.
- Both composition and final frontier receipts independently verified.
- `timeout 1800 nix flake check --no-build -L` passed.

The Calyx exporter warning about non-interface memory ports is additional
evidence that the prior SV/Yosys output must not be promoted.  The current
frontier receipt records `calyx_frontier` and leaves SV/synthesis empty.  A
future repair must preserve actual Torch dataflow and non-GEMV semantics before
any SV/Yosys or inference claim.
