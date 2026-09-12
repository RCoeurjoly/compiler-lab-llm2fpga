#!/usr/bin/env python3
"""Verify the exact TinyStories Torch-MLIR legalization boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


GEMV = '"llm2fpga.serial_gemv"'
EXPECTED_CALLS = 49


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(mlir: Path) -> dict[str, object]:
    text = mlir.read_text(encoding="utf-8")
    calls = len(re.findall(re.escape(GEMV), text))
    raw = len(re.findall(r'"torch\.operator"', text))
    attrs = len(re.findall(r'mac_order = "ascending_i64_wrap"', text))
    if calls != EXPECTED_CALLS:
        raise SystemExit(f"expected {EXPECTED_CALLS} GEMV calls, found {calls}")
    if raw:
        raise SystemExit(f"unlegalized torch.operator nodes remain: {raw}")
    if attrs != EXPECTED_CALLS:
        raise SystemExit(f"GEMV contract attributes missing: {attrs}/{EXPECTED_CALLS}")
    return {
        "schema": "tinystories-1m-exact-torch-mlir-gate-v1",
        "status": "legalized",
        "mlir_sha256": sha256(mlir),
        "gemv_calls": calls,
        "raw_torch_operator_calls": raw,
        "ascending_i64_wrap_contracts": attrs,
        "bounded_build_seconds": 1800,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mlir", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.mlir)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
