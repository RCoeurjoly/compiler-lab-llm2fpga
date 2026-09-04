# R7: open reusable accelerator control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M2_STATEFUL_DECODE`
- First observed gate: `SOURCE_CLOSURE`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/artifact_inventory.csv#project_family_id=PF-4EBDD47F47E94583`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The exact MIT checkout is accessible, but its hardware-generation templates depend on elastic-ai.creator through a mutable git branch rather than a source-pinned release; the checked-in VHDL templates remain unrendered. The later import and GHDL checks are retained as diagnostics, while source closure is the first failed gate.

Next bounded action: Pin and include the exact ElasticAI.Creator source/template revision needed to render complete VHDL before attempting operator triage.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
