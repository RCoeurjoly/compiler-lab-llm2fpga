#!/usr/bin/env python3
"""Independently verify and replay the exact rank-one copy gate receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evaluation.json"
EVIDENCE_ROOT = ROOT / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence"
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
PREDECESSOR_EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json"
PREDECESSOR_OUTPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/complete-retained-c22-flat-scf/output.mlir"
SIZE1 = ROOT / "reproducers/tinystories-1m-exact-direct-rank1-copy/size1.mlir"
SIZE64 = ROOT / "reproducers/tinystories-1m-exact-direct-rank1-copy/size64.mlir"
PASS_SOURCE = ROOT / "tools/mlir-passes/FoldConstantTruncFOps.cpp"
PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
PROBE_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx)"
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
PREDECESSOR_EVALUATION_SHA256 = "eae77d6f74ccb5091ec6b6ab3d1876b6326a34fee6e974c29ea7dc1b5e7946ad"
PREDECESSOR_OUTPUT_SHA256 = "733e65144ef46004a5de4fde3a38c418b8ed894daf4482f32cd468157389ce9f"
PREDECESSOR_SELF_SHA256 = "6e7772175d4f4acf1badae01df293f7f37419fc05e74e2f5da1d04f85bc0a540"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
PREDECESSOR_COMMIT = "83391e92af089b4aa68a47dd8ec5278bcb284afd"
ASSIGNED_BASE = "8b08bd21a683abfa2837e1aa62c57e5bc77be439"
PASS_SOURCE_BLOB = "3c570a72637686161b27d5d78474aef34eea5697"
PASS_SOURCE_SHA256 = "a7461a22d405212534b9d3a6a0df415d8a960042ba253459e2e14e3c1e894756"
TOOL = {
    "path": "/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt",
    "bytes": 496904,
    "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
}
PREDECESSOR_PLUGIN = {
    "path": "/nix/store/7nffqc9cn9da37py316ilmcarjpp9gbn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21726600,
    "sha256": "9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984",
}
PLUGIN = {
    "path": "/nix/store/f6mglahvc3l9pnsanr0pgiww0wcsivgg-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so",
    "bytes": 21726600,
    "sha256": "79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738",
}
PROBE_SPECS = {
    "size1": {"path": SIZE1, "extent": 1, "live_index": 0},
    "size64": {"path": SIZE64, "extent": 64, "live_index": 63},
}
RUN_SPECS = (
    ("semantic-size1-pass-only", "semantic_probe_pass_only", SIZE1, PROBE_PIPELINE),
    ("semantic-size1-integrated", "semantic_probe_integrated", SIZE1, PIPELINE),
    ("semantic-size64-pass-only", "semantic_probe_pass_only", SIZE64, PROBE_PIPELINE),
    ("semantic-size64-integrated", "semantic_probe_integrated", SIZE64, PIPELINE),
)
BINDING_KEYS = {"path", "bytes", "sha256"}
RUN_KEYS = {
    "sequence", "id", "kind", "causal_preconditions_satisfied", "command",
    "input", "input_after", "exit_code", "elapsed_ns", "output_created",
    "stdout", "stderr", "output", "parse_check", "parseable", "generic_prints",
}
GENERIC_KEYS = {"subject", "command", "exit_code", "input", "stdout", "stderr", "output"}
PARSE_KEYS = {"command", "exit_code", "stdout", "stderr"}
PHASE_KEYS = {"operation_census", "registered_blocker_counts", "registered_operation_count"}
COMPLETE_KEYS = {"parseable", "before", "after", "after_only_operation_classes", "invariant_status"}
PROBE_KEYS = {"id", "pass_execution_id", "integrated_execution_id", "invariant_status", "proof", "checks"}
PROOF_KEYS = {
    "extent", "live_index", "distinct_bases", "source_allocation", "target_allocation",
    "loop_domain", "copy_accesses", "live_flow",
}
HANDOFF_KEYS = {"artifact", "next_plan", "stage_registration_authorized", "calyx_authorized"}
SOURCE_KEYS = {"assigned_base", "task1_commit", "pass_source_blob", "pass_source"}
PREDECESSOR_OBSERVATION_KEYS = {"decision", "registered_blocker_counts"}


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
    _require(isinstance(value, dict) and set(value) == expected, f"{label} schema mismatch")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {error}") from error
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


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
    _require(completed.returncode == 0, f"historical Git binding missing for {relative}")
    return completed.stdout


def _check_binding(claimed: Any, canonical: Path, label: str) -> Path:
    _require_keys(claimed, BINDING_KEYS, label)
    _require(canonical.is_file(), f"{label} absent")
    _require(claimed == _binding(canonical, relative=not canonical.is_absolute() or canonical.is_relative_to(ROOT)), label)
    return canonical


def _validate_closed_schema(payload: dict[str, Any]) -> None:
    common = {
        "schema", "status", "model", "task_1_through_3_identities", "task2_contract",
        "predecessor_evaluation", "predecessor_evaluation_self_sha256",
        "predecessor_normalized_artifact", "predecessor_plugin", "predecessor_observation",
        "input", "tool", "plugin", "python", "source_revision", "pipeline",
        "probe_pipeline", "provenance", "executions", "semantic_probes", "complete",
        "zero_registered_blockers", "decision", "sha256",
    }
    decision = payload.get("decision")
    if decision == "zero_registered_blockers":
        expected = common | {"normalized_artifact", "handoff"}
    elif decision == "residual_registered_blockers":
        expected = common | {"normalized_artifact", "next_pair"}
    elif decision == "next_compiler_frontier":
        expected = common | {"next_frontier"}
    else:
        raise ValueError("decision schema mismatch")
    extras = set(payload) - expected
    missing = expected - set(payload)
    if extras & {"next_pair", "next_frontier", "normalized_artifact", "handoff"}:
        raise ValueError("decision schema mismatch")
    _require(not extras and not missing, "top-level schema mismatch")
    _require_keys(payload["task2_contract"], BINDING_KEYS, "Task 2 contract binding")
    _require_keys(payload["predecessor_evaluation"], BINDING_KEYS, "predecessor evaluation")
    _require_keys(payload["predecessor_normalized_artifact"], BINDING_KEYS, "predecessor artifact")
    _require_keys(payload["predecessor_plugin"], BINDING_KEYS, "predecessor plugin")
    _require_keys(payload["input"], BINDING_KEYS, "input")
    _require_keys(payload["tool"], BINDING_KEYS, "tool")
    _require_keys(payload["plugin"], BINDING_KEYS, "plugin")
    _require_keys(payload["python"], BINDING_KEYS, "python")
    _require_keys(payload["source_revision"], SOURCE_KEYS, "source revision")
    _require_keys(payload["source_revision"]["pass_source"], BINDING_KEYS, "pass source")
    _require_keys(payload["predecessor_observation"], PREDECESSOR_OBSERVATION_KEYS, "predecessor observation")
    _require(isinstance(payload["executions"], list), "execution schema mismatch")
    for run in payload["executions"]:
        _require_keys(run, RUN_KEYS, "execution")
        for key in ("input", "input_after", "stdout", "stderr", "output"):
            _require_keys(run[key], BINDING_KEYS, f"execution {key}")
        _require_keys(run["parse_check"], PARSE_KEYS, "parse check")
        _require_keys(run["parse_check"]["stdout"], BINDING_KEYS, "parse stdout")
        _require_keys(run["parse_check"]["stderr"], BINDING_KEYS, "parse stderr")
        _require(isinstance(run["generic_prints"], list) and len(run["generic_prints"]) == 2, "execution generic schema mismatch")
        for record in run["generic_prints"]:
            _require_keys(record, GENERIC_KEYS, "generic execution")
            for key in ("input", "stdout", "stderr", "output"):
                _require_keys(record[key], BINDING_KEYS, f"generic {key}")
    _require_keys(payload["complete"], COMPLETE_KEYS, "complete")
    _require_keys(payload["complete"]["before"], PHASE_KEYS, "complete before")
    _require_keys(payload["complete"]["after"], PHASE_KEYS, "complete after")
    _require(isinstance(payload["semantic_probes"], list) and len(payload["semantic_probes"]) == 2, "semantic probe schema mismatch")
    for probe in payload["semantic_probes"]:
        _require_keys(probe, PROBE_KEYS, "semantic probe")
        _require_keys(probe["proof"], PROOF_KEYS, "semantic proof")
    if decision == "zero_registered_blockers":
        _require_keys(payload["normalized_artifact"], BINDING_KEYS, "normalized artifact")
        _require_keys(payload["handoff"], HANDOFF_KEYS, "handoff")


_GENERIC_OPERATION = re.compile(r'"((?:[^"\\]|\\.)+)"\s*\(')


def _decode_name(raw: str) -> str:
    result: list[str] = []
    cursor = 0
    while cursor < len(raw):
        if raw[cursor] != "\\":
            result.append(raw[cursor])
            cursor += 1
            continue
        cursor += 1
        _require(cursor < len(raw), "generic operation escape is incomplete")
        escaped = raw[cursor]
        if escaped in {'"', "\\"}:
            result.append(escaped)
            cursor += 1
        elif escaped == "n":
            result.append("\n")
            cursor += 1
        elif escaped == "t":
            result.append("\t")
            cursor += 1
        elif (
            cursor + 1 < len(raw)
            and escaped in "0123456789abcdefABCDEF"
            and raw[cursor + 1] in "0123456789abcdefABCDEF"
        ):
            result.append(chr(int(raw[cursor : cursor + 2], 16)))
            cursor += 2
        else:
            raise ValueError("generic operation escape is invalid")
    return "".join(result)


def _operation_census(generic_text: str) -> dict[str, int]:
    census: dict[str, int] = {}
    for match in _GENERIC_OPERATION.finditer(generic_text):
        operation = _decode_name(match.group(1))
        census[operation] = census.get(operation, 0) + 1
    return dict(sorted(census.items()))


def _registered(census: dict[str, int]) -> dict[str, int]:
    return {name: census.get(name, 0) for name in REGISTERED}


def _new_classes(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return sorted(set(after) - set(before))


def _index_values(text: str, induction: str) -> dict[str, tuple[int, int]]:
    values: dict[str, tuple[int, int]] = {induction: (0, 1)}
    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) <\{value = (-?[0-9]+) : index\}>'
    )
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.(addi|muli)"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    for line in text.splitlines():
        if match := constant.match(line):
            values[match.group(1)] = (int(match.group(2)), 0)
        elif match := binary.match(line):
            result, operation, lhs, rhs = match.groups()
            if lhs not in values or rhs not in values:
                continue
            left, right = values[lhs], values[rhs]
            if operation == "addi":
                values[result] = (left[0] + right[0], left[1] + right[1])
            elif left[1] == 0:
                values[result] = (right[0] * left[0], right[1] * left[0])
            elif right[1] == 0:
                values[result] = (left[0] * right[0], left[1] * right[0])
            else:
                raise ValueError("semantic probe contains non-affine index")
    return values


def _independent_copy_proof(before: str, after: str, probe_id: str) -> dict[str, Any]:
    spec = PROBE_SPECS[probe_id]
    before_allocations = re.findall(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.alloc"\(', before, re.MULTILINE
    )
    after_allocations = re.findall(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.alloc"\(', after, re.MULTILINE
    )
    _require(len(before_allocations) == len(after_allocations) == 2, "semantic probe allocation count mismatch")
    copy_op = re.search(r'"memref\.copy"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)', before)
    _require(copy_op is not None and list(copy_op.groups()) == before_allocations, "semantic probe input direction mismatch")
    literal_constants = {
        result: int(value)
        for result, value in re.findall(
            r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) <\{value = (-?[0-9]+) : index\}>',
            after,
            re.MULTILINE,
        )
    }
    loops = re.findall(
        r'"scf\.for"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\) \(\{\s*\^bb[0-9]+\((%[A-Za-z0-9_]+): index\)',
        after,
        re.DOTALL,
    )
    _require(len(loops) == 1, "semantic probe loop count mismatch")
    lower, upper, step, induction = loops[0]
    _require(all(name in literal_constants for name in (lower, upper, step)), "semantic probe loop bounds mismatch")
    expressions = _index_values(after, induction)
    load_matches = list(
        re.finditer(
            r'^\s*(%[A-Za-z0-9_]+) = "memref\.load"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)',
            after,
            re.MULTILINE,
        )
    )
    store_matches = list(
        re.finditer(
            r'^\s*"memref\.store"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)',
            after,
            re.MULTILINE,
        )
    )
    loop_loads = [item for item in load_matches if expressions.get(item.group(3), (0, 0))[1]]
    loop_stores = [item for item in store_matches if expressions.get(item.group(3), (0, 0))[1]]
    observed_loads = [item for item in load_matches if not expressions.get(item.group(3), (0, 0))[1]]
    initialized_stores = [item for item in store_matches if not expressions.get(item.group(3), (0, 0))[1]]
    _require(
        all(len(items) == 1 for items in (loop_loads, loop_stores, observed_loads, initialized_stores)),
        "semantic probe access cardinality mismatch",
    )
    loop_load, loop_store = loop_loads[0], loop_stores[0]
    observed, initialized = observed_loads[0], initialized_stores[0]
    _require(loop_store.group(1) == loop_load.group(1), "semantic probe data direction mismatch")
    returned = re.search(r'"func\.return"\((%[A-Za-z0-9_]+)\)', after)
    _require(returned is not None, "semantic probe live result absent")
    allocation_numbers = {name: number for number, name in enumerate(after_allocations)}
    load_expr = expressions[loop_load.group(3)]
    store_expr = expressions[loop_store.group(3)]
    initial_expr = expressions[initialized.group(3)]
    observed_expr = expressions[observed.group(3)]
    return {
        "extent": spec["extent"],
        "live_index": spec["live_index"],
        "distinct_bases": after_allocations[0] != after_allocations[1],
        "source_allocation": allocation_numbers.get(loop_load.group(2)),
        "target_allocation": allocation_numbers.get(loop_store.group(2)),
        "loop_domain": {
            "lower": literal_constants[lower],
            "upper_exclusive": literal_constants[upper],
            "step": literal_constants[step],
        },
        "copy_accesses": [
            {
                "kind": "load", "role": "source",
                "allocation": allocation_numbers.get(loop_load.group(2)),
                "offset": load_expr[0], "coefficient": load_expr[1],
            },
            {
                "kind": "store", "role": "target",
                "allocation": allocation_numbers.get(loop_store.group(2)),
                "offset": store_expr[0], "coefficient": store_expr[1],
            },
        ],
        "live_flow": {
            "input_argument": 0 if initialized.group(1) == "%arg0" else None,
            "source_store_index": initial_expr[0]
            if initial_expr[1] == 0 and allocation_numbers.get(initialized.group(2)) == 0
            else None,
            "target_load_index": observed_expr[0]
            if observed_expr[1] == 0 and allocation_numbers.get(observed.group(2)) == 1
            else None,
            "returned_target_observation": returned.group(1) == observed.group(1),
        },
    }


def _literal_proof(probe_id: str) -> dict[str, Any]:
    spec = PROBE_SPECS[probe_id]
    return {
        "extent": spec["extent"],
        "live_index": spec["live_index"],
        "distinct_bases": True,
        "source_allocation": 0,
        "target_allocation": 1,
        "loop_domain": {"lower": 0, "upper_exclusive": spec["extent"], "step": 1},
        "copy_accesses": [
            {"kind": "load", "role": "source", "allocation": 0, "offset": 0, "coefficient": 1},
            {"kind": "store", "role": "target", "allocation": 1, "offset": 0, "coefficient": 1},
        ],
        "live_flow": {
            "input_argument": 0,
            "source_store_index": spec["live_index"],
            "target_load_index": spec["live_index"],
            "returned_target_observation": True,
        },
    }


def _authenticated_predecessor() -> dict[str, Any]:
    expected_receipt = {
        "path": "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json",
        "bytes": 40_418,
        "sha256": PREDECESSOR_EVALUATION_SHA256,
    }
    _require(_binding(PREDECESSOR_EVALUATION, relative=True) == expected_receipt, "predecessor evaluation identity mismatch")
    _require(
        _git_bytes(PREDECESSOR_COMMIT, expected_receipt["path"]) == PREDECESSOR_EVALUATION.read_bytes(),
        "predecessor historical Git binding mismatch",
    )
    previous = _load_object(PREDECESSOR_EVALUATION, "predecessor evaluation")
    unsigned = copy.deepcopy(previous)
    unsigned["sha256"] = None
    _require(previous.get("sha256") == PREDECESSOR_SELF_SHA256, "predecessor self hash mismatch")
    _require(_digest(_canonical(unsigned)) == PREDECESSOR_SELF_SHA256, "predecessor self hash mismatch")
    expected_output = {
        "path": "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/complete-retained-c22-flat-scf/output.mlir",
        "bytes": 15_196_673,
        "sha256": PREDECESSOR_OUTPUT_SHA256,
    }
    _require(_binding(PREDECESSOR_OUTPUT, relative=True) == expected_output, "predecessor normalized artifact mismatch")
    _require(
        _git_bytes(PREDECESSOR_COMMIT, expected_output["path"]) == PREDECESSOR_OUTPUT.read_bytes(),
        "predecessor output historical Git binding mismatch",
    )
    _require(previous.get("schema") == "tinystories-1m-exact-unit-collapse-extension-v1", "predecessor schema mismatch")
    _require(previous.get("decision") == "valid_normalized_output", "predecessor decision mismatch")
    _require(previous.get("plugin") == PREDECESSOR_PLUGIN, "predecessor plugin identity mismatch")
    _require(previous.get("tool") == TOOL, "predecessor tool identity mismatch")
    _require(previous.get("normalized_artifact") == expected_output, "predecessor artifact binding mismatch")
    expected_counts = {
        "memref.collapse_shape": 0,
        "memref.copy": 1022,
        "memref.expand_shape": 0,
        "memref.reinterpret_cast": 0,
    }
    _require(previous.get("complete", {}).get("after", {}).get("registered_blocker_counts") == expected_counts, "predecessor blocker census mismatch")
    return previous


def _expected_source_revision() -> dict[str, Any]:
    relative = str(PASS_SOURCE.relative_to(ROOT))
    live = PASS_SOURCE.read_bytes()
    _require(_git_bytes(ASSIGNED_BASE, relative) == live, "source revision mismatch")
    _require(_digest(live) == PASS_SOURCE_SHA256, "source revision mismatch")
    completed = subprocess.run(
        ["git", "rev-parse", f"{ASSIGNED_BASE}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    _require(completed.returncode == 0 and completed.stdout.strip() == PASS_SOURCE_BLOB, "source revision mismatch")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ASSIGNED_BASE, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(ancestor.returncode == 0, "source revision mismatch")
    return {
        "assigned_base": ASSIGNED_BASE,
        "task1_commit": ASSIGNED_BASE,
        "pass_source_blob": PASS_SOURCE_BLOB,
        "pass_source": _binding(PASS_SOURCE, relative=True),
    }


def _validate_generic(record: dict[str, Any], *, subject: str, input_path: Path, directory: Path) -> Path:
    output = directory / f"{subject}.generic.mlir"
    expected_command = [TOOL["path"], str(input_path), "-mlir-print-op-generic", "-o", str(output)]
    _require(record["subject"] == subject, "exact generic command mismatch")
    _require(record["command"] == expected_command, "exact generic command mismatch")
    _require(record["input"] == _binding(input_path, relative=True), "generic input identity mismatch")
    _require(record["stdout"] == _binding(directory / f"{subject}.generic.stdout.bin", relative=True), "canonical evidence path mismatch")
    _require(record["stderr"] == _binding(directory / f"{subject}.generic.stderr.bin", relative=True), "canonical evidence path mismatch")
    _require(record["output"] == _binding(output, relative=True), "canonical evidence path mismatch")
    return output


def _validate_run(
    run: dict[str, Any],
    *,
    spec: tuple[str, str, Path, str],
    sequence: int,
    replay: bool,
) -> tuple[Path, list[Path]]:
    identifier, kind, input_path, pipeline = spec
    directory = EVIDENCE_ROOT / identifier
    output_path = directory / "output.mlir"
    _require(run["sequence"] == sequence and run["id"] == identifier and run["kind"] == kind, "causal execution order mismatch")
    _require(run["causal_preconditions_satisfied"] is True, "causal precondition mismatch")
    _require(type(run["elapsed_ns"]) is int and run["elapsed_ns"] > 0, "elapsed time invalid")
    _require(run["input"] == _binding(input_path, relative=True), "unchanged input identity mismatch")
    _require(run["input_after"] == run["input"], "unchanged input identity mismatch")
    expected_command = [
        TOOL["path"], str(input_path), f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={pipeline}", "-o", str(output_path),
    ]
    _require(run["command"] == expected_command, "exact pass command mismatch")
    lowered = " ".join(run["command"]).lower().replace("for-calyx", "")
    _require("calyx" not in lowered and "circt-opt" not in lowered, "Calyx command forbidden")
    _require(run["stdout"] == _binding(directory / "stdout.bin", relative=True), "canonical evidence path mismatch")
    _require(run["stderr"] == _binding(directory / "stderr.bin", relative=True), "canonical evidence path mismatch")
    _require(run["output"] == _binding(output_path, relative=True), "canonical evidence path or stale output mismatch")
    parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
    _require(run["parse_check"]["command"] == parse_command, "parse command mismatch")
    _require(run["parse_check"]["stdout"] == _binding(directory / "parse.stdout.bin", relative=True), "canonical evidence path mismatch")
    _require(run["parse_check"]["stderr"] == _binding(directory / "parse.stderr.bin", relative=True), "canonical evidence path mismatch")
    expected_parseable = run["exit_code"] == 0 and run["parse_check"]["exit_code"] == 0
    _require(run["parseable"] is expected_parseable, "parseable status mismatch")
    _require(run["output_created"] is (run["exit_code"] == 0), "output creation mismatch")
    generics = [
        _validate_generic(run["generic_prints"][0], subject="input", input_path=input_path, directory=directory),
        _validate_generic(run["generic_prints"][1], subject="output", input_path=output_path, directory=directory),
    ]
    if replay:
        with tempfile.TemporaryDirectory(prefix=f"rank1-replay-{identifier}-") as raw:
            temporary = Path(raw)
            replay_output = temporary / "output.mlir"
            replay_command = [
                TOOL["path"], str(input_path), f"--load-pass-plugin={PLUGIN['path']}",
                f"--pass-pipeline={pipeline}", "-o", str(replay_output),
            ]
            completed = subprocess.run(
                replay_command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            _require(completed.returncode == run["exit_code"], "pass replay exit mismatch")
            _require(completed.stdout == (directory / "stdout.bin").read_bytes(), "pass replay stdout mismatch")
            _require(completed.stderr == (directory / "stderr.bin").read_bytes(), "pass replay stderr mismatch")
            replay_bytes = replay_output.read_bytes() if replay_output.is_file() else b""
            _require(replay_bytes == output_path.read_bytes(), "pass replay output bytes mismatch")
            parsed = subprocess.run(
                [TOOL["path"], str(replay_output), "-o", "/dev/null"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            _require(parsed.returncode == run["parse_check"]["exit_code"], "parse replay exit mismatch")
            _require(parsed.stdout == (directory / "parse.stdout.bin").read_bytes(), "parse replay stdout mismatch")
            _require(parsed.stderr == (directory / "parse.stderr.bin").read_bytes(), "parse replay stderr mismatch")
            for subject, source, retained in (
                ("input", input_path, generics[0]),
                ("output", replay_output, generics[1]),
            ):
                generic_output = temporary / f"{subject}.generic.mlir"
                generic = subprocess.run(
                    [TOOL["path"], str(source), "-mlir-print-op-generic", "-o", str(generic_output)],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                record = run["generic_prints"][0 if subject == "input" else 1]
                _require(generic.returncode == record["exit_code"], "generic replay exit mismatch")
                _require(generic.stdout == (directory / f"{subject}.generic.stdout.bin").read_bytes(), "generic replay stdout mismatch")
                _require(generic.stderr == (directory / f"{subject}.generic.stderr.bin").read_bytes(), "generic replay stderr mismatch")
                _require(generic_output.read_bytes() == retained.read_bytes(), "generic replay output bytes mismatch")
    return output_path, generics


def validate_payload(payload: dict[str, Any], root: Path = ROOT, *, replay: bool) -> None:
    _require(root.resolve() == ROOT.resolve(), "verification root mismatch")
    _require(payload.get("schema") == "tinystories-1m-exact-rank1-copy-extension-v1", "schema mismatch")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    _require(payload.get("sha256") == _digest(_canonical(unsigned)), "evaluation self-hash mismatch")
    _validate_closed_schema(payload)
    _require(payload.get("status") == "evaluated", "status mismatch")
    _require(payload.get("pipeline") == PIPELINE and payload.get("probe_pipeline") == PROBE_PIPELINE, "pipeline mismatch")
    _require(payload.get("tool") == TOOL and _binding(Path(TOOL["path"])) == TOOL, "tool identity mismatch")
    _require(payload.get("predecessor_plugin") == PREDECESSOR_PLUGIN, "predecessor plugin identity mismatch")
    _require(_binding(Path(PREDECESSOR_PLUGIN["path"])) == PREDECESSOR_PLUGIN, "predecessor plugin bytes mismatch")
    _require(payload.get("plugin") == PLUGIN, "plugin identity mismatch")
    _require(_binding(Path(PLUGIN["path"])) == PLUGIN, "plugin identity mismatch")
    _require(PLUGIN["sha256"] != PREDECESSOR_PLUGIN["sha256"], "plugin identity mismatch")
    _require(_digest(CONTRACT.read_bytes()) == CONTRACT_SHA256, "Task 2 contract identity mismatch")
    _require(payload.get("task2_contract") == _binding(CONTRACT, relative=True), "Task 2 contract binding mismatch")
    predecessor = _authenticated_predecessor()
    _require(payload.get("predecessor_evaluation") == _binding(PREDECESSOR_EVALUATION, relative=True), "predecessor evaluation binding mismatch")
    _require(payload.get("predecessor_evaluation_self_sha256") == predecessor["sha256"], "predecessor identity mismatch")
    _require(payload.get("predecessor_normalized_artifact") == _binding(PREDECESSOR_OUTPUT, relative=True), "predecessor normalized artifact mismatch")
    expected_observation = {
        "decision": predecessor["decision"],
        "registered_blocker_counts": predecessor["complete"]["after"]["registered_blocker_counts"],
    }
    _require(payload.get("predecessor_observation") == expected_observation, "predecessor observation mismatch")
    contract = _load_object(CONTRACT, "Task 2 contract")
    _require(payload.get("model") == contract["model"], "model mismatch")
    _require(payload.get("task_1_through_3_identities") == contract["task_1_through_3_identities"], "Task 1--3 identities mismatch")
    _require(payload.get("provenance") == predecessor["provenance"], "provenance mismatch")
    _require(payload.get("source_revision") == _expected_source_revision(), "source revision mismatch")
    _require(payload.get("python") == _binding(Path(sys.executable).resolve()), "python binding mismatch")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    _require(_binding(flat_scf, relative=True) == {
        "path": contract["source"]["flat_scf"]["path"],
        "bytes": 18_933_168,
        "sha256": FLAT_SCF_SHA256,
    }, "input identity mismatch")
    _require(payload.get("input") == _binding(flat_scf, relative=True), "input identity mismatch")
    expected_specs = (*RUN_SPECS, ("complete-retained-c22-flat-scf", "complete", flat_scf, PIPELINE))
    runs = payload["executions"]
    _require(len(runs) == 5, "causal execution order mismatch")
    outputs: list[Path] = []
    generics: list[list[Path]] = []
    for sequence, (run, spec) in enumerate(zip(runs, expected_specs), start=1):
        output_path, generic_paths = _validate_run(run, spec=spec, sequence=sequence, replay=replay)
        outputs.append(output_path)
        generics.append(generic_paths)
    _require(all(run["exit_code"] == 0 and run["parseable"] for run in runs[:4]), "semantic probe execution failed")
    expected_probes = []
    for probe_index, probe_id in enumerate(("size1", "size64")):
        pass_index = probe_index * 2
        integrated_index = pass_index + 1
        before = generics[pass_index][0].read_text(encoding="utf-8")
        after = generics[pass_index][1].read_text(encoding="utf-8")
        proof = _independent_copy_proof(before, after, probe_id)
        pass_output = outputs[pass_index].read_text(encoding="utf-8")
        integrated_output = outputs[integrated_index].read_text(encoding="utf-8")
        checks = {
            "pass_exit_zero": runs[pass_index]["exit_code"] == 0,
            "pass_parseable": runs[pass_index]["parseable"],
            "integrated_exit_zero": runs[integrated_index]["exit_code"] == 0,
            "integrated_parseable": runs[integrated_index]["parseable"],
            "literal_loop_base_index_direction_and_liveness": proof == _literal_proof(probe_id),
            "pass_copy_eliminated": "memref.copy" not in pass_output,
            "integrated_copy_eliminated": "memref.copy" not in integrated_output,
        }
        expected_probes.append(
            {
                "id": probe_id,
                "pass_execution_id": runs[pass_index]["id"],
                "integrated_execution_id": runs[integrated_index]["id"],
                "invariant_status": "proven" if all(checks.values()) else "unproven",
                "proof": proof,
                "checks": checks,
            }
        )
    _require(payload["semantic_probes"] == expected_probes, "semantic probe mismatch")
    _require(all(item["invariant_status"] == "proven" for item in expected_probes), "semantic probe unproven")
    before_census = _operation_census(generics[-1][0].read_text(encoding="utf-8"))
    full_valid = runs[-1]["exit_code"] == 0 and runs[-1]["parseable"]
    if full_valid:
        after_census = _operation_census(generics[-1][1].read_text(encoding="utf-8"))
        after_counts: dict[str, int | None] = _registered(after_census)
        after_total: int | None = sum(after_counts.values())
        introduced = _new_classes(before_census, after_census)
    else:
        after_census = {}
        after_counts = {name: None for name in REGISTERED}
        after_total = None
        introduced = []
    before_counts = _registered(before_census)
    expected_contract_counts = {name: contract["classes"][name]["count"] for name in REGISTERED}
    _require(before_counts == expected_contract_counts, "before blocker census mismatch")
    expected_complete = {
        "parseable": runs[-1]["parseable"],
        "before": {
            "operation_census": before_census,
            "registered_blocker_counts": before_counts,
            "registered_operation_count": sum(before_counts.values()),
        },
        "after": {
            "operation_census": after_census,
            "registered_blocker_counts": after_counts,
            "registered_operation_count": after_total,
        },
        "after_only_operation_classes": introduced,
        "invariant_status": (
            "unavailable_due_invalid_output"
            if not full_valid
            else ("proven" if not introduced else "unproven")
        ),
    }
    _require(payload["complete"]["before"] == expected_complete["before"], "before blocker census mismatch")
    _require(payload["complete"]["after"]["operation_census"] == after_census, "after operation census mismatch")
    _require(payload["complete"]["after"] == expected_complete["after"], "after blocker census mismatch")
    _require(payload["complete"]["after_only_operation_classes"] == introduced, "after-only operation classes mismatch")
    _require(payload["complete"] == expected_complete, "complete census mismatch")
    semantic_status = "proven"
    zero = (
        full_valid
        and set(after_counts) == set(REGISTERED)
        and all(type(after_counts[name]) is int and after_counts[name] == 0 for name in REGISTERED)
        and not introduced
        and semantic_status == "proven"
    )
    _require(payload["zero_registered_blockers"] is zero, "zero blocker gate mismatch")
    if zero:
        _require(payload["decision"] == "zero_registered_blockers", "decision schema mismatch")
        _require(payload["normalized_artifact"] == runs[-1]["output"], "normalized artifact mismatch")
        expected_handoff = {
            "artifact": runs[-1]["output"],
            "next_plan": "separate-stage-registration-and-pre-calyx-legality",
            "stage_registration_authorized": False,
            "calyx_authorized": False,
        }
        _require(payload["handoff"]["stage_registration_authorized"] is False, "stage registration authorization mismatch")
        _require(payload["handoff"]["calyx_authorized"] is False, "Calyx authorization mismatch")
        _require(payload["handoff"] == expected_handoff, "handoff mismatch")
    elif full_valid and isinstance(after_total, int) and after_total > 0:
        _require(payload["decision"] == "residual_registered_blockers", "decision schema mismatch")
        _require(payload["normalized_artifact"] == runs[-1]["output"], "normalized artifact mismatch")
        # Fail closed: the claimed pair must at least name the first registered
        # source line and carry a nonempty defining chain.
        text = outputs[-1].read_text(encoding="utf-8")
        first = min(
            (
                (line_number, line.index(name) + 1, name)
                for line_number, line in enumerate(text.splitlines(), start=1)
                for name in REGISTERED
                if re.search(rf"\b{re.escape(name)}\b", line)
            ),
            default=None,
        )
        _require(first is not None, "earliest residual chain mismatch")
        pair = payload["next_pair"]
        _require(pair.get("blocker", {}).get("operation") == first[2], "earliest residual chain mismatch")
        _require(pair.get("blocker", {}).get("source_location", {}).get("line") == first[0], "earliest residual chain mismatch")
        _require(bool(pair.get("defining_chain")), "earliest residual chain mismatch")
    else:
        _require(payload["decision"] == "next_compiler_frontier", "decision schema mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, default=EVALUATION)
    parser.add_argument("--no-replay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = _load_object(args.evaluation, "Task 2 evaluation")
    validate_payload(payload, ROOT, replay=not args.no_replay)
    print("status: PASS")
    print(f"decision: {payload['decision']}")
    print(f"zero_registered_blockers: {str(payload['zero_registered_blockers']).lower()}")
    print("after: " + json.dumps(payload["complete"]["after"]["registered_blocker_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
