# R1: compiler-lab MLIR/CIRCT control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M3_GENERIC_SYNTHESIS`
- First observed gate: `RTL_GENERATION`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB`
- Fixture: `M3-repository-fixture`
- Budget cap: `16` hours

The environment and capture/Linalg commands completed. The focused smoke suite's stale patches-directory assertion and the pinned pytest collection errors are preserved baseline diagnostics, not F_ENV. The first protocol-taxonomy blocker is RTL generation: the native-SV derivation's store-copied export script references the missing verify_calyx_f32_constant_bits.py helper. Independent lint and generic synthesis of a hash-pinned existing RC RTL then also failed; no RTL gate passed.

Next bounded action: In a separate compiler-lab change, supply the committed CALYX_VERIFY_F32_CONSTANT_BITS derivation input, then regenerate RTL before rerunning lint and synthesis.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
