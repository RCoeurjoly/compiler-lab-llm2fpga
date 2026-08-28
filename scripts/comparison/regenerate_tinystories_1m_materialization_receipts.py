#!/usr/bin/env python3
"""Regenerate fail-closed receipts for a realized full TinyStories-1M SV input.

The command deliberately records the compiler artifact's *actual* identity.
If it is not exactly the frozen kev-gpt contract, Task 2 emits
``contract_mismatch`` and Task 3 records that same gate without fabricating a
slice, trace, timing, or resource comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR_PATH = ROOT / "scripts/comparison/extract_tinystories_1m_block_slice.py"
COMPARISON_PATH = ROOT / "scripts/comparison/compare_tinystories_1m_slice.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metadata(compiler_sv: Path, *, flake_attribute: str, source_model_id: str, source_revision: str) -> dict[str, Any]:
    return {
        "schema": "tinystories-1m-compiler-artifact-metadata-v1",
        "artifact": {
            "flake_attribute": flake_attribute,
            "source": str(compiler_sv),
            "sha256": sha256(compiler_sv),
            "bytes": compiler_sv.stat().st_size,
        },
        "contract_identity": {
            "model": {
                "name": "TinyStories-1M",
                "source_model_id": source_model_id,
                "source_revision": source_revision,
            },
            "package": {"sha256": None, "manifest_sha256": None},
        },
        "note": "Compiler artifact identity recorded as observed; this is not an assertion of frozen kev-gpt contract equivalence.",
    }


def regenerate(
    compiler_sv: Path,
    contract: Path,
    metadata_out: Path,
    slice_manifest_out: Path,
    comparison_out: Path,
    *,
    flake_attribute: str,
    source_model_id: str,
    source_revision: str,
) -> int:
    if not compiler_sv.is_file():
        raise FileNotFoundError(f"compiler SystemVerilog does not exist: {compiler_sv}")
    write_json(metadata_out, metadata(
        compiler_sv,
        flake_attribute=flake_attribute,
        source_model_id=source_model_id,
        source_revision=source_revision,
    ))
    extractor = load_module("tinystories_1m_extractor", EXTRACTOR_PATH)
    comparison = load_module("tinystories_1m_comparison", COMPARISON_PATH)
    slice_dir = slice_manifest_out.parent / ".tinystories-1m-extracted-slice"
    extract_code = extractor.main([
        "--input", str(compiler_sv),
        "--metadata", str(metadata_out),
        "--contract", str(contract),
        "--slice-dir", str(slice_dir),
        "--out", str(slice_manifest_out),
    ])
    if extract_code != 2:
        raise RuntimeError(f"expected strict extractor exit 2 for non-frozen artifact, got {extract_code}")
    manifest = json.loads(slice_manifest_out.read_text(encoding="utf-8"))
    if manifest.get("status") != "contract_mismatch" or slice_dir.exists():
        raise RuntimeError("realized compiler artifact did not produce the required fail-closed contract_mismatch receipt")
    comparison_code = comparison.main([
        "--contract", str(contract),
        "--slice-manifest", str(slice_manifest_out),
        "--out", str(comparison_out),
    ])
    if comparison_code != 0:
        raise RuntimeError(f"comparison receipt failed with exit {comparison_code}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler-sv", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--metadata-out", type=Path, required=True)
    parser.add_argument("--slice-manifest-out", type=Path, required=True)
    parser.add_argument("--comparison-out", type=Path, required=True)
    parser.add_argument("--flake-attribute", required=True)
    parser.add_argument("--source-model-id", default="roneneldan/TinyStories-1M")
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args(argv)
    return regenerate(
        args.compiler_sv,
        args.contract,
        args.metadata_out,
        args.slice_manifest_out,
        args.comparison_out,
        flake_attribute=args.flake_attribute,
        source_model_id=args.source_model_id,
        source_revision=args.source_revision,
    )


if __name__ == "__main__":
    raise SystemExit(main())
