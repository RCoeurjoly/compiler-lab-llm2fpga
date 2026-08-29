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
import struct
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-exp-lowering-boundary-v1"
SOURCE = {
    "operation": "math.exp",
    "semantic_role": "attention softmax",
    "source_line": 830,
    "input_type": "f32",
    "output_type": "f32",
    "stabilization": "score - row_max",
}


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


def build_report() -> dict[str, Any]:
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
        "source": SOURCE,
        "boundary": {
            "first_unsupported_operation": "math.exp",
            "location": "pre-Calyx flat-SCF artifact line 830",
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
    args = parser.parse_args()
    report = build_report()
    report["sha256"] = canonical_sha256(report)
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
