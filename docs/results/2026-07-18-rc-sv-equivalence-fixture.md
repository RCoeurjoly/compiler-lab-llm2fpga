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
