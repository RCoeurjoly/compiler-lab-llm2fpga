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
        constants = "    %c2 = arith.constant 2 : index\n    %c3 = arith.constant 3 : index\n"
        indices = "%c2, %c3"
        arguments = f"%source: {operands[0]}"
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
        + constants + operation
        + f"    %value = memref.load {base}[{indices}] : {access_type}\n"
        + f"    memref.store %value, {base}[{indices}] : {access_type}\n"
        + "    return %value : i64\n  }\n}\n"
    )


_INDEX_CONSTANT = re.compile(r"^\s*(%[A-Za-z0-9_.$-]+)\s*=\s*arith\.constant\s+(-?[0-9]+)\s*:\s*index\s*$")
_MEMORY_ACCESS = re.compile(
    r"^\s*(?:%[A-Za-z0-9_.$-]+\s*=\s*)?memref\.(load|store)\s+.*?"
    r"(%[A-Za-z0-9_.$-]+)\[([^]]+)\]\s*:\s*(memref<.+>)\s*$"
)


def _access_model(text: str, parser: Any) -> dict[str, Any]:
    constants = {
        matched.group(1): int(matched.group(2))
        for line in text.splitlines()
        if (matched := _INDEX_CONSTANT.match(line))
    }
    accesses, memrefs = [], []
    for line in text.splitlines():
        matched = _MEMORY_ACCESS.match(line)
        if not matched:
            continue
        memref = parser.parse_memref_type(matched.group(4))
        tokens = [token.strip() for token in matched.group(3).split(",")]
        _require(all(token in constants for token in tokens), "semantic probe access is not constant")
        indices = [constants[token] for token in tokens]
        _require(len(indices) == memref["rank"], "semantic probe access rank mismatch")
        linear = memref["offset"] + sum(
            index * stride for index, stride in zip(indices, memref["strides"])
        )
        accesses.append({"kind": matched.group(1), "linear_index": linear})
        memrefs.append(memref)
    _require(bool(accesses), "semantic probe has no live memory access")
    counts = [__import__("math").prod(memref["shape"]) for memref in memrefs]
    _require(len(set(counts)) == 1, "semantic probe element-count mismatch")
    shape, strides = memrefs[0]["shape"], memrefs[0]["strides"]
    expected_stride, contiguous = 1, True
    for dimension, stride in reversed(list(zip(shape, strides))):
        contiguous = contiguous and stride == expected_stride
        expected_stride *= dimension
    return {
        "shape": memrefs[0]["shape"], "strides": memrefs[0]["strides"],
        "offset": memrefs[0]["offset"], "contiguous": contiguous,
        "element_count": counts[0],
        "access_maps": accesses,
    }


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
    _require(set(binding) >= {"path", "bytes", "sha256"}, f"{label} binding incomplete")
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


def _check_command(run: dict[str, Any], input_path: Path, output_path: Path) -> None:
    expected = [
        TOOL["path"], str(input_path), f"--load-pass-plugin={PLUGIN['path']}",
        f"--pass-pipeline={PIPELINE}", "-o", str(output_path),
    ]
    _require(run.get("command") == expected, "exact pass command mismatch")
    command_text = " ".join(expected).lower().replace("for-calyx", "")
    _require("calyx" not in command_text, "Calyx invocation is forbidden")
    _require("circt-opt" not in command_text, "Calyx invocation is forbidden")


def _replay(run: dict[str, Any], input_path: Path) -> None:
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
        _require(completed.stdout == (ROOT / run["stdout"]["path"]).read_bytes(), "replay stdout mismatch")
        _require(completed.stderr == (ROOT / run["stderr"]["path"]).read_bytes(), "replay stderr mismatch")
        replay_output = output.read_bytes() if output.exists() else b""
        _require(replay_output == (ROOT / run["output"]["path"]).read_bytes(), "replay output mismatch")


