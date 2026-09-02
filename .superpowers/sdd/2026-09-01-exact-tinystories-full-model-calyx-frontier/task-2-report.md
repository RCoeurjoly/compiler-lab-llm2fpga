# Task 2 Report: Exact TinyStories Calyx Frontier

## Progress ledger

- 2026-09-02T10:10:17+02:00: recovery is active in `/home/roland/compiler-lab-llm2fpga/.worktrees/exact-tinystories-compiler` on branch `codex/exact-tinystories-compiler`.
- The inherited primary build remains authoritative and active: `nix` PID 2530843, runner PID 2530918, and `circt-opt` PID 2530919 are still live on the exact authenticated command for `.#tiny-stories-1m-kev-gpt-exact-calyx-frontier`.
- Latest live-process snapshot: `nix` elapsed 18:23:35, runner alive, `circt-opt` elapsed 18:23:34, CPU 20:01:14, RSS 853732 KB.
- The explicit autonomous ruling received during recovery is to preserve the primary run until the 24h wall-clock deadline of 2026-09-02T15:46:46+02:00, measured from its 2026-09-01T15:46:46+02:00 start. If it exits first, Task 2 proceeds from that exact result. If it remains live at the deadline, recheck PID and command identity, terminate only that exact process tree, preserve accessible logs/state, and classify the result as a deterministic 24h timebox/scalability frontier.
- The recovered Task 2 verifier and test are being committed independently before the primary result so the authenticated replay/test infrastructure is preserved under repo policy.

## Recovered verifier/test state

- `scripts/pipeline/verify_exact_tinystories_calyx_frontier.py` authenticates the predecessor exact normalized flat-SCF package, validates the Calyx-stage receipt, independently replays the pinned `circt-opt --lower-scf-to-calyx=top-level-function=main` command, compares the stable diagnostic/log/artifact binding, and emits a canonical self-hashed frontier receipt.
- `tests/test_exact_tinystories_calyx_frontier.py` covers provenance mutation rejection, canonical replay receipts, coherent forged-manifest rejection, valid artifact acceptance, and recovered minimization sidecar binding for bounded reduction evidence.

## Pending primary-result work

- Capture the exact primary result without rerunning it.
- Run the independent replay verifier against the authoritative bundle or record the 24h timebox/scalability frontier evidence if the explicit deadline is reached.
- Attempt bounded reduction only if the exact result is a stable compiler failure where reduction is applicable.
- Write final artifact JSON, result documentation, and replace this progress ledger with the complete Task 2 report before the final Task 2 commit.
