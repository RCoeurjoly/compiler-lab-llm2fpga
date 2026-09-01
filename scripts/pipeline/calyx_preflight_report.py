#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PROHIBITED_OPERATIONS = frozenset(
    {
        "arith.negf",
        "arith.uitofp",
        "math.absi",
        "math.floor",
        "memref.collapse_shape",
        "memref.copy",
        "memref.expand_shape",
        "memref.reinterpret_cast",
    }
)

# Quoted generic operations do not carry parser registration information. Keep
# this allowlist explicit so a newly observed spelling cannot silently become a
# clean result. It covers the current pre-Calyx pipeline vocabulary plus the
# prohibited operations above; extending it requires a reviewed contract
# change.
KNOWN_QUOTED_OPERATIONS = frozenset(
    {
        "affine.apply",
        "arith.addf",
        "arith.addi",
        "arith.andi",
        "arith.cmpf",
        "arith.cmpi",
        "arith.constant",
        "arith.divf",
        "arith.divsi",
        "arith.divui",
        "arith.extf",
        "arith.extsi",
        "arith.extui",
        "arith.fptosi",
        "arith.fptoui",
        "arith.index_cast",
        "arith.index_castui",
        "arith.maxf",
        "arith.minf",
        "arith.mulf",
        "arith.muli",
        "arith.negf",
        "arith.ori",
        "arith.remsi",
        "arith.remui",
        "arith.select",
        "arith.shli",
        "arith.shrsi",
        "arith.shrui",
        "arith.sitofp",
        "arith.subf",
        "arith.subi",
        "arith.truncf",
        "arith.trunci",
        "arith.uitofp",
        "arith.xori",
        "builtin.module",
        "cf.assert",
        "cf.br",
        "cf.cond_br",
        "func.call",
        "func.func",
        "func.return",
        "math.absi",
        "math.floor",
        "memref.alloc",
        "memref.alloca",
        "memref.cast",
        "memref.collapse_shape",
        "memref.copy",
        "memref.dealloc",
        "memref.dim",
        "memref.expand_shape",
        "memref.get_global",
        "memref.global",
        "memref.load",
        "memref.reinterpret_cast",
        "memref.store",
        "memref.subview",
        "scf.condition",
        "scf.execute_region",
        "scf.for",
        "scf.if",
        "scf.while",
        "scf.yield",
    }
)

SSA_VALUE = r"%(?:[0-9]+|[A-Za-z_$.-][A-Za-z0-9_$.-]*)(?::[0-9]+)?"
RESULT_ASSIGNMENT = re.compile(
    rf"(?:{SSA_VALUE})(?:[ \t]*,[ \t]*(?:{SSA_VALUE}))*[ \t]*="
)
BARE_OPERATION = re.compile(r"[A-Za-z_][A-Za-z0-9_$.-]*")
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _location(line: int, column: int) -> dict[str, int]:
    return {"line": line, "column": column}


def _diagnostic(
    kind: str, line: int, column: int, message: str
) -> dict[str, object]:
    return {
        "kind": kind,
        "line": line,
        "column": column,
        "message": message,
    }


def _skip_horizontal_space(line: str, cursor: int) -> int:
    while cursor < len(line) and line[cursor] in " \t\r":
        cursor += 1
    return cursor


def _decode_quoted_operation(
    line: str, cursor: int, line_number: int
) -> tuple[str | None, int, dict[str, object] | None]:
    quote_column = cursor + 1
    cursor += 1
    decoded: list[str] = []
    while cursor < len(line):
        char = line[cursor]
        if char == '"':
            return "".join(decoded), cursor + 1, None
        if char == "\\":
            if (
                cursor + 2 >= len(line)
                or line[cursor + 1] not in HEX_DIGITS
                or line[cursor + 2] not in HEX_DIGITS
            ):
                return (
                    None,
                    len(line),
                    _diagnostic(
                        "malformed_quoted_operation",
                        line_number,
                        quote_column,
                        "malformed quoted operation: escape must contain two hexadecimal digits",
                    ),
                )
            decoded.append(chr(int(line[cursor + 1 : cursor + 3], 16)))
            cursor += 3
            continue
        decoded.append(char)
        cursor += 1
    return (
        None,
        cursor,
        _diagnostic(
            "malformed_quoted_operation",
            line_number,
            quote_column,
            "malformed quoted operation: missing closing quote",
        ),
    )


