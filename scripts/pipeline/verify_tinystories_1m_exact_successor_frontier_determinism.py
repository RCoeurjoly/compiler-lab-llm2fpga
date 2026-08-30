#!/usr/bin/env python3
"""Verify deterministic evidence for the post-right-shift TinyStories frontier."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "tinystories-1m-exact-successor-frontier-determinism-bundles-v1"
RECEIPT_SCHEMA = "tinystories-1m-exact-successor-frontier-receipt-v1"
RIGHT_OPERATION = "torch.aten.bitwise_right_shift.Tensor_Scalar"
LEFT_OPERATION = "torch.aten.bitwise_left_shift.Tensor_Scalar"
DIAGNOSTIC = "failed to legalize operation 'torch.operator' that was explicitly marked illegal"
EXPECTED_CANONICAL_FILES = [
    "receipt.json",
    "pytorch-exported-build.log",
    "torch-mlir.log",
    "compiler-import-capture.log",
    "pre-reduce-op-variants.log",
    "interesting-full.log",
    "interesting-reproducer.log",
    "right-shift-lowering.log",
    "full-failing-ir.mlir.gz",
]
EXPECTED_NOT_RUN = ["linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"]


class VerificationError(RuntimeError):
    """Raised when successor-frontier evidence is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load JSON evidence {path}: {error}") from error
    require(isinstance(value, dict), f"JSON evidence must be an object: {path}")
    return value


