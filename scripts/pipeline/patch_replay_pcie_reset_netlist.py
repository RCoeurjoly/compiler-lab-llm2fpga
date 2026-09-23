#!/usr/bin/env python3
"""Make the replay BAR transport reset independent of the DDR clock domain."""

import argparse
import copy
import hashlib
import json
from pathlib import Path


TOP = "compiler_ddr3_trace_replay_top"
SOURCE_SHA256 = "f24399228ba1009fbf1c890c01bfc670c140919479ca5df5d82c41c2c3c40e22"
TRANSPORT_RESET_LUT = "$abc$270451$auto$blifparse.cc:557:parse_blif$270489"
ROW_READY_BIT = 161
RAW_CFG_RESET_BIT = 10470
TRANSPORT_RESET_BIT = 155

PROFILES = {
    SOURCE_SHA256: {
        "source_sha256": SOURCE_SHA256,
        "transport_reset_lut": TRANSPORT_RESET_LUT,
        "replay_pcie_init_bits": [37134, ROW_READY_BIT],
        "raw_cfg_reset_bit": RAW_CFG_RESET_BIT,
        "transport_reset_bit": TRANSPORT_RESET_BIT,
        "reset_type": "LUT2",
        "reset_init": "0111",
        "reset_connections": {"I0": [160], "I1": [ROW_READY_BIT],
                              "O": [TRANSPORT_RESET_BIT]},
    },
    "97aa66856adbcb8391bbc59b04b02ca0ac0e5dcd37bb3a926fe3f5ec982c510f": {
        "source_sha256": "97aa66856adbcb8391bbc59b04b02ca0ac0e5dcd37bb3a926fe3f5ec982c510f",
        "transport_reset_lut": "$abc$273896$auto$blifparse.cc:557:parse_blif$273929",
        "replay_pcie_init_bits": [39309, 163],
        "raw_cfg_reset_bit": 157,
        "transport_reset_bit": 152,
        "reset_type": "LUT2",
        "reset_init": "1011",
        "reset_connections": {"I0": [157], "I1": [158], "O": [152]},
    },
    "dedca1f39150eecc1561e3d07ced277034f7d90903419a358bcd473a79b68710": {
        "source_sha256": "dedca1f39150eecc1561e3d07ced277034f7d90903419a358bcd473a79b68710",
        "transport_reset_lut": "$abc$272155$auto$blifparse.cc:557:parse_blif$272158",
        "replay_pcie_init_bits": [38450, 74],
        "raw_cfg_reset_bit": 70,
        "transport_reset_bit": 64,
        "reset_type": "LUT4",
        "reset_init": "1111111111111110",
        "reset_connections": {"I0": [69], "I1": [70], "I2": [71],
                              "I3": [72], "O": [64]},
    },
    "b336c49d339a9147498d8cd6d7e3deb6eb9d14762b77e90b4a3ccdba37eaa1d9": {
        "source_sha256": "b336c49d339a9147498d8cd6d7e3deb6eb9d14762b77e90b4a3ccdba37eaa1d9",
        "transport_reset_lut": "$abc$270435$auto$blifparse.cc:557:parse_blif$270471",
        "replay_pcie_init_bits": [37087, 163],
        "raw_cfg_reset_bit": 159,
        "transport_reset_bit": 153,
        "reset_type": "LUT4",
        "reset_init": "1111111111111110",
        "reset_connections": {"I0": [158], "I1": [159], "I2": [160],
                              "I3": [161], "O": [153]},
    },
    "05edb5047a549e2da573008419283a7a1aec1df957ee802495664d45e4cc618c": {
        "source_sha256": "05edb5047a549e2da573008419283a7a1aec1df957ee802495664d45e4cc618c",
        "transport_reset_lut": "$abc$268294$auto$blifparse.cc:557:parse_blif$268349",
        "replay_pcie_init_bits": [36453, 197],
        "raw_cfg_reset_bit": 191,
        "transport_reset_bit": 186,
        "reset_type": "LUT2",
        "reset_init": "1011",
        "reset_connections": {"I0": [191], "I1": [192], "O": [186]},
    },
    # Current Nix synthesis keeps the replay bridge hierarchical.  The
    # transport-reset LUT is therefore addressed in the child module and its
    # PCIe reset input is the bridge-local bit 3 (top-level bit 7994).
    "f742f9c8fc3dfe28ce7fdf9625308c73aee1c34407bd355a5131a1b3ca85488e": {
        "source_sha256": "f742f9c8fc3dfe28ce7fdf9625308c73ee1c34407bd355a5131a1b3ca85488e",
        "transport_reset_lut": "$abc$281284$auto$blifparse.cc:557:parse_blif$282094",
        "replay_pcie_init_bits": [11504, 7966],
        "raw_cfg_reset_bit": 7994,
        "transport_reset_bit": 1844,
        "reset_type": "LUT4",
        "reset_init": "1111111111111110",
        "reset_connections": {"I0": [1740], "I1": [1741], "I2": [4], "I3": [3], "O": [1844]},
        "hierarchical_bridge": True,
        "bridge_pcie_reset_bit": 3,
    },
    "570b384ab2e3a7c5e43e3b5e6f171c03fd3960eaf77e110910c9d4f3b965fc1d": {
        "source_sha256": "570b384ab2e3a7c5e43e3b5e6f171c03fd3960eaf77e110910c9d4f3b965fc1d",
        "transport_reset_lut": "$abc$281425$auto$blifparse.cc:557:parse_blif$282255",
        "replay_pcie_init_bits": [11504, 7966],
        "raw_cfg_reset_bit": 7994,
        "transport_reset_bit": 2130,
        "reset_type": "LUT4",
        "reset_init": "1111111111111110",
        "reset_connections": {"I0": [2022], "I1": [2023], "I2": [4], "I3": [3], "O": [2130]},
        "hierarchical_bridge": True,
        "bridge_pcie_reset_bit": 3,
    },
    # The compiler-only command-boundary register causes synthesis to
    # renumber the hierarchical reset LUT. Keep this exact netlist profile
    # authenticated rather than using a heuristic cell/bit search.
    "bbbb6b6fe3000510e94b11fbe008f9df06bc577547a15455fd396fcd42f19d4f": {
        "source_sha256": "bbbb6b6fe3000510e94b11fbe008f9df06bc577547a15455fd396fcd42f19d4f",
        "transport_reset_lut": "$abc$282204$auto$blifparse.cc:557:parse_blif$283034",
        "replay_pcie_init_bits": [11504, 7966],
        "raw_cfg_reset_bit": 7994,
        "transport_reset_bit": 2130,
        "reset_type": "LUT4",
        "reset_init": "1111111111111110",
        "reset_connections": {"I0": [2022], "I1": [2023], "I2": [4], "I3": [3], "O": [2130]},
        "hierarchical_bridge": True,
        "bridge_pcie_reset_bit": 3,
    },
}


