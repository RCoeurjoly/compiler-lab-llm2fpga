#!/usr/bin/env python3
"""Create or verify a self-hashed exact serial-GEMV Calyx shape-gate receipt."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

REQUIRED = ("model.calyx.mlir", "parsed.calyx.mlir", "model.futil", "model.sv", "ordered-address-data-trace.json", "provenance.json", "yosys-stat.txt")

def binding(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def canonical(payload: dict) -> str:
    copy = dict(payload); copy.pop("receipt_sha256", None)
    return hashlib.sha256(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def emitted_trace_summary(model: Path) -> dict:
    text = model.read_text()
    match = re.search(r"runtime rows=(\d+) outputs=(\d+) inputs=(\d+) mac_order=ascending_i64_wrap", text)
    if match is None: raise ValueError("model lacks exact runtime descriptor")
    rows, outputs, inputs = map(int, match.groups())
    required = ("calyx.group @read_operands", "calyx.group @launch_multiply", "calyx.group_done %mac_mul.done", "calyx.group @write_result", "calyx.assign %results.write_en = %true : i1", "calyx.while %row_less.out with @row_not_done")
    if any(item not in text for item in required): raise ValueError("model lacks bound runtime control/data path")
    control = "\n".join(line.strip() for line in text.splitlines() if "calyx." in line)
    return {"descriptor": {"rows": rows, "outputs": outputs, "inputs": inputs, "mac_order": "ascending_i64_wrap"}, "entry_count": rows * outputs * inputs, "first": {"row": 0, "output": 0, "input": 0, "activation_address": 0, "weight_address": 0, "result_address": 0}, "last": {"row": rows-1, "output": outputs-1, "input": inputs-1, "activation_address": rows*inputs-1, "weight_address": outputs*inputs-1, "result_address": rows*outputs-1}, "emitted_control_sha256": hashlib.sha256(control.encode()).hexdigest()}

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
        expected_trace = emitted_trace_summary(root / "model.calyx.mlir")
        for key, value in expected_trace.items():
            if trace.get(key) != value: raise ValueError(f"trace {key} disagrees with emitted Calyx control")
        if provenance["descriptor"] != trace["descriptor"]:
            raise ValueError("trace descriptor disagrees with provenance")
        gates[name] = {"descriptor": provenance["descriptor"], "files": files}
    payload = {"schema": "llm2fpga-exact-serial-gemv-calyx-gate-v1", "gates": gates}
    payload["receipt_sha256"] = canonical(payload)
    if args.write: args.receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    actual = json.loads(args.receipt.read_text())
    if actual != payload or actual.get("receipt_sha256") != canonical(actual): raise ValueError("invalid exact serial-GEMV Calyx gate receipt")

if __name__ == "__main__": main()
