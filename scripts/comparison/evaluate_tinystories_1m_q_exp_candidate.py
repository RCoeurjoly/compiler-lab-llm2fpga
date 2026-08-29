#!/usr/bin/env python3
"""Evaluate the existing fixed-point ``q_exp_approx`` Softmax candidate.

This is an evidence probe, not a lowering or hardware-equivalence gate.  It
reimplements the arithmetic in ``task3-main/rtl/fp/circt_fp_primitives.sv``
and binds the probe to the authenticated TinyStories-1M package and Q/DQ
receipt.  The frozen checkpoint contains only the final-token Q/K vectors;
therefore it cannot provide complete causal attention rows.  The report must
remain ``unsupported`` until a full score-row/checkpoint trace is available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / "task3-main/rtl/fp/circt_fp_primitives.sv"
PACKAGE_DEFAULT = Path("/tmp/kev-gpt-startinit/model_packages/tinystories-1m")
QDQ = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"

Q = 1 << 16
I32_MIN, I32_MAX = -(1 << 31), (1 << 31) - 1


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    # Match the authenticated Q/DQ receipt's canonical JSON (no trailing LF).
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', f32(value)))[0]:08x}"


def q16_16_to_f32_bits(q: int) -> int:
    """Match the RTL's normalized, truncating ``q16_16_to_f32`` function."""
    q = int(q)
    if q == 0:
        return 0
    sign = 1 if q < 0 else 0
    magnitude = abs(q)
    msb = magnitude.bit_length() - 1
    exponent = msb - 16
    if exponent > 127:
        return (sign << 31) | (0xFE << 23) | 0x7FFFFF
    if exponent < -126:
        return sign << 31
    # RTL shifts right when the significand has more than 24 bits, dropping
    # (not rounding) the low bits, then takes norm[22:0] as the fraction.
    norm = magnitude >> (msb - 23) if msb >= 23 else magnitude << (23 - msb)
    return (sign << 31) | ((exponent + 127) << 23) | (norm & 0x7FFFFF)


def q16_16_to_f32(q: int) -> float:
    return struct.unpack("<f", struct.pack("<I", q16_16_to_f32_bits(q)))[0]


def trunc_div(numerator: int, denominator: int) -> int:
    """SV signed division: quotient truncates toward zero."""
    if denominator == 0:
        raise ZeroDivisionError
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    return sign * (abs(numerator) // abs(denominator))


def sat32(value: int) -> int:
    return max(I32_MIN, min(I32_MAX, value))


def f32_to_q16_16(value: float) -> int:
    """Match the RTL conversion (truncating right shifts and saturating)."""
    value = f32(value)
    if not math.isfinite(value):
        return I32_MIN if math.copysign(1.0, value) < 0 else I32_MAX
    # The RTL operates on the IEEE mantissa and shifts right, so this is the
    # same truncation toward zero for the representable normal score range.
    return sat32(math.trunc(value * Q))


def q_mul(a: int, b: int) -> int:
    # Python's // differs for negative values; arithmetic SV >>> floors, which
    # is exactly the signed floor division below.
    return sat32((a * b) >> 16)


def q_exp_approx(value: float) -> tuple[float, int]:
    """Return RTL-style f32 output and its Q16.16 integer."""
    x = f32_to_q16_16(value)
    q8 = 8 * Q
    if x <= -q8:
        result = 0
    elif x >= q8:
        result = I32_MAX
    else:
        total = Q
        term = Q
        term = q_mul(term, x); total = sat32(total + term)
        term = q_mul(term, x); total = sat32(total + trunc_div(term, 2))
        term = q_mul(term, x); total = sat32(total + trunc_div(term, 6))
        term = q_mul(term, x); total = sat32(total + trunc_div(term, 24))
        result = total
    return q16_16_to_f32(result), result


def _summarize(points: list[float]) -> dict[str, Any]:
    rows = []
    max_abs = 0.0
    max_rel = 0.0
    for x in points:
        observed, q = q_exp_approx(x)
        expected = f32(math.exp(x))
        error = abs(observed - expected)
        relative = error / expected if expected else 0.0
        max_abs = max(max_abs, error)
        max_rel = max(max_rel, relative)
        rows.append((x, observed, expected, error, q))
    worst = max(rows, key=lambda row: row[3])
    return {
        "sample_count": len(rows),
        "domain": {"min": min(x for x, *_ in rows), "max": max(x for x, *_ in rows)},
        "max_absolute_error": max_abs,
        "max_relative_error": max_rel,
        "worst_case": {
            "input": worst[0], "input_bits": f32_bits(worst[0]),
            "observed": worst[1], "observed_bits": f32_bits(worst[1]),
            "reference": worst[2], "reference_bits": f32_bits(worst[2]),
            "absolute_error": worst[3], "q16_16": worst[4],
        },
        "boundary_vectors": [
            {"input": x, "input_bits": f32_bits(x), "observed": q_exp_approx(x)[0],
             "reference": f32(math.exp(x)), "q16_16": q_exp_approx(x)[1]}
            for x in (-8.0, -1.0, -0.5, -0.0, 0.0, 8.0)
        ],
    }


def evaluate_grid() -> dict[str, Any]:
    # Dense deterministic grid covers the stabilized candidate domain and
    # separately probes both saturation boundaries.  It is characterization,
    # not an oracle corpus.
    stabilized = [f32(-8.0 * i / 65536.0) for i in range(65537)]
    probe = stabilized + [f32(-8.5), f32(8.0), f32(8.5)]
    return {
        "stabilized_domain": _summarize(stabilized),
        "extended_probe": _summarize(probe),
    }


def package_evidence(package: Path) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = contract.get("package", {}).get("files", {})
    required = tuple(expected) if expected else ("manifest.json", "weights.bin", "scales.bin", "calibration_ids.bin", "receipt.json")
    if not all((package / name).is_file() for name in required):
        return {"available": False, "path": str(package), "missing": [name for name in required if not (package / name).is_file()]}
    mismatches = {name: {"expected": digest, "actual": sha256_file(package / name)}
                  for name, digest in expected.items() if sha256_file(package / name) != digest}
    if mismatches:
        raise ValueError(f"package hash mismatch: {mismatches}")
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(package),
        "manifest_sha256": sha256_file(package / "manifest.json"),
        "weights_sha256": sha256_file(package / "weights.bin"),
        "scales_sha256": sha256_file(package / "scales.bin"),
        "calibration_ids_sha256": sha256_file(package / "calibration_ids.bin"),
        "receipt_sha256": sha256_file(package / "receipt.json"),
        "manifest_model": manifest.get("model"),
    }


