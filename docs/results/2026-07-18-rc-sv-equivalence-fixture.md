# V=6 RC SV equivalence fixture

The first image-backed fixture for the V=6 PT2E W8A8 RC is implemented by
`scripts/pipeline/run_rc_sv_equivalence.py`.  It targets the generated Calyx
`main_1` module, supplies every `arg_mem_N` service port, initializes
`arg_mem_0..20` from the frozen image, drives the eight token IDs through
`arg_mem_25`, and observes the six output codes written to `arg_mem_26`.

The generated top-level `main` remains a Calyx control-only wrapper.  The
functional memory-service module is `main_1`; this mapping is derived from the
flat-SCF ABI and the generated port declarations, not guessed from `done`.

## First execution

The fixture was run against:

- `tinystories-w8a8-rc-polynomial-exp-calyx-native-sv`
- the frozen `tinystories-w8a8-rc-reference-image`
- the four frozen corpus cases
- Verilator from the repository development shell

Verilator first rejected CIRCT's 613,929-character FSM assignment as one
preprocessor line.  The fixture removes comments and inserts lexical line
breaks; this does not change RTL semantics.  Verilator then rejected the
normalized design with:

```
memory exhausted
... fsm0_out == 13'd5339 ...
```

Therefore there is currently no PyTorch-versus-SV equivalence result.  The
failure is a simulator/parser scalability blocker, not evidence of a numerical
mismatch or a pass.  The next intervention is to obtain a partitioned or
otherwise simulator-tractable SV artifact, while preserving the same memory
image and `arg_mem_25`/`arg_mem_26` observable contract.

Icarus Verilog 13 was also tried as an independent simulator. It reported a
few compatibility diagnostics for the emitted SV and then independently failed
with `memory exhausted` while elaborating the same monolithic FSM. Switching
simulators alone therefore does not remove the blocker.

## Non-nested Calyx experiment

The repository now exposes `tinystories-w8a8-rc-polynomial-exp-sv-flat`, which
uses the same Calyx artifact without Calyx's `--nested` flag. It completed and
produced a valid SV artifact, but the result grew from 9,955,404 bytes to
18,894,272 bytes and retained the same `main`/`main_1` interface split. The
fixture then failed in Verilator with `memory exhausted` in the larger FSM.

Consequently, `--nested` is not the cause of the simulation scalability
blocker. The next intervention is structural partitioning or a different
backend emission strategy, not another simulator choice or a P&R run on an
unverified implementation.

## Simulation-front-end normalization

The fixture now applies a simulation-only normalization to the generated SV:
large scalar OR trees and wide FSM priority-ternary chains are emitted as
equivalent procedural assignments. Wide data-bus assignments are explicitly
excluded from the scalar rewrite. This removes the immediate Verilator parser
OOM, but the resulting model still requires a very large C++ compilation and
has not yet produced a runtime equivalence result. The normalization must not
be used as the synthesis/P&R artifact.

## CIRCT control-compilation probe

The pinned CIRCT pass `--calyx-remove-groups-fsm` was tested on the actual
`model.calyx.mlir`. It rejected the input because the control did not yet
contain exactly one FSM. Prepending the standard `--calyx-compile-control`
pass did not produce an artifact: `circt-opt` aborted with exit code 134 in
`CompileControlVisitor::visit(circt::calyx::SeqOp)`. The captured stack trace
identifies the assertion inside CIRCT's Calyx control compiler.

This rules out the obvious standard pass ordering for the current RC and gives
us a minimal upstream-relevant failure boundary: Calyx `seq` control from the
Torch/SCF lowering is not accepted by the pinned CIRCT control compiler.

## CIRCT HW/SV route

The repository's standard `calyx_to_hw_sv_no_handshake.sh` route was also
applied to the same RC Calyx MLIR. Its upstream-style preflight rejected the
input before SV generation:

```
calyx.seq_mem blocks direct Calyx-HW lowering
calyx.instance blocks direct Calyx-HW lowering
calyx.invoke blocks direct Calyx-HW lowering
```

This is a precise backend boundary. The route requires memory lowering or an
external-memory ABI, plus structuralizing/inlining component instances and
invokes. It is not an equivalence result and does not justify running P&R.

## No-synthesis Calyx experiment

The pinned Calyx command also supports omitting `--synthesis`, so the
repository exposes `tinystories-w8a8-rc-polynomial-exp-sv-no-synthesis`. The
derivation reached the native Calyx backend but produced no artifact or
incremental diagnostic output during a bounded several-minute run and was
terminated. This is evidence that omitting synthesis is not currently a fast
or usable equivalence route for this RC; it is not a success claim.
