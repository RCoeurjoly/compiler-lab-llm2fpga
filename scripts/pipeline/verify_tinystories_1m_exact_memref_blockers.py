#!/usr/bin/env python3
"""Independent verifier for the exact TinyStories memref blocker contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
CAPTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1"
REP_PREFIX = Path("reproducers/tinystories-1m-exact-flat-scf-memref")
CLASSES = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
CLASS_SET = frozenset(CLASSES)
ALIAS = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-flat-scf"
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


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _binding(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": _digest(raw)}


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _top_level_parts(text: str) -> list[str]:
    result: list[str] = []
    begin = 0
    depths = {"(": 0, "[": 0, "{": 0, "<": 0}
    close = {")": "(", "]": "[", "}": "{", ">": "<"}
    quoted = False
    escaped = False
    for position, character in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in depths:
            depths[character] += 1
        elif character in close:
            opening = close[character]
            depths[opening] -= 1
            if depths[opening] < 0:
                raise ValueError("malformed nested syntax")
        elif character == "," and not any(depths.values()):
            result.append(text[begin:position].strip())
            begin = position + 1
    if quoted or any(depths.values()):
        raise ValueError("unbalanced nested syntax")
    result.append(text[begin:].strip())
    return result


def _memref(text: str) -> dict[str, Any]:
    if not (text.startswith("memref<") and text.endswith(">")):
        raise ValueError(f"malformed memref type: {text}")
    fields = _top_level_parts(text[7:-1])
    if len(fields) not in (1, 2):
        raise ValueError("unsupported memref type fields")
    shape_element = fields[0].split("x")
    if len(shape_element) < 2:
        raise ValueError("unranked memref is outside this contract")
    element = shape_element[-1]
    if re.fullmatch(r"(?:i\d+|f\d+|index)", element) is None:
        raise ValueError("unsupported memref element type")
    shape: list[Any] = []
    for dimension in shape_element[:-1]:
        if dimension == "?":
            shape.append("?")
        elif dimension.isdigit():
            shape.append(int(dimension))
        else:
            raise ValueError("malformed memref shape")
    identity: list[Any] = [0] * len(shape)
    stride: Any = 1
    for position in range(len(shape) - 1, -1, -1):
        identity[position] = stride
        dimension = shape[position]
        stride = stride * dimension if isinstance(stride, int) and isinstance(dimension, int) else "?"
    layout = "identity"
    offset: Any = 0
    strides = identity
    if len(fields) == 2:
        layout = fields[1]
        match = re.fullmatch(r"strided<\[([^]]*)\](?:,\s*offset:\s*(-?\d+|\?))?>", layout)
        if match is None:
            raise ValueError("malformed static/affine strided layout")
        raw_strides = [word.strip() for word in match.group(1).split(",")]
        if len(raw_strides) != len(shape):
            raise ValueError("strided layout rank mismatch")
        strides = []
        for word in raw_strides:
            if word == "?":
                strides.append("?")
            elif re.fullmatch(r"-?\d+", word):
                strides.append(int(word))
            else:
                raise ValueError("malformed strided layout value")
        raw_offset = match.group(2)
        offset = 0 if raw_offset is None else ("?" if raw_offset == "?" else int(raw_offset))
    return {
        "text": text,
        "rank": len(shape),
        "shape": shape,
        "element_type": element,
        "layout": layout,
        "offset": offset,
        "strides": strides,
    }


def _values(raw: str, dynamic_names: dict[str, str]) -> list[Any]:
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError("metadata is not a bracketed list")
    body = raw[1:-1].strip()
    if not body:
        return []
    values: list[Any] = []
    for word in _top_level_parts(body):
        if re.fullmatch(r"-?\d+", word):
            values.append(int(word))
        elif re.fullmatch(r"%[A-Za-z0-9_.$-]+", word):
            dynamic_names.setdefault(word, f"%dynamic{len(dynamic_names)}")
            values.append(dynamic_names[word])
        else:
            raise ValueError("malformed static/affine metadata")
    return values


def _groups(raw: str) -> list[list[int]]:
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError("malformed reassociation")
    body = raw[1:-1].strip()
    groups = [] if not body else [_values(item, {}) for item in _top_level_parts(body)]
    if any(not group or not all(isinstance(value, int) and value >= 0 for value in group) for group in groups):
        raise ValueError("malformed reassociation indices")
    return groups


def _type_pair(raw: str, separator: str) -> tuple[str, str]:
    marker = f" {separator} memref<"
    split = raw.rfind(marker)
    if split < 0:
        raise ValueError(f"missing {separator} memref type separator")
    first = raw[:split].strip()
    second = raw[split + len(f" {separator} ") :].strip()
    if not first.startswith("memref<") or not second.startswith("memref<"):
        raise ValueError("malformed memref type pair")
    return first, second


def _normalize_operation(raw: str) -> tuple[str, str | None]:
    compact = " ".join(piece.strip() for piece in raw.splitlines() if piece.strip())
    location = None
    location_match = re.search(r'\s+(loc\("(?:[^"\\]|\\.)+":\d+:\d+\))$', compact)
    if location_match:
        location = location_match.group(1)
        compact = compact[: location_match.start()]
    return compact, location


def _signature(operation: str, raw: str) -> tuple[dict[str, Any], str | None]:
    compact, location = _normalize_operation(raw)
    dynamic: dict[str, str] = {}
    if operation == "memref.copy":
        match = re.fullmatch(
            r"memref\.copy\s+%[A-Za-z0-9_.$-]+\s*,\s*%[A-Za-z0-9_.$-]+\s*:\s*(.+)", compact
        )
        if match is None:
            raise ValueError("malformed memref.copy")
        source_text, target_text = _type_pair(match.group(1), "to")
        source, target = _memref(source_text), _memref(target_text)
        if source["shape"] != target["shape"] or source["element_type"] != target["element_type"]:
            raise ValueError("memref.copy type mismatch")
        return {
            "operation": operation,
            "operand_types": [source_text, target_text],
            "result_types": [],
            "operand_memrefs": [source, target],
            "result_memrefs": [],
            "dynamic_operands": [],
        }, location

    head = re.fullmatch(
        rf"%[A-Za-z0-9_.$-]+\s*=\s*{re.escape(operation)}\s+%[A-Za-z0-9_.$-]+\s+(.+)", compact
    )
    if head is None:
        raise ValueError(f"malformed {operation}")
    tail = head.group(1)
    extra: dict[str, Any] = {}
    if operation == "memref.reinterpret_cast":
        match = re.fullmatch(
            r"to\s+offset:\s*(\[[^]]*\])\s*,\s*sizes:\s*(\[[^]]*\])\s*,\s*strides:\s*(\[[^]]*\])\s*:\s*(.+)",
            tail,
        )
        if match is None:
            raise ValueError("malformed reinterpret_cast metadata")
        source_text, result_text = _type_pair(match.group(4), "to")
        extra = {
            "offset": _values(match.group(1), dynamic),
            "sizes": _values(match.group(2), dynamic),
            "strides": _values(match.group(3), dynamic),
        }
    else:
        separator = tail.find("]]")
        if separator < 0:
            raise ValueError("malformed shape reassociation")
        reassociation_raw = tail[: separator + 2]
        remainder = tail[separator + 2 :].strip()
        extra["reassociation"] = _groups(reassociation_raw)
        if operation == "memref.expand_shape":
            match = re.fullmatch(r"output_shape\s*(\[[^]]*\])\s*:\s*(.+)", remainder)
            if match is None:
                raise ValueError("malformed expand_shape output_shape")
            extra["output_shape"] = _values(match.group(1), dynamic)
            type_tail = match.group(2)
        else:
            if not remainder.startswith(":"):
                raise ValueError("malformed collapse_shape type separator")
            type_tail = remainder[1:].strip()
        source_text, result_text = _type_pair(type_tail, "into")
    source, result = _memref(source_text), _memref(result_text)
    if operation == "memref.reinterpret_cast":
        if len(extra["offset"]) != 1 or len(extra["sizes"]) != result["rank"] or len(extra["strides"]) != result["rank"]:
            raise ValueError("reinterpret_cast metadata rank mismatch")
        for size, dimension in zip(extra["sizes"], result["shape"]):
            if isinstance(size, int) and isinstance(dimension, int) and size != dimension:
                raise ValueError("reinterpret_cast static size mismatch")
    else:
        reassociation = extra["reassociation"]
        ranked = result if operation == "memref.expand_shape" else source
        expected = list(range(ranked["rank"]))
        if [value for group in reassociation for value in group] != expected:
            raise ValueError("non-covering reassociation")
        if operation == "memref.expand_shape":
            if len(reassociation) != source["rank"] or len(extra["output_shape"]) != result["rank"]:
                raise ValueError("expand_shape metadata rank mismatch")
            for output, dimension in zip(extra["output_shape"], result["shape"]):
                if isinstance(output, int) and isinstance(dimension, int) and output != dimension:
                    raise ValueError("expand_shape static output mismatch")
            for source_dimension, group in zip(source["shape"], reassociation):
                dimensions = [extra["output_shape"][index] for index in group]
                if all(isinstance(value, int) for value in [source_dimension, *dimensions]):
                    product = 1
                    for value in dimensions:
                        product *= value
                    if product != source_dimension:
                        raise ValueError("expand_shape static shape product mismatch")
        elif len(reassociation) != result["rank"]:
            raise ValueError("collapse_shape metadata rank mismatch")
        else:
            for group, result_dimension in zip(reassociation, result["shape"]):
                dimensions = [source["shape"][index] for index in group]
                if all(isinstance(value, int) for value in [*dimensions, result_dimension]):
                    product = 1
                    for value in dimensions:
                        product *= value
                    if product != result_dimension:
                        raise ValueError("collapse_shape static shape product mismatch")
    signature = {
        "operation": operation,
        **extra,
        "operand_types": [source_text],
        "result_types": [result_text],
        "operand_memrefs": [source],
        "result_memrefs": [result],
        "dynamic_operands": list(dynamic.values()),
    }
    return signature, location


def _masked(line: str) -> str:
    result = []
    quoted = False
    escaped = False
    index = 0
    while index < len(line):
        character = line[index]
        if quoted:
            result.append(" ")
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
            result.append(" ")
        elif character == "/" and index + 1 < len(line) and line[index + 1] == "/":
            result.extend(" " * (len(line) - index))
            break
        else:
            result.append(character)
        index += 1
    return "".join(result)


def _reject_registered_generic_forms(text: str) -> None:
    """Fail closed instead of silently masking generic registered operations."""
    index = 0
    while index < len(text):
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline + 1
            continue
        if text[index] != '"':
            index += 1
            continue
        line_number = text.count("\n", 0, index) + 1
        end = index + 1
        escaped = False
        while end < len(text):
            character = text[end]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                break
            end += 1
        if end == len(text):
            raise ValueError("unterminated MLIR string literal")
        name = text[index + 1 : end]
        following = end + 1
        while following < len(text) and text[following].isspace():
            following += 1
        if name in CLASS_SET and following < len(text) and text[following] == "(":
            raise ValueError(
                f"generic-form registered operation is not accepted at line {line_number}: {name}"
            )
        index = end + 1


def _independent_operations(text: str) -> list[dict[str, Any]]:
    _reject_registered_generic_forms(text)
    lines = text.splitlines()
    output = []
    function = None
    line_index = 0
    while line_index < len(lines):
        mask = _masked(lines[line_index])
        function_match = re.search(r"\bfunc\.func\s+@([A-Za-z0-9_.$-]+)", mask)
        if function_match:
            function = function_match.group(1)
        matches = [
            (match.start(), name)
            for name in CLASSES
            for match in re.finditer(rf"(?<![A-Za-z0-9_.]){re.escape(name)}(?![A-Za-z0-9_.])", mask)
        ]
        if not matches:
            line_index += 1
            continue
        if len(matches) != 1:
            raise ValueError("multiple registered memref operations on one line")
        column, name = matches[0]
        start = line_index
        parsed = None
        error: Exception | None = None
        for end in range(start, min(len(lines), start + 33)):
            raw = "\n".join(lines[start : end + 1]).strip()
            try:
                parsed = _signature(name, raw)
            except ValueError as candidate_error:
                error = candidate_error
                continue
            if end + 1 < len(lines) and _masked(lines[end + 1]).strip().startswith("loc("):
                end += 1
                raw = "\n".join(lines[start : end + 1]).strip()
                parsed = _signature(name, raw)
            break
        if parsed is None:
            raise ValueError(f"independent parser failed at line {start + 1}: {error}")
        signature, mlir_location = parsed
        output.append(
            {
                "operation": name,
                "signature": signature,
                "source_location": {
                    "line": start + 1,
                    "column": column + 1,
                    "function": function,
                    "mlir": mlir_location,
                },
            }
        )
        line_index = end + 1
    return output


def _selection(item: dict[str, Any]) -> tuple[str, str, str]:
    location = item["source_location"]
    return (
        item["operation"],
        _canonical(item["signature"]).decode(),
        json.dumps(
            [location.get("function"), location.get("line"), location.get("column"), location.get("mlir")],
            separators=(",", ":"),
        ),
    )


def _script_bytes() -> bytes:
    return b'''#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd -P)"
root="$(cd "$here/../../.." && pwd -P)"
candidate="${1:-$here/input.mlir}"
exec python3 "$root/scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py" \\
  --check-representative "$candidate" --metadata "$here/representative.json"
'''


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "tinystories-1m-exact-memref-representative-v1",
        "operation": item["operation"],
        "signature": item["signature"],
        "signature_sha256": _digest(_canonical(item["signature"])),
        "source_location": item["source_location"],
        "selection_tuple": list(_selection(item)),
    }


def _representative_text(item: dict[str, Any]) -> str:
    signature = item["signature"]
    name = item["operation"]
    args = [f"%source: {signature['operand_types'][0]}"]
    if name == "memref.copy":
        args.append(f"%target: {signature['operand_types'][1]}")
    args.extend(f"{dynamic}: index" for dynamic in signature["dynamic_operands"])
    render_list = lambda values: "[" + ", ".join(str(value) for value in values) + "]"
    render_groups = lambda groups: "[" + ", ".join(render_list(group) for group in groups) + "]"
    if name == "memref.reinterpret_cast":
        op = f"%result = {name} %source to offset: {render_list(signature['offset'])}, sizes: {render_list(signature['sizes'])}, strides: {render_list(signature['strides'])} : {signature['operand_types'][0]} to {signature['result_types'][0]}"
    elif name == "memref.collapse_shape":
        op = f"%result = {name} %source {render_groups(signature['reassociation'])} : {signature['operand_types'][0]} into {signature['result_types'][0]}"
    elif name == "memref.expand_shape":
        op = f"%result = {name} %source {render_groups(signature['reassociation'])} output_shape {render_list(signature['output_shape'])} : {signature['operand_types'][0]} into {signature['result_types'][0]}"
    else:
        op = f"{name} %source, %target : {signature['operand_types'][0]} to {signature['operand_types'][1]}"
    return f"module {{\n  func.func @representative({', '.join(args)}) {{\n    {op}\n    return\n  }}\n}}\n"


def _summary(operations: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    classes: dict[str, Any] = {}
    locations = []
    for name in CLASSES:
        members = [item for item in operations if item["operation"] == name]
        if not members:
            raise ValueError(f"missing registered class {name}")
        selected = min(members, key=_selection)
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in members:
            encoded = _canonical(item["signature"]).decode()
            buckets.setdefault(encoded, []).append(item)
            locations.append(
                {
                    "operation": name,
                    **item["source_location"],
                    "signature_sha256": _digest(_canonical(item["signature"])),
                }
            )
        signatures = [
            {
                "signature": values[0]["signature"],
                "signature_sha256": _digest(_canonical(values[0]["signature"])),
                "multiplicity": len(values),
            }
            for _, values in sorted(buckets.items())
        ]
        slug = name.replace(".", "-").replace("_", "-")
        metadata = _canonical(_metadata(selected)) + b"\n"
        representative = _representative_text(selected).encode()
        classes[name] = {
            "count": len(members),
            "signatures": signatures,
            "representative": {
                "path": f"{REP_PREFIX}/{slug}/input.mlir",
                "sha256": _digest(representative),
                "metadata": f"{REP_PREFIX}/{slug}/representative.json",
                "metadata_sha256": _digest(metadata),
                "interestingness_test": f"{REP_PREFIX}/{slug}/interestingness-test.sh",
                "interestingness_test_sha256": _digest(_script_bytes()),
                "selection_tuple": list(_selection(selected)),
                "signature_sha256": _digest(_canonical(selected["signature"])),
                "source_location": selected["source_location"],
            },
        }
    locations.sort(key=lambda item: (item["operation"], item["function"] or "", item["line"], item["column"], item["signature_sha256"]))
    return classes, locations


def _check_report(operations: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if report.get("stage") != "flat-scf":
        raise ValueError("blocker report stage mismatch")
    blockers = report.get("blockers")
    locations = report.get("locations")
    if not isinstance(blockers, list) or not isinstance(locations, list):
        raise ValueError("malformed blocker report")
    names = {entry.get("op") for entry in blockers if isinstance(entry, dict)}
    if names - CLASS_SET:
        raise ValueError(f"unknown blocker classes: {sorted(names - CLASS_SET)}")
    if names != CLASS_SET:
        raise ValueError("blocker report does not contain exactly four registered classes")
    counts = {name: sum(item["operation"] == name for item in operations) for name in CLASSES}
    if {entry.get("op"): entry.get("count") for entry in blockers} != counts:
        raise ValueError("independently recomputed blocker count mismatch")
    reported = sorted((entry.get("op"), entry.get("line"), entry.get("function")) for entry in locations)
    actual = sorted((entry["operation"], entry["source_location"]["line"], entry["source_location"]["function"]) for entry in operations)
    if reported != actual:
        raise ValueError("independently recomputed blocker location mismatch")


def _actual_rep_path(contract_path: str, representative_root: Path | None) -> Path:
    relative = Path(contract_path)
    if representative_root is None:
        return ROOT / relative
    try:
        suffix = relative.relative_to(REP_PREFIX)
    except ValueError as error:
        raise ValueError("representative path escapes canonical root") from error
    return representative_root / suffix


def _parse_with_tool(tool: Path, module: Path) -> None:
    completed = subprocess.run(
        [str(tool), str(module), "-o", "/dev/null"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"representative does not parse with pinned MLIR tool: {completed.stderr.strip()}")


def _git_no_replace_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _canonical_receipt_bytes() -> bytes:
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
    if tree.returncode or tree.stdout != expected:
        raise ValueError("canonical receipt commit/path/blob binding mismatch")
    blob = subprocess.run(
        ["git", "cat-file", "blob", CANONICAL_RECEIPT_BLOB],
        cwd=ROOT,
        env=_git_no_replace_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if blob.returncode or _digest(blob.stdout) != CANONICAL_RECEIPT_SHA256:
        raise ValueError("canonical receipt Git blob bytes mismatch")
    return blob.stdout


def _check_receipt(receipt: dict[str, Any], receipt_path: Path) -> None:
    if receipt_path.read_bytes() != _canonical_receipt_bytes():
        raise ValueError("c22 receipt bytes differ from canonical Git object")
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    if receipt.get("sha256") != _digest(_canonical(unsigned)):
        raise ValueError("c22 receipt self-hash mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unexpected c22 receipt schema")
    if receipt.get("model") != FROZEN_MODEL:
        raise ValueError("unexpected c22 receipt model")
    if receipt.get("source_commit") != C22_COMMIT:
        raise ValueError("c22 source identity mismatch")
    if receipt.get("frozen_task_1_through_3_identities") != FROZEN_IDENTITIES:
        raise ValueError("unexpected Task 1--3 identities")
    execution = receipt.get("registered_build_execution", {}).get("flat-scf", {})
    tool_bindings = [
        binding
        for binding in execution.get("derivation_tool_bindings", [])
        if Path(str(binding.get("path", ""))).name == "mlir-opt"
    ]
    if len(tool_bindings) != 1 or {
        key: tool_bindings[0].get(key) for key in ("path", "bytes", "sha256")
    } != PINNED_TOOL:
        raise ValueError("unexpected pinned MLIR tool identity")


def _git_object(commit: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        env=_git_no_replace_environment(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise ValueError(f"Task 1 runtime ancestry object is unavailable: {commit}:{path}")
    return completed.stdout


def _runtime_names() -> list[str]:
    reference = re.compile(r"\$\{pipelineScripts\}/([^\s\"\\]+)")
    return sorted(
        {
            Path(match.group(1)).name
            for path in (ROOT / "flake.nix", ROOT / "nix/pipeline.nix")
            for match in reference.finditer(path.read_text(encoding="utf-8"))
        }
    )


def _verify_runtime_equivalence(proof: Any) -> None:
    if not isinstance(proof, dict) or set(proof) != {
        "proof", "task1_commit", "c22_commit", "file_count", "files",
        "filtered_runtime_source", "filtered_runtime_nar_sha256",
    }:
        raise ValueError("Task 1 runtime-equivalence binding is missing or malformed")
    if proof["proof"] != "workspace/task1/c22-git-object-byte-equality":
        raise ValueError("Task 1 runtime-equivalence method mismatch")
    if proof["task1_commit"] != TASK1_COMMIT or proof["c22_commit"] != C22_COMMIT:
        raise ValueError("Task 1/c22 ancestry identity mismatch")
    names = _runtime_names()
    if len(names) != 29 or proof["file_count"] != 29:
        raise ValueError("Task 1 runtime-equivalence file-count mismatch")
    expected_files = []
    for name in names:
        relative = f"scripts/pipeline/{name}"
        workspace = (ROOT / relative).read_bytes()
        if workspace != _git_object(TASK1_COMMIT, relative) or workspace != _git_object(C22_COMMIT, relative):
            raise ValueError(f"Task 1 runtime byte-equivalence failed: {relative}")
        expected_files.append({"path": relative, "bytes": len(workspace), "sha256": _digest(workspace)})
    if proof["files"] != expected_files:
        raise ValueError("Task 1 runtime-equivalence payload mismatch")
    if proof["filtered_runtime_source"] != RUNTIME_SOURCE or proof["filtered_runtime_nar_sha256"] != RUNTIME_NAR_HASH:
        raise ValueError("Task 1 filtered runtime source/NAR identity mismatch")
    if not Path(RUNTIME_SOURCE).is_dir():
        raise ValueError("Task 1 filtered runtime source is unavailable")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", C22_COMMIT, TASK1_COMMIT],
        cwd=ROOT, env=_git_no_replace_environment(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    task1_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", TASK1_COMMIT, "HEAD"],
        cwd=ROOT, env=_git_no_replace_environment(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if ancestry.returncode or task1_ancestor.returncode:
        raise ValueError("c22 -> Task 1 -> current ancestry proof failed")


def _nix_value(field: str) -> str:
    completed = subprocess.run(
        ["nix", "eval", "--raw", f".#{ALIAS}.{field}"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ValueError(f"cannot resolve current registered alias {field}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def verify_contract_payload(
    payload: dict[str, Any],
    root: Path,
    flat_scf: Path,
    blockers: Path,
    manifest: Path,
    receipt_path: Path,
    *,
    skip_nix_resolution: bool,
    representative_root: Path | None = None,
) -> dict[str, int]:
    expected_keys = {
        "schema", "status", "model", "registered_classes", "source", "nix", "tool",
        "c22_receipt_self_sha256", "task_1_through_3_identities", "task1_runtime_equivalence",
        "receipt_git_anchor", "classes", "locations", "sha256",
    }
    if set(payload) != expected_keys:
        raise ValueError("contract schema keys mismatch")
    if payload.get("schema") != "tinystories-1m-exact-memref-blockers-v1" or payload.get("status") != "authenticated":
        raise ValueError("contract schema/status mismatch")
    if payload.get("model") != FROZEN_MODEL:
        raise ValueError("contract model mismatch")
    unsigned = copy.deepcopy(payload)
    claimed = unsigned.get("sha256")
    unsigned["sha256"] = None
    if claimed != _digest(_canonical(unsigned)):
        raise ValueError("contract self-hash mismatch")
    if payload.get("registered_classes") != list(CLASSES):
        raise ValueError("contract registered class order mismatch")
    if set(payload.get("classes", {})) - CLASS_SET:
        raise ValueError("contract contains unknown blocker classes")
    if set(payload.get("classes", {})) != CLASS_SET:
        raise ValueError("contract must contain exactly four registered classes")
    if payload.get("receipt_git_anchor") != {
        "commit": CANONICAL_RECEIPT_COMMIT,
        "path": CANONICAL_RECEIPT_PATH,
        "blob": CANONICAL_RECEIPT_BLOB,
        "sha256": CANONICAL_RECEIPT_SHA256,
    }:
        raise ValueError("canonical receipt Git anchor mismatch")

    paths = {"flat_scf": flat_scf, "blockers": blockers, "manifest": manifest, "c22_receipt": receipt_path}
    expected_source_paths = {
        "flat_scf": "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/flat.scf.mlir",
        "blockers": "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/blockers.json",
        "manifest": "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/minimal-reproducer.json",
        "c22_receipt": "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/receipt.json",
    }
    if set(payload["source"]) != set(paths):
        raise ValueError("contract source payload set mismatch")
    for name, path in paths.items():
        expected = payload["source"].get(name)
        if (
            not isinstance(expected, dict)
            or set(expected) != {"path", "bytes", "sha256"}
            or expected.get("path") != expected_source_paths[name]
            or {key: expected.get(key) for key in ("bytes", "sha256")} != _binding(path)
        ):
            label = "flat.scf.mlir" if name == "flat_scf" else name
            raise ValueError(f"{label} payload binding mismatch")
    receipt = _object(receipt_path, "c22 receipt")
    _check_receipt(receipt, receipt_path)
    if receipt["sha256"] != payload["c22_receipt_self_sha256"]:
        raise ValueError("c22 receipt identity mismatch")
    if payload.get("task_1_through_3_identities") != FROZEN_IDENTITIES:
        raise ValueError("Task 1--3 identities mismatch")
    _verify_runtime_equivalence(payload["task1_runtime_equivalence"])
    expected_manifest = {"artifact": "flat.scf.mlir", "blockers": "blockers.json", "stage": "flat-scf", "status": "completed-with-residuals"}
    if _object(manifest, "flat-SCF manifest") != expected_manifest:
        raise ValueError("flat-SCF manifest mismatch")
    execution = receipt.get("registered_build_execution", {}).get("flat-scf", {})
    if (
        execution.get("derivation") != payload["nix"].get("c22_derivation")
        or execution.get("result") != payload["nix"].get("c22_output")
    ):
        raise ValueError("c22 receipt ancestry binding mismatch")
    tool_bindings = [
        binding for binding in execution.get("derivation_tool_bindings", [])
        if Path(str(binding.get("path", ""))).name == "mlir-opt"
    ]
    if len(tool_bindings) != 1 or {
        key: tool_bindings[0].get(key) for key in ("path", "bytes", "sha256")
    } != PINNED_TOOL:
        raise ValueError("c22 receipt MLIR tool binding mismatch")

    if not skip_nix_resolution:
        if _nix_value("drvPath") != payload["nix"]["current_derivation"] or _nix_value("outPath") != payload["nix"]["current_output"]:
            raise ValueError("current registered alias identity mismatch")
        c22_output = Path(payload["nix"]["c22_output"])
        if not c22_output.is_dir():
            raise ValueError("retained c22 live Nix output is unavailable")
        for name, filename in (("manifest", "manifest.json"), ("flat_scf", "flat.scf.mlir"), ("blockers", "blockers.json")):
            if (c22_output / filename).read_bytes() != paths[name].read_bytes():
                raise ValueError(f"retained c22 live {name} bytes differ")
        queried = subprocess.run(
            ["nix-store", "-q", "--deriver", str(c22_output)], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if queried.returncode or queried.stdout.strip() != payload["nix"]["c22_derivation"]:
            raise ValueError("retained c22 Nix deriver mismatch")
        nar = subprocess.run(
            ["nix", "hash", "path", "--type", "sha256", RUNTIME_SOURCE],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if nar.returncode or nar.stdout.strip() != RUNTIME_NAR_HASH:
            raise ValueError("Task 1 filtered runtime NAR verification failed")

    nix_binding = payload["nix"]
    if set(nix_binding) != {
        "alias_attribute", "current_derivation", "current_output", "current_output_realized",
        "c22_derivation", "c22_output", "payload_source", "provenance_residual",
    }:
        raise ValueError("Nix ancestry/equivalence binding is incomplete")
    if nix_binding["alias_attribute"] != ALIAS:
        raise ValueError("registered alias name mismatch")
    if nix_binding["current_derivation"] == nix_binding["c22_derivation"]:
        raise ValueError("c22 deriver is incorrectly identified as the current alias")
    if nix_binding["current_output_realized"] is not False or Path(nix_binding["current_output"]).exists():
        raise ValueError("protected current alias must remain explicitly unrealized")
    if nix_binding["payload_source"] != "retained-authenticated-c22-output":
        raise ValueError("retained c22 payload source is not explicit")

    if payload.get("tool") != PINNED_TOOL:
        raise ValueError("pinned MLIR tool identity mismatch")
    if set(payload["tool"]) != {"path", "bytes", "sha256"}:
        raise ValueError("pinned MLIR tool schema mismatch")
    tool = Path(payload["tool"]["path"])
    if not tool.is_file() or {key: payload["tool"].get(key) for key in ("bytes", "sha256")} != _binding(tool):
        raise ValueError("pinned MLIR tool binding mismatch")
    _parse_with_tool(tool, flat_scf)
    operations = _independent_operations(flat_scf.read_text(encoding="utf-8"))
    _check_report(operations, _object(blockers, "blockers report"))
    classes, locations = _summary(operations)
    if payload["classes"] != classes:
        raise ValueError("independently recomputed signatures/counts/representatives mismatch")
    if payload["locations"] != locations:
        raise ValueError("independently recomputed contract locations mismatch")

    for name, entry in classes.items():
        representative = entry["representative"]
        module_path = _actual_rep_path(representative["path"], representative_root)
        metadata_path = _actual_rep_path(representative["metadata"], representative_root)
        script_path = _actual_rep_path(representative["interestingness_test"], representative_root)
        try:
            if _binding(module_path)["sha256"] != representative["sha256"]:
                raise ValueError("representative module hash mismatch")
            if _binding(metadata_path)["sha256"] != representative["metadata_sha256"]:
                raise ValueError("representative metadata hash mismatch")
            if _binding(script_path)["sha256"] != representative["interestingness_test_sha256"]:
                raise ValueError("representative interestingness hash mismatch")
            _parse_with_tool(tool, module_path)
            parsed = _independent_operations(module_path.read_text(encoding="utf-8"))
            metadata = _object(metadata_path, "representative metadata")
            if len(parsed) != 1 or parsed[0]["operation"] != name or parsed[0]["signature"] != metadata.get("signature"):
                raise ValueError("representative exact interestingness mismatch")
        except (OSError, ValueError) as error:
            raise ValueError(f"representative {name} verification failed: {error}") from error
    return {name: classes[name]["count"] for name in CLASSES}


def check_representative(module: Path, metadata_path: Path) -> None:
    payload = _object(CONTRACT, "memref blocker contract")
    verify_contract_payload(
        payload,
        ROOT,
        CAPTURE / "flat.scf.mlir",
        CAPTURE / "blockers.json",
        CAPTURE / "minimal-reproducer.json",
        CAPTURE / "receipt.json",
        skip_nix_resolution=False,
    )
    metadata = _object(metadata_path, "representative metadata")
    operation_name = metadata.get("operation")
    if (
        metadata.get("schema") != "tinystories-1m-exact-memref-representative-v1"
        or operation_name not in CLASS_SET
    ):
        raise ValueError("unknown representative metadata")
    representative = payload["classes"][operation_name]["representative"]
    canonical_metadata_path = ROOT / representative["metadata"]
    if (
        metadata_path.read_bytes() != canonical_metadata_path.read_bytes()
        or _binding(metadata_path)["sha256"] != representative["metadata_sha256"]
    ):
        raise ValueError("representative metadata differs from authenticated contract selection")
    tool = Path(PINNED_TOOL["path"])
    if {"path": str(tool), **_binding(tool)} != PINNED_TOOL:
        raise ValueError("pinned representative MLIR tool mismatch")
    _parse_with_tool(tool, module)
    operations = _independent_operations(module.read_text(encoding="utf-8"))
    if len(operations) != 1:
        raise ValueError("representative must contain exactly one registered operation")
    operation = operations[0]
    if operation["operation"] != operation_name or operation["signature"] != metadata["signature"]:
        raise ValueError("representative exact class/signature mismatch")
    if _digest(_canonical(operation["signature"])) != metadata["signature_sha256"]:
        raise ValueError("representative signature hash mismatch")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--flat-scf", type=Path, default=CAPTURE / "flat.scf.mlir")
    parser.add_argument("--blockers", type=Path, default=CAPTURE / "blockers.json")
    parser.add_argument("--manifest", type=Path, default=CAPTURE / "minimal-reproducer.json")
    parser.add_argument("--receipt", type=Path, default=CAPTURE / "receipt.json")
    parser.add_argument("--skip-nix-resolution", action="store_true")
    parser.add_argument("--check-representative", type=Path)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _args()
    try:
        if args.check_representative is not None:
            if args.metadata is None:
                raise ValueError("--check-representative requires --metadata")
            check_representative(args.check_representative, args.metadata)
            print("PASS: representative parses and has the exact required class/signature")
            return 0
        payload = _object(args.contract, "memref blocker contract")
        counts = verify_contract_payload(
            payload, ROOT, args.flat_scf, args.blockers, args.manifest, args.receipt,
            skip_nix_resolution=args.skip_nix_resolution,
        )
        print(f"PASS: independently recomputed exact flat-SCF memref blockers {json.dumps(counts, sort_keys=True)}")
        return 0
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
