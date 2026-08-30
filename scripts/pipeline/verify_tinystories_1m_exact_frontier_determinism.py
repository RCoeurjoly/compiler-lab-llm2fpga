#!/usr/bin/env python3
"""Verify the two preserved live Task 5 determinism evidence bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shlex
import stat
import subprocess
from typing import Any


_MODEL = "tiny-stories-1m-kev-gpt-exact"
_STAGES = ["pytorch-exported", "torch", "linalg", "scf"]
_NOT_RUN = ["flat-scf", "calyx", "calyx-native-sv"]
_DIAGNOSTIC = (
    "error: registered scf stage status is 'unavailable': "
    "baseline hardware pipeline lowers through CF and Handshake"
)
_SCF_MANIFEST = {
    "reason": "baseline hardware pipeline lowers through CF and Handshake",
    "stage": "scf",
    "status": "unavailable",
}
_CLASSIFIER = "scripts/pipeline/classify_tinystories_1m_exact_frontier.py"
_VERIFIER = "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py"
_SEMANTIC_VERIFIER = "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
_SEMANTIC_REPORT = "artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json"
_DECISION = "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"
_PREDECESSOR = (
    "artifacts/comparison/tinystories-1m-exact-frontier-determinism/run-1/receipt.json"
)
_FROZEN_IDENTITIES = {
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
_DECISION_SELF_SHA256 = "429da5a367755d35bc38308589beaf25d291a8272ebf4d8944bfa4b8919ef8fe"
_PREDECESSOR_FILE_SHA256 = "b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55"
_PREDECESSOR_SELF_SHA256 = "af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b"
_V1_CANONICAL_FILES = (
    "receipt.json",
    "pytorch-exported-build.log",
    "torch-mlir.log",
    "compiler-import-capture.log",
)
_V2_LEGACY_CANONICAL_FILES = (
    "receipt.json",
    "pytorch-exported.log",
    "torch.log",
    "linalg.log",
    "scf.log",
    "full-input.gz",
    "minimal-reproducer.json",
)
_V2_CURRENT_CANONICAL_FILES = (
    *_V2_LEGACY_CANONICAL_FILES,
    "linalg.drv",
    "linalg.derivation.json",
    "scf.drv",
    "scf.derivation.json",
)
_RUN_METADATA_FILES: frozenset[str] = frozenset()
_LEGACY_V3_SOURCE_COMMIT = "aec02920481bf9fc4650062f74191fde4943ce3a"


class VerificationError(RuntimeError):
    """Raised when preserved determinism evidence is incomplete or inconsistent."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _canonical_receipt_hash(receipt: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load JSON evidence {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"JSON evidence must be an object: {path}")
    return value


def _enumerate_run_files(run_root: Path, run_name: str) -> set[str]:
    """Enumerate one run without following links and reject non-regular entries."""

    try:
        root_mode = run_root.lstat().st_mode
    except OSError as error:
        raise VerificationError(f"missing preserved run directory: {run_name}") from error
    _require(
        stat.S_ISDIR(root_mode) and not run_root.is_symlink(),
        f"{run_name}: run root must be a real directory",
    )
    actual_files: set[str] = set()
    try:
        entries = list(run_root.iterdir())
    except OSError as error:
        raise VerificationError(f"{run_name}: cannot enumerate run directory: {error}") from error
    for entry in entries:
        try:
            mode = entry.lstat().st_mode
        except OSError as error:
            raise VerificationError(f"{run_name}: cannot inspect {entry.name}: {error}") from error
        _require(
            not stat.S_ISLNK(mode) and stat.S_ISREG(mode),
            f"{run_name}: run directory contents must be regular files: {entry.name}",
        )
        actual_files.add(entry.name)
    return actual_files


def _verify_run_directory(
    run_root: Path, run_name: str, canonical_files: tuple[str, ...]
) -> None:
    """Enforce one run's exact schema-defined regular-file set."""

    actual_files = _enumerate_run_files(run_root, run_name)
    expected_files = set(canonical_files) | _RUN_METADATA_FILES
    _require(
        actual_files == expected_files,
        f"{run_name}: run directory contents mismatch: "
        f"expected {sorted(expected_files)}, found {sorted(actual_files)}",
    )


def _run(command: list[str], repo_root: Path) -> str:
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    if result.returncode != 0:
        raise VerificationError(
            f"independent command failed ({result.returncode}): {shlex.join(command)}\n"
            f"{result.stderr}"
        )
    return result.stdout


