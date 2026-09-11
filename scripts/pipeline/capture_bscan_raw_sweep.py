#!/usr/bin/env python3
"""Capture un-decoded BSCAN TDO vectors for physical/simulation comparison.

The output is deliberately a JSON list of individual bits in JTAG order.  It
must not be reduced to an integer before comparison: a one-clock capture or
shift offset is the signal this experiment is intended to measure.
"""

import argparse
import json
import sys
import time

sys.path.insert(0, "/home/roland/LLM2FPGA/scripts/task6")
from read_jtag_debug_ftdi_bitbang import FtdiMpsseJtag
from read_jtag_debug_xvc import clock_tms, reset_tap, shift_ir


def exchange(client, command, length):
    # Enter Shift-DR, clock exactly ``length`` bits, and leave through UPDATE.
    clock_tms(client, [1, 0, 0])
    tms = [0] * length
    tms[-1] = 1
    tdi = [(command >> i) & 1 for i in range(length)]
    tdo = client.shift(tms, tdi)
    clock_tms(client, [1, 0])
    return tdo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--serial", default="210299BF3824")
    ap.add_argument("--frequencies", default="100000,1000000,6000000,12000000")
    ap.add_argument("--lengths", default="64,65,66")
    ap.add_argument("--tdo-bits", default="7,0")
    ap.add_argument("--repetitions", type=int, default=3)
    args = ap.parse_args()

    frequencies = [int(x) for x in args.frequencies.split(",")]
    lengths = [int(x) for x in args.lengths.split(",")]
    tdo_bits = [int(x) for x in args.tdo_bits.split(",")]
    rows = []
    for freq in frequencies:
        for tdo_bit in tdo_bits:
            # The reader's TDO extraction bit is part of the experiment, so
            # create a fresh FTDI session for every setting.
            client = FtdiMpsseJtag(args.serial, 0x0403, 0x6014, freq, tdo_bit)
            try:
                reset_tap(client)
                shift_ir(client, 6, 6)
                for length in lengths:
                    for repetition in range(args.repetitions):
                        # 0x7 is the CSR-only loopback opcode.  The payload is
                        # a pattern chosen to expose every bit position.
                        pattern = 0x0123456789ABCDEF
                        command = (0x7 << 60) | (pattern & ((1 << 60) - 1))
                        started = time.time()
                        bits = exchange(client, command, length)
                        rows.append({
                            "frequency_hz": freq,
                            "tdo_bit": tdo_bit,
                            "capture_length": length,
                            "repetition": repetition,
                            "command": f"0x{command:016x}",
                            "tdo_bits_lsb_first": bits,
                            "elapsed_s": time.time() - started,
                        })
            finally:
                client.close()

    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump({"schema": 1, "rows": rows}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
