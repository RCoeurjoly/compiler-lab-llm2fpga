#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

if [[ ! -x .githooks/pre-commit ]]; then
  echo ".githooks/pre-commit is missing or not executable" >&2
  exit 1
fi

git config --local core.hooksPath .githooks
echo "configured core.hooksPath=.githooks"
