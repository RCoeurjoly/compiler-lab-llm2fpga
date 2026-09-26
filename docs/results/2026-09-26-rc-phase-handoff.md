# Compiler-generated RC phase handoff ABI

The three authenticated W4A8 Representative Core phase artifacts were parsed
from their pinned exported PyTorch, flat-SCF and native-SV files. The typed
handoff builder verified all source/namespace hashes, semantic and RTL memory
geometries, initialized memory-image hashes, 237 readback words and the eight
cache-leaf transfers. The generated manifest from this diagnostic run is
`/tmp/rc-phase-namespace.3HMATU/handoff.json`; it must be packaged by Nix for
durable production use.
Its SHA-256 is `ddd135bdac56b23cdde324997cea16538945309d83b4c921556c722f14f8823c`;
the corrected three-phase ABI verification receipt has SHA-256
`18d6086caefd7a4b9a9c3e49a9adef25116f27c6b91cb049924d55e8e9763486`.

An important ABI correction was found: `arg_mem_0` contains **position IDs**,
not token IDs. The prompt token input is `arg_mem_31` in `prefill-8`; generated
token feedback enters `arg_mem_27` in `decode-8` and `decode-9`. Their cache
inputs are `arg_mem_28` through `arg_mem_31`. The real prompt image at prefill
port 31 is `[0, 1, 2, 3, 4, 5, 0, 1]`; the frozen decode token inputs are both
`[0]`. The prefill logits select the last six of 48 words, beginning at word
offset 42. The handoff map uses token destinations 27 and copies four raw
32-bit cache leaves from output ports 33–36 to input ports 28–31.

Each of the eight decode cache-input payload hashes matches the preceding
phase's frozen output-cache hash in the integrated PyTorch observation. The
legacy phase-ABI verifier previously mislabeled port 0 as the token input; it
now checks the real token ports and reports the position port separately.

This is a validated compiler-artifact **interface** and memory-image result,
not integrated generated-RTL simulation, PCIe ingress, DDR3 calibration,
FPGA fit, timing closure or board inference.
