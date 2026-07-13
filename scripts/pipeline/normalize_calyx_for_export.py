#!/usr/bin/env python3
"""Remove dead private MemRef globals that CIRCT's Calyx exporter cannot parse."""

import re
import sys
from pathlib import Path


DECLARATION = re.compile(
    r'^\s*memref\.global\s+"private".*?@([A-Za-z0-9_.$-]+)\b.*\n?$',
    re.MULTILINE,
)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input.mlir> <output.mlir>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    source = input_path.read_text(encoding="utf-8")
    removed = []

    def remove_if_unreferenced(match: re.Match[str]) -> str:
        symbol = match.group(1)
        occurrences = len(re.findall(rf"@{re.escape(symbol)}\b", source))
        if occurrences == 1:
            removed.append(symbol)
            return ""
        return match.group(0)

    normalized = DECLARATION.sub(remove_if_unreferenced, source)
    output_path.write_text(normalized, encoding="utf-8")
    print(f"removed {len(removed)} unreferenced private memref.global declaration(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
