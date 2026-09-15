"""Compiler-owned placement records shared by BRAM and DDR3 backends."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from scripts.analysis.memory_placement_equivalence import ProjectionTable


def placement_record(table: ProjectionTable, mode: str) -> dict:
    if mode not in {"bram", "ddr3"}:
        raise ValueError("memory placement must be bram or ddr3")
    record = {
        "logical_name": table.logical_name,
        "space": mode,
        "width_bits": table.width_bits,
        "depth_words": table.depth_words,
        "read_only": True,
        "read_latency": 1 if mode == "bram" else "variable_bounded",
        "burst_words": 1 if mode == "bram" else 16,
        "alignment_bytes": 1 if mode == "bram" else 16,
        "address_map": {
            "logical_unit": "byte",
            "external_unit": "wishbone_128_bit_word" if mode == "ddr3" else "bram_byte",
            "endianness": "little",
            "lane_zero_is_lowest_address": True,
        },
        "source_path": table.source_path,
        "source_sha256": table.source_sha256,
        "image_sha256": hashlib.sha256(table.data).hexdigest(),
        "quantization": "W8A8_INT8_projection_weights",
    }
    return record


def placement_manifest_hash(records: Iterable[dict]) -> str:
    canonical = json.dumps(list(records), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()