def _record_operation(
    operation: str,
    line: int,
    column: int,
    counts: dict[str, int],
    first_locations: dict[str, dict[str, int]],
) -> None:
    if operation not in PROHIBITED_OPERATIONS:
        return
    counts[operation] = counts.get(operation, 0) + 1
    first_locations.setdefault(operation, _location(line, column))


def _scan_operations(
    text: str,
) -> tuple[
    dict[str, int],
    dict[str, dict[str, int]],
    list[dict[str, object]],
]:
    counts: dict[str, int] = {}
    first_locations: dict[str, dict[str, int]] = {}
    diagnostics: list[dict[str, object]] = []
    awaiting_operation = False
    awaiting_generic_operands: tuple[int, int] | None = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        cursor = _skip_horizontal_space(line, 0)
        if cursor == len(line) or line.startswith("//", cursor):
            continue

        if awaiting_generic_operands is not None:
            if line[cursor] == "(":
                awaiting_generic_operands = None
            else:
                diagnostics.append(
                    _diagnostic(
                        "malformed_trivia",
                        line_number,
                        cursor + 1,
                        "malformed trivia after quoted operation",
                    )
                )
                awaiting_generic_operands = None
            continue

        has_result_assignment = awaiting_operation
        if not awaiting_operation:
            result_match = RESULT_ASSIGNMENT.match(line, cursor)
            if result_match is not None:
                has_result_assignment = True
                cursor = result_match.end()
        awaiting_operation = False
        cursor = _skip_horizontal_space(line, cursor)
        if cursor == len(line) or line.startswith("//", cursor):
            if has_result_assignment:
                awaiting_operation = True
            continue

        operation_column = cursor + 1
        if line[cursor] == '"':
            operation, after_name, diagnostic = _decode_quoted_operation(
                line, cursor, line_number
            )
            if diagnostic is not None:
                if has_result_assignment or cursor == _skip_horizontal_space(line, 0):
                    diagnostics.append(diagnostic)
                continue
            assert operation is not None

            after_trivia = _skip_horizontal_space(line, after_name)
            valid_generic_syntax = False
            if after_trivia < len(line) and line[after_trivia] == "(":
                valid_generic_syntax = True
            elif line.startswith("//", after_trivia) or after_trivia == len(line):
                valid_generic_syntax = True
                awaiting_generic_operands = (line_number, operation_column)
            elif has_result_assignment:
                diagnostics.append(
                    _diagnostic(
                        "malformed_trivia",
                        line_number,
                        after_trivia + 1,
                        "malformed trivia after quoted operation",
                    )
                )

            if not valid_generic_syntax and not has_result_assignment:
                continue
            _record_operation(
                operation,
                line_number,
                operation_column,
                counts,
                first_locations,
            )
            if operation not in KNOWN_QUOTED_OPERATIONS:
                diagnostics.append(
                    _diagnostic(
                        "unknown_operation",
                        line_number,
                        operation_column,
                        f"unknown quoted operation: {operation}",
                    )
                )
            continue

        operation_match = BARE_OPERATION.match(line, cursor)
        if operation_match is None:
            continue
        _record_operation(
            operation_match.group(0),
            line_number,
            operation_column,
            counts,
            first_locations,
        )

    if awaiting_operation:
        line_number = max(1, len(text.splitlines()))
        diagnostics.append(
            _diagnostic(
                "malformed_operation",
                line_number,
                1,
                "result assignment is missing an operation",
            )
        )
    if awaiting_generic_operands is not None:
        line_number, operation_column = awaiting_generic_operands
        diagnostics.append(
            _diagnostic(
                "malformed_trivia",
                line_number,
                operation_column,
                "quoted operation is missing its operand list",
            )
        )

    return (
        dict(sorted(counts.items())),
        dict(sorted(first_locations.items())),
        diagnostics,
    )


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def build_report(text: str) -> dict[str, object]:
    prohibited_ops, first_locations, scanner_diagnostics = _scan_operations(text)
    report: dict[str, object] = {
        "schema_version": 2,
        "status": "blocked"
        if prohibited_ops or scanner_diagnostics
        else "ok",
        "prohibited_ops": prohibited_ops,
        "first_locations": first_locations,
        "scanner_diagnostics": scanner_diagnostics,
    }
    report["sha256"] = hashlib.sha256(_canonical_json(report)).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report prohibited operations at the SCF-to-Calyx boundary."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"missing input MLIR: {args.input}")

    report = build_report(args.input.read_text(encoding="utf-8"))
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 1 if args.require_clean and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
