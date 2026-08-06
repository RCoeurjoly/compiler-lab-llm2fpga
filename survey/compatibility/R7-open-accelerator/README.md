# R7: open reusable accelerator control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M2_STATEFUL_DECODE`
- First observed gate: `CAUSAL_LM_COVERAGE`
- Failure code: `F_INTERFACE`
- Source evidence: `survey/build/artifact_inventory.csv#project_family_id=PF-4EBDD47F47E94583`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The audited MIT source is a time-series transformer and does not provide a causal-LM prefill/decode, KV-cache, or token-generation interface.

Next bounded action: Select a licensed causal-LM accelerator with a prefill/decode and persistent-KV interface.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
