# Full TinyStories-1M compiler SV materialization

On 2026-08-29 the pinned full-model compiler route successfully realized
`tiny-stories-1m-baseline-float-sv` through
PyTorch ExportedProgram, Torch MLIR, Linalg, CF, Handshake, HW, SV MLIR, and
SystemVerilog.  The complete `main.sv` is 310,344,726 bytes, SHA-256
`04b090f78c358757dfca4b56f2d45ee1d05281a8ed9d803ee267ac3000fe9d06`, at Nix
output `/nix/store/rl80y735sa4jr5yqxb6280imqm4h50am-tiny-stories-1m-baseline-float-sv`.

This historical materialization does not satisfy the reference-guided
comparison gate.  At the build's source commit
`cc8d7e69edd6e7296be976d84f15b4fc5e4d90ac`, the compiler registry used
`roneneldan/TinyStories-1M` revision
`77f1b168e219585646439073245fe87e56b3023e`; the frozen kev-gpt contract pins
`ac533fb8b4f69c71894bf96badfe11e6294d9fcf` and a distinct quantized-package
identity.  The strict extractor therefore returned `contract_mismatch` and
made no slice artifact.  The current registry has since been repinned to
`ac533…9fcf`; a new full SV build and extraction are still required before any
comparison can proceed.

The next required decision is to authenticate a single common model revision
and package identity before extracting or comparing a transformer-block
token-step slice.  No Representative Core, PCIe, DDR3, transport, weights, or
optimization stage was changed for this materialization.

## Current-pin follow-up

The current flake pins the model source to
`ac533fb8b4f69c71894bf96badfe11e6294d9fcf`. An existing Nix output at
`/nix/store/29kyjiv04x0bq7xbf9nwqq025kkcyn5f-tiny-stories-1m-baseline-float-sv`
contains the same 310,344,726-byte `main.sv` (the same SHA-256 shown above).
The metadata receipt records that output and the current source pin.

An independent rebuild could not be rerun in this environment: `nix build`
failed before evaluation with
`cannot connect to socket at /nix/var/nix/daemon-socket/socket: Operation not permitted`;
`NIX_REMOTE=local` likewise failed because `/nix/var/nix/db/big-lock` is not
writable. Therefore the existing store path is recorded as an observed
candidate, not as independently rebuilt current-pin evidence. The strict
extractor still fails closed (`contract_mismatch`) because compiler metadata
does not carry the authenticated package and manifest hashes; no slice or
functional comparison is claimed.
