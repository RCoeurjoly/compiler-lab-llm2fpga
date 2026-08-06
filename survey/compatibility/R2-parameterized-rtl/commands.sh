#!/usr/bin/env bash
set -u

sha256sum survey/protocol.md survey/build/deep_review.csv survey/build/artifact_inventory.csv survey/build/repository_audit.csv
curl -fsSL https://zenodo.org/api/records/10462167/files/README.md/content
python3 -c "import json; d=json.load(open('survey/build/api-cache/responses/zenodo/19f09e16466d9bcc9442e69b70f082e079eb5a6a349e4c225943c8366ac8a331.body')); print([(f['key'],f['size'],f['checksum']) for f in d['files']])"
