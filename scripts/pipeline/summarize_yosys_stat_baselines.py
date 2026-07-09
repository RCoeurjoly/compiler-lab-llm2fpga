#!/usr/bin/env python3
"""Build a resource-baseline matrix from Yosys stat report JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ENTRY_KEYS = {"alias", "model", "frontend", "backend", "stat"}


def parse_entry(raw: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise SystemExit(f"invalid --entry item: {item!r}")
        fields[key] = value

    missing = sorted(REQUIRED_ENTRY_KEYS - set(fields))
    if missing:
        raise SystemExit(f"--entry is missing required keys: {', '.join(missing)}")
    return fields


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def top_cell_types(counts: dict[str, Any], limit: int = 8) -> list[dict[str, int | str]]:
    rows = [
        {"type": str(cell_type), "count": int(count)}
        for cell_type, count in counts.items()
        if isinstance(count, int)
    ]
    return sorted(rows, key=lambda row: (-int(row["count"]), str(row["type"])))[:limit]


def summarize_entry(raw_entry: str) -> dict[str, Any]:
    entry = parse_entry(raw_entry)
    stat_path = Path(entry["stat"])
    stat = load_json(stat_path)
    design = ((stat.get("yosys_stat") or {}).get("design")) or {}

    return {
        "alias": entry["alias"],
        "model": entry["model"],
        "frontend": entry["frontend"],
        "backend": entry["backend"],
        "status": stat.get("status", "unknown"),
        "stat": str(stat_path),
        "num_cells": design.get("num_cells"),
        "num_memories": design.get("num_memories"),
        "num_memory_bits": design.get("num_memory_bits"),
        "top_cell_types": top_cell_types(design.get("num_cells_by_type") or {}),
    }


def markdown_table(entries: list[dict[str, Any]]) -> str:
    lines = [
        "| alias | frontend | backend | status | cells | memories | memory bits |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for entry in entries:
        lines.append(
            "| {alias} | {frontend} | {backend} | {status} | {num_cells} | "
            "{num_memories} | {num_memory_bits} |".format(**entry)
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", action="append", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    entries = [summarize_entry(entry) for entry in args.entry]
    payload = {
        "schemaVersion": 1,
        "report_kind": "yosys-stat-resource-baseline-matrix",
        "entries": entries,
    }

    Path(args.summary_json).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.summary_md).write_text(markdown_table(entries), encoding="utf-8")


if __name__ == "__main__":
    main()
