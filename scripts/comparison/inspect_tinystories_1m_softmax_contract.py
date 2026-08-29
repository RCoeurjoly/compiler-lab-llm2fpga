#!/usr/bin/env python3
"""Recover the TinyStories-1M reference softmax contract without copying RTL.

The kev-gpt-derived RTL is an external reference.  This tool records hashes of
the relevant reference files and extracts only the arithmetic facts needed to
compare it with the package-aware compiler boundary.  It deliberately refuses
to report a contract when the expected source patterns are absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_ROOT = pathlib.Path(
    "/home/roland/kev-gpt/.worktrees/kintex-selftest"
)
COMPILER_BOUNDARY = ROOT / "artifacts/comparison/tinystories-1m-exp-lowering-boundary.json"
COMPILER_FRONTIER = ROOT / "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"

REFERENCE_FILES = (
    pathlib.Path("fpga/rtl/gptneo_attention.sv"),
    pathlib.Path("fpga/rtl/gptneo_iterative_divider.sv"),
    pathlib.Path("tinystories/hardware_reference.py"),
    pathlib.Path("tinystories/rtl_memories.py"),
    pathlib.Path("fpga/tb/tb_gptneo_attention.sv"),
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        raise ValueError(f"reference pattern unavailable: {label}")


def _round_exp(index: int) -> int:
    return round(math.exp((index - 4096) / 256.0) * (1 << 20))


def _reference_contract(reference_root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {str(name): reference_root / name for name in REFERENCE_FILES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError("missing reference files: " + ", ".join(missing))
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}

    attention = text["fpga/rtl/gptneo_attention.sv"]
    divider = text["fpga/rtl/gptneo_iterative_divider.sv"]
    hardware = text["tinystories/hardware_reference.py"]
    memories = text["tinystories/rtl_memories.py"]
    testbench = text["fpga/tb/tb_gptneo_attention.sv"]

    patterns = {
        "attention_q16": r"Q16\.16 data",
        "attention_unscaled": r"scores are intentionally unscaled",
        "attention_shift": r"score_code\s*=\s*product_total\s*>>>\s*24",
        "attention_delta_clamp": r"if\s*\(delta_code\s*<\s*-4096\)",
        "attention_lut": r"exp_lut\s*\[exp_index\]",
        "attention_zero_exp": r"exp_value\s*<=\s*21'd1048576",
        "attention_sum": r"reg\s*\[63:0\]\s+exp_sum",
        "attention_prefix": r"if\s*\(time_index==position\)",
        "context_round_positive": r"context_total\s*\+\s*\$signed\(exp_sum>>>1\)",
        "context_round_negative": r"context_total\s*-\s*\$signed\(exp_sum>>>1\)",
        "divider_trunc": r"Division truncates toward zero",
        "divider_signed": r"quotient\s*<=\s*negative\s*\?\s*-\$signed\(completed_quotient\[31:0\]\)",
        "reference_exp": r"round\(math\.exp\(\(index\s*-\s*4096\)\s*/\s*256\.0\)\s*\*\s*\(1\s*<<\s*20\)\)",
        "memory_exp": r"value\s*=\s*math\.exp\(\(index\s*-\s*4096\)\s*/\s*256\.0\)",
        "test_position": r"begin_token\(1,3\*65536\);\s*drain\(2\*65536\)",
    }
    for label, pattern in patterns.items():
        source = attention if label.startswith("attention_") or label.startswith("context_") else (
            divider if label.startswith("divider_") else
            hardware if label == "reference_exp" else
            memories if label == "memory_exp" else testbench
        )
        _require(source, pattern, label)

    source_records = {
        name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for name, path in paths.items()
    }
    contract = {
        "dimensions": {"hidden": 64, "heads": 16, "head_dim": 4, "context_max": 32},
        "score": {
            "input_encoding": "signed Q16.16 q and k",
            "scaling": "unscaled GPT-Neo dot product",
            "accumulator_bits": 96,
            "post_shift": 24,
            "rounding": "truncate arithmetic right shift",
            "saturation": "none at score register",
            "causal_mask": "implicit prefix time_index <= position; no mask port",
        },
        "exponential": {
            "input": "score_code - score_max in signed score-code units",
            "clamp": "delta < -4096 maps to LUT index 0; delta >= 0 maps to special one",
            "domain": "[-16, 0] in Q8.8 score units",
            "lut_entries": 4096,
            "lut_indices": "0..4095 represent exp(-16)..exp(-1/256)",
            "output_encoding": "unsigned Q1.20",
            "zero_delta_value": 1048576,
            "generation": "round(exp((index-4096)/256) * 2^20)",
        },
        "normalization": {
            "sum_bits": 64,
            "context_product": "Q1.20 probability times signed Q16.16 value",
            "rounding": "add floor(sum/2) for non-negative numerator; subtract for negative",
            "division": "unsigned restoring magnitude, sign reapplied; truncates toward zero",
            "zero_denominator": "quotient zero",
        },
    }
    vectors = {
        "exp_lut": [
            {"index": i, "delta_q8_8": i - 4096, "output_q1_20": _round_exp(i)}
            for i in (0, 1, 256, 2048, 4094, 4095)
        ],
        "special_zero_delta": {"delta": 0, "output_q1_20": 1 << 20},
        "clamp": [
            {"delta_q8_8": -4097, "effective_index": 0},
            {"delta_q8_8": -4096, "effective_index": 0},
            {"delta_q8_8": -1, "effective_index": 4095},
            {"delta_q8_8": 0, "effective_index": "special_one"},
            {"delta_q8_8": 1, "effective_index": "special_one"},
        ],
        "causal_prefix": {
            "position": 1,
            "score_codes": [0, -256],
            "exp_values_q1_20": [1 << 20, _round_exp(3840)],
            "mask": "only time indices 0 and 1 are visited; future entries are not read",
        },
        "context_rounding": [
            {"numerator": 3, "denominator": 4, "rounded_numerator": 5, "quotient": 1},
            {"numerator": -3, "denominator": 4, "rounded_numerator": -5, "quotient": -1},
        ],
        "existing_testbench": {
            "position_0_value_q16_16": 65536,
            "position_0_expected_context_q16_16": 65536,
            "position_1_value_q16_16": 196608,
            "position_1_expected_context_q16_16": 131072,
        },
    }
    return {"files": source_records, "contract": contract}, vectors


def _compiler_boundary() -> dict[str, Any]:
    if not COMPILER_BOUNDARY.is_file() or not COMPILER_FRONTIER.is_file():
        raise ValueError("compiler softmax boundary artifacts are unavailable")
    boundary = json.loads(COMPILER_BOUNDARY.read_text(encoding="utf-8"))
    frontier = json.loads(COMPILER_FRONTIER.read_text(encoding="utf-8"))
    if boundary.get("source", {}).get("operation") != "math.exp":
        raise ValueError("compiler boundary is not the authenticated math.exp site")
    if boundary.get("source", {}).get("semantic_role") != "attention softmax":
        raise ValueError("compiler boundary semantic role changed")
    return {
        "boundary_report_sha256": sha256(COMPILER_BOUNDARY),
        "frontier_report_sha256": sha256(COMPILER_FRONTIER),
        "operation": boundary["source"]["operation"],
        "input_type": boundary["source"]["input_type"],
        "output_type": boundary["source"]["output_type"],
        "stabilization": boundary["source"]["stabilization"],
        "location": boundary["boundary"]["location"],
        "contract_fields": boundary["boundary"]["required_contract"],
        "frontier_status": frontier.get("status"),
    }


def build_report(reference_root: pathlib.Path) -> dict[str, Any]:
    try:
        source, vectors = _reference_contract(reference_root)
        compiler = _compiler_boundary()
        status = "reference_contract_recovered_compiler_boundary_unaligned"
        failure = None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        source = {"files": {}, "contract": None}
        vectors = {}
        compiler = None
        status = "unsupported"
        failure = str(exc)

    report: dict[str, Any] = {
        "schema": "tinystories-1m-softmax-contract-diagnostic-v1",
        "model": "TinyStories-1M",
        "status": status,
        "reference_root": str(reference_root),
        "reference": source,
        "vectors": vectors,
        "compiler_boundary": compiler,
        "comparison": {
            "reference_input_encoding": "integer Q16.16/Q8.8/Q1.20 datapath",
            "compiler_input_encoding": "f32 stabilized score to math.exp",
            "same_contract": False,
            "equivalence_claim": False,
            "next_required_evidence": [
                "derive compiler score quantization and causal mask from the package-aware graph",
                "run both implementations on identical score rows",
                "bind an exhaustive or accepted full-model output gate before approximation",
            ],
        },
        "authority": {
            "functional_equivalence": False,
            "rtl_equivalence": False,
            "hardware_equivalence": False,
            "optimization_acceptance": False,
        },
    }
    if failure is not None:
        report["failure"] = failure
    payload = json.dumps(report, indent=2, sort_keys=True).encode() + b"\n"
    report["sha256"] = hashlib.sha256(payload).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=pathlib.Path, default=DEFAULT_REFERENCE_ROOT)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(args.reference_root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
