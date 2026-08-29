#!/usr/bin/env python3
"""Statically inspect Verilator's public hierarchy for Calyx memories.

This probe is intentionally not an inference test.  With ``--public-flat-rw``
Verilator emits the internal ``seq_mem_d1`` arrays in ``V<top>___024root.h``;
the report records their exact C++ spellings and whether all expected 64x32
arrays are present.  It is useful for deciding whether a memory-initializing
testbench can be written without changing the generated RTL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(root_header: Path, *, top: str = "main") -> dict[str, object]:
    text = root_header.read_text(encoding="utf-8")
    # Verilator represents each unpacked 32-bit memory as a VlUnpacked<IData,64>
    # field.  Keep the complete generated C++ member name: callers include the
    # root header and use model.rootp()-><member> with --public-flat-rw.
    pattern = re.compile(
        r"VlUnpacked<IData/\*31:0\*/,\s*64>\s+(?P<name>main__DOT__mem_[0-3]__DOT__mem);"
    )
    names = sorted(match.group("name") for match in pattern.finditer(text))
    expected = [f"main__DOT__mem_{index}__DOT__mem" for index in range(4)]
    return {
        "schema": "verilator-calyx-memory-hierarchy-probe-v1",
        "top": top,
        "root_header": str(root_header),
        "root_header_sha256": sha256(root_header),
        "public_flat_rw": bool(names),
        "memory_fields": names,
        "expected_memory_fields": expected,
        "all_expected_memory_fields_present": names == expected,
        "field_shape": {"width_bits": 32, "depth": 64},
        "claim_scope": "hierarchy_compile_probe_only",
        "inference_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-header", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top", default="main")
    args = parser.parse_args()
    report = inspect(args.root_header, top=args.top)
    report["sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
