#!/usr/bin/env python3
from __future__ import annotations

"""Audit whether the kev-gpt TinyStories package defines an exact compiler input."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QDQ_RECEIPT = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
IMPLEMENTATION_PROFILE = ROOT / "artifacts/reference/tinystories-1m-implementation-profile.json"
FIXED_PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
REFERENCE_SOURCES = (
    "tinystories/quantize.py",
    "tinystories/build_package.py",
    "tinystories/int_reference.py",
    "tinystories/hardware_reference.py",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(kev_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(kev_root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def audit_exact_input(
    contract_path: Path, package_path: Path, kev_root: Path
) -> dict[str, Any]:
    contract = _load_json(contract_path)
    manifest = _load_json(package_path / "manifest.json")
    receipt = _load_json(package_path / "receipt.json")
    qdq = _load_json(QDQ_RECEIPT)
    implementation = _load_json(IMPLEMENTATION_PROFILE)
    fixed_profile = _load_json(FIXED_PROFILE)

    receipt_files = receipt.get("files")
    if not isinstance(receipt_files, dict):
        raise ValueError("package receipt lacks files")
    package_files: dict[str, dict[str, Any]] = {}
    for name, expected in sorted(receipt_files.items()):
        if not isinstance(expected, dict):
            raise ValueError(f"package receipt entry {name} is malformed")
        path = package_path / name
        actual = {"sha256": _sha256(path), "size": path.stat().st_size}
        if actual != expected:
            raise ValueError(f"package file identity mismatch: {name}")
        package_files[name] = actual

    manifest_hash = _sha256(package_path / "manifest.json")
    if receipt.get("manifest_sha256") != manifest_hash:
        raise ValueError("package manifest receipt mismatch")
    package_contract = contract.get("package")
    if not isinstance(package_contract, dict):
        raise ValueError("contract package identity is missing")
    if package_contract.get("manifest_sha256") != manifest_hash:
        raise ValueError("contract manifest identity mismatch")
    if package_contract.get("sha256") != _sha256(package_path / "weights.bin"):
        raise ValueError("contract weight identity mismatch")

    activation_scales = manifest.get("activation_scales")
    if not isinstance(activation_scales, dict):
        raise ValueError("manifest activation_scales is missing")
    widths: set[int] = set()
    for name, values in sorted(activation_scales.items()):
        if not isinstance(name, str) or not isinstance(values, list) or not values:
            raise ValueError(f"activation scale vector is malformed: {name!r}")
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value > 0
            for value in values
        ):
            raise ValueError(f"activation scale vector is invalid: {name}")
        widths.add(len(values))

    quantization = contract.get("quantization")
    if not isinstance(quantization, dict):
        raise ValueError("contract quantization is missing")
    activation_label = quantization.get("activations")
    activation_granularity = (
        "per_channel" if activation_label == "symmetric per-channel INT8" else "conflicting"
    )

    conflicts: list[dict[str, str]] = []
    if activation_granularity != "per_channel":
        conflicts.append(
            {
                "code": "activation_scale_granularity_conflict",
                "reason": "contract activation label disagrees with 97 package scale vectors",
            }
        )
    if implementation.get("status") != "resolved":
        conflicts.append(
            {
                "code": "implementation_profile_unresolved",
                "reason": "the selected executable implementation profile is not resolved",
            }
        )
    if fixed_profile.get("board_authenticated") is not True:
        conflicts.append(
            {
                "code": "board_checkpoint_trace_unavailable",
                "reason": "the fixed-point profile is not authenticated by a board checkpoint trace",
            }
        )
    incomplete_reasons = qdq.get("incomplete_reasons")
    if isinstance(incomplete_reasons, list) and any(
        "non-finite" in str(reason).lower() for reason in incomplete_reasons
    ):
        conflicts.append(
            {
                "code": "nonfinite_policy_unresolved",
                "reason": "the executable references do not define one portable non-finite policy",
            }
        )

    source_files = {
        name: _sha256(kev_root / name) for name in REFERENCE_SOURCES
    }
    relevant_status = _git(kev_root, "status", "--short", "--", *REFERENCE_SOURCES)
    source = {
        "head_revision": _git(kev_root, "rev-parse", "HEAD"),
        "package_revision": _git(
            kev_root, "log", "-1", "--format=%H", "--", "model_packages/tinystories-1m"
        ),
        "reference_sources": source_files,
        "reference_source_worktree_clean": not bool(relevant_status),
        "reference_source_status": relevant_status.splitlines(),
    }

    result: dict[str, Any] = {
        "schema": "tinystories-1m-exact-input-audit-v1",
        "status": "authenticated" if not conflicts else "identity_frontier",
        "contract": {
            "path": str(contract_path),
            "sha256": _sha256(contract_path),
            "activation_granularity": activation_granularity,
        },
        "package": {
            "path": str(package_path),
            "manifest_sha256": manifest_hash,
            "files": package_files,
        },
        "activation_quantization": {
            "format": manifest.get("activation_format"),
            "granularity": "per_channel",
            "boundary_count": len(activation_scales),
            "vector_widths": sorted(widths),
        },
        "source": source,
        "semantic_receipts": {
            "qdq": {"path": str(QDQ_RECEIPT.relative_to(ROOT)), "status": qdq.get("status"), "sha256": _sha256(QDQ_RECEIPT)},
            "implementation_profile": {"path": str(IMPLEMENTATION_PROFILE.relative_to(ROOT)), "status": implementation.get("status"), "sha256": _sha256(IMPLEMENTATION_PROFILE)},
            "fixed_profile": {"path": str(FIXED_PROFILE.relative_to(ROOT)), "status": fixed_profile.get("status"), "sha256": _sha256(FIXED_PROFILE)},
        },
        "conflicts": conflicts,
        "next_gate": (
            "exact_quantized_pytorch_model"
            if not conflicts
            else "resolve_all_identity_frontier_conflicts"
        ),
    }
    result["sha256"] = _canonical_sha256(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--kev-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_exact_input(args.contract, args.package, args.kev_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
