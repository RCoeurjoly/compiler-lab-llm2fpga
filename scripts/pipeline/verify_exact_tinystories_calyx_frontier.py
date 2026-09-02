#!/usr/bin/env python3
"""Independently verify and replay the exact TinyStories Calyx stage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


EXPECTED_PREPARED_SHA256 = (
    "54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31"
)
EXPECTED_RECEIPT_SELF_SHA256 = (
    "451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30"
)
EXPECTED_CIRCT_OPT_PATH = (
    "/nix/store/b9p48l2nrw1c6zncc6f86jd9nr611x7z-"
    "circt-1.144.0g20260331_5dc62fe/bin/circt-opt"
)
EXPECTED_CIRCT_OPT_SHA256 = (
    "087732aac4608ed45effd1d7a81e032791e40a2a11ffff1a75b7031cb69eb2c7"
)
LOWERING_OPTION = "--lower-scf-to-calyx=top-level-function=main"
DIAGNOSTIC_PATTERNS = (
    re.compile(r"error:", re.IGNORECASE),
    re.compile(r"failed to legalize operation", re.IGNORECASE),
    re.compile(r"unhandled operation", re.IGNORECASE),
    re.compile(r"llvm error", re.IGNORECASE),
)
MAIN_COMPONENT = re.compile(
    r"^\s*calyx\.component\s+@main(?:\s|\(|\{|$)", re.MULTILINE
)
DEFAULT_REPRODUCER_DIR = (
    Path(__file__).resolve().parents[2]
    / "reproducers/tinystories-1m-exact-calyx-frontier"
)
MINIMIZATION_SCHEMA = "tinystories-1m-exact-calyx-minimization-v1"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _binding(path: Path, *, recorded_path: str | None = None) -> dict[str, object]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValueError(f"missing bound file {path}: {error}") from error
    return {
        "path": recorded_path if recorded_path is not None else path.name,
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {description}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _self_hash(value: dict[str, Any]) -> str:
    unsigned = {key: item for key, item in value.items() if key != "sha256"}
    return _sha256_bytes(_canonical_json(unsigned))


def _normalize_diagnostic(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _first_diagnostic(log: bytes) -> str | None:
    for raw_line in log.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line and any(pattern.search(line) for pattern in DIAGNOSTIC_PATTERNS):
            return _normalize_diagnostic(line)
    return None


def _require_binding(
    declared: object, actual_path: Path, description: str
) -> dict[str, object]:
    if not isinstance(declared, dict):
        raise ValueError(f"{description} binding is missing")
    actual = _binding(actual_path)
    if declared.get("path") != actual["path"]:
        raise ValueError(f"{description} path mismatch")
    if declared.get("bytes") != actual["bytes"]:
        raise ValueError(f"{description} byte count mismatch")
    if declared.get("sha256") != actual["sha256"]:
        raise ValueError(f"{description} SHA-256 mismatch")
    return actual


def _require_reproducer_binding(
    reproducer_dir: Path, declared: object, description: str
) -> dict[str, object]:
    if not isinstance(declared, dict):
        raise ValueError(f"{description} binding is missing")
    recorded_path = declared.get("path")
    if not isinstance(recorded_path, str) or Path(recorded_path).name != recorded_path:
        raise ValueError(f"{description} path mismatch")
    return _require_binding(declared, reproducer_dir / recorded_path, description)


def _validate_predecessor(predecessor: Path) -> dict[str, object]:
    manifest_path = predecessor / "manifest.json"
    input_path = predecessor / "pre-calyx.mlir"
    receipt_path = predecessor / "pre-calyx-legality.json"
    manifest = _read_object(manifest_path, "predecessor manifest")
    receipt = _read_object(receipt_path, "predecessor receipt")
    if manifest.get("calyx_authorized") is not True:
        raise ValueError("predecessor calyx_authorized must be true")
    input_binding = _binding(input_path)
    if input_binding["sha256"] != EXPECTED_PREPARED_SHA256:
        raise ValueError("predecessor input SHA-256 mismatch")
    receipt_self_sha256 = receipt.get("sha256")
    if receipt_self_sha256 != EXPECTED_RECEIPT_SELF_SHA256:
        raise ValueError("predecessor receipt SHA-256 mismatch")
    if receipt_self_sha256 != _self_hash(receipt):
        raise ValueError("predecessor receipt self-hash mismatch")
    if receipt.get("status") != "ok":
        raise ValueError("predecessor receipt status is not ok")

    preparation = manifest.get("preparation")
    if not isinstance(preparation, dict):
        raise ValueError("predecessor preparation binding is missing")
    declared_input = preparation.get("output")
    if declared_input != input_binding:
        raise ValueError("predecessor manifest input binding mismatch")
    legality = preparation.get("legality")
    if not isinstance(legality, dict):
        raise ValueError("predecessor legality binding is missing")
    receipt_file_binding = _binding(receipt_path)
    if legality.get("path") != receipt_file_binding["path"]:
        raise ValueError("predecessor legality path mismatch")
    if legality.get("sha256") != receipt_file_binding["sha256"]:
        raise ValueError("predecessor legality file SHA-256 mismatch")
    if legality.get("receipt_sha256") != receipt_self_sha256:
        raise ValueError("predecessor legality receipt SHA-256 mismatch")
    if legality.get("status") != "ok":
        raise ValueError("predecessor legality status is not ok")
    return {
        "package": str(predecessor.resolve()),
        "manifest": _binding(manifest_path),
        "input": input_binding,
        "legality_receipt": {
            **receipt_file_binding,
            "self_sha256": receipt_self_sha256,
        },
    }


def _validate_minimization(
    predecessor: Path, first_diagnostic: str | None
) -> dict[str, object]:
    receipt_path = DEFAULT_REPRODUCER_DIR / "minimization.json"
    if not receipt_path.is_file():
        return {"status": "not_attempted"}

    minimization = _read_object(receipt_path, "minimization receipt")
    if minimization.get("sha256") != _self_hash(minimization):
        raise ValueError("minimization receipt self-hash mismatch")
    if minimization.get("schema") != MINIMIZATION_SCHEMA:
        raise ValueError("minimization receipt schema mismatch")
    if _normalize_diagnostic(minimization.get("first_diagnostic")) != first_diagnostic:
        raise ValueError("minimization diagnostic mismatch")
    if not isinstance(minimization.get("command"), list):
        raise ValueError("minimization command is missing")
    elapsed = minimization.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or elapsed < 0:
        raise ValueError("minimization elapsed_seconds is invalid")
    _require_binding(
        minimization.get("full_input"),
        predecessor / "pre-calyx.mlir",
        "minimization full input",
    )
    _require_reproducer_binding(
        DEFAULT_REPRODUCER_DIR,
        minimization.get("reducer_log"),
        "minimization reducer log",
    )
    if minimization.get("status") == "not_practical":
        if minimization.get("minimal_reproducer") is not None:
            raise ValueError("not_practical minimization must not bind a minimal reproducer")
        return minimization
    if minimization.get("status") == "reduced":
        _require_reproducer_binding(
            DEFAULT_REPRODUCER_DIR,
            minimization.get("interesting_script"),
            "minimization interesting script",
        )
        minimal = _require_reproducer_binding(
            DEFAULT_REPRODUCER_DIR,
            minimization.get("minimal_reproducer"),
            "minimal reproducer",
        )
        script = DEFAULT_REPRODUCER_DIR / str(
            minimization["interesting_script"]["path"]
        )
        completed = subprocess.run(
            [str(script), str(DEFAULT_REPRODUCER_DIR / str(minimal["path"]))],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise ValueError("minimal reproducer is not interesting")
        return minimization
    raise ValueError("minimization status is invalid")


def _validate_tool(
    command: list[object], declared: object
) -> tuple[Path, dict[str, object]]:
    if not command or not isinstance(command[0], str):
        raise ValueError("command does not identify circt-opt")
    tool = Path(command[0])
    if str(tool.resolve()) != str(Path(EXPECTED_CIRCT_OPT_PATH).resolve()):
        raise ValueError("pinned circt-opt path mismatch")
    if not isinstance(declared, dict):
        raise ValueError("tool binding is missing")
    actual = _binding(tool)
    if actual["sha256"] != EXPECTED_CIRCT_OPT_SHA256:
        raise ValueError("pinned tool SHA-256 mismatch")
    if declared.get("path") != actual["path"]:
        raise ValueError("tool path mismatch")
    if declared.get("bytes") != actual["bytes"]:
        raise ValueError("tool byte count mismatch")
    if declared.get("sha256") != actual["sha256"]:
        raise ValueError("tool SHA-256 mismatch")
    try:
        version = subprocess.run(
            [str(tool), "--version"], check=False, capture_output=True
        )
    except OSError as error:
        raise ValueError(f"environment failure executing pinned circt-opt: {error}") from error
    version_text = (version.stdout + version.stderr).decode(
        "utf-8", errors="replace"
    ).strip()
    if declared.get("version_exit_code") != version.returncode:
        raise ValueError("tool version exit code mismatch")
    if declared.get("version") != version_text:
        raise ValueError("tool version mismatch")
    return tool, {
        **actual,
        "canonical_path": str(tool.resolve()),
        "version_exit_code": version.returncode,
        "version": version_text,
    }


def _classify_execution(
    tool: Path, input_path: Path, candidate: Path
) -> dict[str, object]:
    command = [str(tool), str(input_path), LOWERING_OPTION, "-o", str(candidate)]
    try:
        completed = subprocess.run(command, check=False, capture_output=True)
    except OSError as error:
        raise ValueError(f"environment failure replaying circt-opt: {error}") from error
    log = completed.stdout + completed.stderr
    diagnostic = _first_diagnostic(log)
    candidate_is_nonempty = candidate.is_file() and candidate.stat().st_size > 0
    parse_exit_code: int | None = None
    has_main_component = False
    if candidate_is_nonempty:
        parsed_candidate = candidate.with_name("parsed.calyx.mlir")
        try:
            parsed = subprocess.run(
                [str(tool), str(candidate), "-o", str(parsed_candidate)],
                check=False,
                capture_output=True,
            )
        except OSError as error:
            raise ValueError(
                f"environment failure parsing replay candidate: {error}"
            ) from error
        parse_exit_code = parsed.returncode
        if parsed.returncode == 0 and parsed_candidate.is_file():
            has_main_component = MAIN_COMPONENT.search(
                parsed_candidate.read_text(encoding="utf-8", errors="replace")
            ) is not None

    if diagnostic is None and completed.returncode != 0:
        diagnostic = f"circt-opt exited with status {completed.returncode}"
    if diagnostic is None and not candidate_is_nonempty:
        diagnostic = "Calyx lowering produced empty output"
    if diagnostic is None and parse_exit_code != 0:
        diagnostic = "Calyx candidate failed to parse"
    if diagnostic is None and not has_main_component:
        diagnostic = "Calyx candidate does not define calyx.component @main"
    status = "ok" if diagnostic is None else "failed"
    candidate_binding = _binding(candidate) if candidate_is_nonempty else None
    return {
        "status": status,
        "first_diagnostic": diagnostic,
        "exit_code": completed.returncode,
        "parse_exit_code": parse_exit_code,
        "log_classification": (
            "terminal_diagnostic" if _first_diagnostic(log) is not None else "clean"
        ),
        "candidate": candidate_binding,
    }


def _validate_stage_bundle(
    bundle: Path, predecessor: Path
) -> tuple[dict[str, Any], Path, dict[str, object], dict[str, object] | None]:
    manifest_path = bundle / "manifest.json"
    log_path = bundle / "lower-scf-to-calyx.log"
    manifest = _read_object(manifest_path, "stage receipt")
    if manifest.get("sha256") != _self_hash(manifest):
        raise ValueError("receipt self-hash mismatch")
    if manifest.get("schema") != "tinystories-1m-exact-calyx-stage-v1":
        raise ValueError("stage receipt schema mismatch")
    if manifest.get("stage") != "calyx":
        raise ValueError("stage receipt must identify calyx")
    if str(Path(str(manifest.get("derivation"))).resolve()) != str(bundle.resolve()):
        raise ValueError("stage derivation identity mismatch")

    command = manifest.get("command")
    if not isinstance(command, list):
        raise ValueError("stage command is missing")
    tool, tool_binding = _validate_tool(command, manifest.get("circt_opt"))
    expected_command = [
        str(tool),
        str((predecessor / "pre-calyx.mlir").resolve()),
        LOWERING_OPTION,
        "-o",
        str(bundle.resolve() / ".candidate.calyx.mlir"),
    ]
    normalized_command = [
        str(Path(item).resolve()) if index in (0, 1, 4) else item
        for index, item in enumerate(command)
    ]
    if normalized_command != expected_command:
        raise ValueError("command mismatch")

    actual_input = _require_binding(
        manifest.get("input"), predecessor / "pre-calyx.mlir", "input"
    )
    if actual_input["sha256"] != EXPECTED_PREPARED_SHA256:
        raise ValueError("input SHA-256 mismatch")
    actual_log = _require_binding(manifest.get("log"), log_path, "log")
    log = log_path.read_bytes()
    classified_diagnostic = _first_diagnostic(log)
    declared_diagnostic = _normalize_diagnostic(manifest.get("first_diagnostic"))
    if declared_diagnostic != classified_diagnostic:
        if not (
            classified_diagnostic is None
            and declared_diagnostic
            in {
                f"circt-opt exited with status {manifest.get('exit_code')}",
                "Calyx lowering produced empty output",
                "Calyx candidate failed to parse",
                "Calyx candidate does not define calyx.component @main",
            }
        ):
            raise ValueError("diagnostic differs from log")

    status = manifest.get("status")
    accepted = manifest.get("artifact_accepted")
    artifact_binding: dict[str, object] | None
    if status == "ok":
        if accepted is not True:
            raise ValueError("result status mismatch: ok result is not accepted")
        if declared_diagnostic is not None:
            raise ValueError("result status mismatch: ok result has a diagnostic")
        artifact_binding = _require_binding(
            manifest.get("artifact"), bundle / "model.calyx.mlir", "Calyx artifact"
        )
        if manifest.get("partial_artifact") is not None or (
            bundle / "partial.calyx.mlir"
        ).exists():
            raise ValueError("result status mismatch: ok result retains partial artifact")
    elif status == "failed":
        if accepted is not False:
            raise ValueError("result status mismatch: failed result is accepted")
        if manifest.get("artifact") is not None or (bundle / "model.calyx.mlir").exists():
            raise ValueError("result status mismatch: failed result retains Calyx artifact")
        partial_declared = manifest.get("partial_artifact")
        if partial_declared is None:
            if (bundle / "partial.calyx.mlir").exists():
                raise ValueError("partial artifact binding is missing")
            artifact_binding = None
        else:
            artifact_binding = _require_binding(
                partial_declared,
                bundle / "partial.calyx.mlir",
                "partial artifact",
            )
    else:
        raise ValueError("result status mismatch: invalid stage status")
    return manifest, tool, {**actual_log, "classification": (
        "terminal_diagnostic" if classified_diagnostic is not None else "clean"
    )}, artifact_binding


def _compare_replay(
    manifest: dict[str, Any], log_binding: dict[str, object], replay: dict[str, object]
) -> None:
    declared_candidate = (
        manifest.get("artifact")
        if manifest.get("status") == "ok"
        else manifest.get("partial_artifact")
    )
    declared_candidate_sha256 = (
        declared_candidate.get("sha256")
        if isinstance(declared_candidate, dict)
        else None
    )
    replay_candidate = replay.get("candidate")
    replay_candidate_sha256 = (
        replay_candidate.get("sha256") if isinstance(replay_candidate, dict) else None
    )
    expected = {
        "status": manifest.get("status"),
        "first_diagnostic": _normalize_diagnostic(manifest.get("first_diagnostic")),
        "exit_code": manifest.get("exit_code"),
        "parse_exit_code": manifest.get("parse_exit_code"),
        "log_classification": log_binding.get("classification"),
        "candidate_sha256": declared_candidate_sha256,
    }
    observed = {
        "status": replay.get("status"),
        "first_diagnostic": replay.get("first_diagnostic"),
        "exit_code": replay.get("exit_code"),
        "parse_exit_code": replay.get("parse_exit_code"),
        "log_classification": replay.get("log_classification"),
        "candidate_sha256": replay_candidate_sha256,
    }
    if observed != expected:
        raise ValueError(
            "replay result differs: "
            + json.dumps({"expected": expected, "observed": observed}, sort_keys=True)
        )


def verify_bundle(bundle: Path, predecessor: Path) -> dict[str, object]:
    """Authenticate one stage bundle and independently replay its exact command."""
    bundle = bundle.resolve()
    predecessor = predecessor.resolve()
    predecessor_binding = _validate_predecessor(predecessor)
    manifest, tool, log_binding, result_candidate = _validate_stage_bundle(
        bundle, predecessor
    )
    with tempfile.TemporaryDirectory(prefix="exact-calyx-replay-") as temporary:
        replay_candidate = Path(temporary) / "candidate.calyx.mlir"
        replay = _classify_execution(
            tool, predecessor / "pre-calyx.mlir", replay_candidate
        )
    _compare_replay(manifest, log_binding, replay)

    stage_manifest_path = bundle / "manifest.json"
    stage_receipt = {
        **_binding(stage_manifest_path),
        "self_sha256": manifest["sha256"],
    }
    replay_receipt = {
        "status": "verified",
        "command": [
            str(tool),
            str(predecessor / "pre-calyx.mlir"),
            LOWERING_OPTION,
            "-o",
            "$REPLAY_DIR/candidate.calyx.mlir",
        ],
        "observed": {
            key: replay[key]
            for key in (
                "status",
                "first_diagnostic",
                "exit_code",
                "parse_exit_code",
                "log_classification",
                "candidate",
            )
        },
    }
    if manifest["status"] == "ok":
        receipt: dict[str, object] = {
            "schema": "tinystories-1m-exact-calyx-frontier-v1",
            "status": "complete",
            "frontier": None,
            "first_diagnostic": None,
            "predecessor": predecessor_binding,
            "stage": {
                "package": str(bundle),
                "manifest": stage_receipt,
                "command": manifest["command"],
                "tool": {
                    **manifest["circt_opt"],
                    "canonical_path": str(tool),
                },
                "log": log_binding,
            },
            "replay": replay_receipt,
            "calyx_artifact": result_candidate,
            "rejected_candidate": None,
            "minimization": None,
        }
    else:
        minimization = _validate_minimization(
            predecessor, _normalize_diagnostic(manifest["first_diagnostic"])
        )
        receipt = {
            "schema": "tinystories-1m-exact-calyx-frontier-v1",
            "status": "compiler_frontier",
            "frontier": "calyx_frontier",
            "first_diagnostic": _normalize_diagnostic(manifest["first_diagnostic"]),
            "predecessor": predecessor_binding,
            "stage": {
                "package": str(bundle),
                "manifest": stage_receipt,
                "command": manifest["command"],
                "tool": {
                    **manifest["circt_opt"],
                    "canonical_path": str(tool),
                },
                "log": log_binding,
            },
            "replay": replay_receipt,
            "calyx_artifact": None,
            "rejected_candidate": result_candidate,
            "minimization": minimization,
        }
    receipt["sha256"] = _self_hash(receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify_bundle(args.bundle, args.predecessor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_canonical_json(receipt) + b"\n")


if __name__ == "__main__":
    main()
