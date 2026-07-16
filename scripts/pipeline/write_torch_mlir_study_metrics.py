#!/usr/bin/env python3
"""Record reproducible size and elapsed-time metadata for a Torch-MLIR stage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write measured Torch-MLIR stage metadata."
    )
    parser.add_argument("--mlir", required=True, type=Path)
    parser.add_argument("--elapsed-ns", required=True, type=int)
    parser.add_argument("--phase-timing", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.elapsed_ns <= 0:
        raise SystemExit("--elapsed-ns must be positive")

    contents = args.mlir.read_bytes()
    payload: dict[str, object] = {
        "schema_version": 1,
        "scope": "one in-derivation Torch-MLIR import; not FPGA utilization",
        "lowering_elapsed_ns": args.elapsed_ns,
        "mlir_bytes": len(contents),
        "mlir_sha256": hashlib.sha256(contents).hexdigest(),
    }
    if args.phase_timing is not None:
        phase_timing = json.loads(args.phase_timing.read_text(encoding="utf-8"))
        if not isinstance(phase_timing, dict) or phase_timing.get("schema_version") != 1:
            raise SystemExit("--phase-timing must contain schema version 1")
        for field in (
            "torch_export_load_elapsed_ns",
            "torch_mlir_import_elapsed_ns",
            "mlir_text_render_elapsed_ns",
        ):
            value = phase_timing.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise SystemExit(f"--phase-timing field {field} must be a positive integer")
            payload[field] = value
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
