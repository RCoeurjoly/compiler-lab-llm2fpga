#!/usr/bin/env python3
"""Inventory provenance-bound TinyStories-1M one-block compiler evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-one-block-evidence-inventory-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return value


def artifact(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {"path": relative, "sha256": sha256_file(path), "exists": path.is_file()}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


def build_inventory(root: Path) -> dict[str, Any]:
    root = Path(root)
    contract = load_json(root, "artifacts/reference/tinystories-1m-kev-gpt-contract.json")
    profile = load_json(root, "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json")
    slice_lowering = load_json(root, "artifacts/comparison/tinystories-1m-fixed-profile-slice-lowering.json")
    block_receipt = load_json(root, "artifacts/comparison/tinystories-1m-complete-block-comparison-receipt.json")
    slice_comparison = load_json(root, "artifacts/comparison/tinystories-1m-slice-comparison.json")
    full_yosys = load_json(root, "artifacts/full-tinystories-pt2e-w8a8-scout/yosys-slang-structural-utilization.json")
    baseline_memory = load_json(root, "references/task3/tiny-stories-1m-baseline-float-selftest-all-memory-utilization/summary.json")
    checkpoints = profile["software_trace"]["checkpoints"]
    blocking_reasons = block_receipt.get("blocking_reasons", [])
    if not isinstance(blocking_reasons, list) or not blocking_reasons:
        raise ValueError("complete block receipt has no blocking_reasons")

    return {
        "schema": SCHEMA,
        "status": "blocked",
        "first_missing_gate": blocking_reasons[0],
        "compiler_package_identity": {
            "contract_path": "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            "contract_file_sha256": sha256_file(root / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"),
            "contract_sha256": profile["identity"]["contract_sha256"],
            "model": contract["model"],
            "manifest_sha256": contract["package"]["manifest_sha256"],
            "weights_sha256": contract["package"]["sha256"],
            "scales_sha256": contract["package"]["files"]["scales.bin"],
            "calibration_ids_sha256": contract["package"]["files"]["calibration_ids.bin"],
            "package_receipt_sha256": contract["package"]["files"]["receipt.json"],
            "memory_image": contract["memory_image"],
        },
        "trace_checkpoints": {
            "source": artifact(root, "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"),
            "status": slice_lowering["software_trace"]["status"],
            "profile_status": profile["status"],
            "board_authenticated": profile["board_authenticated"],
            "checkpoint_count": slice_lowering["software_trace"]["checkpoint_count"],
            "checkpoint_order": slice_lowering["software_trace"]["checkpoint_order"],
            "trace_sha256": slice_lowering["software_trace"]["sha256"],
            "checkpoint_hashes": {name: checkpoints[name]["sha256"] for name in slice_lowering["software_trace"]["checkpoint_order"]},
        },
        "compiler_graph_handoff": {
            "source": artifact(root, "artifacts/comparison/tinystories-1m-fixed-profile-slice-lowering.json"),
            "status": slice_lowering["status"],
            "alignment_status": slice_lowering["alignment_status"],
            "compiler_artifacts": slice_lowering["compiler_artifacts"],
            "first_unsupported_operation": slice_lowering["first_unsupported_operation"],
            "evidence": slice_lowering["evidence"],
            "task2_metadata": slice_lowering["task2_metadata"],
        },
        "accepted_one_block_metrics": {
            "resources": block_receipt["evidence"]["resources"],
            "timing": block_receipt["evidence"]["timing"],
            "memory": block_receipt["evidence"]["memory"],
            "latency": block_receipt["evidence"]["latency"],
            "throughput": block_receipt["evidence"]["throughput"],
        },
        "rejected_or_non_one_block_artifacts": {
            "compiler_yosys_fixture": {
                "source": artifact(root, "tests/fixtures/tinystories-1m-compiler-yosys.json"),
                "status": "fixture_only_not_provenance_bound",
            },
            "compiler_nextpnr_fixture": {
                "source": artifact(root, "tests/fixtures/tinystories-1m-compiler-nextpnr.rpt"),
                "status": "fixture_only_not_provenance_bound",
            },
            "full_w8a8_yosys_slang_structural": {
                "source": artifact(root, "artifacts/full-tinystories-pt2e-w8a8-scout/yosys-slang-structural-utilization.json"),
                "status": "not_one_block_evidence",
                "reported_status": full_yosys.get("status"),
                "scope": full_yosys.get("scope"),
            },
            "baseline_float_memory_utilization": {
                "source": artifact(root, "references/task3/tiny-stories-1m-baseline-float-selftest-all-memory-utilization/summary.json"),
                "status": "not_compiler_one_block_evidence",
                "reported_utilization": baseline_memory.get("utilization"),
            },
        },
        "slice_comparison_status": {
            "source": artifact(root, "artifacts/comparison/tinystories-1m-slice-comparison.json"),
            "status": slice_comparison.get("status"),
            "resources": slice_comparison.get("resources"),
            "timing": slice_comparison.get("timing"),
        },
        "blocking_reasons": blocking_reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    inventory = build_inventory(args.root)
    text = json.dumps(inventory, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
