#!/usr/bin/env python3
"""Decode the authenticated Task 6 PCIe USER1 diagnostic payload."""

import argparse
import json

MAGIC = 0x54365049  # T6PI


def field(payload: int, offset: int, width: int) -> int:
    return (payload >> offset) & ((1 << width) - 1)


def decode(raw_hex: str, bit_count: int) -> dict:
    payload = int(raw_hex, 16)
    version = field(payload, 32, 8)
    decoded = {
        "raw_hex": raw_hex,
        "bit_count": bit_count,
        "magic": field(payload, 0, 32),
        "magic_ok": field(payload, 0, 32) == MAGIC,
        "version": version,
    }
    if version >= 2:
        first_tx = field(payload, 712, 64)
        decoded["tlp_debug"] = {
            "rx_beat_count": field(payload, 392, 32),
            "rx_packet_count": field(payload, 424, 32),
            "rx_eof_count": field(payload, 456, 32),
            "tx_beat_count": field(payload, 520, 32),
            "tx_packet_count": field(payload, 552, 32),
            "tx_eof_count": field(payload, 584, 32),
            "first_rx_qword_hex": f"0x{field(payload, 648, 64):016x}",
            "first_tx_qword_hex": f"0x{first_tx:016x}",
        }
    if version >= 3:
        total = field(payload, 360, 32)
        writes = field(payload, 328, 32)
        decoded["cfg_transactions"] = {
            "counter_semantics": "wrapping_32_bit",
            "total_count": total,
            "read_count": (total - writes) & 0xFFFFFFFF,
            "write_count": writes,
        }
    if version >= 4:
        sticky = field(payload, 616, 32)
        last = field(payload, 712, 64)
        decoded["bar_read_boundary"] = {
            "arvalid_cycles": field(payload, 520, 32),
            "ar_handshakes": field(payload, 552, 32),
            "rvalid_cycles": field(payload, 584, 32),
            "r_handshake_seen": bool(sticky & (1 << 3)),
            "last_araddr": last & 0xFFFFFFFF,
            "last_rdata": last >> 32,
        }
    return decoded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_hex")
    parser.add_argument("--bits", type=int, default=1024)
    args = parser.parse_args()
    print(json.dumps(decode(args.raw_hex, args.bits), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
