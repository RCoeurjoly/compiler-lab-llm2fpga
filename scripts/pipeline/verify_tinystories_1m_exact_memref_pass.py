#!/usr/bin/env python3
"""Independently verify and replay the exact static-memref-pass evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
)
EVIDENCE_ROOT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evidence"
)
CONTRACT_PATH = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
)
TASK2_VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
TASK2_EXTRACTOR = ROOT / "scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
CLASSIFICATIONS = {
    "eliminated", "preserved", "rewritten_equivalent", "new_invalid"
}
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
TOOL = {
    "path": "/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt",
    "bytes": 496904,
    "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
}
PLUGIN = {
    "path": (
        "/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-"
        "llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so"
    ),
    "bytes": 21714240,
    "sha256": "6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744",
}
TOP_LEVEL_COMMON_KEYS = {
    "schema", "status", "model", "pipeline", "task2_contract", "input",
    "tool", "plugin", "python", "provenance", "task_1_through_3_identities",
    "executions", "representatives", "semantic_probes", "complete", "decision",
    "sha256",
}
RUN_KEYS = {
    "sequence", "id", "kind", "operation", "command", "input", "input_after",
    "exit_code", "elapsed_ns", "stdout", "stderr", "output", "parse_check",
    "parseable",
}
PARSE_CHECK_KEYS = {"command", "exit_code", "stdout", "stderr"}
COMPLETE_KEYS = {
    "parseable", "before", "after", "signature_mappings",
    "new_invalid_signatures", "unknown_blocker_classes", "invariant_status",
}
COMPLETE_PHASE_KEYS = {
    "operation_census", "blocker_counts", "registered_operation_count",
}
EARLIEST_KEYS = {
    "operation", "signature_sha256", "classification", "signature",
    "source_location", "diagnostic", "reproducer",
}
REPRODUCER_KEYS = {"path", "bytes", "sha256", "operation_count", "metadata"}
METADATA_KEYS = {
    "operation", "signature", "signature_sha256", "classification", "selection",
    "execution",
}
METADATA_EXECUTION_KEYS = {
    "command", "exit_code", "elapsed_ns", "output_created", "stdout", "stderr",
    "output",
}
BINDING_KEYS = {"path", "bytes", "sha256"}


def _expected_provenance(contract: dict[str, Any]) -> dict[str, Any]:
    nix = contract["nix"]
    return {
        "payload_source": nix["payload_source"],
        "c22_derivation": nix["c22_derivation"],
        "c22_output": nix["c22_output"],
        "current_alias_derivation": nix["current_derivation"],
        "current_alias_output": nix["current_output"],
        "current_alias_realized": nix["current_output_realized"],
        "unrealized_current_alias_residual": nix["provenance_residual"],
    }


def _contract_signature(contract: dict[str, Any], name: str) -> dict[str, Any]:
    representative = contract["classes"][name]["representative"]
    signature = json.loads(representative["selection_tuple"][1])
    _require(
        _digest(_canonical(signature)) == representative["signature_sha256"],
        f"representative binding signature mismatch for {name}",
    )
    return signature


def _expected_probe_text(contract: dict[str, Any], name: str) -> str:
    signature = _contract_signature(contract, name)
    operands, results = signature["operand_types"], signature["result_types"]
    if name == "memref.collapse_shape":
        operation = f"    %view = memref.collapse_shape %source [[0, 1], [2]] : {operands[0]} into {results[0]}\n"
        indices = "%i0, %i1"
        arguments = f"%source: {operands[0]}, %i0: index, %i1: index"
        access_type = results[0]
    elif name == "memref.copy":
        operation = f"    memref.copy %source, %target : {operands[0]} to {operands[1]}\n"
        constants = "    %c0 = arith.constant 0 : index\n"
        indices = "%c0"
        arguments = f"%source: {operands[0]}, %target: {operands[1]}"
        access_type = operands[1]
    elif name == "memref.expand_shape":
        operation = f"    %view = memref.expand_shape %source [[0, 1]] output_shape [1, 1] : {operands[0]} into {results[0]}\n"
        constants = "    %c0 = arith.constant 0 : index\n"
        indices = "%c0, %c0"
        arguments = f"%source: {operands[0]}"
        access_type = results[0]
    elif name == "memref.reinterpret_cast":
        operation = f"    %view = memref.reinterpret_cast %source to offset: [0], sizes: [1], strides: [1] : {operands[0]} to {results[0]}\n"
        constants = "    %c0 = arith.constant 0 : index\n"
        indices = "%c0"
        arguments = f"%source: {operands[0]}"
        access_type = results[0]
    else:
        raise ValueError(f"unsupported semantic probe operation {name}")
    base = "%target" if name == "memref.copy" else "%view"
    return (
        "module {\n"
        f"  func.func @probe({arguments}) -> i64 {{\n"
        + ("" if name == "memref.collapse_shape" else constants)
        + operation
        + f"    %value = memref.load {base}[{indices}] : {access_type}\n"
        + f"    memref.store %value, {base}[{indices}] : {access_type}\n"
        + "    return %value : i64\n  }\n}\n"
    )


_FUNC_PROBE = re.compile(r"^\s*func\.func @probe\((.*)\) -> i64 \{\s*$")
_FUNC_ARG = re.compile(r"(%[A-Za-z0-9_.$-]+)\s*:\s*(memref<[^>]+>|index)")
_INDEX_CONSTANT = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.constant\s+(-?[0-9]+)\s*:\s*index\s*$")
_INDEX_BINARY = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.(addi|subi|muli)\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:\s*index\s*$")
_VIEW_ALIAS = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*memref\.(?:collapse_shape|expand_shape|reinterpret_cast)\s+(%[A-Za-z0-9_.$-]+)\b")
_LOAD = re.compile(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.load\s+(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_STORE = re.compile(r"^\s*memref\.store\s+%[A-Za-z0-9_.$-]+,\s*(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_COPY = re.compile(r"^\s*memref\.copy\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:")


def _sum_affine(left: dict[str, Any], right: dict[str, Any], factor: int = 1) -> dict[str, Any]:
    return {
        "coefficients": [
            lhs + factor * rhs
            for lhs, rhs in zip(left["coefficients"], right["coefficients"])
        ],
        "offset": left["offset"] + factor * right["offset"],
    }


def _scale_affine(value: dict[str, Any], factor: int) -> dict[str, Any]:
    return {
        "coefficients": [factor * item for item in value["coefficients"]],
        "offset": factor * value["offset"],
    }


def _derive_access_model(
    text: str, parser: Any, *, operation: str, signature: dict[str, Any]
) -> dict[str, Any]:
    logical_shape = (
        signature["operand_memrefs"][1]["shape"]
        if operation == "memref.copy"
        else signature["result_memrefs"][0]["shape"]
    )
    function = next(
        (match for line in text.splitlines() if (match := _FUNC_PROBE.match(line))),
        None,
    )
    if function is None:
        raise ValueError("semantic probe function signature is unavailable")
    arguments = list(_FUNC_ARG.finditer(function.group(1)))
    buffers = [item for item in arguments if item.group(2).startswith("memref<")]
    indices = [item for item in arguments if item.group(2) == "index"]
    variable_dimensions = [
        (dimension, extent)
        for dimension, extent in enumerate(logical_shape)
        if extent > 1
    ]
    if len(indices) != len(variable_dimensions):
        raise ValueError("semantic probe index-variable rank is dynamic or mismatched")
    variables = [
        {
            "name": f"i{variable_dimensions[position][0]}",
            "argument": arguments.index(item), "lower_inclusive": 0,
            "upper_exclusive": variable_dimensions[position][1],
        }
        for position, item in enumerate(indices)
    ]
    count = len(variables)
    expressions = {}
    for position, item in enumerate(indices):
        coefficients = [0] * count
        coefficients[position] = 1
        expressions[item.group(1)] = {"coefficients": coefficients, "offset": 0}
    for line in text.splitlines():
        constant = _INDEX_CONSTANT.match(line)
        if constant:
            expressions[constant.group(1)] = {
                "coefficients": [0] * count, "offset": int(constant.group(2))
            }
            continue
        binary = _INDEX_BINARY.match(line)
        if binary is None:
            continue
        left, right = expressions.get(binary.group(3)), expressions.get(binary.group(4))
        if left is None or right is None:
            raise ValueError("semantic probe contains a dynamic index expression")
        if binary.group(2) == "addi":
            value = _sum_affine(left, right)
        elif binary.group(2) == "subi":
            value = _sum_affine(left, right, -1)
        else:
            left_constant = not any(left["coefficients"])
            right_constant = not any(right["coefficients"])
            if not left_constant and not right_constant:
                raise ValueError("semantic probe contains a non-affine multiplication")
            value = _scale_affine(
                right if left_constant else left,
                left["offset"] if left_constant else right["offset"],
            )
        expressions[binary.group(1)] = value

    roles = {0: "source", 1: "target"} if operation == "memref.copy" else {0: "source"}
    buffer_identities = {
        item.group(1): {"argument": arguments.index(item), "role": roles[position]}
        for position, item in enumerate(buffers)
    }
    aliases = {
        match.group(1): match.group(2)
        for line in text.splitlines()
        if (match := _VIEW_ALIAS.match(line))
    }

    def resolve_base(name: str) -> dict[str, Any]:
        while name in aliases:
            name = aliases[name]
        if name not in buffer_identities:
            raise ValueError("semantic probe access base is not a function buffer")
        return buffer_identities[name]

    copy_provenance = None
    for line in text.splitlines():
        copied = _COPY.match(line)
        if copied:
            copy_provenance = {
                "source": resolve_base(copied.group(1)),
                "target": resolve_base(copied.group(2)),
            }
    accesses, memrefs = [], []
    for line in text.splitlines():
        matched, kind = _LOAD.match(line), "load"
        if matched is None:
            matched, kind = _STORE.match(line), "store"
        if matched is None:
            continue
        memref = parser.parse_memref_type(matched.group(3))
        raw_indices = []
        for token in (item.strip() for item in matched.group(2).split(",")):
            expression = expressions.get(token)
            if expression is None:
                raise ValueError("semantic probe contains a dynamic or non-affine index")
            raw_indices.append(copy.deepcopy(expression))
        if len(raw_indices) != memref["rank"]:
            raise ValueError("semantic probe access rank mismatch")
        for expression, dimension in zip(raw_indices, memref["shape"]):
            lower = upper = expression["offset"]
            for coefficient, variable in zip(expression["coefficients"], variables):
                extent = variable["upper_exclusive"] - 1
                lower += min(0, coefficient * extent)
                upper += max(0, coefficient * extent)
            expression["range"] = {
                "lower_inclusive": lower, "upper_exclusive": upper + 1,
                "memref_upper_exclusive": dimension,
                "in_bounds": 0 <= lower and upper < dimension,
            }
        linear = {"coefficients": [0] * count, "offset": memref["offset"]}
        for stride, expression in zip(memref["strides"], raw_indices):
            linear = _sum_affine(linear, _scale_affine(expression, stride))
        sample_values = [
            min(variable["upper_exclusive"] - 1, position + 2)
            for position, variable in enumerate(variables)
        ]
        sample_linear = linear["offset"] + sum(
            coefficient * value
            for coefficient, value in zip(linear["coefficients"], sample_values)
        )
        accesses.append({
            "kind": kind, "base": resolve_base(matched.group(1)),
            "raw_indices": raw_indices, "linear_formula": linear,
            "supplementary_sample": {
                "variables": sample_values, "linear_index": sample_linear,
            },
        })
        memrefs.append(memref)
    if not accesses:
        raise ValueError("semantic probe has no live memory access")
    if operation == "memref.copy" and copy_provenance is None:
        raise ValueError("semantic copy probe lacks source-target provenance")
    element_counts = [__import__("math").prod(item["shape"]) for item in memrefs]
    if len(set(element_counts)) != 1:
        raise ValueError("semantic probe element-count mismatch")
    shape, strides = memrefs[0]["shape"], memrefs[0]["strides"]
    expected_stride, contiguous = 1, True
    for dimension, stride in reversed(list(zip(shape, strides))):
        contiguous = contiguous and stride == expected_stride
        expected_stride *= dimension
    affine_mappings = [
        {"kind": item["kind"], "base": item["base"],
         "linear_formula": item["linear_formula"]}
        for item in accesses
    ]
    return {
        "affine_status": "proven", "index_variables": variables,
        "shape": shape, "strides": strides, "offset": memrefs[0]["offset"],
        "contiguous": contiguous, "element_count": element_counts[0],
        "copy_provenance": copy_provenance,
        "access_maps": accesses, "affine_mappings": affine_mappings,
    }


def _access_model(
    text: str, parser: Any, *, operation: str, signature: dict[str, Any]
) -> dict[str, Any]:
    try:
        return _derive_access_model(
            text, parser, operation=operation, signature=signature
        )
    except ValueError as error:
        return {"affine_status": "unproven", "reason": str(error)}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _binding(path: Path, *, relative: bool = False) -> dict[str, Any]:
    data = path.read_bytes()
    rendered = str(path.relative_to(ROOT)) if relative else str(path)
    return {"path": rendered, "bytes": len(data), "sha256": _digest(data)}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_keys(value: Any, expected: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == expected, f"{label} mismatch")


def _validate_closed_schema(payload: dict[str, Any]) -> None:
    decision = payload.get("decision")
    _require(
        decision in {"compiler_pass_extension", "register_existing_pass"},
        "decision schema mismatch",
    )
    branch_fields = {
        key for key in ("earliest_remaining_signature", "normalized_artifact")
        if key in payload
    }
    expected_branch = (
        {"earliest_remaining_signature"}
        if decision == "compiler_pass_extension"
        else {"normalized_artifact"}
    )
    _require(branch_fields == expected_branch, "decision schema mismatch")
    _require(
        set(payload) - branch_fields == TOP_LEVEL_COMMON_KEYS,
        "top-level schema mismatch",
    )
    _require(payload.get("status") == "evaluated", "status mismatch")
    runs = payload.get("executions")
    _require(isinstance(runs, list), "execution schema mismatch")
    for run in runs:
        _require_keys(run, RUN_KEYS, "execution schema")
        _require_keys(run.get("parse_check"), PARSE_CHECK_KEYS, "parse-check schema")
    _require_keys(payload.get("complete"), COMPLETE_KEYS, "complete schema")
    _require_keys(payload["complete"].get("before"), COMPLETE_PHASE_KEYS, "complete before schema")
    _require_keys(payload["complete"].get("after"), COMPLETE_PHASE_KEYS, "complete after schema")
    if decision == "compiler_pass_extension":
        earliest = payload["earliest_remaining_signature"]
        _require_keys(earliest, EARLIEST_KEYS, "earliest signature schema")
        _require_keys(earliest.get("reproducer"), REPRODUCER_KEYS, "reproducer schema")
        _require_keys(earliest["reproducer"].get("metadata"), BINDING_KEYS, "reproducer metadata binding schema")
    else:
        _require_keys(payload.get("normalized_artifact"), BINDING_KEYS, "normalized artifact schema")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def _load_parser():
    spec = importlib.util.spec_from_file_location("exact_memref_task2_verify", TASK2_EXTRACTOR)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load authenticated Task 2 parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _semantic(signature: dict[str, Any]) -> bytes:
    value = copy.deepcopy(signature)
    value.pop("operand_types", None)
    value.pop("result_types", None)
    for key in ("operand_memrefs", "result_memrefs"):
        for memref in value.get(key, []):
            memref.pop("text", None)
    return _canonical(value)


def _classify(before: dict[str, Any], after: list[dict[str, Any]], valid: bool) -> str:
    if not valid:
        return "new_invalid"
    exact = _canonical(before)
    if any(_canonical(candidate) == exact for candidate in after):
        return "preserved"
    semantic = _semantic(before)
    if any(_semantic(candidate) == semantic for candidate in after):
        return "rewritten_equivalent"
    return "eliminated"


def _mask_line(line: str) -> str:
    result = []
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


_OP_LINE = re.compile(
    r"^\s*(?:[%][^=]+?=\s*)?(?:\([^=]+\)\s*=\s*)?"
    r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*)\b"
)


def _operation_census(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in text.splitlines():
        matched = _OP_LINE.match(_mask_line(raw))
        if matched:
            name = matched.group(1)
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _signature_index(operations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {name: [] for name in REGISTERED}
    seen = {name: set() for name in REGISTERED}
    for operation in operations:
        signature = operation["signature"]
        name = signature["operation"]
        encoded = _canonical(signature)
        if encoded not in seen[name]:
            seen[name].add(encoded)
            result[name].append(signature)
    for signatures in result.values():
        signatures.sort(key=_canonical)
    return result


def _expected_mappings(
    contract: dict[str, Any], operations: list[dict[str, Any]], valid: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    after = _signature_index(operations)
    mappings = []
    exact_before = {name: set() for name in REGISTERED}
    semantic_before = {name: set() for name in REGISTERED}
    for name in REGISTERED:
        for entry in contract["classes"][name]["signatures"]:
            signature = entry["signature"]
            exact_before[name].add(_canonical(signature))
            semantic_before[name].add(_semantic(signature))
            mappings.append(
                {
                    "operation": name,
                    "input_signature_sha256": entry["signature_sha256"],
                    "input_multiplicity": entry["multiplicity"],
                    "classification": _classify(signature, after[name], valid),
                    "output_signature_sha256": [
                        _digest(_canonical(candidate))
                        for candidate in after[name]
                        if _canonical(candidate) == _canonical(signature)
                        or _semantic(candidate) == _semantic(signature)
                    ],
                }
            )
    invalid = []
    for name in REGISTERED:
        for signature in after[name]:
            encoded = _canonical(signature)
            if encoded not in exact_before[name] and _semantic(signature) not in semantic_before[name]:
                invalid.append(
                    {
                        "operation": name,
                        "signature_sha256": _digest(encoded),
                        "reason": "output signature has no exact or shape/layout-equivalent input",
                        "signature": signature,
                    }
                )
    mappings.sort(key=lambda item: (item["operation"], item["input_signature_sha256"]))
    invalid.sort(key=lambda item: (item["operation"], item["signature_sha256"]))
    return mappings, invalid


_SUBVIEW = re.compile(
    r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.subview\s+"
    r"%[A-Za-z0-9_.$-]+\[(?P<offsets>[^]]+)\]\s*"
    r"\[(?P<sizes>[^]]+)\]\s*\[(?P<strides>[^]]+)\]\s*:\s*"
    r"(?P<source>memref<.+>)\s+to\s+(?P<result>memref<.+>)\s*$"
)


def _ints(raw: str) -> list[int]:
    values = []
    for item in raw.split(","):
        token = item.strip()
        _require(bool(re.fullmatch(r"-?[0-9]+", token)), "invalid subview metadata")
        values.append(int(token))
    return values


def _invalid_frontier(stderr: bytes, source: str, parser: Any) -> dict[str, Any]:
    diagnostic = stderr.decode("utf-8", errors="strict")
    location = re.search(r":([0-9]+):([0-9]+): error: ([^\n]+)", diagnostic)
    _require(location is not None, "new invalid diagnostic is missing")
    line = int(location.group(1))
    column = int(location.group(2))
    source_lines = source.splitlines()
    _require(1 <= line <= len(source_lines), "new invalid source location mismatch")
    matched = _SUBVIEW.match(source_lines[line - 1])
    _require(matched is not None, "new invalid operation is not canonical subview")
    _require('"memref.subview"' in diagnostic, "new invalid operation class mismatch")
    _require("expected 1 offset values, got 2" in diagnostic, "new invalid diagnostic mismatch")
    source_type = matched.group("source")
    result_type = matched.group("result")
    signature = {
        "operation": "memref.subview",
        "operand_types": [source_type],
        "result_types": [result_type],
        "operand_memrefs": [parser.parse_memref_type(source_type)],
        "result_memrefs": [parser.parse_memref_type(result_type)],
        "offsets": _ints(matched.group("offsets")),
        "sizes": _ints(matched.group("sizes")),
        "strides": _ints(matched.group("strides")),
    }
    return {
        "operation": "memref.subview",
        "classification": "new_invalid",
        "signature": signature,
        "signature_sha256": _digest(_canonical(signature)),
        "source_location": {"function": "main", "line": line, "column": column, "mlir": None},
        "diagnostic": location.group(3),
        "stderr_sha256": _digest(stderr),
        "reason": (
            "the pass flattened a rank-2 function argument while leaving its "
            "rank-2 memref.subview metadata unchanged"
        ),
    }


def _check_binding(binding: Any, label: str) -> Path:
    _require(isinstance(binding, dict), f"{label} binding missing")
    _require(set(binding) == BINDING_KEYS, f"{label} binding schema mismatch")
    path = Path(str(binding["path"]))
    if not path.is_absolute():
        path = ROOT / path
    _require(path.is_file(), f"{label} evidence unavailable")
    actual = _binding(path, relative=not Path(str(binding["path"])).is_absolute())
    _require(
        all(actual[key] == binding[key] for key in ("path", "bytes", "sha256")),
        f"{label} evidence hash/size mismatch",
    )
    return path


def _check_canonical_binding(binding: Any, path: Path, label: str) -> Path:
    _require(
        binding == _binding(path, relative=True),
        f"canonical evidence path mismatch for {label}",
    )
    return path


def _run_identifier(kind: str, operation: str | None) -> str:
    if kind == "complete" and operation is None:
        return "complete-retained-c22-flat-scf"
    _require(operation in REGISTERED, "canonical run operation mismatch")
    slug = operation.replace(".", "-").replace("_", "-")
    if kind == "representative":
        return slug
    if kind == "semantic_probe":
        return "semantic-" + slug
    raise ValueError("canonical run kind mismatch")


def _check_command(run: dict[str, Any], input_path: Path, output_path: Path) -> None:
    expected = [
        TOOL["path"], str(input_path), f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}", "-o", str(output_path),
    ]
    _require(run.get("command") == expected, "exact pass command mismatch")
    command_text = " ".join(expected).lower().replace("for-calyx", "")
    _require("calyx" not in command_text, "Calyx invocation is forbidden")
    _require("circt-opt" not in command_text, "Calyx invocation is forbidden")


def _replay(run: dict[str, Any], input_path: Path, evidence_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="exact-memref-pass-replay-") as raw:
        output = Path(raw) / "output.mlir"
        command = [
            TOOL["path"], str(input_path), f"--load-pass-plugin={PLUGIN['path']}",
            f"--pass-pipeline={PIPELINE}", "-o", str(output),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
        _require(completed.returncode == run["exit_code"], "replay exit code mismatch")
        _require(completed.stdout == (evidence_dir / "stdout.bin").read_bytes(), "replay stdout mismatch")
        _require(completed.stderr == (evidence_dir / "stderr.bin").read_bytes(), "replay stderr mismatch")
        replay_output = output.read_bytes() if output.exists() else b""
        _require(replay_output == (evidence_dir / "output.mlir").read_bytes(), "replay output mismatch")


def validate_payload(payload: dict[str, Any], root: Path = ROOT, *, replay: bool) -> None:
    _require(root.resolve() == ROOT.resolve(), "verification root mismatch")
    _require(payload.get("schema") == "tinystories-1m-exact-memref-pass-v1", "schema mismatch")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    _require(payload.get("sha256") == _digest(_canonical(unsigned)), "evaluation self-hash mismatch")
    _validate_closed_schema(payload)
    _require(payload.get("pipeline") == PIPELINE, "pipeline mismatch")
    _require(payload.get("tool") == TOOL, "tool identity mismatch")
    _require(payload.get("plugin") == PLUGIN, "plugin identity mismatch")
    _require(_binding(Path(TOOL["path"])) == TOOL, "tool bytes mismatch")
    _require(_binding(Path(PLUGIN["path"])) == PLUGIN, "plugin bytes mismatch")
    _require(_digest(CONTRACT_PATH.read_bytes()) == CONTRACT_SHA256, "Task 2 contract bytes mismatch")
    _require(payload.get("task2_contract") == _binding(CONTRACT_PATH, relative=True), "Task 2 contract binding mismatch")
    contract = _load_object(CONTRACT_PATH, "Task 2 contract")
    _require(payload.get("model") == contract["model"], "model mismatch")
    _require(
        payload.get("task_1_through_3_identities")
        == contract["task_1_through_3_identities"],
        "Task 1--3 identities mismatch",
    )
    _require(payload.get("provenance") == _expected_provenance(contract), "provenance mismatch")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    _require(_digest(flat_scf.read_bytes()) == FLAT_SCF_SHA256, "input SHA-256 mismatch")
    _require(payload.get("input") == _binding(flat_scf, relative=True), "input SHA-256 mismatch")
    parser = _load_parser()
    runs = payload.get("executions")
    _require(isinstance(runs, list) and len(runs) == 9, "representative order is incomplete")
    _require([run.get("sequence") for run in runs] == list(range(1, 10)), "representative order sequence mismatch")
    _require([run.get("operation") for run in runs[:4]] == list(REGISTERED), "representative order mismatch")
    _require(all(run.get("kind") == "representative" for run in runs[:4]), "representative order kind mismatch")
    _require([run.get("operation") for run in runs[4:8]] == list(REGISTERED), "semantic probe order mismatch")
    _require(all(run.get("kind") == "semantic_probe" for run in runs[4:8]), "semantic probe order kind mismatch")
    _require(runs[8].get("kind") == "complete" and runs[8].get("operation") is None, "representative order complete mismatch")

    expected_kinds_operations = (
        [("representative", name) for name in REGISTERED]
        + [("semantic_probe", name) for name in REGISTERED]
        + [("complete", None)]
    )
    expected_ids = [
        _run_identifier(kind, operation)
        for kind, operation in expected_kinds_operations
    ]
    _require(
        [run.get("id") for run in runs] == expected_ids,
        "canonical run id mismatch",
    )
    evidence_dirs = [EVIDENCE_ROOT / identifier for identifier in expected_ids]

    expected_inputs = []
    for name in REGISTERED:
        representative = contract["classes"][name]["representative"]
        path = ROOT / representative["path"]
        actual = _binding(path, relative=True)
        _require(
            actual["sha256"] == representative["sha256"],
            f"representative binding mismatch for {name}",
        )
        expected_inputs.append(path)
    for name in REGISTERED:
        slug = "semantic-" + name.replace(".", "-").replace("_", "-")
        path = EVIDENCE_ROOT / slug / "input.mlir"
        _require(path.is_file(), f"semantic probe input unavailable for {name}")
        _require(
            path.read_text(encoding="utf-8") == _expected_probe_text(contract, name),
            f"semantic probe input mismatch for {name}",
        )
        expected_inputs.append(path)
    expected_inputs.append(flat_scf)

    for index, run in enumerate(runs):
        expected_input = expected_inputs[index]
        evidence_dir = evidence_dirs[index]
        binding_label = "representative binding" if index < 4 else "unchanged input identity"
        _require(run.get("input") == _binding(expected_input, relative=True), f"{binding_label} mismatch")
        _require(run.get("input_after") == run.get("input"), "unchanged input identity mismatch")
        _require(isinstance(run.get("elapsed_ns"), int) and run["elapsed_ns"] > 0, "elapsed time invalid")
        if index < 8:
            _require(run.get("exit_code") == 0, "representative pass execution failed")
            _require(run.get("parseable") is True, "representative parseable output required")
        else:
            expected_parseable = (
                run.get("exit_code") == 0
                and run.get("parse_check", {}).get("exit_code") == 0
            )
            _require(run.get("parseable") is expected_parseable, "complete parseable status mismatch")
        output_path = _check_canonical_binding(
            run.get("output"), evidence_dir / "output.mlir", f"{run['id']} output"
        )
        _check_canonical_binding(
            run.get("stdout"), evidence_dir / "stdout.bin", f"{run['id']} stdout"
        )
        _check_canonical_binding(
            run.get("stderr"), evidence_dir / "stderr.bin", f"{run['id']} stderr"
        )
        _check_canonical_binding(
            run.get("parse_check", {}).get("stdout"),
            evidence_dir / "parse.stdout.bin", f"{run['id']} parse stdout",
        )
        _check_canonical_binding(
            run.get("parse_check", {}).get("stderr"),
            evidence_dir / "parse.stderr.bin", f"{run['id']} parse stderr",
        )
        _require(run.get("parse_check", {}).get("exit_code") == 0, "parse exit mismatch")
        _check_command(run, expected_input, output_path)
        parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
        _require(run["parse_check"].get("command") == parse_command, "parse command mismatch")
        parsed = subprocess.run(
            parse_command,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        _require(parsed.returncode == run["parse_check"]["exit_code"], "parse exit mismatch")
        _require(parsed.stdout == (evidence_dir / "parse.stdout.bin").read_bytes(), "parse stdout mismatch")
        _require(parsed.stderr == (evidence_dir / "parse.stderr.bin").read_bytes(), "parse stderr mismatch")

    trusted_python = Path(sys.executable).resolve()
    _require(
        payload.get("python") == _binding(trusted_python),
        "python interpreter binding mismatch",
    )

    representatives = payload.get("representatives")
    _require(
        isinstance(representatives, list) and len(representatives) == 4,
        "representative result set mismatch",
    )
    for index, result in enumerate(representatives):
        name = REGISTERED[index]
        input_path = ROOT / contract["classes"][name]["representative"]["path"]
        input_text = input_path.read_text(encoding="utf-8")
        output_text_rep = (evidence_dirs[index] / "output.mlir").read_text(
            encoding="utf-8"
        )
        before_ops = parser.parse_registered_operations(input_text)
        after_ops = parser.parse_registered_operations(output_text_rep)
        before_counts = {
            operation: sum(1 for item in before_ops if item["operation"] == operation)
            for operation in REGISTERED
        }
        after_counts = {
            operation: sum(1 for item in after_ops if item["operation"] == operation)
            for operation in REGISTERED
        }
        after_signatures = _signature_index(after_ops)[name]
        expected_result = {
            "operation": name,
            "input_signature_sha256": contract["classes"][name]["representative"]["signature_sha256"],
            "classification": _classify(before_ops[0]["signature"], after_signatures, True),
            "parseable": True,
            "before": {
                "operation_census": _operation_census(input_text),
                "blocker_counts": before_counts,
            },
            "after": {
                "operation_census": _operation_census(output_text_rep),
                "blocker_counts": after_counts,
            },
        }
        _require(result == expected_result, "representative census/classification mismatch")

    semantic_probes = payload.get("semantic_probes")
    _require(
        isinstance(semantic_probes, list) and len(semantic_probes) == 4,
        "semantic probe result set mismatch",
    )
    for index, name in enumerate(REGISTERED):
        signature = _contract_signature(contract, name)
        probe_text = _expected_probe_text(contract, name)
        before_model = _access_model(
            probe_text, parser, operation=name, signature=signature
        )
        after_model = _access_model(
            (evidence_dirs[index + 4] / "output.mlir").read_text(encoding="utf-8"),
            parser, operation=name, signature=signature,
        )
        shape_element_count_preserved = (
            before_model["affine_status"] == "proven"
            and after_model["affine_status"] == "proven"
            and
            before_model["element_count"] == after_model["element_count"]
        )
        layout_preserved = (
            before_model["affine_status"] == "proven"
            and after_model["affine_status"] == "proven"
            and before_model["contiguous"] and after_model["contiguous"]
            and before_model["offset"] == after_model["offset"]
        )
        access_maps_preserved = (
            before_model.get("index_variables") == after_model.get("index_variables")
            and before_model.get("affine_mappings") == after_model.get("affine_mappings")
            and before_model.get("copy_provenance") == after_model.get("copy_provenance")
            and all(
                raw["range"]["in_bounds"]
                for model in (before_model, after_model)
                for access in model.get("access_maps", [])
                for raw in access["raw_indices"]
            )
        )
        proven = shape_element_count_preserved and layout_preserved and access_maps_preserved
        expected_probe = {
            "operation": name,
            "execution_id": runs[index + 4]["id"],
            "invariant_status": "proven" if proven else "unproven",
            "before": before_model,
            "after": after_model,
            "checks": {
                "shape_element_count_preserved": shape_element_count_preserved,
                "layout_contiguous_and_offset_preserved": layout_preserved,
                "memory_access_maps_preserved": access_maps_preserved,
                "complete_affine_mapping_preserved": access_maps_preserved,
                "shape_layout_access_equivalent": proven,
            },
        }
        _require(semantic_probes[index] == expected_probe, "semantic probe mismatch")

    complete = payload.get("complete", {})
    _require(complete.get("unknown_blocker_classes") == [], "unknown blocker classes present")
    full_parseable = runs[-1]["parseable"]
    output_text = (
        (evidence_dirs[-1] / "output.mlir").read_text(encoding="utf-8")
        if full_parseable else ""
    )
    operations = parser.parse_registered_operations(output_text)
    if full_parseable:
        expected_after = {
            name: sum(1 for item in operations if item["operation"] == name)
            for name in REGISTERED
        }
        expected_invalid_from_output: list[dict[str, Any]] = []
    else:
        expected_after = {name: None for name in REGISTERED}
        expected_invalid_from_output = [
            _invalid_frontier(
                (evidence_dirs[-1] / "stderr.bin").read_bytes(),
                flat_scf.read_text(encoding="utf-8"),
                parser,
            )
        ]
    _require(complete.get("after", {}).get("blocker_counts") == expected_after, "after blocker census mismatch")
    expected_before = {name: contract["classes"][name]["count"] for name in REGISTERED}
    _require(complete.get("before", {}).get("blocker_counts") == expected_before, "before blocker census mismatch")
    _require(
        complete.get("before", {}).get("operation_census")
        == _operation_census(flat_scf.read_text(encoding="utf-8")),
        "before operation census mismatch",
    )
    _require(
        complete.get("after", {}).get("operation_census")
        == _operation_census(output_text),
        "after operation census mismatch",
    )
    mappings, invalid = _expected_mappings(contract, operations, full_parseable)
    if not full_parseable:
        invalid = expected_invalid_from_output
    _require(complete.get("signature_mappings") == mappings, "per-signature classification mismatch")
    _require(complete.get("new_invalid_signatures") == invalid, "new invalid signatures mismatch")
    expected_invariant_status = (
        "unavailable_due_invalid_output"
        if not full_parseable
        else (
            "proven"
            if not invalid and all(
                item["invariant_status"] == "proven" for item in semantic_probes
            )
            else "unproven"
        )
    )
    _require(
        complete.get("invariant_status") == expected_invariant_status,
        "invariant status mismatch",
    )
    _require(all(item["classification"] in CLASSIFICATIONS for item in mappings), "classification vocabulary mismatch")
    gate = (
        full_parseable
        and all(expected_after[name] == 0 for name in REGISTERED)
        and not invalid
        and not complete["unknown_blocker_classes"]
        and expected_invariant_status == "proven"
    )
    decision = "register_existing_pass" if gate else "compiler_pass_extension"
    authenticated = subprocess.run(
        [sys.executable, str(TASK2_VERIFIER)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    _require(authenticated.returncode == 0, "authenticated Task 2 verifier failed")
    if replay:
        for index, run in enumerate(runs):
            _replay(run, expected_inputs[index], evidence_dirs[index])
    _require(payload.get("decision") == decision, "decision gate mismatch")
    if decision == "register_existing_pass":
        _require(payload.get("normalized_artifact") == runs[-1]["output"], "normalized artifact identity mismatch")
        _require("earliest_remaining_signature" not in payload, "unexpected extension reproducer")
    else:
        earliest = payload.get("earliest_remaining_signature", {})
        _require(earliest.get("operation") == invalid[0]["operation"], "earliest remaining signature missing")
        reproducer_record = earliest.get("reproducer", {})
        reproducer = _check_binding(
            {key: reproducer_record.get(key) for key in BINDING_KEYS},
            "earliest remaining reproducer",
        )
        lines = reproducer.read_text(encoding="utf-8").splitlines()
        subviews = [line for line in lines if "memref.subview" in line]
        _require(len(subviews) == 1, "earliest remaining reproducer is not exact")
        _require(earliest.get("reproducer", {}).get("operation_count") == 1, "earliest remaining reproducer count mismatch")
        metadata_path = _check_binding(earliest["reproducer"].get("metadata"), "earliest remaining metadata")
        metadata = _load_object(metadata_path, "earliest remaining metadata")
        _require_keys(metadata, METADATA_KEYS, "reproducer metadata schema")
        _require(metadata.get("signature_sha256") == earliest.get("signature_sha256"), "earliest remaining signature mismatch")
        execution = metadata.get("execution", {})
        _require_keys(execution, METADATA_EXECUTION_KEYS, "reproducer execution schema")
        expected_stdout = reproducer.parent / "pass.stdout.bin"
        expected_stderr = reproducer.parent / "pass.stderr.bin"
        expected_output = reproducer.parent / "pass.output.mlir"
        expected_repro_command = [
            TOOL["path"], str(reproducer), f"--load-pass-plugin={PLUGIN['path']}",
            f"--pass-pipeline={PIPELINE}", "-o", str(expected_output),
        ]
        _require(execution.get("command") == expected_repro_command, "reproducer command mismatch")
        _require(execution.get("exit_code") == 1, "reproducer exit mismatch")
        _require(isinstance(execution.get("elapsed_ns"), int) and execution["elapsed_ns"] > 0, "reproducer elapsed time invalid")
        _require(execution.get("output_created") is False, "reproducer output-created status mismatch")
        _require(execution.get("stdout") == _binding(expected_stdout, relative=True), "reproducer stdout mismatch")
        _require(execution.get("stderr") == _binding(expected_stderr, relative=True), "reproducer stderr mismatch")
        _require(execution.get("output") == _binding(expected_output, relative=True), "reproducer output mismatch")
        repro_stderr = _check_binding(execution.get("stderr"), "earliest reproducer stderr")
        repro_stdout = _check_binding(execution.get("stdout"), "earliest reproducer stdout")
        repro_output = _check_binding(execution.get("output"), "earliest reproducer output")
        _require(b"expected 1 offset values, got 2" in repro_stderr.read_bytes(), "earliest reproducer diagnostic mismatch")
        if replay:
            with tempfile.TemporaryDirectory(prefix="exact-subview-replay-") as raw:
                output = Path(raw) / "out.mlir"
                command = [
                    TOOL["path"], str(reproducer), f"--load-pass-plugin={PLUGIN['path']}",
                    f"--pass-pipeline={PIPELINE}", "-o", str(output),
                ]
                completed_repro = subprocess.run(
                    command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
                )
                replay_created = output.exists()
                replay_output = output.read_bytes() if replay_created else b""
                _require(completed_repro.returncode == execution["exit_code"], "reproducer exit mismatch")
                _require(completed_repro.stdout == repro_stdout.read_bytes(), "reproducer stdout mismatch")
                _require(completed_repro.stderr == repro_stderr.read_bytes(), "reproducer stderr mismatch")
                _require(replay_created == execution["output_created"], "reproducer output-created status mismatch")
                _require(replay_output == repro_output.read_bytes(), "reproducer output mismatch")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, default=EVALUATION)
    parser.add_argument("--no-replay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _args()
    payload = _load_object(args.evaluation, "Task 3 evaluation")
    validate_payload(payload, ROOT, replay=not args.no_replay)
    counts = payload["complete"]["after"]["blocker_counts"]
    print(json.dumps({"status": "PASS", "decision": payload["decision"], "after": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
