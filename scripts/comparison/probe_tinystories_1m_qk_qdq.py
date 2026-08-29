#!/usr/bin/env python3
"""Run an authenticated block-0 q/k QDQ projection probe.

This is an evidence-producing adapter probe, not a compiler or hardware
equivalence claim.  It deliberately records the float source and the fixed
projection separately.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories import model_adapter_reference_package as adapter
from scripts.comparison.tinystories_1m_fixed_qdq_helper import (
    dequantize_int8_to_q16, load_fixed_hardware_profile, quantize_q16_to_int8,
)

SCHEMA = "tinystories-1m-compiler-qk-qdq-probe-v1"

def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _q16(values: list[float]) -> list[int]:
    return [int(round(float(v) * (1 << 16))) for v in values]

def _scales_q24(boundary: dict[str, Any]) -> list[int]:
    scales = boundary.get("scales")
    if not isinstance(scales, list) or len(scales) != 64:
        raise ValueError("activation_scale_width_mismatch")
    return [int(round(float(v) * (1 << 24))) for v in scales]

def _head_scale_slice(scales_q24: list[int], head_index: int) -> list[int]:
    if head_index < 0 or head_index >= 16:
        raise ValueError("head_index_out_of_range")
    start = head_index * 4
    stop = start + 4
    if len(scales_q24) != 64:
        raise ValueError("activation_scale_width_mismatch")
    return scales_q24[start:stop]

def build_probe(contract: Path, package: Path, model: Path, profile: Path) -> dict[str, Any]:
    profile_data = load_fixed_hardware_profile(profile)
    bundle = adapter.load_authenticated_package(contract, package, model)
    trace = adapter.build_numeric_trace_gate(bundle)
    if trace.get("status") != "matched":
        raise ValueError("package_trace_mismatch")
    prompt = bundle.contract["reference"]["prompt_tokens"]
    q_float = trace["checkpoints"]["block.attention.q"]["package_reconstruction"]
    k_float = trace["checkpoints"]["block.attention.k"]["package_reconstruction"]
    if not isinstance(q_float, list) or len(q_float) != 16 or not isinstance(k_float, list) or len(k_float) != 16:
        raise ValueError("qk_shape_mismatch")
    boundaries = bundle.receipt["activation_qdq_boundaries"]
    q_scales = _scales_q24(boundaries["transformer.h.0.attn.attention.q_proj.output"])
    k_scales = _scales_q24(boundaries["transformer.h.0.attn.attention.k_proj.output"])
    q_q16 = [_q16(row) for row in q_float]
    k_q16 = [_q16(row) for row in k_float]
    q_head_scales = [_head_scale_slice(q_scales, head) for head in range(16)]
    k_head_scales = [_head_scale_slice(k_scales, head) for head in range(16)]
    q_codes = [quantize_q16_to_int8(row, scales) for row, scales in zip(q_q16, q_head_scales, strict=True)]
    k_codes = [quantize_q16_to_int8(row, scales) for row, scales in zip(k_q16, k_head_scales, strict=True)]
    q_roundtrip = [dequantize_int8_to_q16(row, scales) for row, scales in zip(q_codes, q_head_scales, strict=True)]
    k_roundtrip = [dequantize_int8_to_q16(row, scales) for row, scales in zip(k_codes, k_head_scales, strict=True)]
    result: dict[str, Any] = {
        "schema": SCHEMA, "status": "compiler_qk_qdq_probe",
        "claims": {"compiler_equivalence": False, "rtl_equivalence": False, "hardware_inference": False},
        "identity": {"contract_sha256": bundle.receipt["identity"]["contract_sha256"],
                     "package_manifest_sha256": bundle.receipt["identity"]["package"]["manifest_sha256"],
                     "profile_sha256": profile_data["profile_sha256"],
                     "prompt_tokens": prompt, "block_index": 0, "token_index": len(prompt)-1},
        "source": {"execution": "authenticated_package_model_export_trace", "trace_sha256": trace["trace_sha256"],
                   "q_boundary": "transformer.h.0.attn.attention.q_proj.output",
                   "k_boundary": "transformer.h.0.attn.attention.k_proj.output"},
        "q": {"shape": [16,4], "float32": q_float, "q16_16": q_q16, "scales_q8_24": q_head_scales, "int8": q_codes, "q16_16_roundtrip": q_roundtrip},
        "k": {"shape": [16,4], "float32": k_float, "q16_16": k_q16, "scales_q8_24": k_head_scales, "int8": k_codes, "q16_16_roundtrip": k_roundtrip},
        "next_boundary": {"code": "compiler_graph_rewrite_not_implemented", "required": "Integrate this projection into the exported/lowered graph before fixed-row equivalence."},
    }
    result["sha256"] = _sha(result)
    return result

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, required=True); p.add_argument("--package", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True); p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); result = build_probe(a.contract, a.package, a.model, a.profile)
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    return 0

if __name__ == "__main__": raise SystemExit(main())
