#!/usr/bin/env python3
"""Independently authenticate and replay the strided unit-collapse evaluation."""

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
EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json"
EVIDENCE_ROOT = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence"
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
PREDECESSOR_EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json"
PREDECESSOR_OUTPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence/complete-retained-c22-flat-scf/output.mlir"
TASK2_VERIFIER_PATH = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
OFFSET_ZERO_PROBE = ROOT / "reproducers/tinystories-1m-exact-strided-unit-collapse/offset-zero.mlir"
OFFSET_SEVEN_PROBE = ROOT / "reproducers/tinystories-1m-exact-strided-unit-collapse/offset-nonzero.mlir"
COPY_PROBE = EVIDENCE_ROOT / "semantic-collapsed-copy/input.mlir"
PASS_SOURCE = ROOT / "tools/mlir-passes/FoldConstantTruncFOps.cpp"
PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
RUN_SPECS = (
    ("semantic-offset-zero", "semantic_probe", OFFSET_ZERO_PROBE),
    ("semantic-offset-seven", "semantic_probe", OFFSET_SEVEN_PROBE),
    ("semantic-collapsed-copy", "semantic_probe", COPY_PROBE),
)
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
PREDECESSOR_EVALUATION_SHA256 = "467229e04ed6f82cf2f8c3596e7cd754ab0510b10fe443ae248735af0fd0c343"
PREDECESSOR_OUTPUT_SHA256 = "42d682b642b899b10bc0814a7786a5803d69b839148e79bbfdc803425e261f34"
PREDECESSOR_SELF_SHA256 = "64fa2b94030ce859c1d2a6cc648ea52caeffb3f1038dca7f1c567ccbaf32772c"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
ASSIGNED_BASE = "3dbfea4dd9bbd03e1032412cc2dee17b1b924d92"
TASK1_COMMIT = ASSIGNED_BASE
PASS_SOURCE_BLOB = "dd2e2ba5956e640353a49574356cee1572c3debc"
TOOL = {
    "path": "/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt",
    "bytes": 496904,
    "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
}
PREDECESSOR_PLUGIN = {
    "path": "/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21720848,
    "sha256": "6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9",
}
PLUGIN = {
    "path": "/nix/store/7nffqc9cn9da37py316ilmcarjpp9gbn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21726600,
    "sha256": "9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984",
}
PROBE_SPECS = {
    "semantic-offset-zero": {
        "function": "offset_zero",
        "variables": [
            {"name": "i", "argument": 1, "lower_inclusive": 0, "upper_exclusive": 64},
        ],
        "accesses": [
            {"kind": "load", "argument": 0, "role": "source", "offset": 0, "coefficients": [64]},
            {"kind": "store", "argument": 0, "role": "target", "offset": 0, "coefficients": [64]},
        ],
    },
    "semantic-offset-seven": {
        "function": "offset_nonzero",
        "variables": [
            {"name": "i", "argument": 1, "lower_inclusive": 0, "upper_exclusive": 64},
        ],
        "accesses": [
            {"kind": "load", "argument": 0, "role": "source", "offset": 7, "coefficients": [64]},
            {"kind": "store", "argument": 0, "role": "target", "offset": 7, "coefficients": [64]},
        ],
    },
    "semantic-collapsed-copy": {
        "function": "collapsed_copy",
        "variables": [
            {"name": "i", "argument": None, "lower_inclusive": 0, "upper_exclusive": 64},
        ],
        "accesses": [
            {"kind": "load", "argument": 0, "role": "source", "offset": 7, "coefficients": [64]},
            {"kind": "store", "argument": 1, "role": "target", "offset": 0, "coefficients": [64]},
        ],
    },
}

