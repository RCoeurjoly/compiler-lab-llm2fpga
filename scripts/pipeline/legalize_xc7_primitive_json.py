#!/usr/bin/env python3
"""Legalize XC7 BRAM vectors before nextpnr.

Yosys' XC7 BRAM techmap can serialize a complete physical write-enable vector
even when only a subset of lanes is meaningful.  The pinned nextpnr packer
expects two logical WEA lanes for RAMB18E1 and four for RAMB36E1; it expands
those lanes to the physical pins itself.  A one-element RAMB18 vector is
parsed as scalar ``WEA`` and cannot be transformed, while retaining lanes
beyond the logical width creates duplicate physical pins.  For an unused
SDP write side, the vector must be absent entirely.

The transform operates on Yosys JSON modules and is deliberately limited to
the pinned XC7 RAMB18E1/RAMB36E1 ABI.  A receipt is emitted when requested so
the transform is auditable and restartable.
"""

from __future__ import annotations

import argparse
from collections import Counter
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


def _trim_lanes(cell: dict[str, Any], port: str, width: int, logical_lanes: int) -> int:
    connections = cell.get("connections", {})
    lanes = connections.get(port)
    if not isinstance(lanes, list):
        return 0
    if width == 0:
        cell["connections"].pop(port, None)
        cell.get("port_directions", {}).pop(port, None)
        return len(lanes)
    used = min(max(width // 9, 1), logical_lanes)
    # Keep the logical lanes in their original order.  For a narrow RAMB18,
    # retain a second constant-disabled logical lane so the frontend names the
    # ports WEA[0]/WEA[1] rather than scalar WEA.
    kept = lanes[:used]
    if logical_lanes == 2 and used == 1:
        kept.append("0")
    removed = max(0, len(lanes) - len(kept))
    if kept != lanes:
        cell["connections"][port] = kept
    return removed or int(kept != lanes)


def _trim_port(cell: dict[str, Any], port: str, width: int, net_refs: Counter[str] | None = None) -> int:
    """Keep only the physical XC7 port width, preserving low-order lanes."""
    lanes = cell.get("connections", {}).get(port)
    if not isinstance(lanes, list) or len(lanes) <= width:
        return 0
    if net_refs is not None:
        dropped = [str(net) for net in lanes[width:] if isinstance(net, int)]
        if any(net_refs[net] > 1 for net in dropped):
            raise ValueError(f"cannot trim consumed output lanes on {port}")
    cell["connections"][port] = lanes[:width]
    return len(lanes) - width


def _normalize_full_width_address(cell: dict[str, Any], port: str, logical_width: int) -> int:
    """Undo the extra address bit emitted by the 72-bit XC7 BRAM map.

    The pinned Yosys map constructs a full-width RAMB36 address as
    ``{1'b1, PORT_ADDR}``.  When ``PORT_ADDR`` is still the generic 16-bit
    bus, JSON contains 17 lanes: the source's unused high zero at lane 15 and
    the required constant-one extension at lane 16.  XC7 exposes only 16
    physical address pins; remove that proven-unused zero lane while retaining
    the extension bit at the physical MSB.  Any other 17-lane shape fails
    closed rather than silently changing an address.
    """
    if cell.get("type") != "RAMB36E1" or logical_width != 72:
        return 0
    lanes = cell.get("connections", {}).get(port)
    if not isinstance(lanes, list) or len(lanes) <= 16:
        return 0
    if len(lanes) != 17 or lanes[15] != "0" or lanes[16] != "1":
        raise ValueError(f"cannot normalize unexpected {port} address shape")
    cell["connections"][port] = lanes[:15] + lanes[16:]
    return 1


def legalize(document: dict[str, Any]) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    for module_name, module in document.get("modules", {}).items():
        net_refs = Counter(
            str(bit)
            for cell in module.get("cells", {}).values()
            for bits in cell.get("connections", {}).values()
            for bit in bits
            if isinstance(bit, int)
        )
        for cell_name, cell in module.get("cells", {}).items():
            if cell.get("type") not in {"RAMB18E1", "RAMB36E1"}:
                continue
            width_a = _int_param(cell, "WRITE_WIDTH_A")
            logical_lanes = 2 if cell["type"] == "RAMB18E1" else 4
            removed = _trim_lanes(cell, "WEA", width_a, logical_lanes)
            removed_ports = 0
            # brams_xc6v_map.v exposes 64/8-bit intermediate input buses,
            # while the Kintex-7 RAMB36E1 and RAMB18E1 BELs have 32/4-bit and
            # 16/2-bit DI/DO-plus-parity ports, respectively.  The map
            # interleaves parity explicitly; retaining the low physical lanes
            # is therefore ABI normalization. Output lanes are trimmed only
            # when the module-local net-use invariant proves they are
            # driver-only; consumed logical read-data lanes are rejected.
            data_width = 16 if cell["type"] == "RAMB18E1" else 32
            parity_width = 2 if cell["type"] == "RAMB18E1" else 4
            for port in ("DIADI", "DIBDI"):
                removed_ports += _trim_port(cell, port, data_width)
            for port in ("DIPADIP", "DIPBDIP"):
                removed_ports += _trim_port(cell, port, parity_width)
            for port in ("DOADO", "DOBDO"):
                removed_ports += _trim_port(cell, port, data_width, net_refs)
            for port in ("DOPADOP", "DOPBDOP"):
                removed_ports += _trim_port(cell, port, parity_width, net_refs)
            removed_ports += _normalize_full_width_address(
                cell, "ADDRARDADDR", _int_param(cell, "READ_WIDTH_A")
            )
            removed_ports += _normalize_full_width_address(
                cell, "ADDRBWRADDR", _int_param(cell, "WRITE_WIDTH_B")
            )
            if removed or removed_ports:
                changed.append(
                    {
                        "module": module_name,
                        "cell": cell_name,
                        "primitive": cell["type"],
                        "write_width_a": width_a,
                        "removed_wea_lanes": removed,
                        "removed_physical_port_lanes": removed_ports,
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
            "scope": "XC7 RAMB18/RAMB36 write-enable, address, and physical data/parity port widths",
            **result,
        }
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
