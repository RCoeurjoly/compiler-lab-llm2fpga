#!/usr/bin/env python3
from __future__ import annotations

"""Audit whether the kev-gpt TinyStories package defines an exact compiler input."""

import argparse
import hashlib
import json
import math
import struct
import subprocess
import sys
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
    "tinystories/write_rtl_fixture.py",
    "fpga/rtl/gptneo_resident_gemv.sv",
    "fpga/rtl/gptneo_iterative_divider.sv",
    "host/kevin_jtag_cli.py",
)
FROZEN_PROMPT_IDS = [7454, 2402, 257, 640]
FROZEN_EXPECTED_TOKENS = [
    11, 612, 373, 257, 1310, 2576, 3706, 20037,
    13, 1375, 6151, 284, 711, 2354, 287, 262,
]


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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_finite_adapter_input(value: Any) -> None:
    """Reject non-finite values before they can enter the integer datapath."""

    if isinstance(value, bool):
        raise ValueError("adapter input must be integer token IDs, not booleans")
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("adapter input contains a non-finite value")
        raise ValueError("adapter input must be integer token IDs")
    if isinstance(value, (list, tuple)):
        for item in value:
            validate_finite_adapter_input(item)
        return
    raise ValueError("adapter input must be integer token IDs")


def _validate_finite_package_values(package_path: Path, manifest: dict[str, Any]) -> None:
    """The fixed profile has no NaN/Inf representation after materialization."""

    for file_name in ("scales.bin",):
        payload = (package_path / file_name).read_bytes()
        _require(len(payload) % 4 == 0, f"{file_name} is not float32-aligned")
        for (value,) in struct.iter_unpack("<f", payload):
            _require(math.isfinite(value), f"package {file_name} contains a non-finite value")
    image = (package_path / "weights.bin").read_bytes()
    tensors = manifest.get("tensors")
    _require(isinstance(tensors, dict), "manifest tensor table is missing")
    for name, descriptor in tensors.items():
        if not isinstance(descriptor, dict) or descriptor.get("format") != "float32":
            continue
        offset = descriptor.get("offset")
        nbytes = descriptor.get("nbytes")
        _require(isinstance(offset, int) and isinstance(nbytes, int) and nbytes % 4 == 0,
                 f"manifest float32 tensor is malformed: {name}")
        _require(0 <= offset <= len(image) and offset + nbytes <= len(image),
                 f"manifest float32 tensor is out of range: {name}")
        for (value,) in struct.iter_unpack("<f", image[offset:offset + nbytes]):
            _require(math.isfinite(value), f"package tensor contains a non-finite value: {name}")


def _run_fixed_reference(kev_root: Path, package_path: Path) -> list[int]:
    """Run the content-authenticated deployed fixed-point reference once."""

    program = """\
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tinystories.hardware_reference import FixedGPTNeo
print(json.dumps(FixedGPTNeo(Path(sys.argv[2])).generate([7454, 2402, 257, 640], 16)))
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(kev_root), str(package_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    tokens = json.loads(result.stdout)
    _require(
        isinstance(tokens, list)
        and all(isinstance(token, int) and not isinstance(token, bool) for token in tokens),
        "fixed reference returned malformed tokens",
    )
    return tokens


def _validate_deployed_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the accepted-spec selection without reinterpreting old receipts."""

    model = contract.get("model")
    package = contract.get("package")
    tokenizer = contract.get("tokenizer")
    quantization = contract.get("quantization")
    fixed_point = contract.get("fixed_point")
    reference = contract.get("reference")
    deployed = contract.get("deployed_profile")
    selection_authority = contract.get("selection_authority")
    _require(isinstance(model, dict), "contract model identity is missing")
    _require(isinstance(package, dict) and isinstance(package.get("files"), dict),
             "contract complete package identity is missing")
    _require(isinstance(tokenizer, dict), "contract tokenizer identity is missing")
    _require(isinstance(quantization, dict), "contract quantization profile is missing")
    _require(isinstance(fixed_point, dict), "contract fixed-point profile is missing")
    _require(isinstance(reference, dict), "contract reference fixture is missing")
    _require(isinstance(deployed, dict), "contract deployed profile is missing")
    _require(isinstance(selection_authority, dict), "contract selection authority is missing")
    selection_path = selection_authority.get("path")
    _require(isinstance(selection_path, str)
             and selection_authority.get("sha256") == _sha256(ROOT / selection_path),
             "accepted-spec selection authority mismatch")
    _require(model.get("source_revision") == "ac533fb8b4f69c71894bf96badfe11e6294d9fcf",
             "contract model revision differs from the accepted spec")
    _require(tokenizer.get("sha256") == package["files"].get("tokenizer.json", {}).get("sha256"),
             "contract tokenizer hash is not bound to the complete package")
    _require(quantization == {
        "weights": "symmetric per-output INT8",
        "activations": "symmetric per-channel INT8",
        "activation_boundary_count": 97,
        "activation_vector_widths": [64, 256],
        "scale_format": "little-endian float32",
    }, "contract quantization profile differs from the deployed package")
    _require(fixed_point == {
        "value_format": "signed Q16.16",
        "scale_format": "unsigned Q8.24",
        "gemv_accumulator": "signed 64-bit serial accumulator",
    }, "contract fixed-point profile differs from the accepted spec")
    _require(reference.get("prompt_tokens") == FROZEN_PROMPT_IDS
             and reference.get("tokens") == FROZEN_EXPECTED_TOKENS
             and reference.get("generation") == "greedy top-1",
             "contract frozen generation fixture differs from the accepted spec")
    _require(deployed.get("name") == "fixed_hardware_reference"
             and deployed.get("input_domain") == "finite_integer_or_fixed_point_only"
             and deployed.get("nonfinite_policy") == "reject_nonfinite_adapter_input",
             "contract deployed profile or non-finite policy is not fail closed")
    sources = deployed.get("sources")
    _require(isinstance(sources, dict) and set(sources) == set(REFERENCE_SOURCES),
             "contract deployed source set is incomplete")
    return deployed


