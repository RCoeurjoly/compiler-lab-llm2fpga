#!/usr/bin/env python3
"""Receipt the pinned kev-gpt LayerNorm evidence without importing it into lowering.

This is an evidence extractor, not a compiler implementation.  It content-binds
the fixed Python oracle and the checked-in synthesizable RTL, records their
independent arithmetic contracts, and refuses to select one where their full
input domains differ.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np


SCHEMA = "tinystories-1m-layernorm-semantics-v1"
REFERENCE_REVISION = "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f"
SOURCES = {
    "tinystories/hardware_reference.py": "3780015d7f4be69cae3952fb630af971a37490a17cf8519fd6ac81a7bb080371",
    "fpga/rtl/gptneo_layernorm.sv": "354104a1d2b57552bdca54f291764d90d6b9f7d6f8a2ecc2cb0d95a396430e1b",
    "fpga/rtl/gptneo_iterative_divider.sv": "8665cc99e7bf98e0415775a36c78aa4ff242d30c976dce0719e6d465686a1540",
}
CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
QDQ_PROFILE_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"


class LayerNormEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def authenticate_sources(reference_root: Path) -> list[dict[str, str]]:
    if _git(reference_root, "rev-parse", "HEAD") != REFERENCE_REVISION:
        raise LayerNormEvidenceError("git_revision_mismatch", str(reference_root))
    evidence: list[dict[str, str]] = []
    for relative, expected in SOURCES.items():
        path = reference_root / relative
        if not path.is_file():
            raise LayerNormEvidenceError("source_missing", relative)
        actual = _sha256(path)
        if actual != expected:
            raise LayerNormEvidenceError("source_hash_mismatch", f"{relative}: {actual} != {expected}")
        if _git(reference_root, "status", "--porcelain", "--", relative):
            raise LayerNormEvidenceError("source_worktree_dirty", relative)
        evidence.append({"path": relative, "sha256": actual})
    return evidence


def _require_anchor(text: str, anchor: str, source: str) -> None:
    if anchor not in text:
        raise LayerNormEvidenceError("semantic_anchor_missing", f"{source}: {anchor}")


def _runtime_probe(reference_root: Path) -> dict[str, Any]:
    """Execute the content-bound runtime; this is a probe, never a lowering."""
    path = reference_root / "tinystories/hardware_reference.py"
    root = str(reference_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    sys.modules.pop("tinystories.hardware_reference", None)
    module = importlib.import_module("tinystories.hardware_reference")
    if Path(module.__file__).resolve() != path.resolve():
        raise LayerNormEvidenceError("module_origin_mismatch", str(module.__file__))
    values = np.asarray([65536 if index % 2 == 0 else -65536 for index in range(64)], dtype=np.int64)
    output = module.fixed_layer_norm(values, np.full(64, 65536, dtype=np.int64), np.zeros(64, dtype=np.int64))
    payload = {"shape": [64], "dtype": "signed_q16.16_int64_runtime", "values": [int(value) for value in output]}
    return {"input_pattern": "alternating_plus_minus_one_q16.16", "output": payload, "sha256": canonical_sha256(payload)}


def _trunc_toward_zero(numerator: int, denominator: int) -> int:
    quotient = abs(numerator) // abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


def _wrap_signed(value: int, width: int) -> int:
    unsigned = value & ((1 << width) - 1)
    return unsigned - (1 << width) if unsigned & (1 << (width - 1)) else unsigned


def overflow_witness(reference_root: Path) -> dict[str, Any]:
    """Run the oracle and an independently written model of declared RTL widths."""
    path = reference_root / "tinystories/hardware_reference.py"
    root = str(reference_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    sys.modules.pop("tinystories.hardware_reference", None)
    runtime = importlib.import_module("tinystories.hardware_reference")
    if Path(runtime.__file__).resolve() != path.resolve():
        raise LayerNormEvidenceError("module_origin_mismatch", str(runtime.__file__))
    values = [-2**31, 2**31 - 1] * 32
    array = np.asarray(values, dtype=np.int64)
    try:
        runtime.fixed_layer_norm(array, np.full(64, 65536, dtype=np.int64), np.zeros(64, dtype=np.int64))
    except Exception as error:  # Exact runtime exception is evidence, not a replacement model.
        runtime_result: dict[str, Any] = {"status": "raised", "exception": f"{type(error).__name__}: {error}"}
    else:
        runtime_result = {"status": "accepted_unexpectedly"}

    # Independent arithmetic model of the RTL declarations: 33-bit deltas,
    # 66-bit squares, a 72-bit serial sum, then assignment to unsigned 64-bit
    # variance.  It intentionally does not reuse the reference implementation.
    mean = _trunc_toward_zero(sum(values), 64)
    deltas = [value - mean for value in values]
    square_sum_72 = sum(abs(delta) * abs(delta) for delta in deltas) & ((1 << 72) - 1)
    variance_64 = ((square_sum_72 // 64) + 42950) & ((1 << 64) - 1)
    deviation = math.isqrt(variance_64)
    normalized = [_trunc_toward_zero(delta << 16, deviation) for delta in deltas]
    rtl_result = {
        "mean": mean,
        "square_sum_72": square_sum_72,
        "variance_64": variance_64,
        "deviation_floor_sqrt": deviation,
        "normalized_first_two": normalized[:2],
    }
    return {"input_q16_16": values, "runtime": runtime_result, "independent_rtl_width_model": rtl_result}


def affine_overflow_witness() -> dict[str, Any]:
    """Show the output-width conflict after legal normalized values reach affine."""
    normalized = [-370727, 370727]
    gamma = 2**31 - 1
    beta = 0
    runtime = [((value * gamma) >> 16) + beta for value in normalized]
    rtl = [_wrap_signed(value, 32) for value in runtime]
    return {
        "normalized_q16_16": normalized,
        "gamma_q16_16": gamma,
        "beta_q16_16": beta,
        "runtime_int64_affine_output": runtime,
        "rtl_signed_int32_out_y": rtl,
    }


def derive_receipt(reference_root: Path, qdq_profile: Path) -> dict[str, Any]:
    sources = authenticate_sources(reference_root)
    if not qdq_profile.is_file() or _sha256(qdq_profile) != QDQ_PROFILE_SHA256:
        raise LayerNormEvidenceError("qdq_profile_identity_mismatch", str(qdq_profile))
    runtime = (reference_root / "tinystories/hardware_reference.py").read_text(encoding="utf-8")
    rtl = (reference_root / "fpga/rtl/gptneo_layernorm.sv").read_text(encoding="utf-8")
    divider = (reference_root / "fpga/rtl/gptneo_iterative_divider.sv").read_text(encoding="utf-8")
    # These anchors make a changed source fail before any textual conclusion is emitted.
    for text, anchor, source in [
        (runtime, "epsilon_q32 = 42950", "hardware_reference.py"),
        (runtime, "math.isqrt(variance)", "hardware_reference.py"),
        (runtime, "outputs[row_index] = (normalized * gamma >> Q_VALUE) + beta", "hardware_reference.py"),
        (rtl, "localparam [63:0] EPSILON_Q32 = 64'd42950", "gptneo_layernorm.sv"),
        (rtl, "reg [71:0] square_sum", "gptneo_layernorm.sv"),
        (rtl, "out_y <= (affine >>> 16) + $signed(bmem[index])", "gptneo_layernorm.sv"),
        (divider, "quotient <= negative ? -$signed(completed_quotient[31:0])", "gptneo_iterative_divider.sv"),
    ]:
        _require_anchor(text, anchor, source)

    candidate_trace = json.loads(qdq_profile.read_text(encoding="utf-8"))["software_trace"]
    runtime_probe = _runtime_probe(reference_root)
    reduction_overflow = overflow_witness(reference_root)
    affine_overflow = affine_overflow_witness()
    return {
        "schema": SCHEMA,
        "version": 1,
        "status": "incomplete",
        "selected_profile": None,
        "identity": {
            "frozen_contract_sha256": CONTRACT_SHA256,
            "fixed_hardware_qdq_profile_sha256": QDQ_PROFILE_SHA256,
            "reference_git_revision": REFERENCE_REVISION,
            "sources": sources,
        },
        "candidate_profiles": {
            "fixed_hardware_runtime": {
                "input_and_parameters": {"format": "signed_q16.16_int32", "byte_order": "little_endian_package_materialization"},
                "reduction": {"mean": "signed_int64_numpy_sum_then_truncation_toward_zero_divide_by_D", "variance": "signed_int64_numpy_product_and_sum_then_floor_divide_by_D", "order": "NumPy API does not promise reduction order", "overflow": "signed_int64_NumPy_wrap"},
                "epsilon": {"q32": 42950, "real": "round(1e-5 * 2^32)"},
                "inverse_sqrt": {"algorithm": "integer_floor_square_root_then_signed_truncation_toward_zero_division", "implementation": "math.isqrt"},
                "affine": {"gamma_beta_format": "signed_q16.16_int32", "rounding": "arithmetic_right_shift_by_16", "output_dtype": "numpy_int64", "saturation": "none"},
                "non_finite": {"status": "not_applicable_after_integer_materialization"},
            },
            "synthesizable_rtl": {
                "input_and_parameters": {"format": "signed_q16.16_int32", "byte_order": "bit_vectors_no_external_byte_stream"},
                "reduction": {"mean": "signed_64_bit_accumulator_then_signed_divide_by_D_truncation_toward_zero", "variance": "33_bit_delta; 66_bit_square; 72_bit_serial_ascending_index_square_sum; unsigned_64_bit_variance_assignment", "order": "ascending_index_0_to_D_minus_1", "overflow": "two_complement_truncation_at_declared_register_widths"},
                "epsilon": {"q32": 42950, "real": "round(1e-5 * 2^32)"},
                "inverse_sqrt": {"algorithm": "restoring_integer_square_root; iterative_signed_divider", "rounding": "floor_sqrt_then_truncation_toward_zero_quotient"},
                "affine": {"gamma_beta_format": "signed_q16.16_int32", "rounding": "arithmetic_right_shift_by_16", "output_dtype": "signed_32_bit", "saturation": "none; assignment truncates/wraps"},
                "non_finite": {"status": "impossible_at_integer_ports"},
            },
        },
        "checkpoint_trace": {
            "authority": "content_authenticated_fixed_runtime_not_board_authenticated",
            "prompt_tokens": candidate_trace["prompt_tokens"],
            "block_index": candidate_trace["block_index"],
            "token_index": candidate_trace["token_index"],
            "ln_1": candidate_trace["checkpoints"]["block.ln_1.output"],
            "ln_2": candidate_trace["checkpoints"]["block.ln_2.output"],
        },
        "runtime_probe": runtime_probe,
        "conflicts": [
            {
                "code": "layernorm_overflow_domain_conflict",
                "runtime": "variance products and reduction are NumPy signed int64 and can wrap for legal int32 Q16.16 inputs",
                "rtl": "delta squares and their serial sum retain 66/72 bits before a distinct 64-bit variance truncation",
                "witness_domain": "a row containing both -2147483648 and 2147483647 is legal at the declared ports and exercises different intermediate widths",
                "executable_witness": reduction_overflow,
                "effect": "no one full-domain bit-exact LayerNorm lowering may be selected from these two authorities",
            },
            {
                "code": "layernorm_affine_output_width_conflict",
                "runtime": "the fixed runtime retains its affine result as NumPy signed int64",
                "rtl": "out_y is signed 32-bit and assignment truncates/wraps without saturation",
                "executable_witness": affine_overflow,
                "effect": "the authorities differ even after normalized Q16.16 values are supplied directly to gamma/beta affine",
            },
            {
                "code": "board_checkpoint_authority_missing",
                "effect": "the deterministic Q16.16 LN checkpoint hashes are fixed-runtime evidence, not FPGA board evidence",
            },
        ],
        "incomplete_reasons": [
            "A board-bound LayerNorm trace and an approved resolution of the runtime/RTL overflow-domain conflict are required before selecting a compiler profile.",
            "The affine output-width conflict must also be resolved or constrained by an approved input-domain proof.",
            "This receipt does not authorize copying reference source or RTL into compiler output.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--qdq-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = derive_receipt(args.reference_root, args.qdq_profile)
    receipt["receipt_sha256"] = receipt_sha256(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
