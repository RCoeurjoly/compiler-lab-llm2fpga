#!/usr/bin/env python3
"""Preserve the generated Calyx main_1 module during Yosys flattening."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    source = raw.decode("utf-8")
    marker = "module main_1("
    if source.count(marker) != 1:
        raise SystemExit("expected exactly one generated main_1 module")
    transformed = source.replace(
        marker,
        '(* keep_hierarchy = "yes" *) module main_1(',
        1,
    )
    output = transformed.encode("utf-8")
    args.output.write_bytes(output)
    args.receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga.calyx-main-hierarchy.v1",
                "status": "ok",
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "module": "main_1",
                "attribute": "keep_hierarchy=yes",
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
