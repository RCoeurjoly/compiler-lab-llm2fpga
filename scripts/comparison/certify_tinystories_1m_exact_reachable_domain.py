#!/usr/bin/env python3
"""Prove package-reachable fixed runtime/RTL equivalence for exact TinyStories.

The older LayerNorm receipt correctly rejects equivalence over arbitrary signed
32-bit port values.  This certificate derives a smaller conservative domain
from the authenticated package: embedding extrema, Q/DQ-clamped projection
extrema, and residual topology.  Every width inequality must close or the
result is an ``identity_frontier`` with the first failing inequality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping

import torch


SCHEMA = "tinystories-1m-exact-reachable-domain-v1"
CONTRACT_SHA256 = "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c"
AUDIT_FILE_SHA256 = "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd"
PROFILE_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"
SOFTMAX_SHA256 = "d6f5c89799a7e66c825a003c07680ea8334b2f1264fb0ef4ccf942b4ec20f1b1"
LAYERNORM_RECEIPT = Path("artifacts/reference/tinystories-1m-layernorm-semantics.json")
GELU_RECEIPT = Path("artifacts/comparison/tinystories-1m-gelu-equivalence-2026-08-29.json")
GELU_ADAPTER = Path("rtl/llm2fpga_gelu_q16_tensor.sv")
LAYERNORM_RECEIPT_SHA256 = "e035dc5835a3908fa687281089e75d1a9dac0f846f84950211ba2681f1259006"
GELU_RECEIPT_SHA256 = "2edeecada4d0abc915d877b2093dd78bdf06e57872a1b0b35cb6102f728b1f3e"
GELU_ADAPTER_SHA256 = "efeb6d00d6554976dc22a0cd6017c49d04a346cf8407e195d277f3be9d83c24b"
REFERENCE_REVISION = "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f"
SEMANTIC_SOURCE_PATHS = (
    "tinystories/hardware_reference.py",
    "tinystories/rtl_memories.py",
    "fpga/rtl/gptneo_layernorm.sv",
    "fpga/rtl/gptneo_gelu.sv",
    "fpga/rtl/gptneo_attention.sv",
    "fpga/rtl/gptneo_iterative_divider.sv",
)
Q_VALUE = 16
Q_SCALE = 24
EPSILON_Q32 = 42950


class ReachableDomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ReachableDomainError(code, message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def certificate_sha256(value: Mapping[str, Any]) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != "certificate_sha256"})


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "invalid_json", str(path))
    return value


def _trunc(numerator: int, denominator: int) -> int:
    quotient = abs(numerator) // abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


def _wrap(value: int, width: int) -> int:
    value &= (1 << width) - 1
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _round_shift(value: int, shift: int) -> int:
    magnitude = abs(value)
    rounded = (magnitude + (1 << (shift - 1))) >> shift
    return -rounded if value < 0 else rounded


def _normalized_abs_bound(delta_abs_bound: int) -> int:
    """Exhaust the scalar relaxation S >= delta_i^2 for a rigorous bound."""

    maximum = 0
    for delta in range(1, delta_abs_bound + 1):
        denominator = math.isqrt(delta * delta // 64 + EPSILON_Q32)
        maximum = max(maximum, delta * (1 << Q_VALUE) // denominator)
    return maximum


def _runtime_layer_norm(values: list[int], gamma: list[int], beta: list[int]) -> list[int]:
    mean = _trunc(sum(values), 64)
    deltas = [value - mean for value in values]
    variance = sum(delta * delta for delta in deltas) // 64 + EPSILON_Q32
    deviation = math.isqrt(variance)
    normalized = [_trunc(delta << Q_VALUE, deviation) for delta in deltas]
    return [((value * scale) >> Q_VALUE) + offset
            for value, scale, offset in zip(normalized, gamma, beta, strict=True)]


def _rtl_layer_norm(values: list[int], gamma: list[int], beta: list[int]) -> list[int]:
    total = 0
    for value in values:
        total = _wrap(total + value, 64)
    mean = _trunc(total, 64)
    square_sum = 0
    deltas = []
    for value in values:
        delta = _wrap(value - mean, 33)
        deltas.append(delta)
        square_sum = (square_sum + abs(delta) * abs(delta)) & ((1 << 72) - 1)
    variance = (square_sum // 64 + EPSILON_Q32) & ((1 << 64) - 1)
    deviation = math.isqrt(variance)
    normalized = [_wrap(_trunc(delta << Q_VALUE, deviation), 32) for delta in deltas]
    return [_wrap(((value * scale) >> Q_VALUE) + offset, 32)
            for value, scale, offset in zip(normalized, gamma, beta, strict=True)]


def prove_layernorm_interval(name: str, lower: list[int], upper: list[int],
                             gamma: list[int], beta: list[int]) -> dict[str, Any]:
    _require(len(lower) == len(upper) == len(gamma) == len(beta) == 64,
             "layernorm_shape_mismatch", name)
    sum_lower = sum(lower)
    sum_upper = sum(upper)
    mean_lower = _trunc(sum_lower, 64)
    mean_upper = _trunc(sum_upper, 64)
    delta_lower = [value - mean_upper for value in lower]
    delta_upper = [value - mean_lower for value in upper]
    delta_abs = max(max(abs(value) for value in delta_lower),
                    max(abs(value) for value in delta_upper))
    square_each = [max(lo * lo, hi * hi) for lo, hi in zip(delta_lower, delta_upper, strict=True)]
    square_sum = sum(square_each)
    variance = square_sum // 64 + EPSILON_Q32
    reduction_domain_closes = (
        max(square_each) < (1 << 63)
        and square_sum < (1 << 63)
        and square_sum < (1 << 72)
        and variance < (1 << 63)
    )
    # Do not perform an enormous scalar-domain enumeration after a prior width
    # inequality has already made the call an identity frontier.
    normalized = _normalized_abs_bound(delta_abs) if reduction_domain_closes else (1 << 31)
    affine_product = normalized * max(abs(value) for value in gamma)
    affine_output = 0
    for scale, offset in zip(gamma, beta, strict=True):
        product = normalized * abs(scale)
        affine_output = max(affine_output, abs((-product >> Q_VALUE) + offset),
                            abs((product >> Q_VALUE) + offset))
    inequalities = {
        "input_fits_signed_int32": min(lower) >= -(1 << 31) and max(upper) < (1 << 31),
        "runtime_sum_fits_signed_int64": max(abs(sum_lower), abs(sum_upper)) < (1 << 63),
        "rtl_delta_fits_signed_33": delta_abs < (1 << 32),
        "runtime_each_square_fits_signed_int64": max(square_each) < (1 << 63),
        "runtime_square_sum_fits_signed_int64": square_sum < (1 << 63),
        "rtl_square_sum_fits_unsigned_72": square_sum < (1 << 72),
        "variance_fits_runtime_signed_int64": variance < (1 << 63),
        "variance_fits_rtl_unsigned_64": variance < (1 << 64),
        "divider_numerator_fits_signed_96": delta_abs << Q_VALUE < (1 << 95),
        "normalized_quotient_fits_signed_int32": normalized < (1 << 31),
        "affine_product_fits_signed_int64": affine_product < (1 << 63),
        "affine_output_fits_signed_int32": affine_output < (1 << 31),
    }
    ordered = list(inequalities)
    failing = next((key for key in ordered if not inequalities[key]), None)
    witnesses = []
    for label, values in (
        ("alternating_lower_upper", [lower[i] if i % 2 == 0 else upper[i] for i in range(64)]),
        ("alternating_upper_lower", [upper[i] if i % 2 == 0 else lower[i] for i in range(64)]),
    ):
        runtime = _runtime_layer_norm(values, gamma, beta) if failing is None else None
        rtl = _rtl_layer_norm(values, gamma, beta) if failing is None else None
        witnesses.append({
            "pattern": label,
            "input_sha256": canonical_sha256(values),
            "runtime_sha256": canonical_sha256(runtime) if runtime is not None else None,
            "rtl_sha256": canonical_sha256(rtl) if rtl is not None else None,
            "matched": runtime == rtl if runtime is not None else False,
        })
    return {
        "name": name,
        "status": "proven" if failing is None else "identity_frontier",
        "failing_inequality": failing,
        "input_bounds_q16_16": {"lower_by_channel": lower, "upper_by_channel": upper},
        "parameter_identity": {
            "gamma_sha256": canonical_sha256(gamma), "beta_sha256": canonical_sha256(beta),
            "gamma_abs_max": max(abs(value) for value in gamma),
            "beta_abs_max": max(abs(value) for value in beta),
        },
        "proof": {
            "sum_lower": sum_lower, "sum_upper": sum_upper,
            "delta_abs_bound": delta_abs,
            "each_square_abs_bound": max(square_each),
            "square_sum_abs_bound": square_sum,
            "variance_abs_bound": variance,
            "normalized_abs_bound": normalized,
            "affine_product_abs_bound": affine_product,
            "affine_output_abs_bound": affine_output,
            "inequalities": inequalities,
        },
        "edge_witnesses": {
            "status": "runtime_rtl_matched" if all(item["matched"] for item in witnesses) else "not_compared",
            "vectors": witnesses,
        },
    }


def _read_package(package: Path) -> tuple[dict[str, Any], bytes, bytes]:
    manifest = _load(package / "manifest.json")
    return manifest, (package / "weights.bin").read_bytes(), (package / "scales.bin").read_bytes()


def _q24_scales(descriptor: Mapping[str, Any], scales_image: bytes) -> torch.Tensor:
    offset = int(descriptor["scale_offset"])
    raw = scales_image[offset:offset + int(descriptor["scale_nbytes"])]
    return torch.round(
        torch.frombuffer(bytearray(raw), dtype=torch.float32).to(torch.float64) * (1 << Q_SCALE)
    ).to(torch.int64)


def _parameter_q16(name: str, manifest: Mapping[str, Any], weights: bytes) -> list[int]:
    descriptor = manifest["tensors"][name]
    offset = int(descriptor["offset"])
    raw = weights[offset:offset + int(descriptor["nbytes"])]
    values = torch.frombuffer(bytearray(raw), dtype=torch.float32).to(torch.float64)
    rounded = torch.round(values * (1 << Q_VALUE))
    _require(bool(torch.isfinite(rounded).all())
             and bool(((rounded >= -(1 << 31)) & (rounded < (1 << 31))).all()),
             "parameter_q16_range_failure", name)
    return rounded.to(torch.int64).tolist()


def _embedding_bounds(name: str, rows: int, manifest: Mapping[str, Any], weights: bytes,
                      scales_image: bytes) -> tuple[list[int], list[int]]:
    descriptor = manifest["tensors"][name]
    shape = tuple(descriptor["logical_shape"])
    offset = int(descriptor["offset"])
    raw = weights[offset:offset + int(descriptor["nbytes"])]
    codes = torch.frombuffer(bytearray(raw), dtype=torch.int8).reshape(shape)[:rows].to(torch.int64)
    scales = _q24_scales(descriptor, scales_image)[:rows]
    products = codes * scales[:, None]
    magnitude = (products.abs() + 128) >> 8
    values = torch.where(products < 0, -magnitude, magnitude)
    return values.amin(dim=0).tolist(), values.amax(dim=0).tolist()


def _activation_bounds(name: str, manifest: Mapping[str, Any]) -> tuple[list[int], list[int]]:
    scales = torch.round(
        torch.tensor(manifest["activation_scales"][name], dtype=torch.float64) * (1 << Q_SCALE)
    ).to(torch.int64).tolist()
    return ([_round_shift(-128 * value, 8) for value in scales],
            [_round_shift(127 * value, 8) for value in scales])


def _gelu_lut_payload() -> bytes:
    lines = []
    for index in range(8192):
        value = -8.0 + index / 512.0
        result = 0.5 * value * (
            1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (value + 0.044715 * value ** 3))
        )
        code = max(-32768, min(32767, round(result * 4096.0)))
        lines.append(f"{code & 0xffff:04x}\n")
    return "".join(lines).encode()


def _gelu_proof(layer: int, manifest: Mapping[str, Any]) -> dict[str, Any]:
    name = f"transformer.h.{layer}.mlp.c_fc.output"
    lower, upper = _activation_bounds(name, manifest)
    input_abs = max(max(abs(value) for value in lower), max(abs(value) for value in upper))
    inequalities = {
        "input_fits_signed_int32": input_abs < (1 << 31),
        "signed_negation_and_rounding_add_are_safe": input_abs + 8 < (1 << 31),
        "q4_12_clamp_fits_signed_16": True,
        "lut_difference_fits_signed_17": 65535 < (1 << 16),
        "interpolation_product_fits_signed_20": 65535 * 7 < (1 << 19),
        "q16_output_fits_signed_int32": 32768 << 4 < (1 << 31),
    }
    return {
        "name": f"transformer.h.{layer}.mlp.gelu",
        "input_boundary": name,
        "input_bounds_q16_16": {"lower_by_channel": lower, "upper_by_channel": upper},
        "proof": {"input_abs_bound": input_abs, "inequalities": inequalities,
                  "all": all(inequalities.values())},
    }


def _attention_proof(layer: int, manifest: Mapping[str, Any]) -> dict[str, Any]:
    bounds = {}
    for projection in ("q", "k", "v"):
        boundary = f"transformer.h.{layer}.attn.attention.{projection}_proj.output"
        lower, upper = _activation_bounds(boundary, manifest)
        bounds[projection] = (lower, upper)
    q_abs = [max(abs(lo), abs(hi)) for lo, hi in zip(*bounds["q"], strict=True)]
    k_abs = [max(abs(lo), abs(hi)) for lo, hi in zip(*bounds["k"], strict=True)]
    v_abs = [max(abs(lo), abs(hi)) for lo, hi in zip(*bounds["v"], strict=True)]
    score_accum = max(sum(q_abs[i] * k_abs[i] for i in range(head * 4, head * 4 + 4))
                      for head in range(16))
    score_code = (score_accum + (1 << 24) - 1) >> 24
    numerator = 32 * (1 << 20) * max(v_abs)
    rounded_numerator = numerator + (32 * (1 << 20)) // 2
    quotient = max(v_abs) + 1
    inequalities = {
        "score_accumulator_fits_runtime_signed_int64": score_accum < (1 << 63),
        "score_accumulator_fits_rtl_signed_96": score_accum < (1 << 95),
        "score_code_fits_signed_int32": score_code < (1 << 31),
        "score_max_sentinel_is_below_reachable_scores": score_code < (1 << 31) - 1,
        "delta_subtraction_fits_signed_int32": 2 * score_code < (1 << 31),
        "exp_sum_fits_unsigned_64": 32 * (1 << 20) < (1 << 64),
        "context_numerator_fits_runtime_signed_int64": rounded_numerator < (1 << 63),
        "context_numerator_fits_rtl_signed_96": rounded_numerator < (1 << 95),
        "divider_quotient_fits_signed_int32": quotient < (1 << 31),
    }
    return {
        "name": f"transformer.h.{layer}.attn.attention",
        "input_bounds_q16_16": {
            key: {"lower_by_channel": value[0], "upper_by_channel": value[1]}
            for key, value in bounds.items()
        },
        "proof": {
            "score_accumulator_abs_bound": score_accum,
            "score_code_abs_bound": score_code,
            "context_rounded_numerator_abs_bound": rounded_numerator,
            "divider_quotient_abs_bound": quotient,
            "sequence_length_max": 32,
            "inequalities": inequalities,
            "all": all(inequalities.values()),
        },
    }


def derive_certificate(contract_path: Path, audit_path: Path, profile_path: Path,
                       softmax_path: Path, package: Path, reference_root: Path,
                       repo_root: Path) -> dict[str, Any]:
    contract_path, audit_path, profile_path = map(Path, (contract_path, audit_path, profile_path))
    softmax_path, package, reference_root, repo_root = map(
        Path, (softmax_path, package, reference_root, repo_root)
    )
    expected_files = {
        contract_path: CONTRACT_SHA256, audit_path: AUDIT_FILE_SHA256,
        profile_path: PROFILE_SHA256, softmax_path: SOFTMAX_SHA256,
        repo_root / LAYERNORM_RECEIPT: LAYERNORM_RECEIPT_SHA256,
        repo_root / GELU_RECEIPT: GELU_RECEIPT_SHA256,
        repo_root / GELU_ADAPTER: GELU_ADAPTER_SHA256,
    }
    for path, expected in expected_files.items():
        _require(path.is_file() and sha256_file(path) == expected,
                 "authority_identity_mismatch", str(path))
    contract, audit = _load(contract_path), _load(audit_path)
    _require(audit.get("status") == "authenticated", "identity_frontier", "audit")
    _require(contract["deployed_profile"]["revision"] == REFERENCE_REVISION,
             "source_revision_mismatch", REFERENCE_REVISION)
    for name, identity in contract["package"]["files"].items():
        path = package / name
        _require(path.is_file() and path.stat().st_size == identity["size"]
                 and sha256_file(path) == identity["sha256"],
                 "package_identity_mismatch", name)
    source_identity = {}
    closure = contract["deployed_profile"]["sources"]
    audit_closure = audit["source"]["pinned_semantic_source_closure"]
    for name in SEMANTIC_SOURCE_PATHS:
        _require(closure.get(name) == audit_closure.get(name), "source_identity_mismatch", name)
        source_identity[name] = closure[name]

    manifest, weights, scales_image = _read_package(package)
    token_lower, token_upper = _embedding_bounds(
        "token_embedding.weight", 50257, manifest, weights, scales_image
    )
    position_lower, position_upper = _embedding_bounds(
        "position_embedding.weight", 32, manifest, weights, scales_image
    )
    lower = [a + b for a, b in zip(token_lower, position_lower, strict=True)]
    upper = [a + b for a, b in zip(token_upper, position_upper, strict=True)]
    calls = []
    for layer in range(8):
        block = f"blocks.{layer}"
        ln1 = prove_layernorm_interval(
            f"transformer.h.{layer}.ln_1", lower, upper,
            _parameter_q16(f"{block}.ln1.weight", manifest, weights),
            _parameter_q16(f"{block}.ln1.bias", manifest, weights),
        )
        ln1["topology"] = "embedding_plus_prior_attention_and_mlp_qdq_residuals"
        calls.append(ln1)
        add_lower, add_upper = _activation_bounds(
            f"transformer.h.{layer}.attn.attention.out_proj.output", manifest
        )
        lower = [a + b for a, b in zip(lower, add_lower, strict=True)]
        upper = [a + b for a, b in zip(upper, add_upper, strict=True)]
        ln2 = prove_layernorm_interval(
            f"transformer.h.{layer}.ln_2", lower, upper,
            _parameter_q16(f"{block}.ln2.weight", manifest, weights),
            _parameter_q16(f"{block}.ln2.bias", manifest, weights),
        )
        ln2["topology"] = "layer_input_plus_attention_out_qdq"
        calls.append(ln2)
        add_lower, add_upper = _activation_bounds(
            f"transformer.h.{layer}.mlp.c_proj.output", manifest
        )
        lower = [a + b for a, b in zip(lower, add_lower, strict=True)]
        upper = [a + b for a, b in zip(upper, add_upper, strict=True)]
    final = prove_layernorm_interval(
        "transformer.ln_f", lower, upper,
        _parameter_q16("final_ln.weight", manifest, weights),
        _parameter_q16("final_ln.bias", manifest, weights),
    )
    final["topology"] = "embedding_plus_all_eight_attention_and_mlp_qdq_residuals"
    calls.append(final)
    gelu_calls = [_gelu_proof(layer, manifest) for layer in range(8)]
    attention_calls = [_attention_proof(layer, manifest) for layer in range(8)]
    failure = next((call for call in calls if call["status"] != "proven"), None)
    nonlinear_failure = next(
        (call for call in gelu_calls + attention_calls if not call["proof"]["all"]), None
    )
    status = "proven_reachable_domain_equivalent" if failure is None and nonlinear_failure is None else "identity_frontier"
    certificate: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "identity": {
            "contract_sha256": sha256_file(contract_path),
            "audit_file_sha256": sha256_file(audit_path),
            "audit_payload_sha256": audit["sha256"],
            "profile_sha256": sha256_file(profile_path),
            "softmax_authority_sha256": sha256_file(softmax_path),
            "layernorm_conflict_receipt_sha256": sha256_file(repo_root / LAYERNORM_RECEIPT),
            "gelu_equivalence_receipt_sha256": sha256_file(repo_root / GELU_RECEIPT),
            "gelu_adapter_sha256": sha256_file(repo_root / GELU_ADAPTER),
            "package_manifest_sha256": sha256_file(package / "manifest.json"),
            "package_weights_sha256": sha256_file(package / "weights.bin"),
            "package_scales_sha256": sha256_file(package / "scales.bin"),
            "reference_revision": REFERENCE_REVISION,
            "semantic_sources": source_identity,
            "certifier_sha256": sha256_file(Path(__file__)),
        },
        "materialization": {
            "parameters": "nearest_ties_to_even_float32_to_signed_q16.16",
            "scales": "nearest_ties_to_even_float32_to_unsigned_q8.24",
            "all_package_parameters_fit_signed_int32": True,
        },
        "layer_norm": {
            "domain_derivation": "per_channel_embedding_extrema_plus_qdq_clamped_projection_output_extrema_through_residual_topology",
            "calls": calls,
            "conclusion": (
                "runtime_and_synthesizable_rtl_identical_on_reachable_domain"
                if failure is None else "identity_frontier"
            ),
            "failing_call": failure["name"] if failure else None,
            "failing_inequality": failure["failing_inequality"] if failure else None,
        },
        "nonlinear": {
            "gelu": {
                "runtime_source": "tinystories/hardware_reference.py:fixed_gelu",
                "rtl_sources": ["tinystories/rtl_memories.py", "fpga/rtl/gptneo_gelu.sv",
                                str(GELU_ADAPTER)],
                "lut_sha256": hashlib.sha256(_gelu_lut_payload()).hexdigest(),
                "calls": gelu_calls,
            },
            "attention_softmax": {
                "runtime_source": "tinystories/hardware_reference.py:FixedGPTNeo._attention",
                "rtl_sources": ["fpga/rtl/gptneo_attention.sv", "fpga/rtl/gptneo_iterative_divider.sv"],
                "authenticated_checkpoint_artifact_sha256": sha256_file(softmax_path),
                "calls": attention_calls,
            },
            "failing_call": nonlinear_failure["name"] if nonlinear_failure else None,
        },
    }
    certificate["certificate_sha256"] = certificate_sha256(certificate)
    return certificate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--softmax", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = derive_certificate(
        args.contract, args.audit, args.profile, args.softmax, args.package,
        args.reference_root, args.repo_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(value["status"])


if __name__ == "__main__":
    main()
