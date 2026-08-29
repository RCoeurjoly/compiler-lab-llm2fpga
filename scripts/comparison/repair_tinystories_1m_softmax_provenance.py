#!/usr/bin/env python3
"""Repair current-graph constants and layer/head metadata in softmax provenance."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def repair(source: dict[str, Any]) -> dict[str, Any]:
    result = dict(source)
    result["layer_count"] = 8
    result["heads_per_layer"] = 16
    result["constants"] = {"zero_f32": {
        "value": "0.0", "type": "f32", "pre_lowering_identity": "%zero",
        "lowered_identities": {"torch_mlir": "%zero", "linalg": "%zero", "scf": "%zero", "flat_scf": "%cst_6"}
    }}
    result.pop("sha256", None)
    result["sha256"] = canonical(result)
    return result

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--input", type=Path, required=True); ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(); source = json.loads(args.input.read_text(encoding="utf-8")); result = repair(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
