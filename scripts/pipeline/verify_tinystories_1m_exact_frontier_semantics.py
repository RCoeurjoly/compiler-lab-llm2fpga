#!/usr/bin/env python3
"""Validate the Task 6 signed-si64 shift semantic and identity contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
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
    decision_without_hash = dict(decision)
    decision_hash = decision_without_hash.pop("sha256", None)
    require(decision_hash == canonical_sha256(decision_without_hash), "decision_self_hash")
    frontier = decision.get("frontier")
    require(isinstance(frontier, dict), "decision_frontier")
    frontier_path = ROOT / str(frontier.get("frontier_receipt_path"))
    reproducer_path = ROOT / str(frontier.get("minimal_reproducer_path"))
    frontier_receipt = load_object(frontier_path)
    require(sha256_file(frontier_path) == frontier.get("frontier_hash"), "task5_frontier_file_hash")
    require(frontier_receipt.get("sha256") == frontier.get("frontier_receipt_self_hash"), "task5_frontier_self_hash")
    require(sha256_file(reproducer_path) == frontier.get("minimal_reproducer_sha256"), "task5_reproducer_hash")
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
        "decision_sha256": decision_hash,
        "fixture_file_sha256": sha256_file(fixture_path),
        "fixture_self_hash": fixture_hash,
        "rejected_cases": [str(case["id"]) for case in invalid_cases],
        "shift_one_output": observed["shift_one"],
        "valid_cases": [str(case["id"]) for case in valid_cases],
    }


def _expected_case_ids(fixture: dict[str, Any]) -> set[str]:
    cases = fixture["valid_cases"] + fixture["invalid_cases"]
    ids = [case.get("id") for case in cases]
    require(all(isinstance(case_id, str) for case_id in ids), "fixture_case_id")
    require(len(ids) == len(set(ids)), "fixture_case_duplicate")
    return set(ids)


def _verify_case_records(records: object, fixture: dict[str, Any]) -> None:
    require(isinstance(records, list), "probe_cases")
    require(all(isinstance(record, dict) for record in records), "probe_case_object")
    ids = [record.get("id") for record in records]
    require(all(isinstance(case_id, str) for case_id in ids), "probe_case_id")
    require(len(ids) == len(set(ids)), "probe_case_duplicate")
    require(set(ids) == _expected_case_ids(fixture), "probe_case_set")
    by_id = {record["id"]: record for record in records}
    for case in fixture["valid_cases"]:
        record = by_id[case["id"]]
        require(record.get("status") == "ok", f"lowered_status_mismatch:{case['id']}")
        require(record.get("output") == case["expected"], f"lowered_result_mismatch:{case['id']}")
        require(canonical_sha256(record["output"]) == case["expected_sha256"], f"lowered_output_hash_mismatch:{case['id']}")
    for case in fixture["invalid_cases"]:
        record = by_id[case["id"]]
        require(record.get("status") == case["status"], f"lowered_status_mismatch:{case['id']}")
        require(record.get("diagnostic") == case["diagnostic"], f"lowered_diagnostic_mismatch:{case['id']}")
        require("output" not in record, f"lowered_invalid_output:{case['id']}")


def _resolve_derivation_from_store(artifact: Path) -> Path:
    result = subprocess.run(
        ["nix", "path-info", "--derivation", str(artifact)],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def verify_probe_report(
    report_path: Path,
    fixture_path: Path,
    decision_path: Path,
    *,
    derivation_resolver: Any = _resolve_derivation_from_store,
) -> dict[str, object]:
    verify_contract(fixture_path, decision_path)
    fixture = load_object(fixture_path)
    decision = load_object(decision_path)
    semantic = decision["semantic_regression"]
    report = load_object(report_path)
    report_without_hash = dict(report)
    report_hash = report_without_hash.pop("sha256", None)
    require(report.get("schema") == "tinystories-1m-exact-shift-semantic-probe-v1", "probe_schema")
    require(report_hash == canonical_sha256(report_without_hash), "probe_self_hash")
    require(report.get("decision_sha256") == decision["sha256"], "probe_decision_hash")
    require(report.get("fixture_file_sha256") == semantic["fixture_file_sha256"], "probe_fixture_file_hash")
    require(report.get("fixture_self_hash") == semantic["fixture_self_hash"], "probe_fixture_self_hash")
    producer = report.get("producer")
    stage = report.get("stage")
    tool = report.get("tool")
    require(isinstance(producer, dict) and isinstance(stage, dict) and isinstance(tool, dict), "probe_provenance")
    require(producer.get("script_path") == semantic["probe_producer_script_path"], "probe_producer_script_path")
    require(producer.get("script_sha256") == semantic["probe_producer_script_sha256"], "probe_producer_script_hash")
    producer_script = ROOT / str(semantic["probe_producer_script_path"])
    require(producer_script.is_file() and sha256_file(producer_script) == semantic["probe_producer_script_sha256"], "decision_producer_script_hash")
    require(isinstance(producer.get("command"), list) and all(isinstance(part, str) for part in producer["command"]), "probe_producer_command")
    require(producer.get("command_sha256") == canonical_sha256(producer["command"]), "probe_producer_command_hash")
    require(stage.get("attribute") == semantic["registered_stage_attribute"], "probe_stage_attribute")
    require(stage.get("build_command") == semantic["registered_stage_build_command"], "probe_stage_command")
    require(stage.get("build_command_sha256") == semantic["registered_stage_build_command_sha256"], "probe_stage_command_hash")
    artifact = Path(str(stage.get("artifact")))
    derivation = Path(str(stage.get("derivation")))
    binary = Path(str(tool.get("binary")))
    require(artifact.is_file(), "probe_stage_artifact_missing")
    require(sha256_file(artifact) == stage.get("artifact_sha256"), "probe_stage_artifact_hash")
    require(derivation_resolver(artifact).resolve() == derivation.resolve(), "probe_stage_derivation_path")
    require(derivation.is_file() and sha256_file(derivation) == stage.get("derivation_sha256"), "probe_stage_derivation_hash")
    require(binary.name == semantic["torch_mlir_tool_name"], "probe_tool_identity")
    require(binary.is_file() and sha256_file(binary) == tool.get("binary_sha256"), "probe_tool_binary_hash")
    require(tool.get("pipeline") == semantic["torch_mlir_pipeline"], "probe_pipeline")
    require(tool.get("pipeline_sha256") == semantic["torch_mlir_pipeline_sha256"], "probe_pipeline_hash")
    executor = report.get("executor")
    require(isinstance(executor, dict), "probe_executor")
    require(executor.get("path") == semantic["probe_executor_contract_path"], "probe_executor_path")
    require(isinstance(executor.get("sha256"), str) and len(executor["sha256"]) == 64, "probe_executor_hash")
    require(isinstance(executor.get("command"), list) and all(isinstance(part, str) for part in executor["command"]), "probe_executor_command")
    require(executor.get("command_sha256") == canonical_sha256(executor["command"]), "probe_executor_command_hash")
    _verify_case_records(report.get("cases"), fixture)
    return {
        "probe_report_sha256": sha256_file(report_path),
        "stage_artifact": str(artifact),
        "stage_artifact_sha256": sha256_file(artifact),
        "status": "accepted",
    }


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
    parser.add_argument("--probe-report", type=Path)
    parser.add_argument("--stage-artifact", type=Path)
    args = parser.parse_args()
    contract = verify_contract(args.fixture, args.decision)
    result: dict[str, object] = {"contract": contract}
    verified_probe_stage: Path | None = None
    if args.probe_report is not None:
        probe = verify_probe_report(args.probe_report, args.fixture, args.decision)
        result["semantic_probe"] = probe
        verified_probe_stage = Path(str(probe["stage_artifact"]))
    if args.stage_artifact is not None and verified_probe_stage is not None:
        require(args.stage_artifact.resolve() == verified_probe_stage.resolve(), "probe_registered_stage_path")
    stage_artifact = args.stage_artifact or verified_probe_stage
    if stage_artifact is not None:
        result["registered_stage"] = verify_registered_stage(stage_artifact, load_object(args.decision))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
