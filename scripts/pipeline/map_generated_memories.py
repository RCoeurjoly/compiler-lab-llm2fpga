#!/usr/bin/env python3
"""Map generated sequential memories to XC7 BRAM/LUTRAM cells with Yosys."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def build_yosys_script(input_sv: str, output_il: str, top: str = "main") -> str:
    return "\n".join(
        [
            f"read_verilog -sv {input_sv}",
            f"hierarchy -top {top} -check",
            "proc",
            "opt",
            "memory_dff",
            "memory -nomap -nosat -nowiden",
            "memory_libmap -lib +/xilinx/brams_xc4v.txt -D HAS_SIZE_36 -D HAS_CASCADE -D HAS_MIXWIDTH_SDP -lib +/xilinx/lutrams_xc5v.txt",
            f"write_rtlil {output_il}",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_sv", type=Path)
    parser.add_argument("output_il", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--top", default="main")
    parser.add_argument("--yosys", default="yosys")
    args = parser.parse_args()
    args.output_il.parent.mkdir(parents=True, exist_ok=True)
    script = build_yosys_script(str(args.input_sv), str(args.output_il), args.top)
    script_path = args.output_il.with_suffix(".ys")
    script_path.write_text(script)
    try:
        run = subprocess.run([args.yosys, "-s", str(script_path)], capture_output=True, text=True)
    finally:
        script_path.unlink(missing_ok=True)
    if run.returncode != 0:
        raise SystemExit(run.returncode)
    mapped = args.output_il.read_text()
    if "$mem_v2" in mapped:
        raise SystemExit("mapping incomplete: output still contains $mem_v2")
    receipt = {
        "schema": "tinystories-xc7-combined-memory-libmap-v1",
        "status": "passed",
        "top": args.top,
        "input_sv_sha256": hashlib.sha256(args.input_sv.read_bytes()).hexdigest(),
        "output_il_sha256": hashlib.sha256(args.output_il.read_bytes()).hexdigest(),
        "yosys": args.yosys,
        "script": script,
        "stdout_sha256": hashlib.sha256(run.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(run.stderr.encode()).hexdigest(),
    }
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
