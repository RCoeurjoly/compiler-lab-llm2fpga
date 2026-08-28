# Full TinyStories-1M compiler SV materialization

On 2026-08-29 the pinned full-model compiler route successfully realized
`tiny-stories-1m-baseline-float-sv` through
PyTorch ExportedProgram, Torch MLIR, Linalg, CF, Handshake, HW, SV MLIR, and
SystemVerilog.  The complete `main.sv` is 310,344,726 bytes, SHA-256
`04b090f78c358757dfca4b56f2d45ee1d05281a8ed9d803ee267ac3000fe9d06`, at Nix
output `/nix/store/rl80y735sa4jr5yqxb6280imqm4h50am-tiny-stories-1m-baseline-float-sv`.

This does not yet satisfy the reference-guided comparison gate.  The compiler
registry pins `roneneldan/TinyStories-1M` revision
`77f1b168e219585646439073245fe87e56b3023e`; the frozen kev-gpt contract pins
`ac533fb8b4f69c71894bf96badfe11e6294d9fcf` and a distinct quantized-package
identity.  The strict extractor therefore returned `contract_mismatch`, made
no slice artifact, and the comparison receipt remains incomplete.

The next required decision is to authenticate a single common model revision
and package identity before extracting or comparing a transformer-block
token-step slice.  No Representative Core, PCIe, DDR3, transport, weights, or
optimization stage was changed for this materialization.
