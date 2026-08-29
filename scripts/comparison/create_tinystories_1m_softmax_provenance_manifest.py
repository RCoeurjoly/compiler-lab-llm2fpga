#!/usr/bin/env python3
"""Validate and seal pre-lowering TinyStories attention provenance.

The exported graph is the last representation in which semantic roles such as
score, row maximum, and causal output are available.  This tool deliberately
does not infer those roles from lowered text: callers provide the identities
from the package-aware exporter, and this script authenticates their binding
to the frozen contract/package and to the exact lowering-stage files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
PACKAGE = {
    "manifest_sha256": "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35",
    "weights_sha256": "caa140a70f824334d626e20819effabb3a56c28f35cc5c84e6f5f174b3f6bf4e",
    "scales_sha256": "a81faadf9ab21a525a8a20870f2fa97572c66bbf6b88c5cbe2a29cd253355155",
    "calibration_ids_sha256": "2537125a6edea656c5f6b8fe537b4cec7f2a3b2f633f5ee36297135e705bb075",
}
ROLES = ("score", "row_max", "delta", "exp", "sum", "normalization", "causal", "output")


class ManifestError(ValueError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise ManifestError(f"stage_missing:{path}:{error}") from error


def extract_pre_lowering_identities(source: str, source_path: str) -> dict[str, Any]:
    """Extract only the explicit Torch-MLIR softmax SSA identities.

    This is intentionally narrow and fail-closed.  It recognizes the actual
    package-aware graph's one tensor-valued attention chain and expands its
    eight head lanes as views of those exact SSA results; it does not guess
    identities from lowered alloc numbers or operation proximity.
    """
    import re

    def result(op: str, pattern: str) -> str:
        match = re.search(pattern, source, re.MULTILINE)
        if not match:
            raise ManifestError(f"pre_lowering_role_missing:{op}")
        return match.group(1)

    score = result("score", r"^(\s*%\w+)\s*=\s*torch\.aten\.add\.Tensor\s+%\w+,\s*%\w+.*->\s*!torch\.vtensor<\[1,16,4,4\],f32>")
    row_max = result("row_max", r"^(\s*%\w+),\s*%\w+\s*=\s*torch\.aten\.max\.dim\s+%\w+.*->\s*!torch\.vtensor<\[1,16,4,1\],f32>")
    delta = result("delta", r"^(\s*%\w+)\s*=\s*torch\.aten\.sub\.Tensor\s+%\w+,\s*%\w+.*->\s*!torch\.vtensor<\[1,16,4,4\],f32>")
    exp = result("exp", r"^(\s*%\w+)\s*=\s*torch\.aten\.exp\s+%\w+.*->\s*!torch\.vtensor<\[1,16,4,4\],f32>")
    summation = result("sum", r"^(\s*%\w+)\s*=\s*torch\.aten\.sum\.dim_IntList\s+%\w+.*->\s*!torch\.vtensor<\[1,16,4,1\],f32>")
    normalization = result("normalization", r"^(\s*%\w+)\s*=\s*torch\.aten\.div\.Tensor\s+%\w+,\s*%\w+.*->\s*!torch\.vtensor<\[1,16,4,4\],f32>")
    causal = result("causal", r"^(\s*%\w+)\s*=\s*torch\.aten\.where\.self\s+%\w+,\s*%\w+,\s*%\w+.*->\s*!torch\.vtensor<\[1,16,4,4\],f32>")
    output = normalization
    identities = {"score": score.strip(), "row_max": row_max.strip(), "delta": delta.strip(), "exp": exp.strip(), "sum": summation.strip(), "normalization": normalization.strip(), "causal": causal.strip(), "output": output.strip()}
    return {"kind": "torch-mlir-ssa", "path": source_path, "sha256": hashlib.sha256(source.encode()).hexdigest(), "identities": identities}


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise ManifestError(f"{code}:{detail}")


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"invalid_json:{path}:{error}") from error
    _require(isinstance(value, dict), "invalid_json", "manifest input must be an object")
    return value


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an unsigned manifest payload and return its canonical copy."""
    _require(payload.get("schema") == "tinystories-1m-softmax-provenance-v1", "schema", str(payload.get("schema")))
    _require(payload.get("model") == "TinyStories-1M", "model", str(payload.get("model")))
    _require(payload.get("contract_sha256") == CONTRACT_SHA256, "contract_identity", "frozen contract")
    _require(payload.get("package") == PACKAGE, "package_identity", "frozen package")
    source = payload.get("pre_lowering_source")
    _require(isinstance(source, dict), "source", "pre_lowering_source")
    for key in ("kind", "path", "sha256"):
        _require(isinstance(source.get(key), str) and source[key], "source", key)
    _require(len(source["sha256"]) == 64, "source", "sha256 length")
    stages = payload.get("lowering_stages")
    _require(isinstance(stages, dict), "stages", "lowering_stages")
    required_stages = ("torch_mlir", "linalg", "scf", "flat_scf")
    _require(set(stages) == set(required_stages), "stages", "exact stage set")
    for stage in required_stages:
        value = stages[stage]
        _require(isinstance(value, dict), "stage", stage)
        _require(isinstance(value.get("path"), str) and value["path"], "stage", f"{stage}.path")
        _require(isinstance(value.get("sha256"), str) and len(value["sha256"]) == 64, "stage", f"{stage}.sha256")
        _require(isinstance(value.get("bytes"), int) and value["bytes"] > 0, "stage", f"{stage}.bytes")
    heads = payload.get("heads")
    _require(isinstance(heads, list) and len(heads) == 8, "heads", "exactly eight heads")
    seen: set[str] = set()
    for expected, head in enumerate(heads):
        _require(isinstance(head, dict), "head", str(expected))
        _require(head.get("head") == expected, "head", f"ordered head {expected}")
        identities = head.get("identities")
        _require(isinstance(identities, dict) and set(identities) == set(ROLES), "head_roles", str(expected))
        for role in ROLES:
            identity = identities[role]
            _require(isinstance(identity, str) and identity, "head_identity", f"{expected}.{role}")
            _require(identity not in seen, "head_identity_duplicate", identity)
            seen.add(identity)
    return payload


