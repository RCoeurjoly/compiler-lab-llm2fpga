#!/usr/bin/env python3
"""Remove unused XC7 BRAM write-enable lanes before nextpnr.

Yosys' XC7 BRAM techmap can serialize the complete physical write-enable
vector even when a narrow RAMB18E1 port uses only one or two byte lanes.  The
XC7 nextpnr packer expands WEA[0]/WEA[1] to WEA0..WEA3 itself; retaining the
unused WEA[2]/WEA[3] entries makes those names collide during packing.  This
bounded legalization keeps only the lanes implied by WRITE_WIDTH_A.  The
packer adds and ties the omitted physical lanes to the appropriate constant
after its own expansion, so no logical data path is changed.

The transform operates on Yosys JSON modules and is deliberately limited to
RAMB18E1.  It does not alter nets, initialization data, addresses, or any
other primitive.  A receipt is emitted when requested so the transform is
auditable and restartable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _int_param(cell: dict[str, Any], name: str, default: int = 0) -> int:
    value = cell.get("parameters", {}).get(name, default)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Yosys JSON encodes integer parameters as a zero-padded binary string.
        try:
            return int(value, 2)
        except ValueError:
            return default
    return default


def _trim_lanes(cell: dict[str, Any], port: str, width: int) -> int:
    connections = cell.get("connections", {})
    directions = cell.get("port_directions", {})
    lanes = connections.get(port)
    if not isinstance(lanes, list):
        return 0
    used = max(width // 9, 1)
    # Keep the logical lanes in their original order.  The nextpnr packer
    # expands WEA[0]/WEA[1] into the physical pins and supplies unused pins.
    removed = 0
    for index in range(used, len(lanes)):
        key = f"{port}[{index}]"
        if key in directions:
            del directions[key]
        removed += 1
    if removed:
        cell["connections"][port] = lanes[:used]
    return removed


def legalize(document: dict[str, Any]) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    for module_name, module in document.get("modules", {}).items():
        for cell_name, cell in module.get("cells", {}).items():
            if cell.get("type") != "RAMB18E1":
                continue
            width_a = _int_param(cell, "WRITE_WIDTH_A")
            removed = _trim_lanes(cell, "WEA", width_a)
            if removed:
                changed.append(
                    {
                        "module": module_name,
                        "cell": cell_name,
                        "write_width_a": width_a,
                        "removed_wea_lanes": removed,
                    }
                )
    return {"changed": changed, "changed_cells": len(changed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    source = args.input.read_bytes()
    document = json.loads(source)
    result = legalize(document)
    encoded = (json.dumps(document, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "llm2fpga.xc7-primitive-json-legalization.v1",
            "status": "PASS" if result["changed_cells"] else "NOOP",
            "input": str(args.input),
            "input_sha256": hashlib.sha256(source).hexdigest(),
            "output": str(args.output),
            "output_sha256": hashlib.sha256(encoded).hexdigest(),
            "scope": "RAMB18E1 WEA lanes only",
            **result,
        }
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
