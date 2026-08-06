#!/usr/bin/env python3
"""Repair stale-result capture around CIRCT-exported Calyx FP-to-int groups."""

import re
import sys
from pathlib import Path


GROUP = re.compile(r"(?ms)^(\s*group\s+\w+\s*\{\n)(.*?^\s*\})")
INPUT = re.compile(
    r"(?m)^\s*(fptosi_\d+_reg)\.in\s*=\s*(std_fpToIntFN_\d+)\.out;\s*$"
)


def fix_group(match: re.Match[str]) -> str:
    body = match.group(2)
    binding = INPUT.search(body)
    if binding is None:
        return match.group(0)

    result_reg, converter = binding.groups()
    write_enable = re.compile(
        rf"(?m)^(\s*{re.escape(result_reg)}\.write_en\s*=\s*)1'b1(\s*;)\s*$"
    )
    fixed, count = write_enable.subn(rf"\g<1>{converter}.done\g<2>", body)
    already_fixed = re.search(
        rf"(?m)^\s*{re.escape(result_reg)}\.write_en\s*=\s*"
        rf"{re.escape(converter)}\.done\s*;\s*$",
        body,
    )
    if count == 0 and already_fixed:
        return match.group(0)
    if count != 1:
        raise ValueError(
            f"expected one unconditional or already-gated write enable for "
            f"{result_reg}, found {count}"
        )
    return match.group(1) + fixed


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <input.futil> <output.futil>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    fixed, group_count = GROUP.subn(fix_group, source)
    gated_count = sum(
        1
        for line in fixed.splitlines()
        if re.search(r"fptosi_\d+_reg\.write_en = std_fpToIntFN_\d+\.done;", line)
    )
    Path(sys.argv[2]).write_text(fixed, encoding="utf-8")
    print(
        f"checked {group_count} Calyx group(s); verified {gated_count} gated FP-to-int handshake(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
