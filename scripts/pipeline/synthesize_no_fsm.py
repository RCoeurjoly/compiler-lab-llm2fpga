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


def build_script(
    sv: Path | str,
    *,
    top: str = "main",
    preserve_multipliers: bool = False,
    rtlil: Path | None = None,
) -> str:
    """Prepare generated SV without FSM extraction.

    The pre-DSP boundary must retain $mul cells: running alumacc here turns
    them into $macc_v2 before synth_xilinx's map_dsp stage can see them.
    """
    commands = COMMANDS[:3] + (
        ("memory_dff; opt_expr -fine; wreduce; stat;",)
        if preserve_multipliers
        else COMMANDS[3:]
    )
    script = (
        f"read_slang --threads 1 --no-proc --max-parse-depth 20000 "
        f"--top {top} {sv}; "
        + " ".join(part.format(top=top) for part in commands)
    )
    if rtlil:
        script += f" write_rtlil {rtlil};"
    return script


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sv", type=Path)
    parser.add_argument("--top", default="main")
    parser.add_argument("--rtlil", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--preserve-multipliers",
        action="store_true",
        help="stop before alumacc so Xilinx map_dsp can infer signed DSPs",
    )
    args = parser.parse_args()
    if not args.sv.is_file():
        parser.error(f"missing SystemVerilog input: {args.sv}")
    script = build_script(
        args.sv,
        top=args.top,
        preserve_multipliers=args.preserve_multipliers,
        rtlil=args.rtlil,
    )
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
