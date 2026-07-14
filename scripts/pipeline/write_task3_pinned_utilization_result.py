#!/usr/bin/env python3
"""Write compact, comparable evidence for the pinned Task 3 W8A8 route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROUTE = (
    "PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg -> SCF -> "
    "Calyx -> native SV -> Task 3 Xilinx synthesis"
)
STAGE_ORDER = [
    "stage1",
    "stage2",
    "stage3",
    "stage4",
    "stage5",
    "stage6",
    "stage7",
    "stage8",
    "stage9",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["mapped", "frontier"], required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--exit-status", required=True, type=int)
    parser.add_argument("--toolchain-manifest", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--utilization-summary")
    parser.add_argument("--monitor-summary")
    parser.add_argument("--command", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def completed_stages(status: str, stage: str) -> list[str]:
    if stage in {"sv-to-rtlil-import", "interface-verify"}:
        return []
    try:
        index = STAGE_ORDER.index(stage)
    except ValueError as error:
        raise SystemExit(f"unrecognized Task 3 stage: {stage}") from error
    if status == "mapped" and stage != "stage9":
        raise SystemExit("mapped status requires stage9")
    end = index + 1 if status == "mapped" else index
    return STAGE_ORDER[:end]


def main() -> None:
    args = parse_args()
    toolchain = load_json(args.toolchain_manifest)
    interface = load_json(args.interface)
    if args.status == "mapped" and not args.utilization_summary:
        raise SystemExit("--utilization-summary is required for mapped status")
    if args.status == "frontier" and args.utilization_summary:
        raise SystemExit("frontier status must not claim a utilization summary")
    summary = load_json(args.utilization_summary) if args.utilization_summary else None
    payload = {
        "schema_version": 1,
        "route": ROUTE,
        "top": interface["top"],
        "status": args.status,
        "stage": args.stage,
        "completed_stages": completed_stages(args.status, args.stage),
        "exit_status": args.exit_status,
        "toolchain": toolchain,
        "external_memory_boundary": {
            "verification": interface.get("verification", "unknown"),
            "port_count": interface["port_count"],
            "port_bits": interface["port_bits"],
            "logical_memories": 2133,
        },
        "resources": None if summary is None else summary["resources"],
        "downstream": {
            "technology_mapped_utilization_available": summary is not None,
            "nextpnr_attempted": False,
            "equivalence_attempted": False,
            "ddr3_controller_present": False,
        },
        "command": args.command,
    }
    if args.monitor_summary:
        payload["monitor_summary"] = Path(args.monitor_summary).read_text(
            encoding="utf-8"
        )
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
