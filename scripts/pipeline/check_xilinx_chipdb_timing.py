#!/usr/bin/env python3
"""Reject nextpnr-xilinx v1 databases with no cell-timing tile types.

This checks coverage metadata, not correctness or completeness of timing arcs.
The schema uses signed 32-bit relative offsets in units of four bytes.
"""
import argparse
import json
import mmap
import struct


def inspect(data):
    def integer(offset):
        if offset < 0 or offset + 4 > len(data):
            raise ValueError("chipdb pointer outside file")
        return struct.unpack_from("<i", data, offset)[0]

    def pointer(offset):
        target = offset + 4 * integer(offset)
        integer(target)
        return target

    root = pointer(0)
    if integer(root + 8) != 1:
        raise ValueError("unsupported chipdb schema version")
    name = pointer(root)
    end = data.find(b"\0", name, min(name + 256, len(data)))
    if end < 0:
        raise ValueError("unterminated device name")
    timing = pointer(root + 52)
    count = integer(timing)
    if count < 0:
        raise ValueError("negative timing tile count")
    return {
        "schema": "xilinx-chipdb-timing-coverage-v1",
        "device": data[name:end].decode("ascii"),
        "speed_grades": integer(root + 48),
        "timed_tile_types": count,
        "wire_timing_classes": integer(timing + 4),
        "pip_timing_classes": integer(timing + 8),
        "status": "missing_cell_timing" if count == 0 else "cell_timing_present_not_qualified",
        "timing_closure_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chipdb")
    args = parser.parse_args()
    with open(args.chipdb, "rb") as file:
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
            report = inspect(data)
    print(json.dumps(report, indent=2))
    return 1 if report["timed_tile_types"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
