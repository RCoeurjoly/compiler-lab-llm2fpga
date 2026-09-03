# Task 4: exact serial-GEMV composition frontier

## Result

Green structural frontier.  The pure Task 4 derivation consumes the portable
Torch successor receipt, derives the complete ordered serial-GEMV callsite map
from its legalized Torch MLIR, emits a compiler-owned Calyx composition, and
exports and synthesizes SystemVerilog.

The generated composition contains exactly 49 ordered `calyx.invoke` sites.
Its callsite map has four exact reusable descriptor shapes:

- `64 x 64`
- `256 x 64`
- `64 x 256`
- `50257 x 64`

No generic SCF lowering or reference RTL is used.  The composition receipt
binds the Torch input, callsite map, Calyx MLIR, SV, and Yosys report by byte
count and SHA-256.  The final frontier receipt accepts SV only when it is in
the compiler closure.

## Portable provenance and Nix closure

The historical Task 2 receipt is retained unchanged.  Task 4 instead consumes
the portable successor provenance chain, which binds content hashes rather
than a local absolute Nix output path.  The Torch MLIR is an explicit command
dependency of the composition derivation, not a `buildInputs` item: data files
must not be sourced as shell setup hooks.

The final derivation is:

`tiny-stories-1m-exact-serial-gemv-sv`

Its verified immutable output is:

`/nix/store/18mpbqkmlbizn2v1km7r6jrrafssfw0g-tiny-stories-1m-exact-serial-gemv-sv`

The frontier receipt SHA-256 is
`c8d825b25e77925dbda21208b0913dcfd92f8d128dc2d1bd66826cd4a8f181c0`.
The composition receipt SHA-256 is
`92fa3ddcad23167c60b8cbb0e9765ae1a1d0e2de49d0cf89c28251b203c9ccc5`.

## Verification

- 7 Python tests passed, including a red/green mutation test that rejects a
  four-gate map claiming the 49-callsite Torch boundary.
- `timeout 7200 nix build --no-link -L .#tiny-stories-1m-exact-serial-gemv-sv`
  passed.
- Both composition and final frontier receipts independently verified.
- `timeout 1800 nix flake check --no-build -L` passed.

The Calyx exporter warns that the generated entrypoint has non-interface memory
ports, so this structural SV/Yosys result is not a token-level simulation or
board-inference claim.  Completing the non-GEMV model semantics and a
simulation-ready top-level remains a subsequent task.
