#!/usr/bin/env python3
"""Repair the exceptional signed-add case in Calyx's shared integer adder.

The RC Q4.12 roundeven expansion can feed ``INT32_MIN`` and ``-1`` to the
shared ``std_add`` primitive after ``fptosi(-inf)``.  Two's-complement wrap
then changes the later int8 conversion from 0x80 to 0x7f.  The source-level
MLIR guard is preferable when the graph can afford it; this deterministic RTL
repair is the RC backend fallback that keeps the guard out of every lane's
control graph.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


MODULE = re.compile(r"(?ms)(^module std_add\s*#\(.*?^endmodule\s*)")
OLD = "assign out = left + right;"
NEW = """assign out = (WIDTH == 32 && left == 32'h80000000 && right == 32'hffffffff)
           ? 32'h80000000
           : ((WIDTH == 32 && right == 32'h80000000 && left == 32'hffffffff)
              ? 32'h80000000
              : left + right);"""


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def rewrite(text: str) -> tuple[str, int]:
    matches = list(MODULE.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one std_add module, found {len(matches)}")
    module = matches[0].group(1)
    count = module.count(OLD)
    if count != 1:
        raise ValueError(f"expected exactly one std_add assignment, found {count}")
    updated_module = module.replace(OLD, NEW)
    return text[: matches[0].start(1)] + updated_module + text[matches[0].end(1) :], count


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        raise SystemExit(
            "usage: fix_sv_roundeven_overflow.py INPUT.sv OUTPUT.sv [RECEIPT.json]"
        )
    source = Path(argv[1])
    destination = Path(argv[2])
    original = source.read_text(encoding="utf-8")
    updated, count = rewrite(original)
    destination.write_text(updated, encoding="utf-8")
    if len(argv) == 4:
        Path(argv[3]).write_text(
            json.dumps(
                {
                    "schema": "rc-roundeven-overflow-fix-v1",
                    "repair_count": count,
                    "input_sha256": sha256(original),
                    "output_sha256": sha256(updated),
                    "exception": "WIDTH32 INT32_MIN plus -1 (and commuted form)",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