def receipt_self_hash(receipt: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    return sha256_bytes(
        json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


def verify_local_binding(binding: dict[str, Any], label: str) -> None:
    path = ROOT / str(binding.get("path", ""))
    require(path.is_file(), f"{label}: bound file is missing")
    require(
        binding.get("file_sha256") == sha256_file(path),
        f"{label}: current file SHA-256 mismatch",
    )


def verify_identities(receipt: dict[str, Any]) -> None:
    identities = receipt.get("identity_bindings")
    require(isinstance(identities, dict), "Task 1-3 identity bindings are missing")
    require(
        sorted(identities) == ["adapter", "task_1", "task_2", "task_3"],
        "Task 1-3 identity set is incomplete",
    )
    for name, binding in identities.items():
        require(isinstance(binding, dict), f"{name}: identity binding is invalid")
        verify_local_binding(binding, name)
    audit = load_json(ROOT / identities["task_1"]["path"])
    model = load_json(ROOT / identities["task_2"]["path"])
    generation = load_json(ROOT / identities["task_3"]["path"])
    require(
        audit.get("sha256") == identities["task_1"].get("payload_sha256"),
        "Task 1 payload SHA-256 mismatch",
    )
    require(
        model.get("artifact_sha256") == identities["task_2"].get("artifact_sha256"),
        "Task 2 artifact SHA-256 mismatch",
    )
    require(
        model.get("identity", {}).get("model_receipt_sha256")
        == identities["task_2"].get("model_receipt_sha256"),
        "Task 2 model receipt SHA-256 mismatch",
    )
    require(
        generation.get("artifact_sha256")
        == identities["task_3"].get("artifact_sha256"),
        "Task 3 artifact SHA-256 mismatch",
    )
    require(
        generation.get("generation", {}).get("result_sha256")
        == identities["task_3"].get("result_sha256"),
        "Task 3 result SHA-256 mismatch",
    )


def verify_compiler(receipt: dict[str, Any]) -> None:
    compiler = receipt.get("compiler")
    require(isinstance(compiler, dict), "patched compiler binding is missing")
    require(
        compiler.get("torch_mlir_source_revision")
        == "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
        "pinned Torch-MLIR source revision mismatch",
    )
    for path_key, hash_key in (
        ("binary", "binary_sha256"),
        ("tool_derivation", "tool_derivation_file_sha256"),
    ):
        path = Path(str(compiler.get(path_key, "")))
        require(path.is_file(), f"patched compiler {path_key} is missing")
        require(
            compiler.get(hash_key) == sha256_file(path),
            f"patched compiler {path_key} SHA-256 mismatch",
        )
    output = str(compiler.get("tool_output", ""))
    require(
        str(compiler["binary"]).startswith(output + "/"),
        "compiler binary is not inside the bound patched output",
    )
    for path_key, hash_key in (
        ("patch", "patch_sha256"),
        ("nix_expression", "nix_expression_sha256"),
        ("producer", "producer_sha256"),
        ("verifier", "verifier_sha256"),
    ):
        path = ROOT / str(compiler.get(path_key, ""))
        require(path.is_file(), f"compiler input {path_key} is missing")
        require(
            compiler.get(hash_key) == sha256_file(path),
            f"compiler input {path_key} SHA-256 mismatch",
        )
    patch_text = (ROOT / compiler["patch"]).read_text(encoding="utf-8")
    require(LEFT_OPERATION not in patch_text, "right-shift patch mentions left shift")


def verify_receipt(
    run_root: Path, receipt: dict[str, Any], file_bytes: dict[str, bytes]
) -> None:
    require(receipt.get("schema") == RECEIPT_SCHEMA, "unsupported receipt schema")
    require(receipt.get("status") == "compiler_frontier", "receipt status mismatch")
    require(receipt.get("stage") == "torch-mlir", "earliest stage mismatch")
    require(receipt.get("frontier") == "torch_mlir_frontier", "frontier class mismatch")
    require(receipt.get("operation") == LEFT_OPERATION, "successor operation mismatch")
    require(receipt.get("diagnostic") == DIAGNOSTIC, "successor diagnostic mismatch")
    require(receipt.get("sha256") == receipt_self_hash(receipt), "receipt self-hash mismatch")

    pipeline = receipt.get("pipeline_execution")
    require(isinstance(pipeline, dict), "pipeline execution binding is missing")
    require(
        pipeline.get("first_invalid_stage") == "torch-mlir"
        and pipeline.get("stopped_after_first_invalid_stage") is True,
        "receipt does not stop at the first invalid stage",
    )
    require(pipeline.get("not_run") == EXPECTED_NOT_RUN, "later-stage exclusion mismatch")
    claims = receipt.get("claims")
    require(isinstance(claims, dict), "claims are missing")
    require(all(value is False for value in claims.values()), "receipt makes a later/semantic claim")

    executions = receipt.get("executions")
    require(isinstance(executions, dict), "execution records are missing")
    expected_execution_logs = {
        "pytorch-exported": "pytorch-exported-build.log",
        "torch-mlir": "torch-mlir.log",
        "compiler-import-capture": "compiler-import-capture.log",
        "pre-reduce-op-variants": "pre-reduce-op-variants.log",
        "interesting-full": "interesting-full.log",
        "interesting-reproducer": "interesting-reproducer.log",
        "right-shift-lowering": "right-shift-lowering.log",
    }
    require(
        sorted(executions) == sorted(expected_execution_logs),
        "execution record set is incomplete",
    )
    for name, filename in expected_execution_logs.items():
        record = executions[name]
        require(record.get("command"), f"{name}: command is missing")
        require(record.get("log") == filename, f"{name}: log path mismatch")
        data = file_bytes[filename]
        require(record.get("log_bytes") == len(data), f"{name}: log size mismatch")
        require(
            record.get("log_sha256") == sha256_bytes(data),
            f"{name}: log SHA-256 mismatch",
        )
    require(executions["pytorch-exported"].get("exit_code") == 0, "export did not succeed")
    require(executions["torch-mlir"].get("exit_code") != 0, "Torch frontier did not fail")
    require(
        executions["compiler-import-capture"].get("exit_code") != 0,
        "content-bound compiler capture did not fail",
    )
    require(
        executions["compiler-import-capture"].get("operation") == LEFT_OPERATION,
        "content-bound compiler capture does not name the successor operation",
    )
    require(
        executions["pre-reduce-op-variants"].get("exit_code") != 0,
        "pre-Reduce frontier execution did not fail",
    )
    for name in ("interesting-full", "interesting-reproducer", "right-shift-lowering"):
        require(executions[name].get("exit_code") == 0, f"{name}: evidence command failed")

    torch_log = file_bytes["torch-mlir.log"].decode("utf-8")
    capture_log = file_bytes["compiler-import-capture.log"].decode("utf-8")
    pre_reduce_log = file_bytes["pre-reduce-op-variants.log"].decode("utf-8")
    lowering_log = file_bytes["right-shift-lowering.log"].decode("utf-8")
    require(DIAGNOSTIC in torch_log, "registered Torch log lost the diagnostic")
    require(DIAGNOSTIC in capture_log, "compiler capture lost the diagnostic")
    require(DIAGNOSTIC in pre_reduce_log, "pre-Reduce log lost the diagnostic")
    require(LEFT_OPERATION in pre_reduce_log, "pre-Reduce log lost the left-shift op")
    require("arith.shrsi" in lowering_log, "runtime lowering log lost arith.shrsi")
    require(RIGHT_OPERATION not in lowering_log, "runtime lowering retained generic right shift")

    full = receipt.get("full_failing_ir")
    require(isinstance(full, dict), "full failing input binding is missing")
    archive = file_bytes["full-failing-ir.mlir.gz"]
    require(full.get("archive") == "full-failing-ir.mlir.gz", "archive path mismatch")
    require(full.get("archive_bytes") == len(archive), "archive size mismatch")
    require(full.get("archive_sha256") == sha256_bytes(archive), "archive SHA-256 mismatch")
    try:
        content = gzip.decompress(archive)
    except OSError as error:
        raise VerificationError(f"full failing input is not valid deterministic gzip: {error}") from error
    text = content.decode("utf-8")
    require(full.get("content_bytes") == len(content), "full input size mismatch")
    require(full.get("content_sha256") == sha256_bytes(content), "full input SHA-256 mismatch")
    require(full.get("raw_torch_operator_count") == text.count("torch.operator "), "operator count mismatch")
    require(full.get("raw_right_shift_count") == text.count(RIGHT_OPERATION), "raw right count mismatch")
    require(full.get("raw_left_shift_count") == text.count(LEFT_OPERATION), "raw left count mismatch")
    require(full.get("raw_right_shift_count", 0) > 0, "raw input has no right shifts")
    require(full.get("raw_left_shift_count", 0) > 0, "raw input has no left shifts")
    require(full.get("pre_reduce_right_shift_count") == 0, "right shift remains at successor frontier")
    require(
        full.get("pre_reduce_left_shift_count") == full.get("raw_left_shift_count"),
        "left-shift population changed before the successor frontier",
    )

    reproducer = receipt.get("minimal_reproducer")
    require(isinstance(reproducer, dict), "minimal reproducer binding is missing")
    reproducer_path = ROOT / str(reproducer.get("path", ""))
    require(reproducer_path.is_file(), "minimal reproducer is missing")
    reproducer_bytes = reproducer_path.read_bytes()
    require(reproducer.get("bytes") == len(reproducer_bytes), "reproducer size mismatch")
    require(reproducer.get("sha256") == sha256_bytes(reproducer_bytes), "reproducer SHA-256 mismatch")
    reproducer_text = reproducer_bytes.decode("utf-8")
    require(reproducer_text.count("torch.operator") == 1, "reproducer is not minimal")
    require(LEFT_OPERATION in reproducer_text, "reproducer lost the left-shift operation")
    require(
        re.search(
            r"\(!torch\.vtensor<\[4,64\],si64>, !torch\.int\) -> "
            r"!torch\.vtensor<\[4,64\],si64>",
            reproducer_text,
        )
        is not None,
        "reproducer lost the original types",
    )
    require(reproducer.get("full_verified") is True, "full input interestingness is unverified")
    require(reproducer.get("reproducer_verified") is True, "reproducer interestingness is unverified")

    historical = receipt.get("historical_frontier")
    require(isinstance(historical, dict), "historical frontier binding is missing")
    historical_path = ROOT / str(historical.get("path", ""))
    require(historical_path.is_file(), "historical frontier receipt is missing")
    require(
        historical.get("file_sha256") == sha256_file(historical_path),
        "historical receipt SHA-256 mismatch",
    )
    historical_receipt = load_json(historical_path)
    require(
        historical.get("self_sha256") == historical_receipt.get("sha256"),
        "historical receipt self-hash mismatch",
    )
    require(historical.get("preserved") is True, "historical receipt was not preserved")
    verify_identities(receipt)
    verify_compiler(receipt)


def verify_successor_bundles(bundle_root: Path) -> dict[str, Any]:
    bundle_root = bundle_root.resolve()
    manifest = load_json(bundle_root / "manifest.json")
    require(manifest.get("schema") == SCHEMA, "unsupported successor manifest schema")
    require(
        manifest.get("canonical_files") == EXPECTED_CANONICAL_FILES,
        "successor canonical file set mismatch",
    )
    runs = manifest.get("runs")
    require(isinstance(runs, dict), "successor run manifests are missing")
    run_names = sorted(runs)
    require(run_names == ["run-1", "run-2"], "exactly two successor runs are required")

    verified: dict[str, tuple[dict[str, Any], dict[str, bytes]]] = {}
    for run_name in run_names:
        run_root = bundle_root / run_name
        require(run_root.is_dir(), f"missing successor run directory: {run_name}")
        run_manifest = runs[run_name]
        require(isinstance(run_manifest, dict), f"{run_name}: invalid run manifest")
        files = run_manifest.get("files")
        require(isinstance(files, dict), f"{run_name}: file manifest is missing")
        require(sorted(files) == sorted(EXPECTED_CANONICAL_FILES), f"{run_name}: file set mismatch")
        file_bytes: dict[str, bytes] = {}
        for filename in EXPECTED_CANONICAL_FILES:
            path = run_root / filename
            require(path.is_file(), f"{run_name}: missing canonical file {filename}")
            data = path.read_bytes()
            file_bytes[filename] = data
            binding = files[filename]
            require(binding.get("bytes") == len(data), f"{run_name}: size mismatch for {filename}")
            require(
                binding.get("sha256") == sha256_bytes(data),
                f"{run_name}: SHA-256 mismatch for {filename}",
            )
        receipt = load_json(run_root / "receipt.json")
        require(
            run_manifest.get("source_commit") == receipt.get("source_commit")
            == manifest.get("source_commit"),
            f"{run_name}: source commit mismatch",
        )
        require(
            run_manifest.get("receipt_self_hash") == receipt.get("sha256"),
            f"{run_name}: receipt self-hash manifest mismatch",
        )
        metadata = run_manifest.get("noncanonical_metadata")
        require(isinstance(metadata, dict), f"{run_name}: noncanonical metadata missing")
        require(metadata.get("canonical") is False, f"{run_name}: metadata marked canonical")
        verify_receipt(run_root, receipt, file_bytes)
        verified[run_name] = (receipt, file_bytes)

    first_receipt, first_files = verified["run-1"]
    second_receipt, second_files = verified["run-2"]
    for filename in EXPECTED_CANONICAL_FILES:
        require(
            first_files[filename] == second_files[filename],
            f"successor runs differ at canonical file {filename}",
        )
    require(first_receipt == second_receipt, "successor parsed receipts differ")
    expected = manifest.get("expected_comparison")
    require(isinstance(expected, dict), "successor comparison binding is missing")
    require(expected.get("byte_identical") is True, "manifest does not require identity")
    require(
        expected.get("receipt_file_sha256") == sha256_bytes(first_files["receipt.json"]),
        "successor receipt file SHA-256 mismatch",
    )
    require(
        expected.get("receipt_self_hash") == first_receipt.get("sha256"),
        "successor receipt self-hash mismatch",
    )
    require(
        expected.get("full_failing_ir_sha256")
        == sha256_bytes(first_files["full-failing-ir.mlir.gz"]),
        "successor full input comparison SHA-256 mismatch",
    )
    successor = manifest.get("successor_receipt")
    require(isinstance(successor, dict), "top-level successor receipt binding is missing")
    successor_path = ROOT / str(successor.get("path", ""))
    require(successor_path.is_file(), "top-level successor receipt is missing")
    successor_bytes = successor_path.read_bytes()
    require(
        successor.get("bytes") == len(successor_bytes),
        "top-level successor receipt size mismatch",
    )
    require(
        successor.get("file_sha256") == sha256_bytes(successor_bytes)
        == sha256_bytes(first_files["receipt.json"]),
        "top-level successor receipt SHA-256 mismatch",
    )
    require(
        successor.get("self_sha256") == first_receipt.get("sha256"),
        "top-level successor receipt self-hash mismatch",
    )
    require(
        successor_bytes == first_files["receipt.json"],
        "top-level successor receipt differs from preserved captures",
    )
    full = first_receipt["full_failing_ir"]
    return {
        "source_commit": manifest["source_commit"],
        "runs": run_names,
        "byte_identical": True,
        "receipt_file_sha256": expected["receipt_file_sha256"],
        "receipt_self_hash": expected["receipt_self_hash"],
        "frontier_operation": first_receipt["operation"],
        "raw_right_shift_count": full["raw_right_shift_count"],
        "raw_left_shift_count": full["raw_left_shift_count"],
        "pre_reduce_right_shift_count": full["pre_reduce_right_shift_count"],
        "pre_reduce_left_shift_count": full["pre_reduce_left_shift_count"],
    }


def main() -> None:
    default_bundle = (
        ROOT
        / "artifacts/comparison/tinystories-1m-exact-successor-frontier-determinism"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_successor_bundles(args.bundle_dir), indent=2, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
