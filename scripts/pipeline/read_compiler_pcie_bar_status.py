#!/usr/bin/env python3
"""Read and decode the compiler integration's persistent USER4 BAR boundary."""
import argparse
import json
import subprocess
import sys

MAGIC = 0x43504253  # CPBS


def field(payload: int, offset: int, width: int = 32) -> int:
    return (payload >> offset) & ((1 << width) - 1)


def decode(raw_hex: str, bit_count: int = 320) -> dict:
    payload = int(raw_hex, 16)
    flags = field(payload, 40)
    names = ("rst_n", "arvalid", "arready", "rvalid", "rready", "awvalid",
             "awready", "wvalid", "wready", "bvalid", "bready")
    result = {
        "raw_hex": raw_hex, "bit_count": bit_count,
        "magic": field(payload, 0), "magic_ok": field(payload, 0) == MAGIC,
        "version": field(payload, 32, 8),
        "flags": {name: bool(flags & (1 << index)) for index, name in enumerate(names)},
        "clk_count": field(payload, 56, 24),
    }
    offsets = {
        "arvalid_cycles": 80, "ar_handshakes": 112,
        "rvalid_cycles": 144, "r_handshakes": 176,
        "last_araddr": 208, "last_rdata": 240,
    }
    result.update({name: field(payload, offset) for name, offset in offsets.items()})
    result["sticky_word"] = field(payload, 272, 16)
    result["reset_seen_cycles"] = field(payload, 288, 16)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader", required=True)
    parser.add_argument("--serial", default="210299BF3824")
    parser.add_argument("--freq-hz", type=int, default=1_000_000)
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()
    command = [sys.executable, args.reader, "--serial", args.serial, "--tdo-bit", "7",
               "--bits", "320", "--user-ir", "0x05", "--freq-hz", str(args.freq_hz),
               "--json-only"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result = {"command": command, "returncode": completed.returncode,
              "reader_output": completed.stdout}
    if completed.returncode == 0:
        raw = json.loads(completed.stdout)
        result["reader"] = raw
        if raw.get("raw_hex"):
            result["bar"] = decode(raw["raw_hex"])
    if not args.json_only:
        print(json.dumps(result.get("bar", {}), indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