COMMON_KEYS = {
    "schema", "status", "model", "pipeline", "task2_contract",
    "predecessor_evaluation", "predecessor_normalized_artifact",
    "predecessor_observation", "input", "tool", "predecessor_plugin",
    "plugin", "python", "source_revision", "provenance",
    "task_1_through_3_identities", "executions",
    "semantic_probes", "complete", "decision", "sha256",
}
RUN_KEYS = {
    "sequence", "id", "kind", "causal_preconditions_satisfied", "command",
    "input", "input_after", "exit_code", "elapsed_ns", "output_created",
    "stdout", "stderr", "output", "parse_check", "parseable", "generic_prints",
}
GENERIC_KEYS = {"subject", "command", "exit_code", "input", "stdout", "stderr", "output"}
PARSE_KEYS = {"command", "exit_code", "stdout", "stderr"}
BINDING_KEYS = {"path", "bytes", "sha256"}
PREDECESSOR_OBSERVATION_KEYS = {
    "evaluation_self_sha256", "decision", "registered_blocker_counts",
}
SOURCE_REVISION_KEYS = {
    "assigned_base", "task1_commit", "pass_source_blob", "pass_source",
}
PROVENANCE_KEYS = {
    "payload_source", "c22_derivation", "c22_output",
    "current_alias_derivation", "current_alias_output", "current_alias_realized",
    "unrealized_current_alias_residual",
}
PROBE_KEYS = {"id", "execution_id", "invariant_status", "before", "after", "checks"}
PROBE_CHECK_KEYS = {
    "exit_zero", "parseable", "before_matches_literal_affine_map",
    "after_matches_literal_affine_map", "complete_affine_mapping_preserved",
    "subview_eliminated", "collapse_eliminated", "copy_eliminated_or_absent",
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
NEXT_PAIR_KEYS = {
    "kind", "blocker", "defining_view_chain", "pair_signature_sha256",
    "checks", "execution", "reproducer",
}
PAIR_BLOCKER_KEYS = {"operation", "signature", "signature_sha256", "source_location"}
CHAIN_KEYS = {"operation", "result_ssa", "source_ssa", "source_location"}
PAIR_CHECK_KEYS = {
    "earliest_registered_blocker", "defining_view_chain_present",
    "one_registered_operation_in_input", "parseable_reproducer_execution",
    "residual_pair_reproduced",
}
PAIR_REPRODUCER_KEYS = {
    "path", "bytes", "sha256", "registered_operation_count",
    "view_operation_count", "metadata",
}


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
        key for key in ("normalized_artifact", "next_pair", "next_frontier")
        if key in payload
    }
    if decision == "valid_normalized_output":
        residual_counts = (
            payload.get("complete", {}).get("after", {}).get(
                "registered_blocker_counts", {}
            )
        )
        residual = sum(residual_counts.values()) if residual_counts else 0
        expected_branch = (
            {"normalized_artifact", "next_pair"}
            if residual
            else {"normalized_artifact"}
        )
    else:
        expected_branch = {"next_frontier"}
    _require(branch_keys == expected_branch, "decision schema mismatch")
    _require(set(payload) - branch_keys == COMMON_KEYS, "top-level schema mismatch")
    _require(payload.get("status") == "evaluated", "status mismatch")
    _require_keys(payload.get("task2_contract"), BINDING_KEYS, "Task 2 contract binding schema")
    _require_keys(payload.get("predecessor_evaluation"), BINDING_KEYS, "predecessor evaluation binding schema")
    _require_keys(payload.get("predecessor_normalized_artifact"), BINDING_KEYS, "predecessor normalized artifact binding schema")
    _require_keys(payload.get("predecessor_observation"), PREDECESSOR_OBSERVATION_KEYS, "predecessor observation schema")
    _require_keys(payload.get("input"), BINDING_KEYS, "input binding schema")
    _require_keys(payload.get("tool"), BINDING_KEYS, "tool binding schema")
    _require_keys(payload.get("predecessor_plugin"), BINDING_KEYS, "predecessor plugin binding schema")
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
        generic_prints = run.get("generic_prints")
        _require(isinstance(generic_prints, list) and len(generic_prints) == 2, "generic-print schema mismatch")
        for generic in generic_prints:
            _require_keys(generic, GENERIC_KEYS, "generic-print schema")
            for key in ("input", "stdout", "stderr", "output"):
                _require_keys(generic.get(key), BINDING_KEYS, f"generic {key} schema")
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
        if "next_pair" in payload:
            pair = payload["next_pair"]
            _require_keys(pair, NEXT_PAIR_KEYS, "next-pair schema")
            _require_keys(pair.get("blocker"), PAIR_BLOCKER_KEYS, "next-pair blocker schema")
            _require_keys(pair["blocker"].get("source_location"), LOCATION_KEYS, "next-pair blocker location schema")
            chain = pair.get("defining_view_chain")
            _require(isinstance(chain, list) and chain, "earliest residual pair chain schema mismatch")
            for item in chain:
                _require_keys(item, CHAIN_KEYS, "next-pair chain schema")
                _require_keys(item.get("source_location"), LOCATION_KEYS, "next-pair chain location schema")
            _require_keys(pair.get("checks"), PAIR_CHECK_KEYS, "next-pair checks schema")
            _require_keys(pair.get("execution"), RUN_KEYS, "next-pair execution schema")
            _require_keys(pair.get("reproducer"), PAIR_REPRODUCER_KEYS, "next-pair reproducer schema")
            _require_keys(pair["reproducer"].get("metadata"), BINDING_KEYS, "next-pair metadata schema")
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


def _generic_memref_types(line: str) -> list[str]:
    types: list[str] = []
    cursor = 0
    while True:
        start = line.find("memref<", cursor)
        if start < 0:
            return types
        depth = 0
        for end in range(start + len("memref"), len(line)):
            if line[end] == "<":
                depth += 1
            elif line[end] == ">":
                depth -= 1
                if depth == 0:
                    types.append(line[start : end + 1])
                    cursor = end + 1
                    break
        else:
            raise ValueError("unterminated generic memref type")


