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
HISTORICAL_RIGHT_SHIFT_PATCH_SHA256 = "1f3ab13eb4bcfb4bf87112cf8bb648424174f01a483aa38c0583a056ca7fab99"
HISTORICAL_SUCCESSOR_INPUT_SHA256 = {
    "patch": HISTORICAL_RIGHT_SHIFT_PATCH_SHA256,
    "producer": "74c47ee7ac2df0b2d2b24f1f4b8a33e6196c09109a7c0c8cec014bd5e9fdc818",
    "verifier": "12a33a34064437ef77f6a3f8ec5a9d83e169f6a037abd3f65d9b7674224fac06",
}
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
SUCCESS_SCHEMA = "tinystories-1m-exact-left-shift-success-determinism-v1"
SUCCESS_RECEIPT_SCHEMA = "tinystories-1m-exact-left-shift-success-receipt-v1"
SUCCESS_CANONICAL_FILES = [
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
        current_hash = sha256_file(path)
        if path_key in HISTORICAL_SUCCESSOR_INPUT_SHA256 and compiler.get(hash_key) != current_hash:
            require(
                compiler.get(hash_key) == HISTORICAL_SUCCESSOR_INPUT_SHA256[path_key],
                f"compiler input {path_key} SHA-256 mismatch",
            )
            continue
        require(compiler.get(hash_key) == current_hash, f"compiler input {path_key} SHA-256 mismatch")
    patch_text = (ROOT / compiler["patch"]).read_text(encoding="utf-8")
    require("LegalizeBitwiseRightShiftTensorScalarPass" in patch_text, "right-shift pass is missing")
    if "LegalizeBitwiseLeftShiftTensorScalarPass" in patch_text:
        right_shift_text = patch_text[
            patch_text.index("class LegalizeBitwiseRightShiftTensorScalarPass") :
            patch_text.index("class LegalizeBitwiseLeftShiftTensorScalarPass")
        ]
    else:
        right_shift_text = patch_text
    require(LEFT_OPERATION not in right_shift_text, "right-shift matcher mentions left shift")


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


def _verify_success_receipt(
    run_root: Path, receipt: dict[str, Any], file_bytes: dict[str, bytes]
) -> None:
    require(receipt.get("schema") == SUCCESS_RECEIPT_SCHEMA, "unsupported success receipt schema")
    require(receipt.get("status") == "registered_torch_valid", "registered Torch status mismatch")
    require(receipt.get("stage") == "torch-mlir", "registered Torch stage mismatch")
    require(receipt.get("sha256") == receipt_self_hash(receipt), "success receipt self-hash mismatch")

    artifact = receipt.get("artifact")
    require(isinstance(artifact, dict), "registered Torch artifact binding is missing")
    archive = file_bytes["torch-artifact.mlir.gz"]
    require(artifact.get("archive") == "torch-artifact.mlir.gz", "artifact archive path mismatch")
    require(artifact.get("archive_bytes") == len(archive), "artifact archive size mismatch")
    require(artifact.get("archive_sha256") == sha256_bytes(archive), "artifact archive SHA-256 mismatch")
    try:
        content = gzip.decompress(archive)
    except OSError as error:
        raise VerificationError(f"registered Torch artifact is not valid gzip: {error}") from error
    text = content.decode("utf-8")
    require(artifact.get("bytes") == len(content) and len(content) > 0, "artifact content size mismatch")
    require(artifact.get("sha256") == sha256_bytes(content), "artifact content SHA-256 mismatch")
    require(artifact.get("generic_operator_count") == text.count("torch.operator") == 0, "generic operator remains")
    require(
        artifact.get("left_tensor_scalar_count")
        == text.count("torch.aten.bitwise_left_shift.Tensor_Scalar")
        == 0,
        "tensor/scalar left shift remains",
    )
    require(
        artifact.get("right_tensor_scalar_count")
        == text.count("torch.aten.bitwise_right_shift.Tensor_Scalar")
        == 0,
        "tensor/scalar right shift remains",
    )
    require(
        artifact.get("left_tensor_count") == text.count("torch.aten.bitwise_left_shift.Tensor") > 0,
        "registered left shifts are missing",
    )
    require(
        artifact.get("right_tensor_count") == text.count("torch.aten.bitwise_right_shift.Tensor") > 0,
        "registered right shifts are missing",
    )
    output = Path(str(artifact.get("output", "")))
    if output.is_file():
        require(sha256_file(output) == artifact.get("sha256"), "live artifact SHA-256 mismatch")

    for receipt_key, canonical_file in (
        ("stage_derivation", "stage-derivation.drv"),
        ("compiler", "tool-derivation.drv"),
    ):
        binding = receipt.get(receipt_key)
        require(isinstance(binding, dict), f"{receipt_key} binding is missing")
        expected_hash = (
            binding.get("file_sha256")
            if receipt_key == "stage_derivation"
            else binding.get("derivation_file_sha256")
        )
        require(sha256_bytes(file_bytes[canonical_file]) == expected_hash, f"{receipt_key} captured SHA-256 mismatch")
        store_key = "path" if receipt_key == "stage_derivation" else "derivation"
        store_path = Path(str(binding.get(store_key, "")))
        if store_path.is_file():
            require(sha256_file(store_path) == expected_hash, f"{receipt_key} live SHA-256 mismatch")

    compiler = receipt.get("compiler")
    require(isinstance(compiler, dict), "compiler binding is missing")
    require(
        compiler.get("torch_mlir_source_revision")
        == "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
        "pinned Torch-MLIR revision mismatch",
    )
    binary = Path(str(compiler.get("binary", "")))
    require(binary.is_file() and sha256_file(binary) == compiler.get("binary_sha256"), "compiler binary mismatch")
    for path_key, hash_key in (
        ("patch", "patch_sha256"),
        ("nix_expression", "nix_expression_sha256"),
        ("producer", "producer_sha256"),
        ("verifier", "verifier_sha256"),
    ):
        path = ROOT / str(compiler.get(path_key, ""))
        require(path.is_file(), f"compiler {path_key} is missing")
        require(sha256_file(path) == compiler.get(hash_key), f"compiler {path_key} SHA-256 mismatch")
    patch_text = (ROOT / str(compiler["patch"])).read_text(encoding="utf-8")
    require("LegalizeBitwiseLeftShiftTensorScalarPass" in patch_text, "left-shift compiler patch is missing")
    require("AtenBitwiseLeftShiftTensorOp" in patch_text, "registered left-shift rewrite is missing")
    require("arith.shli" in patch_text, "left-shift arithmetic binding is missing")

    executions = receipt.get("executions")
    require(isinstance(executions, dict), "success execution records are missing")
    expected_logs = {
        "registered-torch-stage": "stage-build.log",
        "patched-tool": "tool-build.log",
        "left-shift-lowering": "left-shift-lowering.log",
        "right-shift-lowering": "right-shift-lowering.log",
        "left-shift-semantics": "left-shift-semantics.log",
    }
    require(sorted(executions) == sorted(expected_logs), "success execution record set mismatch")
    for name, filename in expected_logs.items():
        record = executions[name]
        data = file_bytes[filename]
        require(record.get("command"), f"{name}: command is missing")
        require(record.get("exit_code") == 0, f"{name}: command failed")
        require(record.get("log") == filename, f"{name}: log path mismatch")
        require(record.get("log_bytes") == len(data), f"{name}: log size mismatch")
        require(record.get("log_sha256") == sha256_bytes(data), f"{name}: log SHA-256 mismatch")
    require(b"arith.shli" in file_bytes["left-shift-lowering.log"], "left lowering lost arith.shli")
    require(b"arith.shrsi" in file_bytes["right-shift-lowering.log"], "right lowering lost arith.shrsi")
    require(b'"status": "accepted"' in file_bytes["left-shift-semantics.log"], "semantic proof is missing")

    identities = receipt.get("identity_bindings")
    require(isinstance(identities, dict) and sorted(identities) == ["task_1", "task_2", "task_3"], "Task 1-3 identities are incomplete")
    synthetic = {"identity_bindings": {"adapter": {
        "path": "TinyStories/model_adapter_exact_package.py",
        "file_sha256": "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e",
    }, **identities}}
    verify_identities(synthetic)
    fixture = receipt.get("semantic_fixture")
    require(isinstance(fixture, dict), "semantic fixture binding is missing")
    verify_local_binding(fixture, "semantic fixture")
    fixture_value = load_json(ROOT / fixture["path"])
    require(fixture_value.get("sha256") == fixture.get("self_sha256"), "semantic fixture self-hash mismatch")
    prior = receipt.get("prior_receipts")
    require(isinstance(prior, list) and len(prior) == 2, "prior receipt set is incomplete")
    for index, binding in enumerate(prior):
        require(binding.get("preserved") is True, f"prior receipt {index} is not preserved")
        verify_local_binding(binding, f"prior receipt {index}")
        value = load_json(ROOT / binding["path"])
        require(value.get("sha256") == binding.get("self_sha256"), f"prior receipt {index} self-hash mismatch")
    identity_log = json.loads(file_bytes["identity-checks.json"].decode("utf-8"))
    require(identity_log.get("task_identities") == identities, "identity log Task 1-3 mismatch")
    require(identity_log.get("prior_receipts") == prior, "identity log prior receipt mismatch")
    require(identity_log.get("semantic_fixture") == fixture, "identity log semantic fixture mismatch")

    pipeline = receipt.get("pipeline_execution")
    require(isinstance(pipeline, dict), "pipeline execution evidence is missing")
    require(pipeline.get("registered_torch_stage_valid") is True, "registered Torch success is not asserted")
    require(pipeline.get("full_later_stages_run") == [], "receipt overclaims later full stages")
    require(pipeline.get("full_later_stages_not_run") == EXPECTED_NOT_RUN, "later-stage exclusion mismatch")
    claims = receipt.get("claims")
    require(isinstance(claims, dict), "success claims are missing")
    require(claims.get("left_shift_implemented") is True, "left-shift success claim is missing")
    require(claims.get("right_shift_preserved") is True, "right-shift preservation claim is missing")
    require(claims.get("model_contract_changed") is False, "model contract change was claimed")
    require(claims.get("adapter_changed") is False, "adapter change was claimed")


def verify_success_bundles(bundle_root: Path) -> dict[str, Any]:
    bundle_root = bundle_root.resolve()
    manifest = load_json(bundle_root / "manifest.json")
    require(manifest.get("schema") == SUCCESS_SCHEMA, "unsupported success manifest schema")
    require(manifest.get("canonical_files") == SUCCESS_CANONICAL_FILES, "success canonical file set mismatch")
    runs = manifest.get("runs")
    require(isinstance(runs, dict) and sorted(runs) == ["run-1", "run-2"], "exactly two success runs are required")
    verified: dict[str, tuple[dict[str, Any], dict[str, bytes]]] = {}
    for run_name in ("run-1", "run-2"):
        run_root = bundle_root / run_name
        run_manifest = runs[run_name]
        files = run_manifest.get("files")
        require(isinstance(files, dict) and sorted(files) == sorted(SUCCESS_CANONICAL_FILES), f"{run_name}: file set mismatch")
        file_bytes: dict[str, bytes] = {}
        for filename in SUCCESS_CANONICAL_FILES:
            data = (run_root / filename).read_bytes()
            file_bytes[filename] = data
            require(files[filename].get("bytes") == len(data), f"{run_name}: size mismatch for {filename}")
            require(files[filename].get("sha256") == sha256_bytes(data), f"{run_name}: SHA-256 mismatch for {filename}")
        receipt = load_json(run_root / "receipt.json")
        require(run_manifest.get("source_commit") == receipt.get("source_commit") == manifest.get("source_commit"), f"{run_name}: source commit mismatch")
        require(run_manifest.get("receipt_self_hash") == receipt.get("sha256"), f"{run_name}: self-hash manifest mismatch")
        metadata = run_manifest.get("noncanonical_metadata")
        require(isinstance(metadata, dict) and metadata.get("canonical") is False, f"{run_name}: metadata classification mismatch")
        _verify_success_receipt(run_root, receipt, file_bytes)
        verified[run_name] = (receipt, file_bytes)
    first, first_files = verified["run-1"]
    second, second_files = verified["run-2"]
    require(first == second, "success receipts differ")
    for filename in SUCCESS_CANONICAL_FILES:
        require(first_files[filename] == second_files[filename], f"success runs differ at {filename}")
    expected = manifest.get("expected_comparison")
    require(isinstance(expected, dict) and expected.get("byte_identical") is True, "byte identity expectation is missing")
    require(expected.get("receipt_file_sha256") == sha256_bytes(first_files["receipt.json"]), "success receipt file SHA-256 mismatch")
    require(expected.get("receipt_self_hash") == first.get("sha256"), "success receipt self-hash mismatch")
    require(expected.get("artifact_archive_sha256") == sha256_bytes(first_files["torch-artifact.mlir.gz"]), "success artifact archive SHA-256 mismatch")
    top = manifest.get("success_receipt")
    require(isinstance(top, dict), "top-level success receipt binding is missing")
    top_path = ROOT / str(top.get("path", ""))
    require(top_path.is_file(), "top-level success receipt is missing")
    top_bytes = top_path.read_bytes()
    require(top.get("bytes") == len(top_bytes), "top-level success receipt size mismatch")
    require(top.get("file_sha256") == sha256_bytes(top_bytes) == sha256_bytes(first_files["receipt.json"]), "top-level success receipt SHA-256 mismatch")
    require(top.get("self_sha256") == first.get("sha256"), "top-level success receipt self-hash mismatch")
    require(top_bytes == first_files["receipt.json"], "top-level success receipt differs from captures")
    return {
        "source_commit": manifest["source_commit"],
        "runs": ["run-1", "run-2"],
        "byte_identical": True,
        "status": first["status"],
        "artifact_bytes": first["artifact"]["bytes"],
        "artifact_sha256": first["artifact"]["sha256"],
        "receipt_file_sha256": expected["receipt_file_sha256"],
        "receipt_self_hash": expected["receipt_self_hash"],
        "task_identity_count": len(first["identity_bindings"]),
    }


def main() -> None:
    default_bundle = (
        ROOT
        / "artifacts/comparison/tinystories-1m-exact-left-shift-success-determinism"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_success_bundles(args.bundle_dir), indent=2, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
