#!/usr/bin/env python3
"""Verify the ordered external-memory trace for the LayerNorm slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(trace_path: Path, vector_path: Path) -> dict[str, object]:
    rows = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        cycle, port, address, write_enable, data = line.split(",")
        rows.append((int(cycle), int(port), int(address), int(write_enable), data.lower()))
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    expected = [int(value) & 0xFFFFFFFF for value in vector["result"]["output_q16_16"]]
    if len(rows) != 256:
        raise ValueError(f"expected 256 transactions, got {len(rows)}")
    by_port = {port: [row for row in rows if row[1] == port] for port in range(4)}
    if any(len(by_port[port]) != 64 for port in range(4)):
        raise ValueError("each port must have exactly 64 transactions")
    for port in range(4):
        if [row[2] for row in by_port[port]] != list(range(64)):
            raise ValueError(f"port {port} addresses are not ascending 0..63")
    if any(row[3] != 0 for port in range(3) for row in by_port[port]):
        raise ValueError("input ports contain writes")
    output = by_port[3]
    if any(row[3] != 1 for row in output):
        raise ValueError("output port contains reads")
    for index, row in enumerate(output):
        if row[4] != f"{expected[index]:08x}":
            raise ValueError(f"output word {index} differs: {row[4]} != {expected[index]:08x}")
    return {
        "schema": "tinystories-1m-layernorm-memory-trace-verification-v1",
        "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
        "vector_sha256": vector["sha256"],
        "transactions": len(rows),
        "per_port_transactions": {str(port): len(by_port[port]) for port in range(4)},
        "addresses_ascending": True,
        "output_matches_reference": True,
        "status": "accepted",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--vector", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.trace, args.vector)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
