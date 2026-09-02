# Task 2 Report: Exact TinyStories Calyx Frontier

## Progress ledger

- 2026-09-02T10:10:17+02:00: recovery is active in `/home/roland/compiler-lab-llm2fpga/.worktrees/exact-tinystories-compiler` on branch `codex/exact-tinystories-compiler`.
- The inherited primary build remains authoritative and active: `nix` PID 2530843, runner PID 2530918, and `circt-opt` PID 2530919 are still live on the exact authenticated command for `.#tiny-stories-1m-kev-gpt-exact-calyx-frontier`.
- Latest live-process snapshot: `nix` elapsed 18:23:35, runner alive, `circt-opt` elapsed 18:23:34, CPU 20:01:14, RSS 853732 KB.
- The explicit autonomous ruling received during recovery is to preserve the primary run until the 24h wall-clock deadline of 2026-09-02T15:46:46+02:00, measured from its 2026-09-01T15:46:46+02:00 start. If it exits first, Task 2 proceeds from that exact result. If it remains live at the deadline, recheck PID and command identity, terminate only that exact process tree, preserve accessible logs/state, and classify the result as a deterministic 24h timebox/scalability frontier.
- The recovered Task 2 verifier and test are being committed independently before the primary result so the authenticated replay/test infrastructure is preserved under repo policy.
- A later autonomous ruling clarified that a deadline termination is not a compiler diagnostic and must not be represented as `compiler_frontier`. The verifier now has a separate `calyx_scalability_frontier` receipt path for signed 24h timebox evidence, binding the original command/input/tool, start and deadline timestamps, wall/CPU/RSS observations, no-output observations, process identity snapshots, and the termination signal.

## Scaling/root-cause evidence to bind after deadline if needed

- Exact pre-Calyx input: 15,748,461 bytes, 293,972 lines.
- Operation-scale counts supplied during monitoring: 42,558 `scf.for`, 102,229 `arith.`, 106,621 `memref.`, one function, zero `scf.if`, zero `linalg`.
- Loop-shape analysis supplied during monitoring: 42,558 loops normalize to 274 structural forms. The largest repeated forms are 4,155 vector-add inner loops, 2,040 i64 multiply/store loops over 1024x16384, 2,016 i64 multiply/store loops over 256x4096, and 1,600 select/store loops.
- Live-resource observation at approximately 18.5h: `circt-opt` remained CPU-active at roughly 108% CPU and about 820 MiB RSS with no candidate output observed. This supports a compiler-scaling frontier rather than a transport or I/O failure if the run reaches the 24h timebox.

## Recovered verifier/test state

- `scripts/pipeline/verify_exact_tinystories_calyx_frontier.py` authenticates the predecessor exact normalized flat-SCF package, validates the Calyx-stage receipt, independently replays the pinned `circt-opt --lower-scf-to-calyx=top-level-function=main` command, compares the stable diagnostic/log/artifact binding, and emits a canonical self-hashed frontier receipt.
- `scripts/pipeline/verify_exact_tinystories_calyx_frontier.py` also authenticates signed 24h timebox evidence with a distinct `tinystories-1m-exact-calyx-scalability-frontier-v1` receipt. That path intentionally has no compiler diagnostic and no replay claim.
- `tests/test_exact_tinystories_calyx_frontier.py` covers provenance mutation rejection, canonical replay receipts, coherent forged-manifest rejection, valid artifact acceptance, recovered minimization sidecar binding for bounded reduction evidence, and RED/GREEN mutation coverage for the new timebox scalability-frontier evidence path.

## Pending primary-result work

- Capture the exact primary result without rerunning it.
- Run the independent replay verifier against the authoritative bundle or record the 24h timebox/scalability frontier evidence if the explicit deadline is reached.
- Attempt bounded reduction only if the exact result is a stable compiler failure where reduction is applicable.
- Write final artifact JSON, result documentation, and replace this progress ledger with the complete Task 2 report before the final Task 2 commit.
