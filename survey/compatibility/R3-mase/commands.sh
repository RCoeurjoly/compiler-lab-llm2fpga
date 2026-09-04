#!/usr/bin/env bash
set -u

sha256sum survey/protocol.md survey/build/deep_review.csv survey/build/artifact_inventory.csv survey/build/repository_audit.csv
python3 -c "import csv; r=list(csv.DictReader(open('survey/build/artifact_inventory.csv'))); m=[x for x in r if 'mase' in (x['title']+' '+x['normalized_artifact_url']).lower()]; print('matching_artifact_rows='+str(len(m)))"
