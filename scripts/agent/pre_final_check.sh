#!/usr/bin/env bash
set -euo pipefail

if [[ -n "$(git status --porcelain)" ]]; then
  echo "uncommitted changes remain; commit them before final response" >&2
  git status --short >&2
  exit 1
fi
