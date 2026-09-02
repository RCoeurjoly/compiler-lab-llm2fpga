#!/usr/bin/env python3
"""Record the exact eager/export contract for the serial-GEMV compiler boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories.model_adapter_exact_package import exported_program_identity
from TinyStories.serial_gemv_boundary import serial_gemv


RECEIPT = ROOT / "artifacts/comparison/tinystories-1m-exact-serial-gemv-export.json"


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
        "adapter": hashlib.sha256(
            (ROOT / "TinyStories/model_adapter_exact_package.py").read_bytes()
        ).hexdigest(),
        "boundary": hashlib.sha256(
            (ROOT / "TinyStories/serial_gemv_boundary.py").read_bytes()
        ).hexdigest(),
    }


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
    args = parser.parse_args()
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
