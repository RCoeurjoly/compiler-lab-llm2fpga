#!/usr/bin/env python3
"""Execute the exact signed-si64 shift fixture through pinned compiler tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "tinystories-1m-exact-shift-executor-results-v1"
EXPECTED_STAGE_SHA256 = "e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674"
EXPECTED_FIXTURE_FILE_SHA256 = "2aadecfedbbf93a617890d21586d17456f945028d866c368c15af754471f3064"
EXPECTED_TOOL_SHA256 = "e1445e7540ef7bea2c29e5f36af8f0120e7b13f8fe0e78b01a21d2a0b7a8d9a9"
EXPECTED_MLIR_OPT_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
EXPECTED_MLIR_RUNNER_SHA256 = "d501573e86911cb0b21f0ad307ea641431d5daf46b8f6b2a914888ca537f1d79"
EXPECTED_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)
TORCH_BACKEND_PIPELINE = "torch-backend-to-linalg-on-tensors-backend-pipeline"
LINALG_TO_LLVM_PIPELINE = [
    "--empty-tensor-to-alloc-tensor",
    "--one-shot-bufferize=bufferize-function-boundaries",
    "--convert-bufferization-to-memref",
    "--linalg-generalize-named-ops",
    "--convert-linalg-to-loops",
    "--lower-affine",
    "--convert-scf-to-cf",
    "--expand-strided-metadata",
    "--finalize-memref-to-llvm",
    "--convert-index-to-llvm",
    "--convert-arith-to-llvm",
    "--convert-math-to-llvm",
    "--convert-cf-to-llvm",
    "--convert-func-to-llvm",
    "--reconcile-unrealized-casts",
]
EXPECTED_CASE_IDS = {
    "shift_one",
    "shift_zero",
    "shift_sixty_two",
    "negative_shift",
    "shift_greater_than_sixty_two",
}
INVALID_CONTRACTS = {
    -1: ("rejected_negative_shift", "shift_contract:negative_shift"),
    63: (
        "rejected_shift_greater_than_sixty_two",
        "shift_contract:greater_than_sixty_two",
    ),
}


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def load_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "executor_fixture_object")
    require(value.get("schema") == "tinystories-1m-exact-shift-semantics-v1", "executor_fixture_schema")
    without_hash = dict(value)
    fixture_hash = without_hash.pop("sha256", None)
    require(fixture_hash == canonical_sha256(without_hash), "executor_fixture_self_hash")
    valid_cases = value.get("valid_cases")
    invalid_cases = value.get("invalid_cases")
    require(isinstance(valid_cases, list) and isinstance(invalid_cases, list), "executor_fixture_cases")
    cases = valid_cases + invalid_cases
    require(all(isinstance(case, dict) for case in cases), "executor_fixture_case_object")
    ids = [case.get("id") for case in cases]
    require(all(isinstance(case_id, str) for case_id in ids), "executor_fixture_case_id")
    require(len(ids) == len(set(ids)), "executor_fixture_case_duplicate")
    require(set(ids) == EXPECTED_CASE_IDS, "executor_fixture_case_set")
    require(sha256_file(path) == EXPECTED_FIXTURE_FILE_SHA256, "executor_fixture_file_hash")
    return value


def resolve_bound_tool(name: str, expected_sha256: str) -> Path:
    resolved = shutil.which(name)
    require(resolved is not None, f"executor_{name.replace('-', '_')}_missing")
    path = Path(str(resolved)).resolve()
    require(path.is_file(), f"executor_{name.replace('-', '_')}_missing")
    require(sha256_file(path) == expected_sha256, f"executor_{name.replace('-', '_')}_binary_hash")
    return path


def validate_bindings(stage: Path, fixture: Path, tool: Path, pipeline: str) -> tuple[Path, Path]:
    require(stage.is_file(), "executor_stage_artifact_missing")
    require(sha256_file(stage) == EXPECTED_STAGE_SHA256, "executor_stage_artifact_hash")
    stage_text = stage.read_text(encoding="utf-8")
    require("torch.aten.bitwise_right_shift.Tensor_Scalar" not in stage_text, "executor_stage_scalar_shift")
    require("torch.aten.bitwise_right_shift.Tensor" in stage_text, "executor_stage_registered_right_shift")
    require(fixture.is_file(), "executor_fixture_missing")
    require(tool.is_file() and tool.name == "torch-mlir-opt", "executor_tool_identity")
    require(sha256_file(tool) == EXPECTED_TOOL_SHA256, "executor_tool_binary_hash")
    require(pipeline == EXPECTED_PIPELINE, "executor_pipeline")
    mlir_opt = resolve_bound_tool("mlir-opt", EXPECTED_MLIR_OPT_SHA256)
    mlir_runner = resolve_bound_tool("mlir-runner", EXPECTED_MLIR_RUNNER_SHA256)
    return mlir_opt, mlir_runner


def validate_tensor(case: dict[str, Any]) -> tuple[list[int], list[int], int]:
    tensor = case.get("input")
    require(isinstance(tensor, dict), f"executor_input:{case.get('id')}")
    require(tensor.get("dtype") == "si64", f"executor_input_dtype:{case.get('id')}")
    shape = tensor.get("shape")
    values = tensor.get("values")
    shift = case.get("shift")
    require(
        isinstance(shape, list)
        and len(shape) == 1
        and isinstance(shape[0], int)
        and shape[0] > 0,
        f"executor_input_shape:{case.get('id')}",
    )
    require(
        isinstance(values, list)
        and len(values) == shape[0]
        and all(isinstance(value, int) and -(1 << 63) <= value < (1 << 63) for value in values),
        f"executor_input_values:{case.get('id')}",
    )
    require(isinstance(shift, int), f"executor_shift:{case.get('id')}")
    return shape, values, shift


def torch_module(case: dict[str, Any], result_index: int | None = None) -> str:
    shape, values, shift = validate_tensor(case)
    extent = shape[0]
    dense_values = ", ".join(str(value) for value in values)
    if result_index is None:
        result_type = f"!torch.vtensor<[{extent}],si64>"
        result_operations = ""
        result_name = "%out"
    else:
        require(0 <= result_index < extent, f"executor_result_index:{case.get('id')}")
        result_type = "!torch.int"
        result_operations = f"""    %dim = torch.constant.int 0
    %index = torch.constant.int {result_index}
    %selected = torch.aten.select.int %out, %dim, %index : !torch.vtensor<[{extent}],si64>, !torch.int, !torch.int -> !torch.vtensor<[],si64>
    %scalar = torch.aten.item %selected : !torch.vtensor<[],si64> -> !torch.int
