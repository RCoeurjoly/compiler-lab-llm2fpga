#!/usr/bin/env python3
"""Probe execution of the authenticated fixed-LayerNorm Calyx backend.

This is deliberately a fail-closed execution gate.  Calyx MLIR conversion is
not simulation: the generated component has external memories, and a numeric
Python implementation of the same schedule is not evidence that Calyx (or
the emitted RTL) executed.  The probe records the available runtime tools and
the first concrete boundary at which execution cannot be established.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
BACKEND_SCRIPT = ROOT / "scripts/comparison/lower_tinystories_1m_fixed_layernorm_backend.py"
BACKEND_SCRIPT_SHA256 = ""  # filled by the generator below; checked by tests when pinned


class ExecutionProbeError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise ExecutionProbeError(f"missing_artifact: {path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _load_backend_module() -> Any:
    spec = importlib.util.spec_from_file_location("task3q_backend", BACKEND_SCRIPT)
    if spec is None or spec.loader is None:
        raise ExecutionProbeError(f"backend_script_load_failed: {BACKEND_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_inputs(backend_report_path: Path, calyx_path: Path, vector_path: Path) -> dict[str, Any]:
    """Authenticate the exact Task 3q artifact and Task 3o vector."""

    backend = json.loads(backend_report_path.read_text(encoding="utf-8"))
    if not isinstance(backend, dict):
        raise ExecutionProbeError("backend_report_invalid: expected object")
    if backend.get("sha256") != canonical_sha256({k: v for k, v in backend.items() if k != "sha256"}):
        raise ExecutionProbeError("backend_report_hash_mismatch")
    try:
        calyx_bytes = calyx_path.read_bytes()
    except OSError as error:
        raise ExecutionProbeError(f"missing_artifact: {calyx_path}: {error}") from error
    expected_calyx = backend.get("compiler_artifacts", {}).get("calyx", {}).get("sha256")
    if expected_calyx != sha256_bytes(calyx_bytes):
        raise ExecutionProbeError("calyx_artifact_hash_mismatch")
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    if not isinstance(vector, dict) or vector.get("sha256") != canonical_sha256({k: v for k, v in vector.items() if k != "sha256"}):
        raise ExecutionProbeError("vector_report_hash_mismatch")
    if backend.get("model") != "TinyStories-1M":
        raise ExecutionProbeError("backend_model_mismatch")
    if "llm2fpga.fixed_layer_norm_q16_16" in calyx_bytes.decode("utf-8"):
        raise ExecutionProbeError("calyx_custom_op_not_eliminated")
    return {"backend": backend, "calyx": calyx_bytes.decode("utf-8"), "vector": vector}


def _tool(path_or_name: str | None, names: tuple[str, ...]) -> dict[str, Any]:
    selected = str(Path(path_or_name)) if path_or_name else next((shutil.which(name) for name in names if shutil.which(name)), None)
    available = bool(selected and Path(selected).is_file() and os.access(selected, os.X_OK))
    return {"path": selected, "available": available}


def external_memory_inventory(calyx_mlir: str) -> dict[str, int]:
    return {
        "external_memories": calyx_mlir.count("{external = true}"),
        "external_64x32_memories": calyx_mlir.count("<[64] x 32>"),
    }


def build_report(inputs: Mapping[str, Any], *, calyx_bin: str | None = None, fud: str | None = None, verilator: str | None = None) -> dict[str, Any]:
    backend = inputs["backend"]
    calyx = inputs["calyx"]
    vector = inputs["vector"]
    backend_module = _load_backend_module()
    expected = vector.get("result")
    algorithm = backend_module.execute_lowered_algorithm(vector)
    if algorithm != expected:
        raise ExecutionProbeError("reference_algorithm_mismatch")
    tools = {
        "calyx": _tool(calyx_bin, ("calyx",)),
        "fud": _tool(fud, ("fud",)),
        "verilator": _tool(verilator, ("verilator",)),
    }
    memories = external_memory_inventory(calyx)
    if not tools["calyx"]["available"]:
        boundary = {
            "code": "calyx_runtime_unavailable",
            "target": "calyx_execution",
            "reason": "no Calyx executable was available to execute or emit a simulator for the authenticated Calyx MLIR",
        }
    elif memories["external_memories"] != 4 or memories["external_64x32_memories"] < 8:
        boundary = {
            "code": "calyx_artifact_memory_interface_unrecognized",
            "target": "external_memory_harness",
            "reason": "authenticated Calyx artifact does not expose the expected four external 64xi32 memories",
        }
    else:
        boundary = {
            "code": "external_memory_harness_not_implemented",
            "target": "calyx_numeric_equivalence",
            "reason": "Calyx execution needs a harness that initializes and observes the four external memories; no such harness is present in this repository",
        }
    return {
        "schema": "tinystories-1m-fixed-layernorm-backend-execution-v1",
        "model": "TinyStories-1M",
        "status": "unsupported",
        "execution": {
            "status": "not_executed",
            "tools": tools,
            "external_memory_inventory": memories,
            "first_unsupported_operation": boundary,
        },
        "numeric_trace": {
            "status": "algorithm_matched_backend_execution_not_run",
            "expected_sha256": canonical_sha256(expected),
            "algorithm_sha256": canonical_sha256(algorithm),
            "result": algorithm,
        },
        "evidence": {
            "backend_report_sha256": sha256_file(Path(inputs["backend_path"])),
            "calyx_sha256": sha256_bytes(calyx.encode()),
            "vector_sha256": sha256_file(Path(inputs["vector_path"])),
            "backend_calyx_sha256": backend["compiler_artifacts"]["calyx"]["sha256"],
        },
        "provenance": {
            "reference_role": "content_authenticated_behavioral_oracle_only",
            "reference_source_or_rtl_copied": False,
            "compiler_source": "LLM2FPGA",
            "llm_assistance_disclosure_required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-report", required=True, type=Path)
    parser.add_argument("--calyx", required=True, type=Path)
    parser.add_argument("--vector", required=True, type=Path)
    parser.add_argument("--calyx-bin")
    parser.add_argument("--fud")
    parser.add_argument("--verilator")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    inputs = load_inputs(args.backend_report, args.calyx, args.vector)
    inputs["backend_path"] = str(args.backend_report)
    inputs["vector_path"] = str(args.vector)
    report = build_report(inputs, calyx_bin=args.calyx_bin, fud=args.fud, verilator=args.verilator)
    report["sha256"] = canonical_sha256(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