def transport_reset(cfg_reset, row_ready, bar_ready, flush_nonzero):
    del row_ready, bar_ready, flush_nonzero
    return bool(cfg_reset)


def _require_equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label} does not match authenticated baseline")


def patch_document(document, profile=None):
    profile = PROFILES[SOURCE_SHA256] if profile is None else profile
    if set(document.get("modules", {})) == set():
        raise ValueError("missing modules")
    try:
        module = document["modules"][TOP]
        cells = module["cells"]
        netnames = module["netnames"]
    except KeyError as error:
        raise ValueError(f"missing authenticated object: {error}") from error

    _require_equal(netnames["replay_pcie_init"]["bits"], profile["replay_pcie_init_bits"],
                   "row-ready synchronizer")
    if profile.get("hierarchical_bridge"):
        bridge_cell = cells["replay_bridge"]
        bridge_module = document["modules"][bridge_cell["type"]]
        bridge_netnames = bridge_module["netnames"]
        bridge_cells = bridge_module["cells"]
        _require_equal(bridge_netnames["transport_reset"]["bits"],
                       [profile["transport_reset_bit"]], "transport reset net")
        _require_equal(bridge_netnames["pcie_reset"]["bits"],
                       [profile["bridge_pcie_reset_bit"]], "bridge PCIe reset")
        _require_equal(cells["pcie_7x_top_aximm_i"]["connections"]["task6_user_cfg_rst_n_o"],
                       [7993], "raw PCIe configuration reset")
        reset_lut = bridge_cells[profile["transport_reset_lut"]]
    else:
        _require_equal(netnames["replay_bridge.transport_reset"]["bits"],
                       [profile["transport_reset_bit"]], "transport reset net")
        _require_equal(netnames["pcie_7x_top_aximm_i.user_reset_q"]["bits"],
                       [profile["raw_cfg_reset_bit"]], "raw PCIe configuration reset")
        reset_lut = cells[profile["transport_reset_lut"]]
    expected_directions = {
        port: ("output" if port == "O" else "input")
        for port in profile["reset_connections"]
    }
    _require_equal(reset_lut, {
        "hide_name": 1,
        "type": profile["reset_type"],
        "parameters": {"INIT": profile["reset_init"]},
        "attributes": reset_lut.get("attributes", {}),
        "port_directions": expected_directions,
        "connections": profile["reset_connections"],
    }, "transport reset LUT")
    reset_lut["type"] = "LUT1"
    reset_lut["parameters"]["INIT"] = "10"
    reset_lut["port_directions"] = {"I0": "input", "O": "output"}
    reset_lut["connections"] = {
        "I0": ([profile["bridge_pcie_reset_bit"]]
                if profile.get("hierarchical_bridge")
                else [profile["raw_cfg_reset_bit"]]),
        "O": [profile["transport_reset_bit"]],
    }

    receipt = {
        "schema": "compiler-replay-pcie-reset-netlist-patch-v2",
        "top": TOP,
        "source_sha256": profile["source_sha256"],
        "changed_existing_cells": [profile["transport_reset_lut"]],
        "added_cells": [],
        "added_netnames": [],
        "invariants": {
            "ddr_cells_changed": 0,
            "raw_cfg_reset_bit": profile["raw_cfg_reset_bit"],
            "transport_reset_bit": profile["transport_reset_bit"],
            "transport_reset_depends_only_on_raw_cfg_reset": True,
        },
    }
    return document, receipt


def patch_file(source, output, receipt_path):
    source_bytes = source.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual not in PROFILES:
        raise ValueError(
            f"source SHA-256 mismatch: no authenticated profile for {actual}"
        )
    document = json.loads(source_bytes)
    patched, receipt = patch_document(copy.deepcopy(document), PROFILES[actual])
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