def seal(payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(validate_manifest(payload))
    unsigned.pop("sha256", None)
    unsigned["sha256"] = canonical_sha256(unsigned)
    return unsigned


def materialize(input_path: Path, output_path: Path, stage_paths: dict[str, Path] | None = None) -> dict[str, Any]:
    payload = _load(input_path)
    if stage_paths:
        stages = payload.get("lowering_stages")
        _require(isinstance(stages, dict), "stages", "lowering_stages")
        for name, path in stage_paths.items():
            _require(name in stages, "stage", name)
            stages[name] = {**stages[name], "sha256": file_sha256(path), "bytes": path.stat().st_size}
    result = seal(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return result


def load_authenticated(path: Path) -> dict[str, Any]:
    value = _load(path)
    _require(value.get("sha256") == canonical_sha256({k: v for k, v in value.items() if k != "sha256"}), "self_hash", str(path))
    return seal(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, help="Torch-MLIR source used to populate the semantic identities")
    for name in ("torch_mlir", "linalg", "scf", "flat_scf"):
        parser.add_argument(f"--{name.replace('_', '-')}", dest=name, type=Path)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ("torch_mlir", "linalg", "scf", "flat_scf") if getattr(args, name) is not None}
    if args.source is not None:
        value = _load(args.input)
        source = args.source.read_text(encoding="utf-8")
        extracted = extract_pre_lowering_identities(source, str(args.source))
        value["pre_lowering_source"] = {key: extracted[key] for key in ("kind", "path", "sha256")}
        value["heads"] = [
            {"head": head, "identities": {role: f"{extracted['identities'][role]}[head={head}]" for role in ROLES}}
            for head in range(8)
        ]
        args.input.write_text(json.dumps(value), encoding="utf-8")
    result = materialize(args.input, args.output, paths or None)
    print(json.dumps({"status": "authenticated", "sha256": result["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
