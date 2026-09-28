#!/usr/bin/env python3
"""Compare placement and exact routed resources, ignoring JSON enumeration order."""

import argparse
import hashlib
import json
from pathlib import Path


def route_digest(route):
    fields = route.split(";") if route else []
    if len(fields) % 3:
        raise ValueError("ROUTING must contain wire/PIP/strength triples")
    triples = sorted(tuple(fields[i:i + 3]) for i in range(0, len(fields), 3))
    encoded = json.dumps(triples, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def identity(path):
    # Load one checkpoint at a time; retain only small comparison records.
    design = json.loads(Path(path).read_text())
    modules = design["modules"]
    if len(modules) != 1:
        raise ValueError("Expected a single flattened module")
    module = next(iter(modules.values()))
    cells = {
        name: (cell["type"], cell.get("attributes", {}).get("NEXTPNR_BEL"),
               cell.get("parameters", {}))
        for name, cell in module.get("cells", {}).items()
    }
    routes = {
        name: route_digest(net.get("attributes", {}).get("ROUTING", ""))
        for name, net in module.get("netnames", {}).items()
    }
    return cells, routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("reloaded", type=Path)
    args = parser.parse_args()
    original = identity(args.original)
    reloaded = identity(args.reloaded)
    for label, before, after in zip(("cells/BELs/parameters", "net routes"), original, reloaded):
        if before != after:
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            raise SystemExit(f"FAIL {label}: {len(changed)} differences; first: {changed[:5]}")
    print(f"PASS: {len(original[0])} cells/BELs/parameters and {len(original[1])} exact net routes unchanged")


if __name__ == "__main__":
    main()
