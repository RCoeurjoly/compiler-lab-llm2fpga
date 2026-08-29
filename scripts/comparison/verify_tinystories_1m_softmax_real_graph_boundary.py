#!/usr/bin/env python3
"""Authenticate and re-run the real-graph TinyStories softmax boundary.

The package-aware compiler stages are intentionally runtime inputs: this
checker refuses to accept a site count or mismatch report unless every input
hash and byte count agrees with the authenticated frontier receipt.  A
fail-closed bridge mismatch is evidence; it is not a lowering success.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-softmax-real-graph-boundary.json"
FRONTIER_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"
BRIDGE_DEFAULT = ROOT / "scripts/comparison/bridge_tinystories_1m_softmax.py"


class BoundaryVerificationError(ValueError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BoundaryVerificationError(f"invalid_json:{path}:{error}") from error
    if not isinstance(value, dict):
        raise BoundaryVerificationError(f"json_not_object:{path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BoundaryVerificationError(message)


def load_bridge(path: Path):
    spec = importlib.util.spec_from_file_location("tinystories_softmax_bridge", path)
    require(spec is not None and spec.loader is not None, f"bridge_import:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_file_stage(report: dict[str, Any], frontier: dict[str, Any], key: str, path: Path) -> None:
    expected = report["stages"][key]
    frontier_expected = frontier["stages"][key]
    require(expected == frontier_expected, f"stage_receipt_mismatch:{key}")
    require(path.is_file(), f"stage_missing:{key}:{path}")
    actual = {"sha256": file_sha256(path), "bytes": path.stat().st_size}
    require(actual == expected, f"stage_identity_mismatch:{key}:{actual}")


def verify(report_path: Path, frontier_path: Path, bridge_path: Path, stage_paths: dict[str, Path]) -> dict[str, Any]:
    report = load_object(report_path)
    frontier = load_object(frontier_path)
    require(report.get("sha256") == canonical_sha256({k: v for k, v in report.items() if k != "sha256"}), "boundary_report_self_hash_mismatch")
    require(frontier.get("sha256") == canonical_sha256({k: v for k, v in frontier.items() if k != "sha256"}), "frontier_report_self_hash_mismatch")
    require(report.get("frontier_report", {}).get("sha256") == frontier.get("sha256"), "frontier_report_hash_mismatch")
    require(report.get("bridge_script_sha256") == file_sha256(bridge_path), "bridge_script_identity_mismatch")
    require(report.get("contract_sha256") == frontier.get("contract_sha256"), "contract_identity_mismatch")
    require(report.get("package") == {
        "manifest_sha256": frontier["package"]["manifest_sha256"],
        "weights_sha256": frontier["package"]["weights_sha256"],
        "scales_sha256": frontier["package"]["scales_sha256"],
        "calibration_ids_sha256": frontier["package"]["calibration_ids_sha256"],
    }, "package_identity_mismatch")
    for key, path in stage_paths.items():
        _assert_file_stage(report, frontier, key, path)

    text = stage_paths["flat_scf"].read_text(encoding="utf-8")
    expected_count = report["attempt"]["expected_exp_sites"]
    actual_count = len(re.findall(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*math\.exp\b", text, re.MULTILINE))
    require(actual_count == expected_count, f"exp_site_count_mismatch:{actual_count}")
    bridge = load_bridge(bridge_path)
    zero_matches = re.findall(r"%(cst_[A-Za-z0-9_]+)\s*=\s*arith\.constant\s+0(?:\.0+)?(?:e[+\-]?0+)?\s*:\s*f32", text, re.I)
    require(len(set(zero_matches)) == 1, f"zero_identity_not_authenticated:{sorted(set(zero_matches))}")
    zero_identity = zero_matches[0]
    try:
        pattern = bridge._pattern_evidence(text, expected_exp_sites=expected_count, zero_identity=zero_identity)
    except bridge.SoftmaxBridgeError as error:
        mismatch = report["attempt"]["first_mismatch"]
        require(isinstance(mismatch, dict), "mismatch_missing_for_rejected_pattern")
        require(error.code == mismatch["code"], "mismatch_code_changed")
        require(str(error).split(": ", 1)[1] == mismatch["message"], "mismatch_message_changed")
    else:
        require(report.get("status") == "accepted", "accepted_status_missing")
        require(report.get("bridge_status") == "real_graph_pattern_accepted", "accepted_bridge_status_missing")
        require(report.get("attempt", {}).get("first_mismatch") is None, "accepted_mismatch_present")
        require(report.get("claims", {}).get("authenticated_pattern_matched") is True, "accepted_pattern_claim_missing")
        accepted = report.get("attempt", {}).get("accepted_evidence", {})
        require(pattern.get("exp_site_count") == accepted.get("exp_site_count"), "accepted_site_count_mismatch")
        require(pattern.get("binding_mode") == accepted.get("binding_mode"), "accepted_binding_mode_mismatch")
        return {"status": "verified_accepted", "stage_hashes": report["stages"], "pattern": pattern}

    lines = [line.rstrip("\n") for line in text.splitlines()]
    mismatch = report["attempt"]["first_mismatch"]
    line_no = mismatch["flat_scf_line"]
    require(lines[line_no - 1].strip() == mismatch["context"][1], "mismatch_context_exp_line_changed")
    require(lines[line_no - 2].strip() == mismatch["context"][0], "mismatch_context_load_changed")
    require(lines[line_no].strip() == mismatch["context"][2], "mismatch_context_store_changed")
    sub_line = mismatch["arith_subf_line"]
    require(lines[sub_line - 1].strip() == mismatch["arith_subf"], "mismatch_context_subf_changed")
    return {"status": "verified_fail_closed", "first_mismatch": mismatch, "stage_hashes": report["stages"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--frontier", type=Path, default=FRONTIER_DEFAULT)
    parser.add_argument("--bridge", type=Path, default=BRIDGE_DEFAULT)
    for key in ("torch_mlir", "linalg", "scf", "flat_scf"):
        parser.add_argument(f"--{key.replace('_', '-')}", dest=key, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.report, args.frontier, args.bridge, {key: getattr(args, key) for key in ("torch_mlir", "linalg", "scf", "flat_scf")})
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
