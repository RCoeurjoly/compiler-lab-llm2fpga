#!/usr/bin/env python3
"""Attach the authenticated serving ABI to a flat-SCF module."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PHASES = ("prefill-8", "decode-8", "decode-9")
SCHEMA = "rc-serving-w4a8-compiler-phase-abi-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("abi", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()

    source = args.input.read_bytes()
    abi_bytes = args.abi.read_bytes()
    abi = json.loads(abi_bytes)
    if abi.get("schema") != SCHEMA:
        raise SystemExit("unsupported compiler phase ABI schema")
    if tuple(phase.get("name") for phase in abi.get("phases", ())) != PHASES:
        raise SystemExit("compiler phase ABI is not in canonical order")

    text = source.decode("utf-8")
    marker = "module {"
    if text.count(marker) != 1 or not text.startswith(marker):
        raise SystemExit("expected one top-level flat-SCF module")
    abi_hash = hashlib.sha256(abi_bytes).hexdigest()
    names = ",".join(PHASES)
    header = (
        'module attributes {'
        f'llm2fpga.phase_abi_schema = "{SCHEMA}", '
        f'llm2fpga.phase_names = "{names}", '
        f'llm2fpga.phase_abi_sha256 = "{abi_hash}"'
        "} {"
    )
    output = text.replace(marker, header, 1).encode("utf-8")
    args.output.write_bytes(output)
    args.receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga.flat-scf-phase-abi-annotation-v1",
                "status": "ok",
                "input_sha256": hashlib.sha256(source).hexdigest(),
                "abi_sha256": abi_hash,
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "phases": list(PHASES),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
