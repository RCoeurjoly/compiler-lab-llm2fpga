# R3: Mase compiler route

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M1_RTL`
- First observed gate: `SOURCE_PIN`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/artifact_inventory.csv (no attributed Mase artifact row)`
- Fixture: `M0-operators`
- Budget cap: `16` hours

Task 5 contains no paper-attributed, commit-pinned Mase source artifact.

Next bounded action: Attribute a Mase release to a frozen survey work and audit its licence and immutable source commit.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