def _build_command_file_bindings(build_command: str) -> list[dict[str, Any]]:
    candidates = re.findall(
        r"/nix/store/[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._?=/:-]+)?",
        build_command,
    )
    result: list[dict[str, Any]] = []
    for value in sorted(set(candidates)):
        path = Path(value.rstrip("'\"),;"))
        if path.is_file():
            data = path.read_bytes()
            result.append(
                {"path": str(path), "bytes": len(data), "sha256": _sha256_bytes(data)}
            )
    return result


def _live_derivation(
    repo_root: Path, stage: str, flake_reference: str = "."
) -> dict[str, Any]:
    attribute = f"{_MODEL}-{stage}"
    document = json.loads(
        _run(
            ["nix", "derivation", "show", f"{flake_reference}#{attribute}"],
            repo_root,
        )
    )
    derivations = document.get("derivations", {})
    _require(len(derivations) == 1, f"{stage}: live derivation count mismatch")
    basename, derivation = next(iter(derivations.items()))
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    drv = Path("/nix/store") / basename
    drv_bytes = drv.read_bytes()
    output_name = derivation.get("outputs", {}).get("out", {}).get("path")
    _require(isinstance(output_name, str), f"{stage}: live output missing")
    build_command = str(derivation.get("env", {}).get("buildCommand", ""))
    return {
        "attribute": attribute,
        "path": str(drv),
        "file_bytes": drv_bytes,
        "file_sha256": _sha256_bytes(drv_bytes),
        "canonical_json": canonical,
        "json_sha256": _sha256_bytes(canonical),
        "output": f"/nix/store/{output_name}",
        "build_command": build_command,
        "build_command_sha256": _sha256_bytes(build_command.encode()),
        "tool_bindings": _build_command_file_bindings(build_command),
    }


def _independent_trust(repo_root: Path, source_commit: str) -> dict[str, Any]:
    decision = _load_json(repo_root / _DECISION)
    _require(decision.get("identity_hashes") == _FROZEN_IDENTITIES, "live frozen Task 1-3 identities changed")
    _require(decision.get("sha256") == _DECISION_SELF_SHA256, "live Task 2 decision identity changed")
    predecessor_path = repo_root / _PREDECESSOR
    predecessor = _load_json(predecessor_path)
    _require(_sha256_bytes(predecessor_path.read_bytes()) == _PREDECESSOR_FILE_SHA256, "live predecessor file identity changed")
    _require(predecessor.get("sha256") == _PREDECESSOR_SELF_SHA256, "live predecessor self identity changed")
    semantic_command = [
        "nix", "develop", "-c", "python", _SEMANTIC_VERIFIER,
        "--probe-report", _SEMANTIC_REPORT,
    ]
    semantic_evidence = json.loads(_run(semantic_command, repo_root))
    source_flake = f"git+file://{repo_root}?rev={source_commit}"
    _run(
        [
            "nix", "build", "--no-link", "--print-out-paths",
            f"{source_flake}#{_MODEL}-linalg",
            f"{source_flake}#{_MODEL}-scf",
        ],
        repo_root,
    )
    derivations = {
        stage: _live_derivation(repo_root, stage, source_flake)
        for stage in ("linalg", "scf")
    }
    linalg_artifact = Path(derivations["linalg"]["output"])
    scf_artifact = Path(derivations["scf"]["output"]) / "manifest.json"
    for stage, artifact in (("linalg", linalg_artifact), ("scf", scf_artifact)):
        data = artifact.read_bytes()
        derivations[stage]["artifact_bytes"] = data
        derivations[stage]["artifact_sha256"] = _sha256_bytes(data)
    return {
        "repo_root": repo_root,
        "capture_tool_paths": {
            "classifier": _CLASSIFIER,
            "determinism_verifier": _VERIFIER,
        },
        "semantic_gate": {
            "command": shlex.join(semantic_command),
            "status": "accepted",
            "verifier": _SEMANTIC_VERIFIER,
            "verifier_sha256": _sha256_bytes((repo_root / _SEMANTIC_VERIFIER).read_bytes()),
            "probe_report": _SEMANTIC_REPORT,
            "probe_report_sha256": _sha256_bytes((repo_root / _SEMANTIC_REPORT).read_bytes()),
            "evidence": semantic_evidence,
        },
        "identities": _FROZEN_IDENTITIES,
        "decision_self_sha256": _DECISION_SELF_SHA256,
        "predecessor": {
            "historical_bundle": "artifacts/comparison/tinystories-1m-exact-frontier-determinism",
            "file_sha256": _PREDECESSOR_FILE_SHA256,
            "self_sha256": _PREDECESSOR_SELF_SHA256,
        },
        "derivations": derivations,
    }


