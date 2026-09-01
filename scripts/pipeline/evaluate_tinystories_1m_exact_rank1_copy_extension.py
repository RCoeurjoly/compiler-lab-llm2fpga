#!/usr/bin/env python3
"""Replay the exact direct rank-one copy extension and close its blocker gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
PREDECESSOR_EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json"
PREDECESSOR_OUTPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/complete-retained-c22-flat-scf/output.mlir"
DEFAULT_OUTPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evaluation.json"
DEFAULT_EVIDENCE = ROOT / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence"
DEFAULT_REPORT = ROOT / "docs/results/2026-09-01-tinystories-1m-rank1-copy-extension-evaluation.md"
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
TASK1_COMMIT = ASSIGNED_BASE
PASS_SOURCE_BLOB = "3c570a72637686161b27d5d78474aef34eea5697"
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
PROBE_IDENTITIES = {
    "size1": {"bytes": 444, "sha256": "e7f0a9d9d1b7bbb1b9a26e6b180e2db00fc47c6452a1a0fa1116b62d87fce730"},
    "size64": {"bytes": 455, "sha256": "4500229e430254508d22d4ff24ab276f57bbccb16e6baf865e293b0427caf026"},
}
PROBE_SPECS = {
    "size1": {"path": SIZE1, "extent": 1, "live_index": 0},
    "size64": {"path": SIZE64, "extent": 64, "live_index": 63},
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
        raise ValueError(
            f"cannot authenticate Git object {commit}:{relative}: "
            + completed.stderr.decode(errors="replace").strip()
        )
    return completed.stdout


def authenticate_predecessor_receipt() -> dict[str, Any]:
    receipt = file_binding(PREDECESSOR_EVALUATION, relative=True)
    expected_receipt = {
        "path": "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json",
        "bytes": 40_418,
        "sha256": PREDECESSOR_EVALUATION_SHA256,
    }
    if receipt != expected_receipt:
        raise ValueError("predecessor evaluation identity mismatch")
    relative_receipt = expected_receipt["path"]
    if _git_bytes(PREDECESSOR_COMMIT, relative_receipt) != PREDECESSOR_EVALUATION.read_bytes():
        raise ValueError("predecessor evaluation historical Git binding mismatch")
    payload = load_json(PREDECESSOR_EVALUATION, "predecessor evaluation")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    if (
        payload.get("sha256") != PREDECESSOR_SELF_SHA256
        or sha256_bytes(canonical_json(unsigned)) != PREDECESSOR_SELF_SHA256
    ):
        raise ValueError("predecessor evaluation self hash mismatch")
    normalized = file_binding(PREDECESSOR_OUTPUT, relative=True)
    expected_output = {
        "path": "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/complete-retained-c22-flat-scf/output.mlir",
        "bytes": 15_196_673,
        "sha256": PREDECESSOR_OUTPUT_SHA256,
    }
    if normalized != expected_output:
        raise ValueError("predecessor normalized artifact identity mismatch")
    if _git_bytes(PREDECESSOR_COMMIT, expected_output["path"]) != PREDECESSOR_OUTPUT.read_bytes():
        raise ValueError("predecessor output historical Git binding mismatch")
    exact = {
        "schema": "tinystories-1m-exact-unit-collapse-extension-v1",
        "status": "evaluated",
        "model": "tiny-stories-1m-kev-gpt-exact",
        "pipeline": PIPELINE,
        "decision": "valid_normalized_output",
    }
    if any(payload.get(key) != value for key, value in exact.items()):
        raise ValueError("predecessor semantic identity mismatch")
    if payload.get("normalized_artifact") != normalized:
        raise ValueError("predecessor normalized artifact binding mismatch")
    if payload.get("plugin") != PREDECESSOR_PLUGIN:
        raise ValueError("predecessor plugin identity mismatch")
    if payload.get("tool") != TOOL:
        raise ValueError("predecessor tool identity mismatch")
    if payload.get("input", {}).get("sha256") != FLAT_SCF_SHA256:
        raise ValueError("predecessor c22 input identity mismatch")
    if payload.get("complete", {}).get("after", {}).get("registered_blocker_counts") != {
        "memref.collapse_shape": 0,
        "memref.copy": 1022,
        "memref.expand_shape": 0,
        "memref.reinterpret_cast": 0,
    }:
        raise ValueError("predecessor residual census mismatch")
    return {
        **receipt,
        "self_sha256": payload["sha256"],
        "normalized_artifact": normalized,
        "plugin": copy.deepcopy(payload["plugin"]),
        "payload": payload,
    }


def require_binding(path: Path, expected: dict[str, Any], label: str) -> None:
    if not path.is_file() or file_binding(path) != expected:
        raise ValueError(f"{label} identity mismatch")


def apply_zero_blocker_gate(
    *,
    pass_exit_zero: bool,
    parseable: bool,
    blocker_counts: dict[str, int | None],
    after_only_classes: list[str],
    semantic_status: str,
) -> bool:
    return (
        pass_exit_zero
        and parseable
        and set(blocker_counts) == set(REGISTERED)
        and all(type(blocker_counts[name]) is int and blocker_counts[name] == 0 for name in REGISTERED)
        and not after_only_classes
        and semantic_status == "proven"
    )


_GENERIC_OPERATION = re.compile(r'"((?:[^"\\]|\\.)+)"\s*\(')


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


def operation_census(generic_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _GENERIC_OPERATION.finditer(generic_text):
        name = _decode_mlir_name(match.group(1))
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def after_only_classes(before: dict[str, int], after: dict[str, int]) -> list[str]:
    return sorted(set(after) - set(before))


def _registered_counts(census: dict[str, int]) -> dict[str, int]:
    return {name: census.get(name, 0) for name in REGISTERED}


def _generic_print(*, subject: str, input_path: Path, output_dir: Path) -> dict[str, Any]:
    output_path = output_dir / f"{subject}.generic.mlir"
    stdout_path = output_dir / f"{subject}.generic.stdout.bin"
    stderr_path = output_dir / f"{subject}.generic.stderr.bin"
    command = [TOOL["path"], str(input_path), "-mlir-print-op-generic", "-o", str(output_path)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    if not output_path.is_file():
        output_path.write_bytes(b"")
    return {
        "subject": subject,
        "command": command,
        "exit_code": completed.returncode,
        "input": file_binding(input_path, relative=True),
        "stdout": file_binding(stdout_path, relative=True),
        "stderr": file_binding(stderr_path, relative=True),
        "output": file_binding(output_path, relative=True),
    }


def run_pass(
    *,
    sequence: int,
    identifier: str,
    kind: str,
    input_path: Path,
    output_dir: Path,
    pipeline: str,
    causal_preconditions_satisfied: bool,
) -> dict[str, Any]:
    if not causal_preconditions_satisfied:
        raise ValueError(f"causal preconditions failed before {identifier}")
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "output.mlir"
    stdout_path = output_dir / "stdout.bin"
    stderr_path = output_dir / "stderr.bin"
    parse_stdout_path = output_dir / "parse.stdout.bin"
    parse_stderr_path = output_dir / "parse.stderr.bin"
    before = file_binding(input_path, relative=True)
    input_generic = _generic_print(subject="input", input_path=input_path, output_dir=output_dir)
    command = [
        TOOL["path"],
        str(input_path),
        f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={pipeline}",
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
    output_generic = _generic_print(subject="output", input_path=output_path, output_dir=output_dir)
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
        "generic_prints": [input_generic, output_generic],
    }


def _affine_expressions(generic_text: str, induction: str) -> dict[str, tuple[int, int]]:
    expressions: dict[str, tuple[int, int]] = {induction: (0, 1)}
    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) <\{value = (-?[0-9]+) : index\}>'
    )
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.(addi|muli)"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    for line in generic_text.splitlines():
        if match := constant.match(line):
            expressions[match.group(1)] = (int(match.group(2)), 0)
            continue
        if match := binary.match(line):
            result, operation, left_name, right_name = match.groups()
            if left_name not in expressions or right_name not in expressions:
                continue
            left = expressions[left_name]
            right = expressions[right_name]
            if operation == "addi":
                expressions[result] = (left[0] + right[0], left[1] + right[1])
            elif left[1] == 0:
                expressions[result] = (right[0] * left[0], right[1] * left[0])
            elif right[1] == 0:
                expressions[result] = (left[0] * right[0], left[1] * right[0])
            else:
                raise ValueError("copy proof encountered non-affine multiplication")
    return expressions


def derive_copy_semantics(before_generic: str, after_generic: str, probe_id: str) -> dict[str, Any]:
    spec = PROBE_SPECS[probe_id]
    extent = spec["extent"]
    live_index = spec["live_index"]
    before_allocs = re.findall(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.alloc"\(', before_generic, re.MULTILINE
    )
    after_allocs = re.findall(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.alloc"\(', after_generic, re.MULTILINE
    )
    if len(before_allocs) != 2 or len(after_allocs) != 2:
        raise ValueError("copy proof requires exactly two allocations")
    copy_match = re.search(
        r'"memref\.copy"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)', before_generic
    )
    if copy_match is None or list(copy_match.groups()) != before_allocs:
        raise ValueError("copy proof source/target direction mismatch in input")
    constants = {
        name: int(value)
        for name, value in re.findall(
            r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) <\{value = (-?[0-9]+) : index\}>',
            after_generic,
            re.MULTILINE,
        )
    }
    loops = re.findall(
        r'"scf\.for"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\) \(\{\s*\^bb[0-9]+\((%[A-Za-z0-9_]+): index\)',
        after_generic,
        re.DOTALL,
    )
    if len(loops) != 1:
        raise ValueError("copy proof requires exactly one loop")
    lower, upper, step, induction = loops[0]
    if any(name not in constants for name in (lower, upper, step)):
        raise ValueError("copy loop bounds are not literal")
    expressions = _affine_expressions(after_generic, induction)
    load_pattern = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "memref\.load"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)',
        re.MULTILINE,
    )
    store_pattern = re.compile(
        r'^\s*"memref\.store"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)',
        re.MULTILINE,
    )
    loads = list(load_pattern.finditer(after_generic))
    stores = list(store_pattern.finditer(after_generic))
    copy_loads = [match for match in loads if expressions.get(match.group(3), (0, 0))[1] != 0]
    copy_stores = [match for match in stores if expressions.get(match.group(3), (0, 0))[1] != 0]
    live_loads = [match for match in loads if expressions.get(match.group(3), (0, 0))[1] == 0]
    live_stores = [match for match in stores if expressions.get(match.group(3), (0, 0))[1] == 0]
    if not (len(copy_loads) == len(copy_stores) == len(live_loads) == len(live_stores) == 1):
        raise ValueError("copy proof access cardinality mismatch")
    copy_load = copy_loads[0]
    copy_store = copy_stores[0]
    live_load = live_loads[0]
    live_store = live_stores[0]
    if copy_store.group(1) != copy_load.group(1):
        raise ValueError("source load does not feed target store")
    returned = re.search(r'"func\.return"\((%[A-Za-z0-9_]+)\)', after_generic)
    if returned is None:
        raise ValueError("copy proof return is absent")
    allocation_index = {name: index for index, name in enumerate(after_allocs)}
    live_store_index = expressions.get(live_store.group(3))
    live_load_index = expressions.get(live_load.group(3))
    load_formula = expressions.get(copy_load.group(3))
    store_formula = expressions.get(copy_store.group(3))
    if None in (live_store_index, live_load_index, load_formula, store_formula):
        raise ValueError("copy proof contains unresolved index")
    return {
        "extent": extent,
        "live_index": live_index,
        "distinct_bases": after_allocs[0] != after_allocs[1],
        "source_allocation": allocation_index.get(copy_load.group(2)),
        "target_allocation": allocation_index.get(copy_store.group(2)),
        "loop_domain": {
            "lower": constants[lower],
            "upper_exclusive": constants[upper],
            "step": constants[step],
        },
        "copy_accesses": [
            {
                "kind": "load",
                "role": "source",
                "allocation": allocation_index.get(copy_load.group(2)),
                "offset": load_formula[0],
                "coefficient": load_formula[1],
            },
            {
                "kind": "store",
                "role": "target",
                "allocation": allocation_index.get(copy_store.group(2)),
                "offset": store_formula[0],
                "coefficient": store_formula[1],
            },
        ],
        "live_flow": {
            "input_argument": 0 if live_store.group(1) == "%arg0" else None,
            "source_store_index": live_store_index[0]
            if live_store_index[1] == 0 and allocation_index.get(live_store.group(2)) == 0
            else None,
            "target_load_index": live_load_index[0]
            if live_load_index[1] == 0 and allocation_index.get(live_load.group(2)) == 1
            else None,
            "returned_target_observation": returned.group(1) == live_load.group(1),
        },
    }


def _proof_matches_literal(proof: dict[str, Any], probe_id: str) -> bool:
    spec = PROBE_SPECS[probe_id]
    return proof == {
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


_ALLOC = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*(memref\.alloc)\(")
_VIEW = re.compile(
    r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*"
    r"(memref\.(?:subview|collapse_shape|expand_shape|reinterpret_cast))\s+"
    r"(%[A-Za-z0-9_.$-]+)"
)


def derive_earliest_residual_pair(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    blockers: list[tuple[int, int, str, str]] = []
    definitions: dict[str, dict[str, Any]] = {}
    function: str | None = None
    for line_number, line in enumerate(lines, start=1):
        if match := re.match(r"^\s*func\.func\s+@([A-Za-z0-9_.$-]+)", line):
            function = match.group(1)
        operation = next((name for name in REGISTERED if re.search(rf"\b{re.escape(name)}\b", line)), None)
        if operation:
            blockers.append((line_number, line.index(operation) + 1, operation, line.strip()))
        match = _VIEW.match(line)
        alloc = _ALLOC.match(line)
        if match is None and alloc is None:
            continue
        selected = match or alloc
        result, op = selected.group(1), selected.group(2)
        definitions[result] = {
            "operation": op,
            "result_ssa": result,
            "source_ssa": match.group(3) if match is not None else None,
            "source_location": {
                "function": function,
                "line": line_number,
                "column": line.index(op) + 1,
                "mlir": line.strip(),
            },
        }
    if not blockers:
        raise ValueError("no residual registered blocker")
    line_number, column, operation, mlir = min(blockers)
    operands = re.findall(r"%[A-Za-z0-9_.$-]+", mlir)
    if "=" in mlir and operands:
        operands = operands[1:]
    chain: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        definition = definitions.get(name)
        if definition is None or name in visited:
            return
        if definition["source_ssa"]:
            visit(definition["source_ssa"])
        visited.add(name)
        chain.append(copy.deepcopy(definition))

    for operand in operands:
        visit(operand)
    blocker = {
        "operation": operation,
        "source_location": {
            "function": function,
            "line": line_number,
            "column": column,
            "mlir": mlir,
        },
        "signature_sha256": sha256_bytes(mlir.encode()),
    }
    base = {"blocker": blocker, "defining_chain": chain}
    return {
        "kind": "earliest_residual_defining_chain",
        **base,
        "pair_signature_sha256": sha256_bytes(canonical_json(base)),
    }


def _source_revision() -> dict[str, Any]:
    relative = str(PASS_SOURCE.relative_to(ROOT))
    assigned = _git_bytes(ASSIGNED_BASE, relative)
    live = PASS_SOURCE.read_bytes()
    if assigned != live:
        raise ValueError("Task 1 pass source differs from assigned base")
    completed = subprocess.run(
        ["git", "rev-parse", f"{ASSIGNED_BASE}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode or completed.stdout.strip() != PASS_SOURCE_BLOB:
        raise ValueError("Task 1 pass source blob identity mismatch")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ASSIGNED_BASE, "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestor.returncode:
        raise ValueError("assigned Task 1 base is not an ancestor of HEAD")
    return {
        "assigned_base": ASSIGNED_BASE,
        "task1_commit": TASK1_COMMIT,
        "pass_source_blob": PASS_SOURCE_BLOB,
        "pass_source": file_binding(PASS_SOURCE, relative=True),
    }


def _report(payload: dict[str, Any]) -> str:
    counts = payload["complete"]["after"]["registered_blocker_counts"]
    rows = "\n".join(
        f"| `{name}` | {payload['complete']['before']['registered_blocker_counts'][name]:,} | {counts[name]:,} |"
        for name in REGISTERED
    )
    probes = "\n".join(
        f"| `{probe['id']}` | `{probe['invariant_status']}` | `[0,{probe['proof']['extent']})` | source alloc 0 -> target alloc 1 at `i` | live index {probe['proof']['live_index']} |"
        for probe in payload["semantic_probes"]
    )
    handoff = payload.get("handoff")
    next_text = (
        "The exact artifact is bound for a separate stage-registration and pre-Calyx legality plan. "
        "This task authorizes neither action and did not invoke Calyx."
        if handoff
        else "The earliest residual defining chain is bound in the receipt for the next bounded compiler plan."
    )
    return f"""# Exact TinyStories-1M direct rank-one copy extension evaluation

