#!/usr/bin/env python3
"""Factor nested conditional assignments in generated SV (diagnostic only).

The rewrite preserves conditional ordering and only handles continuous
assignments whose left-hand net has an explicit packed width declaration.  It
is deliberately conservative and never edits a source file in place.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ASSIGN = re.compile(r"(?ms)(?P<indent>^[ \t]*)assign\s+(?P<lhs>[A-Za-z_$][\w$]*)\s*=\s*(?P<rhs>.*?);\s*$")
DECL = re.compile(r"\b(?:wire|logic|reg)\s+(?P<width>\[[^\]]+\])\s+(?P<name>[A-Za-z_$][\w$]*)\s*;")


def _top_ternary(expr: str) -> tuple[str, str, str] | None:
    depth = 0
    question = -1
    nested = 0
    for i, ch in enumerate(expr):
        if ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        elif ch == "?" and depth == 0:
            if question < 0:
                question = i
            else:
                nested += 1
        elif ch == ":" and depth == 0 and question >= 0:
            if nested:
                nested -= 1
            else:
                return expr[:question].strip(), expr[question + 1:i].strip(), expr[i + 1:].strip()
    return None


def factor(source: str) -> tuple[str, dict[str, object]]:
    widths = {m.group("name"): m.group("width") for m in DECL.finditer(source)}
    counter = 0
    factors = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter, factors
        lhs, rhs = match.group("lhs"), match.group("rhs").strip()
        width = widths.get(lhs)
        if width is None:
            return match.group(0)
        arms: list[tuple[str, str]] = []
        current = rhs
        while True:
            split = _top_ternary(current)
            if split is None:
                break
            cond, true, false = split
            name = f"__llm2fpga_mux_{counter}"
            counter += 1
            arms.append((name, f"{cond} ? {true}"))
            factors += 1
            current = false
        if not arms:
            return match.group(0)
        # Rebuild from the innermost arm outward, preserving original priority.
        tail = current
        declarations: list[str] = []
        for name, arm in reversed(arms):
            arm = arm + f" : {tail}"
            declarations.append(f"{match.group('indent')}wire {width} {name};\n{match.group('indent')}assign {name} = {arm};")
            tail = name
        declarations.reverse()
        return "\n".join(declarations) + f"\n{match.group('indent')}assign {lhs} = {tail};"

    output = ASSIGN.sub(replace, source)
    return output, {
        "schema": "llm2fpga.sv-nested-mux-factor-v1",
        "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "factor_count": factors,
        "diagnostic_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    output, receipt = factor(args.input.read_text(encoding="utf-8"))
    args.output.write_text(output, encoding="utf-8")
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
