#!/usr/bin/env python3
"""Run the bounded coarse Xilinx synthesis path without FSM extraction.

The generated TinyStories control is already structurally scheduled.  Yosys's
generic ``fsm`` pass expands that schedule catastrophically, so this probe
keeps the ordinary process/memory/alumacc preparation while deliberately
omitting FSM extraction.  It is a diagnostic netlist stage, not a timing or
bitstream claim.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


COMMANDS = (
    "hierarchy -top {top} -check;",
    "proc; check; tribuf -logic; deminout; opt_expr; opt_clean;",
    "opt -nodffe -nosdff; opt; wreduce; peepopt; opt_clean; sort;",
    "memory_dff; opt_expr -fine; wreduce; alumacc; share; opt;",
    "memory -nomap; opt_clean; stat;",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sv", type=Path)
    parser.add_argument("--top", default="main")
    parser.add_argument("--rtlil", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not args.sv.is_file():
        parser.error(f"missing SystemVerilog input: {args.sv}")
    script = (
        f'read_slang --threads 1 --no-proc --max-parse-depth 20000 '
        f'--top {args.top} {args.sv}; '
        + " ".join(part.format(top=args.top) for part in COMMANDS)
    )
    if args.rtlil:
        script += f" write_rtlil {args.rtlil};"
    result = subprocess.run(
        ["yosys", "-m", "slang", "-p", script],
        text=True,
        capture_output=True,
        timeout=args.timeout,
        check=False,
    )
    output = result.stdout + result.stderr
    if args.log:
        args.log.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