def validate_payload(payload: dict[str, Any], root: Path = ROOT, *, replay: bool) -> None:
    _require(root.resolve() == ROOT.resolve(), "verification root mismatch")
    _require(payload.get("schema") == "tinystories-1m-exact-memref-pass-v1", "schema mismatch")
    unsigned = copy.deepcopy(payload)
    unsigned["sha256"] = None
    _require(payload.get("sha256") == _digest(_canonical(unsigned)), "evaluation self-hash mismatch")
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
    trusted_python = Path(sys.executable).resolve()
    _require(
        payload.get("python") == _binding(trusted_python),
        "python interpreter binding mismatch",
    )
    for name in REGISTERED:
        slug = "semantic-" + name.replace(".", "-").replace("_", "-")
        path = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evidence" / slug / "input.mlir"
        _require(path.is_file(), f"semantic probe input unavailable for {name}")
        _require(
            path.read_text(encoding="utf-8") == _expected_probe_text(contract, name),
            f"semantic probe input mismatch for {name}",
        )
        expected_inputs.append(path)
    expected_inputs.append(flat_scf)

    for index, run in enumerate(runs):
        expected_input = expected_inputs[index]
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
        output_path = _check_binding(run.get("output"), f"{run.get('id')} output")
        _check_binding(run.get("stdout"), f"{run.get('id')} stdout")
        _check_binding(run.get("stderr"), f"{run.get('id')} stderr")
        _check_binding(run.get("parse_check", {}).get("stdout"), f"{run.get('id')} parse stdout")
        _check_binding(run.get("parse_check", {}).get("stderr"), f"{run.get('id')} parse stderr")
        _require(run.get("parse_check", {}).get("exit_code") == 0, "parse exit mismatch")
        _check_command(run, expected_input, output_path)
        parse_command = [TOOL["path"], str(output_path), "-o", "/dev/null"]
        _require(run["parse_check"].get("command") == parse_command, "parse command mismatch")
        parsed = subprocess.run(
            parse_command,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        _require(parsed.returncode == run["parse_check"]["exit_code"], "parse exit mismatch")
        _require(parsed.stdout == (ROOT / run["parse_check"]["stdout"]["path"]).read_bytes(), "parse stdout mismatch")
        _require(parsed.stderr == (ROOT / run["parse_check"]["stderr"]["path"]).read_bytes(), "parse stderr mismatch")

    representatives = payload.get("representatives")
    _require(
        isinstance(representatives, list) and len(representatives) == 4,
        "representative result set mismatch",
    )
    for index, result in enumerate(representatives):
        name = REGISTERED[index]
        input_path = ROOT / contract["classes"][name]["representative"]["path"]
        input_text = input_path.read_text(encoding="utf-8")
        output_text_rep = (ROOT / runs[index]["output"]["path"]).read_text(
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
        probe_text = _expected_probe_text(contract, name)
        before_model = _access_model(probe_text, parser)
        after_model = _access_model(
            (ROOT / runs[index + 4]["output"]["path"]).read_text(encoding="utf-8"),
            parser,
        )
        shape_element_count_preserved = (
            before_model["element_count"] == after_model["element_count"]
        )
        layout_preserved = (
            before_model["contiguous"] and after_model["contiguous"]
            and before_model["offset"] == after_model["offset"]
        )
        access_maps_preserved = (
            before_model["access_maps"] == after_model["access_maps"]
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
                "shape_layout_access_equivalent": proven,
            },
        }
        _require(semantic_probes[index] == expected_probe, "semantic probe mismatch")

    complete = payload.get("complete", {})
    _require(complete.get("unknown_blocker_classes") == [], "unknown blocker classes present")
    full_parseable = runs[-1]["parseable"]
    output_text = (
        (ROOT / runs[-1]["output"]["path"]).read_text(encoding="utf-8")
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
                (ROOT / runs[-1]["stderr"]["path"]).read_bytes(),
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
            _replay(run, expected_inputs[index])
    _require(payload.get("decision") == decision, "decision gate mismatch")
    if decision == "register_existing_pass":
        _require(payload.get("normalized_artifact") == runs[-1]["output"], "normalized artifact identity mismatch")
        _require("earliest_remaining_signature" not in payload, "unexpected extension reproducer")
    else:
        earliest = payload.get("earliest_remaining_signature", {})
        _require(earliest.get("operation") == invalid[0]["operation"], "earliest remaining signature missing")
        reproducer = _check_binding(earliest.get("reproducer"), "earliest remaining reproducer")
        lines = reproducer.read_text(encoding="utf-8").splitlines()
        subviews = [line for line in lines if "memref.subview" in line]
        _require(len(subviews) == 1, "earliest remaining reproducer is not exact")
        _require(earliest.get("reproducer", {}).get("operation_count") == 1, "earliest remaining reproducer count mismatch")
        metadata_path = _check_binding(earliest["reproducer"].get("metadata"), "earliest remaining metadata")
        metadata = _load_object(metadata_path, "earliest remaining metadata")
        _require(metadata.get("signature_sha256") == earliest.get("signature_sha256"), "earliest remaining signature mismatch")
        execution = metadata.get("execution", {})
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
