#!/usr/bin/env python3
"""Check the compiler top's 64-bit USER1 CSR without starting inference."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

STATUS = 0x3000000000000000
RESET = 0x5000000000000000
IDLE_INITIALIZED = 0x2800000000000000
# Index bits overlap the value in the frozen CSR ABI. These exercise all four
# addresses without pretending the interface accepts arbitrary prompt values.
PROMPT_WORDS = (0x0001, 0x0012, 0x0023, 0x0034)


def check(client, *, clock_tms, reset_tap, shift_ir, runs=3, delay=time.sleep):
    if runs < 1:
        raise ValueError("runs must be positive")
    records = []

    def exchange(command):
        if command >> 60 not in (1, 3, 5):
            raise ValueError("only prompt/status/reset commands are permitted")
        clock_tms(client, [1, 0, 0])  # Idle -> Capture-DR -> Shift-DR
        bits = client.shift([0] * 63 + [1], [(command >> i) & 1 for i in range(64)])
        clock_tms(client, [1, 0])  # Exit1-DR -> Update-DR -> Idle
        if len(bits) != 64:
            raise RuntimeError(f"short JTAG response: {len(bits)} bits")
        response = sum((bit & 1) << i for i, bit in enumerate(bits))
        delay(0.01)
        records.append({"command": f"{command:016x}", "captured": f"{response:016x}"})
        return response

    def expect(command, expected):
        exchange(command)
        # Capture the executed command's result without resetting the TAP.
        actual = exchange(STATUS)
        if actual != expected:
            raise RuntimeError(
                f"command {command:016x}: expected {expected:016x}, got {actual:016x}"
            )

    for _ in range(runs):
        reset_tap(client)
        shift_ir(client, 0x02, 6)  # USER1
        delay(0.01)
        expect(STATUS, IDLE_INITIALIZED)
        expect(RESET, 0)
        for word in PROMPT_WORDS:
            expect(0x1000000000000000 | word, word)
        expect(STATUS, IDLE_INITIALIZED | PROMPT_WORDS[0])
        expect(RESET, 0)
        expect(STATUS, IDLE_INITIALIZED)
    return {
        "schema": "tinystories-user1-csr-check-v1", "status": "passed",
        "runs": runs, "transactions": records, "inference_started": False,
        "scope": "status, prompt echoes and prompt-0 status, reset; no inference",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport-dir", type=Path, required=True)
    parser.add_argument("--serial", default="210299BF3824")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    transport_dir = args.transport_dir.resolve()
    sys.path.insert(0, str(transport_dir))
    ftdi = importlib.import_module("read_jtag_debug_ftdi_bitbang")
    jtag = importlib.import_module("read_jtag_debug_xvc")
    client = None
    result = {"schema": "tinystories-user1-csr-check-v1", "status": "failed"}
    try:
        client = ftdi.FtdiMpsseJtag(
            serial=args.serial, vid=0x0403, pid=0x6014, freq_hz=1_000_000, tdo_bit=7,
        )
        result = check(client, clock_tms=jtag.clock_tms, reset_tap=jtag.reset_tap,
                       shift_ir=jtag.shift_ir, runs=args.runs)
    except Exception as error:
        result["error"] = str(error)
    finally:
        if client is not None:
            client.close()
    result["transport_serial"] = args.serial
    result["transport_sha256"] = {
        Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (ftdi, jtag)
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
