#!/usr/bin/env python3
"""Materialize converted PT2E W4A8 serving phases and frozen weights."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.rc_serving_w4a8_export import materialize_w4a8_bundle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    materialize_w4a8_bundle(args.model_path, args.trace, args.out_dir)


if __name__ == "__main__":
    main()
