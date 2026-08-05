#!/usr/bin/env python3
"""Materialize the independent prefill-8, decode-8, decode-9 cache bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.rc_serving_direct_export import (  # noqa: E402
    materialize_direct_export_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    materialize_direct_export_bundle(
        args.model_path, args.trace, args.reference, args.out_dir
    )


if __name__ == "__main__":
    main()
