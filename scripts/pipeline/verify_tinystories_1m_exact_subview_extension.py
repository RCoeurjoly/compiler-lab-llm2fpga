#!/usr/bin/env python3
"""Independently authenticate and replay the exact static-subview evaluation."""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json"
EVIDENCE_ROOT = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence"
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
BASELINE = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
TASK2_VERIFIER_PATH = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
BASELINE_VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py"
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
RUN_SPECS = (
    ("predecessor-task3-subview", "predecessor_reproducer", PREDECESSOR),
    ("semantic-identity-offset", "semantic_probe", IDENTITY_PROBE),
    ("semantic-nonzero-offset-stride", "semantic_probe", NONZERO_PROBE),
)
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
BASELINE_SHA256 = "26e0ddcaf0abc6100332378d2cacf0555f3560a7635bcdd60dbb9f47bd5ad0d8"
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

COMMON_KEYS = {
    "schema", "status", "model", "pipeline", "task2_contract",
    "baseline_evaluation", "baseline_observation", "input", "tool",
    "baseline_plugin", "plugin", "python", "source_revision", "provenance",
    "task_1_through_3_identities", "executions", "predecessor_reproducer",
    "semantic_probes", "complete", "decision", "sha256",
}
RUN_KEYS = {
    "sequence", "id", "kind", "causal_preconditions_satisfied", "command",
    "input", "input_after", "exit_code", "elapsed_ns", "output_created",
    "stdout", "stderr", "output", "parse_check", "parseable",
}
PARSE_KEYS = {"command", "exit_code", "stdout", "stderr"}
BINDING_KEYS = {"path", "bytes", "sha256"}
BASELINE_OBSERVATION_KEYS = {
    "evaluation_self_sha256", "decision", "frontier_signature_sha256",
    "complete_output",
}
SOURCE_REVISION_KEYS = {
    "assigned_base", "task1_commit", "task2_implementation_commit",
    "pass_source_blob", "pass_source",
}
PROVENANCE_KEYS = {
    "payload_source", "c22_derivation", "c22_output",
    "current_alias_derivation", "current_alias_output", "current_alias_realized",
    "unrealized_current_alias_residual",
}
PREDECESSOR_KEYS = {"execution_id", "signature_sha256", "legalization_status", "checks"}
PREDECESSOR_CHECK_KEYS = {
    "exit_zero", "parseable", "subview_eliminated", "flattened_argument_present",
}
PROBE_KEYS = {"id", "execution_id", "invariant_status", "before", "after", "checks"}
PROBE_CHECK_KEYS = {
    "exit_zero", "parseable", "before_matches_literal_affine_map",
    "after_matches_literal_affine_map", "complete_affine_mapping_preserved",
    "subview_eliminated",
}
PROOF_KEYS = {"affine_status", "index_variables", "access_maps"}
VARIABLE_KEYS = {"name", "argument", "lower_inclusive", "upper_exclusive"}
ACCESS_KEYS = {"kind", "base", "raw_indices", "linear_formula"}
BASE_KEYS = {"argument", "role"}
AFFINE_KEYS = {"coefficients", "offset"}
RAW_INDEX_KEYS = {"coefficients", "offset", "range"}
RANGE_KEYS = {
    "lower_inclusive", "upper_exclusive", "memref_upper_exclusive", "in_bounds",
}
COMPLETE_KEYS = {"parseable", "before", "after", "new_invalid_classes", "invariant_status"}
PHASE_KEYS = {"operation_census", "registered_blocker_counts", "registered_operation_count"}
FRONTIER_KEYS = {
    "kind", "operation", "signature", "signature_sha256", "source_location",
    "diagnostic", "reproducer",
}
LOCATION_KEYS = {"function", "line", "column", "mlir"}
REPRODUCER_KEYS = {"path", "bytes", "sha256", "operation_count", "metadata"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _binding(path: Path, *, relative: bool = False) -> dict[str, Any]:
    raw = path.read_bytes()
    rendered = str(path.relative_to(ROOT)) if relative else str(path)
    return {"path": rendered, "bytes": len(raw), "sha256": _digest(raw)}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_keys(value: Any, expected: set[str], label: str) -> None:
    _require(isinstance(value, dict) and set(value) == expected, f"{label} mismatch")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def _load_task2_verifier():
    spec = importlib.util.spec_from_file_location("exact_memref_task2_independent", TASK2_VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load independent Task 2 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_binding(binding: Any, canonical_path: Path, label: str) -> Path:
    _require_keys(binding, BINDING_KEYS, f"{label} binding schema")
    expected = _binding(canonical_path, relative=not Path(str(binding["path"])).is_absolute())
    _require(binding == expected, f"canonical evidence path mismatch for {label}")
    return canonical_path


def _validate_proof_schema(proof: Any, label: str) -> None:
    _require_keys(proof, PROOF_KEYS, f"{label} proof schema")
    _require(proof.get("affine_status") == "proven", f"{label} proof status mismatch")
    variables = proof.get("index_variables")
    accesses = proof.get("access_maps")
    _require(isinstance(variables, list) and isinstance(accesses, list), f"{label} proof schema mismatch")
    for variable in variables:
        _require_keys(variable, VARIABLE_KEYS, f"{label} variable schema")
    for access in accesses:
        _require_keys(access, ACCESS_KEYS, f"{label} access schema")
        _require_keys(access.get("base"), BASE_KEYS, f"{label} base schema")
        _require_keys(access.get("linear_formula"), AFFINE_KEYS, f"{label} affine schema")
        raw_indices = access.get("raw_indices")
        _require(isinstance(raw_indices, list), f"{label} raw-index schema mismatch")
        for raw in raw_indices:
            _require_keys(raw, RAW_INDEX_KEYS, f"{label} raw-index schema")
            _require_keys(raw.get("range"), RANGE_KEYS, f"{label} range schema")


def _validate_closed_schema(payload: dict[str, Any]) -> None:
    decision = payload.get("decision")
    _require(
        decision in {"valid_normalized_output", "next_compiler_frontier"},
        "decision schema mismatch",
    )
    branch_keys = {
        key for key in ("normalized_artifact", "next_frontier") if key in payload
    }
    expected_branch = (
        {"normalized_artifact"}
        if decision == "valid_normalized_output"
        else {"next_frontier"}
    )
    _require(branch_keys == expected_branch, "decision schema mismatch")
    _require(set(payload) - branch_keys == COMMON_KEYS, "top-level schema mismatch")
    _require(payload.get("status") == "evaluated", "status mismatch")
    _require_keys(payload.get("task2_contract"), BINDING_KEYS, "Task 2 contract binding schema")
    _require_keys(payload.get("baseline_evaluation"), BINDING_KEYS, "baseline evaluation binding schema")
    _require_keys(payload.get("baseline_observation"), BASELINE_OBSERVATION_KEYS, "baseline observation schema")
    _require_keys(payload["baseline_observation"].get("complete_output"), BINDING_KEYS, "baseline output binding schema")
    _require_keys(payload.get("input"), BINDING_KEYS, "input binding schema")
    _require_keys(payload.get("tool"), BINDING_KEYS, "tool binding schema")
    _require_keys(payload.get("baseline_plugin"), BINDING_KEYS, "baseline plugin binding schema")
    _require_keys(payload.get("plugin"), BINDING_KEYS, "plugin binding schema")
    _require_keys(payload.get("python"), BINDING_KEYS, "python binding schema")
    _require_keys(payload.get("source_revision"), SOURCE_REVISION_KEYS, "source revision schema")
    _require_keys(payload["source_revision"].get("pass_source"), BINDING_KEYS, "pass source binding schema")
    _require_keys(payload.get("provenance"), PROVENANCE_KEYS, "provenance schema")
    runs = payload.get("executions")
    _require(isinstance(runs, list), "execution schema mismatch")
    for run in runs:
        _require_keys(run, RUN_KEYS, "execution schema")
        _require_keys(run.get("parse_check"), PARSE_KEYS, "parse-check schema")
        for key in ("input", "input_after", "stdout", "stderr", "output"):
            _require_keys(run.get(key), BINDING_KEYS, f"execution {key} schema")
        for key in ("stdout", "stderr"):
            _require_keys(run["parse_check"].get(key), BINDING_KEYS, f"parse {key} schema")
    predecessor = payload.get("predecessor_reproducer")
    _require_keys(predecessor, PREDECESSOR_KEYS, "predecessor schema")
    _require_keys(predecessor.get("checks"), PREDECESSOR_CHECK_KEYS, "predecessor check schema")
    probes = payload.get("semantic_probes")
    _require(isinstance(probes, list), "semantic probe schema mismatch")
    for probe in probes:
        _require_keys(probe, PROBE_KEYS, "semantic probe schema")
        _validate_proof_schema(probe.get("before"), "semantic probe before")
        _validate_proof_schema(probe.get("after"), "semantic probe after")
        _require_keys(probe.get("checks"), PROBE_CHECK_KEYS, "semantic probe check schema")
    complete = payload.get("complete")
    _require_keys(complete, COMPLETE_KEYS, "complete schema")
    _require_keys(complete.get("before"), PHASE_KEYS, "complete before schema")
    _require_keys(complete.get("after"), PHASE_KEYS, "complete after schema")
    if decision == "valid_normalized_output":
        _require_keys(payload.get("normalized_artifact"), BINDING_KEYS, "normalized artifact schema")
    else:
        frontier = payload.get("next_frontier")
        _require_keys(frontier, FRONTIER_KEYS, "frontier schema")
        _require(
            frontier.get("kind") in {"diagnostic", "new_invalid_class", "residual_registered_blocker"},
            "frontier kind schema mismatch",
        )
        _require_keys(frontier.get("source_location"), LOCATION_KEYS, "frontier source location schema")
        _require_keys(frontier.get("reproducer"), REPRODUCER_KEYS, "frontier reproducer schema")
        _require_keys(frontier["reproducer"].get("metadata"), BINDING_KEYS, "frontier metadata binding schema")


def _logical_lines(text: str) -> list[str]:
    return re.sub(r"\n\s+(:\s+memref<)", r" \1", text).splitlines()


_FUNC = re.compile(r"^\s*func\.func @([A-Za-z0-9_.$-]+)\((.*)\) -> i64 \{\s*$")
_ARG = re.compile(r"(%[A-Za-z0-9_.$-]+)\s*:\s*(memref<[^>]+>|index|i64)")
_CONSTANT = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.constant\s+(-?[0-9]+)\s*:\s*index\s*$")
_BINARY = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.(addi|subi|muli)\s+(%[A-Za-z0-9_.$-]+),\s*(%[A-Za-z0-9_.$-]+)\s*:\s*index\s*$")
_ALIAS = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*memref\.(?:subview|collapse_shape|expand_shape|reinterpret_cast)\s+(%[A-Za-z0-9_.$-]+)\b")
_LOAD = re.compile(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*memref\.load\s+(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")
_STORE = re.compile(r"^\s*memref\.store\s+%[A-Za-z0-9_.$-]+,\s*(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$")


def _sum(left: dict[str, Any], right: dict[str, Any], factor: int = 1) -> dict[str, Any]:
    return {
        "coefficients": [
            lhs + factor * rhs
            for lhs, rhs in zip(left["coefficients"], right["coefficients"])
        ],
        "offset": left["offset"] + factor * right["offset"],
    }


def _scale(value: dict[str, Any], factor: int) -> dict[str, Any]:
    return {
        "coefficients": [factor * item for item in value["coefficients"]],
        "offset": factor * value["offset"],
    }


def _independent_affine_proof(
    text: str, *, probe_id: str, task2: Any
) -> dict[str, Any]:
    spec = PROBE_SPECS[probe_id]
    lines = _logical_lines(text)
    function = next((match for line in lines if (match := _FUNC.match(line))), None)
    _require(function is not None and function.group(1) == spec["function"], "semantic probe function mismatch")
    arguments = list(_ARG.finditer(function.group(2)))
    variables = copy.deepcopy(spec["variables"])
    expressions: dict[str, dict[str, Any]] = {}
    for position, variable in enumerate(variables):
        argument = arguments[variable["argument"]]
        _require(argument.group(2) == "index", "semantic probe variable mismatch")
        coefficients = [0] * len(variables)
        coefficients[position] = 1
        expressions[argument.group(1)] = {"coefficients": coefficients, "offset": 0}
    for line in lines:
        constant = _CONSTANT.match(line)
        if constant:
            expressions[constant.group(1)] = {
                "coefficients": [0] * len(variables),
                "offset": int(constant.group(2)),
            }
            continue
        binary = _BINARY.match(line)
        if binary is None:
            continue
        left, right = expressions.get(binary.group(3)), expressions.get(binary.group(4))
        _require(left is not None and right is not None, "semantic probe unresolved index")
        if binary.group(2) == "addi":
            value = _sum(left, right)
        elif binary.group(2) == "subi":
            value = _sum(left, right, -1)
        else:
            left_constant = not any(left["coefficients"])
            right_constant = not any(right["coefficients"])
            _require(left_constant or right_constant, "semantic probe non-affine multiplication")
            value = _scale(
                right if left_constant else left,
                left["offset"] if left_constant else right["offset"],
            )
        expressions[binary.group(1)] = value
    memrefs = {
        item.group(1): arguments.index(item)
        for item in arguments
        if item.group(2).startswith("memref<")
    }
    aliases = {
        match.group(1): match.group(2)
        for line in lines
        if (match := _ALIAS.match(line))
    }

    def base(name: str) -> int:
        seen = set()
        while name in aliases:
            _require(name not in seen, "semantic probe alias cycle")
            seen.add(name)
            name = aliases[name]
        _require(name in memrefs, "semantic probe base mismatch")
        return memrefs[name]

    accesses = []
    for line in lines:
        match, kind = _STORE.match(line), "store"
        if match is None:
            match, kind = _LOAD.match(line), "load"
        if match is None:
            continue
        memref = task2._memref(match.group(3))
        raw_indices = []
        for token in (part.strip() for part in match.group(2).split(",")):
            _require(token in expressions, "semantic probe dynamic index")
            raw_indices.append(copy.deepcopy(expressions[token]))
        _require(len(raw_indices) == memref["rank"], "semantic probe access rank mismatch")
        for expression, dimension in zip(raw_indices, memref["shape"]):
            _require(isinstance(dimension, int), "semantic probe dynamic shape")
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
        _require(
            isinstance(memref["offset"], int)
            and all(isinstance(stride, int) for stride in memref["strides"]),
            "semantic probe dynamic layout",
        )
        linear = {"coefficients": [0] * len(variables), "offset": memref["offset"]}
        for stride, expression in zip(memref["strides"], raw_indices):
            linear = _sum(linear, _scale(expression, stride))
        accesses.append(
            {
                "kind": kind,
                "base": {
                    "argument": base(match.group(1)),
                    "role": "target" if kind == "store" else "source",
                },
                "raw_indices": raw_indices,
                "linear_formula": linear,
            }
        )
    _require(len(accesses) == 2 and {item["kind"] for item in accesses} == {"load", "store"}, "semantic probe access set mismatch")
    return {"affine_status": "proven", "index_variables": variables, "access_maps": accesses}


def _proof_matches_literal(proof: dict[str, Any], probe_id: str) -> bool:
    spec = PROBE_SPECS[probe_id]
    return (
        proof == {**proof, "affine_status": "proven"}
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
            raw["range"]["in_bounds"]
            for item in proof["access_maps"]
            for raw in item["raw_indices"]
        )
    )


def _mask(line: str) -> str:
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


_OP = re.compile(
    r"^\s*(?:[%][^=]+?=\s*)?(?:\([^=]+\)\s*=\s*)?"
    r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_GENERIC_OP = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*\(')


def _decode_generic_name(raw: str) -> str:
    decoded: list[str] = []
    position = 0
    while position < len(raw):
        character = raw[position]
        if character != "\\":
            decoded.append(character)
            position += 1
            continue
        position += 1
        _require(position < len(raw), "incomplete generic operation-name escape")
        escaped = raw[position]
        if escaped in {'"', "\\"}:
            decoded.append(escaped)
            position += 1
        elif escaped in {"n", "t"}:
            decoded.append("\n" if escaped == "n" else "\t")
            position += 1
        elif (
            position + 1 < len(raw)
            and escaped in "0123456789abcdefABCDEF"
            and raw[position + 1] in "0123456789abcdefABCDEF"
        ):
            decoded.append(chr(int(raw[position : position + 2], 16)))
            position += 2
        else:
            raise ValueError("unknown generic operation-name escape")
    return "".join(decoded)


def _operation_census(text: str) -> dict[str, int]:
    census: dict[str, int] = {}
    for line in text.splitlines():
        match = _OP.match(_mask(line))
        if match is not None:
            name = match.group(1)
        else:
            generic = _GENERIC_OP.match(line)
            if generic is None:
                continue
            name = _decode_generic_name(generic.group(1))
            _require(
                re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_.]*",
                    name,
                )
                is not None,
                "malformed generic operation name",
            )
        census[name] = census.get(name, 0) + 1
    return dict(sorted(census.items()))


def _counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return {name: sum(item["operation"] == name for item in operations) for name in REGISTERED}


def _new_invalid(before: dict[str, int], after: dict[str, int]) -> list[str]:
    suspicious = re.compile(r"(?:view|cast|shape|copy)")
    return sorted(
        name
        for name in after
        if name.startswith("memref.")
        and name not in before
        and name not in REGISTERED
        and suspicious.search(name.split(".", 1)[1])
    )


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
    _require(completed.returncode == 0, "authenticated source object unavailable")
    return completed.stdout


def _expected_source_revision() -> dict[str, Any]:
    relative = "tools/mlir-passes/FoldConstantTruncFOps.cpp"
    _require(PASS_SOURCE.read_bytes() == _git_bytes(ASSIGNED_BASE, relative), "Task 2 pass source mismatch")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ASSIGNED_BASE, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(ancestry.returncode == 0, "Task 3 assigned-base ancestry mismatch")
    return {
        "assigned_base": ASSIGNED_BASE,
        "task1_commit": TASK1_COMMIT,
        "task2_implementation_commit": TASK2_IMPLEMENTATION_COMMIT,
        "pass_source_blob": PASS_SOURCE_BLOB,
        "pass_source": _binding(PASS_SOURCE, relative=True),
    }


def _command(input_path: Path, output_path: Path) -> list[str]:
    return [
        TOOL["path"],
        str(input_path),
        f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}",
        "-o",
        str(output_path),
    ]


def _check_command(run: dict[str, Any], input_path: Path, output_path: Path) -> None:
    expected = _command(input_path, output_path)
    _require(run.get("command") == expected, "exact pass command mismatch")
    lowered = " ".join(expected).lower().replace("for-calyx", "")
    _require("calyx" not in lowered and "circt-opt" not in lowered, "Calyx invocation is forbidden")


def _replay(run: dict[str, Any], input_path: Path, evidence_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="exact-subview-extension-replay-") as raw:
        output = Path(raw) / "output.mlir"
        completed = subprocess.run(
            _command(input_path, output),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        created = output.exists()
        output_bytes = output.read_bytes() if created else b""
        _require(completed.returncode == run["exit_code"], "replay exit mismatch")
        _require(completed.stdout == (evidence_dir / "stdout.bin").read_bytes(), "replay stdout mismatch")
        _require(completed.stderr == (evidence_dir / "stderr.bin").read_bytes(), "replay stderr mismatch")
        _require(created == run["output_created"], "replay output-created mismatch")
        _require(output_bytes == (evidence_dir / "output.mlir").read_bytes(), "replay output mismatch")


@functools.lru_cache(maxsize=1)
def _verify_predecessors() -> None:
    """Authenticate immutable predecessors once per verifier process."""
    for verifier, label in (
        (TASK2_VERIFIER_PATH, "Task 2 verifier"),
        (BASELINE_VERIFIER, "baseline verifier"),
    ):
        completed = subprocess.run(
            [sys.executable, str(verifier)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        _require(completed.returncode == 0, f"authenticated {label} failed")


def validate_payload(payload: dict[str, Any], root: Path = ROOT, *, replay: bool) -> None:
    _require(root.resolve() == ROOT.resolve(), "verification root mismatch")
    _require(payload.get("schema") == "tinystories-1m-exact-subview-extension-v1", "schema mismatch")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    _require(payload.get("sha256") == _digest(_canonical(unsigned)), "evaluation self-hash mismatch")
    _validate_closed_schema(payload)
    _require(payload.get("pipeline") == PIPELINE, "pipeline mismatch")
    _require(payload.get("tool") == TOOL and _binding(Path(TOOL["path"])) == TOOL, "tool identity mismatch")
    _require(payload.get("baseline_plugin") == BASELINE_PLUGIN, "baseline plugin identity mismatch")
    _require(payload.get("plugin") == PLUGIN, "plugin identity mismatch")
    _require(_binding(Path(BASELINE_PLUGIN["path"])) == BASELINE_PLUGIN, "baseline plugin bytes mismatch")
    _require(_binding(Path(PLUGIN["path"])) == PLUGIN, "plugin identity mismatch")
    _require(PLUGIN["sha256"] != BASELINE_PLUGIN["sha256"], "plugin identity does not differ from baseline")
    _require(_digest(CONTRACT.read_bytes()) == CONTRACT_SHA256, "Task 2 contract bytes mismatch")
    _require(_digest(BASELINE.read_bytes()) == BASELINE_SHA256, "baseline evaluation bytes mismatch")
    _require(payload.get("task2_contract") == _binding(CONTRACT, relative=True), "Task 2 contract binding mismatch")
    _require(payload.get("baseline_evaluation") == _binding(BASELINE, relative=True), "baseline evaluation binding mismatch")
    contract = _load_object(CONTRACT, "Task 2 contract")
    baseline = _load_object(BASELINE, "baseline evaluation")
    baseline_output = ROOT / baseline["executions"][-1]["output"]["path"]
    expected_baseline = {
        "evaluation_self_sha256": baseline["sha256"],
        "decision": "compiler_pass_extension",
        "frontier_signature_sha256": EARLIEST_SIGNATURE_SHA256,
        "complete_output": _binding(baseline_output, relative=True),
    }
    _require(payload.get("baseline_observation") == expected_baseline, "baseline observation mismatch")
    _require(payload.get("model") == contract["model"], "model mismatch")
    _require(
        payload.get("task_1_through_3_identities") == contract["task_1_through_3_identities"],
        "Task 1--3 identities mismatch",
    )
    _require(payload.get("provenance") == _expected_provenance(contract), "provenance mismatch")
    _require(payload.get("source_revision") == _expected_source_revision(), "source revision mismatch")
    trusted_python = Path(sys.executable).resolve()
    _require(payload.get("python") == _binding(trusted_python), "python interpreter binding mismatch")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    _require(_digest(flat_scf.read_bytes()) == FLAT_SCF_SHA256, "input identity mismatch")
    _require(payload.get("input") == _binding(flat_scf, relative=True), "input identity mismatch")

    _verify_predecessors()

    runs = payload["executions"]
    _require(len(runs) == 4, "causal execution order mismatch")
    expected_specs = [*RUN_SPECS, ("complete-retained-c22-flat-scf", "complete", flat_scf)]
    _require([run["sequence"] for run in runs] == [1, 2, 3, 4], "causal execution sequence mismatch")
    _require([run["id"] for run in runs] == [item[0] for item in expected_specs], "canonical run id mismatch")
    _require([run["kind"] for run in runs] == [item[1] for item in expected_specs], "causal execution kind mismatch")
    _require(all(run["causal_preconditions_satisfied"] is True for run in runs), "causal precondition mismatch")
    evidence_dirs = [EVIDENCE_ROOT / item[0] for item in expected_specs]
    input_paths = [item[2] for item in expected_specs]
    for index, run in enumerate(runs):
        input_path = input_paths[index]
        evidence_dir = evidence_dirs[index]
        _require(run["input"] == _binding(input_path, relative=True), "unchanged input identity mismatch")
        _require(run["input_after"] == run["input"], "unchanged input identity mismatch")
        _require(isinstance(run["elapsed_ns"], int) and run["elapsed_ns"] > 0, "elapsed time invalid")
        output_path = _check_binding(run["output"], evidence_dir / "output.mlir", f"{run['id']} output")
        _check_binding(run["stdout"], evidence_dir / "stdout.bin", f"{run['id']} stdout")
        _check_binding(run["stderr"], evidence_dir / "stderr.bin", f"{run['id']} stderr")
        _check_binding(run["parse_check"]["stdout"], evidence_dir / "parse.stdout.bin", f"{run['id']} parse stdout")
        _check_binding(run["parse_check"]["stderr"], evidence_dir / "parse.stderr.bin", f"{run['id']} parse stderr")
        _check_command(run, input_path, output_path)
        parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
        _require(run["parse_check"]["command"] == parse_command, "parse command mismatch")
        parsed = subprocess.run(
            parse_command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        _require(parsed.returncode == run["parse_check"]["exit_code"], "parse exit mismatch")
        _require(parsed.stdout == (evidence_dir / "parse.stdout.bin").read_bytes(), "parse stdout mismatch")
        _require(parsed.stderr == (evidence_dir / "parse.stderr.bin").read_bytes(), "parse stderr mismatch")
        expected_parseable = run["exit_code"] == 0 and run["parse_check"]["exit_code"] == 0
        _require(run["parseable"] is expected_parseable, "parseable status mismatch")
        if index < 3:
            _require(run["exit_code"] == 0 and run["parseable"], "probe execution failed")

    predecessor_text = (evidence_dirs[0] / "output.mlir").read_text(encoding="utf-8")
    predecessor_checks = {
        "exit_zero": runs[0]["exit_code"] == 0,
        "parseable": runs[0]["parseable"],
        "subview_eliminated": "memref.subview" not in predecessor_text,
        "flattened_argument_present": "memref<4096xi64>" in predecessor_text,
    }
    expected_predecessor = {
        "execution_id": runs[0]["id"],
        "signature_sha256": EARLIEST_SIGNATURE_SHA256,
        "legalization_status": "proven" if all(predecessor_checks.values()) else "unproven",
        "checks": predecessor_checks,
    }
    _require(payload["predecessor_reproducer"] == expected_predecessor, "predecessor reproducer mismatch")
    _require(expected_predecessor["legalization_status"] == "proven", "predecessor reproducer unproven")

    task2 = _load_task2_verifier()
    expected_probes = []
    for offset, (identifier, _, input_path) in enumerate(RUN_SPECS[1:], start=1):
        before = _independent_affine_proof(input_path.read_text(encoding="utf-8"), probe_id=identifier, task2=task2)
        output_text = (evidence_dirs[offset] / "output.mlir").read_text(encoding="utf-8")
        after = _independent_affine_proof(output_text, probe_id=identifier, task2=task2)
        checks = {
            "exit_zero": runs[offset]["exit_code"] == 0,
            "parseable": runs[offset]["parseable"],
            "before_matches_literal_affine_map": _proof_matches_literal(before, identifier),
            "after_matches_literal_affine_map": _proof_matches_literal(after, identifier),
            "complete_affine_mapping_preserved": (
                _proof_matches_literal(before, identifier)
                and _proof_matches_literal(after, identifier)
            ),
            "subview_eliminated": "memref.subview" not in output_text,
        }
        expected_probes.append(
            {
                "id": identifier,
                "execution_id": runs[offset]["id"],
                "invariant_status": "proven" if all(checks.values()) else "unproven",
                "before": before,
                "after": after,
                "checks": checks,
            }
        )
    _require(payload["semantic_probes"] == expected_probes, "semantic probe mismatch")
    _require(all(item["invariant_status"] == "proven" for item in expected_probes), "semantic probe unproven")

    before_text = flat_scf.read_text(encoding="utf-8")
    before_operations = task2._independent_operations(before_text)
    before_census = _operation_census(before_text)
    full_parseable = runs[-1]["parseable"]
    if full_parseable:
        after_text = (evidence_dirs[-1] / "output.mlir").read_text(encoding="utf-8")
        after_operations = task2._independent_operations(after_text)
        after_counts: dict[str, int | None] = _counts(after_operations)
        after_registered_count: int | None = len(after_operations)
        after_census = _operation_census(after_text)
        invalid_classes = _new_invalid(before_census, after_census)
    else:
        after_text = ""
        after_counts = {name: None for name in REGISTERED}
        after_registered_count = None
        after_census = {}
        invalid_classes = []
    expected_complete = {
        "parseable": full_parseable,
        "before": {
            "operation_census": before_census,
            "registered_blocker_counts": _counts(before_operations),
            "registered_operation_count": len(before_operations),
        },
        "after": {
            "operation_census": after_census,
            "registered_blocker_counts": after_counts,
            "registered_operation_count": after_registered_count,
        },
        "new_invalid_classes": invalid_classes,
        "invariant_status": (
            "unavailable_due_invalid_output"
            if not full_parseable
            else ("proven" if not invalid_classes else "unproven")
        ),
    }
    _require(payload["complete"]["before"] == expected_complete["before"], "before blocker census mismatch")
    _require(payload["complete"]["after"] == expected_complete["after"], "after blocker census mismatch")
    _require(payload["complete"]["new_invalid_classes"] == invalid_classes, "new invalid classes mismatch")
    _require(payload["complete"] == expected_complete, "complete census mismatch")
    valid = (
        full_parseable
        and all(isinstance(after_counts[name], int) for name in REGISTERED)
        and not invalid_classes
        and expected_complete["invariant_status"] == "proven"
    )
    decision = "valid_normalized_output" if valid else "next_compiler_frontier"
    _require(payload["decision"] == decision, "decision gate mismatch")
    if decision == "valid_normalized_output":
        _require(payload["normalized_artifact"] == runs[-1]["output"], "normalized artifact identity mismatch")
    else:
        frontier = payload["next_frontier"]
        _require(not full_parseable and frontier["kind"] == "diagnostic", "earliest frontier mismatch")
        diagnostic = (evidence_dirs[-1] / "stderr.bin").read_text(encoding="utf-8")
        first = re.search(r":([0-9]+):([0-9]+): error: ([^\n]+)", diagnostic)
        _require(first is not None, "earliest frontier diagnostic missing")
        _require(frontier["source_location"]["line"] == int(first.group(1)), "earliest frontier mismatch")
        _require(frontier["source_location"]["column"] == int(first.group(2)), "earliest frontier mismatch")
        _require(frontier["diagnostic"] == first.group(3), "earliest frontier mismatch")
        _require(frontier["signature_sha256"] == _digest(_canonical(frontier["signature"])), "earliest frontier signature mismatch")
        reproducer = ROOT / frontier["reproducer"]["path"]
        _check_binding(
            {key: frontier["reproducer"][key] for key in BINDING_KEYS},
            reproducer,
            "frontier reproducer",
        )
        _require(frontier["reproducer"]["operation_count"] == 1, "frontier reproducer count mismatch")
        metadata = ROOT / frontier["reproducer"]["metadata"]["path"]
        _check_binding(frontier["reproducer"]["metadata"], metadata, "frontier metadata")
        claimed_metadata = _load_object(metadata, "frontier metadata")
        _require(claimed_metadata["operation"] == frontier["operation"], "frontier metadata operation mismatch")
        _require(claimed_metadata["signature"] == frontier["signature"], "frontier metadata signature mismatch")

    if replay:
        for run, input_path, evidence_dir in zip(runs, input_paths, evidence_dirs):
            _replay(run, input_path, evidence_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, default=EVALUATION)
    parser.add_argument("--no-replay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = _load_object(args.evaluation, "Task 3 evaluation")
    validate_payload(payload, ROOT, replay=not args.no_replay)
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision": payload["decision"],
                "after": payload["complete"]["after"]["registered_blocker_counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
