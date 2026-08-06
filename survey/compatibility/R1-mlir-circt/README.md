# R1: compiler-lab MLIR/CIRCT control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M3_GENERIC_SYNTHESIS`
- First observed gate: `SMOKE_TESTS`
- Failure code: `F_ENV`
- Source evidence: `survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB`
- Fixture: `M3-repository-fixture`
- Budget cap: `16` hours

Capture and Linalg lowering completed, but the focused smoke suite failed 18/19 at a stale patches-directory assertion. Pinned pytest collection also reported the preserved Python 3.11 f-string SyntaxError and submodule import errors. The representative-core SV derivation failed because the store-copied export script resolved an unexported verification helper to a nonexistent /nix/store path. Independent lint and generic synthesis of the hash-pinned existing RC RTL then failed in Verilator and Yosys; no RTL gate passed.

Next bounded action: In a separate compiler-lab change, repair the baseline test collection and missing CALYX_VERIFY_F32_CONSTANT_BITS derivation input, then regenerate RTL before rerunning lint and synthesis.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
