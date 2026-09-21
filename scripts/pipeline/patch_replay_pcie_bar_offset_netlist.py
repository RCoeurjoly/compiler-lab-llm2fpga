#!/usr/bin/env python3
"""Make replay CSR decoding relative to the authenticated 4-KiB PCIe BAR.

The PCIe bridge supplies absolute host addresses, while the replay CSR window
occupies offsets 0x900..0x97f.  The timing-passing baseline retained bits
31:12 in the captured AW/AR addresses.  Disconnect only their authenticated
input consumers so decode and forwarded loader addresses use the BAR offset.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path


TOP = "compiler_ddr3_trace_replay_top"
SOURCE_SHA256 = "f24399228ba1009fbf1c890c01bfc670c140919479ca5df5d82c41c2c3c40e22"
RESET_PATCHED_SHA256 = "bcf7027888c52b9724d6d18c21d816cddd2e91995f07735437134ad8c8bf2ea9"
SOURCE_SHA256S = {SOURCE_SHA256, RESET_PATCHED_SHA256}
ADDRESS_NETS = {
    "replay_bridge.awaddr": "80b1d704ba5e4f898b35d1b3c7806e5cd8024857fffd221d0527fa5a1ac8bec5",
    "replay_bridge.araddr": "be2d399af65dd97c3a9b62e9277d84345a1e2753a54e5c927ca7570811301c7f",
}


def output_sites(module, bit):
    sites = []
    for name, cell in module["cells"].items():
        for port, bits in cell.get("connections", {}).items():
            if cell.get("port_directions", {}).get(port) == "output" and bit in bits:
                sites.append([name, port])
    return sorted(sites)


def _input_sites(module, bits):
    selected = set(bits)
    sites = []
    for name, cell in module["cells"].items():
        for port, connection in cell.get("connections", {}).items():
            if cell.get("port_directions", {}).get(port) == "output":
                continue
            hits = sorted(selected.intersection(item for item in connection if isinstance(item, int)))
            if hits:
                sites.append([name, port, hits])
    return sorted(sites)


def _signature(sites):
    payload = json.dumps(sites, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def patch_document(document, source_sha256=SOURCE_SHA256):
    try:
        module = document["modules"][TOP]
    except KeyError as error:
        raise ValueError(f"missing authenticated object: {error}") from error

    all_sites = []
    high_bits = set()
    for net, expected_signature in ADDRESS_NETS.items():
        bits = module["netnames"][net]["bits"]
        if len(bits) != 32 or not all(isinstance(bit, int) for bit in bits[12:]):
            raise ValueError(f"{net} high-address structure mismatch")
        selected = bits[12:]
        sites = _input_sites(module, selected)
        if len(sites) != 40 or _signature(sites) != expected_signature:
            raise ValueError(f"{net} consumer set does not match authenticated baseline")
        if any(len(output_sites(module, bit)) != 1 for bit in selected):
            raise ValueError(f"{net} driver set does not match authenticated baseline")
        all_sites.extend(sites)
        high_bits.update(selected)

    for name, port, _ in all_sites:
        module["cells"][name]["connections"][port] = [
            "0" if bit in high_bits else bit
            for bit in module["cells"][name]["connections"][port]
        ]

    return document, {
        "schema": "compiler-replay-pcie-bar-offset-netlist-patch-v1",
        "top": TOP,
        "source_sha256": source_sha256,
        "address_nets": sorted(ADDRESS_NETS),
        "zeroed_high_bits_per_address": 20,
        "changed_consumer_ports": len(all_sites),
        "changed_existing_cells": sorted({site[0] for site in all_sites}),
        "added_cells": [],
        "added_netnames": [],
        "invariants": {
            "address_register_drivers_unchanged": True,
            "pcie_ddr_clock_and_reset_cells_unchanged": True,
        },
    }


def patch_file(source, output, receipt_path):
    source_bytes = source.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual not in SOURCE_SHA256S:
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    patched, receipt = patch_document(copy.deepcopy(json.loads(source_bytes)), actual)
    rendered = (json.dumps(patched, indent=2) + "\n").encode()
    receipt["output_sha256"] = hashlib.sha256(rendered).hexdigest()
    output.write_bytes(rendered)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    patch_file(args.source, args.output, args.receipt)


if __name__ == "__main__":
    main()
