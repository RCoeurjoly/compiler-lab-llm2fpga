#!/usr/bin/env python3
"""Create or verify a self-hashed exact serial-GEMV Calyx shape-gate receipt."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

REQUIRED = ("model.calyx.mlir", "parsed.calyx.mlir", "model.futil", "model.sv", "ordered-address-data-trace.json", "provenance.json", "yosys-stat.txt")

def binding(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def canonical(payload: dict) -> str:
    copy = dict(payload); copy.pop("receipt_sha256", None)
    return hashlib.sha256(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--receipt", type=Path, required=True); p.add_argument("--gate", action="append", default=[]); p.add_argument("--write", action="store_true"); args = p.parse_args()
    gates = {}
    for item in args.gate:
        name, raw = item.split("=", 1); root = Path(raw)
        if not root.is_dir(): raise ValueError(f"missing gate output: {root}")
        files = {}
        for filename in REQUIRED:
            path = root / filename
            if not path.is_file() or not path.stat().st_size: raise ValueError(f"missing gate artifact: {path}")
            files[filename] = binding(path)
        provenance = json.loads((root / "provenance.json").read_text())
        trace = json.loads((root / "ordered-address-data-trace.json").read_text())
        if provenance["descriptor"] != trace.get("descriptor", provenance["descriptor"]):
            raise ValueError("trace descriptor disagrees with provenance")
        gates[name] = {"descriptor": provenance["descriptor"], "files": files}
    payload = {"schema": "llm2fpga-exact-serial-gemv-calyx-gate-v1", "gates": gates}
    payload["receipt_sha256"] = canonical(payload)
    if args.write: args.receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    actual = json.loads(args.receipt.read_text())
    if actual != payload or actual.get("receipt_sha256") != canonical(actual): raise ValueError("invalid exact serial-GEMV Calyx gate receipt")

if __name__ == "__main__": main()
