#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd -P)"
root="$(cd "$here/../../.." && pwd -P)"
candidate="${1:-$here/input.mlir}"
exec python3 "$root/scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py" \
  --check-representative "$candidate" --metadata "$here/representative.json"
