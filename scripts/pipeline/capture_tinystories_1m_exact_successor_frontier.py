#!/usr/bin/env python3
"""Capture deterministic evidence for the exact post-left-shift Torch stage."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_ATTRIBUTE = "tiny-stories-1m-kev-gpt-exact-torch"
TOOL_ATTRIBUTE = "torchMlir"
PATCH = ROOT / "patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch"
TORCH_NIX = ROOT / "torch-mlir.nix"
SEMANTICS_FIXTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json"
SEMANTICS_VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py"
LEFT_REPRODUCER = ROOT / "reproducers/tinystories-1m-exact-torch-mlir/bitwise-left-shift-tensor-scalar.mlir"
RIGHT_REPRODUCER = ROOT / "reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir"
LINALG_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=}, "
    "torch-backend-to-linalg-on-tensors-backend-pipeline)"
)
CANONICAL_FILES = [
    "receipt.json",
    "stage-build.log",
    "tool-build.log",
    "left-shift-lowering.log",
    "right-shift-lowering.log",
    "left-shift-semantics.log",
    "identity-checks.json",
    "stage-derivation.drv",
    "tool-derivation.drv",
    "torch-artifact.mlir.gz",
]
IDENTITIES = {
    "task_1": {
        "path": "artifacts/reference/tinystories-1m-exact-input-audit.json",
        "file_sha256": "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd",
        "payload_sha256": "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766",
    },
    "task_2": {
        "path": "artifacts/reference/tinystories-1m-exact-package-model.json",
        "file_sha256": "173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a",
        "artifact_sha256": "af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838",
        "model_receipt_sha256": "5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834",
    },
    "task_3": {
        "path": "artifacts/reference/tinystories-1m-exact-generation.json",
        "file_sha256": "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3",
        "artifact_sha256": "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3",
        "result_sha256": "c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644",
    },
}
PRIOR_RECEIPTS = [
    "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json",
    "artifacts/comparison/tinystories-1m-exact-successor-frontier.json",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: dict[str, Any]) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


def write_log(path: Path, completed: subprocess.CompletedProcess[str]) -> None:
    path.write_text(
        "[stdout]\n" + completed.stdout + "[stderr]\n" + completed.stderr,
        encoding="utf-8",
    )


def execution(path: Path, command: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": shlex.join(command),
        "exit_code": completed.returncode,
        "log": path.name,
        "log_bytes": path.stat().st_size,
        "log_sha256": sha256_file(path),
    }


def only_store_path(completed: subprocess.CompletedProcess[str], label: str) -> Path:
    paths = [line.strip() for line in completed.stdout.splitlines() if line.startswith("/nix/store/")]
    if completed.returncode != 0 or len(paths) != 1:
        raise RuntimeError(f"{label} did not produce exactly one Nix store path: {paths}")
    path = Path(paths[0])
    if not path.exists():
        raise RuntimeError(f"{label} output is missing: {path}")
    return path


def derivation(attribute: str) -> Path:
    completed = run(["nix", "path-info", "--derivation", f".#{attribute}"])
    if completed.returncode != 0:
        raise RuntimeError(f"cannot resolve {attribute} derivation: {completed.stderr}")
    paths = [line.strip() for line in completed.stdout.splitlines() if line.startswith("/nix/store/")]
    if len(paths) != 1 or not Path(paths[0]).is_file():
        raise RuntimeError(f"invalid {attribute} derivation path: {paths}")
    return Path(paths[0])


def verify_identities() -> dict[str, dict[str, Any]]:
    checked = json.loads(json.dumps(IDENTITIES))
    for name, binding in checked.items():
        path = ROOT / binding["path"]
        if sha256_file(path) != binding["file_sha256"]:
            raise RuntimeError(f"{name} file identity changed")
        value = json.loads(path.read_text(encoding="utf-8"))
        if name == "task_1" and value.get("sha256") != binding["payload_sha256"]:
            raise RuntimeError("Task 1 payload identity changed")
        if name == "task_2":
            if value.get("artifact_sha256") != binding["artifact_sha256"]:
                raise RuntimeError("Task 2 artifact identity changed")
            if value.get("identity", {}).get("model_receipt_sha256") != binding["model_receipt_sha256"]:
                raise RuntimeError("Task 2 model receipt identity changed")
        if name == "task_3":
            if value.get("artifact_sha256") != binding["artifact_sha256"]:
                raise RuntimeError("Task 3 artifact identity changed")
            if value.get("generation", {}).get("result_sha256") != binding["result_sha256"]:
                raise RuntimeError("Task 3 result identity changed")
    return checked


def prior_receipts() -> list[dict[str, Any]]:
    result = []
    for relative in PRIOR_RECEIPTS:
        path = ROOT / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        unsigned = {key: item for key, item in value.items() if key != "sha256"}
        if value.get("sha256") != canonical_hash(unsigned):
            raise RuntimeError(f"prior receipt self-hash mismatch: {relative}")
        result.append({
            "path": relative,
            "file_sha256": sha256_file(path),
            "self_sha256": value["sha256"],
            "preserved": True,
        })
    return result


def capture_run(run_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    run_dir.mkdir(parents=True, exist_ok=False)
    source_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    identities = verify_identities()
    historical = prior_receipts()

    stage_command = ["nix", "build", "--no-link", "--print-out-paths", "-L", f".#{MODEL_ATTRIBUTE}"]
    stage_result = run(stage_command)
    stage_log = run_dir / "stage-build.log"
    write_log(stage_log, stage_result)
    artifact = only_store_path(stage_result, "registered Torch stage")
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise RuntimeError("registered Torch artifact is missing or empty")
    artifact_bytes = artifact.read_bytes()
    artifact_text = artifact_bytes.decode("utf-8")
    if "torch.operator" in artifact_text:
        raise RuntimeError("registered Torch artifact retains a generic torch.operator")
    if "torch.aten.bitwise_left_shift.Tensor_Scalar" in artifact_text:
        raise RuntimeError("registered Torch artifact retains tensor/scalar left shift")
    if "torch.aten.bitwise_right_shift.Tensor_Scalar" in artifact_text:
        raise RuntimeError("registered Torch artifact retains tensor/scalar right shift")
    left_count = artifact_text.count("torch.aten.bitwise_left_shift.Tensor")
    right_count = artifact_text.count("torch.aten.bitwise_right_shift.Tensor")
    if left_count <= 0 or right_count <= 0:
        raise RuntimeError("registered Torch artifact lost registered shift operations")
    (run_dir / "torch-artifact.mlir.gz").write_bytes(gzip.compress(artifact_bytes, compresslevel=9, mtime=0))

    tool_command = ["nix", "build", "--no-link", "--print-out-paths", "-L", f".#{TOOL_ATTRIBUTE}"]
    tool_result = run(tool_command)
    tool_log = run_dir / "tool-build.log"
    write_log(tool_log, tool_result)
    tool_output = only_store_path(tool_result, "patched Torch-MLIR tool")
    tool = tool_output / "bin/torch-mlir-opt"
    if not tool.is_file():
        raise RuntimeError("patched torch-mlir-opt is missing")

    lowering_commands = {
        "left-shift-lowering": [str(tool), f"-pass-pipeline={LINALG_PIPELINE}", str(LEFT_REPRODUCER)],
        "right-shift-lowering": [str(tool), f"-pass-pipeline={LINALG_PIPELINE}", str(RIGHT_REPRODUCER)],
    }
    lowering_results: dict[str, subprocess.CompletedProcess[str]] = {}
    for name, command in lowering_commands.items():
        completed = run(command)
        lowering_results[name] = completed
        write_log(run_dir / f"{name}.log", completed)
        expected = "arith.shli" if name.startswith("left") else "arith.shrsi"
        generic = "left_shift.Tensor_Scalar" if name.startswith("left") else "right_shift.Tensor_Scalar"
        if completed.returncode != 0 or expected not in completed.stdout or generic in completed.stdout:
            raise RuntimeError(f"{name} did not prove {expected}")

    semantics_command = [sys.executable, str(SEMANTICS_VERIFIER)]
    semantics_result = run(semantics_command)
    semantics_log = run_dir / "left-shift-semantics.log"
    write_log(semantics_log, semantics_result)
    if semantics_result.returncode != 0 or '"status": "accepted"' not in semantics_result.stdout:
        raise RuntimeError("left-shift semantic fixture verification failed")

    stage_drv = derivation(MODEL_ATTRIBUTE)
    tool_drv = derivation(TOOL_ATTRIBUTE)
    (run_dir / "stage-derivation.drv").write_bytes(stage_drv.read_bytes())
    (run_dir / "tool-derivation.drv").write_bytes(tool_drv.read_bytes())
    semantic_value = json.loads(SEMANTICS_FIXTURE.read_text(encoding="utf-8"))
    identity_log = {
        "schema": "tinystories-1m-exact-left-shift-success-identities-v1",
        "task_identities": identities,
        "prior_receipts": historical,
        "semantic_fixture": {
            "path": str(SEMANTICS_FIXTURE.relative_to(ROOT)),
            "file_sha256": sha256_file(SEMANTICS_FIXTURE),
            "self_sha256": semantic_value["sha256"],
        },
    }
    (run_dir / "identity-checks.json").write_text(json.dumps(identity_log, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    producer = Path(__file__).resolve()
    executions = {
        "registered-torch-stage": execution(stage_log, stage_command, stage_result),
        "patched-tool": execution(tool_log, tool_command, tool_result),
        "left-shift-lowering": execution(run_dir / "left-shift-lowering.log", lowering_commands["left-shift-lowering"], lowering_results["left-shift-lowering"]),
        "right-shift-lowering": execution(run_dir / "right-shift-lowering.log", lowering_commands["right-shift-lowering"], lowering_results["right-shift-lowering"]),
        "left-shift-semantics": execution(semantics_log, semantics_command, semantics_result),
    }
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-left-shift-success-receipt-v1",
        "source_commit": source_commit,
        "model": "tiny-stories-1m-kev-gpt-exact",
        "status": "registered_torch_valid",
        "stage": "torch-mlir",
        "artifact": {
            "output": str(artifact),
            "bytes": len(artifact_bytes),
            "sha256": sha256_bytes(artifact_bytes),
            "archive": "torch-artifact.mlir.gz",
            "archive_bytes": (run_dir / "torch-artifact.mlir.gz").stat().st_size,
            "archive_sha256": sha256_file(run_dir / "torch-artifact.mlir.gz"),
            "generic_operator_count": artifact_text.count("torch.operator"),
            "left_tensor_scalar_count": artifact_text.count("torch.aten.bitwise_left_shift.Tensor_Scalar"),
            "right_tensor_scalar_count": artifact_text.count("torch.aten.bitwise_right_shift.Tensor_Scalar"),
            "left_tensor_count": left_count,
            "right_tensor_count": right_count,
        },
        "stage_derivation": {
            "path": str(stage_drv),
            "file_sha256": sha256_file(stage_drv),
            "captured_file": "stage-derivation.drv",
        },
        "compiler": {
            "torch_mlir_source_revision": "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
            "output": str(tool_output),
            "binary": str(tool),
            "binary_sha256": sha256_file(tool),
            "derivation": str(tool_drv),
            "derivation_file_sha256": sha256_file(tool_drv),
            "captured_derivation": "tool-derivation.drv",
            "patch": str(PATCH.relative_to(ROOT)),
            "patch_sha256": sha256_file(PATCH),
            "nix_expression": str(TORCH_NIX.relative_to(ROOT)),
            "nix_expression_sha256": sha256_file(TORCH_NIX),
            "producer": str(producer.relative_to(ROOT)),
            "producer_sha256": sha256_file(producer),
            "verifier": str(VERIFIER.relative_to(ROOT)),
            "verifier_sha256": sha256_file(VERIFIER),
        },
        "semantic_fixture": identity_log["semantic_fixture"],
        "identity_bindings": identities,
        "prior_receipts": historical,
        "executions": executions,
        "pipeline_execution": {
            "registered_torch_stage_valid": True,
            "full_later_stages_run": [],
            "full_later_stages_not_run": ["linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"],
            "reduced_linalg_shift_proofs_run": ["left-shift-lowering", "right-shift-lowering"],
        },
        "claims": {
            "left_shift_implemented": True,
            "right_shift_preserved": True,
            "registered_torch_artifact_nonempty": True,
            "model_contract_changed": False,
            "adapter_changed": False,
        },
    }
    receipt["sha256"] = canonical_hash(receipt)
    (run_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata = {
        "canonical": False,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_seconds_approximate": round(time.monotonic() - started),
    }
    (run_dir / "noncanonical-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def finalize(bundle_root: Path) -> dict[str, Any]:
    run_data: dict[str, dict[str, bytes]] = {}
    runs: dict[str, Any] = {}
    for run_name in ("run-1", "run-2"):
        run_dir = bundle_root / run_name
        receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
        files = {name: (run_dir / name).read_bytes() for name in CANONICAL_FILES}
        run_data[run_name] = files
        runs[run_name] = {
            "source_commit": receipt["source_commit"],
            "receipt_self_hash": receipt["sha256"],
            "files": {name: {"bytes": len(data), "sha256": sha256_bytes(data)} for name, data in files.items()},
            "commands": {name: value["command"] for name, value in receipt["executions"].items()},
            "exit_codes": {name: value["exit_code"] for name, value in receipt["executions"].items()},
            "noncanonical_metadata": json.loads((run_dir / "noncanonical-metadata.json").read_text(encoding="utf-8")),
        }
    for filename in CANONICAL_FILES:
        if run_data["run-1"][filename] != run_data["run-2"][filename]:
            raise RuntimeError(f"independent success captures differ at {filename}")
    receipt = json.loads(run_data["run-1"]["receipt.json"])
    success_receipt = bundle_root.parent / "tinystories-1m-exact-left-shift-success.json"
    success_receipt.write_bytes(run_data["run-1"]["receipt.json"])
    manifest = {
        "schema": "tinystories-1m-exact-left-shift-success-determinism-v1",
        "source_commit": receipt["source_commit"],
        "canonical_files": CANONICAL_FILES,
        "runs": runs,
        "expected_comparison": {
            "byte_identical": True,
            "receipt_file_sha256": sha256_bytes(run_data["run-1"]["receipt.json"]),
            "receipt_self_hash": receipt["sha256"],
            "artifact_archive_sha256": sha256_bytes(run_data["run-1"]["torch-artifact.mlir.gz"]),
        },
        "success_receipt": {
            "path": str(success_receipt.relative_to(ROOT)),
            "bytes": success_receipt.stat().st_size,
            "file_sha256": sha256_file(success_receipt),
            "self_sha256": receipt["sha256"],
        },
    }
    (bundle_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    default = ROOT / "artifacts/comparison/tinystories-1m-exact-left-shift-success-determinism"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-name", choices=("run-1", "run-2"))
    group.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    bundle_root = args.bundle_dir.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    result = finalize(bundle_root) if args.finalize else capture_run(bundle_root / args.run_name)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
