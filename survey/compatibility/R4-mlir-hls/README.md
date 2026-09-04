# R4: Allo MLIR/HLS route

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M1_RTL`
- First observed gate: `SOURCE_CLOSURE`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/repository_audit.csv#repository_audit_id=REPO-PF-86FE8DBFB50CB04C`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The audit observes the general Allo tree but the paper marks the LLM artifact as a future release; no complete LLM RTL artifact is pinned.

Next bounded action: Obtain and audit the paper-specific LLM release before attempting Allo M0/M1 generation.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
