#!/usr/bin/env python3
"""Derive a shape-normalized structural fingerprint from Torch-MLIR text."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


RESULT_DEFINITION_RE = re.compile(
    r"^\s*(?P<results>%[-A-Za-z0-9_.$]+(?:\s*,\s*%[-A-Za-z0-9_.$]+)*)\s*=\s*"
    r"(?P<op>\"[^\"]+\"|[A-Za-z_][-A-Za-z0-9_.$]*(?:\.[-A-Za-z0-9_.$]+)*)"
)
SSA_VALUE_RE = re.compile(r"%[-A-Za-z0-9_.$]+")
SHAPED_TYPE_RE = re.compile(r"!?[A-Za-z_][-A-Za-z0-9_.]*<[^>]+>")
BRACKET_DIMENSION_RE = re.compile(r"(?:(?<=\[)|(?<=,))-?[0-9]+(?=(?:,|\]))")
TENSOR_DIMENSION_RE = re.compile(r"(?:(?<=<)|(?<=x))-?[0-9]+(?=x)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive a structural Torch-MLIR fingerprint without a curated op list."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def normalize_type_text(text: str) -> str:
    """Erase only static tensor extents; retain rank, dtype, and type family."""

    text = BRACKET_DIMENSION_RE.sub("?", text)
    return TENSOR_DIMENSION_RE.sub("?", text)


def operation_name(match: re.Match[str]) -> str:
    name = match.group("op")
    return name[1:-1] if name.startswith('"') else name


def type_tail(line: str, match: re.Match[str]) -> str:
    rhs = line[match.end() :]
    if ":" not in rhs:
        return ""
    return normalize_type_text(rhs.split(":", 1)[1].strip())


def derive_fingerprint(text: str, label: str) -> dict[str, Any]:
    producer_by_value: dict[str, str] = {}
    operation_counts: Counter[str] = Counter()
    operation_signatures: set[str] = set()
    producer_consumer_edges: set[str] = set()
    normalized_type_text: set[str] = set()

    for line in text.splitlines():
        match = RESULT_DEFINITION_RE.match(line)
        if match is None:
            continue

        op = operation_name(match)
        rhs = line[match.end() :]
        operation_counts[op] += 1
        normalized_tail = type_tail(line, match)
        operation_signatures.add(f"{op} :: {normalized_tail}")
        normalized_type_text.update(
            normalize_type_text(value)
            for value in SHAPED_TYPE_RE.findall(normalized_tail)
        )

        for value in SSA_VALUE_RE.findall(rhs):
            producer = producer_by_value.get(value)
            if producer is not None:
                producer_consumer_edges.add(f"{producer} -> {op}")

        for result in SSA_VALUE_RE.findall(match.group("results")):
            producer_by_value[result] = op

    if not operation_counts:
        raise ValueError("no SSA-producing operations were recognized in input MLIR")

    encoded = text.encode("utf-8")
    return {
        "schema_version": 1,
        "label": label,
        "input_sha256": hashlib.sha256(encoded).hexdigest(),
        "input_bytes": len(encoded),
        "operation_counts": dict(sorted(operation_counts.items())),
        "operation_names": sorted(operation_counts),
        "operation_signatures": sorted(operation_signatures),
        "producer_consumer_edges": sorted(producer_consumer_edges),
        "normalized_type_text": sorted(normalized_type_text),
    }


def main() -> None:
    args = parse_args()
    payload = derive_fingerprint(args.input.read_text(encoding="utf-8"), args.label)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
