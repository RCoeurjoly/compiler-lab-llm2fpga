#!/usr/bin/env python3
"""Fail-closed, hash-bound SCF-to-Calyx execution for exact TinyStories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


DIAGNOSTIC_PATTERNS = (
    re.compile(r"error:", re.IGNORECASE),
    re.compile(r"failed to legalize operation", re.IGNORECASE),
    re.compile(r"unhandled operation", re.IGNORECASE),
    re.compile(r"llvm error", re.IGNORECASE),
)
MAIN_COMPONENT = re.compile(
    r"^\s*calyx\.component\s+@main(?:\s|\(|\{|$)", re.MULTILINE
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _binding(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.name, "bytes": len(data), "sha256": _sha256_bytes(data)}


def _first_diagnostic(log: bytes) -> str | None:
    for raw_line in log.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line and any(pattern.search(line) for pattern in DIAGNOSTIC_PATTERNS):
            return line
    return None


def _tool_identity(circt_opt: Path) -> dict[str, object]:
    identity: dict[str, object] = _binding(circt_opt)
    version = subprocess.run(
        [str(circt_opt), "--version"], check=False, capture_output=True
    )
    identity["version_exit_code"] = version.returncode
    identity["version"] = (version.stdout + version.stderr).decode(
        "utf-8", errors="replace"
    ).strip()
    return identity


def validate_predecessor(
    predecessor: Path, expected_prepared_sha256: str, expected_receipt_sha256: str
) -> dict[str, object]:
    """Validate the exact approved pre-Calyx package before lowering it."""
    manifest_path = predecessor / "manifest.json"
    prepared = predecessor / "pre-calyx.mlir"
    receipt = predecessor / "pre-calyx-legality.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid predecessor manifest: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("calyx_authorized") is not True:
        raise ValueError("predecessor calyx_authorized must be true")
    try:
        prepared_sha256 = _sha256_bytes(prepared.read_bytes())
    except OSError as error:
        raise ValueError(f"missing predecessor prepared artifact: {error}") from error
    if prepared_sha256 != expected_prepared_sha256:
        raise ValueError("predecessor prepared SHA-256 mismatch")
    try:
        receipt_document = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid predecessor receipt: {error}") from error
    if not isinstance(receipt_document, dict):
        raise ValueError("predecessor receipt must be a JSON object")
    receipt_self_hash = receipt_document.get("sha256")
    if receipt_self_hash != expected_receipt_sha256:
        raise ValueError("predecessor receipt SHA-256 mismatch")
    unsigned_receipt = {
        key: value for key, value in receipt_document.items() if key != "sha256"
    }
    if _sha256_bytes(_canonical_json(unsigned_receipt)) != receipt_self_hash:
        raise ValueError("predecessor receipt self-hash mismatch")
    return {
        "manifest": manifest,
        "prepared": _binding(prepared),
        "receipt": {**_binding(receipt), "self_sha256": receipt_self_hash},
    }


def _write_manifest(output_dir: Path, manifest: dict[str, object]) -> dict[str, object]:
    unsigned = {key: value for key, value in manifest.items() if key != "sha256"}
    manifest["sha256"] = _sha256_bytes(_canonical_json(unsigned))
    (output_dir / "manifest.json").write_bytes(_canonical_json(manifest) + b"\n")
    return manifest


def validate_stage_output(output_dir: Path) -> dict[str, object]:
    """Enforce the diagnostic-package artifact contract at the Nix boundary."""
    manifest_path = output_dir / "manifest.json"
    log_path = output_dir / "lower-scf-to-calyx.log"
    model = output_dir / "model.calyx.mlir"
    partial = output_dir / "partial.calyx.mlir"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid stage manifest: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("stage") != "calyx":
        raise ValueError("stage manifest must identify calyx")
    if not log_path.is_file():
        raise ValueError("stage log is missing")
    status = manifest.get("status")
    partial_binding = manifest.get("partial_artifact")
    if status == "ok":
        if manifest.get("artifact_accepted") is not True or not model.is_file():
            raise ValueError("accepted stage is missing model.calyx.mlir")
        if partial.exists() or partial_binding is not None:
            raise ValueError("accepted stage must not retain a partial artifact")
    elif status == "failed":
        if manifest.get("artifact_accepted") is not False or model.exists():
            raise ValueError("failed stage must not retain model.calyx.mlir")
        if partial_binding is None:
            if partial.exists():
                raise ValueError("artifactless failed stage must not retain partial.calyx.mlir")
        elif not partial.is_file():
            raise ValueError("failed stage declares a missing partial artifact")
    else:
        raise ValueError("stage manifest has invalid status")
    return manifest


def run_calyx(input_path: Path, output_dir: Path, circt_opt: Path) -> dict[str, object]:
    """Lower one approved MLIR input and accept only a parsed main component."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "model.calyx.mlir",
        "partial.calyx.mlir",
        "manifest.json",
        "lower-scf-to-calyx.log",
        ".candidate.calyx.mlir",
        ".parsed.calyx.mlir",
    ):
        path = output_dir / name
        if path.exists():
            if not path.is_file():
                raise ValueError(f"stage output path is not a file: {path}")
            path.unlink()
    candidate = output_dir / ".candidate.calyx.mlir"
    parsed_candidate = output_dir / ".parsed.calyx.mlir"
    log_path = output_dir / "lower-scf-to-calyx.log"
    command = [
        str(circt_opt),
        str(input_path),
        "--lower-scf-to-calyx=top-level-function=main",
        "-o",
        str(candidate),
    ]
    completed = subprocess.run(command, check=False, capture_output=True)
    log = completed.stdout + completed.stderr
    log_path.write_bytes(log)

    diagnostic = _first_diagnostic(log)
    candidate_is_nonempty = candidate.is_file() and candidate.stat().st_size > 0
    parse_exit_code: int | None = None
    has_main_component = False
    if candidate_is_nonempty:
        parsed = subprocess.run(
            [str(circt_opt), str(candidate), "-o", str(parsed_candidate)],
            check=False,
            capture_output=True,
        )
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
    accepted = diagnostic is None
    artifact: dict[str, object] | None = None
    partial: dict[str, object] | None = None
    if candidate_is_nonempty:
        destination = output_dir / ("model.calyx.mlir" if accepted else "partial.calyx.mlir")
        candidate.replace(destination)
        artifact_binding = _binding(destination)
        if accepted:
            artifact = artifact_binding
        else:
            partial = artifact_binding
    elif candidate.exists():
        candidate.unlink()
    if parsed_candidate.exists():
        parsed_candidate.unlink()

    manifest: dict[str, object] = {
        "schema": "tinystories-1m-exact-calyx-stage-v1",
        "stage": "calyx",
        "status": "ok" if accepted else "failed",
        "artifact_accepted": accepted,
        "first_diagnostic": diagnostic,
        "exit_code": completed.returncode,
        "parse_exit_code": parse_exit_code,
        "command": command,
        "input": _binding(input_path),
        "log": _binding(log_path),
        "circt_opt": _tool_identity(circt_opt),
        "derivation": os.environ.get("NIX_DERIVATION", ""),
        "artifact": artifact,
        "partial_artifact": partial,
    }
    return _write_manifest(output_dir, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--circt-opt", type=Path)
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--expected-prepared-sha256")
    parser.add_argument("--expected-receipt-sha256")
    parser.add_argument("--validate-predecessor", type=Path)
    parser.add_argument("--validate-output", type=Path)
    args = parser.parse_args()
    if args.validate_predecessor is not None:
        if args.expected_prepared_sha256 is None or args.expected_receipt_sha256 is None:
            parser.error("predecessor validation requires both expected hashes")
        validate_predecessor(
            args.validate_predecessor,
            args.expected_prepared_sha256,
            args.expected_receipt_sha256,
        )
        return
    if args.validate_output is not None:
        validate_stage_output(args.validate_output)
        return
    if args.input is None or args.output is None or args.circt_opt is None:
        parser.error("--input, --output, and --circt-opt are required to run Calyx")
    supplied_predecessor_values = (
        args.predecessor,
        args.expected_prepared_sha256,
        args.expected_receipt_sha256,
    )
    if any(value is not None for value in supplied_predecessor_values):
        if any(value is None for value in supplied_predecessor_values):
            parser.error("predecessor validation requires all predecessor hash arguments")
        validate_predecessor(
            args.predecessor, args.expected_prepared_sha256, args.expected_receipt_sha256
        )
    run_calyx(args.input, args.output, args.circt_opt)


if __name__ == "__main__":
    main()
