#!/usr/bin/env python3
"""Replay the authenticated exact static-subview extension in causal order."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
BASELINE_EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
TASK2_EXTRACTOR = ROOT / "scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py"
TASK2_VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
BASELINE_VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py"
DEFAULT_OUTPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json"
DEFAULT_EVIDENCE = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence"
DEFAULT_REPORT = ROOT / "docs/results/2026-09-01-tinystories-1m-subview-extension-evaluation.md"
PREDECESSOR = ROOT / "reproducers/tinystories-1m-exact-flat-scf-memref/task3-earliest-remaining/input.mlir"
IDENTITY_PROBE = ROOT / "reproducers/tinystories-1m-exact-static-subview-extension/identity-offset.mlir"
NONZERO_PROBE = ROOT / "reproducers/tinystories-1m-exact-static-subview-extension/nonzero-offset-stride.mlir"
PASS_SOURCE = ROOT / "tools/mlir-passes/FoldConstantTruncFOps.cpp"
PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
BASELINE_EVALUATION_SHA256 = "26e0ddcaf0abc6100332378d2cacf0555f3560a7635bcdd60dbb9f47bd5ad0d8"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
EARLIEST_SIGNATURE_SHA256 = "6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693"
ASSIGNED_BASE = "3e3441a3eddaf912ccd858b605d0b4bd990852c7"
TASK1_COMMIT = "edd4acb69beb9c7242722f323a96422fd40b8399"
TASK2_IMPLEMENTATION_COMMIT = "fe1e621d8d892156b8d3fff5cd0f1b96a846eac1"
PASS_SOURCE_BLOB = "8aecb2bdb66cdf179b8517828766e962ffdc6889"
TOOL = {
    "path": "/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt",
    "bytes": 496904,
    "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
}
BASELINE_PLUGIN = {
    "path": "/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21714240,
    "sha256": "6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744",
}
PLUGIN = {
    "path": "/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21720848,
    "sha256": "6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9",
}
INPUT_IDENTITIES = {
    "predecessor-task3-subview": {
        "bytes": 200,
        "sha256": "1c0c5e3a0b994782554a6471641c4a73a2addd09850fecefa03d1132403d615c",
    },
    "semantic-identity-offset": {
        "bytes": 432,
        "sha256": "831e4c65d2e0d47b28beae8d9d3e98abb70752ac22afb54747089483d31b7c63",
    },
    "semantic-nonzero-offset-stride": {
        "bytes": 477,
        "sha256": "70a7b7eeab23d75140427afaa9405fa1b0f7c4999e860d91bf1a104b50111382",
    },
}
PROBE_SPECS = {
    "semantic-identity-offset": {
        "function": "identity_offset",
        "variables": [
            {"name": "i0", "argument": 1, "lower_inclusive": 0, "upper_exclusive": 64},
            {"name": "i1", "argument": 2, "lower_inclusive": 0, "upper_exclusive": 1},
        ],
        "offset": 0,
        "coefficients": [64, 1],
    },
    "semantic-nonzero-offset-stride": {
        "function": "nonzero_offset_stride",
        "variables": [
            {"name": "i0", "argument": 1, "lower_inclusive": 0, "upper_exclusive": 16},
            {"name": "i1", "argument": 2, "lower_inclusive": 0, "upper_exclusive": 8},
        ],
        "offset": 64,
        "coefficients": [128, 2],
    },
}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_binding(path: Path, *, relative: bool = False) -> dict[str, Any]:
    raw = path.read_bytes()
    rendered = str(path.relative_to(ROOT)) if relative else str(path)
    return {"path": rendered, "bytes": len(raw), "sha256": sha256_bytes(raw)}


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_binding(path: Path, expected: dict[str, Any], label: str) -> None:
    if not path.is_file() or file_binding(path) != expected:
        raise ValueError(f"{label} identity mismatch")


def load_task2_parser():
    spec = importlib.util.spec_from_file_location("exact_memref_task2_parser", TASK2_EXTRACTOR)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load authenticated Task 2 parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_decision_gate(
    *,
    parseable: bool,
    blocker_counts: dict[str, int | None],
    new_invalid_classes: list[str],
    semantic_status: str,
) -> str:
    if (
        parseable
        and set(blocker_counts) == set(REGISTERED)
        and all(isinstance(blocker_counts[name], int) for name in REGISTERED)
        and not new_invalid_classes
        and semantic_status == "proven"
    ):
        return "valid_normalized_output"
    return "next_compiler_frontier"


def _logical_lines(text: str) -> list[str]:
    text = re.sub(r"\n\s+(:\s+memref<)", r" \1", text)
    return text.splitlines()


_FUNC = re.compile(r"^\s*func\.func @([A-Za-z0-9_.$-]+)\((.*)\) -> i64 \{\s*$")
_ARG = re.compile(r"(%[A-Za-z0-9_.$-]+)\s*:\s*(memref<[^>]+>|index|i64)")
_CONSTANT = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.constant\s+(-?[0-9]+)\s*:\s*index\s*$")
_BINARY = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.(addi|subi|muli)\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:\s*index\s*$")
_ALIAS = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*memref\.(?:subview|collapse_shape|expand_shape|reinterpret_cast)\s+(%[A-Za-z0-9_.$-]+)\b")
_LOAD = re.compile(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.load\s+(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_STORE = re.compile(r"^\s*memref\.store\s+%[A-Za-z0-9_.$-]+,\s*(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")


def _affine_add(left: dict[str, Any], right: dict[str, Any], scale: int = 1) -> dict[str, Any]:
    return {
        "coefficients": [
            lhs + scale * rhs
            for lhs, rhs in zip(left["coefficients"], right["coefficients"])
        ],
        "offset": left["offset"] + scale * right["offset"],
    }


def _affine_scale(value: dict[str, Any], factor: int) -> dict[str, Any]:
    return {
        "coefficients": [factor * item for item in value["coefficients"]],
        "offset": factor * value["offset"],
    }


def _derive_affine_proof(text: str, *, probe_id: str) -> dict[str, Any]:
    if probe_id not in PROBE_SPECS:
        raise ValueError("unknown semantic probe")
    spec = PROBE_SPECS[probe_id]
    parser = load_task2_parser()
    lines = _logical_lines(text)
    function = next((match for line in lines if (match := _FUNC.match(line))), None)
    if function is None or function.group(1) != spec["function"]:
        raise ValueError("semantic probe function mismatch")
    arguments = list(_ARG.finditer(function.group(2)))
    variables = copy.deepcopy(spec["variables"])
    expressions: dict[str, dict[str, Any]] = {}
    for position, variable in enumerate(variables):
        argument = arguments[variable["argument"]]
        if argument.group(2) != "index":
            raise ValueError("semantic probe variable argument mismatch")
        coefficients = [0] * len(variables)
        coefficients[position] = 1
        expressions[argument.group(1)] = {"coefficients": coefficients, "offset": 0}
    for line in lines:
        if match := _CONSTANT.match(line):
            expressions[match.group(1)] = {
                "coefficients": [0] * len(variables),
                "offset": int(match.group(2)),
            }
            continue
        match = _BINARY.match(line)
        if match is None:
            continue
        left = expressions.get(match.group(3))
        right = expressions.get(match.group(4))
        if left is None or right is None:
            raise ValueError("semantic probe has unresolved index arithmetic")
        if match.group(2) == "addi":
            value = _affine_add(left, right)
        elif match.group(2) == "subi":
            value = _affine_add(left, right, -1)
        else:
            left_constant = not any(left["coefficients"])
            right_constant = not any(right["coefficients"])
            if not left_constant and not right_constant:
                raise ValueError("semantic probe contains non-affine multiplication")
            value = _affine_scale(
                right if left_constant else left,
                left["offset"] if left_constant else right["offset"],
            )
        expressions[match.group(1)] = value
    memref_arguments = {
        item.group(1): arguments.index(item)
        for item in arguments
        if item.group(2).startswith("memref<")
    }
    aliases = {
        match.group(1): match.group(2)
        for line in lines
        if (match := _ALIAS.match(line))
    }

    def base_argument(name: str) -> int:
        visited = set()
        while name in aliases:
            if name in visited:
                raise ValueError("semantic probe view cycle")
            visited.add(name)
            name = aliases[name]
        if name not in memref_arguments:
            raise ValueError("semantic probe access base is not a function argument")
        return memref_arguments[name]

    accesses = []
    for line in lines:
        matched = _STORE.match(line)
        kind = "store"
        if matched is None:
            matched = _LOAD.match(line)
            kind = "load"
        if matched is None:
            continue
        memref = parser.parse_memref_type(matched.group(3))
        raw_indices = []
        for token in (item.strip() for item in matched.group(2).split(",")):
            expression = expressions.get(token)
            if expression is None:
                raise ValueError("semantic probe contains a dynamic index")
            raw_indices.append(copy.deepcopy(expression))
        if len(raw_indices) != memref["rank"]:
            raise ValueError("semantic probe access rank mismatch")
        for expression, dimension in zip(raw_indices, memref["shape"]):
            if not isinstance(dimension, int):
                raise ValueError("semantic probe has dynamic access shape")
            lower = upper = expression["offset"]
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
        if not isinstance(memref["offset"], int) or not all(
            isinstance(stride, int) for stride in memref["strides"]
        ):
            raise ValueError("semantic probe has dynamic layout")
        linear = {"coefficients": [0] * len(variables), "offset": memref["offset"]}
        for stride, expression in zip(memref["strides"], raw_indices):
            linear = _affine_add(linear, _affine_scale(expression, stride))
        accesses.append(
            {
                "kind": kind,
                "base": {
                    "argument": base_argument(matched.group(1)),
                    "role": "target" if kind == "store" else "source",
                },
                "raw_indices": raw_indices,
                "linear_formula": linear,
            }
        )
    if {item["kind"] for item in accesses} != {"load", "store"} or len(accesses) != 2:
        raise ValueError("semantic probe must contain one load and one store")
    return {
        "affine_status": "proven",
        "index_variables": variables,
        "access_maps": accesses,
    }


def derive_affine_proof(text: str, *, probe_id: str) -> dict[str, Any]:
    try:
        return _derive_affine_proof(text, probe_id=probe_id)
    except ValueError as error:
        return {"affine_status": "unproven", "reason": str(error)}


def proof_matches_literal(proof: dict[str, Any], probe_id: str) -> bool:
    spec = PROBE_SPECS[probe_id]
    return (
        proof.get("affine_status") == "proven"
        and proof.get("index_variables") == spec["variables"]
        and len(proof.get("access_maps", [])) == 2
        and {item["kind"] for item in proof["access_maps"]} == {"load", "store"}
        and all(item["base"]["argument"] == 0 for item in proof["access_maps"])
        and all(
            item["base"]["role"] == ("target" if item["kind"] == "store" else "source")
            for item in proof["access_maps"]
        )
        and all(
            item["linear_formula"]
            == {"coefficients": spec["coefficients"], "offset": spec["offset"]}
            for item in proof["access_maps"]
        )
        and all(
            index["range"]["in_bounds"]
            for item in proof["access_maps"]
            for index in item["raw_indices"]
        )
    )


def _mask_line(line: str) -> str:
    result: list[str] = []
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


_OP_LINE = re.compile(
    r"^\s*(?:[%][^=]+?=\s*)?(?:\([^=]+\)\s*=\s*)?"
    r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_GENERIC_OP_LINE = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*\(')


def _decode_mlir_name(raw: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(raw):
        if raw[index] != "\\":
            result.append(raw[index])
            index += 1
            continue
        index += 1
        if index >= len(raw):
            raise ValueError("incomplete generic operation-name escape")
        escaped = raw[index]
        if escaped in {'"', "\\"}:
            result.append(escaped)
            index += 1
        elif escaped == "n":
            result.append("\n")
            index += 1
        elif escaped == "t":
            result.append("\t")
            index += 1
        elif (
            index + 1 < len(raw)
            and escaped in "0123456789abcdefABCDEF"
            and raw[index + 1] in "0123456789abcdefABCDEF"
        ):
            result.append(chr(int(raw[index : index + 2], 16)))
            index += 2
        else:
            raise ValueError("unknown generic operation-name escape")
    return "".join(result)


def operation_census(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in text.splitlines():
        match = _OP_LINE.match(_mask_line(raw))
        if match is not None:
            name = match.group(1)
        else:
            generic = _GENERIC_OP_LINE.match(raw)
            if generic is None:
                continue
            name = _decode_mlir_name(generic.group(1))
            if re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*", name
            ) is None:
                raise ValueError("malformed generic operation name")
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def registered_counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return {
        name: sum(item["operation"] == name for item in operations)
        for name in REGISTERED
    }


def new_invalid_classes(before: dict[str, int], after: dict[str, int]) -> list[str]:
    suspicious = re.compile(r"(?:view|cast|shape|copy)")
    return sorted(
        name
        for name in after
        if name.startswith("memref.")
        and name not in before
        and name not in REGISTERED
        and suspicious.search(name.split(".", 1)[1])
    )


def run_pass(
    *,
    sequence: int,
    identifier: str,
    kind: str,
    input_path: Path,
    output_dir: Path,
    causal_preconditions_satisfied: bool,
) -> dict[str, Any]:
    if not causal_preconditions_satisfied:
        raise ValueError(f"causal preconditions failed before {identifier}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "output.mlir"
    stdout_path = output_dir / "stdout.bin"
    stderr_path = output_dir / "stderr.bin"
    parse_stdout_path = output_dir / "parse.stdout.bin"
    parse_stderr_path = output_dir / "parse.stderr.bin"
    output_path.unlink(missing_ok=True)
    before = file_binding(input_path, relative=True)
    command = [
        TOOL["path"],
        str(input_path),
        f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}",
        "-o",
        str(output_path),
    ]
    started = time.monotonic_ns()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.monotonic_ns() - started
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    output_created = output_path.exists()
    if not output_created:
        output_path.write_bytes(b"")
    after_input = file_binding(input_path, relative=True)
    if before != after_input:
        raise ValueError(f"pass mutated input bytes for {identifier}")
    parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
    parsed = subprocess.run(
        parse_command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    parse_stdout_path.write_bytes(parsed.stdout)
    parse_stderr_path.write_bytes(parsed.stderr)
    return {
        "sequence": sequence,
        "id": identifier,
        "kind": kind,
        "causal_preconditions_satisfied": causal_preconditions_satisfied,
        "command": command,
        "input": before,
        "input_after": after_input,
        "exit_code": completed.returncode,
        "elapsed_ns": elapsed,
        "output_created": output_created,
        "stdout": file_binding(stdout_path, relative=True),
        "stderr": file_binding(stderr_path, relative=True),
        "output": file_binding(output_path, relative=True),
        "parse_check": {
            "command": parse_command,
            "exit_code": parsed.returncode,
            "stdout": file_binding(parse_stdout_path, relative=True),
            "stderr": file_binding(parse_stderr_path, relative=True),
        },
        "parseable": completed.returncode == 0 and parsed.returncode == 0,
    }


def _git_bytes(commit: str, relative: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ValueError(f"cannot read authenticated source {commit}:{relative}")
    return completed.stdout


def source_revision_binding() -> dict[str, Any]:
    relative = "tools/mlir-passes/FoldConstantTruncFOps.cpp"
    source = PASS_SOURCE.read_bytes()
    if source != _git_bytes(ASSIGNED_BASE, relative):
        raise ValueError("Task 2 pass source differs from assigned base")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ASSIGNED_BASE, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestry.returncode:
        raise ValueError("assigned Task 3 base is not an ancestor of HEAD")
    return {
        "assigned_base": ASSIGNED_BASE,
        "task1_commit": TASK1_COMMIT,
        "task2_implementation_commit": TASK2_IMPLEMENTATION_COMMIT,
        "pass_source_blob": PASS_SOURCE_BLOB,
        "pass_source": file_binding(PASS_SOURCE, relative=True),
    }


def _known_subview_signature(text: str, parser: Any) -> dict[str, Any]:
    compact = " ".join(piece.strip() for piece in text.splitlines() if piece.strip())
    match = re.search(
        r"memref\.subview\s+%[A-Za-z0-9_.$-]+\[([^]]+)\]\s*"
        r"\[([^]]+)\]\s*\[([^]]+)\]\s*:\s*(memref<.+>)\s+to\s+(memref<.+>)$",
        compact,
    )
    if match is None:
        raise ValueError("diagnostic subview signature is not canonical")

    def integers(raw: str) -> list[int]:
        values = [item.strip() for item in raw.split(",")]
        if not all(re.fullmatch(r"-?[0-9]+", item) for item in values):
            raise ValueError("diagnostic subview has dynamic metadata")
        return [int(item) for item in values]

    source_type, result_type = match.group(4), match.group(5)
    return {
        "operation": "memref.subview",
        "operand_types": [source_type],
        "result_types": [result_type],
        "operand_memrefs": [parser.parse_memref_type(source_type)],
        "result_memrefs": [parser.parse_memref_type(result_type)],
        "offsets": integers(match.group(1)),
        "sizes": integers(match.group(2)),
        "strides": integers(match.group(3)),
    }


def _render_subview_reproducer(signature: dict[str, Any]) -> str:
    render = lambda values: ", ".join(str(value) for value in values)
    source_type = signature["operand_types"][0]
    result_type = signature["result_types"][0]
    return (
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


def diagnostic_frontier(
    *, stderr: bytes, source_path: Path, evidence_root: Path, parser: Any
) -> dict[str, Any]:
    diagnostic = stderr.decode("utf-8", errors="strict")
    location = re.search(r":([0-9]+):([0-9]+): error: ([^\n]+)", diagnostic)
    if location is None:
        raise ValueError("full failure has no canonical diagnostic")
    line_number, column = int(location.group(1)), int(location.group(2))
    operations = parser.parse_registered_operations(source_path.read_text(encoding="utf-8"))
    registered = next(
        (item for item in operations if item["source_location"]["line"] == line_number),
        None,
    )
    if registered is not None:
        signature = registered["signature"]
        operation = registered["operation"]
        reproducer_text = parser.render_representative(registered)
    else:
        lines = source_path.read_text(encoding="utf-8").splitlines()
        if not 1 <= line_number <= len(lines) or "memref.subview" not in lines[line_number - 1]:
            raise ValueError("unsupported independently reconstructed diagnostic class")
        candidate = "\n".join(lines[line_number - 1 : line_number + 2])
        signature = _known_subview_signature(candidate, parser)
        operation = "memref.subview"
        reproducer_text = _render_subview_reproducer(signature)
    directory = evidence_root / "next-frontier"
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "input.mlir"
    input_path.write_text(reproducer_text, encoding="utf-8")
    run = run_pass(
        sequence=1,
        identifier="next-frontier-reproducer",
        kind="frontier_reproducer",
        input_path=input_path,
        output_dir=directory,
        causal_preconditions_satisfied=True,
    )
    metadata = {
        "schema": "tinystories-1m-exact-subview-frontier-reproducer-v1",
        "kind": "diagnostic",
        "operation": operation,
        "signature": signature,
        "signature_sha256": sha256_bytes(canonical_json(signature)),
        "source_location": {
            "function": registered["source_location"]["function"] if registered else "main",
            "line": line_number,
            "column": column,
            "mlir": registered["source_location"]["mlir"] if registered else None,
        },
        "diagnostic": location.group(3),
        "execution": run,
    }
    metadata_path = directory / "metadata.json"
    metadata_path.write_bytes(canonical_json(metadata) + b"\n")
    return {
        "kind": "diagnostic",
        "operation": operation,
        "signature": signature,
        "signature_sha256": sha256_bytes(canonical_json(signature)),
        "source_location": metadata["source_location"],
        "diagnostic": location.group(3),
        "reproducer": {
            **file_binding(input_path, relative=True),
            "operation_count": 1,
            "metadata": file_binding(metadata_path, relative=True),
        },
    }


def _report(payload: dict[str, Any]) -> str:
    complete = payload["complete"]
    rows = []
    for name in REGISTERED:
        after = complete["after"]["registered_blocker_counts"][name]
        rows.append(
            f"| `{name}` | {complete['before']['registered_blocker_counts'][name]:,} | "
            + (f"{after:,}" if isinstance(after, int) else "unavailable")
            + " |"
        )
    probes = []
    for probe in payload["semantic_probes"]:
        formula = probe["after"]["access_maps"][0]["linear_formula"]
        probes.append(
            f"| `{probe['id']}` | `{probe['invariant_status']}` | "
            f"`offset={formula['offset']}, coefficients={formula['coefficients']}` |"
        )
    branch = (
        f"- Normalized artifact: `{payload['normalized_artifact']['path']}`\n"
        if payload["decision"] == "valid_normalized_output"
        else (
            f"- Next frontier: `{payload['next_frontier']['operation']}` / "
            f"`{payload['next_frontier']['signature_sha256']}`\n"
        )
    )
    elapsed = sum(run["elapsed_ns"] for run in payload["executions"])
    return f"""# Exact TinyStories-1M static-subview extension evaluation

