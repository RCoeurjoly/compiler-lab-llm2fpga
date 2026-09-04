#!/usr/bin/env python3
"""Extract the authenticated TinyStories flat-SCF memref blocker contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
REGISTERED_CLASSES = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
REGISTERED_SET = frozenset(REGISTERED_CLASSES)
DEFAULT_CAPTURE = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1"
)
DEFAULT_CONTRACT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
)
DEFAULT_REPRODUCERS = ROOT / "reproducers/tinystories-1m-exact-flat-scf-memref"
ALIAS_ATTRIBUTE = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-flat-scf"
REPRESENTATIVE_ROOT = "reproducers/tinystories-1m-exact-flat-scf-memref"
TASK1_COMMIT = "99f0b6c109d92b6deef8878c8ce296a5f2a05108"
C22_COMMIT = "c22c5f8d85e453a56b185f6238970933f5b1d407"
RUNTIME_SOURCE = "/nix/store/amahjznxmsx37q7x7lazjkf5253syc56-llm2fpga-pipeline-runtime-scripts"
RUNTIME_NAR_HASH = "sha256-v5VXxWwTVtwgGT1BTZ4nE02jtK+hW623ptAOA+0Wdsg="
FROZEN_MODEL = "tiny-stories-1m-kev-gpt-exact"
RECEIPT_SCHEMA = "tinystories-1m-exact-current-pipeline-frontier-v5"
CANONICAL_RECEIPT_COMMIT = TASK1_COMMIT
CANONICAL_RECEIPT_PATH = (
    "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/"
    "run-1/receipt.json"
)
CANONICAL_RECEIPT_BLOB = "f1add36875bcf403f9ba7bce3f11ca29ef11f641"
CANONICAL_RECEIPT_SHA256 = "6af348b82f2e263980f0515f46b0a08c14898118d7e868cacfec3764ceae6acf"
PINNED_TOOL = {
    "path": "/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt",
    "bytes": 496904,
    "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
}
FROZEN_IDENTITIES = {
    "adapter_sha256": "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e",
    "contract_sha256": "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c",
    "package_manifest_sha256": "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35",
    "task_1_audit_file_sha256": "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd",
    "task_1_audit_payload_sha256": "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766",
    "task_2_artifact_file_sha256": "173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a",
    "task_2_artifact_sha256": "af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838",
    "task_2_model_receipt_sha256": "5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834",
    "task_3_generation_artifact_sha256": "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3",
    "task_3_generation_file_sha256": "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3",
    "task_3_generation_result_sha256": "c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644",
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def _mask_line(line: str) -> str:
    result: list[str] = []
    quoted = False
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted:
            result.append(" ")
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            index += 1
            continue
        if char == '"':
            quoted = True
            result.append(" ")
            index += 1
            continue
        if char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            result.extend(" " * (len(line) - index))
            break
        result.append(char)
        index += 1
    return "".join(result)


def _balanced_end(text: str, start: int, opening: str, closing: str) -> int:
    if start >= len(text) or text[start] != opening:
        raise ValueError(f"expected {opening!r}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index + 1
            if depth < 0:
                break
    raise ValueError(f"unbalanced {opening}{closing} metadata")


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _consume(text: str, index: int, literal: str) -> int:
    index = _skip_space(text, index)
    if not text.startswith(literal, index):
        raise ValueError(f"expected {literal!r} in memref operation")
    return index + len(literal)


def _consume_group(text: str, index: int, opening: str, closing: str) -> tuple[str, int]:
    index = _skip_space(text, index)
    end = _balanced_end(text, index, opening, closing)
    return text[index:end], end


def _consume_memref_type(text: str, index: int) -> tuple[str, int]:
    index = _skip_space(text, index)
    if not text.startswith("memref<", index):
        raise ValueError("expected memref type")
    end = _balanced_end(text, index + len("memref"), "<", ">")
    return text[index:end], end


def _split_top_level(text: str, delimiter: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{", ">": "<"}
    openings = set(pairs.values())
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in openings:
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                raise ValueError("malformed nested metadata")
        elif char == delimiter and not stack:
            pieces.append(text[start:index].strip())
            start = index + 1
    if stack or quoted:
        raise ValueError("malformed nested metadata")
    pieces.append(text[start:].strip())
    return pieces


def _static_or_dynamic_list(group: str, dynamic_map: dict[str, str]) -> list[Any]:
    if not (group.startswith("[") and group.endswith("]")):
        raise ValueError("malformed static/dynamic metadata list")
    body = group[1:-1].strip()
    if not body:
        return []
    result: list[Any] = []
    for token in _split_top_level(body, ","):
        if re.fullmatch(r"-?[0-9]+", token):
            result.append(int(token))
        elif re.fullmatch(r"%[A-Za-z0-9_.$-]+", token):
            if token not in dynamic_map:
                dynamic_map[token] = f"%dynamic{len(dynamic_map)}"
            result.append(dynamic_map[token])
        else:
            raise ValueError(f"malformed static/affine metadata token: {token!r}")
    return result


def _reassociation(group: str) -> list[list[int]]:
    if not (group.startswith("[") and group.endswith("]")):
        raise ValueError("malformed reassociation")
    body = group[1:-1].strip()
    if not body:
        return []
    result = []
    for item in _split_top_level(body, ","):
        values: list[Any] = _static_or_dynamic_list(item, {})
        if not all(isinstance(value, int) and value >= 0 for value in values):
            raise ValueError("reassociation indices must be nonnegative integers")
        result.append(values)
    return result


def _identity_strides(shape: list[Any]) -> list[Any]:
    strides: list[Any] = [0] * len(shape)
    stride: Any = 1
    for index in range(len(shape) - 1, -1, -1):
        strides[index] = stride
        dimension = shape[index]
        if not isinstance(dimension, int) or not isinstance(stride, int):
            stride = "?"
        else:
            stride *= dimension
    return strides


def parse_memref_type(type_text: str) -> dict[str, Any]:
    if not type_text.startswith("memref<") or not type_text.endswith(">"):
        raise ValueError(f"malformed memref type: {type_text}")
    body = type_text[len("memref<") : -1]
    pieces = _split_top_level(body, ",")
    if len(pieces) > 2:
        raise ValueError(f"unsupported memref type fields: {type_text}")
    shaped = pieces[0]
    tokens = shaped.split("x")
    if len(tokens) < 2:
        raise ValueError(f"unranked or malformed memref type: {type_text}")
    element = tokens[-1]
    if not re.fullmatch(r"(?:i[0-9]+|f[0-9]+|index)", element):
        raise ValueError(f"unsupported memref element type: {element}")
    shape: list[Any] = []
    for token in tokens[:-1]:
        if token == "?":
            shape.append("?")
        elif re.fullmatch(r"[0-9]+", token):
            shape.append(int(token))
        else:
            raise ValueError(f"malformed memref dimension: {token}")
    layout = "identity"
    offset: Any = 0
    strides: list[Any] = _identity_strides(shape)
    if len(pieces) == 2:
        layout = pieces[1]
        match = re.fullmatch(
            r"strided<\[([^]]*)\](?:,\s*offset:\s*(-?[0-9]+|\?))?>", layout
        )
        if match is None:
            raise ValueError(f"malformed or unsupported memref layout: {layout}")
        stride_tokens = [item.strip() for item in match.group(1).split(",")]
        if len(stride_tokens) != len(shape):
            raise ValueError("strided layout rank mismatch")
        strides = []
        for token in stride_tokens:
            if token == "?":
                strides.append("?")
            elif re.fullmatch(r"-?[0-9]+", token):
                strides.append(int(token))
            else:
                raise ValueError("malformed strided layout")
        raw_offset = match.group(2)
        offset = 0 if raw_offset is None else ("?" if raw_offset == "?" else int(raw_offset))
    return {
        "text": type_text,
        "rank": len(shape),
        "shape": shape,
        "element_type": element,
        "layout": layout,
        "offset": offset,
        "strides": strides,
    }


def _expect_end(text: str, index: int) -> str | None:
    remainder = text[_skip_space(text, index) :]
    if not remainder:
        return None
    if re.fullmatch(r'loc\("(?:[^"\\]|\\.)+":\d+:\d+\)', remainder):
        return remainder
    raise ValueError(f"unexpected operation suffix: {remainder!r}")


def _validate_shape_operation(signature: dict[str, Any]) -> None:
    source = signature["operand_memrefs"][0]
    result = signature["result_memrefs"][0]
    reassociation = signature["reassociation"]
    expected_indices = list(range(source["rank"]))
    if signature["operation"] == "memref.expand_shape":
        expected_indices = list(range(result["rank"]))
        if len(reassociation) != source["rank"]:
            raise ValueError("expand_shape reassociation/source rank mismatch")
    elif len(reassociation) != result["rank"]:
        raise ValueError("collapse_shape reassociation/result rank mismatch")
    flattened = [value for group in reassociation for value in group]
    if flattened != expected_indices or any(not group for group in reassociation):
        raise ValueError("malformed affine reassociation indices")

    if signature["operation"] == "memref.collapse_shape":
        for group, result_dimension in zip(reassociation, result["shape"]):
            dimensions = [source["shape"][index] for index in group]
            if all(isinstance(value, int) for value in [*dimensions, result_dimension]):
                product = 1
                for value in dimensions:
                    product *= value
                if product != result_dimension:
                    raise ValueError("collapse_shape static shape mismatch")
    else:
        output_shape = signature["output_shape"]
        if len(output_shape) != result["rank"]:
            raise ValueError("expand_shape output_shape/result rank mismatch")
        for declared, dimension in zip(output_shape, result["shape"]):
            if isinstance(declared, int) and isinstance(dimension, int) and declared != dimension:
                raise ValueError("expand_shape static output_shape mismatch")
        for source_dimension, group in zip(source["shape"], reassociation):
            dimensions = [output_shape[index] for index in group]
            if all(isinstance(value, int) for value in [source_dimension, *dimensions]):
                product = 1
                for value in dimensions:
                    product *= value
                if product != source_dimension:
                    raise ValueError("expand_shape static shape product mismatch")


def parse_operation_text(operation: str, text: str) -> dict[str, Any]:
    normalized = " ".join(part.strip() for part in text.splitlines() if part.strip())
    dynamic_map: dict[str, str] = {}
    op_index = normalized.find(operation)
    if op_index < 0:
        raise ValueError(f"operation {operation} missing")
    prefix = normalized[:op_index].strip()
    result_name = None
    if prefix:
        match = re.fullmatch(r"(%[A-Za-z0-9_.$-]+)\s*=", prefix)
        if match is None:
            raise ValueError("malformed operation result")
        result_name = match.group(1)
    index = op_index + len(operation)
    signature: dict[str, Any] = {"operation": operation}

    if operation == "memref.copy":
        if result_name is not None:
            raise ValueError("memref.copy must not have a result")
        index = _skip_space(normalized, index)
        operand_match = re.match(
            r"(%[A-Za-z0-9_.$-]+)\s*,\s*(%[A-Za-z0-9_.$-]+)", normalized[index:]
        )
        if operand_match is None:
            raise ValueError("malformed memref.copy operands")
        index += operand_match.end()
        index = _consume(normalized, index, ":")
        source_type, index = _consume_memref_type(normalized, index)
        index = _consume(normalized, index, "to")
        target_type, index = _consume_memref_type(normalized, index)
        mlir_location = _expect_end(normalized, index)
        source = parse_memref_type(source_type)
        target = parse_memref_type(target_type)
        if source["shape"] != target["shape"] or source["element_type"] != target["element_type"]:
            raise ValueError("memref.copy source/target shape or element mismatch")
        signature.update(
            operand_types=[source_type, target_type],
            result_types=[],
            operand_memrefs=[source, target],
            result_memrefs=[],
            dynamic_operands=[],
        )
    else:
        if result_name is None:
            raise ValueError(f"{operation} must have one result")
        index = _skip_space(normalized, index)
        operand_match = re.match(r"%[A-Za-z0-9_.$-]+", normalized[index:])
        if operand_match is None:
            raise ValueError(f"malformed {operation} source operand")
        index += operand_match.end()
        if operation == "memref.reinterpret_cast":
            index = _consume(normalized, index, "to")
            index = _consume(normalized, index, "offset:")
            offset_group, index = _consume_group(normalized, index, "[", "]")
            index = _consume(normalized, index, ",")
            index = _consume(normalized, index, "sizes:")
            sizes_group, index = _consume_group(normalized, index, "[", "]")
            index = _consume(normalized, index, ",")
            index = _consume(normalized, index, "strides:")
            strides_group, index = _consume_group(normalized, index, "[", "]")
            index = _consume(normalized, index, ":")
            source_type, index = _consume_memref_type(normalized, index)
            index = _consume(normalized, index, "to")
            result_type, index = _consume_memref_type(normalized, index)
            mlir_location = _expect_end(normalized, index)
            source = parse_memref_type(source_type)
            result = parse_memref_type(result_type)
            offset = _static_or_dynamic_list(offset_group, dynamic_map)
            sizes = _static_or_dynamic_list(sizes_group, dynamic_map)
            strides = _static_or_dynamic_list(strides_group, dynamic_map)
            if len(offset) != 1 or len(sizes) != result["rank"] or len(strides) != result["rank"]:
                raise ValueError("reinterpret_cast static metadata rank mismatch")
            for declared, dimension in zip(sizes, result["shape"]):
                if isinstance(declared, int) and isinstance(dimension, int) and declared != dimension:
                    raise ValueError("reinterpret_cast static size/result mismatch")
            signature.update(offset=offset, sizes=sizes, strides=strides)
        else:
            reassociation_group, index = _consume_group(normalized, index, "[", "]")
            reassociation = _reassociation(reassociation_group)
            signature["reassociation"] = reassociation
            if operation == "memref.expand_shape":
                index = _consume(normalized, index, "output_shape")
                output_group, index = _consume_group(normalized, index, "[", "]")
                signature["output_shape"] = _static_or_dynamic_list(output_group, dynamic_map)
            index = _consume(normalized, index, ":")
            source_type, index = _consume_memref_type(normalized, index)
            index = _consume(normalized, index, "into")
            result_type, index = _consume_memref_type(normalized, index)
            mlir_location = _expect_end(normalized, index)
            source = parse_memref_type(source_type)
            result = parse_memref_type(result_type)
        signature.update(
            operand_types=[source_type],
            result_types=[result_type],
            operand_memrefs=[source],
            result_memrefs=[result],
            dynamic_operands=list(dynamic_map.values()),
        )
        if operation in {"memref.collapse_shape", "memref.expand_shape"}:
            _validate_shape_operation(signature)
    return {"signature": signature, "mlir_location": mlir_location}


def _operation_on_line(masked: str) -> tuple[str, int] | None:
    matches = []
    for operation in REGISTERED_CLASSES:
        for match in re.finditer(rf"(?<![A-Za-z0-9_.]){re.escape(operation)}(?![A-Za-z0-9_.])", masked):
            matches.append((match.start(), operation))
    if not matches:
        return None
    matches.sort()
    if len(matches) != 1:
        raise ValueError("multiple registered operations on one MLIR line")
    column, operation = matches[0]
    return operation, column


def parse_registered_operations(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    operations: list[dict[str, Any]] = []
    current_function: str | None = None
    index = 0
    while index < len(lines):
        masked = _mask_line(lines[index])
        function_match = re.search(r"\bfunc\.func\s+@([A-Za-z0-9_.$-]+)", masked)
        if function_match:
            current_function = function_match.group(1)
        found = _operation_on_line(masked)
        if found is None:
            index += 1
            continue
        operation, column = found
        start = index
        end = index
        parsed = None
        last_error: Exception | None = None
        while end < len(lines):
            candidate = "\n".join(lines[start : end + 1]).strip()
            try:
                parsed = parse_operation_text(operation, candidate)
            except ValueError as error:
                last_error = error
                end += 1
                if end - start > 32:
                    break
                continue
            following = end + 1
            if following < len(lines) and _mask_line(lines[following]).strip().startswith("loc("):
                end = following
                candidate = "\n".join(lines[start : end + 1]).strip()
                parsed = parse_operation_text(operation, candidate)
            break
        if parsed is None:
            raise ValueError(
                f"cannot parse balanced {operation} operation at line {start + 1}: {last_error}"
            )
        source_location = {
            "line": start + 1,
            "column": column + 1,
            "function": current_function,
            "mlir": parsed["mlir_location"],
        }
        operations.append(
            {
                "operation": operation,
                "text": "\n".join(lines[start : end + 1]).strip(),
                "source_location": source_location,
                "signature": parsed["signature"],
            }
        )
        index = end + 1
    return operations


def verify_blocker_report(operations: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if report.get("stage") != "flat-scf":
        raise ValueError("blocker report stage mismatch")
    blockers = report.get("blockers")
    locations = report.get("locations")
    if not isinstance(blockers, list) or not isinstance(locations, list):
        raise ValueError("malformed blocker report")
    blocker_names = [item.get("op") for item in blockers if isinstance(item, dict)]
    unknown = set(blocker_names) - REGISTERED_SET
    missing = REGISTERED_SET - set(blocker_names)
    if unknown:
        raise ValueError(f"unknown blocker classes: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing blocker classes: {sorted(missing)}")
    actual_counts = {
        operation: sum(item["operation"] == operation for item in operations)
        for operation in REGISTERED_CLASSES
    }
    reported_counts = {item.get("op"): item.get("count") for item in blockers}
    if reported_counts != actual_counts:
        raise ValueError(
            f"blocker count mismatch: reported={reported_counts}, recomputed={actual_counts}"
        )
    reported_locations = sorted(
        (item.get("op"), item.get("line"), item.get("function")) for item in locations
    )
    actual_locations = sorted(
        (
            item["operation"],
            item["source_location"]["line"],
            item["source_location"]["function"],
        )
        for item in operations
    )
    if reported_locations != actual_locations:
        raise ValueError("blocker location mismatch")


def representative_selection_tuple(operation: dict[str, Any]) -> tuple[str, str, str]:
    location = operation["source_location"]
    location_key = json.dumps(
        [
            location.get("function"),
            location.get("line"),
            location.get("column"),
            location.get("mlir"),
        ],
        separators=(",", ":"),
    )
    return (
        operation["operation"],
        canonical_json(operation["signature"]).decode("utf-8"),
        location_key,
    )


def select_representatives(operations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for operation in REGISTERED_CLASSES:
        candidates = [item for item in operations if item["operation"] == operation]
        if not candidates:
            raise ValueError(f"registered blocker class has no representative: {operation}")
        selected[operation] = min(candidates, key=representative_selection_tuple)
    return selected


def _render_list(values: Iterable[Any]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def _render_reassociation(groups: list[list[int]]) -> str:
    return "[" + ", ".join(_render_list(group) for group in groups) + "]"


def render_representative(operation: dict[str, Any]) -> str:
    signature = operation["signature"]
    name = signature["operation"]
    arguments = [f"%source: {signature['operand_types'][0]}"]
    if name == "memref.copy":
        arguments.append(f"%target: {signature['operand_types'][1]}")
    arguments.extend(f"{value}: index" for value in signature["dynamic_operands"])
    if name == "memref.reinterpret_cast":
        body = (
            f"%result = {name} %source to offset: {_render_list(signature['offset'])}, "
            f"sizes: {_render_list(signature['sizes'])}, strides: {_render_list(signature['strides'])} "
            f": {signature['operand_types'][0]} to {signature['result_types'][0]}"
        )
    elif name == "memref.collapse_shape":
        body = (
            f"%result = {name} %source {_render_reassociation(signature['reassociation'])} "
            f": {signature['operand_types'][0]} into {signature['result_types'][0]}"
        )
    elif name == "memref.expand_shape":
        body = (
            f"%result = {name} %source {_render_reassociation(signature['reassociation'])} "
            f"output_shape {_render_list(signature['output_shape'])} "
            f": {signature['operand_types'][0]} into {signature['result_types'][0]}"
        )
    elif name == "memref.copy":
        body = (
            f"{name} %source, %target : {signature['operand_types'][0]} "
            f"to {signature['operand_types'][1]}"
        )
    else:
        raise ValueError(f"unknown representative operation: {name}")
    return (
        "module {\n"
        f"  func.func @representative({', '.join(arguments)}) {{\n"
        f"    {body}\n"
        "    return\n"
        "  }\n"
        "}\n"
    )


def _representative_slug(operation: str) -> str:
    return operation.replace(".", "-").replace("_", "-")


def representative_metadata(operation: dict[str, Any]) -> dict[str, Any]:
    selection = representative_selection_tuple(operation)
    return {
        "schema": "tinystories-1m-exact-memref-representative-v1",
        "operation": operation["operation"],
        "signature": operation["signature"],
        "signature_sha256": sha256_bytes(canonical_json(operation["signature"])),
        "source_location": operation["source_location"],
        "selection_tuple": list(selection),
    }


def render_interestingness_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd -P)"
root="$(cd "$here/../../.." && pwd -P)"
candidate="${1:-$here/input.mlir}"
exec python3 "$root/scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py" \\
  --check-representative "$candidate" --metadata "$here/representative.json"
"""


