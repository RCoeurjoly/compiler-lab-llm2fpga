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
import shutil
import subprocess
import tempfile
from typing import Callable, Literal


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTED_PIPELINE_COMMIT = "7eed3592a661c0cb3c417dc59b29839266446b2d"
_SCF_REGISTRATION_COMMIT = "3314a70ac1cfe0e998f445162d1a2b5ae8398a20"
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
    "torch-mlir": "torch",
    "torch_mlir": "torch",
    "flat_scf": "flat-scf",
    "sv": "calyx-native-sv",
    "calyx_native_sv": "calyx-native-sv",
}
_FRONTIERS = {
    "pytorch-exported": "export_frontier",
    "torch": "torch_mlir_frontier",
    "linalg": "pre_calyx_frontier",
    "scf": "pre_calyx_frontier",
    "flat-scf": "pre_calyx_frontier",
    "calyx": "calyx_frontier",
    "calyx-native-sv": "sv_frontier",
}
_EXACT_LINALG_ALIAS = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake"
_AUTHENTICATED_DIRECT_STAGE_SHA256 = {
    "torch": "e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674",
    "linalg": "f4792aef4a0054386bf4e9e6399cc107e6d947b4d608e97e6041ccdf2ffb59c8",
}
_TERMINAL_DIAGNOSTIC_RE = re.compile(
    r"(?:\berror:\s|failed to legalize operation|unhandled operation|LLVM ERROR)",
    re.IGNORECASE,
)
_CLASSIFIER = "scripts/pipeline/classify_tinystories_1m_exact_frontier.py"
_DETERMINISM_VERIFIER = (
    "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py"
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
class AcceptedStageResult:
    kind: Literal["accepted"]
    artifact: Path
    output: Path


@dataclass(frozen=True)
class ControlManifestFailure:
    kind: Literal["control_manifest"]
    manifest: Path
    upstream_input: Path
    diagnostic: str
    residual_artifact: Path | None = None
    blockers: Path | None = None


@dataclass(frozen=True)
class CompilerFailure:
    kind: Literal["compiler_failure"]
    upstream_input: Path
    log: Path
    diagnostic: str
    operation: str | None
    types: str | None


@dataclass(frozen=True)
class EnvironmentFailure:
    kind: Literal["environment_failure"]
    log: Path
    diagnostic: str
    category: str


RegisteredStageResult = (
    AcceptedStageResult | ControlManifestFailure | CompilerFailure | EnvironmentFailure
)


@dataclass(frozen=True)
class FrontierReceipt:
    status: Literal["complete", "compiler_frontier", "environment_failure"]
    frontier: str | None
    stage: str | None
    diagnostic: str | None


def _serialize_frontier_evidence(
    *,
    stage: str,
    result: ControlManifestFailure | CompilerFailure,
    canonical_root: str,
    manifest_binding: dict[str, object] | None = None,
    residual_artifact_binding: dict[str, object] | None = None,
    blockers_binding: dict[str, object] | None = None,
    interestingness: dict[str, object] | None = None,
    minimization: dict[str, object] | None = None,
) -> dict[str, object]:
    """Serialize the fail-closed evidence union for one rejected stage."""

    if isinstance(result, ControlManifestFailure):
        if interestingness is not None or minimization is not None:
            raise ValueError("control manifest cannot carry compiler minimization")
        if manifest_binding is None:
            raise ValueError("control manifest binding is required")
        try:
            manifest_value = json.loads(result.manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot serialize control manifest: {error}") from error
        if not isinstance(manifest_value, dict):
            raise ValueError("control manifest must be a JSON object")
        status = manifest_value.get("status")
        if status == "completed-with-residuals":
            if (
                result.residual_artifact is None
                or result.blockers is None
                or residual_artifact_binding is None
                or blockers_binding is None
            ):
                raise ValueError(
                    "completed-with-residuals requires artifact and blockers bindings"
                )
        elif (
            result.residual_artifact is not None
            or result.blockers is not None
            or residual_artifact_binding is not None
            or blockers_binding is not None
        ):
            raise ValueError("non-residual control manifest cannot carry residual bindings")
        evidence = {
            "kind": "control_manifest",
            "manifest": {
                **manifest_binding,
                "stage": manifest_value.get("stage"),
                "status": status,
                "reason": manifest_value.get("reason"),
            },
            "operation": None,
            "types": None,
            "minimization": {
                "status": "not_applicable",
                "reason": "control_manifest_is_minimal",
            },
        }
        if status == "completed-with-residuals":
            evidence["manifest"].update(
                {
                    "artifact": manifest_value.get("artifact"),
                    "blockers": manifest_value.get("blockers"),
                }
            )
            evidence["residual_artifact"] = residual_artifact_binding
            evidence["blockers"] = blockers_binding
        return evidence

    if manifest_binding is not None:
        raise ValueError("compiler failure cannot carry a manifest")
    if minimization is None:
        raise ValueError("compiler failure requires minimization evidence")
    if interestingness is None and minimization.get("reason") != "unsupported_compiler_command":
        raise ValueError(
            "compiler failure may omit interestingness only for an unsupported compiler command"
        )
    return {
        "kind": "compiler_failure",
        "manifest": None,
        "diagnostic": result.diagnostic,
        "operation": result.operation,
        "types": result.types,
        "interestingness": interestingness,
        "minimization": minimization,
    }


def _shell_command_units(command: str) -> list[tuple[int, int]]:
    """Return top-level shell command-unit spans without interpreting the shell."""

    units: list[tuple[int, int]] = []
    start = 0
    quote: str | None = None
    substitution_depth = 0
    index = 0
    while index < len(command):
        char = command[index]
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == "\\" and index + 1 < len(command):
                index += 2
                continue
            if char == '"':
                quote = None
            index += 1
            continue
        if char == "\\" and index + 1 < len(command):
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            substitution_depth += 1
            index += 2
            continue
        if substitution_depth:
            if char == "(":
                substitution_depth += 1
            elif char == ")":
                substitution_depth -= 1
            index += 1
            continue
        if char in {"\n", ";"}:
            units.append((start, index))
            start = index + 1
            index = start
            continue
        index += 1
    if quote is not None or substitution_depth:
        raise ValueError("build command has unterminated shell syntax")
    units.append((start, len(command)))
    return units


def _literal_shell_words(command: str, start: int, end: int) -> list[tuple[int, int, str, bool]]:
    """Decode literal shell words while retaining their exact source spans."""

    words: list[tuple[int, int, str, bool]] = []
    index = start
    delimiters = " \t\r\n<>|&;()"
    while index < end:
        while index < end and command[index] in delimiters:
            index += 1
        if index >= end or command[index] == "#":
            break
        word_start = index
        value: list[str] = []
        dynamic = False
        quote: str | None = None
        while index < end:
            char = command[index]
            if quote == "'":
                if char == "'":
                    quote = None
                else:
                    value.append(char)
                index += 1
                continue
            if quote == '"':
                if char == '"':
                    quote = None
                    index += 1
                    continue
                if char == "\\" and index + 1 < end:
                    following = command[index + 1]
                    if following in {'$', '`', '"', "\\", "\n"}:
                        if following != "\n":
                            value.append(following)
                        index += 2
                        continue
                if char in {"$", "`"}:
                    dynamic = True
                value.append(char)
                index += 1
                continue
            if char in delimiters:
                break
            if char in {"'", '"'}:
                quote = char
                index += 1
                continue
            if char == "\\" and index + 1 < end:
                following = command[index + 1]
                if following != "\n":
                    value.append(following)
                index += 2
                continue
            if char in {"$", "`", "*", "?", "["} or (
                char == "~" and index == word_start
            ):
                dynamic = True
            value.append(char)
            index += 1
        if quote is not None:
            raise ValueError("build command has unterminated quoted shell word")
        words.append((word_start, index, "".join(value), dynamic))
    return words


def _is_supported_simple_command(command: str, start: int, end: int) -> bool:
    """Reject shell syntax that can change word roles or process boundaries."""

    quote: str | None = None
    index = start
    while index < end:
        char = command[index]
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == "\\" and index + 1 < end:
                index += 2
                continue
            if char == '"':
                quote = None
                index += 1
                continue
            if char == "`" or (
                char == "$" and index + 1 < end and command[index + 1] == "("
            ):
                return False
            index += 1
            continue
        if char == "\\" and index + 1 < end:
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char in "<>|&()" or char == "`" or (
            char == "$" and index + 1 < end and command[index + 1] == "("
        ):
            return False
        index += 1
    return quote is None


def _has_supported_positional_input(
    words: list[tuple[int, int, str, bool]],
    executable_index: int,
    input_index: int,
) -> bool:
    """Recognize only registered compiler shapes with a proven input slot."""

    executable = words[executable_index]
    executable_name = executable[2].rsplit("/", 1)[-1]
    arguments = words[executable_index + 1 :]
    input_offset = input_index - executable_index - 1

    direct_compilers = {"circt-opt", "mlir-opt", "torch-mlir-opt"}
    if executable_name in direct_compilers and input_offset == 0:
        if len(arguments) == 1:
            return True
        return (
            len(arguments) == 3
            and arguments[1][2] in {"-o", "--output"}
            and not arguments[1][3]
        )

    wrapper_tools = {
        "linalg_to_scf_no_handshake.sh": "mlir-opt",
        "scf_to_flat_scf_no_handshake.sh": "mlir-opt",
        "torch_to_linalg.sh": "torch-mlir-opt",
    }
    if executable_name != "bash" or input_offset != 2 or len(arguments) != 4:
        return False
    wrapper_name = arguments[0][2].rsplit("/", 1)[-1]
    wrapper = next(
        (
            name
            for name in wrapper_tools
            if wrapper_name == name or wrapper_name.endswith(f"-{name}")
        ),
        None,
    )
    tool_name = arguments[1][2].rsplit("/", 1)[-1]
    return (
        wrapper is not None
        and not arguments[0][3]
        and not arguments[1][3]
        and tool_name == wrapper_tools[wrapper]
    )


def _bind_compiler_command(build_command: str, upstream_input: str) -> tuple[str, str]:
    """Bind the unique simple command whose literal shell word is the upstream input."""

    matches: list[tuple[int, int, int, int]] = []
    for unit_start, unit_end in _shell_command_units(build_command):
        for word_start, word_end, value, dynamic in _literal_shell_words(
            build_command, unit_start, unit_end
        ):
            if not dynamic and value == upstream_input:
                matches.append((unit_start, unit_end, word_start, word_end))
    if len(matches) != 1:
        raise ValueError(
            "build command must contain the bound upstream input as exactly one direct argument to a simple compiler command"
        )
    unit_start, unit_end, word_start, word_end = matches[0]
    words = _literal_shell_words(build_command, unit_start, unit_end)
    match_index = next(
        index
        for index, word in enumerate(words)
        if word[0] == word_start and word[1] == word_end
    )
    executable_index = next(
        (
            index
            for index, (_, _, value, _) in enumerate(words)
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", value) is None
        ),
        None,
    )
    shell_keywords = {
        "!",
        "{",
        "}",
        "case",
        "coproc",
        "do",
        "done",
        "elif",
        "else",
        "esac",
        "fi",
        "for",
        "function",
        "if",
        "in",
        "select",
        "then",
        "time",
        "until",
        "while",
    }
    if (
        not _is_supported_simple_command(build_command, unit_start, unit_end)
        or executable_index is None
        or match_index <= executable_index
        or words[executable_index][3]
        or words[executable_index][2] in shell_keywords
        or not _has_supported_positional_input(
            words, executable_index, match_index
        )
    ):
        raise ValueError(
            "bound upstream input is not in a supported positional input slot of a simple compiler command"
        )
    while unit_start < unit_end and build_command[unit_start].isspace():
        unit_start += 1
    while unit_end > unit_start and build_command[unit_end - 1].isspace():
        unit_end -= 1
    compiler_command = build_command[unit_start:unit_end]
    candidate_command = (
        build_command[unit_start:word_start]
        + '"${candidate}"'
        + build_command[word_end:unit_end]
    )
    return compiler_command, candidate_command


def _render_interestingness_test(
    *,
    build_command: str,
    upstream_input: Path,
    compiler_exit_nonzero: bool,
    expected_diagnostic: str,
    operation: str | None,
    types: str | None,
) -> bytes:
    """Render the canonical candidate-substituting compiler-failure predicate."""

    if compiler_exit_nonzero is not True:
        raise ValueError("compiler-failure predicate must require a nonzero compiler exit")
    _, candidate_command = _bind_compiler_command(build_command, str(upstream_input))
    expected_operation = operation or ""
    expected_types = types or ""
    script = f"""#!/usr/bin/env bash
set -uo pipefail
if [[ $# -ne 1 || ! -f $1 ]]; then
  echo "usage: $0 CANDIDATE" >&2
  exit 2
fi
candidate=$1
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
out="$work/output"
export out
set +e
(
{candidate_command}
) >"$work/stdout" 2>"$work/stderr"
actual_exit=$?
set -e
while IFS= read -r line; do printf '%s\n' "$line"; done <"$work/stdout" >"$work/combined"
while IFS= read -r line; do printf '%s\n' "$line"; done <"$work/stderr" >>"$work/combined"
diagnostic=""
while IFS= read -r line; do
  lower=${{line,,}}
  case "$lower" in
    *"failed to legalize operation"*|*"unhandled operation"*|*"llvm error"*)
      if [[ -n $diagnostic ]]; then diagnostic+=$'\\n'; fi
      diagnostic+="$line"
      ;;
  esac
done <"$work/combined"
if [[ -z $diagnostic ]]; then
  while IFS= read -r line; do
    lower=${{line,,}}
    case "$lower" in
      *"error: builder for"*|*"dependencies of derivation"*|*"error: build of"*) ;;
      *"error:"*)
        if [[ -n $diagnostic ]]; then diagnostic+=$'\\n'; fi
        diagnostic+="$line"
        ;;
    esac
  done <"$work/combined"
fi
contains_bound_text() {{
  local needle=$1
  [[ -z $needle ]] && return 0
  while IFS= read -r line; do [[ $line == *"$needle"* ]] && return 0; done <"$work/combined"
  while IFS= read -r line; do [[ $line == *"$needle"* ]] && return 0; done <"$candidate"
  return 1
}}
compiler_exit_nonzero=true
expected_diagnostic={shlex.quote(expected_diagnostic)}
expected_operation={shlex.quote(expected_operation)}
expected_types={shlex.quote(expected_types)}
if [[ $compiler_exit_nonzero != true || $actual_exit -eq 0 || $diagnostic != "$expected_diagnostic" ]]; then
  printf 'interestingness mismatch: exit=%s diagnostic=%q\n' "$actual_exit" "$diagnostic" >&2
  exit 1
fi
contains_bound_text "$expected_operation" || {{ echo "operation mismatch" >&2; exit 1; }}
contains_bound_text "$expected_types" || {{ echo "types mismatch" >&2; exit 1; }}
printf 'interesting candidate: %s\n' "$candidate"
"""
    return script.encode("utf-8")


def _write_interestingness_test(
    path: Path,
    *,
    build_command: str,
    upstream_input: Path,
    compiler_exit_nonzero: bool,
    expected_diagnostic: str,
    operation: str | None,
    types: str | None,
) -> None:
    """Write the deterministic canonical compiler-failure predicate."""

    path.write_bytes(
        _render_interestingness_test(
            build_command=build_command,
            upstream_input=upstream_input,
            compiler_exit_nonzero=compiler_exit_nonzero,
            expected_diagnostic=expected_diagnostic,
            operation=operation,
            types=types,
        )
    )
    path.chmod(0o755)


def _registered_attribute(model: str, stage: str) -> str:
    if model != "tiny-stories-1m-kev-gpt-exact":
        raise ValueError(f"unsupported exact model: {model}")
    if stage == "pytorch-exported":
        return f"{model}-pytorch-exported"
    if stage not in _FRONTIERS:
        raise ValueError(f"unregistered exact stage: {stage}")
    return f"{_EXACT_LINALG_ALIAS}-{stage}"


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


def _run_registered_pipeline(execute_stage: object) -> list[StageRecord]:
    """Execute the registered stages in order and stop at the first invalid one."""

    if not callable(execute_stage):
        raise TypeError("execute_stage must be callable")
    records: list[StageRecord] = []
    upstream: StageRecord | None = None
    for stage in _FRONTIERS:
        if stage == "scf":
            prefix = {record.stage: record for record in records}
            for authenticated_stage in ("torch", "linalg"):
                record = prefix.get(authenticated_stage)
                expected_sha256 = _AUTHENTICATED_DIRECT_STAGE_SHA256.get(
                    authenticated_stage
                )
                if (
                    record is None
                    or record.status != "succeeded"
                    or not record.artifact_accepted
                    or not isinstance(expected_sha256, str)
                    or not _SHA256_RE.fullmatch(expected_sha256)
                    or record.artifact_sha256 != expected_sha256
                ):
                    raise RuntimeError(
                        f"{authenticated_stage}: authenticated alias prefix hash mismatch"
                    )
        record = execute_stage(stage, upstream)
        if not isinstance(record, StageRecord):
            raise TypeError(f"{stage}: executor did not return a StageRecord")
        if _canonical_stage(record.stage) != stage:
            raise ValueError(f"{stage}: executor returned record for {record.stage}")
        records.append(record)
        upstream = record
        if record.status != "succeeded" or not record.artifact_accepted:
            break
    return records


def _require_byte_identical_bundles(
    first: Path, second: Path, canonical_files: tuple[str, ...]
) -> None:
    """Reject capture runs unless every named canonical file is byte-identical."""

    for filename in canonical_files:
        if Path(filename).name != filename:
            raise ValueError(f"unsafe canonical filename: {filename}")
        first_path = first / filename
        second_path = second / filename
        if not first_path.is_file() or not second_path.is_file():
            raise RuntimeError(f"missing canonical bundle file: {filename}")
        if first_path.read_bytes() != second_path.read_bytes():
            raise RuntimeError(f"capture bundles differ at {filename}")


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
        "canonical_json": canonical.decode("utf-8"),
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


def _build_command_file_bindings(build_command: str) -> list[dict[str, object]]:
    """Bind every existing regular /nix/store file named by a build command."""

    candidates = re.findall(r"/nix/store/[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._?=/:-]+)?", build_command)
    bindings: list[dict[str, object]] = []
    for value in sorted(set(candidates)):
        path = Path(value.rstrip("'\"),;"))
        if path.is_file():
            bindings.append(
                {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            )
    return bindings


def _capture_derivation_evidence(
    evidence_dir: Path, stage: str, derivation: dict[str, object]
) -> dict[str, object]:
    drv_destination = evidence_dir / f"{stage}.drv"
    json_destination = evidence_dir / f"{stage}.derivation.json"
    shutil.copyfile(Path(str(derivation["path"])), drv_destination)
    json_destination.write_text(str(derivation["canonical_json"]), encoding="utf-8")
    return {
        "captured_derivation": f"reproducers/{stage}/{stage}.drv",
        "captured_derivation_bytes": drv_destination.stat().st_size,
        "captured_derivation_sha256": _sha256(drv_destination),
        "captured_derivation_json": f"reproducers/{stage}/{stage}.derivation.json",
        "captured_derivation_json_bytes": json_destination.stat().st_size,
        "captured_derivation_json_sha256": _sha256(json_destination),
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
    registration_ancestry = _run(
        ["git", "merge-base", "--is-ancestor", _SCF_REGISTRATION_COMMIT, "HEAD"],
        cwd=repo_root,
        check=False,
    )
    if registration_ancestry.returncode != 0:
        raise RuntimeError("HEAD does not descend from the exact SCF registration commit")

    dirty = _run(
        ["git", "status", "--porcelain", "--", *_CRITICAL_PIPELINE_INPUTS],
        cwd=repo_root,
    ).stdout.strip()
    if dirty:
        raise RuntimeError(f"critical pipeline inputs are dirty:\n{dirty}")

    evidence_flake = f"git+file://{repo_root}?rev={evidence_commit}"
    archive_result = _run(
        ["nix", "flake", "archive", "--json", evidence_flake], cwd=repo_root
    )
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
        authenticated_commit = (
            _SCF_REGISTRATION_COMMIT if path == "flake.nix" else _ACCEPTED_PIPELINE_COMMIT
        )
        authenticated_bytes = _git_bytes(repo_root, authenticated_commit, path)
        authenticated_sha = _sha256_bytes(authenticated_bytes)
        archive_sha = _sha256(archived)
        if not (workspace_sha == authenticated_sha == archive_sha):
            raise RuntimeError(
                f"critical pipeline input mutated since its authenticated commit or differs from "
                f"the evaluated flake archive: {path}"
            )
        task4_blob = _run(
            ["git", "rev-parse", f"{_ACCEPTED_PIPELINE_COMMIT}:{path}"], cwd=repo_root
        ).stdout.strip()
        binding: dict[str, object] = {
            "workspace_sha256": workspace_sha,
            "task4_sha256": task4_sha,
            "task4_blob": task4_blob,
            "authenticated_commit": authenticated_commit,
            "authenticated_sha256": authenticated_sha,
            "authenticated_blob": _run(
                ["git", "rev-parse", f"{authenticated_commit}:{path}"], cwd=repo_root
            ).stdout.strip(),
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
        "flake_archive_source": evidence_flake,
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


def _canonicalize_execution_text(
    value: str,
    ephemeral_paths: dict[str, str] | None = None,
    *,
    drop_git_dirty_warning: bool = False,
    drop_nix_progress: bool = False,
) -> str:
    canonical = value
    for actual, placeholder in sorted(
        (ephemeral_paths or {}).items(), key=lambda item: len(item[0]), reverse=True
    ):
        if not actual or not placeholder:
            raise ValueError("ephemeral path and placeholder must be nonempty")
        canonical = canonical.replace(actual, placeholder)
    lines = [line.rstrip() for line in canonical.splitlines()]
    if drop_git_dirty_warning:
        lines = [line for line in lines if not line.startswith("warning: Git tree ")]
    if drop_nix_progress:
        filtered: list[str] = []
        in_store_path_list = False
        for line in lines:
            if re.fullmatch(
                r"(?:this derivation|these \d+ derivations|these paths) will be (?:built|fetched):",
                line,
            ):
                in_store_path_list = True
                continue
            if in_store_path_list and re.fullmatch(r"  /nix/store/\S+", line):
                continue
            in_store_path_list = False
            if re.fullmatch(r"(?:building|copying path) '/nix/store/[^']+'(?: from '\S+')?\.\.\.", line):
                continue
            filtered.append(line)
        lines = filtered
    return "\n".join(lines)


def _canonical_execution_evidence(
    command: list[str],
    result: subprocess.CompletedProcess[str],
    ephemeral_paths: dict[str, str] | None = None,
) -> tuple[str, bytes]:
    canonical_command = _canonicalize_execution_text(
        shlex.join(command), ephemeral_paths
    )
    canonical_stdout = _canonicalize_execution_text(
        result.stdout, ephemeral_paths, drop_git_dirty_warning=True
    )
    canonical_stderr = _canonicalize_execution_text(
        result.stderr,
        ephemeral_paths,
        drop_git_dirty_warning=True,
        drop_nix_progress=True,
    )
    payload_text = (
        f"$ {canonical_command}\n"
        f"exit_code: {result.returncode}\n"
        "--- stdout ---\n"
    )
    if canonical_stdout:
        payload_text += canonical_stdout + "\n"
    payload_text += "--- stderr ---\n"
    if canonical_stderr:
        payload_text += canonical_stderr + "\n"
    return canonical_command, payload_text.encode("utf-8")


def _run_and_log(
    command: list[str],
    *,
    cwd: Path,
    log: Path,
    environment: dict[str, str] | None = None,
    ephemeral_paths: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
    )
    _, payload = _canonical_execution_evidence(command, result, ephemeral_paths)
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
            command,
            cwd=repo_root,
            log=capture_log,
            environment=environment,
            ephemeral_paths={str(temporary_path): "<capture-tmp>"},
        )
        canonical_program_command, _ = _canonical_execution_evidence(
            command, result, {str(temporary_path): "<capture-tmp>"}
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
                "TMPDIR=<capture-tmp>",
                f"PYTHONPATH={shlex.quote(pythonpath)}",
                canonical_program_command,
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


def _build_obsolete_torch_frontier_receipt(repo_root: Path, model: str) -> dict[str, object]:
    if model != "tiny-stories-1m-kev-gpt-exact":
        raise ValueError("this classifier only authenticates tiny-stories-1m-kev-gpt-exact")

    semantic_command = [
        "nix",
        "develop",
        "-c",
        "python",
        "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py",
        "--probe-report",
        "artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json",
    ]
    _run(semantic_command, cwd=repo_root)

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


_SEMANTIC_VERIFIER = "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
_SEMANTIC_REPORT = "artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json"
_PREDECESSOR_FRONTIER_FILE_SHA256 = (
    "b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55"
)
_PREDECESSOR_FRONTIER_SELF_SHA256 = (
    "af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b"
)


def _verify_semantic_gate(repo_root: Path) -> dict[str, object]:
    command = [
        "nix",
        "develop",
        "-c",
        "python",
        _SEMANTIC_VERIFIER,
        "--probe-report",
        _SEMANTIC_REPORT,
    ]
    result = _run(command, cwd=repo_root)
    try:
        evidence = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("semantic verifier did not emit JSON evidence") from error
    if not isinstance(evidence, dict):
        raise RuntimeError("semantic verifier evidence is not an object")
    probe = evidence.get("semantic_probe")
    registered = evidence.get("registered_stage")
    if not isinstance(probe, dict) or probe.get("status") != "accepted":
        raise RuntimeError("semantic verifier did not accept the compiler-backed probe")
    if not isinstance(registered, dict) or registered.get("status") != "accepted":
        raise RuntimeError("semantic verifier did not accept the registered Torch stage")
    return {
        "command": shlex.join(command),
        "status": "accepted",
        "verifier": _SEMANTIC_VERIFIER,
        "verifier_sha256": _sha256(repo_root / _SEMANTIC_VERIFIER),
        "probe_report": _SEMANTIC_REPORT,
        "probe_report_sha256": _sha256(repo_root / _SEMANTIC_REPORT),
        "evidence": evidence,
    }


def _primary_stage_artifact(stage: str, output: Path) -> Path:
    if stage == "pytorch-exported":
        artifact = output / "exported.pt2"
    elif stage in {"torch", "linalg"}:
        artifact = output
    elif stage == "flat-scf":
        artifact = output / "flat.scf.mlir"
    elif stage == "calyx":
        artifact = output / "model.calyx.mlir"
    elif stage == "calyx-native-sv":
        artifact = output / "sv" / "main.sv"
    else:
        artifact = output
    if not artifact.is_file() or artifact.stat().st_size <= 0:
        raise RuntimeError(f"{stage}: registered output has no nonempty primary artifact: {artifact}")
    return artifact


def _control_manifest_failure(
    stage: str,
    manifest: Path,
    upstream_input: Path | None,
    diagnostic: str,
    *,
    residual_artifact: Path | None = None,
    blockers: Path | None = None,
) -> ControlManifestFailure:
    if upstream_input is None or not upstream_input.is_file():
        raise RuntimeError(f"{stage}: control manifest has no preserved upstream input")
    return ControlManifestFailure(
        kind="control_manifest",
        manifest=manifest,
        upstream_input=upstream_input,
        diagnostic=diagnostic,
        residual_artifact=residual_artifact,
        blockers=blockers,
    )


def _normalized_terminal_diagnostic(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    specific = [
        line
        for line in lines
        if re.search(
            r"failed to legalize operation|unhandled operation|LLVM ERROR",
            line,
            re.IGNORECASE,
        )
    ]
    if specific:
        return "\n".join(specific)
    generic = [
        line
        for line in lines
        if re.search(r"\berror:\s", line, re.IGNORECASE)
        and not re.search(
            r"error: (?:builder for|build of|\d+ dependencies of derivation)",
            line,
            re.IGNORECASE,
        )
    ]
    return "\n".join(generic)


_STRONG_ENVIRONMENT_FAILURES = (
    (
        "nix_daemon",
        re.compile(
            r"cannot connect to (?:the )?(?:nix )?daemon|"
            r"cannot connect to socket|daemon-socket|nix daemon is not running",
            re.IGNORECASE,
        ),
    ),
    (
        "permission",
        re.compile(
            r"permission denied|operation not permitted|read-only file system",
            re.IGNORECASE,
        ),
    ),
    (
        "sandbox",
        re.compile(
            r"(?:creating|setting up|initializing).{0,40}sandbox|"
            r"sandbox.{0,40}(?:failed|unavailable|not permitted)|build users group",
            re.IGNORECASE,
        ),
    ),
    (
        "substituter",
        re.compile(
            r"substituter|narinfo|unable to download|failed to fetch|"
            r"connection (?:refused|timed out)|name or service not known",
            re.IGNORECASE,
        ),
    ),
    (
        "nix_store",
        re.compile(
            r"(?:path ['\"]?/nix/store/[^\n]+ is not valid)|"
            r"(?:/nix/store/[^\n]*(?:corrupt|lock file|database|store path))",
            re.IGNORECASE,
        ),
    ),
    (
        "nix_evaluation",
        re.compile(
            r"while evaluating|evaluation aborted|infinite recursion encountered|"
            r"undefined variable|attribute ['\"][^'\"]+['\"] missing|"
            r"flake ['\"]?[^\n]+ does not provide attribute",
            re.IGNORECASE,
        ),
    ),
)
_NIX_WRAPPER_FAILURE_RE = re.compile(
    r"(?:builder for|build of|dependencies of derivation).{0,160}failed|"
    r"failed to produce output path|build command failed before invoking",
    re.IGNORECASE,
)
_INTRINSIC_COMPILER_DIAGNOSTIC_RE = re.compile(
    r"failed to legalize operation|unhandled operation|LLVM ERROR",
    re.IGNORECASE,
)


def _diagnostic_is_compiler_attributed(
    diagnostic: str,
    upstream_input: Path,
    build_command: str | None,
) -> bool:
    """Require the failure to name compiler semantics, its bound input, or bound tool."""

    if _INTRINSIC_COMPILER_DIAGNOSTIC_RE.search(diagnostic):
        return True
    upstream_names = {str(upstream_input), upstream_input.name}
    if any(
        re.search(
            rf"{re.escape(name)}(?:['\"])?[:]\d+:\d+[^\n]*\berror:",
            diagnostic,
            re.IGNORECASE,
        )
        for name in upstream_names
        if name
    ):
        return True
    if build_command:
        tool_names = {
            Path(token.rstrip("'\"),;")).name
            for token in re.findall(r"(?:/[^\s]+/bin/[^\s]+)", build_command)
        }
        tool_names.discard("nix")
        for tool in tool_names:
            if tool and re.search(
                rf"(?:^|\n).*\b{re.escape(tool)}\b[^\n]*(?:error|fatal):|"
                rf"(?:^|\n).*?(?:error|fatal):[^\n]*\b{re.escape(tool)}\b",
                diagnostic,
                re.IGNORECASE,
            ):
                return True
    return False


def _environment_failure_category(
    text: str, *, compiler_attributed: bool
) -> str | None:
    for category, pattern in _STRONG_ENVIRONMENT_FAILURES:
        if pattern.search(text):
            return category
    if not compiler_attributed and _NIX_WRAPPER_FAILURE_RE.search(text):
        return "nix_build_wrapper"
    if not compiler_attributed:
        return "unattributed_nonzero"
    return None


def _normalized_environment_diagnostic(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    failures = [
        line
        for line in lines
        if re.search(
            r"\b(?:error|warning|fatal):|failed|permission denied|"
            r"operation not permitted|cannot connect",
            line,
            re.IGNORECASE,
        )
    ]
    return "\n".join(failures or lines[-1:])


def _classify_registered_result(
    stage: str,
    exit_code: int,
    output: Path,
    upstream_input: Path | None,
    log: Path,
    *,
    build_command: str | None = None,
) -> RegisteredStageResult:
    if exit_code != 0:
        if not log.is_file():
            raise RuntimeError(f"{stage}: nonzero build log does not exist: {log}")
        text = log.read_text(encoding="utf-8", errors="replace")
        diagnostic = _normalized_terminal_diagnostic(text)
        attributed = bool(
            upstream_input is not None
            and upstream_input.is_file()
            and diagnostic
            and _diagnostic_is_compiler_attributed(
                diagnostic, upstream_input, build_command
            )
        )
        environment_category = _environment_failure_category(
            text, compiler_attributed=attributed
        )
        if environment_category is not None:
            environment_diagnostic = _normalized_environment_diagnostic(text)
            if not environment_diagnostic:
                environment_diagnostic = f"nonzero {stage} build without a compiler diagnostic"
            return EnvironmentFailure(
                kind="environment_failure",
                log=log,
                diagnostic=environment_diagnostic,
                category=environment_category,
            )
        if upstream_input is None or not upstream_input.is_file():
            raise RuntimeError(f"{stage}: compiler failure has no preserved upstream input")
        if not diagnostic or not attributed:
            raise RuntimeError(
                f"{stage}: nonzero registered build had no attributable compiler diagnostic"
            )
        operation_match = re.search(
            r"failed to legalize operation\s+['\"]([^'\"]+)['\"]"
            r"(?:\s*:\s*([^\n]+))?",
            diagnostic,
            re.IGNORECASE,
        )
        return CompilerFailure(
            kind="compiler_failure",
            upstream_input=upstream_input,
            log=log,
            diagnostic=diagnostic,
            operation=operation_match.group(1) if operation_match else None,
            types=operation_match.group(2).strip()
            if operation_match and operation_match.group(2)
            else None,
        )

    manifest = output / "manifest.json" if output.is_dir() else None
    if (
        stage in {"scf", "flat-scf", "calyx", "calyx-native-sv"}
        and manifest is not None
        and manifest.is_file()
    ):
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return _control_manifest_failure(
                stage,
                manifest,
                upstream_input,
                f"error: {stage} manifest is invalid JSON: {error.msg}",
            )
        if not isinstance(value, dict):
            return _control_manifest_failure(
                stage,
                manifest,
                upstream_input,
                f"error: {stage} manifest is not an object",
            )
        manifest_stage = value.get("stage")
        status = value.get("status")
        reason = value.get("reason")
        if status == "completed-with-residuals":
            if (
                stage != "flat-scf"
                or set(value) != {"artifact", "blockers", "stage", "status"}
                or manifest_stage != "flat-scf"
                or reason is not None
                or value.get("artifact") != "flat.scf.mlir"
                or value.get("blockers") != "blockers.json"
            ):
                return _control_manifest_failure(
                    stage,
                    manifest,
                    upstream_input,
                    f"error: registered {stage} residual manifest contract mismatch",
                )
            residual_artifact = output / "flat.scf.mlir"
            blockers = output / "blockers.json"
            if not residual_artifact.is_file() or residual_artifact.stat().st_size <= 0:
                raise RuntimeError(
                    "flat-scf: completed-with-residuals output has no nonempty flat.scf.mlir"
                )
            if not blockers.is_file() or blockers.stat().st_size <= 0:
                raise RuntimeError(
                    "flat-scf: completed-with-residuals output has no nonempty blockers.json"
                )
            return _control_manifest_failure(
                stage,
                manifest,
                upstream_input,
                (
                    "error: registered flat-scf stage completed with residuals; "
                    "artifact remains rejected"
                ),
                residual_artifact=residual_artifact,
                blockers=blockers,
            )
        if manifest_stage != stage or status != "ok" or reason is not None:
            return _control_manifest_failure(
                stage,
                manifest,
                upstream_input,
                (
                    f"error: registered {stage} manifest contract mismatch: "
                    f"stage={manifest_stage!r}, status={status!r}, "
                    f"reason={reason if reason is not None else 'no reason recorded'}"
                ),
            )
        artifact = _primary_stage_artifact(stage, output)
        declared_artifact = value.get("artifact")
        if declared_artifact is not None and output / str(declared_artifact) != artifact:
            return _control_manifest_failure(
                stage,
                manifest,
                upstream_input,
                f"error: registered {stage} manifest names the wrong primary artifact",
            )
        return AcceptedStageResult(kind="accepted", artifact=artifact, output=output)

    if stage in {"flat-scf", "calyx", "calyx-native-sv"} and output.is_dir():
        raise RuntimeError(f"{stage}: registered output has no valid manifest")
    artifact = _primary_stage_artifact(stage, output)
    return AcceptedStageResult(kind="accepted", artifact=artifact, output=output)


def _manifest_diagnostic(stage: str, output: Path) -> tuple[Path | None, str | None]:
    if stage not in {"scf", "flat-scf", "calyx", "calyx-native-sv"}:
        return None, None
    manifest = output / "manifest.json" if output.is_dir() else None
    if manifest is None or not manifest.is_file():
        return None, None
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return manifest, f"error: {stage} manifest is invalid JSON: {error.msg}"
    if not isinstance(value, dict):
        return manifest, f"error: {stage} manifest is not an object"
    status = value.get("status")
    if status == "ok":
        return manifest, None
    reason = value.get("reason", "no reason recorded")
    return manifest, f"error: registered {stage} stage status is {status!r}: {reason}"


def _append_classifier_diagnostic(log: Path, diagnostic: str) -> None:
    payload = log.read_bytes()
    if payload and not payload.endswith(b"\n"):
        payload += b"\n"
    log.write_bytes(payload + f"--- classifier validation ---\n{diagnostic}\n".encode())


def _capture_full_input(source: Path, destination: Path) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    byte_count = 0
    with source.open("rb") as input_stream, destination.open("wb") as raw_archive:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_archive, mtime=0) as archive:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                byte_count += len(chunk)
                digest.update(chunk)
                archive.write(chunk)
    return byte_count, digest.hexdigest()


def _evidence_binding(path: Path, canonical_path: str) -> dict[str, object]:
    return {
        "path": canonical_path,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _mlir_reduce_for_build_command(build_command: str) -> Path | None:
    optimizers = [
        Path(value.rstrip("'\"),;"))
        for value in re.findall(
            r"/nix/store/[A-Za-z0-9+._?=-]+/bin/mlir-opt", build_command
        )
    ]
    reducers = sorted({optimizer.with_name("mlir-reduce") for optimizer in optimizers})
    available = [path for path in reducers if path.is_file()]
    if len(available) > 1:
        raise RuntimeError(f"multiple bound mlir-reduce candidates: {available}")
    return available[0] if available else None


def _run_interestingness(
    script: Path,
    candidate: Path,
    log: Path,
    *,
    repo_root: Path,
    ephemeral_paths: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return _run_and_log(
        [str(script), str(candidate)],
        cwd=repo_root,
        log=log,
        ephemeral_paths=ephemeral_paths,
    )


def _capture_compiler_minimization(
    *,
    repo_root: Path,
    evidence_dir: Path,
    canonical_root: str,
    result: CompilerFailure,
    execution: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object]]:
    """Capture exact interestingness and make one bounded reduction attempt."""

    reduction_log = evidence_dir / "reduction.log"
    try:
        compiler_command, _ = _bind_compiler_command(
            str(execution["derivation_build_command"]), str(result.upstream_input)
        )
    except ValueError:
        reduction_log.write_text(
            "compiler predicate unavailable: unsupported compiler command\n",
            encoding="utf-8",
        )
        return None, {
            "status": "not_practical",
            "reason": "unsupported_compiler_command",
            "reduction_log": _evidence_binding(
                reduction_log, f"{canonical_root}/reduction.log"
            ),
        }
    script = evidence_dir / "interestingness-test.sh"
    _write_interestingness_test(
        script,
        build_command=str(execution["derivation_build_command"]),
        upstream_input=result.upstream_input,
        compiler_exit_nonzero=True,
        expected_diagnostic=result.diagnostic,
        operation=result.operation,
        types=result.types,
    )
    full_log = evidence_dir / "interesting-full.log"
    full_result = _run_interestingness(
        script,
        result.upstream_input,
        full_log,
        repo_root=repo_root,
        ephemeral_paths={
            str(evidence_dir): "<evidence-dir>",
            str(result.upstream_input): "<full-input>",
        },
    )
    interestingness = {
        "compiler_command": compiler_command,
        "test": _evidence_binding(
            script, f"{canonical_root}/interestingness-test.sh"
        ),
        "full_log": _evidence_binding(
            full_log, f"{canonical_root}/interesting-full.log"
        ),
        "compiler_exit_nonzero": True,
        "normalized_terminal_diagnostic": result.diagnostic,
    }
    if full_result.returncode != 0:
        reduction_log.write_text(
            "full input did not satisfy the exact interestingness predicate\n",
            encoding="utf-8",
        )
        return interestingness, {
            "status": "not_practical",
            "reason": "full_input_not_interesting",
            "reduction_log": _evidence_binding(
                reduction_log, f"{canonical_root}/reduction.log"
            ),
        }

    mlir_reduce = _mlir_reduce_for_build_command(
        str(execution["derivation_build_command"])
    )
    if mlir_reduce is None:
        reduction_log.write_text(
            "mlir-reduce is unavailable beside the bound mlir-opt tool\n",
            encoding="utf-8",
        )
        return interestingness, {
            "status": "not_practical",
            "reason": "mlir_reduce_unavailable",
            "reduction_log": _evidence_binding(
                reduction_log, f"{canonical_root}/reduction.log"
            ),
        }

    full_working = evidence_dir / "full-input.mlir"
    shutil.copyfile(result.upstream_input, full_working)
    minimal = evidence_dir / "minimal-reproducer.mlir"
    reduce_command = [
        str(mlir_reduce),
        f"--test={script}",
        str(full_working),
        "-o",
        str(minimal),
    ]
    reduce_result = _run_and_log(
        reduce_command,
        cwd=repo_root,
        log=reduction_log,
        ephemeral_paths={str(evidence_dir): "<evidence-dir>"},
    )
    full_working.unlink()
    reducer_binding = {
        "path": str(mlir_reduce),
        "bytes": mlir_reduce.stat().st_size,
        "sha256": _sha256(mlir_reduce),
    }
    if reduce_result.returncode != 0 or not minimal.is_file():
        if minimal.exists():
            minimal.unlink()
        return interestingness, {
            "status": "not_practical",
            "reason": "reduction_failed",
            "mlir_reduce": reducer_binding,
            "reduction_log": _evidence_binding(
                reduction_log, f"{canonical_root}/reduction.log"
            ),
        }

    reproducer_log = evidence_dir / "interesting-reproducer.log"
    reproducer_result = _run_interestingness(
        script,
        minimal,
        reproducer_log,
        repo_root=repo_root,
        ephemeral_paths={str(evidence_dir): "<evidence-dir>"},
    )
    if reproducer_result.returncode != 0:
        minimal.unlink()
        reproducer_log.unlink()
        return interestingness, {
            "status": "not_practical",
            "reason": "reduction_failed",
            "mlir_reduce": reducer_binding,
            "reduction_log": _evidence_binding(
                reduction_log, f"{canonical_root}/reduction.log"
            ),
        }
    return interestingness, {
        "status": "verified",
        "mlir_reduce": reducer_binding,
        "reduction_log": _evidence_binding(
            reduction_log, f"{canonical_root}/reduction.log"
        ),
        "minimal_reproducer": _evidence_binding(
            minimal, f"{canonical_root}/minimal-reproducer.mlir"
        ),
        "interesting_reproducer_log": _evidence_binding(
            reproducer_log, f"{canonical_root}/interesting-reproducer.log"
        ),
    }


def _run_registered_stage(
    repo_root: Path,
    evidence_dir: Path,
    model: str,
    source_commit: str,
    stage: str,
    upstream: StageRecord | None,
) -> tuple[StageRecord, dict[str, object], RegisteredStageResult]:
    attribute = _registered_attribute(model, stage)
    derivation = _derivation(repo_root, attribute)
    derivation_capture = _capture_derivation_evidence(evidence_dir, stage, derivation)
    command = [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        "-L",
        f".#{attribute}",
    ]
    log = evidence_dir / f"{stage}.log"
    result = _run_and_log(command, cwd=repo_root, log=log)
    output_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("/nix/store/")
    ]
    output = Path(output_lines[0]) if len(output_lines) == 1 else Path(str(derivation["output"]))
    if result.returncode == 0 and str(output) != str(derivation["output"]):
        raise RuntimeError(f"{stage}: build output differs from evaluated derivation")
    registered_result = _classify_registered_result(
        stage=stage,
        exit_code=result.returncode,
        output=output,
        upstream_input=Path(upstream.artifact) if upstream is not None else None,
        log=log,
        build_command=str(derivation["build_command"]),
    )
    if isinstance(registered_result, EnvironmentFailure):
        raise RuntimeError(
            f"{stage}: environment failure invalidates capture "
            f"({registered_result.category}): {registered_result.diagnostic}"
        )
    accepted = isinstance(registered_result, AcceptedStageResult)
    if isinstance(registered_result, AcceptedStageResult):
        artifact = registered_result.artifact
        diagnostic = None
    elif isinstance(registered_result, ControlManifestFailure):
        artifact = registered_result.manifest
        diagnostic = registered_result.diagnostic
        _append_classifier_diagnostic(log, diagnostic)
    else:
        artifact = registered_result.upstream_input
        diagnostic = registered_result.diagnostic
    canonical_log = f"reproducers/{stage}/{stage}.log" if not accepted else f"reproducers/{stage}/{stage}.log"
    artifact_sha256 = _sha256(artifact)
    record = StageRecord(
        stage=stage,
        status="succeeded" if accepted else "compiler_failure",
        artifact=str(artifact),
        artifact_bytes=artifact.stat().st_size,
        artifact_sha256=artifact_sha256,
        artifact_accepted=accepted,
        command=shlex.join(command),
        tool_revisions={
            "evidence_source_commit": source_commit,
            "derivation": str(derivation["path"]),
            "derivation_file_sha256": str(derivation["file_sha256"]),
            "derivation_json_sha256": str(derivation["json_sha256"]),
            "build_command_sha256": str(derivation["build_command_sha256"]),
        },
        log=str(log),
        log_sha256=_sha256(log),
        log_bytes=log.stat().st_size,
        terminal_diagnostics=(diagnostic,) if diagnostic else (),
        upstream_identity=(
            upstream.artifact_sha256
            if upstream is not None
            else "package_manifest_sha256:374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35"
        ),
        exit_code=result.returncode,
    )
    execution = {
        "route_alias": _EXACT_LINALG_ALIAS,
        "frontend": "linalg",
        "backend": "calyx-native-sv",
        "attribute": attribute,
        "invoked": True,
        "command": record.command,
        "exit_code": result.returncode,
        "result": str(output) if result.returncode == 0 else None,
        "artifact": str(artifact),
        "artifact_bytes": record.artifact_bytes,
        "artifact_sha256": artifact_sha256,
        "artifact_accepted": accepted,
        "log": canonical_log,
        "log_bytes": record.log_bytes,
        "log_sha256": record.log_sha256,
        "derivation": derivation["path"],
        "derivation_file_sha256": derivation["file_sha256"],
        "derivation_json_sha256": derivation["json_sha256"],
        "derivation_build_command": derivation["build_command"],
        "derivation_build_command_sha256": derivation["build_command_sha256"],
        "derivation_tool_bindings": _build_command_file_bindings(
            str(derivation["build_command"])
        ),
        **derivation_capture,
    }
    return record, execution, registered_result


def build_current_frontier_receipt(
    repo_root: Path,
    model: str,
    *,
    evidence_dir: Path | None = None,
) -> dict[str, object]:
    """Replay the authenticated registered pipeline and capture its first invalid stage."""

    if model != "tiny-stories-1m-kev-gpt-exact":
        raise ValueError("this classifier only authenticates tiny-stories-1m-kev-gpt-exact")

    semantic_gate = _verify_semantic_gate(repo_root)
    evidence_dir = evidence_dir or (repo_root / "reproducers" / "current")
    evidence_dir.mkdir(parents=True, exist_ok=True)

    export_derivation = _derivation(
        repo_root, _registered_attribute(model, "pytorch-exported")
    )
    torch_derivation = _derivation(repo_root, _registered_attribute(model, "torch"))
    source_identity = _authenticate_pipeline_source(
        repo_root, export_derivation, torch_derivation
    )
    source_commit = str(source_identity["evidence_source_commit"])
    executions: dict[str, dict[str, object]] = {}
    registered_results: dict[str, RegisteredStageResult] = {}

    def execute(stage: str, upstream: StageRecord | None) -> StageRecord:
        record, execution, registered_result = _run_registered_stage(
            repo_root,
            evidence_dir,
            model,
            source_commit,
            stage,
            upstream,
        )
        executions[stage] = execution
        registered_results[stage] = registered_result
        return record

    stage_records = _run_registered_pipeline(execute)
    classification = classify_frontier(stage_records)
    if classification.status == "environment_failure":
        raise RuntimeError("environment failure cannot establish a compiler frontier")

    first_invalid = classification.stage
    canonical_root = f"reproducers/{first_invalid}" if first_invalid else "reproducers/complete"
    for stage, record in zip(_FRONTIERS, stage_records):
        canonical_log = f"{canonical_root}/{stage}.log"
        executions[stage]["log"] = canonical_log
        executions[stage]["captured_derivation"] = (
            f"{canonical_root}/{stage}.drv"
        )
        executions[stage]["captured_derivation_json"] = (
            f"{canonical_root}/{stage}.derivation.json"
        )

    full_input: dict[str, object] | None = None
    frontier_evidence: dict[str, object] | None = None
    if first_invalid is not None:
        failure_index = list(_FRONTIERS).index(first_invalid)
        if failure_index == 0:
            raise RuntimeError("cannot capture a frontier without an upstream stage")
        invalid_result = registered_results[first_invalid]
        if isinstance(invalid_result, AcceptedStageResult):
            raise RuntimeError(f"{first_invalid}: accepted result classified as a frontier")
        upstream_path = invalid_result.upstream_input
        archive = evidence_dir / "full-input.gz"
        content_bytes, content_sha256 = _capture_full_input(upstream_path, archive)
        full_input = {
            "path": f"{canonical_root}/full-input.gz",
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": _sha256(archive),
            "content_bytes": content_bytes,
            "content_sha256": content_sha256,
            "source_stage": stage_records[failure_index - 1].stage,
            "source_artifact": str(upstream_path),
        }
        if isinstance(invalid_result, ControlManifestFailure):
            reproducer = evidence_dir / "minimal-reproducer.json"
            shutil.copyfile(invalid_result.manifest, reproducer)
            residual_artifact_binding = None
            blockers_binding = None
            if invalid_result.residual_artifact is not None:
                residual_artifact = evidence_dir / "flat.scf.mlir"
                blockers = evidence_dir / "blockers.json"
                shutil.copyfile(invalid_result.residual_artifact, residual_artifact)
                if invalid_result.blockers is None:
                    raise RuntimeError("residual control manifest lost blockers path")
                shutil.copyfile(invalid_result.blockers, blockers)
                residual_artifact_binding = _evidence_binding(
                    residual_artifact, f"{canonical_root}/flat.scf.mlir"
                )
                blockers_binding = _evidence_binding(
                    blockers, f"{canonical_root}/blockers.json"
                )
            frontier_evidence = _serialize_frontier_evidence(
                stage=first_invalid,
                result=invalid_result,
                canonical_root=canonical_root,
                manifest_binding=_evidence_binding(
                    reproducer, f"{canonical_root}/minimal-reproducer.json"
                ),
                residual_artifact_binding=residual_artifact_binding,
                blockers_binding=blockers_binding,
            )
        else:
            interestingness, minimization = _capture_compiler_minimization(
                repo_root=repo_root,
                evidence_dir=evidence_dir,
                canonical_root=canonical_root,
                result=invalid_result,
                execution=executions[first_invalid],
            )
            frontier_evidence = _serialize_frontier_evidence(
                stage=first_invalid,
                result=invalid_result,
                canonical_root=canonical_root,
                interestingness=interestingness,
                minimization=minimization,
            )

    decision = json.loads(
        (repo_root / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json").read_text(
            encoding="utf-8"
        )
    )
    not_run = list(_FRONTIERS)[len(stage_records) :]
    receipt: dict[str, object] = {
        "schema": "tinystories-1m-exact-current-pipeline-frontier-v5",
        "model": model,
        "status": classification.status,
        "frontier": classification.frontier,
        "stage": classification.stage,
        "diagnostic": classification.diagnostic,
        "source_commit": source_commit,
        "capture_tools": {
            "classifier": {
                "path": _CLASSIFIER,
                "sha256": _sha256(repo_root / _CLASSIFIER),
            },
            "determinism_verifier": {
                "path": _DETERMINISM_VERIFIER,
                "sha256": _sha256(repo_root / _DETERMINISM_VERIFIER),
            },
        },
        "semantic_gate": semantic_gate,
        "pipeline_source_identity": source_identity,
        "predecessor_receipt": {
            "historical_bundle": "artifacts/comparison/tinystories-1m-exact-frontier-determinism",
            "file_sha256": _PREDECESSOR_FRONTIER_FILE_SHA256,
            "self_sha256": _PREDECESSOR_FRONTIER_SELF_SHA256,
        },
        "frozen_task_1_through_3_identities": decision["identity_hashes"],
        "task_2_decision_self_sha256": decision["sha256"],
        "stages": [
            {
                **asdict(record),
                "log": f"{canonical_root}/{record.stage}.log",
            }
            for record in stage_records
        ],
        "registered_build_execution": executions,
        "pipeline_execution": {
            "registered_order": list(_FRONTIERS),
            "first_invalid_stage": first_invalid,
            "stopped_after_first_invalid_stage": first_invalid is not None,
            "not_run": not_run,
        },
        "full_failing_input": full_input,
        "frontier_evidence": frontier_evidence,
        "claims": {
            "calyx_native_sv": classification.status == "complete",
            "syntax_validated": False,
            "synthesis_validated": False,
            "board_inference": False,
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
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    receipt = build_current_frontier_receipt(
        repo_root, args.model, evidence_dir=args.evidence_dir
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
