"""Namespace Calyx-generated phase modules without changing RTL expressions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


_TOKEN = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_$][A-Za-z_0-9$]*|[^\s]',
    re.MULTILINE,
)
_IDENT = re.compile(r"[A-Za-z_$][A-Za-z_0-9$]*\Z")
_PREFIX = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


def _tokens(source: str) -> list[tuple[str, int, int]]:
    result = []
    for match in _TOKEN.finditer(source):
        value = match.group()
        if value.startswith(("//", "/*", '"')):
            continue
        result.append((value, match.start(), match.end()))
    return result


def _after_parameters(tokens: list[tuple[str, int, int]], index: int) -> int:
    if index >= len(tokens) or tokens[index][0] != "#":
        return index
    if index + 1 >= len(tokens) or tokens[index + 1][0] != "(":
        raise ValueError("unsupported module parameter syntax")
    depth = 0
    for position in range(index + 1, len(tokens)):
        value = tokens[position][0]
        if value == "(":
            depth += 1
        elif value == ")":
            depth -= 1
            if depth == 0:
                return position + 1
    raise ValueError("unterminated module parameter list")


def namespace_modules(source: str, prefix: str) -> tuple[str, dict]:
    """Rename each module declaration and instance type in a phase SV source."""
    if not _PREFIX.fullmatch(prefix):
        raise ValueError("invalid phase prefix")
    tokens = _tokens(source)
    declarations: dict[str, int] = {}
    for index, (value, _, _) in enumerate(tokens):
        if value != "module":
            continue
        if index + 1 >= len(tokens) or not _IDENT.fullmatch(tokens[index + 1][0]):
            raise ValueError("unsupported module declaration syntax")
        name = tokens[index + 1][0]
        if name in declarations:
            raise ValueError(f"duplicate module definition: {name}")
        declarations[name] = index + 1
    if "main_1" not in declarations:
        raise ValueError("missing main_1 module")

    names = {name: f"{prefix}__{name}" for name in declarations}
    replacements: dict[int, str] = {index: names[name] for name, index in declarations.items()}
    for index, (value, _, _) in enumerate(tokens):
        if value not in names or index in replacements:
            continue
        next_index = _after_parameters(tokens, index + 1)
        if next_index + 1 >= len(tokens):
            continue
        instance = tokens[next_index][0]
        if _IDENT.fullmatch(instance) and tokens[next_index + 1][0] == "(":
            replacements[index] = names[value]

    output = source
    for index in sorted(replacements, reverse=True):
        _, start, end = tokens[index]
        output = output[:start] + replacements[index] + output[end:]
    receipt = {
        "modules": names,
        "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
    }
    return output, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    output, receipt = namespace_modules(args.input.read_text(), args.prefix)
    args.output.write_text(output)
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
