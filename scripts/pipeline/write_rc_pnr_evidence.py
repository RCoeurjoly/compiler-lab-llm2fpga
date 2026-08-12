#!/usr/bin/env python3
"""Write a compact machine-readable RC nextpnr result or failure receipt."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


RESOURCE = re.compile(
    r"^Info:\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<used>\d+)\s*/\s*(?P<available>\d+)\s+(?P<pct>\d+)%\s*$"
)
TARGET = re.compile(r"target frequency (?P<mhz>\d+(?:\.\d+)?) MHz")
FMAX = re.compile(
    r"Max frequency for clock\s+'(?P<clock>[^']+)':\s*"
    r"(?P<mhz>\d+(?:\.\d+)?) MHz"
)


def parse(log_text: str, exit_status: int) -> dict[str, object]:
    resources: dict[str, dict[str, int]] = {}
    target_mhz: float | None = None
    fmax: list[dict[str, object]] = []
    failure = ""
    stage = "unknown"

    for line in log_text.splitlines():
        if match := RESOURCE.match(line):
            resources[match.group("name")] = {
                "used": int(match.group("used")),
                "available": int(match.group("available")),
                "percent": int(match.group("pct")),
            }
        if match := TARGET.search(line):
            target_mhz = float(match.group("mhz"))
        if match := FMAX.search(line):
            fmax.append(
                {"clock": match.group("clock"), "max_frequency_mhz": float(match.group("mhz"))}
            )
        if line.startswith("ERROR:"):
            failure = line.removeprefix("ERROR:").strip()
            lowered = failure.lower()
            if "pack" in lowered or "primitive" in lowered:
                stage = "packing"
            elif "place" in lowered or "expand region" in lowered:
                stage = "placement"
            elif "rout" in lowered:
                stage = "routing"
            elif "tim" in lowered or "frequency" in lowered:
                stage = "timing"

    legal_timing = exit_status == 0 and bool(fmax)
    timing_reason = (
        "post-route timing analysis completed"
        if legal_timing
        else "No valid Fmax or critical path exists because legal placement and routing did not complete."
    )
    over_capacity = any(
        value["used"] > value["available"] for value in resources.values()
    )
    return {
        "schema": "llm2fpga.rc-nextpnr-evidence.v1",
        "exit_status": exit_status,
        "result": (
            "success"
            if exit_status == 0
            else "resource-limit-failure" if over_capacity else "tool-failure"
        ),
        "stage": stage,
        "failure": failure or None,
        "resources": resources,
        "timing": {
            "status": "available" if legal_timing else "unavailable",
            "target_mhz": target_mhz,
            "target_period_ns": (
                round(1000.0 / target_mhz, 6) if target_mhz else None
            ),
            "critical_paths": fmax,
            "reason": timing_reason,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--exit-status", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = parse(args.log.read_text(encoding="utf-8"), args.exit_status)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
