#!/usr/bin/env bash
set -euo pipefail

input=${1:?usage: interesting-left-shift.sh INPUT.mlir}
tool=${TORCH_MLIR_OPT:-torch-mlir-opt}
pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})'
log=$(mktemp -t exact-left-shift-interesting.XXXXXX)
trap 'rm -f "$log"' EXIT

rg -q 'torch\.operator "torch\.aten\.bitwise_left_shift\.Tensor_Scalar".*: \(!torch\.vtensor<\[4,64\],si64>, !torch\.int\) -> !torch\.vtensor<\[4,64\],si64>' "$input"
set +e
"$tool" "-pass-pipeline=$pipeline" "$input" -o /dev/null >"$log" 2>&1
status=$?
set -e
test "$status" -ne 0
rg -q "failed to legalize operation 'torch.operator' that was explicitly marked illegal" "$log"
rg -q 'torch\.aten\.bitwise_left_shift\.Tensor_Scalar' "$log"
! rg -q 'shift_contract:' "$log"
cat "$log"
