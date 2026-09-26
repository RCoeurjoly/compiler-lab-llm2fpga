# Compiler-generated RC three-phase equivalence

Status: **exact generated-RTL simulation pass**. This is not PCIe, UberDDR3,
FPGA-fit, timing, bitstream, or board-inference evidence.

The Nix target `tinystories-w4a8-rc-serving-phase-composed-simulation` built
the three authenticated W4A8 Representative Core phase programs through the
pinned PyTorch → MLIR → SCF → Calyx → SystemVerilog route. A compiler-side
generator namespaced those generated phase cores and emitted the token/cache
handoff shell; no kev-gpt or handwritten transformer arithmetic is in the
simulated design. The shell consumed prompt IDs `[0, 1, 2, 3, 4, 5, 0, 1]`,
selected each next token from hardware logits, and copied the four raw `f32`
cache leaves into the next phase.

The immutable Nix output is
`/nix/store/3p2v5hlrg6ar8vr5x2pylj0ywdk8ak93-tinystories-w4a8-rc-serving-phase-composed-simulation`.
Its `report.json` (SHA-256
`fde50bcc0e1d330000a511b16cb64489faf2ae3ebf2ec52640dae918edec191a`)
records:

| Check | Observed result |
| --- | --- |
| Verilator build | exit 0, 1288.47 s, one C++ job, 2700 s bound |
| Simulation | exit 0, 715.14 s, 900 s bound |
| Tokens | expected and actual `[0, 0, 4]` |
| Readback | 237/237 exact words, zero mismatches |
| Simulation cycles | 654,936 |
| Raw `readback.hex` SHA-256 | `60110f1629a17ae8c0cba430b2956c5a20f35083ad27c3aa670af2cd0b2a8455` |
| Generated shell SHA-256 | `16a5d8fcbdd264ab4543c4fa2651845dbf2cc94e2ef2154c00681f1de675d954` |
| Frozen observation SHA-256 | `97a7f335a15fb99226a8e29bdeff48944fc498fa45756699db121cadfd4b5e52` |

The manifest and package receipts are in the output report. Its source table
binds all three namespaced compiler SV files. Verilator received simulation-only
normalized copies *after* checking the original file hashes; normalization
splits oversized generated source lines but does not change the model or RTL
operations. The manifest preserves actual 64-bit address pins on generated
zero-extent placeholder memories; the earlier one-bit shell connections have
been corrected.

The first Nix attempt used four parallel C++ jobs and retained a
`compile_failure` report at
`/nix/store/jfi06my3qdcks4dljnrf36nz8bn28mq1-tinystories-w4a8-rc-serving-phase-composed-simulation`:
`cc1plus` was killed during object compilation. Only build scheduling and its
time bound changed for the passing run. A separate local run of the same
generated phase composition had already produced the identical raw readback
SHA-256. The Nix derivation intentionally succeeds when it has written a
failure receipt, so acceptance requires inspecting `report.json`, not merely
the `nix build` exit code.

Next, classify immutable versus mutable phase memories against this exact
handoff manifest, connect immutable reads to the existing PCIe-loaded
UberDDR3 provider, and prove load/readback plus the same token sequence before
attempting YPCB synthesis and routing. The earlier 146-port integer-RC DDR3
mapping is a different ABI and is not reusable without a fresh compatibility
audit. Three instantiated phase cores may also exceed board resources; fit
must be measured before deciding whether compiler-generated hardware sharing
is required.