"""
        result_name = "%scalar"
    return f"""module {{
  func.func @main() -> {result_type} {{
    %input = torch.vtensor.literal(dense<[{dense_values}]> : tensor<{extent}xsi64>) : !torch.vtensor<[{extent}],si64>
    %shift = torch.constant.int {shift}
    %out = torch.operator \"torch.aten.bitwise_right_shift.Tensor_Scalar\"(%input, %shift) : (!torch.vtensor<[{extent}],si64>, !torch.int) -> !torch.vtensor<[{extent}],si64>
{result_operations}    return {result_name} : {result_type}
  }}
}}
"""


def run_compiler(command: list[str], source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, input=source, capture_output=True, text=True)


def execute_lowered_tensor(
    linalg_source: str, mlir_opt: Path, mlir_runner: Path
) -> tuple[int, str, str]:
    lowered = run_compiler(
        [str(mlir_opt), *LINALG_TO_LLVM_PIPELINE],
        linalg_source,
    )
    require(lowered.returncode == 0, "executor_native_lowering_failed")
    require("llvm.func @main() -> i64" in lowered.stdout, "executor_native_lowering_missing_main")
    require("llvm.ashr" in lowered.stdout, "executor_native_arithmetic_shift")
    executed = run_compiler(
        [str(mlir_runner), "-e", "main", "--entry-point-result=i64"],
        lowered.stdout,
    )
    require(executed.returncode == 0, "executor_native_execution_failed")
    stdout = executed.stdout.strip()
    require(stdout and stdout.lstrip("-").isdigit(), "executor_native_output")
    return int(stdout), lowered.stdout, executed.stdout


def execute_valid_case(
    case: dict[str, Any], tool: Path, pipeline: str, mlir_opt: Path, mlir_runner: Path
) -> dict[str, Any]:
    shape, values, shift = validate_tensor(case)
    require(0 <= shift <= 62, f"executor_valid_shift:{case.get('id')}")
    outputs: list[int] = []
    torch_modules: list[str] = []
    frontend_outputs: list[str] = []
    linalg_outputs: list[str] = []
    native_modules: list[str] = []
    runner_outputs: list[str] = []
    for result_index in range(len(values)):
        module = torch_module(case, result_index)
        frontend = run_compiler([str(tool), f"-pass-pipeline={pipeline}"], module)
        require(frontend.returncode == 0, f"executor_frontend_failed:{case.get('id')}")
        require(
            "torch.aten.bitwise_right_shift.Tensor_Scalar" not in frontend.stdout
            and "torch.aten.bitwise_right_shift.Tensor" in frontend.stdout,
            f"executor_frontend_lowering:{case.get('id')}",
        )
        linalg = run_compiler(
            [str(tool), f"--{TORCH_BACKEND_PIPELINE}"],
            frontend.stdout,
        )
        require(linalg.returncode == 0, f"executor_linalg_failed:{case.get('id')}")
        require(
            "arith.shrsi" in linalg.stdout
            and "torch.aten.bitwise_right_shift" not in linalg.stdout,
            f"executor_arithmetic_lowering:{case.get('id')}",
        )
        output, native_module, runner_output = execute_lowered_tensor(
            linalg.stdout, mlir_opt, mlir_runner
        )
        outputs.append(output)
        torch_modules.append(module)
        frontend_outputs.append(frontend.stdout)
        linalg_outputs.append(linalg.stdout)
        native_modules.append(native_module)
        runner_outputs.append(runner_output)
    record = {
        "id": case["id"],
        "status": "ok",
        "output": {"dtype": "si64", "shape": shape, "values": outputs},
        "compiler_evidence": {
            "torch_module_sha256": sha256_text("".join(torch_modules)),
            "torch_frontend_output_sha256": sha256_text("".join(frontend_outputs)),
            "linalg_output_sha256": sha256_text("".join(linalg_outputs)),
            "native_module_sha256": sha256_text("".join(native_modules)),
            "runner_stdout_sha256": sha256_text("".join(runner_outputs)),
        },
    }
    require(record["output"] == case.get("expected"), f"executor_compiler_output_mismatch:{case.get('id')}")
    return record


def execute_invalid_case(case: dict[str, Any], tool: Path, pipeline: str) -> dict[str, Any]:
    _, _, shift = validate_tensor(case)
    require(shift in INVALID_CONTRACTS, f"executor_invalid_shift:{case.get('id')}")
    expected_status, expected_diagnostic = INVALID_CONTRACTS[shift]
    require(case.get("status") == expected_status, f"executor_invalid_status:{case.get('id')}")
    require(case.get("diagnostic") == expected_diagnostic, f"executor_invalid_diagnostic:{case.get('id')}")
    module = torch_module(case)
    rejected = run_compiler([str(tool), f"-pass-pipeline={pipeline}"], module)
    require(rejected.returncode != 0, f"executor_invalid_accepted:{case.get('id')}")
    require(expected_diagnostic in rejected.stderr, f"executor_rejection_diagnostic:{case.get('id')}")
    return {
        "id": case["id"],
        "status": expected_status,
        "diagnostic": expected_diagnostic,
        "compiler_evidence": {
            "torch_module_sha256": sha256_text(module),
            "compiler_exit_code": rejected.returncode,
            "compiler_stderr_sha256": sha256_text(rejected.stderr),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-artifact", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--pass-pipeline", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    tool = args.tool.resolve()
    mlir_opt, mlir_runner = validate_bindings(
        args.stage_artifact.resolve(), args.fixture.resolve(), tool, args.pass_pipeline
    )
    cases = [
        execute_valid_case(case, tool, args.pass_pipeline, mlir_opt, mlir_runner)
        for case in fixture["valid_cases"]
    ]
    cases.extend(
        execute_invalid_case(case, tool, args.pass_pipeline) for case in fixture["invalid_cases"]
    )
    report = {
        "schema": SCHEMA,
        "stage_artifact_sha256": sha256_file(args.stage_artifact),
        "fixture_file_sha256": sha256_file(args.fixture),
        "tool_binary_sha256": sha256_file(tool),
        "pipeline_sha256": canonical_sha256(args.pass_pipeline),
        "compiler_route": {
            "torch_backend_pipeline": TORCH_BACKEND_PIPELINE,
            "linalg_to_llvm_pipeline": LINALG_TO_LLVM_PIPELINE,
            "mlir_opt": {"binary": str(mlir_opt), "binary_sha256": sha256_file(mlir_opt)},
            "mlir_runner": {
                "binary": str(mlir_runner),
                "binary_sha256": sha256_file(mlir_runner),
            },
        },
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
