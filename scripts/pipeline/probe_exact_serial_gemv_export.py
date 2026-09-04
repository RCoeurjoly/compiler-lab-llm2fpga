#!/usr/bin/env python3
"""Record the exact eager/export contract for the serial-GEMV compiler boundary."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories.model_adapter_exact_package import (
    GEMV_NAMES,
    export_exact_program,
    exported_program_identity,
    load_successor_exact_model,
)
from TinyStories.serial_gemv_boundary import serial_gemv


RECEIPT = ROOT / "artifacts/comparison/tinystories-1m-exact-serial-gemv-export.json"
SUCCESSOR_RECEIPT = ROOT / "artifacts/comparison/tinystories-1m-exact-serial-gemv-successor.json"
GENERATION_ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
ADAPTER = ROOT / "TinyStories/model_adapter_exact_package.py"
BOUNDARY = ROOT / "TinyStories/serial_gemv_boundary.py"
GENERATION_VERIFIER = ROOT / "scripts/comparison/verify_tinystories_1m_exact_generation.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
MODEL_PATH = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _tensor_sha256(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().astype("<i8").tobytes()).hexdigest()


def _activations(rows: int, columns: int) -> torch.Tensor:
    return (torch.arange(rows * columns, dtype=torch.int64).reshape(rows, columns) % 97) - 48


def _codes(rows: int, columns: int) -> torch.Tensor:
    return (torch.arange(rows * columns, dtype=torch.int64).reshape(rows, columns) % 255) - 127


class _SerialGemvModule(torch.nn.Module):
    def forward(self, scaled_input_q24: torch.Tensor, weight_codes: torch.Tensor) -> torch.Tensor:
        return serial_gemv(scaled_input_q24, weight_codes)


def _operator_count(exported: torch.export.ExportedProgram) -> int:
    return sum(
        node.op == "call_function" and node.target == torch.ops.llm2fpga.serial_gemv.default
        for node in exported.graph_module.graph.nodes
    )


def _frozen_boundary_sha256() -> dict[str, str]:
    return {
        "adapter": hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),
        "boundary": hashlib.sha256(BOUNDARY.read_bytes()).hexdigest(),
    }


def _adapter_boundary_coverage() -> dict[str, int | bool]:
    """Prove the two executable GEMV routes use the boundary, never the old helper."""

    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"), filename=str(ADAPTER))
    direct_helper_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "serial_gemv_accumulate"
    ]
    boundary_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "serial_gemv"
    ]
    return {
        "all_adapter_gemvs_cross_boundary": not direct_helper_calls and len(boundary_calls) == 2,
        "direct_serial_helper_call_count": len(direct_helper_calls),
        "boundary_call_site_count": len(boundary_calls),
        "runtime_gemv_operation_count": len(GEMV_NAMES),
    }


def _load_generation_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("exact_generation_verifier", GENERATION_VERIFIER)
    if spec is None or spec.loader is None:
        raise ValueError(f"unable to load frozen generation verifier: {GENERATION_VERIFIER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_frozen_generation_artifact() -> dict[str, Any]:
    artifact = json.loads(GENERATION_ARTIFACT.read_text(encoding="utf-8"))
    verifier = _load_generation_verifier()
    verifier.validate_artifact(artifact, ROOT)
    return {
        "path": str(GENERATION_ARTIFACT.relative_to(ROOT)),
        "file_sha256": hashlib.sha256(GENERATION_ARTIFACT.read_bytes()).hexdigest(),
        "artifact_sha256": artifact["artifact_sha256"],
        "historical_task_1": artifact["identity"]["task_1"],
        "historical_task_2": artifact["identity"]["task_2"],
        "status": "matched",
    }


def _verify_successor_generation(historical_generation_artifact_path: Path) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    package = Path(contract["package"]["origin"])
    if not package.is_dir() or not MODEL_PATH.is_dir():
        raise ValueError("frozen package/model inputs unavailable for successor verification")
    bundle = load_successor_exact_model(
        CONTRACT, package, MODEL_PATH, historical_generation_artifact_path
    )
    prompt = list(bundle.contract["reference"]["prompt_tokens"])
    expected_tokens = list(bundle.contract["reference"]["tokens"])
    with torch.no_grad():
        eager_logits = bundle.model(torch.tensor([prompt], dtype=torch.int64))[0, -1]
    prompt_logits_matched = torch.equal(eager_logits, bundle.oracle_logits)
    exported = export_exact_program(bundle)
    exported_operator_count = _operator_count(exported)
    if exported_operator_count != len(GEMV_NAMES):
        raise ValueError("successor export does not contain one boundary per GEMV")
    generated: list[int] = []
    token_ids = list(prompt)
    with torch.no_grad():
        for _ in expected_tokens:
            logits = bundle.model(torch.tensor([token_ids], dtype=torch.int64))
            next_token = int(torch.argmax(logits[0, -1]))
            generated.append(next_token)
            token_ids.append(next_token)
    if not prompt_logits_matched or generated != expected_tokens:
        raise ValueError("post-boundary successor generation differs from frozen artifact")
    return {
        "prompt_logits": "matched",
        "tokens": "matched",
        "token_count": len(generated),
        "tokens_sha256": canonical_sha256(generated),
        "exported_operator_count": exported_operator_count,
        "export_verification": bundle.export_verification,
    }


def build_successor_receipt() -> dict[str, Any]:
    """Bind the changed adapter to the immutable Task 1--3 generation authority.

    The historical artifact remains validated in place.  The new adapter is
    verified compositionally: every one of its two GEMV execution routes
    dispatches to the custom boundary, whose eager and exported contracts are
    separately bound by the export receipt.  This deliberately does not alter
    or reinterpret any historical Task 1--3 source identity.
    """

    historical_generation = _verify_frozen_generation_artifact()
    coverage = _adapter_boundary_coverage()
    if not coverage["all_adapter_gemvs_cross_boundary"]:
        raise ValueError("adapter GEMV path bypasses serial boundary")
    export_receipt = build_receipt()
    successor_generation = _verify_successor_generation(GENERATION_ARTIFACT)
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-serial-gemv-successor-v1",
        "status": "post_boundary_generation_matched",
        "historical_authority": {
            "generation": historical_generation,
            "preservation": "Task 1--3 source authority is validated in place and never rewritten",
        },
        "successor": {
            "adapter_sha256": hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),
            "boundary_sha256": hashlib.sha256(BOUNDARY.read_bytes()).hexdigest(),
            "export_receipt_sha256": export_receipt["receipt_sha256"],
        },
        "verification": {
            "frozen_generation_artifact": historical_generation["status"],
            **coverage,
            "boundary_eager_export_status": (
                "matched" if export_receipt["eager_output_sha256"]
                == export_receipt["export_output_sha256"] else "mismatch"
            ),
            "successor_prompt_logits": successor_generation["prompt_logits"],
            "successor_tokens": successor_generation["tokens"],
            "successor_token_count": successor_generation["token_count"],
            "successor_tokens_sha256": successor_generation["tokens_sha256"],
            "successor_exported_operator_count": successor_generation["exported_operator_count"],
            "successor_export_verification": successor_generation["export_verification"],
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def build_receipt() -> dict[str, Any]:
    scaled_input = _activations(3, 64)
    weight_codes = _codes(64, 64)
    module = _SerialGemvModule().eval()
    eager = module(scaled_input, weight_codes)
    exported = torch.export.export(module, (scaled_input, weight_codes), strict=False)
    replay = exported.module()(scaled_input, weight_codes)
    if not torch.equal(eager, replay):
        raise ValueError("exact serial GEMV eager/export mismatch")
    identity = exported_program_identity(exported)
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-serial-gemv-export-v1",
        "operator": "llm2fpga.serial_gemv.default",
        "input": {
            "scaled_activation": {"dtype": "signed_i64", "shape": [3, 64]},
            "weight_codes": {"dtype": "signed_i64_w8_codes", "shape": [64, 64]},
        },
        "output": {"dtype": "signed_i64", "shape": [3, 64]},
        "eager_output_sha256": _tensor_sha256(eager),
        "export_output_sha256": _tensor_sha256(replay),
        "exported_program_sha256": identity["program_sha256"],
        "operator_count": _operator_count(exported),
        "frozen_boundary_sha256": _frozen_boundary_sha256(),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RECEIPT)
    parser.add_argument("--successor-output", type=Path, default=SUCCESSOR_RECEIPT)
    args = parser.parse_args()
    receipt = build_receipt()
    successor = build_successor_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.successor_output.parent.mkdir(parents=True, exist_ok=True)
    args.successor_output.write_text(
        json.dumps(successor, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"export": receipt, "successor": successor}, sort_keys=True))


if __name__ == "__main__":
    main()
