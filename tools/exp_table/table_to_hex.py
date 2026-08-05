#!/usr/bin/env python3
"""Convert the validated RC table payload to one-word-per-line Verilog hex."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from table_format import HEADER, decode_table


def convert(source: Path, output: Path) -> None:
    spec = decode_table(source)
    raw = source.read_bytes()[HEADER.size:]
    words = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, len(raw), 4)]
    if len(words) != spec.entry_count:
        raise ValueError("entry count mismatch")
    output.write_text("\n".join(f"{word:08x}" for word in words) + "\n", encoding="ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    convert(args.source, args.output)
