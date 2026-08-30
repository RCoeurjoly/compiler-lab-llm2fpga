#!/usr/bin/env python3
"""Classify the first validly evidenced TinyStories current-pipeline frontier."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Literal


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_PIPELINE_COMMIT = "7eed3592a661c0cb3c417dc59b29839266446b2d"
_PASS_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)
_CRITICAL_PIPELINE_INPUTS = (
    "flake.nix",
    "flake.lock",
    "nix/models.nix",
    "nix/pipeline.nix",
    "scripts/compile-pytorch.py",
    "scripts/materialize-pytorch-exported.py",
    "TinyStories/model_adapter_exact_package.py",
    "artifacts/reference/tinystories-1m-exact-input-contract.json",
    "artifacts/reference/tinystories-1m-exact-input-audit.json",
    "artifacts/reference/tinystories-1m-exact-package-model.json",
    "artifacts/reference/tinystories-1m-exact-generation.json",
    "docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
)
_STAGE_ALIASES = {
    "pytorch_exported": "pytorch-exported",
    "torch_mlir": "torch-mlir",
    "flat_scf": "flat-scf",
    "sv": "calyx-native-sv",
    "calyx_native_sv": "calyx-native-sv",
}
_FRONTIERS = {
    "pytorch-exported": "export_frontier",
    "torch-mlir": "torch_mlir_frontier",
    "linalg": "pre_calyx_frontier",
    "scf": "pre_calyx_frontier",
    "flat-scf": "pre_calyx_frontier",
    "calyx": "calyx_frontier",
    "calyx-native-sv": "sv_frontier",
}
_TERMINAL_DIAGNOSTIC_RE = re.compile(
    r"(?:\berror:\s|failed to legalize operation|unhandled operation|LLVM ERROR)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StageRecord:
    stage: str
    status: Literal["succeeded", "compiler_failure", "environment_failure"]
    artifact: str
    artifact_bytes: int
    artifact_sha256: str
    artifact_accepted: bool
    command: str
    tool_revisions: dict[str, str]
    log: str
    log_sha256: str
    log_bytes: int
    terminal_diagnostics: tuple[str, ...]
    upstream_identity: str
    exit_code: int


@dataclass(frozen=True)
class FrontierReceipt:
    status: Literal["complete", "compiler_frontier", "environment_failure"]
    frontier: str | None
    stage: str | None
    diagnostic: str | None


def _canonical_stage(stage: str) -> str:
    canonical = _STAGE_ALIASES.get(stage, stage)
    if canonical not in _FRONTIERS:
        raise ValueError(f"stage is not registered for exact-frontier classification: {stage!r}")
    return canonical


def _terminal_diagnostics_from_log(record: StageRecord) -> tuple[str, ...]:
    log_path = Path(record.log)
    if not log_path.is_file():
        raise ValueError(f"{record.stage}: actual log does not exist: {record.log}")
    log_bytes = log_path.read_bytes()
    if record.log_bytes != len(log_bytes):
        raise ValueError(
            f"{record.stage}: log_bytes does not match actual log "
            f"({record.log_bytes} != {len(log_bytes)})"
        )
    actual_sha256 = _sha256_bytes(log_bytes)
    if record.log_sha256 != actual_sha256:
        raise ValueError(
            f"{record.stage}: log_sha256 does not match actual log "
            f"({record.log_sha256} != {actual_sha256})"
        )

    diagnostics = []
    for line in log_bytes.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and _TERMINAL_DIAGNOSTIC_RE.search(stripped):
            diagnostics.append(stripped)
    return tuple(diagnostics)


def _require_bindings(record: StageRecord) -> tuple[str, ...]:
    if not record.artifact:
        raise ValueError(f"{record.stage}: artifact is required")
    if record.artifact_bytes <= 0:
        raise ValueError(f"{record.stage}: artifact_bytes must be positive")
    if not _SHA256_RE.fullmatch(record.artifact_sha256):
        raise ValueError(f"{record.stage}: artifact_sha256 must be lowercase SHA-256")
    if not isinstance(record.artifact_accepted, bool):
        raise ValueError(f"{record.stage}: artifact_accepted must be boolean")
    if not record.command.strip():
        raise ValueError(f"{record.stage}: command is required")
    if not record.tool_revisions or any(
        not str(key).strip() or not str(value).strip()
        for key, value in record.tool_revisions.items()
    ):
        raise ValueError(f"{record.stage}: tool_revisions are required")
    if not record.log.strip():
        raise ValueError(f"{record.stage}: log is required")
    if not _SHA256_RE.fullmatch(record.log_sha256):
        raise ValueError(f"{record.stage}: log_sha256 must be lowercase SHA-256")
    if record.log_bytes < 0:
        raise ValueError(f"{record.stage}: log_bytes must be non-negative")
    if not record.upstream_identity.strip():
        raise ValueError(f"{record.stage}: upstream_identity is required")
    if not isinstance(record.exit_code, int):
        raise ValueError(f"{record.stage}: exit_code must be an integer")
    return _terminal_diagnostics_from_log(record)


def classify_frontier(stage_records: list[StageRecord]) -> FrontierReceipt:
    """Return only the earliest invalid stage in the supplied causal order."""

    if not stage_records:
        raise ValueError("stage records must be a nonempty contiguous prefix")
    canonical_stages = [_canonical_stage(record.stage) for record in stage_records]
    expected = list(_FRONTIERS)[: len(canonical_stages)]
    if canonical_stages != expected:
        raise ValueError(
            "stage records must be a contiguous prefix of registered causal order "
            "starting at pytorch-exported"
        )

    evaluated: list[tuple[StageRecord, str, tuple[str, ...], bool]] = []
    for index, (record, stage) in enumerate(zip(stage_records, canonical_stages)):
        diagnostics = _require_bindings(record)
        if record.status not in {"succeeded", "compiler_failure", "environment_failure"}:
            raise ValueError(f"{record.stage}: unknown status {record.status!r}")

        failed = record.status != "succeeded" or bool(diagnostics)
        if record.status != "succeeded" and not diagnostics:
            raise ValueError(
                f"{record.stage}: actual log contains no terminal diagnostic"
            )
        if failed and record.artifact_accepted:
            raise ValueError(f"{record.stage}: artifact_accepted must be false after diagnostics")
        if not failed and not record.artifact_accepted:
            raise ValueError(f"{record.stage}: artifact_accepted must be true on success")
        if not failed and record.exit_code != 0:
            raise ValueError(f"{record.stage}: exit_code must be zero on success")
        evaluated.append((record, stage, diagnostics, failed))
        if failed and index != len(stage_records) - 1:
            raise ValueError("stage records must end at the first invalid stage")

    invalid_positions = [
        index for index, (_, _, _, failed) in enumerate(evaluated) if failed
    ]
    if invalid_positions:
        first_invalid = invalid_positions[0]
        if first_invalid != len(evaluated) - 1:
            raise ValueError("stage records must end at the first invalid stage")
        record, stage, diagnostics, _ = evaluated[first_invalid]
        if record.status == "environment_failure":
            return FrontierReceipt("environment_failure", None, stage, diagnostics[0])
        return FrontierReceipt(
            "compiler_frontier", _FRONTIERS[stage], stage, diagnostics[0]
        )

    if len(evaluated) != len(_FRONTIERS):
        raise ValueError("incomplete successful prefix cannot establish pipeline completion")

    return FrontierReceipt("complete", None, None, None)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(
    command: list[str], *, cwd: Path, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _derivation(repo_root: Path, attribute: str) -> dict[str, object]:
    result = _run(["nix", "derivation", "show", f".#{attribute}"], cwd=repo_root)
    document = json.loads(result.stdout)
    entries = document.get("derivations", {})
    if len(entries) != 1:
        raise RuntimeError(f"expected one derivation for {attribute}, found {len(entries)}")
    basename, derivation = next(iter(entries.items()))
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    drv_path = Path("/nix/store") / basename
    outputs = derivation.get("outputs", {})
    output = outputs.get("out", {}).get("path")
    if not output:
        raise RuntimeError(f"derivation for {attribute} has no out path")
    input_data = derivation.get("inputs", {})
    return {
        "attribute": attribute,
        "path": str(drv_path),
        "file_sha256": _sha256(drv_path),
        "json_sha256": _sha256_bytes(canonical),
        "output": f"/nix/store/{output}",
        "build_command": str(derivation.get("env", {}).get("buildCommand", "")),
        "build_command_sha256": _sha256_bytes(
            str(derivation.get("env", {}).get("buildCommand", "")).encode()
        ),
        "build_inputs": str(derivation.get("env", {}).get("buildInputs", "")),
        "input_derivations": sorted(
            f"/nix/store/{name}" for name in input_data.get("drvs", {})
        ),
        "input_sources": sorted(
            f"/nix/store/{name}" for name in input_data.get("srcs", [])
        ),
    }


def _git_bytes(repo_root: Path, revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=repo_root, capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cannot read {path} from {revision}: "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )
    return result.stdout


def _source_for_suffix(derivation: dict[str, object], suffix: str) -> Path:
    matches = [
        Path(path)
        for path in derivation["input_sources"]
        if str(path).endswith(suffix)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one evaluated source ending {suffix!r}, found {matches}"
        )
    return matches[0]


def _authenticate_pipeline_source(
    repo_root: Path,
    export_derivation: dict[str, object],
    torch_derivation: dict[str, object],
) -> dict[str, object]:
    evidence_commit = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    if evidence_commit == _ACCEPTED_PIPELINE_COMMIT:
        raise RuntimeError("evidence source commit must be distinct from accepted Task 4")
    ancestry = _run(
        ["git", "merge-base", "--is-ancestor", _ACCEPTED_PIPELINE_COMMIT, "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if ancestry.returncode != 0:
        raise RuntimeError("HEAD does not descend from the accepted Task 4 commit")

    dirty = _run(
        ["git", "status", "--porcelain", "--", *_CRITICAL_PIPELINE_INPUTS],
        cwd=repo_root,
    ).stdout.strip()
    if dirty:
        raise RuntimeError(f"critical pipeline inputs are dirty:\n{dirty}")

    archive_result = _run(["nix", "flake", "archive", "--json"], cwd=repo_root)
    archive = Path(json.loads(archive_result.stdout)["path"])
    archive_nar_hash = _run(["nix", "hash", "path", str(archive)], cwd=repo_root).stdout.strip()

    evaluated_paths: dict[str, Path] = {}
    evaluated_sources = {
        "scripts/compile-pytorch.py": (torch_derivation, "-compile-pytorch.py", None),
        "scripts/materialize-pytorch-exported.py": (
            export_derivation,
            "-materialize-pytorch-exported.py",
            None,
        ),
        "TinyStories/model_adapter_exact_package.py": (
            export_derivation,
            "-TinyStories",
            "model_adapter_exact_package.py",
        ),
        "artifacts/reference/tinystories-1m-exact-input-contract.json": (
            export_derivation,
            "-tinystories-1m-exact-input-contract.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-input-audit.json": (
            export_derivation,
            "-tinystories-1m-exact-input-audit.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-package-model.json": (
            export_derivation,
            "-tinystories-1m-exact-package-model.json",
            None,
        ),
        "artifacts/reference/tinystories-1m-exact-generation.json": (
            export_derivation,
            "-tinystories-1m-exact-generation.json",
            None,
        ),
        "docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md": (
            export_derivation,
            "-2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
            None,
        ),
    }
    for path, (derivation, suffix, child) in evaluated_sources.items():
        if path in _CRITICAL_PIPELINE_INPUTS:
            source = _source_for_suffix(derivation, suffix)
            evaluated_paths[path] = source / child if child else source
    critical: dict[str, dict[str, object]] = {}
    for path in _CRITICAL_PIPELINE_INPUTS:
        workspace = repo_root / path
        archived = archive / path
        if not workspace.is_file() or not archived.is_file():
            raise RuntimeError(f"critical pipeline input is missing: {path}")
        workspace_sha = _sha256(workspace)
        task4_bytes = _git_bytes(repo_root, _ACCEPTED_PIPELINE_COMMIT, path)
        task4_sha = _sha256_bytes(task4_bytes)
        archive_sha = _sha256(archived)
        if not (workspace_sha == task4_sha == archive_sha):
            raise RuntimeError(
                f"critical pipeline input mutated since Task 4 or differs from "
                f"the evaluated flake archive: {path}"
            )
        task4_blob = _run(
            ["git", "rev-parse", f"{_ACCEPTED_PIPELINE_COMMIT}:{path}"], cwd=repo_root
        ).stdout.strip()
        binding: dict[str, object] = {
            "workspace_sha256": workspace_sha,
            "task4_sha256": task4_sha,
            "task4_blob": task4_blob,
            "evidence_blob": _run(
                ["git", "rev-parse", f"HEAD:{path}"], cwd=repo_root
            ).stdout.strip(),
            "flake_archive_path": str(archived),
            "flake_archive_sha256": archive_sha,
        }
        if path in evaluated_paths:
            evaluated = evaluated_paths[path]
            evaluated_sha = _sha256(evaluated)
            if evaluated_sha != workspace_sha:
                raise RuntimeError(
                    f"derivation source bytes do not match workspace input: {path}"
                )
            binding["derivation_store_path"] = str(evaluated)
            binding["derivation_store_sha256"] = evaluated_sha
        critical[path] = binding

    return {
        "accepted_task4_commit": _ACCEPTED_PIPELINE_COMMIT,
        "evidence_source_commit": evidence_commit,
        "task4_is_ancestor": True,
        "critical_inputs_clean": True,
        "flake_archive_path": str(archive),
        "flake_archive_nar_hash": archive_nar_hash,
        "critical_inputs": critical,
        "export_derivation": export_derivation,
        "torch_derivation": torch_derivation,
    }


def _locked_revision(repo_root: Path, name: str) -> str:
    lock = json.loads((repo_root / "flake.lock").read_text(encoding="utf-8"))
    node = lock["nodes"][name]["locked"]
    revision = node.get("rev") or node.get("narHash")
    if not revision:
        raise RuntimeError(f"flake input {name} has no locked revision or hash")
    return str(revision)


def _uncompressed_identity(archive: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_count = 0
    with gzip.open(archive, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            byte_count += len(chunk)
            digest.update(chunk)
    return byte_count, digest.hexdigest()


def _canonical_receipt_hash(receipt: dict[str, object]) -> str:
    canonical = json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _stable_nix_diagnostic(stderr: str, repo_root: Path) -> str:
    lines = [
        line
        for line in stderr.splitlines()
        if not line.startswith("warning: Git tree ")
    ]
    return "\n".join(lines).replace(str(repo_root), "<repo>").strip()


def _run_and_log(
    command: list[str], *, cwd: Path, log: Path, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
    )
    normalized_stdout = "\n".join(line.rstrip() for line in result.stdout.split("\n"))
    normalized_stderr = "\n".join(line.rstrip() for line in result.stderr.split("\n"))
    payload = (
        f"$ {shlex.join(command)}\n"
        f"exit_code: {result.returncode}\n"
        "--- stdout ---\n"
        f"{normalized_stdout}"
        "--- stderr ---\n"
        f"{normalized_stderr}"
    ).encode("utf-8")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(payload)
    return result


def _relative(repo_root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def _find_store_path(text: str, suffix: str) -> Path:
    matches = sorted(set(re.findall(r"/nix/store/[^\s\"']+", text)))
    selected = [Path(value.rstrip("\\")) for value in matches if value.rstrip("\\").endswith(suffix)]
    if len(selected) != 1:
        raise RuntimeError(f"expected one store path ending {suffix!r}, found {selected}")
    return selected[0]


def _capture_compiler_failure(
    repo_root: Path,
    failure_dir: Path,
    exported_program: Path,
    torch_derivation: dict[str, object],
) -> dict[str, object]:
    build_command = str(torch_derivation["build_command"])
    compile_script = _find_store_path(build_command, "-compile-pytorch.py")
    derivation_export = _find_store_path(
        build_command, "-tiny-stories-1m-kev-gpt-exact-pytorch-exported"
    )
    if derivation_export.resolve() != exported_program.parent.resolve():
        raise RuntimeError(
            "Torch derivation is not bound to the freshly built exact Task 4 export"
        )

    python_roots = [
        Path(item)
        for item in str(torch_derivation["build_inputs"]).split()
        if "python3-" in item and item.endswith("-env")
    ]
    if len(python_roots) != 1:
        raise RuntimeError(f"cannot identify exact Python environment: {python_roots}")
    python = python_roots[0] / "bin" / "python"
    pythonpath_match = re.search(r'export PYTHONPATH="([^"$]+):\$\{PYTHONPATH:-\}"', build_command)
    if pythonpath_match is None:
        raise RuntimeError("cannot recover the Torch derivation PYTHONPATH")
    pythonpath = pythonpath_match.group(1)
    torch_mlir_root = Path(pythonpath.split(":", 1)[0]).parents[2]
    candidates = (
        torch_mlir_root / "bin" / "torch-mlir-opt",
        torch_mlir_root / "lib" / "python3.11" / "site-packages" / "torch_mlir" / "_mlir_libs" / "torch-mlir-opt",
        torch_mlir_root / "lib" / "python3.11" / "site-packages" / "torch_mlir" / "torch_mlir" / "_mlir_libs" / "torch-mlir-opt",
    )
    tool_matches = [candidate for candidate in candidates if candidate.is_file()]
    if len(tool_matches) != 1:
        raise RuntimeError(f"cannot identify exact torch-mlir-opt binary: {tool_matches}")
    torch_mlir_opt = tool_matches[0]

    capture_log = failure_dir / "compiler-import-capture.log"
    with tempfile.TemporaryDirectory(prefix="tinystories-exact-import-capture-") as temporary:
        temporary_path = Path(temporary)
        requested_output = temporary_path / "requested-torch.mlir"
        command = [
            str(python),
            str(compile_script),
            "--exported-program-dir",
            str(exported_program.parent),
            "--out",
            str(requested_output),
        ]
        environment = {
            **os.environ,
            "TMPDIR": str(temporary_path),
            "PYTHONPATH": pythonpath,
        }
        result = _run_and_log(
            command, cwd=repo_root, log=capture_log, environment=environment
        )
        if result.returncode == 0:
            raise RuntimeError("exact compiler/import capture unexpectedly succeeded")
        dump_candidates = [
            path
            for path in temporary_path.rglob("*.mlir")
            if path != requested_output and path.stat().st_size > 0
        ]
        if len(dump_candidates) != 1:
            raise RuntimeError(f"expected one compiler-emitted failing IR, found {dump_candidates}")
        full_ir_bytes = dump_candidates[0].read_bytes()

    diagnostic = "failed to legalize operation 'torch.operator' that was explicitly marked illegal"
    if diagnostic not in capture_log.read_text(encoding="utf-8"):
        raise RuntimeError("content-bound import capture lost the registered compiler diagnostic")
    operation = "torch.aten.bitwise_right_shift.Tensor_Scalar"
    if operation.encode() not in full_ir_bytes:
        raise RuntimeError("content-bound failing IR lost the original integer shift operation")

    archive = failure_dir / "full-failing-ir.mlir.gz"
    with archive.open("wb") as raw_archive:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, mtime=0) as stream:
            stream.write(full_ir_bytes)

    version = _run([str(torch_mlir_opt), "--version"], cwd=repo_root).stdout.strip()
    return {
        "executed": True,
        "command": " ".join(
            [
                f"TMPDIR={shlex.quote(str(temporary_path))}",
                f"PYTHONPATH={shlex.quote(pythonpath)}",
                shlex.join(command),
            ]
        ),
        "exit_code": result.returncode,
        "exported_program": str(exported_program),
        "export_sha256": _sha256(exported_program),
        "torch_derivation": str(torch_derivation["path"]),
        "torch_derivation_json_sha256": str(torch_derivation["json_sha256"]),
        "compile_script": str(compile_script),
        "compile_script_sha256": _sha256(compile_script),
        "python": str(python),
        "python_sha256": _sha256(python),
        "torch_mlir_opt": str(torch_mlir_opt),
        "torch_mlir_opt_sha256": _sha256(torch_mlir_opt),
        "torch_mlir_version": version,
        "pass_pipeline": _PASS_PIPELINE,
        "produced_ir_bytes": len(full_ir_bytes),
        "produced_ir_sha256": _sha256_bytes(full_ir_bytes),
        "log": _relative(repo_root, capture_log),
        "log_bytes": capture_log.stat().st_size,
        "log_sha256": _sha256(capture_log),
        "diagnostic": diagnostic,
        "operation": operation,
    }


def build_current_frontier_receipt(repo_root: Path, model: str) -> dict[str, object]:
    if model != "tiny-stories-1m-kev-gpt-exact":
        raise ValueError("this classifier only authenticates tiny-stories-1m-kev-gpt-exact")

    requested_attribute = f"{model}-torch-mlir"
    requested_command = f"nix build .#{requested_attribute} -L"
    missing_alias = _run(
        ["nix", "build", "--no-link", "--print-out-paths", f".#{requested_attribute}"],
        cwd=repo_root,
        check=False,
    )
    if missing_alias.returncode == 0:
        raise RuntimeError(
            f"{requested_attribute} unexpectedly exists; review the recorded command resolution"
        )

    export_attribute = f"{model}-pytorch-exported"
    torch_attribute = f"{model}-torch"
    export_derivation = _derivation(repo_root, export_attribute)
    torch_derivation = _derivation(repo_root, torch_attribute)
    source_identity = _authenticate_pipeline_source(
        repo_root, export_derivation, torch_derivation
    )

    failure_dir = repo_root / "reproducers" / "tinystories-1m-exact-torch-mlir"
    failure_dir.mkdir(parents=True, exist_ok=True)
    export_log = failure_dir / "pytorch-exported-build.log"
    torch_log = failure_dir / "torch-mlir.log"
    export_invocation = [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        "-L",
        f".#{export_attribute}",
    ]
    export_output_result = _run_and_log(
        export_invocation, cwd=repo_root, log=export_log
    )
    if export_output_result.returncode != 0:
        raise RuntimeError(
            "registered exact export build failed; no later stage was executed:\n"
            + export_log.read_text(encoding="utf-8")
        )
    output_lines = [
        line.strip()
        for line in export_output_result.stdout.splitlines()
        if line.strip().startswith("/nix/store/")
    ]
    if len(output_lines) != 1:
        raise RuntimeError(f"cannot identify fresh export result: {output_lines}")
    export_output = Path(output_lines[0])
    if str(export_output) != export_derivation["output"]:
        raise RuntimeError("fresh export result differs from the recorded derivation output")
    exported_program = export_output / "exported.pt2"
    if not exported_program.is_file() or exported_program.stat().st_size == 0:
        raise RuntimeError(f"missing nonempty authenticated export: {exported_program}")

    torch_invocation = [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        "-L",
        f".#{torch_attribute}",
    ]
    torch_result = _run_and_log(torch_invocation, cwd=repo_root, log=torch_log)
    if torch_result.returncode == 0:
        raise RuntimeError(
            "registered Torch stage unexpectedly succeeded; this evidence command refuses "
            "to skip directly to a later frontier"
        )
    torch_text = torch_log.read_text(encoding="utf-8")
    compiler_diagnostic = (
        "failed to legalize operation 'torch.operator' that was explicitly marked illegal"
    )
    environment_markers = (
        "cannot connect to socket",
        "failed to download",
        "no space left on device",
        "temporary failure in name resolution",
    )
    if compiler_diagnostic not in torch_text:
        failure_class = (
            "environment failure"
            if any(marker in torch_text.lower() for marker in environment_markers)
            else "unrecognized non-compiler failure"
        )
        raise RuntimeError(
            f"registered Torch build stopped at an {failure_class}; no compiler frontier "
            f"or downstream stage may be claimed:\n{torch_text}"
        )

    capture = _capture_compiler_failure(
        repo_root, failure_dir, exported_program, torch_derivation
    )
    full_archive = failure_dir / "full-failing-ir.mlir.gz"
    reproducer = failure_dir / "bitwise-right-shift-tensor-scalar.mlir"
    interesting = failure_dir / "interesting.sh"
    for path in (export_log, torch_log, full_archive, reproducer, interesting):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing nonempty frontier evidence: {path}")

    full_bytes, full_sha256 = _uncompressed_identity(full_archive)
    if full_bytes != capture["produced_ir_bytes"] or full_sha256 != capture["produced_ir_sha256"]:
        raise RuntimeError("archived failing IR differs from the content-bound compiler capture")
    with gzip.open(full_archive, "rb") as stream:
        full_text = stream.read().decode("utf-8")
    full_operator_count = full_text.count("torch.operator ")
    if full_operator_count == 0:
        raise RuntimeError("full failing IR contains no generic torch.operator")
    operation_signature = (
        'torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"'
        '(%arg0, %int1) : (!torch.vtensor<[4,1],si64>, !torch.int) '
        '-> !torch.vtensor<[4,1],si64>'
    )
    if operation_signature not in reproducer.read_text(encoding="utf-8"):
        raise RuntimeError("minimal reproducer changed the original failing operation types")
    original_type_signature = (
        'torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"'
        '(%72, %int1_96) : (!torch.vtensor<[4,1],si64>, !torch.int) '
        '-> !torch.vtensor<[4,1],si64>'
    )
    if original_type_signature not in full_text:
        raise RuntimeError("fresh compiler capture does not contain the reduced original signature")
    torch_mlir_opt = str(capture["torch_mlir_opt"])
    with tempfile.TemporaryDirectory(prefix="tinystories-exact-frontier-check-") as temporary:
        full_ir = Path(temporary) / "full-failing-ir.mlir"
        with gzip.open(full_archive, "rb") as source:
            full_ir.write_bytes(source.read())
        interesting_environment = {**os.environ, "TORCH_MLIR_OPT": torch_mlir_opt}
        for candidate in (full_ir, reproducer):
            verified = subprocess.run(
                [str(interesting), str(candidate)],
                cwd=repo_root,
                env=interesting_environment,
                text=True,
                capture_output=True,
            )
            if verified.returncode != 0:
                raise RuntimeError(
                    f"exact interestingness check failed for {candidate}:\n"
                    f"{verified.stdout}{verified.stderr}"
                )

    export_sha256 = _sha256(exported_program)

    stage_records = [
        StageRecord(
            stage="pytorch-exported",
            status="succeeded",
            artifact=str(exported_program),
            artifact_bytes=exported_program.stat().st_size,
            artifact_sha256=export_sha256,
            artifact_accepted=True,
            command=shlex.join(export_invocation),
            tool_revisions={
                "evidence_source_commit": str(source_identity["evidence_source_commit"]),
                "kev-gpt-src": _locked_revision(repo_root, "kev-gpt-src"),
                "nixpkgs": _locked_revision(repo_root, "nixpkgs"),
                "derivation": str(export_derivation["path"]),
                "derivation_file_sha256": str(export_derivation["file_sha256"]),
                "derivation_json_sha256": str(export_derivation["json_sha256"]),
                "build_command_sha256": str(export_derivation["build_command_sha256"]),
            },
            log=str(export_log),
            log_sha256=_sha256(export_log),
            log_bytes=export_log.stat().st_size,
            terminal_diagnostics=(),
            upstream_identity=(
                "package_manifest_sha256:"
                "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35"
            ),
            exit_code=0,
        ),
        StageRecord(
            stage="torch-mlir",
            status="compiler_failure",
            artifact=str(full_archive.relative_to(repo_root)),
            artifact_bytes=full_archive.stat().st_size,
            artifact_sha256=_sha256(full_archive),
            artifact_accepted=False,
            command=shlex.join(torch_invocation),
            tool_revisions={
                "evidence_source_commit": str(source_identity["evidence_source_commit"]),
                "torch-mlir-source": "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
                "torch-mlir-version": str(capture["torch_mlir_version"]),
                "torch-mlir-opt-sha256": str(capture["torch_mlir_opt_sha256"]),
                "nixpkgs-llvm21": _locked_revision(repo_root, "nixpkgs-llvm21"),
                "derivation": str(torch_derivation["path"]),
                "derivation_file_sha256": str(torch_derivation["file_sha256"]),
                "derivation_json_sha256": str(torch_derivation["json_sha256"]),
                "build_command_sha256": str(torch_derivation["build_command_sha256"]),
            },
            log=str(torch_log),
            log_sha256=_sha256(torch_log),
            log_bytes=torch_log.stat().st_size,
            terminal_diagnostics=(compiler_diagnostic,),
            upstream_identity=f"sha256:{export_sha256}",
            exit_code=torch_result.returncode,
        ),
    ]
    classification = classify_frontier(stage_records)
    if classification.frontier != "torch_mlir_frontier":
        raise RuntimeError(f"unexpected exact-input frontier: {classification}")

    receipt: dict[str, object] = {
        "schema": "tinystories-1m-exact-current-pipeline-frontier-v2",
        "model": model,
        "status": classification.status,
        "frontier": classification.frontier,
        "stage": classification.stage,
        "diagnostic": classification.diagnostic,
        "source_commit": source_identity["evidence_source_commit"],
        "pipeline_source_identity": source_identity,
        "command_resolution": {
            "requested_command": requested_command,
            "requested_status": "missing_flake_attribute",
            "diagnostic": _stable_nix_diagnostic(missing_alias.stderr, repo_root),
            "resolved_registered_stage": "torch",
            "executed_command": shlex.join(torch_invocation),
            "reason": (
                "The registry names the Torch-MLIR artifact stage 'torch'; "
                "the brief's '-torch-mlir' package alias is not exported."
            ),
        },
        "stages": [
            {
                **asdict(record),
                "log": _relative(repo_root, Path(record.log)),
            }
            for record in stage_records
        ],
        "registered_build_execution": {
            "pytorch-exported": {
                "invoked": True,
                "command": shlex.join(export_invocation),
                "exit_code": export_output_result.returncode,
                "result": str(export_output),
                "log": _relative(repo_root, export_log),
                "log_bytes": export_log.stat().st_size,
                "log_sha256": _sha256(export_log),
                "derivation": export_derivation["path"],
                "derivation_file_sha256": export_derivation["file_sha256"],
                "derivation_json_sha256": export_derivation["json_sha256"],
            },
            "torch-mlir": {
                "invoked": True,
                "command": shlex.join(torch_invocation),
                "exit_code": torch_result.returncode,
                "result": None,
                "log": _relative(repo_root, torch_log),
                "log_bytes": torch_log.stat().st_size,
                "log_sha256": _sha256(torch_log),
                "derivation": torch_derivation["path"],
                "derivation_file_sha256": torch_derivation["file_sha256"],
                "derivation_json_sha256": torch_derivation["json_sha256"],
            },
        },
        "pipeline_execution": {
            "first_invalid_stage": "torch-mlir",
            "stopped_after_first_invalid_stage": True,
            "not_run": [
                "linalg",
                "scf",
                "flat-scf",
                "calyx",
                "calyx-native-sv",
            ],
        },
        "full_failing_ir": {
            "archive": str(full_archive.relative_to(repo_root)),
            "archive_bytes": full_archive.stat().st_size,
            "archive_sha256": _sha256(full_archive),
            "content_bytes": full_bytes,
            "content_sha256": full_sha256,
            "torch_operator_count": full_operator_count,
        },
        "compiler_import_capture": capture,
        "minimal_reproducer": {
            "path": str(reproducer.relative_to(repo_root)),
            "bytes": reproducer.stat().st_size,
            "sha256": _sha256(reproducer),
            "operation": "torch.aten.bitwise_right_shift.Tensor_Scalar",
            "reduction": "manual delta reduction after MLIR 21 lacked Torch dialect registration",
            "original_operation_and_types_preserved": True,
            "interestingness_test": str(interesting.relative_to(repo_root)),
            "interestingness_test_sha256": _sha256(interesting),
            "verified": True,
            "command": (
                f"TORCH_MLIR_OPT={torch_mlir_opt} "
                f"{interesting.relative_to(repo_root)} {reproducer.relative_to(repo_root)}"
            ),
            "diagnostic": compiler_diagnostic,
        },
        "claims": {
            "linalg": False,
            "scf": False,
            "flat_scf": False,
            "calyx": False,
            "systemverilog": False,
            "functional_equivalence": False,
            "resource_or_timing": False,
            "backend_model_quantization_ddr_pcie_changed": False,
        },
    }
    receipt["sha256"] = _canonical_receipt_hash(receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify the first exact TinyStories current-pipeline frontier."
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    receipt = build_current_frontier_receipt(repo_root, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
