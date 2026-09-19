"""Reject undriven compiler-mode PCIe status/write-data nets in a Yosys check log."""

import argparse
from pathlib import Path
import re

WATCHED = (
    "rowstream_compiler_wb_data",
    "rowstream_tinystories_bridge_error",
    "rowstream_tinystories_cache_hits",
    "rowstream_tinystories_cache_misses",
    "rowstream_tinystories_debug",
    "rowstream_tinystories_stall_cycles",
    "replay_cyc", "replay_stb", "replay_we", "replay_addr", "replay_sel",
    "replay_accept", "replay_ack", "replay_err", "replay_rdata",
    "req_toggle", "response_toggle", "replay_active", "pending",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--top", default="task6_ypcb_pcie_uberddr3_rowstream_loader_top",
                        choices=["task6_ypcb_pcie_uberddr3_rowstream_loader_top",
                                 "compiler_ddr3_trace_replay_top"])
    args = parser.parse_args()
    log = args.log.read_text()
    if not re.search(r"Found and reported \d+ problems\.", log) or "End of script." not in log:
        parser.error("a completed Yosys check is required")
    if f"Checking module {args.top}" not in log:
        parser.error("the board top was not checked")
    failures = sorted({name for line in log.splitlines()
                       if "Warning:" in line and "has no driver" in line
                       for name in WATCHED if re.search(rf"\b{re.escape(name)}\b", line)})
    if failures:
        print("FAIL: undriven compiler-shell nets: " + ", ".join(failures))
        return 1
    print("PASS: watched compiler-shell nets have no undriven warnings (not a full-design check)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
