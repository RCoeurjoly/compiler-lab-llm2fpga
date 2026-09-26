# Compiler-generated RC phase composition

## Purpose and status

This design continues the active Representative Core qualification goal. Its
immediate result is one autonomous three-token compiler-generated RTL design
whose prefill and two cached-decode outputs match the frozen W4A8 PyTorch
contract. PCIe, UberDDR3, YPCB timing and three cold-start runs remain later
gates of the same goal.

The authenticated phase programs and their compiler-generated Calyx SV are
the implementation inputs. The existing monolithic integrated program is an
equivalence reference: its SV builds, but Verilator is killed during
elaboration, while nested Calyx conversion exceeds 900 seconds and 23 GiB.
The design therefore composes the three separately compiled phases.

## Contract

- Prompt: eight 64-bit token IDs `[0, 1, 2, 3, 4, 5, 0, 1]` for the fixed
  qualification run. The hardware interface accepts the eight IDs before
  `start` and retains the current reset/start/token-output ABI.
- Phase order: `prefill-8`, `decode-8`, `decode-9`. The second and third input
  token comes from the preceding phase's hardware logits by lowest-index
  greedy argmax.
- Cache handoff: copy the four raw `f32` output leaves of each phase into the
  next phase's four input leaves, preserving order, shape, byte values and
  valid positions. No arithmetic or model semantics are reimplemented in the
  wrapper.
- Outputs: three generated token IDs and the frozen 237-word readback ABI for
  logits and all cache leaves. The simulation gate compares every word with
  the integrated PyTorch observation.
- Implementation inputs: phase `exported.pt2`, flat SCF, Calyx-native SV,
  readback ABI, and their hashes. No kev-gpt accelerator RTL or handcrafted
  transformer datapath enters the build.

## Generated structure

The compiler-side generator validates each phase's semantic and RTL memory
ports, source digests, token/cache shapes and widths. It namespaces every
module definition and instantiation in the three native-SV sources so that
different generated helper modules cannot collide. It emits one instance of
each phase core and an RTL control shell.

The shell owns three states for compute, two bounded cache transfers, token
selection, reset and readback. Each phase's immutable weights and globals
are initialized from its own exported program and flat-SCF data. The shell
services the phase memory ports with the same registered read and completion
semantics as the passing per-phase simulation fixtures. Cache transfer uses
one element per cycle, allowing an eventual DDR3-backed provider without a
large parallel copy network. Phase launch waits for the previous phase's
token and cache transfer to finish.

The first artifact is a simulation shell. It is not a YPCB top or a DDR3
implementation. Its memory-port layout and readback map form the input to a
separate PCIe/UberDDR3 integration step; that step must preserve the validated
two-lane 333/83.33 MHz profile and existing transport ABI.

## Verification and failure behavior

1. Reject mismatched phase shapes, widths, cache leaf order, missing memory
   ports, duplicate module names, unsupported module syntax and inconsistent
   source digests before emitting SV.
2. Compile a tiny synthetic three-phase fixture to test reset, ordering,
   lowest-index ties, cache byte preservation and readback address mapping.
3. Simulate the real compiler-generated three-phase shell with bounded
   compile and run times. Require the exact three tokens and all 237 output
   words. On failure, retain logs and identify the first phase, port, word
   and expected/actual bits. A simulator memory kill is a tool failure, not a
   functional mismatch.
4. Only after the real simulation gate passes, connect phase memories to the
   already validated PCIe-to-UberDDR3 platform, prove image load/readback,
   calibration/BIST and multi-token operation, and then attempt timing-closed
   implementation and three cold-start board runs.

The compiler phase result may be too large to fit YPCB when three cores are
instantiated. Resource reports decide whether a later compiler optimization
must share or serialize the phase hardware; simulation success alone does not
claim fit.
