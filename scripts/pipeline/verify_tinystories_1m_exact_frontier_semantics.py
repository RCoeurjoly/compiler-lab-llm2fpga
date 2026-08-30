#!/usr/bin/env python3
"""Validate the Task 6 signed-si64 shift semantic and identity contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-exact-shift-semantics.json"
DECISION_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid_object:{path}")
    return value


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def shift_output(input_value: dict[str, Any], shift: int) -> dict[str, Any]:
    require(input_value.get("dtype") == "si64", "shift_contract:input_dtype")
    shape = input_value.get("shape")
    values = input_value.get("values")
    require(isinstance(shape, list) and isinstance(values, list), "shift_contract:input_shape_or_values")
    require(len(values) == (shape[0] if len(shape) == 1 and isinstance(shape[0], int) else -1), "shift_contract:input_shape")
    require(isinstance(shift, int) and 0 <= shift <= 62, "shift_contract:shift_range")
    require(all(isinstance(value, int) and -(1 << 63) <= value < (1 << 63) for value in values), "shift_contract:input_range")
    return {"dtype": "si64", "shape": shape, "values": [value >> shift for value in values]}


def verify_contract(fixture_path: Path, decision_path: Path) -> dict[str, Any]:
    fixture = load_object(fixture_path)
    decision = load_object(decision_path)
    fixture_without_hash = dict(fixture)
    fixture_hash = fixture_without_hash.pop("sha256", None)
    require(fixture.get("schema") == "tinystories-1m-exact-shift-semantics-v1", "fixture_schema")
    require(fixture_hash == canonical_sha256(fixture_without_hash), "fixture_self_hash")
    semantic = decision.get("semantic_regression")
    require(isinstance(semantic, dict), "decision_semantic_regression_missing")
    require(semantic.get("fixture_file_sha256") == sha256_file(fixture_path), "decision_fixture_file_hash")
    require(semantic.get("fixture_self_hash") == fixture_hash, "decision_fixture_self_hash")
    valid_cases = fixture.get("valid_cases")
    invalid_cases = fixture.get("invalid_cases")
    require(isinstance(valid_cases, list) and isinstance(invalid_cases, list), "fixture_cases")
    observed: dict[str, list[int]] = {}
    for case in valid_cases:
        require(isinstance(case, dict), "valid_case_object")
        output = shift_output(case["input"], case["shift"])
        require(output == case.get("expected"), f"reference_output_mismatch:{case.get('id')}")
        require(canonical_sha256(output) == case.get("expected_sha256"), f"expected_hash_mismatch:{case.get('id')}")
        observed[str(case["id"])] = output["values"]
    for case in invalid_cases:
        require(isinstance(case, dict), "invalid_case_object")
        shift = case.get("shift")
        expected_status = "rejected_negative_shift" if shift == -1 else "rejected_shift_greater_than_sixty_two"
        expected_diagnostic = "shift_contract:negative_shift" if shift == -1 else "shift_contract:greater_than_sixty_two"
        require(case.get("status") == expected_status, f"invalid_status_contract:{case.get('id')}")
        require(case.get("diagnostic") == expected_diagnostic, f"invalid_diagnostic_contract:{case.get('id')}")
        try:
            shift_output(case["input"], shift)
        except ValueError as error:
            require(str(error) == "shift_contract:shift_range", f"invalid_reference_diagnostic:{case.get('id')}")
        else:
            raise ValueError(f"invalid_shift_accepted:{case.get('id')}")
    return {
        "fixture_file_sha256": sha256_file(fixture_path),
        "fixture_self_hash": fixture_hash,
        "rejected_cases": [str(case["id"]) for case in invalid_cases],
        "shift_one_output": observed["shift_one"],
        "valid_cases": [str(case["id"]) for case in valid_cases],
    }


def verify_lowered_result(result_path: Path, fixture: dict[str, Any]) -> dict[str, object]:
    result = load_object(result_path)
    require(result.get("schema") == "tinystories-1m-exact-shift-lowered-results-v1", "lowered_result_schema")
    records = result.get("cases")
    require(isinstance(records, list), "lowered_result_cases")
    by_id = {record.get("id"): record for record in records if isinstance(record, dict)}
    for case in fixture["valid_cases"]:
        record = by_id.get(case["id"])
        require(isinstance(record, dict), f"lowered_result_missing:{case['id']}")
        require(record.get("status") == "ok", f"lowered_status_mismatch:{case['id']}")
        require(record.get("output") == case["expected"], f"lowered_result_mismatch:{case['id']}")
        require(canonical_sha256(record["output"]) == case["expected_sha256"], f"lowered_output_hash_mismatch:{case['id']}")
    for case in fixture["invalid_cases"]:
        record = by_id.get(case["id"])
        require(isinstance(record, dict), f"lowered_result_missing:{case['id']}")
        require(record.get("status") == case["status"], f"lowered_status_mismatch:{case['id']}")
        require(record.get("diagnostic") == case["diagnostic"], f"lowered_diagnostic_mismatch:{case['id']}")
        require("output" not in record, f"lowered_invalid_output:{case['id']}")
    return {"lowered_result_sha256": sha256_file(result_path), "status": "accepted"}


def verify_registered_stage(stage_artifact: Path, decision: dict[str, Any]) -> dict[str, object]:
    require(stage_artifact.is_file() and stage_artifact.stat().st_size > 0, "registered_stage_artifact_missing")
    identities = decision["identity_hashes"]
    audit_path = ROOT / "artifacts/reference/tinystories-1m-exact-input-audit.json"
    model_path = ROOT / "artifacts/reference/tinystories-1m-exact-package-model.json"
    generation_path = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
    audit = load_object(audit_path)
    model = load_object(model_path)
    generation = load_object(generation_path)
    require(sha256_file(audit_path) == identities["task_1_audit_file_sha256"], "task1_audit_file_hash")
    require(audit.get("sha256") == identities["task_1_audit_payload_sha256"], "task1_audit_payload_hash")
    require(sha256_file(model_path) == identities["task_2_artifact_file_sha256"], "task2_artifact_file_hash")
    require(model.get("artifact_sha256") == identities["task_2_artifact_sha256"], "task2_artifact_hash")
    require(model.get("identity", {}).get("model_receipt_sha256") == identities["task_2_model_receipt_sha256"], "task2_model_receipt_hash")
    require(sha256_file(generation_path) == identities["task_3_generation_file_sha256"], "task3_generation_file_hash")
    require(generation.get("artifact_sha256") == identities["task_3_generation_artifact_sha256"], "task3_generation_artifact_hash")
    require(generation.get("generation", {}).get("result_sha256") == identities["task_3_generation_result_sha256"], "task3_generation_result_hash")
    return {"stage_artifact_sha256": sha256_file(stage_artifact), "status": "accepted"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=FIXTURE_DEFAULT)
    parser.add_argument("--decision", type=Path, default=DECISION_DEFAULT)
    parser.add_argument("--lowered-result", type=Path)
    parser.add_argument("--stage-artifact", type=Path)
    args = parser.parse_args()
    contract = verify_contract(args.fixture, args.decision)
    result: dict[str, object] = {"contract": contract}
    fixture = load_object(args.fixture)
    if args.lowered_result is not None:
        result["lowered_result"] = verify_lowered_result(args.lowered_result, fixture)
    if args.stage_artifact is not None:
        result["registered_stage"] = verify_registered_stage(args.stage_artifact, load_object(args.decision))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
