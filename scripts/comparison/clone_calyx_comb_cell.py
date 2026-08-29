#!/usr/bin/env python3
"""Clone one primitive combinational cell for a specific Futil destination.

This is intentionally a narrow, source-aware post-pass.  It only accepts the
known combinational primitive families and requires an exact source assignment;
it never guesses from generated Verilog.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

_COMB = {"std_add", "std_sub", "std_signext", "std_slice", "std_mux", "std_rsh", "std_lsh"}


def clone(text: str, cell: str, destination: str) -> tuple[str, str]:
    decl = re.search(rf"(?m)^\s*{re.escape(cell)}\s*=\s*(std_[A-Za-z0-9_]+)\(([^;]+)\);", text)
    if not decl or decl.group(1) not in _COMB:
        raise ValueError("cell declaration is missing or not an approved combinational primitive")
    old = f"{cell}.out"
    if text.count(old) == 0:
        raise ValueError("cell output is not present")
    target = f"{destination} = {old};"
    if text.count(target) != 1:
        raise ValueError("expected exactly one source assignment for destination")
    clone_name = f"{cell}__for__{destination.replace('.', '_')}"
    if clone_name in text:
        raise ValueError("clone already exists")
    cloned_decl = f"    {clone_name} = {decl.group(1)}({decl.group(2)});"
    text = text[: decl.start()] + decl.group(0) + "\n" + cloned_decl + text[decl.end() :]
    text = text.replace(target, f"{destination} = {clone_name}.out;", 1)
    # Copy the clone's input assignments alongside the original assignments so
    # the primitive remains well-formed in every control group.
    input_assignments = list(re.finditer(rf"(?m)^(\s*){re.escape(cell)}\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+);$", text))
    for match in reversed(input_assignments):
        port = match.group(2)
        if port == "out":
            continue
        line = match.group(0)
        replacement = line.replace(f"{cell}.{port}", f"{clone_name}.{port}", 1)
        text = text[: match.end()] + "\n" + replacement + text[match.end() :]
    return text, clone_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    result, _ = clone(args.input.read_text(encoding="utf-8"), args.cell, args.destination)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