The rebuilt pass was replayed in causal order against the authenticated
predecessor reproducer, the two complete affine probes, and only then the
18,933,168-byte retained c22 flat-SCF artifact. No Calyx stage ran and no Nix
pipeline stage was registered.

## Decision

`{payload['decision']}`

{branch}
## Semantic probes

| Probe | Status | Complete affine mapping |
| --- | --- | --- |
{chr(10).join(probes)}

## Full registered-blocker census

| Registered class | Before | After |
| --- | ---: | ---: |
{chr(10).join(rows)}

- Full output parseable: `{str(complete['parseable']).lower()}`
- New invalid classes: `{len(complete['new_invalid_classes'])}`
- Semantic boundary/access status: `{complete['invariant_status']}`
- Input SHA-256: `{payload['input']['sha256']}`
- Tool SHA-256: `{payload['tool']['sha256']}`
- Baseline plugin SHA-256: `{payload['baseline_plugin']['sha256']}`
- Rebuilt plugin SHA-256: `{payload['plugin']['sha256']}`
- Exact pipeline: `{payload['pipeline']}`
- Measured time over four ordered executions: `{elapsed}` ns
"""


def evaluate(*, output: Path, evidence_root: Path, report: Path) -> dict[str, Any]:
    require_binding(Path(TOOL["path"]), TOOL, "pinned MLIR tool")
    require_binding(Path(BASELINE_PLUGIN["path"]), BASELINE_PLUGIN, "baseline plugin")
    require_binding(Path(PLUGIN["path"]), PLUGIN, "rebuilt plugin")
    if PLUGIN["sha256"] == BASELINE_PLUGIN["sha256"]:
        raise ValueError("rebuilt plugin does not differ from baseline")
    if sha256_bytes(CONTRACT.read_bytes()) != CONTRACT_SHA256:
        raise ValueError("authenticated Task 2 contract bytes mismatch")
    if sha256_bytes(BASELINE_EVALUATION.read_bytes()) != BASELINE_EVALUATION_SHA256:
        raise ValueError("authenticated baseline evaluation bytes mismatch")
    for verifier, label in (
        (TASK2_VERIFIER, "Task 2 contract"),
        (BASELINE_VERIFIER, "baseline evaluation"),
    ):
        authenticated = subprocess.run(
            [sys.executable, str(verifier)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if authenticated.returncode:
            raise ValueError(
                f"authenticated {label} verification failed: "
                + authenticated.stderr.decode(errors="replace")
            )
    contract = load_json(CONTRACT, "Task 2 contract")
    baseline = load_json(BASELINE_EVALUATION, "baseline evaluation")
    if baseline.get("decision") != "compiler_pass_extension":
        raise ValueError("baseline decision drifted")
    if (
        baseline.get("earliest_remaining_signature", {}).get("signature_sha256")
        != EARLIEST_SIGNATURE_SHA256
    ):
        raise ValueError("baseline earliest frontier drifted")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    if file_binding(flat_scf, relative=True) != {
        "path": contract["source"]["flat_scf"]["path"],
        "bytes": 18_933_168,
        "sha256": FLAT_SCF_SHA256,
    }:
        raise ValueError("retained c22 input identity mismatch")
    for identifier, path in (
        ("predecessor-task3-subview", PREDECESSOR),
        ("semantic-identity-offset", IDENTITY_PROBE),
        ("semantic-nonzero-offset-stride", NONZERO_PROBE),
    ):
        expected = {"path": str(path.relative_to(ROOT)), **INPUT_IDENTITIES[identifier]}
        if file_binding(path, relative=True) != expected:
            raise ValueError(f"{identifier} input identity mismatch")

    evidence_root.mkdir(parents=True, exist_ok=True)
    executions = []
    predecessor_run = run_pass(
        sequence=1,
        identifier="predecessor-task3-subview",
        kind="predecessor_reproducer",
        input_path=PREDECESSOR,
        output_dir=evidence_root / "predecessor-task3-subview",
        causal_preconditions_satisfied=True,
    )
    executions.append(predecessor_run)
    predecessor_text = (ROOT / predecessor_run["output"]["path"]).read_text(encoding="utf-8")
    predecessor_checks = {
        "exit_zero": predecessor_run["exit_code"] == 0,
        "parseable": predecessor_run["parseable"],
        "subview_eliminated": "memref.subview" not in predecessor_text,
        "flattened_argument_present": "memref<4096xi64>" in predecessor_text,
    }
    predecessor_proven = all(predecessor_checks.values())
    predecessor_result = {
        "execution_id": predecessor_run["id"],
        "signature_sha256": EARLIEST_SIGNATURE_SHA256,
        "legalization_status": "proven" if predecessor_proven else "unproven",
        "checks": predecessor_checks,
    }
    if not predecessor_proven:
        raise ValueError("predecessor reproducer did not legalize")

    semantic_probes = []
    prior_proven = predecessor_proven
    for sequence, (identifier, input_path) in enumerate(
        (
            ("semantic-identity-offset", IDENTITY_PROBE),
            ("semantic-nonzero-offset-stride", NONZERO_PROBE),
        ),
        start=2,
    ):
        run = run_pass(
            sequence=sequence,
            identifier=identifier,
            kind="semantic_probe",
            input_path=input_path,
            output_dir=evidence_root / identifier,
            causal_preconditions_satisfied=prior_proven,
        )
        executions.append(run)
        before = derive_affine_proof(input_path.read_text(encoding="utf-8"), probe_id=identifier)
        output_text = (ROOT / run["output"]["path"]).read_text(encoding="utf-8")
        after = derive_affine_proof(output_text, probe_id=identifier)
        checks = {
            "exit_zero": run["exit_code"] == 0,
            "parseable": run["parseable"],
            "before_matches_literal_affine_map": proof_matches_literal(before, identifier),
            "after_matches_literal_affine_map": proof_matches_literal(after, identifier),
            "complete_affine_mapping_preserved": (
                proof_matches_literal(before, identifier)
                and proof_matches_literal(after, identifier)
            ),
            "subview_eliminated": "memref.subview" not in output_text,
        }
        proven = all(checks.values())
        semantic_probes.append(
            {
                "id": identifier,
                "execution_id": run["id"],
                "invariant_status": "proven" if proven else "unproven",
                "before": before,
                "after": after,
                "checks": checks,
            }
        )
        if not proven:
            raise ValueError(f"semantic proof failed before full replay: {identifier}")
        prior_proven = prior_proven and proven

    full_run = run_pass(
        sequence=4,
        identifier="complete-retained-c22-flat-scf",
        kind="complete",
        input_path=flat_scf,
        output_dir=evidence_root / "complete-retained-c22-flat-scf",
        causal_preconditions_satisfied=prior_proven,
    )
    executions.append(full_run)
    parser = load_task2_parser()
    before_text = flat_scf.read_text(encoding="utf-8")
    before_operations = parser.parse_registered_operations(before_text)
    before_census = operation_census(before_text)
    if full_run["parseable"]:
        after_text = (ROOT / full_run["output"]["path"]).read_text(encoding="utf-8")
        after_operations = parser.parse_registered_operations(after_text)
        after_counts: dict[str, int | None] = registered_counts(after_operations)
        after_registered_count: int | None = len(after_operations)
        after_census = operation_census(after_text)
        invalid_classes = new_invalid_classes(before_census, after_census)
    else:
        after_text = ""
        after_operations = []
        after_counts = {name: None for name in REGISTERED}
        after_registered_count = None
        after_census = {}
        invalid_classes = []
    semantic_status = "proven" if prior_proven else "unproven"
    invariant_status = (
        "unavailable_due_invalid_output"
        if not full_run["parseable"]
        else (
            "proven"
            if semantic_status == "proven" and not invalid_classes
            else "unproven"
        )
    )
    complete = {
        "parseable": full_run["parseable"],
        "before": {
            "operation_census": before_census,
            "registered_blocker_counts": registered_counts(before_operations),
            "registered_operation_count": len(before_operations),
        },
        "after": {
            "operation_census": after_census,
            "registered_blocker_counts": after_counts,
            "registered_operation_count": after_registered_count,
        },
        "new_invalid_classes": invalid_classes,
        "invariant_status": invariant_status,
    }
    decision = apply_decision_gate(
        parseable=complete["parseable"],
        blocker_counts=complete["after"]["registered_blocker_counts"],
        new_invalid_classes=invalid_classes,
        semantic_status=invariant_status,
    )
    baseline_output = ROOT / baseline["executions"][-1]["output"]["path"]
    python = Path(sys.executable).resolve()
    payload: dict[str, Any] = {
        "schema": "tinystories-1m-exact-subview-extension-v1",
        "status": "evaluated",
        "model": contract["model"],
        "pipeline": PIPELINE,
        "task2_contract": file_binding(CONTRACT, relative=True),
        "baseline_evaluation": file_binding(BASELINE_EVALUATION, relative=True),
        "baseline_observation": {
            "evaluation_self_sha256": baseline["sha256"],
            "decision": baseline["decision"],
            "frontier_signature_sha256": baseline["earliest_remaining_signature"]["signature_sha256"],
            "complete_output": file_binding(baseline_output, relative=True),
        },
        "input": file_binding(flat_scf, relative=True),
        "tool": dict(TOOL),
        "baseline_plugin": dict(BASELINE_PLUGIN),
        "plugin": dict(PLUGIN),
        "python": file_binding(python),
        "source_revision": source_revision_binding(),
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
        "predecessor_reproducer": predecessor_result,
        "semantic_probes": semantic_probes,
        "complete": complete,
        "decision": decision,
        "sha256": None,
    }
    if decision == "valid_normalized_output":
        payload["normalized_artifact"] = full_run["output"]
    else:
        if full_run["parseable"]:
            raise ValueError(
                "parseable next-frontier selection requires an observed canonical reproducer class"
            )
        payload["next_frontier"] = diagnostic_frontier(
            stderr=(ROOT / full_run["stderr"]["path"]).read_bytes(),
            source_path=flat_scf,
            evidence_root=evidence_root,
            parser=parser,
        )
    payload["sha256"] = sha256_bytes(canonical_json(payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json(payload) + b"\n")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = evaluate(output=args.output, evidence_root=args.evidence_root, report=args.report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": payload["decision"],
                "before": payload["complete"]["before"]["registered_blocker_counts"],
                "after": payload["complete"]["after"]["registered_blocker_counts"],
                "sha256": payload["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
