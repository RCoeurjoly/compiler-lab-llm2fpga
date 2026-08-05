#!/usr/bin/env python3
"""Generate a deterministic, oracle-backed RC exp table."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from table_format import TableSpec, encode_header, write_receipt


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_table(domain_receipt: Path, output: Path, address_bits: int, output_format: str) -> dict[str, object]:
    if output_format != "float32":
        raise ValueError("only float32 output is currently supported")
    source = json.loads(domain_receipt.read_text(encoding="utf-8"))
    sites = source.get("sites", {})
    if not sites:
        raise ValueError("domain receipt has no sites")
    lows = [float(site["derived_pre_exp_finite_min"]) for site in sites.values()]
    highs = [float(site["derived_pre_exp_finite_max"]) for site in sites.values()]
    scale = max(float(site["boundary"]["scale"]) for site in sites.values())
    lo = min(lows) - scale
    hi = max(highs)
    if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
        raise ValueError("invalid finite domain")
    entries = 1 << address_bits
    values = [math.exp(lo + (hi - lo) * i / (entries - 1)) for i in range(entries)]
    payload = b"".join(struct.pack("<f", value) for value in values)
    digest = hashlib.sha256(payload).hexdigest()
    spec = TableSpec(address_bits, 4, lo, hi, digest, entries)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encode_header(spec) + payload)
    receipt = output.with_suffix(".json")
    write_receipt(receipt, spec, {"domain_receipt": str(domain_receipt),
                                  "domain_receipt_sha256": _sha(domain_receipt),
                                  "oracle": "python-math.exp", "output_format": output_format})
    return {"table": spec.__dict__, "receipt": str(receipt)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--address-bits", type=int, default=8)
    parser.add_argument("--output-format", default="float32")
    args = parser.parse_args()
    if not 1 <= args.address_bits <= 16:
        raise ValueError("address-bits must be in [1, 16]")
    print(json.dumps(generate_table(args.domain_receipt, args.output, args.address_bits, args.output_format), indent=2))


if __name__ == "__main__":
    main()
