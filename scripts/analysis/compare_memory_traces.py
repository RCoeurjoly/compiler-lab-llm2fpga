#!/usr/bin/env python3
"""Compare completed single-outstanding memory traces using bounded memory.

A match establishes trace equality only, not successful inference. Verify the
simulators' terminal exit status, load/readback and token checks separately.
"""
import argparse
from itertools import zip_longest
import json
from pathlib import Path
import re

REQUEST = re.compile(r"Q ([0-9]+) ([0-9a-f]{8})\n")
RESPONSE = re.compile(r"R ([0-9]+) ([0-9a-f]{8}) ([0-9a-f]{32})\n")


def records(path):
    sequence, pending = 0, None
    with path.open(encoding="ascii") as stream:
        for line_number, line in enumerate(stream, 1):
            pattern = REQUEST if pending is None else RESPONSE
            match = pattern.fullmatch(line)
            if match is None or int(match[1]) != sequence:
                raise ValueError(f"{path}:{line_number}: malformed or out-of-order record")
            if pending is None:
                pending = match[2]
            else:
                if match[2] != pending:
                    raise ValueError(f"{path}:{line_number}: response address differs from request")
                pending = None
                sequence += 1
            yield line.rstrip("\n")
    if pending is not None:
        raise ValueError(f"{path}: missing final response")
    if sequence == 0:
        raise ValueError(f"{path}: empty trace")


def compare(reference, candidate):
    lines = 0
    for lines, (expected, observed) in enumerate(
            zip_longest(records(reference), records(candidate)), 1):
        if expected != observed:
            record = expected if expected is not None else observed
            return 1, {"status": "mismatch", "line": lines,
                       "boundary": "request" if record.startswith("Q ") else "response",
                       "reference": expected, "candidate": observed}
    return 0, {"status": "match", "transactions": lines // 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        code, report = compare(args.reference, args.candidate)
    except (ValueError, OSError) as error:
        code, report = 2, {"status": "invalid", "error": str(error)}
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
