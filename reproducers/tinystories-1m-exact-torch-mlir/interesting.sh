#!/usr/bin/env bash
set -euo pipefail

candidate="${1:?usage: interesting.sh <candidate.mlir>}"
diagnostic="$(mktemp /tmp/tinystories-exact-torch-mlir-reduce.XXXXXX.log)"
cleanup() {
  rm -f "$diagnostic"
}
trap cleanup EXIT

set +e
torch-mlir-opt \
  -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' \
  "$candidate" -o /dev/null >"$diagnostic" 2>&1
rc=$?
set -e

if [[ "$rc" -ne 0 ]] && grep -Fq \
  "failed to legalize operation 'torch.operator' that was explicitly marked illegal" \
  "$diagnostic"; then
  exit 0
fi

exit 1
