#!/usr/bin/env python3
"""Capture the first exact TinyStories frontier after right-shift legalization."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_PATH = ROOT / "scripts/pipeline/classify_tinystories_1m_exact_frontier.py"
CLASSIFIER_SPEC = importlib.util.spec_from_file_location(
    "exact_frontier_capture_base", CLASSIFIER_PATH
)
if CLASSIFIER_SPEC is None or CLASSIFIER_SPEC.loader is None:
    raise RuntimeError(f"cannot load {CLASSIFIER_PATH}")
BASE = importlib.util.module_from_spec(CLASSIFIER_SPEC)
sys.modules[CLASSIFIER_SPEC.name] = BASE
CLASSIFIER_SPEC.loader.exec_module(BASE)

MODEL = "tiny-stories-1m-kev-gpt-exact"
PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)
RIGHT_LOWERING_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=}, "
    "torch-backend-to-linalg-on-tensors-backend-pipeline)"
)
RIGHT_OPERATION = "torch.aten.bitwise_right_shift.Tensor_Scalar"
LEFT_OPERATION = "torch.aten.bitwise_left_shift.Tensor_Scalar"
DIAGNOSTIC = "failed to legalize operation 'torch.operator' that was explicitly marked illegal"
CANONICAL_FILES = [
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
IDENTITIES = {
    "adapter": {
        "path": "TinyStories/model_adapter_exact_package.py",
        "file_sha256": "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e",
    },
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: dict[str, Any]) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


def log_binding(run_dir: Path, filename: str) -> dict[str, Any]:
    path = run_dir / filename
    return {
        "log": filename,
        "log_bytes": path.stat().st_size,
        "log_sha256": sha256_file(path),
    }


def execution_record(
    run_dir: Path,
    filename: str,
    command: list[str],
    completed: subprocess.CompletedProcess[str],
    canonical_command: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "command": canonical_command or shlex.join(command),
        "exit_code": completed.returncode,
        **log_binding(run_dir, filename),
        **extra,
    }


def verify_identities() -> dict[str, Any]:
    bound = json.loads(json.dumps(IDENTITIES))
    for name, binding in bound.items():
        path = ROOT / binding["path"]
        actual = sha256_file(path)
        if actual != binding["file_sha256"]:
            raise RuntimeError(f"{name} file identity changed: {actual}")
        document = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else None
        if name == "task_1" and document["sha256"] != binding["payload_sha256"]:
            raise RuntimeError("Task 1 audit payload identity changed")
        if name == "task_2":
            if document["artifact_sha256"] != binding["artifact_sha256"]:
                raise RuntimeError("Task 2 artifact identity changed")
            if document["identity"]["model_receipt_sha256"] != binding["model_receipt_sha256"]:
                raise RuntimeError("Task 2 model receipt identity changed")
        if name == "task_3":
            if document["artifact_sha256"] != binding["artifact_sha256"]:
                raise RuntimeError("Task 3 artifact identity changed")
            if document["generation"]["result_sha256"] != binding["result_sha256"]:
                raise RuntimeError("Task 3 result identity changed")
    return bound


def one_store_output(result: subprocess.CompletedProcess[str], expected: str) -> Path:
    outputs = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("/nix/store/")
    ]
    if outputs != [expected]:
        raise RuntimeError(f"registered output mismatch: {outputs} != {[expected]}")
    return Path(outputs[0])


def extract_pre_reduce_dump(stderr: str) -> str:
    marker = "IR Dump Before ReduceOpVariants"
    start = stderr.find(marker)
    if start < 0:
        raise RuntimeError("pre-Reduce IR dump marker is missing")
    diagnostic = re.search(
        r"\n[^\n]+:\d+:\d+: error: failed to legalize operation "
        r"'torch\.operator' that was explicitly marked illegal",
        stderr[start:],
    )
    if diagnostic is None:
        raise RuntimeError("cannot delimit pre-Reduce IR dump from diagnostic")
    end = start + diagnostic.start()
    return stderr[start:end]


def capture_run(run_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    run_dir.mkdir(parents=True, exist_ok=False)
    source_commit = BASE._run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    identity_bindings = verify_identities()

    export_attribute = f"{MODEL}-pytorch-exported"
    torch_attribute = f"{MODEL}-torch"
    export_derivation = BASE._derivation(ROOT, export_attribute)
    torch_derivation = BASE._derivation(ROOT, torch_attribute)
    tool_derivation = BASE._derivation(ROOT, "torchMlir")
    source_identity = BASE._authenticate_pipeline_source(
        ROOT, export_derivation, torch_derivation
    )

    export_command = [
        "nix", "build", "--no-link", "--print-out-paths", "-L", f".#{export_attribute}"
    ]
    export_log = run_dir / "pytorch-exported-build.log"
    export_result = BASE._run_and_log(export_command, cwd=ROOT, log=export_log)
    if export_result.returncode != 0:
        raise RuntimeError("authenticated export failed; no later command may run")
    export_output = one_store_output(export_result, str(export_derivation["output"]))
    exported_program = export_output / "exported.pt2"
    if not exported_program.is_file() or exported_program.stat().st_size == 0:
        raise RuntimeError("authenticated ExportedProgram is missing")

    torch_command = [
        "nix", "build", "--no-link", "--print-out-paths", "-L", f".#{torch_attribute}"
    ]
    torch_log = run_dir / "torch-mlir.log"
    torch_result = BASE._run_and_log(torch_command, cwd=ROOT, log=torch_log)
    if torch_result.returncode == 0:
        raise RuntimeError("registered Torch stage unexpectedly succeeded")
    if DIAGNOSTIC not in torch_log.read_text(encoding="utf-8"):
        raise RuntimeError("registered Torch stage did not report the compiler frontier")

    capture = BASE._capture_compiler_failure(
        ROOT, run_dir, exported_program, torch_derivation
    )
    capture["log"] = "compiler-import-capture.log"
    capture["operation"] = LEFT_OPERATION
    full_archive = run_dir / "full-failing-ir.mlir.gz"
    with gzip.open(full_archive, "rb") as stream:
        full_bytes = stream.read()
    full_text = full_bytes.decode("utf-8")
    raw_right_count = full_text.count(RIGHT_OPERATION)
    raw_left_count = full_text.count(LEFT_OPERATION)
    if raw_right_count <= 0 or raw_left_count <= 0:
        raise RuntimeError("full failing input lost the right/left shift transition")
    original_left_signature = (
        'torch.operator "torch.aten.bitwise_left_shift.Tensor_Scalar"'
        '(%65, %int16_289) : (!torch.vtensor<[4,64],si64>, !torch.int) '
        '-> !torch.vtensor<[4,64],si64>'
    )
    if original_left_signature not in full_text:
        raise RuntimeError("full failing input lost the original left-shift op/types")

    tool = Path(str(capture["torch_mlir_opt"]))
    if not tool.is_file() or sha256_file(tool) != capture["torch_mlir_opt_sha256"]:
        raise RuntimeError("captured Torch-MLIR binary identity is inconsistent")
    if not str(tool).startswith(str(tool_derivation["output"]) + "/"):
        raise RuntimeError("captured binary is not from the patched tool derivation")

    with tempfile.TemporaryDirectory(prefix="exact-successor-pre-reduce-") as temporary:
        temporary_path = Path(temporary)
        full_ir = temporary_path / "full-failing-ir.mlir"
        full_ir.write_bytes(full_bytes)
        pre_reduce_command = [
            str(tool),
            "-mlir-disable-threading",
            "-mlir-print-ir-before=torch-reduce-op-variants",
            f"-pass-pipeline={PIPELINE}",
            str(full_ir),
            "-o",
            "/dev/null",
        ]
        pre_reduce_log = run_dir / "pre-reduce-op-variants.log"
        pre_reduce_result = BASE._run_and_log(
            pre_reduce_command,
            cwd=ROOT,
            log=pre_reduce_log,
            ephemeral_paths={str(temporary_path): "<capture-tmp>"},
        )
        if pre_reduce_result.returncode == 0:
            raise RuntimeError("full failing input unexpectedly passed the backend pipeline")
        pre_reduce_dump = extract_pre_reduce_dump(pre_reduce_result.stderr)
        pre_right_count = pre_reduce_dump.count(RIGHT_OPERATION)
        pre_left_count = pre_reduce_dump.count(LEFT_OPERATION)
        if pre_right_count != 0:
            raise RuntimeError("generic right shift remains before ReduceOpVariants")
        if pre_left_count != raw_left_count:
            raise RuntimeError(
                f"left-shift count changed before ReduceOpVariants: {pre_left_count} != {raw_left_count}"
            )
        if LEFT_OPERATION not in pre_reduce_result.stderr or DIAGNOSTIC not in pre_reduce_result.stderr:
            raise RuntimeError("new earliest left-shift diagnostic is not content-bound")

        interesting = ROOT / "reproducers/tinystories-1m-exact-torch-mlir/interesting-left-shift.sh"
        reproducer = ROOT / "reproducers/tinystories-1m-exact-torch-mlir/bitwise-left-shift-tensor-scalar.mlir"
        interesting_environment = {**os.environ, "TORCH_MLIR_OPT": str(tool)}
        full_interesting_command = [str(interesting), str(full_ir)]
        full_interesting = BASE._run_and_log(
            full_interesting_command,
            cwd=ROOT,
            log=run_dir / "interesting-full.log",
            environment=interesting_environment,
            ephemeral_paths={str(temporary_path): "<capture-tmp>"},
        )
        if full_interesting.returncode != 0:
            raise RuntimeError("full failing input lost left-shift interestingness")
        reproducer_command = [str(interesting), str(reproducer)]
        reproducer_interesting = BASE._run_and_log(
            reproducer_command,
            cwd=ROOT,
            log=run_dir / "interesting-reproducer.log",
            environment=interesting_environment,
        )
        if reproducer_interesting.returncode != 0:
            raise RuntimeError("minimal left-shift reproducer is not interesting")

    right_reproducer = ROOT / "reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir"
    lowering_command = [
        str(tool),
        f"-pass-pipeline={RIGHT_LOWERING_PIPELINE}",
        str(right_reproducer),
    ]
    lowering_result = BASE._run_and_log(
        lowering_command, cwd=ROOT, log=run_dir / "right-shift-lowering.log"
    )
    if lowering_result.returncode != 0 or "arith.shrsi" not in lowering_result.stdout:
        raise RuntimeError("runtime right-shift lowering lost arith.shrsi")
    if RIGHT_OPERATION in lowering_result.stdout:
        raise RuntimeError("runtime right-shift lowering retained the generic operator")

    historical_receipt = ROOT / "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"
    historical = json.loads(historical_receipt.read_text(encoding="utf-8"))
    patch = ROOT / "patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch"
    torch_nix = ROOT / "torch-mlir.nix"
    producer = Path(__file__).resolve()
    verifier = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py"

    executions = {
        "pytorch-exported": execution_record(
            run_dir,
            "pytorch-exported-build.log",
            export_command,
            export_result,
            result=str(export_output),
            derivation=str(export_derivation["path"]),
            derivation_file_sha256=str(export_derivation["file_sha256"]),
            derivation_json_sha256=str(export_derivation["json_sha256"]),
        ),
        "torch-mlir": execution_record(
            run_dir,
            "torch-mlir.log",
            torch_command,
            torch_result,
            result=None,
            derivation=str(torch_derivation["path"]),
            derivation_file_sha256=str(torch_derivation["file_sha256"]),
            derivation_json_sha256=str(torch_derivation["json_sha256"]),
        ),
        "compiler-import-capture": capture,
        "pre-reduce-op-variants": execution_record(
            run_dir,
            "pre-reduce-op-variants.log",
            pre_reduce_command,
            pre_reduce_result,
            canonical_command=BASE._canonicalize_execution_text(
                shlex.join(pre_reduce_command), {str(full_ir.parent): "<capture-tmp>"}
            ),
        ),
        "interesting-full": execution_record(
            run_dir,
            "interesting-full.log",
            full_interesting_command,
            full_interesting,
            canonical_command=BASE._canonicalize_execution_text(
                shlex.join(full_interesting_command), {str(full_ir.parent): "<capture-tmp>"}
            ),
        ),
        "interesting-reproducer": execution_record(
            run_dir,
            "interesting-reproducer.log",
            reproducer_command,
            reproducer_interesting,
        ),
        "right-shift-lowering": execution_record(
            run_dir,
            "right-shift-lowering.log",
            lowering_command,
            lowering_result,
        ),
    }
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-successor-frontier-receipt-v1",
        "model": MODEL,
        "source_commit": source_commit,
        "status": "compiler_frontier",
        "frontier": "torch_mlir_frontier",
        "stage": "torch-mlir",
        "operation": LEFT_OPERATION,
        "diagnostic": DIAGNOSTIC,
        "historical_frontier": {
            "path": str(historical_receipt.relative_to(ROOT)),
            "file_sha256": sha256_file(historical_receipt),
            "self_sha256": historical["sha256"],
            "operation": RIGHT_OPERATION,
            "preserved": True,
        },
        "identity_bindings": identity_bindings,
        "pipeline_source_identity": source_identity,
        "compiler": {
            "torch_mlir_source_revision": "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
            "tool_derivation": str(tool_derivation["path"]),
            "tool_derivation_file_sha256": str(tool_derivation["file_sha256"]),
            "tool_derivation_json_sha256": str(tool_derivation["json_sha256"]),
            "tool_output": str(tool_derivation["output"]),
            "binary": str(tool),
            "binary_sha256": sha256_file(tool),
            "version": str(capture["torch_mlir_version"]),
            "patch": str(patch.relative_to(ROOT)),
            "patch_sha256": sha256_file(patch),
            "nix_expression": str(torch_nix.relative_to(ROOT)),
            "nix_expression_sha256": sha256_file(torch_nix),
            "producer": str(producer.relative_to(ROOT)),
            "producer_sha256": sha256_file(producer),
            "verifier": str(verifier.relative_to(ROOT)),
            "verifier_sha256": sha256_file(verifier),
        },
        "executions": executions,
        "full_failing_ir": {
            "archive": "full-failing-ir.mlir.gz",
            "archive_bytes": full_archive.stat().st_size,
            "archive_sha256": sha256_file(full_archive),
            "content_bytes": len(full_bytes),
            "content_sha256": sha256_bytes(full_bytes),
            "raw_torch_operator_count": full_text.count("torch.operator "),
            "raw_right_shift_count": raw_right_count,
            "raw_left_shift_count": raw_left_count,
            "pre_reduce_right_shift_count": pre_right_count,
            "pre_reduce_left_shift_count": pre_left_count,
            "pre_reduce_ir_sha256": sha256_bytes(pre_reduce_dump.encode("utf-8")),
        },
        "minimal_reproducer": {
            "path": str(reproducer.relative_to(ROOT)),
            "bytes": reproducer.stat().st_size,
            "sha256": sha256_file(reproducer),
            "operation": LEFT_OPERATION,
            "input_type": "!torch.vtensor<[4,64],si64>",
            "scalar_type": "!torch.int",
            "result_type": "!torch.vtensor<[4,64],si64>",
            "constant": 16,
            "original_operation_and_types_preserved": True,
            "interestingness_test": str(interesting.relative_to(ROOT)),
            "interestingness_test_sha256": sha256_file(interesting),
            "full_verified": True,
            "reproducer_verified": True,
        },
        "pipeline_execution": {
            "first_invalid_stage": "torch-mlir",
            "stopped_after_first_invalid_stage": True,
            "not_run": ["linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"],
        },
        "claims": {
            "left_shift_implemented": False,
            "linalg": False,
            "scf": False,
            "flat_scf": False,
            "calyx": False,
            "systemverilog": False,
            "model_contract_changed": False,
        },
    }
    receipt["sha256"] = canonical_hash(receipt)
    (run_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata = {
        "canonical": False,
        "receipt_captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_seconds_approximate": round(time.monotonic() - started),
    }
    (run_dir / "noncanonical-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def finalize(bundle_root: Path) -> dict[str, Any]:
    runs: dict[str, Any] = {}
    canonical_bytes: dict[str, dict[str, bytes]] = {}
    for run_name in ("run-1", "run-2"):
        run_dir = bundle_root / run_name
        receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
        metadata = json.loads(
            (run_dir / "noncanonical-metadata.json").read_text(encoding="utf-8")
        )
        files: dict[str, Any] = {}
        canonical_bytes[run_name] = {}
        for filename in CANONICAL_FILES:
            data = (run_dir / filename).read_bytes()
            canonical_bytes[run_name][filename] = data
            files[filename] = {"bytes": len(data), "sha256": sha256_bytes(data)}
        runs[run_name] = {
            "source_commit": receipt["source_commit"],
            "receipt_self_hash": receipt["sha256"],
            "files": files,
            "commands": {
                name: record["command"] for name, record in receipt["executions"].items()
            },
            "exit_codes": {
                name: record["exit_code"] for name, record in receipt["executions"].items()
            },
            "noncanonical_metadata": metadata,
        }
    for filename in CANONICAL_FILES:
        if canonical_bytes["run-1"][filename] != canonical_bytes["run-2"][filename]:
            raise RuntimeError(f"independent successor captures differ at {filename}")
    first_receipt = json.loads(canonical_bytes["run-1"]["receipt.json"])
    if first_receipt != json.loads(canonical_bytes["run-2"]["receipt.json"]):
        raise RuntimeError("independent successor receipts differ")
    manifest = {
        "schema": "tinystories-1m-exact-successor-frontier-determinism-bundles-v1",
        "source_commit": first_receipt["source_commit"],
        "canonical_files": CANONICAL_FILES,
        "runs": runs,
        "expected_comparison": {
            "byte_identical": True,
            "receipt_file_sha256": sha256_bytes(canonical_bytes["run-1"]["receipt.json"]),
            "receipt_self_hash": first_receipt["sha256"],
            "full_failing_ir_sha256": sha256_bytes(
                canonical_bytes["run-1"]["full-failing-ir.mlir.gz"]
            ),
        },
    }
    successor_receipt = (
        bundle_root.parent / "tinystories-1m-exact-successor-frontier.json"
    )
    successor_receipt.write_bytes(canonical_bytes["run-1"]["receipt.json"])
    manifest["successor_receipt"] = {
        "path": str(successor_receipt.relative_to(ROOT)),
        "bytes": successor_receipt.stat().st_size,
        "file_sha256": sha256_file(successor_receipt),
        "self_sha256": first_receipt["sha256"],
    }
    (bundle_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
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
