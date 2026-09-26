#!/usr/bin/env python3
"""Fail closed on a retained three-phase RC simulation diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TOKEN_ADDRESSES = (0, 71, 150)
EXPECTED_TOKENS = [0, 0, 4]
READBACK_WORDS = 237
HANDOFF_WORDS = 136


def verify_simulation_output(simulation: Path) -> dict:
    """Accept only the exact frozen run, including its complete raw readback."""
    report_path = simulation / "report.json"
    readback_path = simulation / "readback.hex"
    report = json.loads(report_path.read_text())
    if report.get("schema") != "rc-phase-composed-sv-equivalence-v1" or report.get("status") != "pass":
        raise ValueError("simulation report status is not a passing RC receipt")
    if (simulation / "runner-exit-code").read_text().strip() != "0":
        raise ValueError("simulation runner did not exit successfully")
    if report.get("compile_returncode") != 0 or report.get("simulation_returncode") != 0:
        raise ValueError("compiler or simulator did not exit successfully")
    if report.get("expected_tokens") != EXPECTED_TOKENS or report.get("actual_tokens") != EXPECTED_TOKENS:
        raise ValueError("token sequence differs from the frozen reference")
    if (report.get("readback_word_count") != READBACK_WORDS
            or report.get("actual_readback_word_count") != READBACK_WORDS
            or report.get("mismatch_count") != 0 or report.get("first_mismatch") is not None):
        raise ValueError("simulation report lacks exact complete readback")
    if report.get("handoff_checked_words") != HANDOFF_WORDS:
        raise ValueError("simulation report lacks all-word cache handoff observation")
    lines = readback_path.read_text().splitlines()
    if len(lines) != READBACK_WORDS:
        raise ValueError("raw readback has the wrong word count")
    values = []
    for address, line in enumerate(lines):
        fields = line.split()
        if len(fields) != 2 or fields[0] != str(address):
            raise ValueError(f"raw readback address {address} is missing or out of order")
        try:
            value = int(fields[1], 16)
        except ValueError as error:
            raise ValueError(f"raw readback word {address} is not hexadecimal") from error
        if value < 0 or value >= 1 << 64:
            raise ValueError(f"raw readback word {address} exceeds 64 bits")
        values.append(value)
    if [values[address] for address in TOKEN_ADDRESSES] != EXPECTED_TOKENS:
        raise ValueError("token readback differs from the frozen reference")
    return {
        "schema": "llm2fpga.rc-phase-composed-acceptance-v1",
        "status": "accepted", "tokens": EXPECTED_TOKENS,
        "readback_words": READBACK_WORDS, "handoff_checked_words": HANDOFF_WORDS,
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "readback_sha256": hashlib.sha256(readback_path.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify_simulation_output(args.simulation)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