def audit_exact_input(
    contract_path: Path, package_path: Path, kev_root: Path
) -> dict[str, Any]:
    contract = _load_json(contract_path)
    manifest = _load_json(package_path / "manifest.json")
    receipt = _load_json(package_path / "receipt.json")
    qdq = _load_json(QDQ_RECEIPT)
    implementation = _load_json(IMPLEMENTATION_PROFILE)
    fixed_profile = _load_json(FIXED_PROFILE)
    deployed = _validate_deployed_contract(contract)
    semantic_authorities = contract.get("semantic_authorities")
    _require(isinstance(semantic_authorities, dict), "contract semantic authorities are missing")
    expected_receipts = {
        "qdq": QDQ_RECEIPT,
        "implementation_profile": IMPLEMENTATION_PROFILE,
        "fixed_profile": FIXED_PROFILE,
    }
    for name, path in expected_receipts.items():
        authority = semantic_authorities.get(name)
        _require(isinstance(authority, dict)
                 and authority.get("path") == str(path.relative_to(ROOT))
                 and authority.get("sha256") == _sha256(path),
                 f"semantic receipt identity mismatch: {name}")

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
    if package_contract.get("files") != package_files:
        raise ValueError("contract complete package identity mismatch")

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
    _validate_finite_package_values(package_path, manifest)
    validate_finite_adapter_input(FROZEN_PROMPT_IDS)

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
    source_files = {
        name: _sha256(kev_root / name) for name in REFERENCE_SOURCES
    }
    if source_files != deployed["sources"]:
        raise ValueError("deployed reference-source identity mismatch")
    relevant_status = _git(kev_root, "status", "--short", "--", *REFERENCE_SOURCES)
    if relevant_status:
        raise ValueError("deployed reference sources have uncommitted changes")
    if _git(kev_root, "rev-parse", "HEAD") != deployed.get("revision"):
        raise ValueError("deployed reference revision mismatch")
    if fixed_profile.get("profile") != deployed["name"]:
        raise ValueError("fixed hardware profile selection mismatch")
    if fixed_profile.get("semantics", {}).get("execution_domain") != "integers_only_after_materialization":
        raise ValueError("fixed hardware profile is not an integer/fixed-point domain")
    if fixed_profile.get("semantics", {}).get("accumulation", {}).get("synthesizable_rtl", {}).get("logical_width_bits") != 64:
        raise ValueError("fixed hardware profile does not use signed 64-bit GEMV accumulation")
    generated_tokens = _run_fixed_reference(kev_root, package_path)
    if generated_tokens != FROZEN_EXPECTED_TOKENS:
        raise ValueError("deployed fixed reference token fixture mismatch")
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
        "model": contract["model"],
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
        "tokenizer": contract["tokenizer"],
        "quantization": contract["quantization"],
        "fixed_point": contract["fixed_point"],
        "source": source,
        "semantic_receipts": {
            "qdq": {"path": str(QDQ_RECEIPT.relative_to(ROOT)), "status": qdq.get("status"), "sha256": _sha256(QDQ_RECEIPT), "contract_sha256": semantic_authorities["qdq"]["sha256"]},
            "implementation_profile": {"path": str(IMPLEMENTATION_PROFILE.relative_to(ROOT)), "status": implementation.get("status"), "sha256": _sha256(IMPLEMENTATION_PROFILE), "contract_sha256": semantic_authorities["implementation_profile"]["sha256"]},
            "fixed_profile": {"path": str(FIXED_PROFILE.relative_to(ROOT)), "status": fixed_profile.get("status"), "sha256": _sha256(FIXED_PROFILE), "contract_sha256": semantic_authorities["fixed_profile"]["sha256"]},
        },
        "implementation_profile": {
            "name": deployed["name"],
            "selection": "accepted_spec_deployed_reference_and_synthesizable_rtl",
            "semantics_source": str(FIXED_PROFILE.relative_to(ROOT)),
            "semantics_sha256": _sha256(FIXED_PROFILE),
            "historical_selector_status": implementation.get("status"),
        },
        "nonfinite_policy": deployed["nonfinite_policy"],
        "reference_fixture": {
            "prompt_ids": FROZEN_PROMPT_IDS,
            "expected_tokens": FROZEN_EXPECTED_TOKENS,
            "fixed_reference_tokens": generated_tokens,
        },
        "observability_limitations": [{
            "code": "board_checkpoint_trace_unavailable",
            "classification": "observability_limitation_not_identity_conflict",
            "reason": "No internal board checkpoint trace is claimed; package/source identity and the frozen deployed token fixture are authenticated independently.",
        }],
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