def _verify_v4_receipt(
    receipt: dict[str, Any], files: dict[str, bytes], trust: dict[str, Any], run_name: str
) -> None:
    """Validate a v4 capture against independently reconstructed live facts."""

    _require(receipt.get("model") == _MODEL, f"{run_name}: model mismatch")
    _require(receipt.get("semantic_gate") == trust["semantic_gate"], f"{run_name}: semantic gate/probe mismatch")
    _require(
        receipt.get("frozen_task_1_through_3_identities") == trust["identities"]
        and receipt.get("task_2_decision_self_sha256") == trust["decision_self_sha256"],
        f"{run_name}: frozen Task 1-3 identity mismatch",
    )
    _require(receipt.get("predecessor_receipt") == trust["predecessor"], f"{run_name}: predecessor identity mismatch")

    source_commit = receipt.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), f"{run_name}: source commit missing")
    tools = receipt.get("capture_tools")
    _require(isinstance(tools, dict), f"{run_name}: capture tool bindings missing")
    repo_root = trust.get("repo_root")
    for name, path_string in trust["capture_tool_paths"].items():
        expected = tools.get(name)
        _require(isinstance(expected, dict) and expected.get("path") == path_string, f"{run_name}: {name} path mismatch")
        if isinstance(repo_root, Path):
            committed = subprocess.run(
                ["git", "show", f"{source_commit}:{path_string}"],
                cwd=repo_root,
                capture_output=True,
            )
            _require(committed.returncode == 0, f"{run_name}: {name} is absent from source commit")
            tool_bytes = committed.stdout
        else:
            tool_bytes = trust["capture_tool_bytes"][name]
        _require(
            expected.get("sha256") == _sha256_bytes(tool_bytes),
            f"{run_name}: {name} source-commit-byte hash mismatch",
        )

    _require(receipt.get("status") == "compiler_frontier", f"{run_name}: frontier status mismatch")
    _require(receipt.get("frontier") == "pre_calyx_frontier", f"{run_name}: frontier class mismatch")
    _require(receipt.get("stage") == "scf", f"{run_name}: first invalid stage is not SCF")
    _require(receipt.get("diagnostic") == _DIAGNOSTIC, f"{run_name}: diagnostic mismatch")
    pipeline = receipt.get("pipeline_execution")
    _require(
        pipeline == {
            "registered_order": ["pytorch-exported", "torch", "linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"],
            "first_invalid_stage": "scf",
            "stopped_after_first_invalid_stage": True,
            "not_run": _NOT_RUN,
        },
        f"{run_name}: exact stop semantics mismatch",
    )
    stages = receipt.get("stages")
    execution = receipt.get("registered_build_execution")
    _require(isinstance(stages, list) and isinstance(execution, dict), f"{run_name}: stage evidence missing")
    stage_sequence = [stage.get("stage") for stage in stages if isinstance(stage, dict)]
    _require(stage_sequence == _STAGES, f"{run_name}: stage sequence mismatch")
    _require(set(execution) == set(stage_sequence), f"{run_name}: execution stage set mismatch")
    registered_order = pipeline.get("registered_order")
    first_invalid = pipeline.get("first_invalid_stage")
    _require(
        isinstance(registered_order, list)
        and registered_order[: len(stage_sequence)] == stage_sequence
        and first_invalid == stage_sequence[-1]
        and pipeline.get("stopped_after_first_invalid_stage") is True
        and pipeline.get("not_run") == registered_order[len(stage_sequence) :],
        f"{run_name}: execution sequence/stop contract mismatch",
    )
    expected_files = {
        "receipt.json", "pytorch-exported.log", "torch.log", "linalg.log",
        "scf.log", "full-input.gz", "minimal-reproducer.json", "linalg.drv",
        "linalg.derivation.json", "scf.drv", "scf.derivation.json",
    }
    _require(set(files) == expected_files, f"{run_name}: canonical evidence file set mismatch")
    for index, stage in enumerate(_STAGES):
        record = stages[index]
        run = execution.get(stage)
        _require(isinstance(run, dict), f"{run_name}: {stage} execution missing")
        filename = f"{stage}.log"
        log = files.get(filename)
        _require(log is not None, f"{run_name}: {stage} log missing")
        expected_status = "compiler_failure" if stage == "scf" else "succeeded"
        expected_accepted = stage != "scf"
        expected_diagnostics = [_DIAGNOSTIC] if stage == "scf" else []
        _require(run.get("invoked") is True, f"{run_name}: {stage.upper()} execution was not invoked")
        _require(record.get("status") == expected_status, f"{run_name}: {stage} status mismatch")
        _require(record.get("artifact_accepted") is expected_accepted, f"{run_name}: {stage} acceptance mismatch")
        _require(
            run.get("artifact_accepted") is expected_accepted
            and run.get("artifact_accepted") is record.get("artifact_accepted"),
            f"{run_name}: {stage} execution acceptance mismatch",
        )
        _require(record.get("exit_code") == 0 and run.get("exit_code") == 0, f"{run_name}: {stage} exit mismatch")
        _require(record.get("terminal_diagnostics") == expected_diagnostics, f"{run_name}: {stage} terminal diagnostic mismatch")
        _require(record.get("log_bytes") == len(log) and run.get("log_bytes") == len(log), f"{run_name}: {stage} log byte mismatch")
        expected_log = f"reproducers/scf/{stage}.log"
        _require(record.get("log") == expected_log and run.get("log") == expected_log, f"{run_name}: {stage} log path mismatch")
        log_hash = _sha256_bytes(log)
        _require(record.get("log_sha256") == log_hash and run.get("log_sha256") == log_hash, f"{run_name}: {stage} log hash mismatch")
        expected_command = shlex.join(["nix", "build", "--no-link", "--print-out-paths", "-L", f".#{_MODEL}-{stage}"])
        _require(record.get("command") == expected_command and run.get("command") == expected_command, f"{run_name}: {stage} command mismatch")
    _require(_DIAGNOSTIC.encode() in files["scf.log"], f"{run_name}: SCF diagnostic absent from log")

    for stage in ("linalg", "scf"):
        live = trust["derivations"][stage]
        run = execution[stage]
        record = stages[_STAGES.index(stage)]
        _require(run.get("derivation") == live["path"], f"{run_name}: {stage} derivation path mismatch")
        _require(run.get("derivation_file_sha256") == live["file_sha256"], f"{run_name}: {stage} derivation hash mismatch")
        _require(run.get("derivation_json_sha256") == live["json_sha256"], f"{run_name}: {stage} derivation JSON hash mismatch")
        _require(run.get("derivation_build_command") == live["build_command"], f"{run_name}: {stage} build command mismatch")
        _require(run.get("derivation_build_command_sha256") == live["build_command_sha256"], f"{run_name}: {stage} build command hash mismatch")
        _require(run.get("derivation_tool_bindings") == live["tool_bindings"], f"{run_name}: {stage} tool binding mismatch")
        _require(record.get("tool_revisions", {}).get("build_command_sha256") == live["build_command_sha256"], f"{run_name}: {stage} stage build binding mismatch")
        expected_artifact = live["output"] if stage == "linalg" else f"{live['output']}/manifest.json"
        _require(run.get("result") == live["output"], f"{run_name}: {stage} result/output mismatch")
        _require(run.get("artifact") == expected_artifact and record.get("artifact") == expected_artifact, f"{run_name}: {stage} artifact path mismatch")
        drv = files.get(f"{stage}.drv")
        drv_json = files.get(f"{stage}.derivation.json")
        _require(drv == live["file_bytes"], f"{run_name}: {stage} captured .drv mismatch")
        _require(drv_json == live["canonical_json"], f"{run_name}: {stage} captured derivation JSON mismatch")
        _require(run.get("captured_derivation") == f"reproducers/scf/{stage}.drv", f"{run_name}: {stage} captured .drv path mismatch")
        _require(run.get("captured_derivation_json") == f"reproducers/scf/{stage}.derivation.json", f"{run_name}: {stage} captured derivation JSON path mismatch")
        _require(run.get("captured_derivation_bytes") == len(drv) and run.get("captured_derivation_sha256") == _sha256_bytes(drv), f"{run_name}: {stage} captured .drv receipt mismatch")
        _require(run.get("captured_derivation_json_bytes") == len(drv_json) and run.get("captured_derivation_json_sha256") == _sha256_bytes(drv_json), f"{run_name}: {stage} captured derivation JSON receipt mismatch")

    full = receipt.get("full_failing_input")
    _require(isinstance(full, dict), f"{run_name}: full input binding missing")
    archive = files.get("full-input.gz")
    _require(archive is not None and full.get("archive_bytes") == len(archive) and full.get("archive_sha256") == _sha256_bytes(archive), f"{run_name}: Linalg archive binding mismatch")
    try:
        content = gzip.decompress(archive)
    except (OSError, EOFError) as error:
        raise VerificationError(f"{run_name}: invalid full input gzip: {error}") from error
    _require(full.get("source_stage") == "linalg", f"{run_name}: full input source stage mismatch")
    _require(full.get("path") == "reproducers/scf/full-input.gz", f"{run_name}: full input path mismatch")
    _require(full.get("source_artifact") == trust["derivations"]["linalg"]["output"], f"{run_name}: full input source artifact mismatch")
    _require(full.get("content_bytes") == len(content) and full.get("content_sha256") == _sha256_bytes(content), f"{run_name}: decompressed Linalg content mismatch")
    linalg_record = stages[2]
    _require(linalg_record.get("artifact_bytes") == len(content) and linalg_record.get("artifact_sha256") == _sha256_bytes(content), f"{run_name}: Linalg artifact/content mismatch")
    _require(content == trust["derivations"]["linalg"]["artifact_bytes"], f"{run_name}: decompressed Linalg bytes differ from live derivation output")

    minimal = receipt.get("minimal_reproducer")
    manifest_bytes = files.get("minimal-reproducer.json")
    _require(isinstance(minimal, dict) and manifest_bytes is not None, f"{run_name}: SCF manifest binding missing")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise VerificationError(f"{run_name}: invalid SCF manifest: {error}") from error
    _require(manifest == _SCF_MANIFEST, f"{run_name}: exact SCF manifest mismatch")
    _require(manifest_bytes == trust["derivations"]["scf"]["artifact_bytes"], f"{run_name}: SCF manifest differs from live derivation output")
    _require(minimal.get("stage") == "scf" and minimal.get("diagnostic") == _DIAGNOSTIC, f"{run_name}: SCF reproducer semantics mismatch")
    _require(minimal.get("path") == "reproducers/scf/minimal-reproducer.json", f"{run_name}: SCF reproducer path mismatch")
    _require(minimal.get("bytes") == len(manifest_bytes) and minimal.get("sha256") == _sha256_bytes(manifest_bytes), f"{run_name}: SCF manifest receipt mismatch")
    _require(stages[3].get("artifact_bytes") == len(manifest_bytes) and stages[3].get("artifact_sha256") == _sha256_bytes(manifest_bytes), f"{run_name}: SCF artifact/manifest mismatch")


