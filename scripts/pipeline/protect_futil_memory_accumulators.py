#!/usr/bin/env python3
"""Protect Calyx memory-accumulator datapaths from unsafe cell sharing."""

import json
import re
import sys
from pathlib import Path


GROUP = re.compile(r"(?ms)^\s*group\s+\w+\s*\{\n(.*?)^\s*\}")
WRITE_DATA = re.compile(r"(?m)^\s*\w+\.write_data\s*=\s*(\w+)\.out;\s*$")
OPERAND = re.compile(r"(?m)^\s*(\w+)\.(?:left|right)\s*=\s*(\w+)\.out;\s*$")


def protected_cells(source: str) -> set[str]:
    cells: set[str] = set()
    for group in GROUP.finditer(source):
        body = group.group(1)
        for write in WRITE_DATA.finditer(body):
            adder = write.group(1)
            operands = {
                operand.group(2)
                for operand in OPERAND.finditer(body)
                if operand.group(1) == adder
            }
            if len(operands) == 2:
                cells.add(adder)
                cells.update(operands)
    return cells


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"usage: {sys.argv[0]} <input.futil> <output.futil> <receipt.json>",
            file=sys.stderr,
        )
        return 2

    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    cells = protected_cells(source)
    replacements = 0
    for cell in sorted(cells):
        definition = re.compile(rf"(?m)^(\s*)(?!@protected\s+)({re.escape(cell)}\s*=)")
        source, count = definition.subn(r"\1@protected \2", source, count=1)
        replacements += count

    Path(sys.argv[2]).write_text(source, encoding="utf-8")
    Path(sys.argv[3]).write_text(
        json.dumps(
            {
                "status": "ok",
                "protected_cells": sorted(cells),
                "protected_cell_count": len(cells),
                "new_annotation_count": replacements,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
