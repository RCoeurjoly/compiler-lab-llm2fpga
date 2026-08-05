#!/usr/bin/env python3
"""Extract hash-bound DDR3 routing evidence from generated RC SystemVerilog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


MEMORY_PORT_COUNT = 146
LEARNED_PORTS = frozenset(range(25)) | frozenset(range(27, 46))
EVIDENCE_SCHEMA = "rc-sv-routing-evidence-v1"
MEMORY_ABI_SCHEMA = "rc-sv-memory-abi-v1"
REQUIRED_PINS = {
    "addr0": ("output", None),
    "content_en": ("output", 1),
    "write_en": ("output", 1),
    "write_data": ("output", None),
    "read_data": ("input", None),
    "done": ("input", 1),
}
COMPLETION = {
    "max_outstanding": 1,
    "response": "one-done-per-accepted-request",
}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_sha256(paths: Sequence[Path]) -> str:
    """Hash the ordered, exact bytes of every SV file used for extraction."""
    if not paths:
        raise ValueError("at least one generated SV source is required")
    digest = hashlib.sha256()
    digest.update(b"rc-sv-routing-evidence-source-v1\0")
    for path in paths:
        if not path.is_file():
            raise ValueError(f"missing generated SV source: {path}")
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _source_text(paths: Sequence[Path]) -> str:
    source_sha256(paths)
    try:
        return "\n".join(path.read_text(encoding="utf-8") for path in paths)
    except UnicodeDecodeError as error:
        raise ValueError("generated SV source is not UTF-8") from error


def _strip_comments(source: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL))


def _matching_paren(source: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    raise RuntimeError("unterminated main_1 port list")


def _main_1_parts(source: str) -> tuple[str, str]:
    source = _strip_comments(source)
    modules = list(re.finditer(r"\bmodule\s+main_1\s*\(", source))
    if len(modules) != 1:
        raise RuntimeError("SV must define exactly one module main_1")
    opening = source.find("(", modules[0].start())
    closing = _matching_paren(source, opening)
    header_end = source.find(";", closing)
    if header_end < 0:
        raise RuntimeError("main_1 port header is missing its terminating semicolon")
    endmodule = re.search(r"\bendmodule\b", source[header_end + 1:])
    if endmodule is None:
        raise RuntimeError("main_1 is missing endmodule")
    body_end = header_end + 1 + endmodule.start()
    return source[opening + 1:closing], source[header_end + 1:body_end]


def _strip_outer_parentheses(expression: str) -> str:
    expression = expression.strip()
    while expression.startswith("(") and expression.endswith(")"):
        closing = _matching_paren(expression, 0)
        if closing != len(expression) - 1:
            break
        expression = expression[1:-1].strip()
    return expression


def _flat_ternary_leaves(expression: str) -> list[str]:
    """Accept the generated flat priority-ternary write-enable grammar only."""
    leaves: list[str] = []
    rest = _strip_outer_parentheses(expression)
    while "?" in rest:
        question = rest.find("?")
        colon = rest.find(":", question + 1)
        if question <= 0 or colon < 0:
            raise RuntimeError(f"unsupported write-enable syntax: {expression!r}")
        leaves.append(_strip_outer_parentheses(rest[question + 1:colon]))
        rest = rest[colon + 1:].strip()
    leaves.append(_strip_outer_parentheses(rest))
    return leaves


def _is_proven_zero(expression: str) -> bool:
    for leaf in _flat_ternary_leaves(expression):
        if not re.fullmatch(r"1'[bBoOdDhH]0", leaf):
            return False
    return True


def _parse_ports(source: str) -> list[dict[str, Any]]:
    header, body = _main_1_parts(source)
    declaration = re.compile(
        r"\b(?P<direction>input|output)\s+logic"
        r"(?:\s+signed)?"
        r"(?:\s+\[\s*(?P<hi>\d+)\s*:\s*(?P<lo>\d+)\s*\])?"
        r"\s+arg_mem_(?P<number>\d+)_(?P<pin>addr0|content_en|write_en|write_data|read_data|done)\b"
    )
    declarations: dict[int, dict[str, tuple[str, int]]] = {}
    for match in declaration.finditer(header):
        number, pin = int(match.group("number")), match.group("pin")
        hi, lo = match.group("hi"), match.group("lo")
        width = int(hi) - int(lo) + 1 if hi is not None else 1
        if width <= 0:
            raise RuntimeError(f"invalid arg_mem_{number}_{pin} packed width")
        if pin in declarations.setdefault(number, {}):
            raise RuntimeError(f"duplicate main_1 declaration for arg_mem_{number}_{pin}")
        declarations[number][pin] = (match.group("direction"), width)
    expected = set(range(MEMORY_PORT_COUNT))
    if set(declarations) != expected:
        raise RuntimeError("generated SV must declare exactly arg_mem_0 through arg_mem_145")
    assignments: dict[int, str] = {}
    for match in re.finditer(
        r"\bassign\s+arg_mem_(?P<number>\d+)_write_en\s*=\s*(?P<expression>.*?);",
        body,
        flags=re.DOTALL,
    ):
        number = int(match.group("number"))
        if number in assignments:
            raise RuntimeError(f"duplicate write-enable assignment for arg_mem_{number}")
        assignments[number] = re.sub(r"\s+", "", match.group("expression"))
    if set(assignments) != expected:
        raise RuntimeError("generated SV is missing a write-enable assignment for one or more memory ports")
    ports = []
    for number in range(MEMORY_PORT_COUNT):
        pins = declarations[number]
        if set(pins) != set(REQUIRED_PINS):
            raise RuntimeError(f"arg_mem_{number} must expose exactly the six DDR3 ABI pins")
        for name, (direction, width) in REQUIRED_PINS.items():
            actual_direction, actual_width = pins[name]
            if actual_direction != direction or (width is not None and actual_width != width):
                raise RuntimeError(f"arg_mem_{number}_{name} has incompatible direction or width")
        if pins["write_data"][1] != pins["read_data"][1]:
            raise RuntimeError(f"arg_mem_{number} read/write widths disagree")
        proven_zero = _is_proven_zero(assignments[number])
        if number in LEARNED_PORTS and not proven_zero:
            raise RuntimeError(f"arg_mem_{number} learned write-enable is not proven-zero")
        ports.append({
            "port": number,
            "pins": {name: pins[name][0] for name in REQUIRED_PINS},
            "write_enable": "proven-zero" if proven_zero else "dynamic",
            "width_bits": pins["read_data"][1],
            "depth_words": 1 << pins["addr0"][1],
            "write_enable_sha256": _sha(assignments[number]),
        })
    return ports


def _validate_memory_abi(receipt: object, ports: Sequence[Mapping[str, Any]]) -> str:
    if not isinstance(receipt, Mapping) or set(receipt) != {"schema", "ports", "canonical_json", "sha256"}:
        raise ValueError("memory ABI receipt has an unsupported schema")
    rows = receipt.get("ports")
    if (receipt.get("schema") != MEMORY_ABI_SCHEMA or not isinstance(rows, list)
            or receipt.get("canonical_json") != _canonical(rows)
            or receipt.get("sha256") != _sha(receipt["canonical_json"])):
        raise ValueError("memory ABI receipt canonical JSON or SHA-256 does not match")
    if len(rows) != MEMORY_PORT_COUNT:
        raise ValueError("memory ABI receipt must contain all 146 ports")
    for number, (row, port) in enumerate(zip(rows, ports)):
        if not isinstance(row, Mapping) or row.get("number") != number:
            raise ValueError("memory ABI receipt port rows are not ordered 0 through 145")
        if row.get("width") != port["width_bits"] or row.get("depth") != port["depth_words"]:
            raise ValueError(f"memory ABI receipt disagrees with arg_mem_{number} dimensions")
        if row.get("write_enable_sha256") != port["write_enable_sha256"]:
            raise ValueError(f"memory ABI receipt disagrees with arg_mem_{number} write-enable")
    return receipt["sha256"]


def build_evidence(sv_paths: Sequence[Path], memory_abi: object) -> dict[str, Any]:
    """Parse generated SV and return canonical, source-byte-bound routing evidence."""
    paths = [Path(path) for path in sv_paths]
    ports = _parse_ports(_source_text(paths))
    memory_abi_sha256 = _validate_memory_abi(memory_abi, ports)
    payload = {
        "schema": EVIDENCE_SCHEMA,
        "source_sha256": source_sha256(paths),
        "memory_abi_sha256": memory_abi_sha256,
        "completion": COMPLETION,
        "ports": [
            {key: port[key] for key in ("port", "pins", "write_enable")}
            for port in ports
        ],
    }
    canonical = _canonical(payload)
    return {**payload, "canonical_json": canonical, "sha256": _sha(canonical)}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-abi", required=True, type=Path)
    parser.add_argument("--sv", action="append", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    evidence = build_evidence(args.sv, json.loads(args.memory_abi.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