def _verify_run(
    bundle_root: Path,
    run_name: str,
    run_manifest: dict[str, Any],
    canonical_files: list[str],
    source_commit: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    run_root = bundle_root / run_name
    _verify_run_directory(run_root, run_name, tuple(canonical_files))
    _require(
        run_manifest.get("source_commit") == source_commit,
        f"{run_name}: source commit does not match manifest root",
    )
    metadata = run_manifest.get("noncanonical_metadata")
    _require(isinstance(metadata, dict), f"{run_name}: noncanonical metadata missing")
    _require(metadata.get("canonical") is False, f"{run_name}: metadata must be noncanonical")
    _require(
        isinstance(metadata.get("receipt_captured_at"), str)
        and bool(metadata["receipt_captured_at"]),
        f"{run_name}: capture timestamp missing",
    )
    _require(
        isinstance(metadata.get("runtime_seconds_approximate"), (int, float)),
        f"{run_name}: approximate runtime missing",
    )

    file_manifest = run_manifest.get("files")
    _require(isinstance(file_manifest, dict), f"{run_name}: file manifest missing")
    _require(
        sorted(file_manifest) == sorted(canonical_files),
        f"{run_name}: canonical file set does not match manifest",
    )
    file_bytes: dict[str, bytes] = {}
    for filename in canonical_files:
        _require(Path(filename).name == filename, f"unsafe canonical filename: {filename}")
        path = run_root / filename
        _require(path.is_file(), f"{run_name}: missing canonical file {filename}")
        data = path.read_bytes()
        binding = file_manifest[filename]
        _require(isinstance(binding, dict), f"{run_name}: bad binding for {filename}")
        _require(
            binding.get("bytes") == len(data),
            f"{run_name}: byte count mismatch for {filename}",
        )
        actual_sha256 = _sha256_bytes(data)
        _require(
            binding.get("sha256") == actual_sha256,
            f"{run_name}: SHA-256 mismatch for {filename}",
        )
        file_bytes[filename] = data

    receipt = _load_json(run_root / "receipt.json")
    _require(
        receipt.get("source_commit") == source_commit,
        f"{run_name}: receipt source commit mismatch",
    )
    self_hash = receipt.get("sha256")
    _require(
        isinstance(self_hash, str) and self_hash == _canonical_receipt_hash(receipt),
        f"{run_name}: receipt self-hash mismatch",
    )
    _require(
        run_manifest.get("receipt_self_hash") == self_hash,
        f"{run_name}: manifest receipt self-hash mismatch",
    )

    execution = receipt.get("registered_build_execution")
    capture = receipt.get("compiler_import_capture")
    _require(isinstance(execution, dict), f"{run_name}: registered execution missing")
    _require(isinstance(capture, dict), f"{run_name}: compiler capture missing")
    export = execution.get("pytorch-exported")
    torch = execution.get("torch-mlir")
    _require(isinstance(export, dict), f"{run_name}: export execution missing")
    _require(isinstance(torch, dict), f"{run_name}: Torch execution missing")

    expected_commands = {
        "pytorch-exported": export.get("command"),
        "torch-mlir": torch.get("command"),
        "compiler-import-capture": capture.get("command"),
    }
    expected_exits = {
        "pytorch-exported": export.get("exit_code"),
        "torch-mlir": torch.get("exit_code"),
        "compiler-import-capture": capture.get("exit_code"),
    }
    _require(
        run_manifest.get("commands") == expected_commands,
        f"{run_name}: commands do not match receipt",
    )
    _require(
        run_manifest.get("exit_codes") == expected_exits,
        f"{run_name}: exit codes do not match receipt",
    )

    log_bindings = {
        "pytorch-exported-build.log": export,
        "torch-mlir.log": torch,
        "compiler-import-capture.log": capture,
    }
    for filename, receipt_binding in log_bindings.items():
        data = file_bytes[filename]
        _require(
            receipt_binding.get("log_bytes") == len(data),
            f"{run_name}: receipt byte count mismatch for {filename}",
        )
        _require(
            receipt_binding.get("log_sha256") == _sha256_bytes(data),
            f"{run_name}: receipt SHA-256 mismatch for {filename}",
        )

    torch_text = file_bytes["torch-mlir.log"].decode("utf-8")
    capture_text = file_bytes["compiler-import-capture.log"].decode("utf-8")
    _require(
        str(receipt.get("diagnostic")) in torch_text,
        f"{run_name}: Torch log lost receipt diagnostic",
    )
    _require(
        str(capture.get("diagnostic")) in capture_text,
        f"{run_name}: capture log lost receipt diagnostic",
    )
    return receipt, file_bytes


def _verify_v1_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    """Verify both preserved live runs and require byte-identical canonical files."""

    bundle_root = bundle_root.resolve()
    manifest = _load_json(bundle_root / "manifest.json")
    _require(
        manifest.get("schema") == "tinystories-1m-exact-frontier-determinism-bundles-v1",
        "unsupported determinism manifest schema",
    )
    source_commit = manifest.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), "source commit missing")
    canonical_files = manifest.get("canonical_files")
    _require(
        canonical_files == list(_V1_CANONICAL_FILES),
        "v1 canonical file list does not match schema",
    )
    runs = manifest.get("runs")
    _require(isinstance(runs, dict), "run manifests missing")
    run_names = sorted(runs)
    _require(run_names == ["run-1", "run-2"], "exactly run-1 and run-2 are required")

    verified: dict[str, tuple[dict[str, Any], dict[str, bytes]]] = {}
    for run_name in run_names:
        _require(isinstance(runs[run_name], dict), f"invalid manifest for {run_name}")
        verified[run_name] = _verify_run(
            bundle_root,
            run_name,
            runs[run_name],
            canonical_files,
            source_commit,
        )

    first_receipt, first_files = verified["run-1"]
    second_receipt, second_files = verified["run-2"]
    for filename in canonical_files:
        _require(
            first_files[filename] == second_files[filename],
            f"preserved runs differ at canonical file {filename}",
        )
    _require(first_receipt == second_receipt, "parsed receipts differ")

    receipt_file_sha256 = _sha256_bytes(first_files["receipt.json"])
    receipt_self_hash = str(first_receipt["sha256"])
    expected = manifest.get("expected_comparison")
    _require(isinstance(expected, dict), "expected comparison missing")
    _require(expected.get("byte_identical") is True, "manifest does not expect identity")
    _require(
        expected.get("receipt_file_sha256") == receipt_file_sha256,
        "manifest comparison receipt SHA-256 mismatch",
    )
    _require(
        expected.get("receipt_self_hash") == receipt_self_hash,
        "manifest comparison receipt self-hash mismatch",
    )

    return {
        "source_commit": source_commit,
        "runs": run_names,
        "byte_identical": True,
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_self_hash": receipt_self_hash,
        "noncanonical_metadata_present": all(
            isinstance(runs[name].get("noncanonical_metadata"), dict)
            for name in run_names
        ),
    }


