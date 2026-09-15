#!/usr/bin/env python3
"""Emit a canonical placement manifest for one compiler memory image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.analysis.memory_placement_contract import placement_manifest_hash, placement_record
from scripts.analysis.memory_placement_equivalence import ProjectionTable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mode", choices=("bram", "ddr3"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = bytes(int(line.strip(), 16) for line in args.image.read_text().splitlines() if line.strip())[:4096]
    table = ProjectionTable("blocks.0.attn.q.weight", 8, len(raw), raw,
                           hashlib.sha256(args.image.read_bytes()).hexdigest(), str(args.image))
    record = placement_record(table, args.mode)
    result = {"schema": "tinystories-1m-memory-placement-v1", "records": [record],
              "manifest_sha256": placement_manifest_hash([record])}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["manifest_sha256"])


if __name__ == "__main__":
    main()
