#!/usr/bin/env python3
"""Extract an ordered SSA dataflow graph from operation-result MLIR text.

This is deliberately a lossless structural view for compiler diagnostics and
backend composition.  It does not lower operations or infer semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

RESULT_RE = re.compile(
    r"^\s*(?P<results>%[-A-Za-z0-9_.$]+(?:\s*,\s*%[-A-Za-z0-9_.$]+)*)\s*=\s*"
    r"(?P<op>\"[^\"]+\"|[A-Za-z_][-A-Za-z0-9_.$]*(?:\.[-A-Za-z0-9_.$]+)*)"
)
SSA_RE = re.compile(r"%[-A-Za-z0-9_.$]+")


def operation_name(match: re.Match[str]) -> str:
    value = match.group("op")
    return value[1:-1] if value.startswith('"') else value


def extract(text: str, label: str) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    producer: dict[str, int] = {}
    edges: list[dict[str, int | str]] = []
    counts: Counter[str] = Counter()
    for line_no, line in enumerate(text.splitlines(), 1):
        match = RESULT_RE.match(line)
        if match is None:
            continue
        op = operation_name(match)
        results = SSA_RE.findall(match.group("results"))
        operands = SSA_RE.findall(line[match.end() :])
        node_id = len(nodes)
        nodes.append({"id": node_id, "line": line_no, "operation": op,
                      "results": results, "operands": operands})
        counts[op] += 1
        for result in results:
            producer[result] = node_id
        for operand in operands:
            if operand in producer:
                edges.append({"from": producer[operand], "to": node_id,
                              "value": operand})
    if not nodes:
        raise ValueError("no SSA-producing operations were recognized")
    payload: dict[str, object] = {
        "schema": "llm2fpga-mlir-ssa-dataflow-v1",
        "label": label,
        "input_bytes": len(text.encode()),
        "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "operation_counts": dict(sorted(counts.items())),
        "nodes": nodes,
        "edges": edges,
    }
    payload["graph_sha256"] = hashlib.sha256(
        json.dumps({k: v for k, v in payload.items() if k != "graph_sha256"},
                   sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    payload = extract(args.input.read_text(encoding="utf-8"), args.label)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
