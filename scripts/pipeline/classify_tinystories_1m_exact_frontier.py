#!/usr/bin/env python3
"""Classify the first validly evidenced TinyStories current-pipeline frontier."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Literal


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_PIPELINE_COMMIT = "7eed3592a661c0cb3c417dc59b29839266446b2d"
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


def _require_bindings(record: StageRecord) -> None:
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


def classify_frontier(stage_records: list[StageRecord]) -> FrontierReceipt:
    """Return only the earliest invalid stage in the supplied causal order."""

    canonical_stages = [_canonical_stage(record.stage) for record in stage_records]
    stage_positions = {stage: index for index, stage in enumerate(_FRONTIERS)}
    positions = [stage_positions[stage] for stage in canonical_stages]
    if any(current >= following for current, following in zip(positions, positions[1:])):
        raise ValueError("stage records must be unique and in registered causal order")

    for record, stage in zip(stage_records, canonical_stages):
        _require_bindings(record)
        diagnostics = tuple(item for item in record.terminal_diagnostics if item.strip())

        if record.status == "environment_failure":
            if not diagnostics:
                raise ValueError(f"{record.stage}: terminal_diagnostics are required for failure")
            if record.artifact_accepted:
                raise ValueError(f"{record.stage}: artifact_accepted must be false after diagnostics")
            return FrontierReceipt("environment_failure", None, stage, diagnostics[0])

        if record.status == "compiler_failure" or diagnostics:
            if not diagnostics:
                raise ValueError(f"{record.stage}: terminal_diagnostics are required for failure")
            if record.artifact_accepted:
                raise ValueError(f"{record.stage}: artifact_accepted must be false after diagnostics")
            return FrontierReceipt(
                "compiler_frontier", _FRONTIERS[stage], stage, diagnostics[0]
            )

        if record.status != "succeeded":
            raise ValueError(f"{record.stage}: unknown status {record.status!r}")
        if not record.artifact_accepted:
            raise ValueError(f"{record.stage}: artifact_accepted must be true on success")
        if record.exit_code != 0:
            raise ValueError(f"{record.stage}: exit_code must be zero on success")

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


def _derivation(repo_root: Path, attribute: str) -> tuple[str, str, list[str]]:
    result = _run(
        ["nix", "derivation", "show", f".#{attribute}"], cwd=repo_root
    )
    entries = json.loads(result.stdout).get("derivations", {})
    if len(entries) != 1:
        raise RuntimeError(f"expected one derivation for {attribute}, found {len(entries)}")
    basename, derivation = next(iter(entries.items()))
    inputs = derivation.get("inputs", {}).get("drvs", {})
    return (
        f"/nix/store/{basename}",
        str(derivation.get("env", {}).get("buildCommand", "")),
        sorted(f"/nix/store/{name}" for name in inputs),
    )


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
    export_output_result = _run(
        ["nix", "build", "--no-link", "--print-out-paths", f".#{export_attribute}"],
        cwd=repo_root,
    )
    export_output = Path(export_output_result.stdout.strip())
    exported_program = export_output / "exported.pt2"
    if not exported_program.is_file() or exported_program.stat().st_size == 0:
        raise RuntimeError(f"missing nonempty authenticated export: {exported_program}")

    export_drv, export_command, export_inputs = _derivation(repo_root, export_attribute)
    torch_drv, torch_command, torch_inputs = _derivation(repo_root, torch_attribute)
    export_log_result = _run(["nix", "log", export_drv], cwd=repo_root)
    torch_log_result = _run(["nix", "log", torch_drv], cwd=repo_root)
    export_log = export_log_result.stdout.encode("utf-8")
    torch_log = (torch_log_result.stdout.rstrip() + "\n").encode("utf-8")

    failure_dir = repo_root / "reproducers" / "tinystories-1m-exact-torch-mlir"
    recorded_log = failure_dir / "torch-mlir.log"
    full_archive = failure_dir / "full-failing-ir.mlir.gz"
    reproducer = failure_dir / "bitwise-right-shift-tensor-scalar.mlir"
    interesting = failure_dir / "interesting.sh"
    for path in (recorded_log, full_archive, reproducer, interesting):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing nonempty frontier evidence: {path}")
    if recorded_log.read_bytes() != torch_log:
        raise RuntimeError("recorded Torch-MLIR log does not match the Nix daemon log")

    diagnostic_match = re.search(
        r"error: (failed to legalize operation 'torch\.operator' that was explicitly marked illegal)",
        torch_log_result.stdout,
    )
    if diagnostic_match is None:
        raise RuntimeError("Torch-MLIR log does not contain the expected terminal diagnostic")
    diagnostic = diagnostic_match.group(1)

    with tempfile.TemporaryDirectory(prefix="tinystories-exact-frontier-") as temporary:
        full_ir = Path(temporary) / "full-failing-ir.mlir"
        with gzip.open(full_archive, "rb") as source, full_ir.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        full_operator_count = full_ir.read_text(encoding="utf-8").count("torch.operator ")
        if full_operator_count == 0:
            raise RuntimeError("full failing IR contains no generic torch.operator")
        if "torch.aten.bitwise_right_shift.Tensor_Scalar" not in reproducer.read_text(
            encoding="utf-8"
        ):
            raise RuntimeError("minimal reproducer lost the original failing shift operation")
        for candidate in (full_ir, reproducer):
            _run([str(interesting), str(candidate)], cwd=repo_root)

    full_bytes, full_sha256 = _uncompressed_identity(full_archive)
    export_sha256 = _sha256(exported_program)
    accepted_commit = _run(
        ["git", "rev-parse", _ACCEPTED_PIPELINE_COMMIT], cwd=repo_root
    ).stdout.strip()
    if accepted_commit != _ACCEPTED_PIPELINE_COMMIT:
        raise RuntimeError("accepted Task 4 pipeline commit identity changed")
    torch_version = _run(["torch-mlir-opt", "--version"], cwd=repo_root).stdout.strip()

    stage_records = [
        StageRecord(
            stage="pytorch-exported",
            status="succeeded",
            artifact=str(exported_program),
            artifact_bytes=exported_program.stat().st_size,
            artifact_sha256=export_sha256,
            artifact_accepted=True,
            command=export_command,
            tool_revisions={
                "git_commit": accepted_commit,
                "kev-gpt-src": _locked_revision(repo_root, "kev-gpt-src"),
                "nixpkgs": _locked_revision(repo_root, "nixpkgs"),
                "derivation": export_drv,
                "input_derivations": ",".join(export_inputs),
            },
            log=f"nix log {export_drv}",
            log_sha256=_sha256_bytes(export_log),
            log_bytes=len(export_log),
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
            command=torch_command,
            tool_revisions={
                "git_commit": accepted_commit,
                "torch-mlir-source": "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9",
                "torch-mlir-version": torch_version,
                "nixpkgs-llvm21": _locked_revision(repo_root, "nixpkgs-llvm21"),
                "derivation": torch_drv,
                "input_derivations": ",".join(torch_inputs),
            },
            log=str(recorded_log.relative_to(repo_root)),
            log_sha256=_sha256_bytes(torch_log),
            log_bytes=len(torch_log),
            terminal_diagnostics=(diagnostic,),
            upstream_identity=f"sha256:{export_sha256}",
            exit_code=1,
        ),
    ]
    classification = classify_frontier(stage_records)
    if classification.frontier != "torch_mlir_frontier":
        raise RuntimeError(f"unexpected exact-input frontier: {classification}")

    receipt: dict[str, object] = {
        "schema": "tinystories-1m-exact-current-pipeline-frontier-v1",
        "model": model,
        "status": classification.status,
        "frontier": classification.frontier,
        "stage": classification.stage,
        "diagnostic": classification.diagnostic,
        "source_commit": accepted_commit,
        "command_resolution": {
            "requested_command": requested_command,
            "requested_status": "missing_flake_attribute",
            "diagnostic": _stable_nix_diagnostic(missing_alias.stderr, repo_root),
            "resolved_registered_stage": "torch",
            "executed_command": f"nix build .#{torch_attribute} -L",
            "reason": (
                "The registry names the Torch-MLIR artifact stage 'torch'; "
                "the brief's '-torch-mlir' package alias is not exported."
            ),
        },
        "stages": [asdict(record) for record in stage_records],
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
        "minimal_reproducer": {
            "path": str(reproducer.relative_to(repo_root)),
            "bytes": reproducer.stat().st_size,
            "sha256": _sha256(reproducer),
            "operation": "torch.aten.bitwise_right_shift.Tensor_Scalar",
            "reduction": "manual delta reduction after MLIR 21 lacked Torch dialect registration",
            "interestingness_test": str(interesting.relative_to(repo_root)),
            "interestingness_test_sha256": _sha256(interesting),
            "verified": True,
            "command": f"nix develop -c {interesting.relative_to(repo_root)} {reproducer.relative_to(repo_root)}",
            "diagnostic": diagnostic,
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
