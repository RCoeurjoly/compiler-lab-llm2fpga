#!/usr/bin/env python3
"""Check the opt-in router2 iteration-1 congestion diagnostic receipt."""

import argparse
import csv
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--heatmap", type=Path, required=True)
    args = parser.parse_args()

    log = args.log.read_text()
    iteration = re.search(r"iter=1 wires=\d+ overused=(\d+) overuse=(\d+)", log)
    if not iteration:
        raise SystemExit("missing router2 iteration-1 statistics")
    overused, overuse = map(int, iteration.groups())
    if overused <= 0 or overuse <= 0:
        raise SystemExit("fixture has no iteration-1 congestion")

    reported = re.search(r"router2 diagnostic iteration=1 overused=(\d+) overuse=(\d+)", log)
    if not reported or tuple(map(int, reported.groups())) != (overused, overuse):
        raise SystemExit("missing or inconsistent iteration-1 diagnostic summary")
    top = re.findall(r"router2 diagnostic net rank=(\d+) shared_wires=(\d+) name=(\S+)", log)
    if not top or top[0][0] != "1" or int(top[0][1]) <= 0:
        raise SystemExit("missing ranked congestion-contributing net")
    if any(int(a[1]) < int(b[1]) for a, b in zip(top, top[1:])):
        raise SystemExit("contributing nets are not ranked by shared-wire count")

    with args.heatmap.open(newline="") as stream:
        rows = [row for row in csv.reader(stream) if row]
    mapped_overuse = sum(int(value) for row in rows for value in row if value)
    if mapped_overuse != overuse:
        raise SystemExit(f"heatmap overuse {mapped_overuse} differs from router overuse {overuse}")
    print(f"router2 diagnostic verified: {overused} shared wires, {len(top)} ranked nets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
