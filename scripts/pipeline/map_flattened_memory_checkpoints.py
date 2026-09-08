#!/usr/bin/env python3
"""Map a flattened generated top's memories in restartable checkpoints.

Yosys can map the complete flattened TinyStories top, but retaining all
intermediate memory structures in one process can exceed the host's memory.
This helper deliberately starts a fresh bounded process for each memory.  A
checkpoint is written only after that memory has been mapped, so an interrupted
run can resume without repeating completed work.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


LUTRAM_NAMES = {
    "attention_context_q16_16.mem",
    "attention_residual_q16_16.mem",
    "block_input_q16_16.mem",
    "block_output_q16_16.mem",
    "ln1_output_q16_16.mem",
    "ln2_output_q16_16.mem",
    "final_output_q16_16.mem",
}


def memory_names(il: Path) -> list[str]:
    names = re.findall(
        r"^\s*memory(?: width \d+)?(?: size \d+)? \\([^\s]+)$",
        il.read_text(),
        flags=re.MULTILINE,
    )
    if not names:
        raise ValueError(f"no RTLIL memories found in {il}")
    return names


def checkpoint_script(source: Path, destination: Path, name: str) -> str:
    library = (
        "/nix/store/cbqyfg8bas2yvlk2hf81g4p5sgqxb6r0-yosys-0.66/share/yosys/"
        "xilinx/lutrams_xc5v.txt"
        if name in LUTRAM_NAMES
        else "/tmp/yosys-data2/xilinx/brams_xc7.txt"
    )
    # The flattened module is main; the leading backslash is RTLIL's escaped
    # identifier syntax and is accepted by Yosys's selection grammar.
    selection = f"main/\\{name}"
    return (
        f"read_rtlil {source}\n"
        f"memory_libmap -lib {library} {selection}\n"
        f"write_rtlil {destination}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="flattened, memory_dff-normalized RTLIL")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0, help="map at most this many new memories")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    names = memory_names(args.input)
    previous = args.input
    completed = 0
    for index, name in enumerate(names, 1):
        destination = args.output_dir / f"map-{index}.il"
        if destination.exists():
            previous = destination
            completed += 1
            continue
        if args.limit and completed >= args.limit:
            break
        with tempfile.NamedTemporaryFile("w", suffix=".ys", delete=False) as script:
            script.write(checkpoint_script(previous, destination, name))
            script_path = Path(script.name)
        try:
            subprocess.run(
                [args.yosys, "-s", str(script_path)],
                check=True,
                timeout=args.timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        finally:
            script_path.unlink(missing_ok=True)
        previous = destination
        completed += 1

    receipt = {
        "schema": "llm2fpga-flattened-memory-checkpoints-v1",
        "input": str(args.input),
        "memory_count": len(names),
        "completed": completed,
        "last_checkpoint": str(previous),
        "status": "complete" if completed == len(names) else "partial",
    }
    (args.output_dir / "memory-checkpoints.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