def assess_checkpoint_boundary() -> dict[str, Any]:
    receipt = json.loads(QDQ.read_text(encoding="utf-8"))
    if receipt.get("schema") != "tinystories-1m-qdq-semantics-v1":
        raise ValueError("Q/DQ receipt schema mismatch")
    receipt_digest = receipt.get("receipt_sha256")
    if receipt_digest != canonical_sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"}):
        raise ValueError("Q/DQ receipt self-hash mismatch")
    identity = receipt.get("identity", {})
    if identity.get("contract_sha256") != sha256_file(CONTRACT):
        raise ValueError("Q/DQ receipt contract identity mismatch")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected_package = contract.get("package", {}).get("files", {})
    for key, identity_key in (("manifest.json", "package_manifest_sha256"),
                              ("weights.bin", "package_weights_sha256"),
                              ("scales.bin", "package_scales_sha256")):
        if identity.get(identity_key) != expected_package.get(key):
            raise ValueError(f"Q/DQ receipt package identity mismatch: {key}")
    checkpoints = receipt.get("candidate_oracle", {}).get("checkpoints", {})
    q = checkpoints.get("block.attention.q", {})
    k = checkpoints.get("block.attention.k", {})
    # The authenticated values are [num_heads, head_dim] for the final token,
    # not [num_heads, query_length, key_length] score rows.
    q_shape, k_shape = q.get("shape"), k.get("shape")
    complete_rows = bool(q_shape and k_shape and len(q_shape) == 3 and len(k_shape) == 3)
    return {
        "qdq_receipt_path": str(QDQ.relative_to(ROOT)),
        "qdq_receipt_file_sha256": sha256_file(QDQ),
        "qdq_receipt_self_sha256": receipt_digest,
        "qdq_receipt_schema": receipt["schema"],
        "qdq_identity": identity,
        "q_checkpoint_shape": q_shape,
        "k_checkpoint_shape": k_shape,
        "complete_causal_score_rows_available": complete_rows,
        "comparison_status": "available" if complete_rows else "unsupported",
        "reason": None if complete_rows else "authenticated trace stores final-token Q/K vectors, not complete causal attention score rows",
    }


def build_report(package: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "tinystories-1m-q-exp-candidate-evaluation-v1",
        "model": "TinyStories-1M",
        "status": "unsupported",
        "candidate": {
            "name": "q_exp_approx",
            "rtl": str(RTL.relative_to(ROOT)),
            "rtl_sha256": sha256_file(RTL),
            "encoding": "signed Q16.16",
            "polynomial": "fourth-order Taylor with Q16.16 multiply and signed truncating divisions",
            "saturation": {"input_le": -8.0, "input_ge": 8.0, "low_output": 0, "high_output": "INT32_MAX"},
        },
        "package": package_evidence(package),
        "contract": {"path": str(CONTRACT.relative_to(ROOT)), "sha256": sha256_file(CONTRACT)},
        "qdq_boundary": assess_checkpoint_boundary(),
        "candidate_characterization": evaluate_grid(),
        "claims": {
            "full_attention_row_error": False,
            "full_model_output_equivalence": False,
            "hardware_inference": False,
            "rtl_lowering": False,
        },
        "decision": {
            "accepted": False,
            "reason_code": "full_attention_score_rows_unavailable",
            "message": "Do not promote q_exp_approx: only bounded primitive characterization is available; the authenticated TinyStories-1M trace lacks complete causal score rows and a softmax-output oracle.",
        },
    }
    report["sha256"] = canonical_sha256({k: v for k, v in report.items() if k != "sha256"})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE_DEFAULT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.package)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "sha256": report["sha256"], "out": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
