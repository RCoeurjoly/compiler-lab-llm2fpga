#!/usr/bin/env python3
"""Convert the authenticated standalone softmax call to a packed integer ABI.

This is an ABI probe only.  It accepts exactly the bridge renderer's module
shape and records that 16*32 lanes of 32 bits are represented by i16384.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


OLD = "tensor<16x32xi32>"
NEW = "i16384"


def convert(source: str) -> str:
    if source.count(OLD) != 5:
        raise ValueError("expected exactly five tensor ABI occurrences")
    if "llm2fpga.attention_softmax_fixed" not in source:
        raise ValueError("authenticated softmax operation missing")
    return source.replace(OLD, NEW)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = convert(args.input.read_text(encoding="utf-8"))
    args.output.write_text(result, encoding="utf-8")
    print(hashlib.sha256(result.encode()).hexdigest())


if __name__ == "__main__":
    main()
