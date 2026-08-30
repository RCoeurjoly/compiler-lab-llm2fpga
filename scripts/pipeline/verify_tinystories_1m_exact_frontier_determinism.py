#!/usr/bin/env python3
"""Verify the two preserved live Task 5 determinism evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def _verify_run(
    bundle_root: Path,
    run_name: str,
    run_manifest: dict[str, Any],
    canonical_files: list[str],
    source_commit: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    run_root = bundle_root / run_name
    _require(run_root.is_dir(), f"missing preserved run directory: {run_name}")
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


def verify_determinism_bundles(bundle_root: Path) -> dict[str, Any]:
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
        isinstance(canonical_files, list)
        and all(isinstance(item, str) for item in canonical_files),
        "canonical file list missing",
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


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_bundle = (
        repo_root
        / "artifacts"
        / "comparison"
        / "tinystories-1m-exact-frontier-determinism"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, default=default_bundle)
    args = parser.parse_args()
    print(json.dumps(verify_determinism_bundles(args.bundle_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
