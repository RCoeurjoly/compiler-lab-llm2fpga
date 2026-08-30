#!/usr/bin/env python3
"""Produce a provenance-bound semantic report from the registered Torch stage.

This runner is intentionally only a contract until the selected Torch-MLIR pass
supplies the executor named by the decision receipt.  It never accepts a result
JSON from a caller: it builds the registered stage and invokes that executor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-exact-shift-semantics.json"
DECISION_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"
def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid_object:{path}")
    return value


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=FIXTURE_DEFAULT)
    parser.add_argument("--decision", type=Path, default=DECISION_DEFAULT)
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    fixture = load_object(args.fixture)
    decision = load_object(args.decision)
    semantic = decision["semantic_regression"]
    script = Path(__file__).resolve()
    if sha256_file(script) != semantic["probe_producer_script_sha256"]:
        raise ValueError("probe_producer_script_hash")
    if args.executor.resolve() != (ROOT / semantic["probe_executor_contract_path"]).resolve():
        raise ValueError("probe_executor_path")
    if not args.executor.is_file() or not args.executor.stat().st_mode & 0o111:
        raise ValueError("probe_executor_missing_or_not_executable")
    build_command = semantic["registered_stage_build_command"]
    if not isinstance(build_command, list) or not all(isinstance(part, str) for part in build_command):
        raise ValueError("probe_stage_command")
    if canonical_sha256(build_command) != semantic["registered_stage_build_command_sha256"]:
        raise ValueError("probe_stage_command_hash")
    stage = Path(run(build_command).stdout.strip())
    derivation = Path(run(["nix", "path-info", "--derivation", str(stage)]).stdout.strip())
    tool_path = shutil.which(semantic["torch_mlir_tool_name"])
    if tool_path is None:
        raise ValueError("probe_tool_missing")
    tool = Path(tool_path).resolve()
    with tempfile.TemporaryDirectory(prefix="tinystories-exact-shift-probe-") as temporary:
        executor_output = Path(temporary) / "executor-results.json"
        executor_command = [
            str(args.executor.resolve()),
            "--stage-artifact", str(stage),
            "--fixture", str(args.fixture.resolve()),
            "--tool", str(tool),
            "--pass-pipeline", semantic["torch_mlir_pipeline"],
            "--out", str(executor_output),
        ]
        run(executor_command)
        execution = load_object(executor_output)
    if execution.get("schema") != "tinystories-1m-exact-shift-executor-results-v1":
        raise ValueError("probe_executor_schema")
    if execution.get("stage_artifact_sha256") != sha256_file(stage):
        raise ValueError("probe_executor_stage_hash")
    if execution.get("fixture_file_sha256") != sha256_file(args.fixture):
        raise ValueError("probe_executor_fixture_hash")
    if execution.get("tool_binary_sha256") != sha256_file(tool):
        raise ValueError("probe_executor_tool_hash")
    if execution.get("pipeline_sha256") != canonical_sha256(semantic["torch_mlir_pipeline"]):
        raise ValueError("probe_executor_pipeline_hash")
    report: dict[str, object] = {
        "schema": "tinystories-1m-exact-shift-semantic-probe-v1",
        "decision_sha256": decision["sha256"],
        "fixture_file_sha256": sha256_file(args.fixture),
        "fixture_self_hash": fixture["sha256"],
        "producer": {
            "script_path": semantic["probe_producer_script_path"],
            "script_sha256": sha256_file(script),
            "command": sys.argv,
            "command_sha256": canonical_sha256(sys.argv),
        },
        "stage": {
            "attribute": semantic["registered_stage_attribute"],
            "build_command": build_command,
            "build_command_sha256": canonical_sha256(build_command),
            "artifact": str(stage),
            "artifact_sha256": sha256_file(stage),
            "derivation": str(derivation),
            "derivation_sha256": sha256_file(derivation),
        },
        "tool": {
            "binary": str(tool),
            "binary_sha256": sha256_file(tool),
            "pipeline": semantic["torch_mlir_pipeline"],
            "pipeline_sha256": canonical_sha256(semantic["torch_mlir_pipeline"]),
        },
        "executor": {
            "path": semantic["probe_executor_contract_path"],
            "sha256": sha256_file(args.executor),
            "command": executor_command,
            "command_sha256": canonical_sha256(executor_command),
        },
        "cases": execution["cases"],
    }
    report["sha256"] = canonical_sha256(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
