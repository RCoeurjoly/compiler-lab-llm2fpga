# R8: Cascade CPU/FPGA fallback control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M2_STATEFUL_DECODE`
- First observed gate: `CAUSAL_LM_COVERAGE`
- Failure code: `F_INTERFACE`
- Source evidence: `survey/build/repository_audit.csv#repository_audit_id=REPO-PF-E9C1300B04E80B95`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The frozen source has a BSD-2 licence despite GitHub's NOASSERTION SPDX classification, but the audited Cascade artifact is a Verilog virtualization control and contains no causal-LM prefill/decode or token-loop implementation.

Next bounded action: Add and audit a causal-LM kernel with persistent KV state before evaluating the fallback runtime.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
