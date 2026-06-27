#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


BLOCKER_PATTERNS = {
    "memref.reinterpret_cast": re.compile(r"\bmemref\.reinterpret_cast\b"),
    "memref.expand_shape": re.compile(r"\bmemref\.expand_shape\b"),
    "memref.collapse_shape": re.compile(r"\bmemref\.collapse_shape\b"),
    "memref.copy": re.compile(r"\bmemref\.copy\b"),
    "tensor": re.compile(r"\btensor\."),
    "linalg": re.compile(r"\blinalg\."),
}

FUNCTION_RE = re.compile(r"\bfunc\.func\s+@([\w$.]+)")
PARENT_OP_RE = re.compile(r"^\s*((?:scf|affine|cf)\.[\w.]+)\b")
RESULT_RE = re.compile(r"^\s*(%[\w$.]+)\s*=")
SSA_VALUE_RE = re.compile(r"%[\w$.]+")
OP_RE = re.compile(r"^\s*(?:%[\w$., ]+\s*=\s*)?([a-zA-Z_][\w.]+)")


def update_parent_stack(stack: list[dict[str, int | str]], line: str) -> None:
    stripped = line.strip()
    close_count = stripped.count("}")
    for _ in range(close_count):
        if stack:
            stack[-1]["depth"] = int(stack[-1]["depth"]) - 1
            if stack[-1]["depth"] <= 0:
                stack.pop()

    match = PARENT_OP_RE.match(line)
    if match and "{" in line:
        stack.append({"op": match.group(1), "depth": line.count("{") - close_count})

    if stack and "{" in line and not match:
        stack[-1]["depth"] = int(stack[-1]["depth"]) + line.count("{")


def operation_name(line: str) -> str | None:
    match = OP_RE.match(line)
    return match.group(1) if match else None


def result_name(line: str) -> str | None:
    match = RESULT_RE.match(line)
    return match.group(1) if match else None


def operand_names(line: str) -> list[str]:
    values = SSA_VALUE_RE.findall(line)
    result = result_name(line)
    if result is not None and values and values[0] == result:
        values = values[1:]
    return list(dict.fromkeys(values))


def value_definitions(lines: list[str]) -> dict[str, dict]:
    definitions = {}
    for line_number, line in enumerate(lines, start=1):
        result = result_name(line)
        if result is None:
            continue
        definitions[result] = {
            "line": line_number,
            "op": operation_name(line),
            "text": line.strip(),
        }
    return definitions


def value_users(lines: list[str], value: str | None, defining_line: int) -> list[dict]:
    if value is None:
        return []

    users = []
    value_pattern = re.compile(rf"(?<![\w$.]){re.escape(value)}(?![\w$.])")
    for line_number, line in enumerate(lines, start=1):
        if line_number == defining_line:
            continue
        if not value_pattern.search(line):
            continue
        users.append(
            {
                "line": line_number,
                "op": operation_name(line),
                "text": line.strip(),
            }
        )
    return users


def build_report(text: str) -> dict:
    lines = text.splitlines()
    definitions = value_definitions(lines)
    counts = {name: 0 for name in BLOCKER_PATTERNS}
    locations = []
    current_function = None
    parent_stack: list[dict[str, int | str]] = []

    for line_number, line in enumerate(lines, start=1):
        function_match = FUNCTION_RE.search(line)
        if function_match:
            current_function = function_match.group(1)
            parent_stack = []

        for op, pattern in BLOCKER_PATTERNS.items():
            if not pattern.search(line):
                continue
            result = result_name(line)
            operands = operand_names(line)
            counts[op] += 1
            locations.append(
                {
                    "op": op,
                    "line": line_number,
                    "function": current_function,
                    "parents": [str(parent["op"]) for parent in parent_stack],
                    "result": result,
                    "operands": operands,
                    "operand_definitions": [
                        definitions[operand]
                        for operand in operands
                        if operand in definitions
                    ],
                    "users": value_users(lines, result, line_number),
                    "text": line.strip(),
                }
            )

        update_parent_stack(parent_stack, line)

    blockers = [
        {"op": op, "count": count}
        for op, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count
    ]
    return {"stage": "flat-scf", "blockers": blockers, "locations": locations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.input.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