def summarize_operations(operations: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_representatives(operations)
    classes: dict[str, Any] = {}
    locations = []
    script_bytes = render_interestingness_script().encode("utf-8")
    for name in REGISTERED_CLASSES:
        class_operations = [item for item in operations if item["operation"] == name]
        signatures: dict[str, list[dict[str, Any]]] = {}
        for item in class_operations:
            key = canonical_json(item["signature"]).decode("utf-8")
            signatures.setdefault(key, []).append(item)
            locations.append(
                {
                    "operation": name,
                    **item["source_location"],
                    "signature_sha256": sha256_bytes(canonical_json(item["signature"])),
                }
            )
        signature_entries = []
        for key in sorted(signatures):
            items = signatures[key]
            signature = items[0]["signature"]
            signature_entries.append(
                {
                    "signature": signature,
                    "signature_sha256": sha256_bytes(canonical_json(signature)),
                    "multiplicity": len(items),
                }
            )
        representative = selected[name]
        slug = _representative_slug(name)
        metadata = representative_metadata(representative)
        input_bytes = render_representative(representative).encode("utf-8")
        metadata_bytes = canonical_json(metadata) + b"\n"
        classes[name] = {
            "count": len(class_operations),
            "signatures": signature_entries,
            "representative": {
                "path": f"{REPRESENTATIVE_ROOT}/{slug}/input.mlir",
                "sha256": sha256_bytes(input_bytes),
                "metadata": f"{REPRESENTATIVE_ROOT}/{slug}/representative.json",
                "metadata_sha256": sha256_bytes(metadata_bytes),
                "interestingness_test": f"{REPRESENTATIVE_ROOT}/{slug}/interestingness-test.sh",
                "interestingness_test_sha256": sha256_bytes(script_bytes),
                "selection_tuple": list(representative_selection_tuple(representative)),
                "signature_sha256": metadata["signature_sha256"],
                "source_location": representative["source_location"],
            },
        }
    locations.sort(
        key=lambda item: (
            item["operation"],
            item["function"] or "",
            item["line"],
            item["column"],
            item["signature_sha256"],
        )
    )
    return {"classes": classes, "locations": locations}


def write_representatives(operations: list[dict[str, Any]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, operation in select_representatives(operations).items():
        directory = output / _representative_slug(name)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "input.mlir").write_text(
            render_representative(operation), encoding="utf-8"
        )
        (directory / "representative.json").write_bytes(
            canonical_json(representative_metadata(operation)) + b"\n"
        )
        script = directory / "interestingness-test.sh"
        script.write_text(render_interestingness_script(), encoding="utf-8")
        script.chmod(0o755)


def _resolve_nix_raw(attribute: str, field: str) -> str:
    completed = subprocess.run(
        ["nix", "eval", "--raw", f".#{attribute}.{field}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"cannot resolve registered alias {field}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _git_no_replace_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def canonical_receipt_bytes() -> bytes:
    tree = subprocess.run(
        ["git", "ls-tree", CANONICAL_RECEIPT_COMMIT, "--", CANONICAL_RECEIPT_PATH],
        cwd=ROOT,
        env=_git_no_replace_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    expected = (
        f"100644 blob {CANONICAL_RECEIPT_BLOB}\t{CANONICAL_RECEIPT_PATH}\n"
    ).encode("utf-8")
    if tree.returncode != 0 or tree.stdout != expected:
        raise ValueError("canonical receipt commit/path/blob binding mismatch")
    blob = subprocess.run(
        ["git", "cat-file", "blob", CANONICAL_RECEIPT_BLOB],
        cwd=ROOT,
        env=_git_no_replace_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if blob.returncode != 0 or sha256_bytes(blob.stdout) != CANONICAL_RECEIPT_SHA256:
        raise ValueError("canonical receipt Git blob bytes mismatch")
    return blob.stdout


def _validate_receipt(receipt: dict[str, Any], receipt_bytes: bytes) -> None:
    if receipt_bytes != canonical_receipt_bytes():
        raise ValueError("c22 receipt bytes differ from canonical Git object")
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    if receipt.get("sha256") != sha256_bytes(canonical_json(unsigned)):
        raise ValueError("c22 receipt self-hash mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected c22 receipt schema")
    if receipt.get("model") != FROZEN_MODEL:
        raise ValueError("unexpected c22 receipt model")
    if receipt.get("source_commit") != C22_COMMIT:
        raise ValueError("unexpected c22 source commit")
    if receipt.get("frozen_task_1_through_3_identities") != FROZEN_IDENTITIES:
        raise ValueError("unexpected Task 1--3 identities")
    tool_bindings = [
        binding
        for binding in receipt.get("registered_build_execution", {})
        .get("flat-scf", {})
        .get("derivation_tool_bindings", [])
        if Path(str(binding.get("path", ""))).name == "mlir-opt"
    ]
    if len(tool_bindings) != 1 or {
        key: tool_bindings[0].get(key) for key in ("path", "bytes", "sha256")
    } != PINNED_TOOL:
        raise ValueError("unexpected pinned MLIR tool identity")


def _git_bytes(commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        env=_git_no_replace_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"cannot read runtime proof object {commit}:{relative}: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def _runtime_references() -> list[str]:
    pattern = re.compile(r"\$\{pipelineScripts\}/([^\s\"\\]+)")
    names = {
        Path(match.group(1)).name
        for source in (ROOT / "flake.nix", ROOT / "nix/pipeline.nix")
        for match in pattern.finditer(source.read_text(encoding="utf-8"))
    }
    return sorted(names)


def runtime_equivalence_proof() -> dict[str, Any]:
    names = _runtime_references()
    if len(names) != 29:
        raise ValueError(f"runtime closure count drifted from Task 1 proof: {len(names)}")
    files = []
    for name in names:
        relative = f"scripts/pipeline/{name}"
        workspace = (ROOT / relative).read_bytes()
        task1 = _git_bytes(TASK1_COMMIT, relative)
        c22 = _git_bytes(C22_COMMIT, relative)
        if not (workspace == task1 == c22):
            raise ValueError(f"runtime byte-equivalence proof failed: {relative}")
        files.append(
            {"path": relative, "bytes": len(workspace), "sha256": sha256_bytes(workspace)}
        )
    runtime_source = Path(RUNTIME_SOURCE)
    if not runtime_source.is_dir():
        raise ValueError("Task 1 filtered runtime source is unavailable")
    return {
        "proof": "workspace/task1/c22-git-object-byte-equality",
        "task1_commit": TASK1_COMMIT,
        "c22_commit": C22_COMMIT,
        "file_count": len(files),
        "files": files,
        "filtered_runtime_source": RUNTIME_SOURCE,
        "filtered_runtime_nar_sha256": RUNTIME_NAR_HASH,
    }


def build_contract(
    *,
    flat_scf: Path,
    blockers_path: Path,
    manifest_path: Path,
    receipt_path: Path,
    mlir_opt: Path,
    current_derivation: str,
    current_output: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt_bytes = receipt_path.read_bytes()
    receipt = _load_object(receipt_path, "c22 receipt")
    _validate_receipt(receipt, receipt_bytes)
    manifest = _load_object(manifest_path, "flat-SCF manifest")
    expected_manifest = {
        "artifact": "flat.scf.mlir",
        "blockers": "blockers.json",
        "stage": "flat-scf",
        "status": "completed-with-residuals",
    }
    if manifest != expected_manifest:
        raise ValueError("flat-SCF manifest mismatch")
    operations = parse_registered_operations(flat_scf.read_text(encoding="utf-8"))
    blocker_report = _load_object(blockers_path, "blockers report")
    verify_blocker_report(operations, blocker_report)
    summary = summarize_operations(operations)
    execution = receipt["registered_build_execution"]["flat-scf"]
    c22_output = Path(execution["result"])
    c22_derivation = execution["derivation"]
    if not c22_output.is_dir():
        raise ValueError("retained c22 registered Nix output is unavailable")
    live_paths = {
        "manifest": c22_output / "manifest.json",
        "flat_scf": c22_output / "flat.scf.mlir",
        "blockers": c22_output / "blockers.json",
    }
    captured_paths = {
        "manifest": manifest_path,
        "flat_scf": flat_scf,
        "blockers": blockers_path,
    }
    for key in live_paths:
        if live_paths[key].read_bytes() != captured_paths[key].read_bytes():
            raise ValueError(f"retained c22 live {key} payload differs from capture")
    receipt_binding = file_binding(receipt_path)
    source = {
        "manifest": {"path": str(manifest_path.relative_to(ROOT)), **file_binding(manifest_path)},
        "flat_scf": {"path": str(flat_scf.relative_to(ROOT)), **file_binding(flat_scf)},
        "blockers": {"path": str(blockers_path.relative_to(ROOT)), **file_binding(blockers_path)},
        "c22_receipt": {"path": str(receipt_path.relative_to(ROOT)), **receipt_binding},
    }
    payload: dict[str, Any] = {
        "schema": "tinystories-1m-exact-memref-blockers-v1",
        "status": "authenticated",
        "model": FROZEN_MODEL,
        "registered_classes": list(REGISTERED_CLASSES),
        "source": source,
        "nix": {
            "alias_attribute": ALIAS_ATTRIBUTE,
            "current_derivation": current_derivation,
            "current_output": current_output,
            "current_output_realized": Path(current_output).is_dir(),
            "c22_derivation": c22_derivation,
            "c22_output": str(c22_output),
            "payload_source": "retained-authenticated-c22-output",
            "provenance_residual": (
                "Task 1 changed the filtered-source derivation boundary; the protected "
                "current alias output is unrealized and was not rebuilt"
            ),
        },
        "task1_runtime_equivalence": runtime_equivalence_proof(),
        "receipt_git_anchor": {
            "commit": CANONICAL_RECEIPT_COMMIT,
            "path": CANONICAL_RECEIPT_PATH,
            "blob": CANONICAL_RECEIPT_BLOB,
            "sha256": CANONICAL_RECEIPT_SHA256,
        },
        "tool": {"path": str(mlir_opt), **file_binding(mlir_opt)},
        "c22_receipt_self_sha256": receipt["sha256"],
        "task_1_through_3_identities": receipt["frozen_task_1_through_3_identities"],
        "classes": summary["classes"],
        "locations": summary["locations"],
        "sha256": None,
    }
    payload["sha256"] = sha256_bytes(canonical_json(payload))
    return payload, operations


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flat-scf", type=Path, default=DEFAULT_CAPTURE / "flat.scf.mlir")
    parser.add_argument("--blockers", type=Path, default=DEFAULT_CAPTURE / "blockers.json")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CAPTURE / "minimal-reproducer.json")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_CAPTURE / "receipt.json")
    parser.add_argument("--mlir-opt", type=Path)
    parser.add_argument("--current-derivation")
    parser.add_argument("--current-output")
    parser.add_argument("--out-contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--out-reproducers", type=Path, default=DEFAULT_REPRODUCERS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    current_derivation = args.current_derivation or _resolve_nix_raw(ALIAS_ATTRIBUTE, "drvPath")
    current_output = args.current_output or _resolve_nix_raw(ALIAS_ATTRIBUTE, "outPath")
    receipt = _load_object(args.receipt, "c22 receipt")
    execution = receipt["registered_build_execution"]["flat-scf"]
    if args.mlir_opt is None:
        candidates = [
            Path(binding["path"])
            for binding in execution["derivation_tool_bindings"]
            if Path(binding["path"]).name == "mlir-opt"
        ]
        if len(candidates) != 1:
            raise ValueError("c22 receipt does not bind exactly one mlir-opt")
        args.mlir_opt = candidates[0]
    if {"path": str(args.mlir_opt), **file_binding(args.mlir_opt)} != PINNED_TOOL:
        raise ValueError("extractor MLIR tool differs from frozen c22 tool")
    payload, operations = build_contract(
        flat_scf=args.flat_scf,
        blockers_path=args.blockers,
        manifest_path=args.manifest,
        receipt_path=args.receipt,
        mlir_opt=args.mlir_opt,
        current_derivation=current_derivation,
        current_output=current_output,
    )
    write_representatives(operations, args.out_reproducers)
    args.out_contract.parent.mkdir(parents=True, exist_ok=True)
    args.out_contract.write_bytes(canonical_json(payload) + b"\n")
    counts = {name: payload["classes"][name]["count"] for name in REGISTERED_CLASSES}
    print(json.dumps({"status": "PASS", "counts": counts, "sha256": payload["sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
