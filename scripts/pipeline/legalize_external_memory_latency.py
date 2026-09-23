#!/usr/bin/env python3
"""Legalize compiler-owned external memories for variable-latency scheduling.

The normal ``seq_mem_d1`` Calyx primitive describes a fixed sequential memory
access.  That is suitable for BRAM, but it lets the Calyx scheduler collapse
an external read sequence before a DDR response exists.  Calyx provides
``dyn_mem_d1`` for the opposite contract: ``content_en`` is a request and
``done`` is the response, with stable data until the consumer advances.

This pass is deliberately narrow.  It rewrites only explicitly selected
``@external`` memories and leaves all local/runtime BRAM memories unchanged.
It runs on generated Futil before Calyx lowering; it does not modify generated
SystemVerilog or reuse reference RTL.
"""

from __future__ import annotations

import re
import argparse
import json
from pathlib import Path
from typing import Iterable


_DECL = re.compile(
    r"(?m)^(?P<prefix>\s*@external\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)"
    r"(?P<kind>seq_mem_d1|dyn_mem_d1)(?P<args>\([^;]+\);\s*)$"
)
_DYN_IMPORT = 'import "primitives/memories/dyn.futil";'


def legalize_external_memory_latency(
    futil: str, memory_names: Iterable[str]
) -> tuple[str, dict[str, object]]:
    """Rewrite selected external memories to Calyx's dynamic primitive.

    The selected set must be present as ``@external`` declarations.  Existing
    dynamic declarations are accepted idempotently; unannotated or missing
    declarations fail closed so a typo cannot silently leave a fixed-latency
    memory in an external design.
    """

    selected = tuple(dict.fromkeys(memory_names))
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in selected):
        raise ValueError("external memory names must be identifiers")
    if not selected:
        return futil, {
            "schema": "llm2fpga-external-memory-latency-v1",
            "selected": [],
            "rewritten": [],
        }

    declarations = {match.group("name"): match for match in _DECL.finditer(futil)}
    missing = [name for name in selected if name not in declarations]
    if missing:
        raise ValueError(f"selected external memories are missing: {missing}")

    rewritten: list[str] = []
    result = futil
    for name in selected:
        match = declarations[name]
        if match.group("kind") == "dyn_mem_d1":
            continue
        replacement = f"{match.group('prefix')}dyn_mem_d1{match.group('args')}"
        result = result[: match.start()] + replacement + result[match.end() :]
        # Offsets changed; refresh matches before the next selected memory.
        declarations = {m.group("name"): m for m in _DECL.finditer(result)}
        rewritten.append(name)

    if rewritten and _DYN_IMPORT not in result:
        imports = list(re.finditer(r"(?m)^import\s+\"[^\"]+\";\s*$", result))
        if imports:
            insertion = imports[-1].end()
            result = result[:insertion] + "\n" + _DYN_IMPORT + result[insertion:]
        else:
            result = _DYN_IMPORT + "\n" + result

    return result, {
        "schema": "llm2fpga-external-memory-latency-v1",
        "selected": list(selected),
        "rewritten": rewritten,
        "primitive": "dyn_mem_d1",
        "scheduler_contract": "request-content_en-response-done-stable-read_data",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory", action="append", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    result, report = legalize_external_memory_latency(source, args.memory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
