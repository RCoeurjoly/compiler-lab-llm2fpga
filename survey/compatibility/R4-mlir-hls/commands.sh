#!/usr/bin/env bash
set -u

sha256sum survey/protocol.md survey/build/deep_review.csv survey/build/artifact_inventory.csv survey/build/repository_audit.csv
python3 -c "import csv,json; r=next(x for x in csv.DictReader(open('survey/build/repository_audit.csv')) if x['project_family_id']=='PF-86FE8DBFB50CB04C'); print(json.dumps({k:r[k] for k in ('observed_commit','licence_state','licence_spdx_id','source_closure_state','generated_or_omitted_rtl','tool_indicators_json','failure_code')},sort_keys=True))"
python3 -c "import csv,json; r=next(x for x in csv.DictReader(open('survey/build/artifact_inventory.csv')) if x['project_family_id']=='PF-86FE8DBFB50CB04C'); print(json.dumps({k:r[k] for k in ('artifact_claim_state','artifact_relation','limitations')},sort_keys=True))"
