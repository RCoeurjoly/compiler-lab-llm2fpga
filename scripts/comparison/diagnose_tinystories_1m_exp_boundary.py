#!/usr/bin/env python3
"""Record the authenticated TinyStories-1M ``math.exp`` backend boundary.

This is a diagnostic, not a lowering pass.  The package-aware lowering reaches
``math.exp`` in the stabilized attention Softmax.  The repository contains
experimental RC LUT/polynomial implementations, but neither is an exact
implementation of the package's f32 operation and neither carries an
authenticated full-model error contract.  Silently selecting one would turn a
representation change into a false equivalence claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-exp-lowering-boundary-v1"
FRONTIER_REPORT = "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"
FRONTIER_REPORT_SHA256 = "81a8ea6b29ceb5a362c70dc7f5adf6b469e41a6f79d6067fc378280abe8b447e"
FRONTIER_FILE_SHA256 = "ee9162f7ed6990c351ff35f15738e32844342527570a1b8b12671eca6542d95a"
PRE_CALYX_PATH = "authenticated-stage:pre_calyx"
PRE_CALYX_SHA256 = "e33e8015440dc89e2c3812daa07e5ac85991752729656d1950f6ddef4875e090"
PRE_CALYX_BYTES = 29336775


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', f32(value)))[0]:08x}"


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def exact_f32_exp(value: float) -> float:
    # The source op is f32.  Round both operand and result at this boundary;
    # Python's double precision result must not be mistaken for the contract.
    return f32(math.exp(f32(value)))


def discover_softmax_exp_context(text: str) -> dict[str, Any]:
    """Derive the first exp context from flat-SCF text, rejecting loose exp calls."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.search(r"(\S+)\s*=\s*math\.exp\s+(\S+)\s*:\s*f32", line)
        if not match:
            continue
        result, operand = match.groups()
        subtract = None
        for prior in range(max(0, index - 12), index):
            if re.search(rf"{re.escape(operand)}\s*=\s*arith\.subf\b", lines[prior]):
                subtract = lines[prior].strip()
        if subtract is None:
            raise ValueError(f"math.exp at line {index + 1} lacks max-subtract predecessor")
        reduction = None
        for following in lines[index + 1:index + 80]:
            if (re.search(r"arith\.addf|\b(sum|reduce|reduction)\b", following, re.IGNORECASE)
                    and (result in following or "reduction" in following.lower()
                         or "sum" in following.lower())):
                reduction = following.strip()
                break
        if reduction is None:
            raise ValueError(f"math.exp at line {index + 1} lacks downstream reduction")
        return {
            "operation": "math.exp",
            "semantic_role": "attention softmax",
            "source_line": index + 1,
            "input_type": "f32",
            "output_type": "f32",
            "stabilization": "score - row_max",
            "exp_result": result,
            "exp_operand": operand,
            "max_subtract": subtract,
            "reduction": reduction,
        }
    raise ValueError("no f32 math.exp operation found")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frontier(root: Path) -> dict[str, Any]:
    path = root / FRONTIER_REPORT
    if _sha256_file(path) != FRONTIER_FILE_SHA256:
        raise ValueError("canonical Task3x frontier report file hash mismatch")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("sha256") != FRONTIER_REPORT_SHA256:
        raise ValueError("canonical Task3x frontier report receipt hash mismatch")
    if report.get("sha256") != canonical_sha256({k: v for k, v in report.items() if k != "sha256"}):
        raise ValueError("canonical Task3x frontier report self-hash mismatch")
    frontier = report.get("frontier", {}).get("next_circt", {})
    if frontier.get("operation") != "math.exp" or frontier.get("semantic_role") != "attention softmax":
        raise ValueError("canonical Task3x frontier does not identify attention math.exp")
    stage = report.get("stages", {}).get("pre_calyx", {})
    if stage.get("sha256") != PRE_CALYX_SHA256 or stage.get("bytes") != PRE_CALYX_BYTES:
        raise ValueError("canonical pre-Calyx stage identity mismatch")
    return report