def _independent_generic_affine_proof(
    text: str, *, probe_id: str, task2: Any
) -> dict[str, Any]:
    spec = PROBE_SPECS[probe_id]
    _require(
        f'sym_name = "{spec["function"]}"' in text,
        "semantic probe function mismatch",
    )
    entry = re.search(r"^\s*\^bb0\(([^)]*)\):", text, re.MULTILINE)
    _require(entry is not None, "semantic probe has no generic entry block")
    argument_names = re.findall(r"(%[A-Za-z0-9_.$-]+)\s*:", entry.group(1))
    _require(bool(argument_names), "semantic probe has no entry arguments")
    variables = copy.deepcopy(spec["variables"])
    expressions: dict[str, dict[str, Any]] = {}
    if probe_id == "semantic-collapsed-copy":
        constants = {
            name: int(value)
            for name, value in re.findall(
                r'^\s*(%[A-Za-z0-9_.$-]+) = "arith\.constant"\(\) '
                r'<\{value = (-?[0-9]+) : index\}>',
                text,
                re.MULTILINE,
            )
        }
        loop = re.search(
            r'"scf\.for"\((%[A-Za-z0-9_.$-]+), (%[A-Za-z0-9_.$-]+), '
            r'(%[A-Za-z0-9_.$-]+)\) \(\{\s*\^bb[0-9]+\('
            r'(%[A-Za-z0-9_.$-]+): index\)',
            text,
            re.DOTALL,
        )
        if loop is None:
            variable_name = "%copy_i"
        else:
            lower, upper, step, variable_name = loop.groups()
            _require(
                all(name in constants for name in (lower, upper, step))
                and [constants[lower], constants[upper], constants[step]] == [0, 64, 1],
                "copy loop domain mismatch",
            )
    else:
        argument = variables[0]["argument"]
        _require(
            isinstance(argument, int) and argument < len(argument_names),
            "semantic probe variable argument mismatch",
        )
        variable_name = argument_names[argument]
    expressions[variable_name] = {"coefficients": [1], "offset": 0}

    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_.$-]+) = "arith\.constant"\(\) '
        r'<\{value = (-?[0-9]+) : index\}>'
    )
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_.$-]+) = "arith\.(addi|subi|muli)"\('
        r'(%[A-Za-z0-9_.$-]+), (%[A-Za-z0-9_.$-]+)\)'
    )
    alias = re.compile(
        r'^\s*(%[A-Za-z0-9_.$-]+) = "memref\.(?:subview|collapse_shape|expand_shape|reinterpret_cast)"\('
        r'(%[A-Za-z0-9_.$-]+)'
    )
    aliases: dict[str, str] = {}
    for line in text.splitlines():
        if match := constant.match(line):
            expressions[match.group(1)] = {
                "coefficients": [0],
                "offset": int(match.group(2)),
            }
            continue
        if match := binary.match(line):
            left = expressions.get(match.group(3))
            right = expressions.get(match.group(4))
            _require(left is not None and right is not None, "semantic probe unresolved index")
            if match.group(2) == "addi":
                value = _sum(left, right)
            elif match.group(2) == "subi":
                value = _sum(left, right, -1)
            else:
                left_constant = not any(left["coefficients"])
                right_constant = not any(right["coefficients"])
                _require(left_constant or right_constant, "semantic probe non-affine multiplication")
                value = _scale(
                    right if left_constant else left,
                    left["offset"] if left_constant else right["offset"],
                )
            expressions[match.group(1)] = value
            continue
        if match := alias.match(line):
            aliases[match.group(1)] = match.group(2)

    def base_argument(name: str) -> int:
        visited: set[str] = set()
        while name in aliases:
            _require(name not in visited, "semantic probe alias cycle")
            visited.add(name)
            name = aliases[name]
        _require(name in argument_names, "semantic probe base mismatch")
        return argument_names.index(name)

    def access(kind: str, base: str, index: dict[str, Any], memref_type: str) -> dict[str, Any]:
        memref = task2._memref(memref_type)
        _require(
            memref["rank"] == 1 and isinstance(memref["shape"][0], int),
            "semantic probe access is not static rank one",
        )
        raw = copy.deepcopy(index)
        first = raw["offset"]
        last = first + raw["coefficients"][0] * (variables[0]["upper_exclusive"] - 1)
        raw["range"] = {
            "lower_inclusive": min(first, last),
            "upper_exclusive": max(first, last) + 1,
            "memref_upper_exclusive": memref["shape"][0],
            "in_bounds": 0 <= min(first, last) and max(first, last) < memref["shape"][0],
        }
        _require(
            isinstance(memref["offset"], int) and isinstance(memref["strides"][0], int),
            "semantic probe dynamic layout",
        )
        linear = _sum(
            {"coefficients": [0], "offset": memref["offset"]},
            _scale(index, memref["strides"][0]),
        )
        return {
            "kind": kind,
            "base": {
                "argument": base_argument(base),
                "role": "target" if kind == "store" else "source",
            },
            "raw_indices": [raw],
            "linear_formula": linear,
        }

    accesses: list[dict[str, Any]] = []
    load = re.compile(
        r'^\s*%[A-Za-z0-9_.$-]+ = "memref\.load"\('
        r'(%[A-Za-z0-9_.$-]+), (%[A-Za-z0-9_.$-]+)\)'
    )
    store = re.compile(
        r'^\s*"memref\.store"\(%[A-Za-z0-9_.$-]+, '
        r'(%[A-Za-z0-9_.$-]+), (%[A-Za-z0-9_.$-]+)\)'
    )
    copy_operation = re.compile(
        r'^\s*"memref\.copy"\((%[A-Za-z0-9_.$-]+), (%[A-Za-z0-9_.$-]+)\)'
    )
    for line in text.splitlines():
        match = load.match(line)
        kind = "load"
        if match is None:
            match = store.match(line)
            kind = "store"
        if match is not None:
            memrefs = _generic_memref_types(line)
            index = expressions.get(match.group(2))
            _require(index is not None and len(memrefs) == 1, "semantic probe access incomplete")
            accesses.append(access(kind, match.group(1), index, memrefs[0]))
            continue
        if copy_match := copy_operation.match(line):
            memrefs = _generic_memref_types(line)
            _require(len(memrefs) == 2, "semantic copy types incomplete")
            unit_index = {"coefficients": [1], "offset": 0}
            accesses.extend(
                (
                    access("load", copy_match.group(1), unit_index, memrefs[0]),
                    access("store", copy_match.group(2), unit_index, memrefs[1]),
                )
            )
    _require(
        len(accesses) == 2 and {item["kind"] for item in accesses} == {"load", "store"},
        "semantic probe access set mismatch",
    )
    return {"affine_status": "proven", "index_variables": variables, "access_maps": accesses}


