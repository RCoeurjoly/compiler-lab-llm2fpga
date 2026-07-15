#!/usr/bin/env python3
"""Write a durable report from a nextpnr-xilinx pack/place/route attempt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


DEVICE_UTILISATION_HEADER = re.compile(
    r"^\s*(?:Info:\s*)?Device utilisation:\s*$", re.IGNORECASE
)
DEVICE_UTILISATION_ROW = re.compile(
    r"^\s*(?:Info:\s*)?(?P<name>.+?):\s*"
    r"(?P<used>\d+)\s*/\s*(?P<available>\d+)\s+"
    r"(?P<pct>\d+(?:\.\d+)?)\s*%\s*$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nextpnr-log", required=True)
    parser.add_argument("--stdout-log", required=True)
    parser.add_argument("--stderr-log", required=True)
    parser.add_argument("--exit-status", required=True, type=int)
    parser.add_argument("--fasm", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def parse_device_utilisation(log: str) -> list[dict[str, int | float | str]]:
    """Parse every row in the nextpnr device-utilisation table.

    Resource names are deliberately captured from the log rather than mapped
    to a fixed set: nextpnr versions and device families may report different
    resource types.
    """

    in_table = False
    rows: list[dict[str, int | float | str]] = []
    for line in log.splitlines():
        if DEVICE_UTILISATION_HEADER.match(line):
            in_table = True
            continue
        if not in_table:
            continue
        match = DEVICE_UTILISATION_ROW.match(line)
        if match is None:
            # A utilisation table is a contiguous block after its header. Keep
            # scanning for a later table header, but never admit row-shaped
            # lines from a subsequent log section.
            in_table = False
            continue
        pct_text = match.group("pct")
        pct: int | float = float(pct_text) if "." in pct_text else int(pct_text)
        rows.append(
            {
                "name": match.group("name").strip(),
                "used": int(match.group("used")),
                "available": int(match.group("available")),
                "pct": pct,
            }
        )
    return rows


def file_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return "present" if path.stat().st_size > 0 else "empty"


def route_outcome(exit_status: int, fasm_status: str) -> tuple[str, str]:
    if exit_status != 0:
        return "failed", f"nextpnr exited with status {exit_status}"
    if fasm_status != "present":
        return (
            "incomplete",
            "nextpnr exited with status 0 but did not produce a nonempty FASM",
        )
    return "success", "nextpnr exited with status 0 and produced a nonempty FASM"


def report(args: argparse.Namespace) -> dict[str, Any]:
    nextpnr_log = Path(args.nextpnr_log)
    fasm = Path(args.fasm)
    fasm_status = file_status(fasm)
    route_status, route_reason = route_outcome(args.exit_status, fasm_status)
    return {
        "schema_version": 1,
        "report_kind": "nextpnr-xilinx-pnr-report",
        "route": {
            "exit_status": args.exit_status,
            "status": route_status,
            "reason": route_reason,
        },
        "fasm": {"path": str(fasm), "status": fasm_status},
        "logs": {
            "nextpnr": str(nextpnr_log),
            "stdout": str(Path(args.stdout_log)),
            "stderr": str(Path(args.stderr_log)),
        },
        "device_utilisation": parse_device_utilisation(
            nextpnr_log.read_text(encoding="utf-8")
        ),
    }


def main() -> None:
    args = parse_args()
    Path(args.out).write_text(
        json.dumps(report(args), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
