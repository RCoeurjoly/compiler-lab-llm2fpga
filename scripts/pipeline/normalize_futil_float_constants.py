#!/usr/bin/env python3
"""Encode CIRCT decimal f32 constants for Calyx versions predating that syntax."""

import re
import struct
import sys
from pathlib import Path


FLOAT_CONST = re.compile(r"std_float_const\(0,\s*32,\s*([+-]?[0-9.]+)\)")


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input.futil> <output.futil>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).read_text(encoding="utf-8")

    def encode(match: re.Match[str]) -> str:
        bits = struct.unpack(">I", struct.pack(">f", float(match.group(1))))[0]
        return f"std_const(32, {bits})"

    normalized, count = FLOAT_CONST.subn(encode, source)
    Path(sys.argv[2]).write_text(normalized, encoding="utf-8")
    print(f"encoded {count} f32 constant(s) as IEEE-754 bit patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