def build_report(root: Path | None = None, pre_calyx: Path | None = None) -> dict[str, Any]:
    root = root or Path(__file__).resolve().parents[2]
    frontier = load_frontier(root)
    if pre_calyx is not None:
        if _sha256_file(pre_calyx) != PRE_CALYX_SHA256 or pre_calyx.stat().st_size != PRE_CALYX_BYTES:
            raise ValueError("pre-Calyx artifact substitution or stale artifact")
        source = discover_softmax_exp_context(pre_calyx.read_text(encoding="utf-8"))
        context_status = "parsed"
    else:
        source = {
            "operation": "math.exp",
            "semantic_role": "attention softmax",
            "source_line": frontier["frontier"]["next_circt"]["source_line"],
            "input_type": "f32",
            "output_type": "f32",
            "stabilization": "score - row_max",
        }
        context_status = "not_materialized"
    values = [0.0, -0.0, -0.5, -1.0, -8.0]
    vectors = [
        {
            "input": f32(value),
            "input_bits": bits(value),
            "reference_output": exact_f32_exp(value),
            "reference_output_bits": bits(exact_f32_exp(value)),
        }
        for value in values
    ]
    # These are deliberately inventory entries, not accepted lowering routes.
    candidates = [
        {
            "name": "rc_exp_table_lookup",
            "implementation": "rtl/rc-working/rc_exp_table_lookup.sv",
            "status": "rejected",
            "reason_code": "scope_and_contract_missing",
            "notes": "RC-specific table; no authenticated TinyStories-1M f32 error/special-value contract",
        },
        {
            "name": "polynomial_exp_order_5",
            "implementation": "scripts/pipeline/evaluate_softmax_candidates.py",
            "status": "rejected",
            "reason_code": "approximation_not_exact",
            "notes": "numerical candidate harness only; not a standard math.exp lowering",
        },
        {
            "name": "upstream_circt_math_exp",
            "implementation": "circt-opt --lower-scf-to-calyx",
            "status": "unsupported",
            "reason_code": "calyx_backend_unhandled_operation",
            "notes": "BuildOpGroups reports unhandled math.exp",
        },
    ]
    return {
        "schema": SCHEMA,
        "status": "unsupported",
        "model": "TinyStories-1M",
        "source": source,
        "source_evidence": {
            "frontier_report": FRONTIER_REPORT,
            "frontier_report_sha256": FRONTIER_REPORT_SHA256,
            "frontier_report_file_sha256": FRONTIER_FILE_SHA256,
            "pre_calyx_artifact": PRE_CALYX_PATH,
            "pre_calyx_sha256": PRE_CALYX_SHA256,
            "pre_calyx_bytes": PRE_CALYX_BYTES,
            "context_validation": context_status,
        },
        "boundary": {
            "first_unsupported_operation": "math.exp",
            "location": f"pre-Calyx flat-SCF artifact line {source['source_line']}",
            "numeric_domain": "stabilized attention scores; full-model domain receipt unavailable",
            "required_contract": {
                "input_encoding": None,
                "output_encoding": None,
                "finite_input_domain": None,
                "underflow_and_overflow": None,
                "rounding_mode": None,
                "special_value_behavior": None,
                "maximum_absolute_error": None,
                "softmax_output_tolerance": None,
                "proof_or_exhaustive_corpus": None,
            },
        },
        "reference_vectors": {
            "description": "f32 boundary probes; diagnostic vectors, not full-model coverage",
            "vectors": vectors,
        },
        "candidate_inventory": candidates,
        "decision": {
            "lowering_applied": False,
            "equivalence_claim": False,
            "reason_code": "math_exp_semantics_contract_unavailable",
            "message": "Do not replace canonical f32 math.exp with an approximation until an explicit contract is authenticated and passes the TinyStories-1M oracle.",
        },
        "claims": {
            "systemverilog": False,
            "rtlil": False,
            "functional_equivalence": False,
            "timing_closure": False,
            "hardware_inference": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--pre-calyx", type=Path)
    args = parser.parse_args()
    report = build_report(args.root, args.pre_calyx)
    report["sha256"] = canonical_sha256(report)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
