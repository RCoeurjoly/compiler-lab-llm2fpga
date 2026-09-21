#!/usr/bin/env python3
"""Compose separately mapped platform and compiler Yosys JSON boundaries.

The platform JSON owns PCIe/UberDDR3.  The compiler JSON owns the generated
adapter/backend.  This tool performs only a checked module-union operation; it
does not lower RTL, flatten logic, or claim that the result is placeable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or not isinstance(value.get("modules"), dict):
        raise ValueError(f"{path} is not a Yosys JSON design")
    return value


def _port_signature(module: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    ports = module.get("ports", {})
    if not isinstance(ports, dict):
        raise ValueError("module has no ports map")
    signature: dict[str, tuple[Any, ...]] = {}
    for name, port in ports.items():
        if not isinstance(port, dict):
            raise ValueError(f"invalid port record for {name}")
        # Port bit IDs are local to each Yosys module.  They are not part of
        # the cross-module ABI and normally differ after independently
        # mapping the platform and compiler.  Compare direction and width;
        # the parent cell connections carry the actual boundary nets.
        signature[str(name)] = (
            port.get("direction"),
            len(port.get("bits", [])),
        )
    return signature


def compose(
    platform: dict[str, Any],
    compiler: dict[str, Any],
    *,
    top: str,
    boundary: str,
    platform_wins: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    platform_modules = platform["modules"]
    compiler_modules = compiler["modules"]
    if top not in platform_modules:
        raise ValueError(f"platform design has no top module {top}")
    if boundary not in compiler_modules:
        raise ValueError(f"compiler design has no boundary module {boundary}")

    top_module = platform_modules[top]
    cells = top_module.get("cells", {})
    boundary_cells = [
        name for name, cell in cells.items()
        if isinstance(cell, dict) and cell.get("type") == boundary
    ]
    if not boundary_cells:
        raise ValueError(f"platform top has no cell of type {boundary}")

    # A platform stub is replaced only after checking its ABI exactly.
    platform_boundary = platform_modules.get(boundary)
    if platform_boundary is not None:
        if _port_signature(platform_boundary) != _port_signature(compiler_modules[boundary]):
            raise ValueError(f"boundary port signature mismatch for {boundary}")

    collisions = sorted(set(platform_modules) & set(compiler_modules))
    unexpected = [name for name in collisions if name != boundary and name not in platform_wins]
    if unexpected:
        raise ValueError(
            "module collisions require explicit --platform-wins: " + ", ".join(unexpected)
        )

    result = dict(platform)
    result["modules"] = dict(platform_modules)
    result["modules"][boundary] = compiler_modules[boundary]
    added: list[str] = []
    replaced: list[str] = [boundary]
    for name, module in compiler_modules.items():
        if name == boundary:
            continue
        if name in result["modules"]:
            # Explicit platform ownership avoids accidentally changing shell
            # primitive definitions while merging a compiler netlist.
            continue
        result["modules"][name] = module
        added.append(name)

    receipt = {
        "schema": "mapped-yosys-json-composition-v1",
        "status": "PASS",
        "top": top,
        "boundary": boundary,
        "boundary_cells": boundary_cells,
        "platform_wins": sorted(platform_wins),
        "collisions": collisions,
        "replaced_modules": replaced,
        "added_modules": added,
        "platform_sha256": hashlib.sha256(
            json.dumps(platform, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "compiler_sha256": hashlib.sha256(
            json.dumps(compiler, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    return result, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-json", type=Path, required=True)
    parser.add_argument("--compiler-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--platform-wins", nargs="*", default=[])
    args = parser.parse_args()

    composed, receipt = compose(
        _load(args.platform_json),
        _load(args.compiler_json),
        top=args.top,
        boundary=args.boundary,
        platform_wins=set(args.platform_wins),
    )
    args.output_json.write_text(json.dumps(composed, separators=(",", ":")) + "\n", encoding="utf-8")
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
