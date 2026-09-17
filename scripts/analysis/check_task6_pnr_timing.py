#!/usr/bin/env python3
"""Fail unless a nextpnr log meets the fixed Task 6 clock targets."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TARGETS_MHZ = {
    "rowstream_clk": 83.33,
    "pcie_user_clk": 62.50,
}


def last_max_frequency(log_text: str, clock_name: str) -> float:
    pattern = re.compile(
        rf"Max frequency for clock\s+'{re.escape(clock_name)}':\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s+MHz\s+\((?:PASS|FAIL) at"
    )
    matches = pattern.findall(log_text)
    if not matches:
        raise ValueError(f"nextpnr log has no max-frequency result for {clock_name}")
    return float(matches[-1])


def timing_failures(log_text: str) -> list[str]:
    failures = []
    for clock_name, target_mhz in TARGETS_MHZ.items():
        actual_mhz = last_max_frequency(log_text, clock_name)
        if actual_mhz < target_mhz:
            failures.append(
                f"{clock_name}: {actual_mhz:.2f} MHz < required {target_mhz:.2f} MHz"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="nextpnr log to verify")
    args = parser.parse_args()
    try:
        failures = timing_failures(args.log.read_text())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if failures:
        print("FAIL: fixed-profile timing gate")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: rowstream_clk >= 83.33 MHz and pcie_user_clk >= 62.50 MHz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
