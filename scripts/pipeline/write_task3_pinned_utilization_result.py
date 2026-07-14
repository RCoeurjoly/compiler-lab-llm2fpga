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
YOSYS_REV = "4716f4410f1508cad384d2f8542ada9f61bb7339"
YOSYS_SLANG_REV = "d82b0b163a725fc1a401fbb6b465cd862517ec1f"
PRE_IMPORT_FRONTIERS = {
    "native-sv-generation",
    "sv-to-rtlil-import",
    "interface-verify",
}


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
    if status == "mapped" and stage != "stage9":
        raise SystemExit("mapped status requires stage9")
    if stage in {
        "native-sv-generation",
        "sv-to-rtlil-import",
        "interface-verify",
    }:
        return []
    try:
        index = STAGE_ORDER.index(stage)
    except ValueError as error:
        raise SystemExit(f"unrecognized Task 3 stage: {stage}") from error
    end = index + 1 if status == "mapped" else index
    return STAGE_ORDER[:end]


def validate_result(status: str, stage: str, exit_status: int) -> None:
    if status == "mapped":
        if stage != "stage9":
            raise SystemExit("mapped status requires stage9")
        if exit_status != 0:
            raise SystemExit("mapped status requires exit status 0")
    elif exit_status == 0:
        raise SystemExit("frontier status requires a nonzero exit status")


def validate_toolchain_manifest(toolchain: dict[str, Any]) -> None:
    if toolchain.get("schema_version") != 1 or toolchain.get("source") != "task3-main":
        raise SystemExit("invalid toolchain manifest schema or source")
    for name, revision, display_name in [
        ("yosys", YOSYS_REV, "Yosys"),
        ("yosys_slang", YOSYS_SLANG_REV, "yosys-slang"),
    ]:
        package = toolchain.get(name)
        if not isinstance(package, dict):
            raise SystemExit(f"invalid toolchain manifest: missing {display_name} object")
        package_version = package.get("package_version")
        if not isinstance(package_version, str) or not package_version.strip():
            raise SystemExit(
                f"invalid toolchain manifest: {display_name} package_version is required"
            )
        if package.get("source_rev") != revision:
            raise SystemExit(
                f"invalid toolchain manifest: {display_name} source revision must equal {revision}"
            )


def validate_interface_manifest(
    interface: dict[str, Any], status: str, stage: str
) -> None:
    if interface.get("schema_version") != 1:
        raise SystemExit("invalid interface manifest schema version")
    if interface.get("top") != "main_1":
        raise SystemExit("invalid interface manifest top")
    if interface.get("port_count") != 12802 or type(interface["port_count"]) is not int:
        raise SystemExit("invalid interface manifest port count")
    if interface.get("port_bits") != 115933 or type(interface["port_bits"]) is not int:
        raise SystemExit("invalid interface manifest port bits")
    required_outputs = interface.get("required_outputs")
    if not isinstance(required_outputs, list) or "done" not in required_outputs:
        raise SystemExit("invalid interface manifest required output")
    verification = interface.get("verification")
    if verification not in {"expected-unverified", "verified-after-import"}:
        raise SystemExit("invalid interface manifest verification")
    if verification == "verified-after-import":
        direction_counts = interface.get("direction_counts")
        if not isinstance(direction_counts, dict) or any(
            type(direction_counts.get(direction)) is not int
            or direction_counts[direction] < 0
            for direction in ("input", "output")
        ):
            raise SystemExit("invalid verified interface manifest direction counts")
    if status == "mapped" or stage in STAGE_ORDER:
        if verification != "verified-after-import":
            raise SystemExit(
                "invalid interface manifest: mapped results and Task 3 stages "
                "require verification verified-after-import"
            )
    elif stage in PRE_IMPORT_FRONTIERS and verification != "expected-unverified":
        raise SystemExit(
            "invalid interface manifest: pre-import frontiers require verification "
            "expected-unverified"
        )


def main() -> None:
    args = parse_args()
    validate_result(args.status, args.stage, args.exit_status)
    toolchain = load_json(args.toolchain_manifest)
    interface = load_json(args.interface)
    validate_toolchain_manifest(toolchain)
    validate_interface_manifest(interface, args.status, args.stage)
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
