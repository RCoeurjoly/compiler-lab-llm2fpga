# R8: Cascade CPU/FPGA fallback control

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M2_STATEFUL_DECODE`
- First observed gate: `SOURCE_CLOSURE`
- Failure code: `F_SOURCE_MISSING`
- Source evidence: `survey/build/repository_audit.csv#repository_audit_id=REPO-PF-E9C1300B04E80B95`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The exact Cascade checkout is accessible and includes soc_system.qsys, but its DE10 Quartus project references the absent generated soc_system/synthesis/soc_system.qip hierarchy. The source requires vendor Qsys generation to produce that input. The later CMake and Yosys checks are retained as diagnostics; causal-LM coverage is not reached.

Next bounded action: Provide the generated DE10 QIP hierarchy or a reproducible, replaceable generation path before attempting fallback-route evaluation.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
