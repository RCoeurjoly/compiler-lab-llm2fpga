#!/usr/bin/env python3
"""Add a one-stage BAR probe to the authenticated timing baseline netlist.

The existing USER1 TX-event counter is unused in the failing image because no
completion TLP is emitted.  Repoint its authenticated event consumers to the
existing AXI-Lite ARVALID net.  This preserves every cell and net while making
the counter prove whether the TLP-to-AXI converter emitted a BAR read.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

TOP = "compiler_ddr3_trace_replay_top"
SOURCE_SHA256 = "f24399228ba1009fbf1c890c01bfc670c140919479ca5df5d82c41c2c3c40e22"
TX_LIVE_BIT = 19555
BAR_ARVALID_BIT = 19853
CONSUMER_COUNT = 14
CONSUMER_SIGNATURE = "5f4bdb52ff0816936480a143a564398b81f95c948cfd3d7ff51c97fb1048d892"


def _load_reset_patch():
    path = Path(os.environ.get(
        "REPLAY_RESET_PATCH_TOOL",
        Path(__file__).with_name("patch_replay_pcie_reset_netlist.py"),
    ))
    spec = importlib.util.spec_from_file_location("replay_reset_patch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _signature(sites):
    rendered = json.dumps(sorted(sites), separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


def patch_document(document):
    reset_patch = _load_reset_patch()
    patched, reset_receipt = reset_patch.patch_document(copy.deepcopy(document))
    module = patched["modules"][TOP]
    netnames = module["netnames"]
    if netnames["pcie_7x_top_aximm_i.task6_pcie_status_i.tx_live"]["bits"] != [TX_LIVE_BIT]:
        raise ValueError("TX event net does not match authenticated baseline")
    if netnames["bar_arvalid"]["bits"] != [BAR_ARVALID_BIT]:
        raise ValueError("BAR ARVALID net does not match authenticated baseline")

    sites = []
    drivers = []
    for name, cell in module["cells"].items():
        for port, bits in cell.get("connections", {}).items():
            if TX_LIVE_BIT in bits:
                (drivers if port == "O" else sites).append([name, port])
    if drivers != [["$abc$270451$auto$blifparse.cc:557:parse_blif$280091", "O"]]:
        raise ValueError("TX event driver does not match authenticated baseline")
    if len(sites) != CONSUMER_COUNT or _signature(sites) != CONSUMER_SIGNATURE:
        raise ValueError("TX event consumer set does not match authenticated baseline")

    changed = []
    for name, port in sites:
        bits = module["cells"][name]["connections"][port]
        if bits.count(TX_LIVE_BIT) != 1:
            raise ValueError("TX event consumer multiplicity mismatch")
        module["cells"][name]["connections"][port] = [
            BAR_ARVALID_BIT if bit == TX_LIVE_BIT else bit for bit in bits
        ]
        changed.append(name)

    receipt = {
        "schema": "compiler-replay-pcie-bar-probe-netlist-patch-v1",
        "top": TOP,
        "source_sha256": SOURCE_SHA256,
        "reset_patch": reset_receipt,
        "probe": {
            "meaning": "USER1 tx_beat_count records BAR ARVALID cycles",
            "source_bit": BAR_ARVALID_BIT,
            "replaced_event_bit": TX_LIVE_BIT,
            "changed_consumer_ports": sorted(sites),
        },
        "changed_existing_cells": sorted(set(changed + reset_receipt["changed_existing_cells"])),
        "added_cells": [],
        "added_netnames": [],
    }
    return patched, receipt


def patch_file(source, output, receipt_path):
    source_bytes = source.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    original = json.loads(source_bytes)
    patched, receipt = patch_document(original)
    rendered = (json.dumps(patched, indent=2) + "\n").encode()
    receipt["output_sha256"] = hashlib.sha256(rendered).hexdigest()
    output.write_bytes(rendered)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    patch_file(args.source, args.output, args.receipt)


if __name__ == "__main__":
    main()
