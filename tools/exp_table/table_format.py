"""Stable binary format for oracle-backed exponential lookup tables."""
from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"RCEXPTBL"
VERSION = 1
HEADER = struct.Struct("<8sIIIIff32s")


@dataclass(frozen=True)
class TableSpec:
    address_bits: int
    output_bytes: int
    input_min: float
    input_max: float
    payload_sha256: str
    entry_count: int
    rounding: str = "float32-round-to-nearest-even"

    @property
    def payload_bytes(self) -> int:
        return self.entry_count * self.output_bytes


def encode_header(spec: TableSpec) -> bytes:
    digest = bytes.fromhex(spec.payload_sha256)
    if len(digest) != 32 or spec.output_bytes != 4:
        raise ValueError("only 32-bit output tables are supported")
    return HEADER.pack(MAGIC, VERSION, spec.address_bits, spec.output_bytes,
                       spec.entry_count, spec.input_min, spec.input_max, digest)


def decode_table(path: Path) -> TableSpec:
    raw = path.read_bytes()
    if len(raw) < HEADER.size:
        raise ValueError("table is shorter than its header")
    magic, version, address_bits, output_bytes, entries, lo, hi, digest = HEADER.unpack(raw[:HEADER.size])
    if magic != MAGIC or version != VERSION:
        raise ValueError("unsupported RC exp table")
    payload = raw[HEADER.size:]
    if len(payload) != entries * output_bytes:
        raise ValueError("table payload length does not match header")
    actual = hashlib.sha256(payload).digest()
    if actual != digest:
        raise ValueError("table payload hash mismatch")
    return TableSpec(address_bits, output_bytes, lo, hi, digest.hex(), entries)


def write_receipt(path: Path, spec: TableSpec, source: dict[str, object]) -> None:
    path.write_text(json.dumps({"schema_version": 1, "kind": "rc-exp-table",
                                "source": source, "table": spec.__dict__},
                               indent=2, sort_keys=True) + "\n", encoding="utf-8")
