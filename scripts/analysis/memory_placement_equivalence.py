"""Cycle-accurate, deterministic BRAM/DDR3 projection-memory reference.

This is deliberately a small compiler-boundary model: it does not replace the
UberDDR3 RTL.  It makes the logical byte-address contract and the latency/cache
policy executable before either backend is connected to the complete kernel.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Sequence


def _digest(values: Iterable[int]) -> str:
    return hashlib.sha256(bytes(v & 0xFF for v in values)).hexdigest()


@dataclass(frozen=True)
class ProjectionTable:
    logical_name: str
    width_bits: int
    depth_words: int
    data: bytes
    source_sha256: str
    source_path: str

    def __post_init__(self) -> None:
        if self.width_bits != 8:
            raise ValueError("the authenticated projection contract is INT8")
        if len(self.data) != self.depth_words:
            raise ValueError("projection image length does not match depth")


class BramBackend:
    """Synchronous one-cycle read model at the compiler memory boundary."""

    def __init__(self, table: ProjectionTable) -> None:
        self.table = table
        self.stats = {"cycles": 0, "external_requests": 0, "cache_hits": 0}

    def read_trace(self, addresses: Sequence[int]) -> list[dict[str, int]]:
        result = []
        for address in addresses:
            if not 0 <= address < self.table.depth_words:
                raise IndexError(address)
            self.stats["cycles"] += 1
            result.append({"cycle": self.stats["cycles"], "address": address, "data": self.table.data[address]})
        return result


class Ddr3PrefetchBackend:
    """Single-outstanding DDR3 model with line-aligned sequential prefetch.

    A miss fetches ``prefetch_lines`` 128-bit (16-byte) lines.  The first
    response incurs a bounded 5-cycle request plus 4-cycle read completion;
    hits take one cycle.  Data ordering is independent of these transport
    cycles and is the equivalence boundary consumed by the compiler kernel.
    """

    def __init__(self, table: ProjectionTable, *, line_bytes: int = 16, prefetch_lines: int = 8) -> None:
        if line_bytes != 16 or prefetch_lines < 1:
            raise ValueError("only the validated 128-bit (16-byte) DDR3 port is supported")
        self.table = table
        self.line_bytes = line_bytes
        self.prefetch_lines = prefetch_lines
        self.stats = {"cycles": 0, "external_requests": 0, "cache_hits": 0, "cache_bytes": 0}
        self._cache: dict[int, int] = {}

    def _fill(self, address: int) -> None:
        first_line = (address // self.line_bytes) * self.line_bytes
        end = min(len(self.table.data), first_line + self.line_bytes * self.prefetch_lines)
        for index in range(first_line, end):
            self._cache[index] = self.table.data[index]
        self.stats["external_requests"] += 1
        self.stats["cache_bytes"] = len(self._cache)

    def read_trace(self, addresses: Sequence[int]) -> list[dict[str, int]]:
        result = []
        for address in addresses:
            if not 0 <= address < self.table.depth_words:
                raise IndexError(address)
            if address in self._cache:
                self.stats["cache_hits"] += 1
                self.stats["cycles"] += 1
            else:
                self._fill(address)
                self.stats["cycles"] += 9
            result.append({"cycle": self.stats["cycles"], "address": address, "data": self._cache[address]})
        return result


def _gemv(table: ProjectionTable, responses: Sequence[dict[str, int]], input_codes: Sequence[int]) -> list[int]:
    # The compiler's signed-64 wrapping MAC.  Repeat the short fixture input
    # across output channels; the memory backend must not alter arithmetic.
    if not input_codes:
        raise ValueError("input_codes must not be empty")
    output = []
    for base in range(0, len(responses), len(input_codes)):
        acc = 0
        for offset, code in enumerate(input_codes):
            if base + offset >= len(responses):
                break
            weight = responses[base + offset]["data"]
            weight = weight - 256 if weight & 0x80 else weight
            acc = (acc + weight * code) & ((1 << 64) - 1)
        output.append(acc)
    return output


def run_equivalence(table: ProjectionTable, addresses: Sequence[int], *, input_codes: Sequence[int]) -> dict:
    bram = BramBackend(table)
    ddr3 = Ddr3PrefetchBackend(table)
    bram_trace = bram.read_trace(addresses)
    ddr3_trace = ddr3.read_trace(addresses)
    first_mismatch = None
    for index, (left, right) in enumerate(zip(bram_trace, ddr3_trace)):
        if left["address"] != right["address"] or left["data"] != right["data"]:
            first_mismatch = {"index": index, "bram": left, "ddr3": right}
            break
    bram_output = _gemv(table, bram_trace, input_codes)
    ddr3_output = _gemv(table, ddr3_trace, input_codes)
    return {
        "schema": "tinystories-1m-projection-memory-equivalence-v1",
        "status": "pass" if first_mismatch is None and bram_output == ddr3_output else "fail",
        "contract": {
            "logical_name": table.logical_name,
            "width_bits": table.width_bits,
            "depth_words": table.depth_words,
            "read_only": True,
            "bram_read_latency": 1,
            "ddr3_line_bytes": 16,
            "ddr3_prefetch_lines": ddr3.prefetch_lines,
            "source_path": table.source_path,
            "source_sha256": table.source_sha256,
            "image_sha256": hashlib.sha256(table.data).hexdigest(),
        },
        "trace": {"addresses": len(addresses), "bram_response_sha256": _digest(x["data"] for x in bram_trace), "ddr3_response_sha256": _digest(x["data"] for x in ddr3_trace)},
        "bram": {**bram.stats, "response_sha256": _digest(x["data"] for x in bram_trace), "output_sha256": _digest(x & 0xFF for value in bram_output for x in value.to_bytes(8, "little"))},
        "ddr3": {**ddr3.stats, "response_sha256": _digest(x["data"] for x in ddr3_trace), "output_sha256": _digest(x & 0xFF for value in ddr3_output for x in value.to_bytes(8, "little"))},
        "first_mismatch": first_mismatch,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from pathlib import Path
    path = Path(args.image)
    raw = bytes(int(line.strip(), 16) for line in path.read_text().splitlines() if line.strip())[:4096]
    table = ProjectionTable("blocks.0.attn.q.weight", 8, len(raw), raw, hashlib.sha256(path.read_bytes()).hexdigest(), str(path))
    addresses = list(range(256)) + [0, 15, 16, 255]
    result = run_equivalence(table, addresses, input_codes=[-3, 7, 11, -5] * 16)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "first_mismatch": result["first_mismatch"]}))


if __name__ == "__main__":
    main()
