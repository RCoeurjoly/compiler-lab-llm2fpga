#!/usr/bin/env python3
"""Run the exact generated-SV TinyStories-1M block-0 MLP crossing gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
DEFAULT_RECEIPT = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-sv-receipt.json"
)
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py"


def _load_lowerer():
    spec = importlib.util.spec_from_file_location(
        "fixed_point_mlp_crossing_calyx_cli", LOWERER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed-point MLP crossing lowerer unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _validate_yosys_stat(stdout: str) -> dict[str, int]:
    """Extract the final hierarchy totals emitted by pinned Yosys 0.66."""
    if "=== main ===" not in stdout or "=== design hierarchy ===" not in stdout:
        raise RuntimeError("Yosys stat did not report the generated main hierarchy")
    hierarchy = stdout.rsplit("=== design hierarchy ===", maxsplit=1)[1]
    values: dict[str, int] = {}
    for key, label in (
        ("cells", "cells"),
        ("memories", "memories"),
        ("memory_bits", "memory bits"),
    ):
        match = re.search(rf"(?m)^\s*(\d+)\s+{re.escape(label)}\s*$", hierarchy)
        if match is None:
            raise RuntimeError(f"Yosys stat is missing final hierarchy {label}")
        values[key] = int(match.group(1))
    if values["cells"] <= 0 or values["memories"] <= 0 or values["memory_bits"] <= 0:
        raise RuntimeError("Yosys stat reported an empty generated main hierarchy")
    return values


def _run_yosys_stat(receipt: dict[str, object]) -> dict[str, object]:
    artifacts = receipt["generated_artifacts"]
    policy = receipt["calyx_compile_policy"]
    futil = artifacts["futil"]
    synthesis_sv = artifacts["synthesis_sv"]
    if policy["same_futil_sha256"] != futil["sha256"]:
        raise RuntimeError("Yosys input is not bound to the receipt Futil")
    command = [
        "yosys",
        "-p",
        f"read_verilog -sv {synthesis_sv['path']}; hierarchy -check -top main; stat",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Yosys stat failed: {completed.stderr.strip()}")
    resources = _validate_yosys_stat(completed.stdout)
    return {
        "status": "passed",
        "same_futil_sha256": futil["sha256"],
        "synthesis_sv_sha256": synthesis_sv["sha256"],
        "command": command,
        "resources": resources,
        "stat": completed.stdout,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--composed", action="store_true")
    parser.add_argument("--yosys-stat", action="store_true")
    args = parser.parse_args()
    if not args.composed:
        parser.error("the bounded acceptance command requires --composed")

    receipt = _load_lowerer().run_composed_mlp_sv(args.fixture.resolve())
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    result: dict[str, object] = {
        "status": "passed",
        "receipt": str(args.receipt.resolve()),
        "receipt_sha256": receipt["receipt_sha256"],
        "cycles": receipt["execution"]["cycles"],
        "observed_checkpoints": len(receipt["observed"]),
    }
    if args.yosys_stat:
        yosys = _run_yosys_stat(receipt)
        result["yosys"] = {
            key: value for key, value in yosys.items() if key != "stat"
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
