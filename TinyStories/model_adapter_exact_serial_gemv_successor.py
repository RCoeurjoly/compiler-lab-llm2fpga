from __future__ import annotations

"""Successor-only export route for the exact serial-GEMV boundary model."""

import importlib.util
from pathlib import Path

import torch

from TinyStories.model_adapter_exact_package import (
    ExactModelError,
    export_exact_program,
    load_successor_exact_model,
)


ROOT = Path(__file__).resolve().parents[1]
GENERATION_ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
SUCCESSOR_VERIFIER = (
    ROOT / "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py"
)


def _verify_successor_authority() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "exact_serial_gemv_successor_authority", SUCCESSOR_VERIFIER
    )
    if spec is None or spec.loader is None:
        raise ExactModelError(
            "successor_receipt_unverified", "successor authority verifier unavailable"
        )
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    try:
        return verifier.verify_successor_authority(ROOT)
    except (OSError, UnicodeError, ValueError) as error:
        raise ExactModelError("successor_receipt_unverified", str(error)) from error


def export_program_with_package(
    model_path: str | Path,
    package_path: str | Path,
    contract_path: str | Path,
) -> torch.export.ExportedProgram:
    """Validate Task 1's successor receipt, then export through its loader."""

    if not model_path or not package_path or not contract_path:
        raise ExactModelError(
            "package_frontend_inputs_missing",
            "model, package, and frozen contract paths are required",
        )
    _verify_successor_authority()
    bundle = load_successor_exact_model(
        Path(contract_path),
        Path(package_path),
        Path(model_path),
        GENERATION_ARTIFACT,
    )
    return export_exact_program(bundle)