The size-1 and size-64 live copy probes were replayed first at the pass boundary and through the exact integrated normalization pipeline. Only after both semantic proofs succeeded was the immutable 18,933,168-byte c22 artifact replayed. No Nix stage was registered and no Calyx command ran.

## Decision

- `zero_registered_blockers: {str(payload['zero_registered_blockers']).lower()}`
- Decision: `{payload['decision']}`
- Exact normalized artifact: `{payload.get('normalized_artifact', {}).get('path', 'none')}`
- Artifact SHA-256: `{payload.get('normalized_artifact', {}).get('sha256', 'none')}`

## Semantic probes

| Probe | Status | Loop domain | Direction/index | Live observation |
| --- | --- | --- | --- | --- |
{probes}

## Complete registered blocker census

| Registered class | Before | After |
| --- | ---: | ---: |
{rows}

- Pass exit: `{payload['executions'][-1]['exit_code']}`
- Parse exit: `{payload['executions'][-1]['parse_check']['exit_code']}`
- After-only operation classes: `{len(payload['complete']['after_only_operation_classes'])}`
- Complete input/output generic operation censuses are retained and independently replayable.

## Handoff boundary

{next_text}
"""


def evaluate(*, output: Path, evidence_root: Path, report: Path) -> dict[str, Any]:
    contract = load_json(CONTRACT, "Task 2 contract")
    if file_binding(CONTRACT, relative=True)["sha256"] != CONTRACT_SHA256:
        raise ValueError("Task 2 contract SHA-256 mismatch")
    predecessor = authenticate_predecessor_receipt()
    require_binding(Path(TOOL["path"]), TOOL, "pinned mlir-opt")
    require_binding(Path(PREDECESSOR_PLUGIN["path"]), PREDECESSOR_PLUGIN, "predecessor plugin")
    require_binding(Path(PLUGIN["path"]), PLUGIN, "Task 1 plugin")
    if PREDECESSOR_PLUGIN["sha256"] == PLUGIN["sha256"]:
        raise ValueError("Task 1 plugin does not differ from predecessor")
    for probe_id, spec in PROBE_SPECS.items():
        expected = {"path": str(spec["path"]), **PROBE_IDENTITIES[probe_id]}
        require_binding(spec["path"], expected, f"{probe_id} fixture")
    flat_scf = ROOT / contract["source"]["flat_scf"]["path"]
    expected_input = {
        "path": str(flat_scf),
        "bytes": 18_933_168,
        "sha256": FLAT_SCF_SHA256,
    }
    require_binding(flat_scf, expected_input, "immutable c22 input")
    source_revision = _source_revision()
    if evidence_root.exists():
        shutil.rmtree(evidence_root)
    evidence_root.mkdir(parents=True)
    runs: list[dict[str, Any]] = []
    causal = True
    sequence = 1
    probe_run_pairs: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for probe_id, spec in PROBE_SPECS.items():
        pass_run = run_pass(
            sequence=sequence,
            identifier=f"semantic-{probe_id}-pass-only",
            kind="semantic_probe_pass_only",
            input_path=spec["path"],
            output_dir=evidence_root / f"semantic-{probe_id}-pass-only",
            pipeline=PROBE_PIPELINE,
            causal_preconditions_satisfied=causal,
        )
        runs.append(pass_run)
        sequence += 1
        causal = causal and pass_run["exit_code"] == 0 and pass_run["parseable"]
        integrated = run_pass(
            sequence=sequence,
            identifier=f"semantic-{probe_id}-integrated",
            kind="semantic_probe_integrated",
            input_path=spec["path"],
            output_dir=evidence_root / f"semantic-{probe_id}-integrated",
            pipeline=PIPELINE,
            causal_preconditions_satisfied=causal,
        )
        runs.append(integrated)
        sequence += 1
        causal = causal and integrated["exit_code"] == 0 and integrated["parseable"]
        probe_run_pairs[probe_id] = (pass_run, integrated)
    semantic_probes = []
    for probe_id, (pass_run, integrated) in probe_run_pairs.items():
        before_path = ROOT / pass_run["generic_prints"][0]["output"]["path"]
        after_path = ROOT / pass_run["generic_prints"][1]["output"]["path"]
        proof = derive_copy_semantics(
            before_path.read_text(encoding="utf-8"),
            after_path.read_text(encoding="utf-8"),
            probe_id,
        )
        pass_output = (ROOT / pass_run["output"]["path"]).read_text(encoding="utf-8")
        integrated_output = (ROOT / integrated["output"]["path"]).read_text(encoding="utf-8")
        checks = {
            "pass_exit_zero": pass_run["exit_code"] == 0,
            "pass_parseable": pass_run["parseable"],
            "integrated_exit_zero": integrated["exit_code"] == 0,
            "integrated_parseable": integrated["parseable"],
            "literal_loop_base_index_direction_and_liveness": _proof_matches_literal(proof, probe_id),
            "pass_copy_eliminated": "memref.copy" not in pass_output,
            "integrated_copy_eliminated": "memref.copy" not in integrated_output,
        }
        status = "proven" if all(checks.values()) else "unproven"
        semantic_probes.append(
            {
                "id": probe_id,
                "pass_execution_id": pass_run["id"],
                "integrated_execution_id": integrated["id"],
                "invariant_status": status,
                "proof": proof,
                "checks": checks,
            }
        )
        causal = causal and status == "proven"
    full_run = run_pass(
        sequence=sequence,
        identifier="complete-retained-c22-flat-scf",
        kind="complete",
        input_path=flat_scf,
        output_dir=evidence_root / "complete-retained-c22-flat-scf",
        pipeline=PIPELINE,
        causal_preconditions_satisfied=causal,
    )
    runs.append(full_run)
    before_generic = ROOT / full_run["generic_prints"][0]["output"]["path"]
    before_census = operation_census(before_generic.read_text(encoding="utf-8"))
    full_valid = full_run["exit_code"] == 0 and full_run["parseable"]
    if full_valid:
        after_generic = ROOT / full_run["generic_prints"][1]["output"]["path"]
        after_census = operation_census(after_generic.read_text(encoding="utf-8"))
        after_counts: dict[str, int | None] = _registered_counts(after_census)
        after_total: int | None = sum(after_counts.values())
        introduced = after_only_classes(before_census, after_census)
    else:
        after_census = {}
        after_counts = {name: None for name in REGISTERED}
        after_total = None
        introduced = []
    semantic_status = (
        "proven"
        if all(probe["invariant_status"] == "proven" for probe in semantic_probes)
        else "unproven"
    )
    complete = {
        "parseable": full_run["parseable"],
        "before": {
            "operation_census": before_census,
            "registered_blocker_counts": _registered_counts(before_census),
            "registered_operation_count": sum(_registered_counts(before_census).values()),
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
            else ("proven" if not introduced and semantic_status == "proven" else "unproven")
        ),
    }
    zero = apply_zero_blocker_gate(
        pass_exit_zero=full_run["exit_code"] == 0,
        parseable=full_run["parseable"],
        blocker_counts=after_counts,
        after_only_classes=introduced,
        semantic_status=semantic_status,
    )
    payload: dict[str, Any] = {
        "schema": "tinystories-1m-exact-rank1-copy-extension-v1",
        "status": "evaluated",
        "model": contract["model"],
        "task_1_through_3_identities": contract["task_1_through_3_identities"],
        "task2_contract": file_binding(CONTRACT, relative=True),
        "predecessor_evaluation": {
            key: predecessor[key] for key in ("path", "bytes", "sha256")
        },
        "predecessor_evaluation_self_sha256": predecessor["self_sha256"],
        "predecessor_normalized_artifact": predecessor["normalized_artifact"],
        "predecessor_plugin": PREDECESSOR_PLUGIN,
        "predecessor_observation": {
            "decision": predecessor["payload"]["decision"],
            "registered_blocker_counts": predecessor["payload"]["complete"]["after"]["registered_blocker_counts"],
        },
        "input": file_binding(flat_scf, relative=True),
        "tool": TOOL,
        "plugin": PLUGIN,
        "python": file_binding(Path(sys.executable).resolve()),
        "source_revision": source_revision,
        "pipeline": PIPELINE,
        "probe_pipeline": PROBE_PIPELINE,
        "provenance": predecessor["payload"]["provenance"],
        "executions": runs,
        "semantic_probes": semantic_probes,
        "complete": complete,
        "zero_registered_blockers": zero,
        "sha256": None,
    }
    if zero:
        payload["decision"] = "zero_registered_blockers"
        payload["normalized_artifact"] = full_run["output"]
        payload["handoff"] = {
            "artifact": full_run["output"],
            "next_plan": "separate-stage-registration-and-pre-calyx-legality",
            "stage_registration_authorized": False,
            "calyx_authorized": False,
        }
    elif full_valid and isinstance(after_total, int) and after_total > 0:
        payload["decision"] = "residual_registered_blockers"
        payload["normalized_artifact"] = full_run["output"]
        payload["next_pair"] = derive_earliest_residual_pair(
            (ROOT / full_run["output"]["path"]).read_text(encoding="utf-8")
        )
    else:
        payload["decision"] = "next_compiler_frontier"
        stderr = (ROOT / full_run["stderr"]["path"]).read_text(
            encoding="utf-8", errors="replace"
        )
        first = re.search(r":([0-9]+):([0-9]+): error: ([^\n]+)", stderr)
        payload["next_frontier"] = {
            "kind": "diagnostic" if not full_valid else "after_only_operation_class",
            "source_location": (
                {"line": int(first.group(1)), "column": int(first.group(2))}
                if first
                else None
            ),
            "diagnostic": first.group(3) if first else None,
            "after_only_operation_classes": introduced,
        }
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
                "status": payload["status"],
                "decision": payload["decision"],
                "zero_registered_blockers": payload["zero_registered_blockers"],
                "after": payload["complete"]["after"]["registered_blocker_counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
