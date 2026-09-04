# R2: FlightLLM parameterized RTL artifact

- Status: `STOPPED`
- Decision: `INELIGIBLE`
- Expected stage: `M2_STATEFUL_DECODE`
- First observed gate: `SOURCE_CLOSURE`
- Failure code: `F_VENDOR_IP`
- Source evidence: `survey/build/artifact_inventory.csv#project_family_id=PF-7FF210B343FEAC43`
- Fixture: `M0-operators`
- Budget cap: `16` hours

The licensed deposit README says the RTL is proprietary Infinigence-AI IP and supplies only a pre-generated U280 bitstream, precompiled cases, and a host file. Independent RTL lint and generic synthesis are impossible.

Next bounded action: Obtain redistributable source RTL from the IP owner; a closed bitstream cannot satisfy independent lint or synthesis gates.

`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by that manifest; stdout and stderr are retained separately. A stopped route has no implied pass at any later stage.
