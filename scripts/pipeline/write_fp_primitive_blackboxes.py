#!/usr/bin/env python3
"""Emit blackbox shells for CIRCT floating-point primitive modules."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MODULE_RE = re.compile(r"^module\s+((?:arith|math)_[A-Za-z0-9_]+)\s*\(")


def extract_blackboxes(source: str) -> list[str]:
    lines = source.splitlines()
    modules: list[str] = []
    idx = 0
    while idx < len(lines):
        match = MODULE_RE.match(lines[idx])
        if not match:
            idx += 1
            continue

        header = [lines[idx]]
        idx += 1
        while idx < len(lines):
            header.append(lines[idx])
            if lines[idx].strip() == ");":
                break
            idx += 1
        else:
            raise ValueError(f"unterminated module header for {match.group(1)}")

        modules.append("\n".join(["(* blackbox *)", *header, "endmodule"]))
        idx += 1

    if not modules:
        raise ValueError("no arith_* or math_* primitive modules found")
    return modules


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    modules = extract_blackboxes(args.input.read_text(encoding="utf-8"))
    args.output.write_text(
        "// Auto-generated blackbox shells for Task 3 utilization reporting.\n\n"
        + "\n\n".join(modules)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
