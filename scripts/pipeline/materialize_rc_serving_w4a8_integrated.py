#!/usr/bin/env python3
"""Materialize one wholesale stateful W4A8 ExportedProgram."""

from __future__ import annotations

import argparse
from pathlib import Path

from TinyStories.rc_serving_w4a8_integrated import materialize_integrated_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--phase-oracle", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    materialize_integrated_bundle(
        args.model_path, args.trace, args.phase_oracle, args.out_dir
    )
    print(args.out_dir)


if __name__ == "__main__":
    main()
