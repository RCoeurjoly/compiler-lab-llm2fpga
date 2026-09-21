"""Qualify only legal, fixed-clock routed fabric evidence, never PHY signoff."""
import argparse
import json
import re
from pathlib import Path


def qualify(log):
    markers = ["overused=0 overuse=0 archfail=0",
               "Running router1 to check that route is legal...",
               "Routing 0 arcs.", "Routing complete."]
    cursor = 0
    for marker in markers:
        position = log.find(marker, cursor)
        if position < 0:
            raise ValueError("missing legal route evidence: " + marker)
        cursor = position + len(marker)
    final = log[cursor:]
    if "Running post-routing legalisation..." not in final or not re.search(
            r"\b\d+ warnings, 0 errors\b", final):
        raise ValueError("missing successful post-route completion")
    clocks = {}
    for name, required, printed in [("rowstream_clk", 83.333333, 83.33),
                                     ("pcie_user_clk", 62.5, 62.50)]:
        rows = re.findall(r"Max frequency for clock\s+'" + name +
                          r"': ([\d.]+) MHz \((PASS|FAIL) at ([\d.]+) MHz\)", final)
        if len(rows) != 1:
            raise ValueError("missing or duplicate routed clock: " + name)
        fmax, state, target = rows[0]
        if state != "PASS" or float(fmax) < required or float(target) != printed:
            raise ValueError("failed or weakened clock: " + name)
        clocks[name] = {"fmax_mhz": float(fmax), "required_mhz": required}
    return {"legal_route": True, "clocks": clocks,
            "scope": "pinned fabric timing model only; not DDR/PHY/CDC/electrical signoff"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(qualify(args.log.read_text()), indent=2) + "\n")
