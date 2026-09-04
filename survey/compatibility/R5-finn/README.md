# R5: FINN transformer-adjacent route

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M1_RTL`
- First observed gate: `ARTIFACT_ATTRIBUTION`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/artifact_inventory.csv (no attributed FINN artifact row)`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The frozen deep-review work has no attributed and audited FINN source artifact.

Next bounded action: Attribute and audit the exact FINN transformer extension release; do not substitute generic FINN.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
