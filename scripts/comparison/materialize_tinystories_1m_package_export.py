#!/usr/bin/env python3
"""Materialize the authenticated TinyStories-1M GPT-Neo export and receipts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories import model_adapter_reference_package as adapter  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def materialize(contract: Path, package: Path, model_path: Path, out_dir: Path) -> None:
    # load_authenticated_package invokes the frozen verifier before any package
    # parsing or output creation.
    bundle = adapter.load_authenticated_package(contract, package, model_path)
    exported = adapter.export_bundle_program(bundle)
    trace = adapter.build_numeric_trace_gate(bundle)
    if trace["status"] != "matched":
        raise adapter.PackageAdapterError(
            "numeric_trace_mismatch", f"first mismatch: {trace['first_mismatch']}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    export_path = out_dir / "exported.pt2"
    trace_path = out_dir / "numeric-trace.json"
    torch.export.save(exported, export_path)
    _write_json(trace_path, trace)

    receipt = copy.deepcopy(bundle.receipt)
    receipt["artifacts"] = {
        "exported_program": {"path": "exported.pt2", "sha256": _sha256(export_path)},
        "numeric_trace": {"path": "numeric-trace.json", "sha256": _sha256(trace_path)},
    }
    receipt["receipt_sha256"] = adapter.receipt_sha256(receipt)
    _write_json(out_dir / "adapter-receipt.json", receipt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    materialize(args.contract, args.package, args.model_path, args.out_dir)


if __name__ == "__main__":
    main()
