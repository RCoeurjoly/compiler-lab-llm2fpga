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

The corrected simulation output is
`/nix/store/4y264sijpfgly9v1l2i3fd463rk4aa3r-tinystories-w4a8-rc-serving-phase-composed-simulation`.
Its `report.json` SHA-256 is
`ffa2dcd1f40b30161b5126ccbfcfabb01e726e85532ddbab81aa684037b14d45`.
The separate **fail-closed** Nix target
`tinystories-w4a8-rc-serving-phase-composed-acceptance` produced
`/nix/store/wzdb796j6mhp1vpcb2yvrxv61s02s9hg-tinystories-w4a8-rc-serving-phase-composed-acceptance/acceptance.json`
(SHA-256 `89e1ace4939d16b0e2a696d0bb0f15853052aba51cc04426c251307f16c628c0`).
It reports `status=accepted` and records:

| Check | Observed result |
| --- | --- |
| Verilator build | exit 0, 1286.16 s, one C++ job, 2700 s bound |
| Simulation | exit 0, 731.89 s, 900 s bound |
| Tokens | expected and actual `[0, 0, 4]` |
| Cache handoff | all 136 words checked at `RUN1`/`RUN2`; both generated token inputs checked |
| Readback | 237/237 exact words, zero mismatches |
| Simulation cycles | 654,936 |
| Raw `readback.hex` SHA-256 | `60110f1629a17ae8c0cba430b2956c5a20f35083ad27c3aa670af2cd0b2a8455` |
| Generated shell SHA-256 | `047b230e7fe5437ddfa529cd38f1a4ba2a1cb6c7f64e05ba719894cf97743156` |
| Frozen observation SHA-256 | `97a7f335a15fb99226a8e29bdeff48944fc498fa45756699db121cadfd4b5e52` |

The manifest and package receipts are in the output report. Its source table
binds all three namespaced compiler SV files. Verilator received simulation-only
normalized copies *after* checking the original file hashes; normalization
splits oversized generated source lines but does not change the model or RTL
operations. The manifest preserves actual 64-bit address pins on generated
zero-extent placeholder memories; the earlier one-bit shell connections have
been corrected.

The first passing Nix diagnostic had preloaded the frozen decode token/cache
examples into dynamic USER_INPUT memories. Its token and readback match was
real, but it did **not** independently establish that the shell transferred
cache values. The corrected handoff manifest has no initialization images for
prefill token port 31 or decode token/cache ports 27–31. Its testbench checks
all 136 destination cache words against preceding phase outputs at the phase
boundaries and checks both generated token inputs. A small synthetic generated
RTL run also exercised the same monitor with nonzero token sequence
`[2, 3, 4]`. The corrected real run retained the same raw readback hash.

The first Nix attempt used four parallel C++ jobs and retained a
`compile_failure` report at
`/nix/store/jfi06my3qdcks4dljnrf36nz8bn28mq1-tinystories-w4a8-rc-serving-phase-composed-simulation`:
`cc1plus` was killed during object compilation. Only build scheduling and its
time bound changed for the first passing diagnostic run. The simulation
derivation intentionally succeeds when it has written a failure receipt;
`nix build .#tinystories-w4a8-rc-serving-phase-composed-acceptance` is the
fail-closed gate and rejects a failed status, nonzero runner exit, incomplete
handoff observation, wrong tokens, or missing/reordered raw readback words.

Next, classify immutable versus mutable phase memories against this exact
handoff manifest, connect immutable reads to the existing PCIe-loaded
UberDDR3 provider, and prove load/readback plus the same token sequence before
attempting YPCB synthesis and routing. The earlier 146-port integer-RC DDR3
mapping is a different ABI and is not reusable without a fresh compatibility
audit. Three instantiated phase cores may also exceed board resources; fit
must be measured before deciding whether compiler-generated hardware sharing
is required.