def _proof_matches_literal(proof: dict[str, Any], probe_id: str) -> bool:
    spec = PROBE_SPECS[probe_id]
    actual = sorted(
        (
            {
                "kind": item["kind"],
                "argument": item["base"]["argument"],
                "role": item["base"]["role"],
                "offset": item["linear_formula"]["offset"],
                "coefficients": item["linear_formula"]["coefficients"],
            }
            for item in proof.get("access_maps", [])
        ),
        key=lambda item: item["kind"],
    )
    return (
        proof.get("affine_status") == "proven"
        and proof.get("index_variables") == spec["variables"]
        and len(proof.get("access_maps", [])) == 2
        and {item["kind"] for item in proof["access_maps"]} == {"load", "store"}
        and actual == sorted(spec["accesses"], key=lambda item: item["kind"])
        and all(
            raw["range"]["in_bounds"]
            for item in proof["access_maps"]
            for raw in item["raw_indices"]
        )
    )


_GENERIC_OPERATION = re.compile(r'"((?:[^"\\]|\\.)+)"\s*\(')


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


def _operation_census(generic_text: str) -> dict[str, int]:
    census: dict[str, int] = {}
    for match in _GENERIC_OPERATION.finditer(generic_text):
        name = _decode_generic_name(match.group(1))
        census[name] = census.get(name, 0) + 1
    return dict(sorted(census.items()))


def _canonical_operation_census(path: Path) -> dict[str, int]:
    command = [TOOL["path"], str(path), "-mlir-print-op-generic"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "canonical generic printing failed: "
        + completed.stderr.decode(errors="replace").strip(),
    )
    try:
        generic_text = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("canonical generic output is not UTF-8") from error
    census = _operation_census(generic_text)
    _require(bool(census), "canonical generic operation census is empty")
    return census


def _counts(operations: list[dict[str, Any]]) -> dict[str, int]:
    return {name: sum(item["operation"] == name for item in operations) for name in REGISTERED}


