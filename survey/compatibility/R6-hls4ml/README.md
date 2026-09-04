# R6: hls4ml transformer route

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M1_RTL`
- First observed gate: `ARTIFACT_ATTRIBUTION`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/artifact_inventory.csv#project_family_id=PF-3DBBE522B68ECE13`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The paper audit found no attributed public project artifact for the transformer extension, so a generic upstream checkout cannot substitute.

Next bounded action: Attribute and audit the exact hls4ml transformer extension release; do not substitute generic hls4ml.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
