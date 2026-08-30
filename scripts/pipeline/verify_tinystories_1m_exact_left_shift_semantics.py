#!/usr/bin/env python3
"""Verify the authenticated signed-si64 Tensor_Scalar left-shift contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DEFAULT = ROOT / "artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json"
SCHEMA = "tinystories-1m-exact-left-shift-semantics-v1"
VALID_CASE_IDS = (
    "shift_zero",
    "model_observed_shift_sixteen",
    "negative_operand",
    "positive_high_bit_wrap",
    "negative_high_bit_discard",
    "shift_sixty_two",
)
INVALID_CASES = {
    "negative_count": ("rejected_negative_shift", "shift_contract:negative_shift"),
    "count_sixty_three": (
        "rejected_shift_greater_than_sixty_two",
        "shift_contract:greater_than_sixty_two",
    ),
    "dynamic_count": ("rejected_dynamic_shift", "shift_contract:dynamic_shift"),
    "si32_rejection": ("rejected_unsupported_dtype", "shift_contract:unsupported_dtype"),
}
MASK64 = (1 << 64) - 1


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"invalid_object:{path}")
    return value


def flatten_values(values: object, shape: object, diagnostic: str) -> list[int]:
    require(isinstance(shape, list) and shape and all(isinstance(x, int) and x > 0 for x in shape), diagnostic)

    def walk(value: object, dimensions: list[int]) -> list[int]:
        if not dimensions:
            require(isinstance(value, int) and not isinstance(value, bool), diagnostic)
            return [value]
        require(isinstance(value, list) and len(value) == dimensions[0], diagnostic)
        return [element for child in value for element in walk(child, dimensions[1:])]

    return walk(values, shape)


def unflatten(values: list[int], shape: list[int]) -> object:
    if len(shape) == 1:
        return values
    width = 1
    for dimension in shape[1:]:
        width *= dimension
    return [unflatten(values[offset : offset + width], shape[1:]) for offset in range(0, len(values), width)]


def independent_left_shift(value: int, count: int) -> int:
    unsigned = value & MASK64
    shifted = (unsigned << count) & MASK64
    return shifted - (1 << 64) if shifted & (1 << 63) else shifted


def _verify_task_identity(task: dict[str, Any], root: Path, name: str) -> None:
    path = root / str(task.get("path"))
    require(path.is_file(), f"{name}_path")
    require(sha256_file(path) == task.get("file_sha256"), f"{name}_file_hash")
    value = load_object(path)
    if name == "task1":
        require(value.get("sha256") == task.get("payload_sha256"), "task1_payload_hash")
    elif name == "task2":
        require(value.get("artifact_sha256") == task.get("artifact_sha256"), "task2_artifact_hash")
        require(
            value.get("identity", {}).get("model_receipt_sha256") == task.get("model_receipt_sha256"),
            "task2_model_receipt_hash",
        )
    else:
        require(value.get("artifact_sha256") == task.get("artifact_sha256"), "task3_artifact_hash")
        require(
            value.get("generation", {}).get("result_sha256") == task.get("result_sha256"),
            "task3_result_hash",
        )


def _verify_provenance(fixture: dict[str, Any], root: Path) -> None:
    provenance = fixture.get("provenance")
    require(isinstance(provenance, dict), "provenance")
    adapter = provenance.get("adapter")
    reproducer = provenance.get("reproducer")
    receipt_ref = provenance.get("successor_receipt")
    identities = provenance.get("task_identities")
    require(isinstance(adapter, dict), "adapter")
    require(isinstance(reproducer, dict), "reproducer")
    require(isinstance(receipt_ref, dict), "successor_receipt")
    require(isinstance(identities, dict), "task_identities")
    adapter_path = root / str(adapter.get("path"))
    reproducer_path = root / str(reproducer.get("path"))
    receipt_path = root / str(receipt_ref.get("path"))
    require(adapter_path.is_file() and sha256_file(adapter_path) == adapter.get("file_sha256"), "adapter_file_hash")
    require(
        reproducer_path.is_file() and sha256_file(reproducer_path) == reproducer.get("file_sha256"),
        "reproducer_file_hash",
    )
    require(receipt_path.is_file() and sha256_file(receipt_path) == receipt_ref.get("file_sha256"), "successor_receipt_file_hash")
    receipt = load_object(receipt_path)
    receipt_without_hash = dict(receipt)
    receipt_hash = receipt_without_hash.pop("sha256", None)
    require(receipt_hash == canonical_sha256(receipt_without_hash), "successor_receipt_self_hash")
    require(receipt_hash == receipt_ref.get("self_sha256"), "successor_receipt_binding")
    minimal = receipt.get("minimal_reproducer")
    bindings = receipt.get("identity_bindings")
    require(isinstance(minimal, dict) and isinstance(bindings, dict), "successor_receipt_structure")
    require(minimal.get("path") == reproducer.get("path"), "successor_reproducer_path")
    require(minimal.get("sha256") == reproducer.get("file_sha256"), "successor_reproducer_hash")
    require(bindings.get("adapter", {}).get("file_sha256") == adapter.get("file_sha256"), "successor_adapter_hash")
    _verify_task_identity(identities.get("task_1", {}), root, "task1")
    _verify_task_identity(identities.get("task_2", {}), root, "task2")
    _verify_task_identity(identities.get("task_3", {}), root, "task3")
    require(bindings.get("task_1") == identities.get("task_1"), "successor_task1_binding")
    require(bindings.get("task_2") == identities.get("task_2"), "successor_task2_binding")
    require(bindings.get("task_3") == identities.get("task_3"), "successor_task3_binding")


def _verify_valid_case(case: dict[str, Any], torch: Any) -> None:
    case_id = str(case.get("id"))
    input_value = case.get("input")
    expected = case.get("expected")
    shift = case.get("shift")
    require(isinstance(input_value, dict) and isinstance(expected, dict), f"{case_id}:value")
    require(input_value.get("dtype") == "si64", f"{case_id}:input_dtype")
    require(expected.get("dtype") == "si64", f"{case_id}:expected_dtype")
    shape = input_value.get("shape")
    require(shape == expected.get("shape"), f"{case_id}:shape_preservation")
    require(isinstance(shift, int) and not isinstance(shift, bool) and 0 <= shift <= 62, f"{case_id}:shift_range")
    input_values = flatten_values(input_value.get("values"), shape, f"{case_id}:input_shape")
    expected_values = flatten_values(expected.get("values"), shape, f"{case_id}:expected_shape")
    require(all(-(1 << 63) <= value < (1 << 63) for value in input_values), f"{case_id}:input_range")
    independent = [independent_left_shift(value, shift) for value in input_values]
    require(independent == expected_values, f"{case_id}:independent_arithmetic")
    require(canonical_sha256(expected) == case.get("expected_sha256"), f"{case_id}:expected_hash")
    input_tensor = torch.tensor(input_value["values"], dtype=torch.int64)
    observed = torch.bitwise_left_shift(input_tensor, shift)
    require(observed.dtype == torch.int64, f"{case_id}:pytorch_dtype")
    require(list(observed.shape) == shape, f"{case_id}:pytorch_shape")
    require(observed.tolist() == unflatten(expected_values, shape), f"{case_id}:pytorch_output")


def _verify_invalid_case(case: dict[str, Any]) -> None:
    case_id = str(case.get("id"))
    expected = INVALID_CASES.get(case_id)
    require(expected is not None, f"invalid_case_id:{case_id}")
    require(case.get("classification") == "compiler_contract", f"{case_id}:classification")
    require(case.get("status") == expected[0], f"{case_id}:status")
    require(case.get("diagnostic") == expected[1], f"{case_id}:diagnostic")
    require("expected" not in case and "expected_sha256" not in case and "pytorch_output" not in case, f"{case_id}:output_forbidden")
    input_value = case.get("input")
    require(isinstance(input_value, dict), f"{case_id}:input")
    flatten_values(input_value.get("values"), input_value.get("shape"), f"{case_id}:input_shape")
    if case_id == "dynamic_count":
        require(case.get("shift") == {"kind": "dynamic"}, "dynamic_count:shift")
    elif case_id == "negative_count":
        require(case.get("shift") == -1, "negative_count:shift")
    elif case_id == "count_sixty_three":
        require(case.get("shift") == 63, "count_sixty_three:shift")
    else:
        require(input_value.get("dtype") == "si32" and case.get("shift") == 1, "si32_rejection:input")


def verify_object(fixture: dict[str, Any], root: Path = ROOT) -> dict[str, object]:
    fixture_without_hash = dict(fixture)
    fixture_hash = fixture_without_hash.pop("sha256", None)
    require(fixture.get("schema") == SCHEMA, "fixture_schema")
    require(fixture_hash == canonical_sha256(fixture_without_hash), "fixture_self_hash")
    _verify_provenance(fixture, root)
    try:
        import torch
    except ImportError as error:
        raise ValueError("pytorch_unavailable") from error
    pytorch = fixture.get("provenance", {}).get("pytorch")
    require(isinstance(pytorch, dict), "pytorch_provenance")
    torch_file = Path(torch.__file__).resolve()
    require(torch.__version__ == pytorch.get("version"), "pytorch_version")
    require(str(torch_file) == pytorch.get("module_file"), "pytorch_module_file")
    require(sha256_file(torch_file) == pytorch.get("module_file_sha256"), "pytorch_module_file_hash")
    require(pytorch.get("operator") == "torch.bitwise_left_shift", "pytorch_operator")
    valid_cases = fixture.get("valid_cases")
    invalid_cases = fixture.get("invalid_cases")
    require(isinstance(valid_cases, list) and isinstance(invalid_cases, list), "fixture_cases")
    require(tuple(case.get("id") for case in valid_cases if isinstance(case, dict)) == VALID_CASE_IDS, "valid_case_ids")
    require(tuple(case.get("id") for case in invalid_cases if isinstance(case, dict)) == tuple(INVALID_CASES), "invalid_case_ids")
    require(len(valid_cases) == len(VALID_CASE_IDS) and len(invalid_cases) == len(INVALID_CASES), "fixture_case_count")
    for case in valid_cases:
        require(isinstance(case, dict), "valid_case_object")
        _verify_valid_case(case, torch)
    for case in invalid_cases:
        require(isinstance(case, dict), "invalid_case_object")
        _verify_invalid_case(case)
    return {
        "status": "accepted",
        "fixture_self_hash": fixture_hash,
        "valid_case_count": len(valid_cases),
        "invalid_case_count": len(invalid_cases),
    }


def verify(path: Path = FIXTURE_DEFAULT) -> dict[str, object]:
    return verify_object(load_object(path), ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=FIXTURE_DEFAULT)
    args = parser.parse_args()
    print(json.dumps(verify(args.fixture), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
