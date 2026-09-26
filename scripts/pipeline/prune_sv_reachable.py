#!/usr/bin/env python3
"""Keep only SystemVerilog modules reachable from a requested top module."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


MODULE_RE = re.compile(r"(?m)^module\s+([A-Za-z_][A-Za-z0-9_$]*)\b")


def prune(source: str, *, top: str) -> tuple[str, dict[str, object]]:
    matches = list(MODULE_RE.finditer(source))
    if not matches:
        raise ValueError("source has no module definitions")
    names = [match.group(1) for match in matches]
    if len(names) != len(set(names)):
        raise ValueError("source has duplicate module definitions")
    bodies = {
        match.group(1): source[match.end() : (matches[index + 1].start() if index + 1 < len(matches) else len(source))]
        for index, match in enumerate(matches)
    }
    if top not in bodies:
        raise ValueError(f"top module {top!r} is not defined")
    # An instantiation has a module name followed by an optional parameter
    # override and an opening port-list.  The module-name alternation is
    # restricted to definitions, so identifiers and comments cannot create
    # dependencies on arbitrary text.
    instance_re = re.compile(
        r"(?<![A-Za-z0-9_$])(?P<name>" + "|".join(re.escape(name) for name in names) + r")\s*"
        r"(?:#\s*\([^;]*?\)\s*)?[A-Za-z_][A-Za-z0-9_$]*\s*\(",
        re.DOTALL,
    )
    reachable: set[str] = set()
    pending = [top]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        for match in instance_re.finditer(bodies[name]):
            dependency = match.group("name")
            if dependency not in reachable:
                pending.append(dependency)
    chunks = []
    for index, match in enumerate(matches):
        name = match.group(1)
        if name not in reachable:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        chunks.append(source[match.start() : end])
    result = "".join(chunks)
    report = {
        "schema": "sv-reachable-prune-v1",
        "top": top,
        "input_module_count": len(names),
        "retained_module_count": len(reachable),
        "removed_module_count": len(names) - len(reachable),
        "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(result.encode()).hexdigest(),
        "retained_modules": [name for name in names if name in reachable],
    }
    return result, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--top", default="main_1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result, report = prune(args.input.read_text(encoding="utf-8"), top=args.top)
    args.output.write_text(result, encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
