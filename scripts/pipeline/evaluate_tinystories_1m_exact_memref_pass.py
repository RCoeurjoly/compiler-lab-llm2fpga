#!/usr/bin/env python3
"""Evaluate the existing memref-view pass on the authenticated exact frontier."""

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
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TASK2_CONTRACT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
)
TASK2_EXTRACTOR = (
    ROOT / "scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py"
)
TASK2_VERIFIER = (
    ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
)
DEFAULT_OUTPUT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
)
DEFAULT_EVIDENCE = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evidence"
)
DEFAULT_REPORT = ROOT / "docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REGISTERED_CLASSES = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
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
TASK2_CONTRACT_SHA256 = (
    "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
)
FLAT_SCF_SHA256 = (
    "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_binding(path: Path, *, relative: bool = False) -> dict[str, Any]:
    data = path.read_bytes()
    rendered = str(path.relative_to(ROOT)) if relative else str(path)
    return {"path": rendered, "bytes": len(data), "sha256": sha256_bytes(data)}


def _load_task2_extractor():
    spec = importlib.util.spec_from_file_location("exact_memref_task2", TASK2_EXTRACTOR)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load authenticated Task 2 parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_binding(path: Path, expected: dict[str, Any], label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} is unavailable: {path}")
    actual = file_binding(path)
    for key in ("path", "bytes", "sha256"):
        if actual[key] != expected[key]:
            raise ValueError(f"{label} {key} mismatch")


def _semantic_signature(signature: dict[str, Any]) -> dict[str, Any]:
    """Return shape/layout semantics without spelling-only type fields."""
    value = json.loads(json.dumps(signature))
    value.pop("operand_types", None)
    value.pop("result_types", None)
    for key in ("operand_memrefs", "result_memrefs"):
        for memref in value.get(key, []):
            memref.pop("text", None)
    return value


def classify_signature(
    before: dict[str, Any], after: list[dict[str, Any]], *, valid: bool
) -> str:
    if not valid:
        return "new_invalid"
    before_exact = canonical_json(before)
    if any(canonical_json(candidate) == before_exact for candidate in after):
        return "preserved"
    before_semantic = canonical_json(_semantic_signature(before))
    if any(
        canonical_json(_semantic_signature(candidate)) == before_semantic
        for candidate in after
    ):
        return "rewritten_equivalent"
    return "eliminated"


def apply_decision_gate(
    *,
    parseable: bool,
    blocker_counts: dict[str, int],
    invalid_signatures: list[Any],
    unknown_blocker_classes: list[str],
    invariant_status: str,
) -> str:
    if (
        parseable
        and set(blocker_counts) == set(REGISTERED_CLASSES)
        and all(blocker_counts[name] == 0 for name in REGISTERED_CLASSES)
        and not invalid_signatures
        and not unknown_blocker_classes
        and invariant_status == "proven"
    ):
        return "register_existing_pass"
    return "compiler_pass_extension"


def _representative_signature(contract: dict[str, Any], name: str) -> dict[str, Any]:
    representative = contract["classes"][name]["representative"]
    signature = json.loads(representative["selection_tuple"][1])
    if sha256_bytes(canonical_json(signature)) != representative["signature_sha256"]:
        raise ValueError(f"authenticated representative signature mismatch for {name}")
    return signature


def render_semantic_probe(contract: dict[str, Any], name: str) -> str:
    """Render a live load/store use of the exact authenticated representative."""
    signature = _representative_signature(contract, name)
    operands = signature["operand_types"]
    results = signature["result_types"]
    if name == "memref.collapse_shape":
        return (
            "module {\n"
            f"  func.func @probe(%source: {operands[0]}, %i0: index, %i1: index) -> i64 {{\n"
            f"    %view = memref.collapse_shape %source [[0, 1], [2]] : {operands[0]} into {results[0]}\n"
            f"    %value = memref.load %view[%i0, %i1] : {results[0]}\n"
            f"    memref.store %value, %view[%i0, %i1] : {results[0]}\n"
            "    return %value : i64\n  }\n}\n"
        )
    if name == "memref.copy":
        return (
            "module {\n"
            f"  func.func @probe(%source: {operands[0]}, %target: {operands[1]}) -> i64 {{\n"
            "    %c0 = arith.constant 0 : index\n"
            f"    memref.copy %source, %target : {operands[0]} to {operands[1]}\n"
            f"    %value = memref.load %target[%c0] : {operands[1]}\n"
            f"    memref.store %value, %target[%c0] : {operands[1]}\n"
            "    return %value : i64\n  }\n}\n"
        )
    if name == "memref.expand_shape":
        return (
            "module {\n"
            f"  func.func @probe(%source: {operands[0]}) -> i64 {{\n"
            "    %c0 = arith.constant 0 : index\n"
            f"    %view = memref.expand_shape %source [[0, 1]] output_shape [1, 1] : {operands[0]} into {results[0]}\n"
            f"    %value = memref.load %view[%c0, %c0] : {results[0]}\n"
            f"    memref.store %value, %view[%c0, %c0] : {results[0]}\n"
            "    return %value : i64\n  }\n}\n"
        )
    if name == "memref.reinterpret_cast":
        return (
            "module {\n"
            f"  func.func @probe(%source: {operands[0]}) -> i64 {{\n"
            "    %c0 = arith.constant 0 : index\n"
            f"    %view = memref.reinterpret_cast %source to offset: [0], sizes: [1], strides: [1] : {operands[0]} to {results[0]}\n"
            f"    %value = memref.load %view[%c0] : {results[0]}\n"
            f"    memref.store %value, %view[%c0] : {results[0]}\n"
            "    return %value : i64\n  }\n}\n"
        )
    raise ValueError(f"unsupported semantic probe operation {name}")


_FUNC_PROBE = re.compile(r"^\s*func\.func @probe\((.*)\) -> i64 \{\s*$")
_FUNC_ARG = re.compile(r"(%[A-Za-z0-9_.$-]+)\s*:\s*(memref<[^>]+>|index)")
_INDEX_CONSTANT = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.constant\s+(-?[0-9]+)\s*:\s*index\s*$")
_INDEX_BINARY = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.(addi|subi|muli)\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:\s*index\s*$")
_VIEW_ALIAS = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*memref\.(?:collapse_shape|expand_shape|reinterpret_cast)\s+(%[A-Za-z0-9_.$-]+)\b")
_LOAD = re.compile(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.load\s+(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_STORE = re.compile(r"^\s*memref\.store\s+%[A-Za-z0-9_.$-]+,\s*(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_COPY = re.compile(r"^\s*memref\.copy\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:")


def _affine_add(left: dict[str, Any], right: dict[str, Any], scale: int = 1) -> dict[str, Any]:
    return {
        "coefficients": [
            lhs + scale * rhs
            for lhs, rhs in zip(left["coefficients"], right["coefficients"])
        ],
        "offset": left["offset"] + scale * right["offset"],
    }


def _affine_scale(value: dict[str, Any], scale: int) -> dict[str, Any]:
    return {
        "coefficients": [scale * item for item in value["coefficients"]],
        "offset": scale * value["offset"],
    }


def _semantic_access_model(
    text: str, parser: Any, *, operation: str, signature: dict[str, Any]
) -> dict[str, Any]:
    logical_shape = (
        signature["operand_memrefs"][1]["shape"]
        if operation == "memref.copy"
        else signature["result_memrefs"][0]["shape"]
    )
    function = next(
        (matched for line in text.splitlines() if (matched := _FUNC_PROBE.match(line))),
        None,
    )
    if function is None:
        raise ValueError("semantic probe function signature is unavailable")
    arguments = list(_FUNC_ARG.finditer(function.group(1)))
    memref_arguments = [item for item in arguments if item.group(2).startswith("memref<")]
    index_arguments = [item for item in arguments if item.group(2) == "index"]
    variable_dimensions = [
        (dimension, extent)
        for dimension, extent in enumerate(logical_shape)
        if extent > 1
    ]
    if len(index_arguments) != len(variable_dimensions):
        raise ValueError("semantic probe index-variable rank is dynamic or mismatched")
    variables = [
        {
            "name": f"i{variable_dimensions[index][0]}",
            "argument": arguments.index(item),
            "lower_inclusive": 0,
            "upper_exclusive": variable_dimensions[index][1],
        }
        for index, item in enumerate(index_arguments)
    ]
    variable_count = len(variables)
    expressions: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(index_arguments):
        coefficients = [0] * variable_count
        coefficients[index] = 1
        expressions[item.group(1)] = {"coefficients": coefficients, "offset": 0}
    for line in text.splitlines():
        constant = _INDEX_CONSTANT.match(line)
        if constant:
            expressions[constant.group(1)] = {
                "coefficients": [0] * variable_count,
                "offset": int(constant.group(2)),
            }
            continue
        binary = _INDEX_BINARY.match(line)
        if not binary:
            continue
        left, right = expressions.get(binary.group(3)), expressions.get(binary.group(4))
        if left is None or right is None:
            raise ValueError("semantic probe contains a dynamic index expression")
        if binary.group(2) == "addi":
            result = _affine_add(left, right)
        elif binary.group(2) == "subi":
            result = _affine_add(left, right, -1)
        else:
            left_constant = not any(left["coefficients"])
            right_constant = not any(right["coefficients"])
            if not left_constant and not right_constant:
                raise ValueError("semantic probe contains a non-affine multiplication")
            result = _affine_scale(
                right if left_constant else left,
                left["offset"] if left_constant else right["offset"],
            )
        expressions[binary.group(1)] = result

    buffer_roles = {0: "source"}
    if operation == "memref.copy":
        buffer_roles[1] = "target"
    buffers = {
        item.group(1): {"argument": arguments.index(item), "role": buffer_roles[index]}
        for index, item in enumerate(memref_arguments)
    }
    aliases = {}
    for line in text.splitlines():
        alias = _VIEW_ALIAS.match(line)
        if alias:
            aliases[alias.group(1)] = alias.group(2)

    def base_identity(name: str) -> dict[str, Any]:
        while name in aliases:
            name = aliases[name]
        if name not in buffers:
            raise ValueError("semantic probe access base is not a function buffer")
        return buffers[name]

    copy_provenance = None
    for line in text.splitlines():
        copied = _COPY.match(line)
        if copied:
            copy_provenance = {
                "source": base_identity(copied.group(1)),
                "target": base_identity(copied.group(2)),
            }
    accesses = []
    memrefs = []
    for line in text.splitlines():
        matched = _LOAD.match(line)
        kind = "load"
        if matched is None:
            matched = _STORE.match(line)
            kind = "store"
        if matched is None:
            continue
        memref = parser.parse_memref_type(matched.group(3))
        tokens = [token.strip() for token in matched.group(2).split(",")]
        raw_indices = []
        for token in tokens:
            expression = expressions.get(token)
            if expression is None:
                raise ValueError("semantic probe contains a dynamic or non-affine index")
            raw_indices.append(copy.deepcopy(expression))
        if len(raw_indices) != memref["rank"]:
            raise ValueError("semantic probe access rank mismatch")
        for expression, dimension in zip(raw_indices, memref["shape"]):
            lower, upper = expression["offset"], expression["offset"]
            for coefficient, variable in zip(expression["coefficients"], variables):
                extent = variable["upper_exclusive"] - 1
                lower += min(0, coefficient * extent)
                upper += max(0, coefficient * extent)
            expression["range"] = {
                "lower_inclusive": lower,
                "upper_exclusive": upper + 1,
                "memref_upper_exclusive": dimension,
                "in_bounds": 0 <= lower and upper < dimension,
            }
        linear = {"coefficients": [0] * variable_count, "offset": memref["offset"]}
        for stride, expression in zip(memref["strides"], raw_indices):
            linear = _affine_add(linear, _affine_scale(expression, stride))
        sample_values = [
            min(variable["upper_exclusive"] - 1, index + 2)
            for index, variable in enumerate(variables)
        ]
        sample_linear = linear["offset"] + sum(
            coefficient * value
            for coefficient, value in zip(linear["coefficients"], sample_values)
        )
        accesses.append(
            {
                "kind": kind,
                "base": base_identity(matched.group(1)),
                "raw_indices": raw_indices,
                "linear_formula": linear,
                "supplementary_sample": {
                    "variables": sample_values, "linear_index": sample_linear
                },
            }
        )
        memrefs.append(memref)
    if not accesses:
        raise ValueError("semantic probe has no live memory access")
    if operation == "memref.copy" and copy_provenance is None:
        raise ValueError("semantic copy probe lacks source-target provenance")
    element_counts = [__import__("math").prod(memref["shape"]) for memref in memrefs]
    if len(set(element_counts)) != 1:
        raise ValueError("semantic probe accesses disagree on element count")
    shape, strides = memrefs[0]["shape"], memrefs[0]["strides"]
    expected_stride, contiguous = 1, True
    for dimension, stride in reversed(list(zip(shape, strides))):
        contiguous = contiguous and stride == expected_stride
        expected_stride *= dimension
    affine_mappings = [
        {
            "kind": access["kind"], "base": access["base"],
            "linear_formula": access["linear_formula"],
        }
        for access in accesses
    ]
    return {
        "affine_status": "proven",
        "index_variables": variables,
        "shape": shape, "strides": strides, "offset": memrefs[0]["offset"],
        "contiguous": contiguous, "element_count": element_counts[0],
        "copy_provenance": copy_provenance,
        "access_maps": accesses, "affine_mappings": affine_mappings,
    }


def semantic_access_model(
    text: str, parser: Any, *, operation: str, signature: dict[str, Any]
) -> dict[str, Any]:
    try:
        return _semantic_access_model(
            text, parser, operation=operation, signature=signature
        )
    except ValueError as error:
        return {"affine_status": "unproven", "reason": str(error)}


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


_OP_LINE = re.compile(
    r"^\s*(?:[%][^=]+?=\s*)?(?:\([^=]+\)\s*=\s*)?"
    r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*)\b"
)


def operation_census(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in text.splitlines():
        match = _OP_LINE.match(_mask_line(raw))
        if match:
            name = match.group(1)
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def summarize_registered_operations(operations: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a post-pass census, where any or all classes may be absent."""
    classes: dict[str, Any] = {}
    locations = []
    for name in REGISTERED_CLASSES:
        grouped: dict[bytes, list[dict[str, Any]]] = {}
        for item in operations:
            if item["operation"] != name:
                continue
            encoded = canonical_json(item["signature"])
            grouped.setdefault(encoded, []).append(item)
            locations.append(
                {
                    "operation": name,
                    **item["source_location"],
                    "signature_sha256": sha256_bytes(encoded),
                }
            )
        classes[name] = {
            "count": sum(len(items) for items in grouped.values()),
            "signatures": [
                {
                    "signature": items[0]["signature"],
                    "signature_sha256": sha256_bytes(encoded),
                    "multiplicity": len(items),
                }
                for encoded, items in sorted(grouped.items())
            ],
        }
    locations.sort(
        key=lambda item: (
            item["operation"], item["function"] or "", item["line"],
            item["column"], item["signature_sha256"],
        )
    )
    return {"classes": classes, "locations": locations}


def _registered_summary(parser: Any, text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    operations = parser.parse_registered_operations(text)
    return operations, summarize_registered_operations(operations)


_SUBVIEW_LINE = re.compile(
    r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.subview\s+"
    r"%[A-Za-z0-9_.$-]+\[(?P<offsets>[^]]+)\]\s*"
    r"\[(?P<sizes>[^]]+)\]\s*\[(?P<strides>[^]]+)\]\s*:\s*"
    r"(?P<source>memref<.+>)\s+to\s+(?P<result>memref<.+>)\s*$"
)


def _integer_list(raw: str) -> list[int]:
    values = []
    for item in raw.split(","):
        token = item.strip()
        if not re.fullmatch(r"-?[0-9]+", token):
            raise ValueError("new invalid subview has dynamic or malformed metadata")
        values.append(int(token))
    return values


def diagnose_invalid_frontier(
    stderr: bytes, source_text: str, parser: Any
) -> dict[str, Any]:
    diagnostic = stderr.decode("utf-8", errors="strict")
    location = re.search(r":([0-9]+):([0-9]+): error: ([^\n]+)", diagnostic)
    if not location:
        raise ValueError("pass failure has no canonical source diagnostic")
    line_number = int(location.group(1))
    column = int(location.group(2))
    lines = source_text.splitlines()
    if line_number < 1 or line_number > len(lines):
        raise ValueError("pass failure diagnostic source line is out of range")
    operation = _SUBVIEW_LINE.match(lines[line_number - 1])
    if (
        operation is None
        or '"memref.subview"' not in diagnostic
        or "expected 1 offset values, got 2" not in diagnostic
    ):
        raise ValueError("unknown pass failure class")
    source_type = operation.group("source")
    result_type = operation.group("result")
    signature = {
        "operation": "memref.subview",
        "operand_types": [source_type],
        "result_types": [result_type],
        "operand_memrefs": [parser.parse_memref_type(source_type)],
        "result_memrefs": [parser.parse_memref_type(result_type)],
        "offsets": _integer_list(operation.group("offsets")),
        "sizes": _integer_list(operation.group("sizes")),
        "strides": _integer_list(operation.group("strides")),
    }
    encoded = canonical_json(signature)
    return {
        "operation": "memref.subview",
        "classification": "new_invalid",
        "signature": signature,
        "signature_sha256": sha256_bytes(encoded),
        "source_location": {
            "function": "main", "line": line_number, "column": column, "mlir": None
        },
        "diagnostic": location.group(3),
        "stderr_sha256": sha256_bytes(stderr),
        "reason": (
            "the pass flattened a rank-2 function argument while leaving its "
            "rank-2 memref.subview metadata unchanged"
        ),
    }


def _signature_index(operations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {name: [] for name in REGISTERED_CLASSES}
    seen: dict[str, set[bytes]] = {name: set() for name in REGISTERED_CLASSES}
    for item in operations:
        signature = item["signature"]
        encoded = canonical_json(signature)
        name = signature["operation"]
        if encoded not in seen[name]:
            seen[name].add(encoded)
            result[name].append(signature)
    for signatures in result.values():
        signatures.sort(key=canonical_json)
    return result


def _bindings_for_run(directory: Path) -> dict[str, Any]:
    return {
        name: file_binding(directory / filename, relative=True)
        for name, filename in (
            ("stdout", "stdout.bin"),
            ("stderr", "stderr.bin"),
            ("output", "output.mlir"),
        )
    }


def run_pass(
    *, sequence: int, identifier: str, kind: str, operation: str | None,
    input_path: Path, output_dir: Path, parser: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stdout.bin"
    stderr_path = output_dir / "stderr.bin"
    output_path = output_dir / "output.mlir"
    before = file_binding(input_path, relative=True)
    command = [
        TOOL["path"],
        str(input_path),
        f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}",
        "-o",
        str(output_path),
    ]
    started_ns = time.monotonic_ns()
    completed = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    elapsed_ns = time.monotonic_ns() - started_ns
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    if not output_path.exists():
        output_path.write_bytes(b"")
    after_input = file_binding(input_path, relative=True)
    if before != after_input:
        raise ValueError(f"pass mutated input bytes for {identifier}")

    output_bytes = output_path.read_bytes()
    parse_stdout = output_dir / "parse.stdout.bin"
    parse_stderr = output_dir / "parse.stderr.bin"
    parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
    parsed = subprocess.run(
        parse_command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    parse_stdout.write_bytes(parsed.stdout)
    parse_stderr.write_bytes(parsed.stderr)
    parseable = completed.returncode == 0 and parsed.returncode == 0
    output_text = output_bytes.decode("utf-8") if parseable else ""
    if parseable:
        after_operations, after_summary = _registered_summary(parser, output_text)
    else:
        after_operations = []
        after_summary = {
            "classes": {
                name: {"count": None, "signatures": []} for name in REGISTERED_CLASSES
            },
            "locations": [],
        }
    evidence = _bindings_for_run(output_dir)
    run = {
        "sequence": sequence,
        "id": identifier,
        "kind": kind,
        "operation": operation,
        "command": command,
        "input": before,
        "input_after": after_input,
        "exit_code": completed.returncode,
        "elapsed_ns": elapsed_ns,
        **evidence,
        "parse_check": {
            "command": parse_command,
            "exit_code": parsed.returncode,
            "stdout": file_binding(parse_stdout, relative=True),
            "stderr": file_binding(parse_stderr, relative=True),
        },
        "parseable": parseable,
    }
    return run, after_operations, after_summary


def _counts(summary: dict[str, Any]) -> dict[str, int]:
    return {name: summary["classes"][name]["count"] for name in REGISTERED_CLASSES}


def _mapping_for_contract(
    contract: dict[str, Any], after_operations: list[dict[str, Any]], *, valid: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    after_by_class = _signature_index(after_operations)
    mappings = []
    before_semantics: dict[str, set[bytes]] = {name: set() for name in REGISTERED_CLASSES}
    before_exact: dict[str, set[bytes]] = {name: set() for name in REGISTERED_CLASSES}
    for name in REGISTERED_CLASSES:
        for entry in contract["classes"][name]["signatures"]:
            signature = entry["signature"]
            before_exact[name].add(canonical_json(signature))
            before_semantics[name].add(canonical_json(_semantic_signature(signature)))
            mappings.append(
                {
                    "operation": name,
                    "input_signature_sha256": entry["signature_sha256"],
                    "input_multiplicity": entry["multiplicity"],
                    "classification": classify_signature(
                        signature, after_by_class[name], valid=valid
                    ),
                    "output_signature_sha256": [
                        sha256_bytes(canonical_json(candidate))
                        for candidate in after_by_class[name]
                        if canonical_json(candidate) == canonical_json(signature)
                        or canonical_json(_semantic_signature(candidate))
                        == canonical_json(_semantic_signature(signature))
                    ],
                }
            )
    invalid = []
    for name, signatures in after_by_class.items():
        for signature in signatures:
            exact = canonical_json(signature)
            semantic = canonical_json(_semantic_signature(signature))
            if exact not in before_exact[name] and semantic not in before_semantics[name]:
                invalid.append(
                    {
                        "operation": name,
                        "signature_sha256": sha256_bytes(exact),
                        "reason": "output signature has no exact or shape/layout-equivalent input",
                        "signature": signature,
                    }
                )
    mappings.sort(key=lambda item: (item["operation"], item["input_signature_sha256"]))
    invalid.sort(key=lambda item: (item["operation"], item["signature_sha256"]))
    return mappings, invalid


def _unknown_blockers(before_census: dict[str, int], after_census: dict[str, int]) -> list[str]:
    """Fail closed on newly introduced view/cast/shape/copy memref families."""
    suspicious = re.compile(r"(?:view|cast|shape|copy)")
    return sorted(
        name
        for name in after_census
        if name.startswith("memref.")
        and suspicious.search(name.split(".", 1)[1])
        and name not in REGISTERED_CLASSES
        and name not in before_census
    )


def _representative_result(
    contract: dict[str, Any], name: str, run: dict[str, Any],
    after_operations: list[dict[str, Any]], after_summary: dict[str, Any], parser: Any,
) -> dict[str, Any]:
    representative = contract["classes"][name]["representative"]
    before_path = ROOT / representative["path"]
    before_operations, before_summary = _registered_summary(
        parser, before_path.read_text(encoding="utf-8")
    )
    signature = before_operations[0]["signature"]
    after_signatures = _signature_index(after_operations)[name]
    classification = classify_signature(
        signature, after_signatures, valid=run["parseable"] and run["exit_code"] == 0
    )
    return {
        "operation": name,
        "input_signature_sha256": representative["signature_sha256"],
        "classification": classification,
        "parseable": run["parseable"],
        "before": {
            "operation_census": operation_census(before_path.read_text(encoding="utf-8")),
            "blocker_counts": _counts(before_summary),
        },
        "after": {
            "operation_census": operation_census(
                (ROOT / run["output"]["path"]).read_text(encoding="utf-8")
                if run["parseable"] else ""
            ),
            "blocker_counts": _counts(after_summary),
        },
    }


def _write_earliest_reproducer(
    parser: Any, contract: dict[str, Any], mappings: list[dict[str, Any]]
) -> dict[str, Any]:
    remaining = [
        item for item in mappings
        if item["classification"] in {"preserved", "rewritten_equivalent", "new_invalid"}
    ]
    if not remaining:
        raise ValueError("extension decision has no remaining canonical signature")
    by_hash = {
        entry["signature_sha256"]: entry
        for name in REGISTERED_CLASSES
        for entry in contract["classes"][name]["signatures"]
    }
    remaining.sort(
        key=lambda item: (
            item["operation"],
            canonical_json(by_hash[item["input_signature_sha256"]]["signature"]),
        )
    )
    earliest = remaining[0]
    entry = by_hash[earliest["input_signature_sha256"]]
    item = {
        "operation": earliest["operation"],
        "signature": entry["signature"],
        "source_location": {"function": None, "line": 0, "column": 0, "mlir": None},
    }
    text = parser.render_representative(item)
    directory = (
        ROOT / "reproducers/tinystories-1m-exact-flat-scf-memref/"
        "task3-earliest-remaining"
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "input.mlir"
    path.write_text(text, encoding="utf-8")
    parsed = parser.parse_registered_operations(text)
    if len(parsed) != 1 or parsed[0]["signature"] != entry["signature"]:
        raise ValueError("earliest reproducer does not preserve the exact signature")
    metadata = {
        "operation": earliest["operation"],
        "signature": entry["signature"],
        "signature_sha256": entry["signature_sha256"],
        "classification": earliest["classification"],
        "selection": "lexicographically earliest remaining canonical signature",
    }
    metadata_path = directory / "task3-evaluation.json"
    metadata_path.write_bytes(canonical_json(metadata) + b"\n")
    return {
        "operation": earliest["operation"],
        "signature_sha256": entry["signature_sha256"],
        "classification": earliest["classification"],
        "signature": entry["signature"],
        "reproducer": {
            **file_binding(path, relative=True),
            "registered_operation_count": 1,
            "metadata": file_binding(metadata_path, relative=True),
        },
    }


def _write_invalid_reproducer(invalid: dict[str, Any]) -> dict[str, Any]:
    signature = invalid["signature"]
    if signature["operation"] != "memref.subview":
        raise ValueError("unsupported new-invalid reproducer class")
    source_type = signature["operand_types"][0]
    result_type = signature["result_types"][0]
    render = lambda values: ", ".join(str(value) for value in values)
    text = (
        "module {\n"
        f"  func.func @representative(%source: {source_type}) {{\n"
        "    %result = memref.subview %source["
        + render(signature["offsets"])
        + "] ["
        + render(signature["sizes"])
        + "] ["
        + render(signature["strides"])
        + f"] : {source_type} to {result_type}\n"
        "    return\n"
        "  }\n"
        "}\n"
    )
    directory = (
        ROOT / "reproducers/tinystories-1m-exact-flat-scf-memref/"
        "task3-earliest-remaining"
    )
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "input.mlir"
    stdout_path = directory / "pass.stdout.bin"
    stderr_path = directory / "pass.stderr.bin"
    output_path = directory / "pass.output.mlir"
    input_path.write_text(text, encoding="utf-8")
    output_path.unlink(missing_ok=True)
    command = [
        TOOL["path"], str(input_path),
        f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}", "-o", str(output_path),
    ]
    started = time.monotonic_ns()
    completed = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    elapsed = time.monotonic_ns() - started
    output_created = output_path.exists()
    output = output_path.read_bytes() if output_created else b""
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    output_path.write_bytes(output)
    if (
        completed.returncode == 0
        or b"expected 1 offset values, got 2" not in completed.stderr
        or b'"memref.subview"' not in completed.stderr
    ):
        raise ValueError("minimal exact reproducer does not reproduce the invalid frontier")
    metadata = {
        "operation": invalid["operation"],
        "signature": signature,
        "signature_sha256": invalid["signature_sha256"],
        "classification": "new_invalid",
        "selection": "earliest diagnostic-emitting operation in the complete pass run",
        "execution": {
            "command": command,
            "exit_code": completed.returncode,
            "elapsed_ns": elapsed,
            "output_created": output_created,
            "stdout": file_binding(stdout_path, relative=True),
            "stderr": file_binding(stderr_path, relative=True),
            "output": file_binding(output_path, relative=True),
        },
    }
    metadata_path = directory / "task3-evaluation.json"
    metadata_path.write_bytes(canonical_json(metadata) + b"\n")
    return {
        "operation": invalid["operation"],
        "signature_sha256": invalid["signature_sha256"],
        "classification": "new_invalid",
        "signature": signature,
        "source_location": invalid["source_location"],
        "diagnostic": invalid["diagnostic"],
        "reproducer": {
            **file_binding(input_path, relative=True),
            "operation_count": 1,
            "metadata": file_binding(metadata_path, relative=True),
        },
    }


def _report(payload: dict[str, Any]) -> str:
    complete = payload["complete"]
    rows = []
    for name in REGISTERED_CLASSES:
        after = complete["after"]["blocker_counts"][name]
        rendered_after = f"{after:,}" if isinstance(after, int) else "unavailable"
        rows.append(
            f"| `{name}` | {complete['before']['blocker_counts'][name]:,} | "
            f"{rendered_after} |"
        )
    representatives = []
    for item in payload["representatives"]:
        representatives.append(
            f"| `{item['operation']}` | `{item['classification']}` | "
            f"{item['after']['blocker_counts'][item['operation']]} |"
        )
    extension = ""
    if payload["decision"] == "compiler_pass_extension":
        earliest = payload["earliest_remaining_signature"]
        extension = (
            "\n## Earliest residual\n\n"
            f"`{earliest['operation']}` / `{earliest['signature_sha256']}`. "
            f"The exact one-operation reproducer is `{earliest['reproducer']['path']}`.\n"
        )
    elapsed = sum(run["elapsed_ns"] for run in payload["executions"])
    return f"""# Exact TinyStories-1M static-memref-pass evaluation

The existing pass was evaluated without modifying it and without invoking
Calyx. All four authenticated representatives ran before the complete retained
c22 flat-SCF artifact. The protected current alias remains explicitly
unrealized; this experiment uses the retained authenticated c22 bytes.

## Decision

`{payload['decision']}`

## Representatives

| Registered class | Classification | Remaining class count |
| --- | --- | ---: |
{chr(10).join(representatives)}

## Complete artifact census

| Registered class | Before | After |
| --- | ---: | ---: |
{chr(10).join(rows)}

- Input SHA-256: `{payload['input']['sha256']}`
- Output SHA-256: `{payload['executions'][-1]['output']['sha256']}`
- Tool SHA-256: `{payload['tool']['sha256']}`
- Plugin SHA-256: `{payload['plugin']['sha256']}`
- Exact pipeline: `{payload['pipeline']}`
- Parseable output: `{str(complete['parseable']).lower()}`
- Unknown blocker classes: `{len(complete['unknown_blocker_classes'])}`
- New invalid signatures: `{len(complete['new_invalid_signatures'])}`
- Full-artifact invariant status: `{complete['invariant_status']}`
- Measured pass time over nine ordered executions: `{elapsed}` ns
{extension}
No Calyx stage ran and no pipeline stage was registered by this evaluation.
"""


def evaluate(*, output: Path, evidence_root: Path, report: Path) -> dict[str, Any]:
    _require_binding(Path(TOOL["path"]), TOOL, "pinned MLIR tool")
    _require_binding(Path(PLUGIN["path"]), PLUGIN, "pinned pass plugin")
    if sha256_bytes(TASK2_CONTRACT.read_bytes()) != TASK2_CONTRACT_SHA256:
        raise ValueError("authenticated Task 2 contract SHA-256 mismatch")
    authenticated = subprocess.run(
        [sys.executable, str(TASK2_VERIFIER)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if authenticated.returncode != 0:
        raise ValueError(
            "authenticated Task 2 contract verification failed: "
            + authenticated.stderr.decode("utf-8", errors="replace")
        )
    contract = _load_json(TASK2_CONTRACT, "Task 2 contract")
    parser = _load_task2_extractor()
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    if file_binding(flat_scf, relative=True)["sha256"] != FLAT_SCF_SHA256:
        raise ValueError("retained c22 flat-SCF identity mismatch")

    evidence_root.mkdir(parents=True, exist_ok=True)
    executions = []
    representatives = []
    sequence = 1
    for name in REGISTERED_CLASSES:
        representative = contract["classes"][name]["representative"]
        slug = name.replace(".", "-").replace("_", "-")
        run, after_ops, after_summary = run_pass(
            sequence=sequence, identifier=slug, kind="representative",
            operation=name, input_path=ROOT / representative["path"],
            output_dir=evidence_root / slug, parser=parser,
        )
        executions.append(run)
        representatives.append(
            _representative_result(contract, name, run, after_ops, after_summary, parser)
        )
        sequence += 1

    semantic_probes = []
    for name in REGISTERED_CLASSES:
        slug = "semantic-" + name.replace(".", "-").replace("_", "-")
        probe_dir = evidence_root / slug
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe_input = probe_dir / "input.mlir"
        probe_text = render_semantic_probe(contract, name)
        probe_input.write_text(probe_text, encoding="utf-8")
        run, _, _ = run_pass(
            sequence=sequence, identifier=slug, kind="semantic_probe",
            operation=name, input_path=probe_input, output_dir=probe_dir, parser=parser,
        )
        executions.append(run)
        signature = _representative_signature(contract, name)
        before_model = semantic_access_model(
            probe_text, parser, operation=name, signature=signature
        )
        after_model = (
            semantic_access_model(
                (ROOT / run["output"]["path"]).read_text(encoding="utf-8"), parser,
                operation=name, signature=signature,
            )
            if run["parseable"] and run["exit_code"] == 0 else None
        )
        shape_element_count_preserved = (
            after_model is not None
            and before_model["affine_status"] == "proven"
            and after_model["affine_status"] == "proven"
            and before_model["element_count"] == after_model["element_count"]
        )
        layout_preserved = (
            after_model is not None
            and before_model["affine_status"] == "proven"
            and after_model["affine_status"] == "proven"
            and before_model["contiguous"]
            and after_model["contiguous"]
            and before_model["offset"] == after_model["offset"]
        )
        access_maps_preserved = (
            after_model is not None
            and before_model.get("index_variables") == after_model.get("index_variables")
            and before_model.get("affine_mappings") == after_model.get("affine_mappings")
            and before_model.get("copy_provenance") == after_model.get("copy_provenance")
            and all(
                raw["range"]["in_bounds"]
                for model in (before_model, after_model)
                for access in model.get("access_maps", [])
                for raw in access["raw_indices"]
            )
        )
        proven = (
            shape_element_count_preserved
            and layout_preserved
            and access_maps_preserved
        )
        semantic_probes.append(
            {
                "operation": name,
                "execution_id": slug,
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
        )
        sequence += 1

    full_run, full_after_ops, full_after_summary = run_pass(
        sequence=sequence, identifier="complete-retained-c22-flat-scf", kind="complete",
        operation=None, input_path=flat_scf,
        output_dir=evidence_root / "complete-retained-c22-flat-scf",
        parser=parser,
    )
    executions.append(full_run)
    before_text = flat_scf.read_text(encoding="utf-8")
    before_operations, before_summary = _registered_summary(parser, before_text)
    output_path = ROOT / full_run["output"]["path"]
    after_text = output_path.read_text(encoding="utf-8") if full_run["parseable"] else ""
    before_census = operation_census(before_text)
    after_census = operation_census(after_text)
    mappings, invalid = _mapping_for_contract(
        contract, full_after_ops,
        valid=full_run["parseable"] and full_run["exit_code"] == 0,
    )
    if not full_run["parseable"]:
        invalid = [
            diagnose_invalid_frontier(
                (ROOT / full_run["stderr"]["path"]).read_bytes(),
                before_text,
                parser,
            )
        ]
    unknown = _unknown_blockers(before_census, after_census)
    invariant_status = (
        "unavailable_due_invalid_output"
        if not full_run["parseable"]
        else (
            "proven"
            if not invalid and all(
                probe["invariant_status"] == "proven" for probe in semantic_probes
            )
            else "unproven"
        )
    )
    complete = {
        "parseable": full_run["parseable"],
        "before": {
            "operation_census": before_census,
            "blocker_counts": _counts(before_summary),
            "registered_operation_count": len(before_operations),
        },
        "after": {
            "operation_census": after_census,
            "blocker_counts": _counts(full_after_summary),
            "registered_operation_count": (
                len(full_after_ops) if full_run["parseable"] else None
            ),
        },
        "signature_mappings": mappings,
        "new_invalid_signatures": invalid,
        "unknown_blocker_classes": unknown,
        "invariant_status": invariant_status,
    }
    decision = apply_decision_gate(
        parseable=complete["parseable"],
        blocker_counts=complete["after"]["blocker_counts"],
        invalid_signatures=invalid,
        unknown_blocker_classes=unknown,
        invariant_status=invariant_status,
    )
    python_path = Path(sys.executable).resolve()
    payload: dict[str, Any] = {
        "schema": "tinystories-1m-exact-memref-pass-v1",
        "status": "evaluated",
        "model": contract["model"],
        "pipeline": PIPELINE,
        "task2_contract": file_binding(TASK2_CONTRACT, relative=True),
        "input": file_binding(flat_scf, relative=True),
        "tool": dict(TOOL),
        "plugin": dict(PLUGIN),
        "python": file_binding(python_path),
        "provenance": {
            "payload_source": contract["nix"]["payload_source"],
            "c22_derivation": contract["nix"]["c22_derivation"],
            "c22_output": contract["nix"]["c22_output"],
            "current_alias_derivation": contract["nix"]["current_derivation"],
            "current_alias_output": contract["nix"]["current_output"],
            "current_alias_realized": contract["nix"]["current_output_realized"],
            "unrealized_current_alias_residual": contract["nix"]["provenance_residual"],
        },
        "task_1_through_3_identities": contract["task_1_through_3_identities"],
        "executions": executions,
        "representatives": representatives,
        "semantic_probes": semantic_probes,
        "complete": complete,
        "decision": decision,
        "sha256": None,
    }
    if decision == "register_existing_pass":
        payload["normalized_artifact"] = full_run["output"]
    else:
        if invalid and invalid[0]["operation"] not in REGISTERED_CLASSES:
            payload["earliest_remaining_signature"] = _write_invalid_reproducer(
                invalid[0]
            )
        else:
            payload["earliest_remaining_signature"] = _write_earliest_reproducer(
                parser, contract, mappings
            )
    payload["sha256"] = sha256_bytes(canonical_json(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(payload) + b"\n")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(payload), encoding="utf-8")
    return payload


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = _args()
    payload = evaluate(output=args.output, evidence_root=args.evidence_root, report=args.report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": payload["decision"],
                "before": payload["complete"]["before"]["blocker_counts"],
                "after": payload["complete"]["after"]["blocker_counts"],
                "sha256": payload["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
