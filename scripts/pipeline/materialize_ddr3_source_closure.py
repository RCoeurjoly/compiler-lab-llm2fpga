#!/usr/bin/env python3
"""Create and verify the pinned UberDDR3 host-simulation source manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "uberddr3-source-closure-v1"
UBERDDR3_REVISION = "4a51b9671347130759c9980d6756918f084e2124"
INCLUDE_PATHS = ["testbench"]
MACROS = {
    "MAX_MEM": "",
    "DUAL_RANK": "",
    "SODIMM": "",
    "den8192Mb": "",
    "sg125": "",
    "x8": "",
}

# The order follows UberDDR3's XSim project: primitive simulation models, the
# controller stack, board wrapper, then the Micron DIMM model and XSim global.
SOURCE_PATHS = [
    "testbench/models/IDELAYCTRL_model.v",
    "testbench/models/IDELAYE2_model.v",
    "testbench/models/IOBUF_DCIEN_model.v",
    "testbench/models/IOBUF_model.v",
    "testbench/models/IOBUFDS_DCIEN_model.v",
    "testbench/models/IOBUFDS_model.v",
    "testbench/models/ISERDESE2_model.v",
    "testbench/models/OBUFDS_model.v",
    "testbench/models/ODELAYE2_model.v",
    "testbench/models/OSERDESE2_model.v",
    "testbench/models/OBUF_model.v",
    "rtl/ddr3_controller.v",
    "rtl/ddr3_phy.v",
    "rtl/ddr3_top.v",
    "example_demo/ypcb_00338_1p1/clk_wiz.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.xdc",
    "testbench/sim_defines.vh",
    "testbench/8192Mb_ddr3_parameters.vh",
    "testbench/ddr3.sv",
    "testbench/ddr3_module.sv",
    "testbench/ddr3_dimm_micron_sim.sv",
    "testbench/xsim/glbl.v",
]

# Inputs passed as source files to the host simulator.  Headers are provided
# through INCLUDE_PATHS and the board XDC remains closure provenance only.
COMPILE_ORDER = [
    "testbench/models/IDELAYCTRL_model.v",
    "testbench/models/IDELAYE2_model.v",
    "testbench/models/IOBUF_DCIEN_model.v",
    "testbench/models/IOBUF_model.v",
    "testbench/models/IOBUFDS_DCIEN_model.v",
    "testbench/models/IOBUFDS_model.v",
    "testbench/models/ISERDESE2_model.v",
    "testbench/models/OBUFDS_model.v",
    "testbench/models/ODELAYE2_model.v",
    "testbench/models/OSERDESE2_model.v",
    "testbench/models/OBUF_model.v",
    "rtl/ddr3_controller.v",
    "rtl/ddr3_phy.v",
    "rtl/ddr3_top.v",
    "example_demo/ypcb_00338_1p1/clk_wiz.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.v",
    "testbench/ddr3.sv",
    "testbench/ddr3_module.sv",
    "testbench/ddr3_dimm_micron_sim.sv",
    "testbench/xsim/glbl.v",
]
SUPPORT_PATHS = [
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.xdc",
    "testbench/sim_defines.vh",
    "testbench/8192Mb_ddr3_parameters.vh",
]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_selected_file(root: Path, logical_path: str) -> bytes:
    candidate = root / logical_path
    if not candidate.is_file():
        raise ValueError(f"required UberDDR3 source is missing: {logical_path}")
    if candidate.is_symlink():
        raise ValueError(f"required UberDDR3 source must not be a symlink: {logical_path}")
    return candidate.read_bytes()


def build_manifest(root: Path) -> dict[str, Any]:
    """Return the complete content-addressed source closure for ``root``."""

    root = root.resolve()
    sources = []
    for ordinal, logical_path in enumerate(SOURCE_PATHS):
        payload = _read_selected_file(root, logical_path)
        sources.append(
            {
                "ordinal": ordinal,
                "logical_path": logical_path,
                "bytes": len(payload),
                "sha256": _sha256(payload),
            }
        )
    return {
        "schema": SCHEMA,
        "uberddr3_revision": UBERDDR3_REVISION,
        "include_paths": INCLUDE_PATHS,
        "macros": MACROS,
        "sources": sources,
        "compile_order": COMPILE_ORDER,
        "support_paths": SUPPORT_PATHS,
    }


def _require_exact_keys(manifest: Mapping[str, Any]) -> None:
    expected = {
        "schema",
        "uberddr3_revision",
        "include_paths",
        "macros",
        "sources",
        "compile_order",
        "support_paths",
    }
    if set(manifest) != expected:
        raise ValueError("DDR3 source manifest has an unsupported field set")


def verify_manifest(root: Path, manifest: Mapping[str, Any]) -> None:
    """Reject any stale, incomplete, reordered, or content-mismatched closure."""

    _require_exact_keys(manifest)
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported DDR3 source manifest schema")
    if manifest.get("uberddr3_revision") != UBERDDR3_REVISION:
        raise ValueError("DDR3 source manifest is not pinned to the required UberDDR3 revision")
    if manifest.get("include_paths") != INCLUDE_PATHS:
        raise ValueError("DDR3 source manifest has unexpected include paths")
    if manifest.get("macros") != MACROS:
        raise ValueError("DDR3 source manifest has unexpected macro definitions")
    if manifest.get("compile_order") != COMPILE_ORDER:
        raise ValueError("DDR3 source manifest has an unexpected compile order")
    if manifest.get("support_paths") != SUPPORT_PATHS:
        raise ValueError("DDR3 source manifest has unexpected support paths")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != len(SOURCE_PATHS):
        raise ValueError("DDR3 source manifest has an incomplete source list")
    for ordinal, (logical_path, row) in enumerate(zip(SOURCE_PATHS, sources)):
        if not isinstance(row, Mapping):
            raise ValueError("DDR3 source manifest source row must be an object")
        if row.get("ordinal") != ordinal or row.get("logical_path") != logical_path:
            raise ValueError("DDR3 source manifest source order does not match the closure")
        payload = _read_selected_file(root.resolve(), logical_path)
        if row.get("bytes") != len(payload):
            raise ValueError(f"DDR3 source {logical_path} byte length does not match")
        if row.get("sha256") != _sha256(payload):
            raise ValueError(f"DDR3 source {logical_path} SHA-256 does not match")


def render_manifest(manifest: Mapping[str, Any]) -> str:
    """Render canonical, reproducible JSON after validating its structure."""

    _require_exact_keys(manifest)
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def _verify_checkout_revision(root: Path) -> None:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"unable to determine UberDDR3 revision at {root}")
    if completed.stdout.strip() != UBERDDR3_REVISION:
        raise ValueError(
            f"UberDDR3 checkout is {completed.stdout.strip()}, expected {UBERDDR3_REVISION}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uberddr3-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true", help="verify --out instead of writing it")
    args = parser.parse_args()

    _verify_checkout_revision(args.uberddr3_root)
    if args.verify:
        manifest = json.loads(args.out.read_text(encoding="utf-8"))
        if args.out.read_text(encoding="utf-8") != render_manifest(manifest):
            raise ValueError("DDR3 source manifest is not canonical JSON")
        verify_manifest(args.uberddr3_root, manifest)
        return

    manifest = build_manifest(args.uberddr3_root)
    verify_manifest(args.uberddr3_root, manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_manifest(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
