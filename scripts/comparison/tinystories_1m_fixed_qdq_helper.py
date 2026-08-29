#!/usr/bin/env python3
"""Authenticated fixed Q/DQ primitives for the TinyStories-1M slice."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

CANONICAL_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
CANONICAL_PROFILE_ARTIFACT_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"
CANONICAL_PROFILE_SHA256 = "7d54acda88f1d1a6979fd0ca8a3b0445e20ef127a399e5124a994427565caad0"
CANONICAL_PACKAGE_MANIFEST_SHA256 = "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35"

class FixedQdqHelperError(ValueError): pass

def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def profile_sha256(profile: dict[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in profile.items() if k != "profile_sha256"})

def _validate_ints(values: list[Any], label: str) -> None:
    if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in values):
        raise ValueError(f"{label} must contain integer values")

def _validate_scales(scales: list[Any], n: int) -> None:
    if not isinstance(scales, list) or len(scales) != n or n == 0:
        raise ValueError("values and scales must have same non-zero length")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in scales):
        raise ValueError("scales must be integer")
    if any(v <= 0 for v in scales): raise ValueError("scales must be positive")
    if any(v >= (1 << 24) for v in scales): raise ValueError("scales must fit unsigned 24-bit")

def quantize_q16_to_int8(values: list[int], scales: list[int]) -> list[int]:
    _validate_ints(values, "values"); _validate_scales(scales, len(values))
    out=[]
    for value, scale in zip(values, scales):
        numerator = value << 8
        magnitude = (abs(numerator) + scale // 2) // scale
        code = -magnitude if numerator < 0 else magnitude
        out.append(max(-128, min(127, code)))
    return out

def dequantize_int8_to_q16(values: list[int], scales: list[int]) -> list[int]:
    _validate_ints(values, "values"); _validate_scales(scales, len(values))
    if any(v < -128 or v > 127 for v in values): raise ValueError("values must fit int8")
    out=[]
    for value, scale in zip(values, scales):
        numerator = value * scale
        magnitude = (abs(numerator) + 128) // 256
        out.append(-magnitude if numerator < 0 else magnitude)
    return out

def load_fixed_hardware_profile(path: Path) -> dict[str, Any]:
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != CANONICAL_PROFILE_ARTIFACT_SHA256:
        raise FixedQdqHelperError("profile_artifact_identity_mismatch")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("identity", {}).get("contract_sha256") != CANONICAL_CONTRACT_SHA256:
        raise FixedQdqHelperError("profile_contract_identity_mismatch")
    if profile.get("profile_sha256") != CANONICAL_PROFILE_SHA256 or profile_sha256(profile) != profile.get("profile_sha256"):
        raise FixedQdqHelperError("profile_identity_mismatch")
    return profile

def load_block0_token3_qk_fixture(profile_path: Path, softmax_path: Path) -> dict[str, Any]:
    profile = load_fixed_hardware_profile(profile_path)
    artifact = json.loads(Path(softmax_path).read_text(encoding="utf-8"))
    if artifact.get("sha256") != canonical_sha256({k:v for k,v in artifact.items() if k != "sha256"}):
        raise FixedQdqHelperError("softmax_artifact_identity_mismatch")
    binding = artifact.get("profile_binding", {})
    if binding.get("profile_artifact_sha256") != CANONICAL_PROFILE_ARTIFACT_SHA256 or binding.get("profile_sha256") != CANONICAL_PROFILE_SHA256:
        raise FixedQdqHelperError("softmax_artifact_identity_mismatch")
    identity = artifact.get("identity", {})
    if identity.get("contract_sha256") != CANONICAL_CONTRACT_SHA256:
        raise FixedQdqHelperError("softmax_artifact_identity_mismatch")
    if identity.get("package_manifest_sha256") != CANONICAL_PACKAGE_MANIFEST_SHA256:
        raise FixedQdqHelperError("softmax_artifact_identity_mismatch")
    rows = artifact.get("softmax_rows")
    if not isinstance(rows, list) or len(rows) != 16: raise FixedQdqHelperError("softmax_rows_missing")
    return {"slice": artifact["slice"], "q_shape": [16,4], "k_shape": [16,4],
            "identity": {"package_manifest_sha256": identity["package_manifest_sha256"], "contract_sha256": identity["contract_sha256"]},
            "profile_binding": binding, "q_q16_16": [r["query_q16_16"] for r in rows],
            "k_q16_16": [r["key_rows_q16_16"][-1] for r in rows], "profile_status": profile.get("status")}
