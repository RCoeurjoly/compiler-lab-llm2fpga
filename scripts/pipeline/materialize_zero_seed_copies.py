#!/usr/bin/env python3
"""Replace copies from zero-filled scratch seeds with destination zero-fills.

Calyx may safely reuse storage for non-overlapping memrefs, but a copy whose
source is intended to remain an immutable zero seed becomes a stale self-copy
when source and destination share physical storage.  Materializing the copy as
a destination fill preserves the flat-SCF semantics under that allocation.
"""

import json
import re
import sys
from pathlib import Path


ALLOC = re.compile(
    r"(?m)^\s*(%[\w.]+) = memref\.alloc\([^\n)]*\)[^\n]*"
    r": memref<(\d+)x([\w]+)(?:,[^\n]*)?>\s*$"
)
VIEW = re.compile(
    r"(?m)^\s*(%[\w.]+) = memref\.reinterpret_cast\s+(%[\w.]+)\b[^\n]*$"
)
ZERO_FILL = re.compile(
    r"(?ms)^([ \t]*)scf\.for\s+(%[\w.]+)\s*=\s+(%[\w.]+)\s+to\s+(%[\w.]+)"
    r"\s+step\s+(%[\w.]+)\s*\{\s*"
    r"memref\.store\s+(%[\w.]+),\s+(%[\w.]+)\[\2\][^\n]*\n\1\}"
)
COPY = re.compile(
    r"(?m)^(?P<indent>[ \t]*)memref\.copy\s+(?P<src>%[\w.]+),\s+"
    r"(?P<dst>%[\w.]+)\s*:[^\n]*$"
)


def materialize(source: str) -> tuple[str, list[dict[str, object]]]:
    allocations = {
        match.group(1): (int(match.group(2)), match.group(3).strip())
        for match in ALLOC.finditer(source)
    }
    bases = {match.group(1): match.group(2) for match in VIEW.finditer(source)}
    bases.update({name: name for name in allocations})
    zero_seeds: dict[str, tuple[str, str, str, str]] = {}
    for match in ZERO_FILL.finditer(source):
        base = match.group(7)
        if base in allocations:
            zero_seeds[base] = (match.group(3), match.group(4), match.group(5), match.group(6))

    changes: list[dict[str, object]] = []

    def replace(match: re.Match[str]) -> str:
        source_base = bases.get(match.group("src"))
        destination_base = bases.get(match.group("dst"))
        seed = zero_seeds.get(source_base or "")
        if seed is None or destination_base not in allocations:
            return match.group(0)
        source_shape = allocations[source_base]
        destination_shape = allocations[destination_base]
        if source_shape != destination_shape:
            return match.group(0)
        lower, upper, step, zero = seed
        indent = match.group("indent")
        induction = f"%zero_fill_{len(changes)}"
        changes.append(
            {
                "source": match.group("src"),
                "destination": match.group("dst"),
                "element_count": destination_shape[0],
            }
        )
        return (
            f"{indent}scf.for {induction} = {lower} to {upper} step {step} {{\n"
            f"{indent}  memref.store {zero}, {destination_base}[{induction}] "
            f": memref<{destination_shape[0]}x{destination_shape[1]}, strided<[1]>>\n"
            f"{indent}}}"
        )

    return COPY.sub(replace, source), changes


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <input.mlir> <output.mlir> <receipt.json>", file=sys.stderr)
        return 2
    rewritten, changes = materialize(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(rewritten, encoding="utf-8")
    Path(sys.argv[3]).write_text(
        json.dumps(
            {
                "status": "ok",
                "materialized_copy_count": len(changes),
                "materialized_copies": changes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