def _new_invalid(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return sorted(set(after) - set(before))


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


def _generic_command(input_path: Path, output_path: Path) -> list[str]:
    return [TOOL["path"], str(input_path), "-mlir-print-op-generic", "-o", str(output_path)]


def _check_generic_record(
    record: dict[str, Any], *, subject: str, input_path: Path, evidence_dir: Path
) -> Path:
    output_path = evidence_dir / f"{subject}.generic.mlir"
    _require(record["subject"] == subject, "generic-print subject mismatch")
    _require(record["command"] == _generic_command(input_path, output_path), "exact generic command mismatch")
    _require(record["input"] == _binding(input_path, relative=True), "generic input identity mismatch")
    for key, path in (
        ("stdout", evidence_dir / f"{subject}.generic.stdout.bin"),
        ("stderr", evidence_dir / f"{subject}.generic.stderr.bin"),
        ("output", output_path),
    ):
        _check_binding(record[key], path, f"{subject} generic {key}")
    return output_path


def _replay(run: dict[str, Any], input_path: Path, evidence_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="exact-unit-collapse-replay-") as raw:
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


def _replay_generic(record: dict[str, Any], input_path: Path, evidence_dir: Path) -> None:
    subject = record["subject"]
    with tempfile.TemporaryDirectory(prefix="exact-unit-generic-replay-") as raw:
        output = Path(raw) / f"{subject}.generic.mlir"
        completed = subprocess.run(
            _generic_command(input_path, output),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        _require(completed.returncode == record["exit_code"], "generic replay exit mismatch")
        _require(completed.stdout == (evidence_dir / f"{subject}.generic.stdout.bin").read_bytes(), "generic replay stdout mismatch")
        _require(completed.stderr == (evidence_dir / f"{subject}.generic.stderr.bin").read_bytes(), "generic replay stderr mismatch")
        _require(output.read_bytes() == (evidence_dir / f"{subject}.generic.mlir").read_bytes(), "generic replay output mismatch")


@functools.lru_cache(maxsize=1)
def _authenticated_predecessor() -> dict[str, Any]:
    _require(_binding(PREDECESSOR_EVALUATION, relative=True) == {
        "path": "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json",
        "bytes": 21_206,
        "sha256": PREDECESSOR_EVALUATION_SHA256,
    }, "predecessor evaluation identity mismatch")
    predecessor = _load_object(PREDECESSOR_EVALUATION, "predecessor evaluation")
    unsigned = copy.deepcopy(predecessor)
    unsigned["sha256"] = None
    _require(
        predecessor.get("sha256") == PREDECESSOR_SELF_SHA256
        and _digest(_canonical(unsigned)) == PREDECESSOR_SELF_SHA256,
        "predecessor evaluation self hash mismatch",
    )
    expected_output = {
        "path": "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence/complete-retained-c22-flat-scf/output.mlir",
        "bytes": 16_373_009,
        "sha256": PREDECESSOR_OUTPUT_SHA256,
    }
    _require(_binding(PREDECESSOR_OUTPUT, relative=True) == expected_output, "predecessor normalized artifact identity mismatch")
    _require(predecessor.get("normalized_artifact") == expected_output, "predecessor normalized artifact binding mismatch")
    _require(predecessor.get("plugin") == PREDECESSOR_PLUGIN, "predecessor plugin identity mismatch")
    _require(predecessor.get("tool") == TOOL, "predecessor tool identity mismatch")
    _require(
        predecessor.get("schema") == "tinystories-1m-exact-subview-extension-v1"
        and predecessor.get("status") == "evaluated"
        and predecessor.get("model") == "tiny-stories-1m-kev-gpt-exact"
        and predecessor.get("pipeline") == PIPELINE
        and predecessor.get("decision") == "valid_normalized_output"
        and predecessor.get("input", {}).get("sha256") == FLAT_SCF_SHA256,
        "predecessor observation mismatch",
    )
    return predecessor


@functools.lru_cache(maxsize=1)
def _verify_predecessors() -> None:
    """Authenticate immutable predecessors once per verifier process."""
    _authenticated_predecessor()
    completed = subprocess.run(
        [sys.executable, str(TASK2_VERIFIER_PATH)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(completed.returncode == 0, "authenticated Task 2 verifier failed")


_PAIR_VIEW = re.compile(
    r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*"
    r"(memref\.(?:subview|collapse_shape|expand_shape|reinterpret_cast))\s+"
    r"(%[A-Za-z0-9_.$-]+)"
)
_PAIR_ALLOC = re.compile(
    r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*(memref\.alloc)\("
)


def _derive_earliest_pair(text: str, task2: Any) -> dict[str, Any]:
    operations = task2._independent_operations(text)
    _require(bool(operations), "earliest residual pair missing")
    earliest = min(
        operations,
        key=lambda item: (
            item["source_location"]["line"],
            item["source_location"]["column"],
        ),
    )
    definitions: dict[str, dict[str, Any]] = {}
    current_function: str | None = None
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        function = re.match(r"^\s*func\.func\s+@([A-Za-z0-9_.$-]+)", line)
        if function:
            current_function = function.group(1)
        view = _PAIR_VIEW.match(line)
        alloc = _PAIR_ALLOC.match(line)
        if view is None and alloc is None:
            continue
        match = view or alloc
        statement = [line.strip()]
        continuation = number
        while continuation < len(lines) and lines[continuation].strip().startswith(":"):
            statement.append(lines[continuation].strip())
            continuation += 1
        operation = match.group(2)
        definitions[match.group(1)] = {
            "operation": operation,
            "result_ssa": match.group(1),
            "source_ssa": view.group(3) if view is not None else None,
            "source_location": {
                "function": current_function,
                "line": number,
                "column": line.index(operation) + 1,
                "mlir": " ".join(statement),
            },
        }
    blocker_line = earliest["source_location"]["line"]
    blocker_statement = [lines[blocker_line - 1].strip()]
    continuation = blocker_line
    while continuation < len(lines) and lines[continuation].strip().startswith(":"):
        blocker_statement.append(lines[continuation].strip())
        continuation += 1
    blocker_mlir = " ".join(blocker_statement)
    operands = re.findall(r"%[A-Za-z0-9_.$-]+", blocker_mlir)
    result = operands.pop(0) if "=" in blocker_mlir and operands else None
    chain: list[dict[str, Any]] = []
    visited: set[str] = set()

    def trace(name: str) -> None:
        definition = definitions.get(name)
        if definition is None or name in visited:
            return
        source = definition["source_ssa"]
        if source is not None:
            trace(source)
        visited.add(name)
        chain.append(copy.deepcopy(definition))

    for operand in operands:
        if operand != result:
            trace(operand)
    blocker = {
        "operation": earliest["operation"],
        "signature": earliest["signature"],
        "signature_sha256": _digest(_canonical(earliest["signature"])),
        "source_location": {**earliest["source_location"], "mlir": blocker_mlir},
    }
    pair_signature = {"blocker": blocker, "defining_view_chain": chain}
    return {
        "kind": "earliest_residual_defining_chain",
        "blocker": blocker,
        "defining_view_chain": chain,
        "pair_signature_sha256": _digest(_canonical(pair_signature)),
    }


def _render_pair_reproducer(pair: dict[str, Any], task2: Any) -> str:
    blocker = pair["blocker"]
    blocker_mlir = blocker["source_location"]["mlir"]
    operands = re.findall(r"%[A-Za-z0-9_.$-]+", blocker_mlir)
    result = operands.pop(0) if "=" in blocker_mlir and operands else None
    definitions = {item["result_ssa"]: item for item in pair["defining_view_chain"]}
    root_types: dict[str, str] = {}
    for item in pair["defining_view_chain"]:
        source = item["source_ssa"]
        if source is not None and source not in definitions:
            types = _generic_memref_types(item["source_location"]["mlir"])
            _require(bool(types), "earliest residual pair source type missing")
            root_types.setdefault(source, types[0])
    operand_types = blocker["signature"].get("operand_types", [])
    for operand, operand_type in zip(operands, operand_types):
        if operand not in definitions and operand not in root_types:
            root_types[operand] = operand_type
    body = [f"    {item['source_location']['mlir']}" for item in pair["defining_view_chain"]]
    arguments = ", ".join(f"{name}: {root_types[name]}" for name in root_types)
    if blocker["operation"] == "memref.copy":
        _require(len(operands) == 2 and len(operand_types) == 2, "earliest residual pair copy incomplete")
        source = task2._memref(operand_types[0])
        target = task2._memref(operand_types[1])
        _require(source["shape"] == target["shape"], "earliest residual pair copy shape mismatch")
        indices = []
        for index in range(source["rank"]):
            name = f"%c{index}"
            body.append(f"    {name} = arith.constant 0 : index")
            indices.append(name)
        element = source["element_type"]
        body.extend(
            (
                f"    %value = arith.constant 0 : {element}",
                f"    memref.store %value, {operands[0]}[{', '.join(indices)}] : {operand_types[0]}",
                f"    {blocker_mlir}",
                f"    %loaded = memref.load {operands[1]}[{', '.join(indices)}] : {operand_types[1]}",
                f"    return %loaded : {element}",
            )
        )
        function_result = f" -> {element}"
    elif result is not None and blocker["signature"].get("result_types"):
        result_type = blocker["signature"]["result_types"][0]
        memref = task2._memref(result_type)
        body.append(f"    {blocker_mlir}")
        indices = []
        for index in range(memref["rank"]):
            name = f"%c{index}"
            body.append(f"    {name} = arith.constant 0 : index")
            indices.append(name)
        body.append(f"    %loaded = memref.load {result}[{', '.join(indices)}] : {result_type}")
        body.append(f"    return %loaded : {memref['element_type']}")
        function_result = f" -> {memref['element_type']}"
    else:
        body.extend((f"    {blocker_mlir}", "    return"))
        function_result = ""
    return (
        "module {\n"
        f"  func.func @representative({arguments}){function_result} {{\n"
        + "\n".join(body)
        + "\n  }\n}\n"
    )


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
    before_census = _canonical_operation_census(flat_scf)
    full_parseable = runs[-1]["parseable"]
    if full_parseable:
        after_text = (evidence_dirs[-1] / "output.mlir").read_text(encoding="utf-8")
        after_operations = task2._independent_operations(after_text)
        after_counts: dict[str, int | None] = _counts(after_operations)
        after_registered_count: int | None = len(after_operations)
        after_census = _canonical_operation_census(evidence_dirs[-1] / "output.mlir")
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


@functools.lru_cache(maxsize=16)
def _trusted_census(path_text: str, expected_sha256: str) -> dict[str, int]:
    path = Path(path_text)
    raw = path.read_bytes()
    _require(_digest(raw) == expected_sha256, "generic census input identity mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("generic census is not UTF-8") from error
    census = _operation_census(text)
    _require(bool(census), "generic census is empty")
    return census


@functools.lru_cache(maxsize=8)
def _trusted_registered(path_text: str, expected_sha256: str) -> tuple[dict[str, int], int]:
    path = Path(path_text)
    raw = path.read_bytes()
    _require(_digest(raw) == expected_sha256, "registered census input identity mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("registered census input is not UTF-8") from error
    operations = _load_task2_verifier()._independent_operations(text)
    return _counts(operations), len(operations)


def _validate_task2_run(
    run: dict[str, Any],
    *,
    input_path: Path,
    evidence_dir: Path,
    replay: bool,
) -> tuple[Path, list[Path]]:
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
    expected_parseable = run["exit_code"] == 0 and run["parse_check"]["exit_code"] == 0
    _require(run["parseable"] is expected_parseable, "parseable status mismatch")
    generic_paths = [
        _check_generic_record(
            run["generic_prints"][0], subject="input", input_path=input_path,
            evidence_dir=evidence_dir,
        ),
        _check_generic_record(
            run["generic_prints"][1], subject="output", input_path=output_path,
            evidence_dir=evidence_dir,
        ),
    ]
    if replay:
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
        _replay(run, input_path, evidence_dir)
        _replay_generic(run["generic_prints"][0], input_path, evidence_dir)
        _replay_generic(run["generic_prints"][1], output_path, evidence_dir)
    return output_path, generic_paths


# This definition deliberately supersedes the mechanically inherited verifier
# above.  It shares no evaluator parser or decision code.
def validate_payload(payload: dict[str, Any], root: Path = ROOT, *, replay: bool) -> None:
    _require(root.resolve() == ROOT.resolve(), "verification root mismatch")
    _require(payload.get("schema") == "tinystories-1m-exact-unit-collapse-extension-v1", "schema mismatch")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    _require(payload.get("sha256") == _digest(_canonical(unsigned)), "evaluation self-hash mismatch")
    _validate_closed_schema(payload)
    _require(payload.get("pipeline") == PIPELINE, "pipeline mismatch")
    _require(payload.get("tool") == TOOL and _binding(Path(TOOL["path"])) == TOOL, "tool identity mismatch")
    _require(payload.get("predecessor_plugin") == PREDECESSOR_PLUGIN, "predecessor plugin identity mismatch")
    _require(payload.get("plugin") == PLUGIN, "plugin identity mismatch")
    _require(_binding(Path(PREDECESSOR_PLUGIN["path"])) == PREDECESSOR_PLUGIN, "predecessor plugin bytes mismatch")
    _require(_binding(Path(PLUGIN["path"])) == PLUGIN, "plugin identity mismatch")
    _require(PLUGIN["sha256"] != PREDECESSOR_PLUGIN["sha256"], "plugin identity does not differ from predecessor")
    _require(_digest(CONTRACT.read_bytes()) == CONTRACT_SHA256, "Task 2 contract bytes mismatch")
    _require(payload.get("task2_contract") == _binding(CONTRACT, relative=True), "Task 2 contract binding mismatch")
    _require(_digest(PREDECESSOR_EVALUATION.read_bytes()) == PREDECESSOR_EVALUATION_SHA256, "predecessor evaluation identity mismatch")
    _require(payload.get("predecessor_evaluation") == _binding(PREDECESSOR_EVALUATION, relative=True), "predecessor evaluation binding mismatch")
    _require(payload.get("predecessor_normalized_artifact") == _binding(PREDECESSOR_OUTPUT, relative=True), "predecessor normalized artifact mismatch")
    contract = _load_object(CONTRACT, "Task 2 contract")
    predecessor = _authenticated_predecessor()
    expected_predecessor = {
        "evaluation_self_sha256": predecessor["sha256"],
        "decision": predecessor["decision"],
        "registered_blocker_counts": predecessor["complete"]["after"]["registered_blocker_counts"],
    }
    _require(payload.get("predecessor_observation") == expected_predecessor, "predecessor observation mismatch")
    _require(payload.get("model") == contract["model"], "model mismatch")
    _require(payload.get("task_1_through_3_identities") == contract["task_1_through_3_identities"], "Task 1--3 identities mismatch")
    _require(payload.get("provenance") == _expected_provenance(contract), "provenance mismatch")
    _require(payload.get("source_revision") == _expected_source_revision(), "source revision mismatch")
    _require(payload.get("python") == _binding(Path(sys.executable).resolve()), "python interpreter binding mismatch")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    _require(_binding(flat_scf, relative=True) == {
        "path": contract["source"]["flat_scf"]["path"],
        "bytes": 18_933_168,
        "sha256": FLAT_SCF_SHA256,
    }, "input identity mismatch")
    _require(payload.get("input") == _binding(flat_scf, relative=True), "input identity mismatch")
    _verify_predecessors()

    expected_specs = [*RUN_SPECS, ("complete-retained-c22-flat-scf", "complete", flat_scf)]
    runs = payload["executions"]
    _require(len(runs) == 4, "causal execution order mismatch")
    _require([run["sequence"] for run in runs] == [1, 2, 3, 4], "causal execution sequence mismatch")
    _require([run["id"] for run in runs] == [spec[0] for spec in expected_specs], "canonical run id mismatch")
    _require([run["kind"] for run in runs] == [spec[1] for spec in expected_specs], "causal execution kind mismatch")
    _require(all(run["causal_preconditions_satisfied"] is True for run in runs), "causal precondition mismatch")
    outputs: list[Path] = []
    generics: list[list[Path]] = []
    evidence_dirs: list[Path] = []
    input_paths: list[Path] = []
    for run, spec in zip(runs, expected_specs):
        evidence_dir = EVIDENCE_ROOT / spec[0]
        output_path, generic_paths = _validate_task2_run(
            run,
            input_path=spec[2],
            evidence_dir=evidence_dir,
            replay=replay,
        )
        outputs.append(output_path)
        generics.append(generic_paths)
        evidence_dirs.append(evidence_dir)
        input_paths.append(spec[2])
    _require(all(run["exit_code"] == 0 and run["parseable"] for run in runs[:3]), "probe execution failed")

    task2 = _load_task2_verifier()
    expected_probes = []
    for index, (identifier, _, input_path) in enumerate(RUN_SPECS):
        before_text = generics[index][0].read_text(encoding="utf-8")
        after_text = generics[index][1].read_text(encoding="utf-8")
        before = _independent_generic_affine_proof(before_text, probe_id=identifier, task2=task2)
        after = _independent_generic_affine_proof(after_text, probe_id=identifier, task2=task2)
        output_text = outputs[index].read_text(encoding="utf-8")
        checks = {
            "exit_zero": runs[index]["exit_code"] == 0,
            "parseable": runs[index]["parseable"],
            "before_matches_literal_affine_map": _proof_matches_literal(before, identifier),
            "after_matches_literal_affine_map": _proof_matches_literal(after, identifier),
            "complete_affine_mapping_preserved": _proof_matches_literal(before, identifier) and _proof_matches_literal(after, identifier),
            "subview_eliminated": "memref.subview" not in output_text,
            "collapse_eliminated": "memref.collapse_shape" not in output_text,
            "copy_eliminated_or_absent": "memref.copy" not in output_text,
        }
        expected_probes.append({
            "id": identifier,
            "execution_id": runs[index]["id"],
            "invariant_status": "proven" if all(checks.values()) else "unproven",
            "before": before,
            "after": after,
            "checks": checks,
        })
    _require(payload["semantic_probes"] == expected_probes, "semantic probe mismatch")
    _require(all(probe["invariant_status"] == "proven" for probe in expected_probes), "semantic probe unproven")

    before_census = _trusted_census(str(generics[-1][0]), runs[-1]["generic_prints"][0]["output"]["sha256"])
    before_counts, before_total = _trusted_registered(str(flat_scf), FLAT_SCF_SHA256)
    full_parseable = runs[-1]["parseable"]
    if full_parseable:
        after_census = _trusted_census(str(generics[-1][1]), runs[-1]["generic_prints"][1]["output"]["sha256"])
        after_counts, after_total = _trusted_registered(str(outputs[-1]), runs[-1]["output"]["sha256"])
        invalid_classes = _new_invalid(before_census, after_census)
    else:
        after_census = {}
        after_counts = {name: None for name in REGISTERED}
        after_total = None
        invalid_classes = []
    expected_complete = {
        "parseable": full_parseable,
        "before": {
            "operation_census": before_census,
            "registered_blocker_counts": before_counts,
            "registered_operation_count": before_total,
        },
        "after": {
            "operation_census": after_census,
            "registered_blocker_counts": after_counts,
            "registered_operation_count": after_total,
        },
        "new_invalid_classes": invalid_classes,
        "invariant_status": (
            "unavailable_due_invalid_output"
            if not full_parseable
            else ("proven" if not invalid_classes else "unproven")
        ),
    }
    _require(payload["complete"]["before"] == expected_complete["before"], "before blocker census mismatch")
    _require(payload["complete"]["after"]["operation_census"] == after_census, "after operation census mismatch")
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
        if isinstance(after_total, int) and after_total:
            claimed = payload["next_pair"]
            full_text = outputs[-1].read_text(encoding="utf-8")
            derived = _derive_earliest_pair(full_text, task2)
            claimed_base = {
                key: claimed[key]
                for key in ("kind", "blocker", "defining_view_chain", "pair_signature_sha256")
            }
            _require(claimed_base == derived, "earliest residual pair mismatch")
            pair_dir = EVIDENCE_ROOT / "next-pair"
            pair_input = pair_dir / "input.mlir"
            _require(pair_input.read_text(encoding="utf-8") == _render_pair_reproducer(derived, task2), "earliest residual pair reproducer mismatch")
            pair_run = claimed["execution"]
            pair_output, pair_generics = _validate_task2_run(
                pair_run,
                input_path=pair_input,
                evidence_dir=pair_dir,
                replay=replay,
            )
            input_operations = task2._independent_operations(pair_input.read_text(encoding="utf-8"))
            output_operations = task2._independent_operations(pair_output.read_text(encoding="utf-8")) if pair_run["parseable"] else []
            checks = {
                "earliest_registered_blocker": True,
                "defining_view_chain_present": bool(derived["defining_view_chain"]),
                "one_registered_operation_in_input": len(input_operations) == 1,
                "parseable_reproducer_execution": pair_run["parseable"],
                "residual_pair_reproduced": (
                    len(output_operations) == 1
                    and output_operations[0]["operation"] == derived["blocker"]["operation"]
                ),
            }
            _require(claimed["checks"] == checks and all(checks.values()), "earliest residual pair checks mismatch")
            expected_reproducer = {
                **_binding(pair_input, relative=True),
                "registered_operation_count": len(input_operations),
                "view_operation_count": sum(
                    item["operation"].startswith("memref.")
                    for item in derived["defining_view_chain"]
                ),
                "metadata": _binding(pair_dir / "metadata.json", relative=True),
            }
            _require(claimed["reproducer"] == expected_reproducer, "earliest residual pair reproducer mismatch")
            metadata = _load_object(pair_dir / "metadata.json", "next-pair metadata")
            _require(metadata == {
                "schema": "tinystories-1m-exact-unit-collapse-next-pair-v1",
                "pair": derived,
                "checks": checks,
                "execution": pair_run,
            }, "earliest residual pair metadata mismatch")
            # The pair's generic evidence is itself a complete census, not an
            # unchecked side file.
            _trusted_census(str(pair_generics[0]), pair_run["generic_prints"][0]["output"]["sha256"])
            _trusted_census(str(pair_generics[1]), pair_run["generic_prints"][1]["output"]["sha256"])
        else:
            _require("next_pair" not in payload, "earliest residual pair decision mismatch")
    else:
        _require(not full_parseable, "earliest frontier mismatch")


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
