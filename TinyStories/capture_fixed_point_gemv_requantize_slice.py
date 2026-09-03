#!/usr/bin/env python3
"""Capture and replay the first exact TinyStories-1M GEMV/requantize slice."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from TinyStories.model_adapter_exact_package import load_successor_exact_model
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path("/home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/snapshots/77f1b168e219585646439073245fe87e56b3023e")
SCHEMA = "tinystories-1m-fixed-point-gemv-requantize-slice-v1"
GENERATION_ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def tensor_record(value: torch.Tensor, semantic: str) -> dict[str, Any]:
    value = value.detach().cpu().contiguous().to(torch.int64)
    raw = value.numpy().astype("<i8", copy=False).tobytes()
    payload = {"semantic": semantic, "shape": list(value.shape), "dtype": "int64", "values": value.tolist()}
    return {**payload, "canonical_sha256": canonical(payload), "little_endian_int64_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def capture() -> dict[str, Any]:
    bundle = load_successor_exact_model(CONTRACT, PACKAGE, MODEL, GENERATION_ARTIFACT)
    prompt = torch.tensor([bundle.contract["reference"]["prompt_tokens"]], dtype=torch.int64)
    with torch.no_grad():
        _, _, qdq, accumulators, _ = bundle.model._execute(prompt)
    # First block-0 q projection: its QDQ observations are input-code, scale,
    # input-dequantized, output-code, scale, output-dequantized in that order.
    value = {
        "schema": SCHEMA,
        "status": "authenticated_frozen_prompt_fixture",
        "identity": {
            "contract_sha256": sha(CONTRACT),
            "package_manifest_sha256": sha(PACKAGE / "manifest.json"),
            "package_weights_sha256": sha(PACKAGE / "weights.bin"),
            "package_scales_sha256": sha(PACKAGE / "scales.bin"),
            "package_receipt_sha256": sha(PACKAGE / "receipt.json"),
            "model_config_sha256": sha(MODEL / "config.json"),
            "adapter_sha256": sha(ROOT / "TinyStories/model_adapter_exact_package.py"),
            "capture_sha256": sha(Path(__file__)),
            "successor_generation_receipt_sha256": sha(GENERATION_ARTIFACT),
        },
        "prompt_tokens": prompt[0].tolist(),
        "slice": {"layer": 0, "module": "transformer.h.0.attn.attention.q_proj", "rows": 4, "inputs": 64, "outputs": 64,
                  "gemv_semantics": "ascending_input_index_signed_int64_twos_complement_wrap",
                  "requantization": "activation_qdq_signed_int8_saturated_nearest_ties_away_from_zero"},
        "tensors": {
            "activation_q16_16": tensor_record(qdq[2], "first_gemv_input_dequantized_q16_16"),
            "gemv_accumulator_i64": tensor_record(accumulators[0], "first_gemv_exact_accumulator_i64"),
            "requantized_codes_i8": tensor_record(qdq[3], "first_gemv_output_signed_int8_codes"),
            "requantized_q16_16": tensor_record(qdq[5], "first_gemv_output_dequantized_q16_16"),
        },
    }
    value["receipt_sha256"] = canonical(value)
    return value


def verify_fixture(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if value.get("schema") != SCHEMA:
        raise ValueError("fixture schema mismatch")
    payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("receipt_sha256") != canonical(payload):
        raise ValueError("fixture self-hash mismatch")
    if value.get("prompt_tokens") != [7454, 2402, 257, 640]:
        raise ValueError("fixture frozen prompt mismatch")
    for name, record in value.get("tensors", {}).items():
        check = {key: record[key] for key in ("semantic", "shape", "dtype", "values")}
        if record.get("canonical_sha256") != canonical(check):
            raise ValueError(f"fixture tensor hash mismatch: {name}")
    return value


def verify_eager_replay(path: Path) -> None:
    expected = verify_fixture(path)
    actual = capture()
    if actual != expected:
        raise ValueError("fixture eager replay mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_eager_replay(args.output)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(capture(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
