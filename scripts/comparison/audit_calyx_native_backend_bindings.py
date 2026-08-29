#!/usr/bin/env python3
"""Audit native-Calyx Verilog input bindings against the Futil source.

This is deliberately an *analysis post-pass*, not an RTL rewriter.  The native
Calyx backend time-multiplexes assignments from many Calyx groups into one
Verilog input mux.  Before a CIRCT plugin attempts to clone or split a shared
cell, this audit establishes that each generated mux arm belongs to the same
source-cell input in Futil.  Otherwise a loop visible after native codegen is a
backend binding defect and an upstream transform would be speculative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


_FUTIL_ASSIGN = re.compile(
    r"(?P<destination>[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*=\s*(?P<source>[A-Za-z_][A-Za-z0-9_]*)\.out\s*;"
)
_FUTIL_CELL = re.compile(r"\b(?P<cell>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:std_|comb_)" )


def _futil_destinations_by_source(source: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for match in _FUTIL_ASSIGN.finditer(source):
        result.setdefault(match.group("source"), set()).add(match.group("destination"))
    return result


def _futil_cells(source: str) -> set[str]:
    """Return named primitive cells, excluding generated group/FSM wires."""

    return {match.group("cell") for match in _FUTIL_CELL.finditer(source)}


def _verilog_assignment(source: str, input_name: str) -> str:
    match = re.search(
        rf"\bassign\s+{re.escape(input_name)}\s*=\s*(?P<rhs>.*?);",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"generated Verilog is missing assignment for {input_name}")
    return match.group("rhs")


def _futil_destination(input_name: str) -> str:
    cell, separator, port = input_name.rpartition("_")
    if not separator or not cell or not port:
        raise ValueError(f"cannot map generated input {input_name} to cell.port")
    return f"{cell}.{port}"


def audit(futil_path: Path, verilog_path: Path, generated_inputs: list[str]) -> dict[str, object]:
    """Return mismatched Futil-to-native-backend input bindings.

    ``generated_inputs`` is intentionally explicit: the caller chooses the
    structurally suspicious inputs from the Yosys loop witness, so the checker
    neither claims a whole-program proof nor accidentally rewrites anything.
    """

    futil = futil_path.read_text(encoding="utf-8")
    destinations = _futil_destinations_by_source(futil)
    cells = _futil_cells(futil)
    verilog = verilog_path.read_text(encoding="utf-8")
    mismatches: list[dict[str, object]] = []
    for generated_input in generated_inputs:
        expected_destination = _futil_destination(generated_input)
        rhs = _verilog_assignment(verilog, generated_input)
        sources = sorted(
            cell
            for cell in set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)_out\b", rhs))
            if cell in cells
        )
        for source_cell in sources:
            futil_destinations = sorted(destinations.get(source_cell, set()))
            if expected_destination not in futil_destinations:
                mismatches.append(
                    {
                        "generated_input": generated_input,
                        "generated_sources": [f"{source_cell}_out"],
                        "source_cell": source_cell,
                        "futil_destinations": futil_destinations,
                    }
                )
    return {
        "schema": "calyx-native-backend-binding-audit-v1",
        "status": "backend_binding_mismatch" if mismatches else "accepted",
        "futil": str(futil_path),
        "verilog": str(verilog_path),
        "generated_inputs": generated_inputs,
        "sha256": {
            "futil": hashlib.sha256(futil_path.read_bytes()).hexdigest(),
            "verilog": hashlib.sha256(verilog_path.read_bytes()).hexdigest(),
        },
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "scope": {
            "production_rtl_changed": False,
            "backend_rewritten": False,
            "plugin_transform_justified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--futil", required=True, type=Path)
    parser.add_argument("--verilog", required=True, type=Path)
    parser.add_argument("--generated-input", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.futil, args.verilog, args.generated_input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
