#!/usr/bin/env python3
"""Locate the first dumped Calyx pass containing a suspicious assignment."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PASS = re.compile(r"^\[INFO  calyx_opt::pass_manager\] (?P<name>[^:]+):")


def locate(path: Path, needle: str) -> dict[str, object]:
    current = "initial"
    occurrences = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = PASS.match(line)
        if match:
            current = match.group("name")
        if needle in line:
            occurrences.append({"line": number, "pass": current, "text": line.strip()})
    return {
        "schema": "calyx-assignment-divergence-location-v1",
        "needle": needle,
        "first": occurrences[0] if occurrences else None,
        "occurrence_count": len(occurrences),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True, type=Path)
    parser.add_argument("--needle", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(locate(args.dump, args.needle), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