def _verify_v2_run(
    bundle_root: Path,
    run_name: str,
    run_manifest: dict[str, Any],
    canonical_files: list[str],
    source_commit: str,
    trust: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    run_root = bundle_root / run_name
    _verify_run_directory(run_root, run_name, tuple(canonical_files))
    _require(
        run_manifest.get("source_commit") == source_commit,
        f"{run_name}: source commit mismatch",
    )
    bindings = run_manifest.get("files")
    _require(isinstance(bindings, dict), f"{run_name}: file bindings missing")
    _require(
        sorted(bindings) == sorted(canonical_files),
        f"{run_name}: canonical file set mismatch",
    )
    files: dict[str, bytes] = {}
    for filename in canonical_files:
        _require(Path(filename).name == filename, f"unsafe canonical filename: {filename}")
        path = run_root / filename
        _require(path.is_file(), f"{run_name}: missing canonical file {filename}")
        data = path.read_bytes()
        binding = bindings[filename]
        _require(isinstance(binding, dict), f"{run_name}: invalid binding for {filename}")
        _require(binding.get("bytes") == len(data), f"{run_name}: byte count mismatch for {filename}")
        _require(
            binding.get("sha256") == _sha256_bytes(data),
            f"{run_name}: SHA-256 mismatch for {filename}",
        )
        files[filename] = data

    receipt = _load_json(run_root / "receipt.json")
    schema = receipt.get("schema")
    _require(
        schema in {
            "tinystories-1m-exact-current-pipeline-frontier-v3",
            "tinystories-1m-exact-current-pipeline-frontier-v4",
        },
        f"{run_name}: unsupported receipt schema",
    )
    _require(receipt.get("source_commit") == source_commit, f"{run_name}: receipt source mismatch")
    _require(receipt.get("stage") == "scf", f"{run_name}: first invalid stage is not SCF")
    _require(receipt.get("status") == "compiler_frontier", f"{run_name}: frontier status mismatch")
    _require(receipt.get("sha256") == _canonical_receipt_hash(receipt), f"{run_name}: receipt self-hash mismatch")
    _require(
        run_manifest.get("receipt_self_hash") == receipt.get("sha256"),
        f"{run_name}: manifest receipt self-hash mismatch",
    )
    execution = receipt.get("pipeline_execution")
    _require(isinstance(execution, dict), f"{run_name}: pipeline execution missing")
    _require(execution.get("first_invalid_stage") == "scf", f"{run_name}: SCF stop missing")
    _require(execution.get("stopped_after_first_invalid_stage") is True, f"{run_name}: stop flag missing")
    _require(
        execution.get("not_run") == ["flat-scf", "calyx", "calyx-native-sv"],
        f"{run_name}: later-stage exclusion mismatch",
    )
    stages = receipt.get("stages")
    _require(isinstance(stages, list), f"{run_name}: stage records missing")
    _require(
        [record.get("stage") for record in stages if isinstance(record, dict)]
        == ["pytorch-exported", "torch", "linalg", "scf"],
        f"{run_name}: executed stage order mismatch",
    )
    _require(all(record.get("artifact_accepted") is True for record in stages[:-1]), f"{run_name}: valid prefix rejected")
    _require(stages[-1].get("artifact_accepted") is False, f"{run_name}: invalid SCF artifact accepted")

    full_input = receipt.get("full_failing_input")
    minimal = receipt.get("minimal_reproducer")
    _require(isinstance(full_input, dict), f"{run_name}: full input binding missing")
    _require(isinstance(minimal, dict), f"{run_name}: minimal reproducer binding missing")
    _require(full_input.get("archive_sha256") == _sha256_bytes(files["full-input.gz"]), f"{run_name}: full input receipt hash mismatch")
    _require(minimal.get("sha256") == _sha256_bytes(files["minimal-reproducer.json"]), f"{run_name}: reproducer receipt hash mismatch")
    _require(minimal.get("operation_and_types_not_applicable") is True, f"{run_name}: frontier kind mismatch")
    for stage in ("pytorch-exported", "torch", "linalg", "scf"):
        record = next(item for item in stages if item["stage"] == stage)
        filename = f"{stage}.log"
        _require(record.get("log_sha256") == _sha256_bytes(files[filename]), f"{run_name}: receipt log hash mismatch for {stage}")
    if schema == "tinystories-1m-exact-current-pipeline-frontier-v4":
        _require(trust is not None, f"{run_name}: independent v4 trust is missing")
        _verify_v4_receipt(receipt, files, trust, run_name)
    return receipt, files


def _verify_v2_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    manifest = _load_json(bundle_root / "manifest.json")
    source_commit = manifest.get("source_commit")
    _require(isinstance(source_commit, str) and bool(source_commit), "source commit missing")
    canonical_files = manifest.get("canonical_files")
    enumerated_runs = {
        name: _enumerate_run_files(bundle_root / name, name)
        for name in ("run-1", "run-2")
    }
    first_receipt = _load_json(bundle_root / "run-1" / "receipt.json")
    receipt_schema = first_receipt.get("schema")
    if receipt_schema == "tinystories-1m-exact-current-pipeline-frontier-v4":
        schema_files = _V2_CURRENT_CANONICAL_FILES
    elif (
        receipt_schema == "tinystories-1m-exact-current-pipeline-frontier-v3"
        and source_commit == _LEGACY_V3_SOURCE_COMMIT
    ):
        schema_files = _V2_LEGACY_CANONICAL_FILES
    else:
        raise VerificationError("unsupported v2 receipt schema/source identity")
    _require(
        canonical_files == list(schema_files),
        "v2 canonical file list does not match receipt schema",
    )
    for name, actual_files in enumerated_runs.items():
        _require(
            actual_files == set(schema_files) | _RUN_METADATA_FILES,
            f"{name}: run directory contents mismatch: "
            f"expected {sorted(set(schema_files) | _RUN_METADATA_FILES)}, "
            f"found {sorted(actual_files)}",
        )
    runs = manifest.get("runs")
    _require(isinstance(runs, dict), "run manifests missing")
    run_names = sorted(runs)
    _require(run_names == ["run-1", "run-2"], "exactly run-1 and run-2 are required")
    trust = (
        _independent_trust(Path(__file__).resolve().parents[2], str(source_commit))
        if first_receipt.get("schema")
        == "tinystories-1m-exact-current-pipeline-frontier-v4"
        else None
    )
    verified = {
        name: _verify_v2_run(
            bundle_root, name, runs[name], canonical_files, source_commit, trust
        )
        for name in run_names
    }
    first_receipt, first_files = verified["run-1"]
    second_receipt, second_files = verified["run-2"]
    for filename in canonical_files:
        _require(
            first_files[filename] == second_files[filename],
            f"preserved runs differ at canonical file {filename}",
        )
    _require(first_receipt == second_receipt, "parsed receipts differ")
    expected = manifest.get("expected_comparison")
    _require(isinstance(expected, dict), "expected comparison missing")
    receipt_file_sha256 = _sha256_bytes(first_files["receipt.json"])
    _require(expected.get("byte_identical") is True, "manifest does not expect identity")
    _require(expected.get("first_invalid_stage") == "scf", "manifest frontier mismatch")
    _require(expected.get("receipt_file_sha256") == receipt_file_sha256, "manifest receipt file hash mismatch")
    _require(expected.get("receipt_self_hash") == first_receipt["sha256"], "manifest receipt self-hash mismatch")
    return {
        "source_commit": source_commit,
        "runs": run_names,
        "byte_identical": True,
        "first_invalid_stage": "scf",
        "receipt_file_sha256": receipt_file_sha256,
        "receipt_self_hash": first_receipt["sha256"],
        "canonical_file_count": len(canonical_files),
    }


def verify_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
    """Verify historical v1 or current v2 deterministic capture bundles."""

    bundle_root = bundle_root.resolve()
    manifest = _load_json(bundle_root / "manifest.json")
    schema = manifest.get("schema")
    if schema == "tinystories-1m-exact-frontier-determinism-bundles-v1":
        return _verify_v1_determinism_bundles(bundle_root)
    if schema == "tinystories-1m-exact-frontier-determinism-bundles-v2":
        return _verify_v2_determinism_bundles(bundle_root)
    raise VerificationError("unsupported determinism manifest schema")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_bundle = (
        repo_root
        / "artifacts"
        / "comparison"
        / "tinystories-1m-exact-frontier-determinism-scf"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle)
    args = parser.parse_args()
    print(json.dumps(verify_determinism_bundles(args.bundle_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
