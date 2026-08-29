#!/usr/bin/env python3
"""Bounded lowered-softmax trace probe; never invents unresolved tensor data."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat-scf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--binding", type=Path)
    ap.add_argument("--oracle", type=Path)
    a = ap.parse_args()
    lines = a.flat_scf.read_text().splitlines()
    exp = [i for i, x in enumerate(lines) if re.search(r"=\s*math\.exp\s+", x)]
    report = {
        "schema": "tinystories-1m-lowered-softmax-trace-v1",
        "status": "fail_closed",
        "flat_scf": {"path": str(a.flat_scf), "exp_sites": len(exp)},
        "trace": [],
        "first_unsupported": None,
    }
    if a.binding is not None:
        binding = json.loads(a.binding.read_text())
        if a.oracle is None or binding.get("source_oracle_sha256") != json.loads(a.oracle.read_text()).get("sha256"):
            report["first_unsupported"] = {"reason": "score_binding_oracle_identity_mismatch"}
        elif binding.get("tensor", {}).get("shape") != [16, 4, 4] or binding.get("tensor", {}).get("layout") != "head,query,key":
            report["first_unsupported"] = {"reason": "score_binding_shape_or_layout_mismatch"}
    if len(exp) != 8:
        report["first_unsupported"] = {"reason": "expected_eight_exp_sites", "observed": len(exp)}
    else:
        # A numerical interpreter needs runtime tensor contents for the first
        # score load.  Constants and index expressions alone are insufficient;
        # stop at that exact boundary rather than substituting zeros.
        for i in range(exp[0] - 1, -1, -1):
            m = re.match(r"\s*%([^ ]+)\s*=\s*memref\.load\s+(%[^\[]+)\[([^\]]+)\]", lines[i])
            if m and m.group(2).strip() not in {"%102"}:
                report["first_unsupported"] = {
                    "reason": "runtime_memref_value_unbound",
                    "line": i + 1,
                    "value": m.group(1),
                    "memref": m.group(2).strip(),
                    "index": m.group(3).strip(),
                    "required": "authenticated score tensor contents or executable lowered runtime",
                }
                break
    if report["first_unsupported"] is None:
        report["first_unsupported"] = {"reason": "no_trace_interpreter_checkpoint"}
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
