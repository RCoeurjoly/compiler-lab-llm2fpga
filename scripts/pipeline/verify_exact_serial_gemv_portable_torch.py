#!/usr/bin/env python3
"""Portable successor provenance for the exact serial-GEMV Torch stage.

Unlike the historical Task 2 receipt, this receipt deliberately contains no
absolute Nix output paths.  The caller supplies artifacts and this verifier
authenticates them by content against a pure source identity.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


MODEL = "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor"
SOURCE_FILES = (
    "flake.nix", "nix/models.nix", "nix/pipeline.nix",
    "scripts/compile-pytorch.py", "TinyStories/model_adapter_exact_serial_gemv_successor.py",
    "TinyStories/serial_gemv_boundary.py", "tools/torch-mlir-passes/LegalizeExactSerialGemv.cpp",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def content(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing stage artifact: {path}")
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def _task1(root: Path) -> dict:
    path = root / "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py"
    spec = importlib.util.spec_from_file_location("portable_task1", path)
    if spec is None or spec.loader is None:
        raise ValueError("Task 1 authority verifier unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify_successor_authority(root)


def source_identity(root: Path) -> dict[str, object]:
    return {"kind": "pure_flake_source", "files": {name: content(root / name) for name in SOURCE_FILES}}


def build(root: Path, exported_dir: Path, torch_output: Path) -> dict:
    exported_dir, torch_output = exported_dir.resolve(), torch_output.resolve()
    output = torch_output.read_text(encoding="utf-8")
    raw = output.count('torch.operator "torch.llm2fpga.serial_gemv"')
    legalized = output.count('"llm2fpga.serial_gemv"')
    if raw != 0 or legalized != 49:
        raise ValueError("portable Torch output does not prove 49 exact legalizations")
    value = {
        "schema": "tinystories-1m-exact-serial-gemv-portable-torch-v1",
        "model": MODEL,
        "authority": _task1(root),
        "source_identity": source_identity(root),
        "input": {
            "exported_program": content(exported_dir / "exported.pt2"),
            "materializer_manifest": content(exported_dir / "manifest.json"),
            "successor_export_manifest": content(exported_dir / "exact-serial-gemv-successor-provenance.json"),
        },
        "legalizer": {"raw_serial_gemv_operator_count": raw, "legalized_serial_gemv_operator_count": legalized},
        "output": content(torch_output),
    }
    value["receipt_sha256"] = canonical(value)
    return value


def verify(value: dict, root: Path, exported_dir: Path, torch_output: Path) -> None:
    if value.get("schema") != "tinystories-1m-exact-serial-gemv-portable-torch-v1" or value.get("model") != MODEL:
        raise ValueError("portable Torch receipt identity mismatch")
    payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("receipt_sha256") != canonical(payload):
        raise ValueError("portable Torch receipt self-hash mismatch")
    if value.get("authority") != _task1(root):
        raise ValueError("portable Torch Task 1 authority mismatch")
    if value.get("source_identity") != source_identity(root):
        raise ValueError("portable Torch pure source identity mismatch")
    expected = build(root, exported_dir, torch_output)
    for key in ("input", "legalizer", "output"):
        if value.get(key) != expected.get(key):
            raise ValueError(f"portable Torch {key} binding mismatch")
    if "/nix/store/" in json.dumps(value, sort_keys=True):
        raise ValueError("portable Torch receipt contains an absolute Nix output path")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--exported-dir", type=Path, required=True)
    parser.add_argument("--torch-output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "write":
        value = build(args.root.resolve(), args.exported_dir, args.torch_output)
        args.receipt.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    value = json.loads(args.receipt.read_text(encoding="utf-8"))
    verify(value, args.root.resolve(), args.exported_dir, args.torch_output)
    print(json.dumps({"status": "verified", "receipt_sha256": value["receipt_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
