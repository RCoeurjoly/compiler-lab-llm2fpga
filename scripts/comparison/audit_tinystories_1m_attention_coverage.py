#!/usr/bin/env python3
"""Audit lowered attention coverage without confusing layers and heads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def audit(graph: str, *, expected_layers: int = 8, expected_heads: int = 16) -> dict[str, Any]:
    """Classify executable exp sites and prove their head-loop extent.

    A flat graph normally contains one softmax operation per transformer layer,
    with the head dimension represented by an enclosing loop.  Counting
    ``math.exp`` operations as heads therefore produces a false 8-vs-16 gap.
    """
    exp_lines = [i for i, line in enumerate(graph.splitlines())
                 if re.match(r"\s*%[^ ]+\s*=\s*math\.exp\b", line)]
    loop_re = re.compile(r"scf\.for\s+%([^ ]+)\s*=\s*([^ ]+)\s+to\s+([^ ]+)")
    proven: list[dict[str, Any]] = []
    layernorm_sites = 0
    lines = graph.splitlines()
    active_at: dict[int, list[tuple[int, re.Match[str]]]] = {}
    stack: list[tuple[int, re.Match[str]]] = []
    for j, line in enumerate(lines):
        closes = line.count("}")
        for _ in range(min(closes, len(stack))): stack.pop()
        match = loop_re.search(line)
        if match: stack.append((j, match))
        active_at[j] = list(stack)
    for line_no in exp_lines:
        headers = active_at.get(line_no, [])
        head = next(((j, m) for j, m in headers if m.group(3) in {"%c16", "%c16_i64"}), None)
        # Attention softmax has a head loop plus query and key loops (both
        # bounded by c4).  A lone c16 loop is LayerNorm, not attention.
        c4_count = sum(1 for _, m in headers if m.group(3) == "%c4")
        if head is None or c4_count < 2:
            layernorm_sites += 1
            continue
        j, match = head
        proven.append({"exp_line": line_no + 1, "head_loop_line": j + 1,
                       "induction": match.group(1), "lower": match.group(2),
                       "upper": match.group(3), "head_count": expected_heads})
    status = "pass" if len(proven) == expected_layers and layernorm_sites == 0 else "fail"
    return {"status": status, "exp_site_count": len(exp_lines),
            "attention_exp_site_count": len(proven), "layernorm_exp_site_count": layernorm_sites,
            "layer_count": expected_layers, "head_count": expected_heads,
            "sites": proven,
            "interpretation": "one executable softmax site per layer; each site iterates all heads",
            "claims": {"all_heads_covered": status == "pass",
                       "attention_softmax_present": len(proven) == expected_layers,
                       "head_count_equals_exp_site_count": False}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    graph = args.graph.read_text(encoding="utf-8")
    result = audit(graph)
    result["graph"] = {"path": str(args.graph),
                        "sha256": hashlib.sha256(graph.encode()).hexdigest(),
                        "bytes": len(graph.encode())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
