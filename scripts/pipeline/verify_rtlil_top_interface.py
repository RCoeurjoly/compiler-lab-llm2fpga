#!/usr/bin/env python3
"""Validate and describe a named RTLIL module's top-level port boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtlil", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--expected-port-count", required=True, type=int)
    parser.add_argument("--expected-port-bits", required=True, type=int)
    parser.add_argument("--required-output", action="append", default=[])
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def unescape_rtlil_name(name: str) -> str:
    return name[1:] if name.startswith("\\") else name


def module_port_rows(rtlil: str, top: str) -> list[tuple[str, int, tuple[str, ...]]]:
    target_names = {top, f"\\{top}"}
    in_target = False
    rows: list[tuple[str, int, tuple[str, ...]]] = []
    for raw_line in rtlil.splitlines():
        fields = raw_line.split()
        if not fields:
            continue
        if fields[0] == "module":
            in_target = len(fields) > 1 and fields[1] in target_names
            continue
        if in_target and fields[0] == "end":
            break
        if not in_target or fields[0] != "wire":
            continue
        directions = tuple(
            direction for direction in ("input", "output") if direction in fields
        )
        if not directions:
            continue
        width = 1
        if "width" in fields:
            width = int(fields[fields.index("width") + 1])
        rows.append((unescape_rtlil_name(fields[-1]), width, directions))
    if not rows:
        raise SystemExit(f"no top-level ports found for {top!r}")
    return rows


def main() -> None:
    args = parse_args()
    rows = module_port_rows(Path(args.rtlil).read_text(encoding="utf-8"), args.top)
    port_count = len(rows)
    port_bits = sum(width for _, width, _ in rows)
    output_names = {name for name, _, directions in rows if "output" in directions}
    missing = sorted(set(args.required_output) - output_names)
    if port_count != args.expected_port_count:
        raise SystemExit(
            f"expected {args.expected_port_count} ports, found {port_count}"
        )
    if port_bits != args.expected_port_bits:
        raise SystemExit(
            f"expected {args.expected_port_bits} port bits, found {port_bits}"
        )
    if missing:
        raise SystemExit(f"missing required output ports: {', '.join(missing)}")
    payload = {
        "schema_version": 1,
        "verification": "verified-after-import",
        "top": args.top,
        "port_count": port_count,
        "port_bits": port_bits,
        "direction_counts": {
            direction: sum(direction in directions for _, _, directions in rows)
            for direction in ("input", "output")
        },
        "required_outputs": sorted(args.required_output),
    }
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
