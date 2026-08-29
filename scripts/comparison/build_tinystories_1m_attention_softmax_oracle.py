#!/usr/bin/env python3
"""Build a software attention score/softmax oracle for TinyStories-1M.

This is deliberately supplementary evidence.  It executes the authenticated
package adapter in floating point and records every causal score and softmax
probability for one complete block-0 prompt sequence.  It is not a QDQ, RTL,
or hardware trace and must not be used as an equivalence receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Mapping

import torch


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "TinyStories/model_adapter_reference_package.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PACKAGE_DEFAULT = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL_DEFAULT = Path(
    "/home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/"
    "snapshots/77f1b168e219585646439073245fe87e56b3023e"
)
QEXP = ROOT / "scripts/comparison/evaluate_tinystories_1m_q_exp_candidate.py"


class OracleError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise OracleError(f"input_unavailable: {path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise OracleError(f"noncanonical_value: {error}") from error
    return sha256_bytes(encoded)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OracleError(f"input_unavailable: {path}: {error}") from error
    require(isinstance(value, dict), f"invalid_json: {path}")
    return value


def load_adapter() -> Any:
    require(ADAPTER.is_file(), f"adapter_unavailable: {ADAPTER}")
    spec = importlib.util.spec_from_file_location("tinystories_reference_package_adapter", ADAPTER)
    require(spec is not None and spec.loader is not None, f"adapter_unavailable: {ADAPTER}")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _flat_stats(values: torch.Tensor) -> dict[str, float | int]:
    flat = values.detach().to(torch.float64).reshape(-1)
    require(bool(torch.isfinite(flat).all()), "non_finite_oracle_values")
    return {
        "count": int(flat.numel()),
        "min": float(flat.min().item()),
        "max": float(flat.max().item()),
        "mean": float(flat.mean().item()),
        "max_abs": float(flat.abs().max().item()),
    }


def _payload(tensor: torch.Tensor) -> list[Any]:
    require(bool(torch.isfinite(tensor).all()), "non_finite_oracle_values")
    return tensor.detach().cpu().tolist()


def _load_qexp() -> Any:
    # q_exp is only an error-characterization aid.  Its RTL identity is
    # included in the report, but no candidate is promoted by this oracle.
    require(QEXP.is_file(), f"q_exp_candidate_unavailable: {QEXP}")
    spec = importlib.util.spec_from_file_location("tinystories_q_exp_candidate", QEXP)
    require(spec is not None and spec.loader is not None, f"q_exp_candidate_unavailable: {QEXP}")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _score_row_oracle(bundle: Any, block_index: int) -> dict[str, Any]:
    contract = bundle.contract
    prompt_ids = contract.get("reference", {}).get("prompt_tokens")
    require(isinstance(prompt_ids, list) and prompt_ids, "frozen_prompt_unavailable")
    require(all(isinstance(token, int) and not isinstance(token, bool) for token in prompt_ids), "frozen_prompt_malformed")
    model = bundle.model
    config = model.config
    require(0 <= block_index < int(config.num_layers), "block_index_out_of_range")
    input_ids = torch.tensor([prompt_ids], dtype=torch.long)
    sequence = len(prompt_ids)
    positions = torch.arange(sequence, dtype=torch.long).unsqueeze(0)
    with torch.no_grad():
        hidden = model.transformer.drop(model.transformer.wte(input_ids) + model.transformer.wpe(positions))
        block = model.transformer.h[block_index]
        ln_1 = block.ln_1(hidden)
        attention = block.attn.attention
        heads = int(config.num_heads)
        head_dim = int(config.hidden_size // config.num_heads)
        q = attention.q_proj(ln_1).view(1, sequence, heads, head_dim).transpose(1, 2).to(torch.float32)
        k = attention.k_proj(ln_1).view(1, sequence, heads, head_dim).transpose(1, 2).to(torch.float32)
        # GPT-Neo's attention implementation has no 1/sqrt(d) score scale.
        scores = torch.matmul(q, k.transpose(-1, -2))[0]
        causal = torch.ones((sequence, sequence), dtype=torch.bool).tril()
        valid_scores = scores[causal.unsqueeze(0).expand(heads, -1, -1)]
        probabilities = torch.softmax(
            torch.where(causal.unsqueeze(0), scores, torch.finfo(scores.dtype).min), dim=-1
        )
        shifted = scores - scores.max(dim=-1, keepdim=True).values
        exp_shifted = torch.exp(shifted)
        exp_valid = exp_shifted[causal.unsqueeze(0).expand(heads, -1, -1)]
        # Exercise the existing RTL candidate on exactly the score domain fed
        # to a numerically stable softmax.  This remains a software comparison.
        qexp = _load_qexp()
        qexp_values = [qexp.q_exp_approx(float(value))[0] for value in exp_valid]
        qexp_tensor = torch.tensor(qexp_values, dtype=torch.float64)
        reference_exp = exp_valid.to(torch.float64)
        error = (qexp_tensor - reference_exp).abs()
        relative = error / torch.clamp(reference_exp.abs(), min=1.0e-30)
        rows = []
        for head in range(heads):
            rows.append({
                "head": head,
                "score_rows": _payload(scores[head]),
                "softmax_rows": _payload(probabilities[head]),
                "shifted_score_rows": _payload(shifted[head]),
                "exp_shifted_rows": _payload(exp_shifted[head]),
            })
        return {
            "sequence_length": sequence,
            "prompt_tokens": list(prompt_ids),
            "block_index": block_index,
            "num_heads": heads,
            "head_dim": head_dim,
            "score_scale": "none (GPT-Neo implementation)",
            "causal_mask": "strict lower triangle including diagonal",
            "rows": rows,
            "domains": {
                "causal_scores": _flat_stats(valid_scores),
                "shifted_scores": _flat_stats(shifted[causal.unsqueeze(0).expand(heads, -1, -1)]),
                "exp_shifted": _flat_stats(exp_valid),
            },
            "q_exp_candidate": {
                "rtl_path": str(qexp.RTL.relative_to(ROOT)),
                "rtl_sha256": sha256_file(qexp.RTL),
                "candidate_implementation_sha256": sha256_file(QEXP),
                "max_absolute_error": float(error.max().item()),
                "max_relative_error": float(relative.max().item()),
                "worst_case_index": int(error.argmax().item()),
                "sample_count": int(error.numel()),
                "comparison": "software-only against exp(score - row_max); not QDQ/RTL/hardware equivalence",
            },
            "final_prompt_token_index": sequence - 1,
            "frozen_next_token": contract.get("reference", {}).get("tokens", [None])[0],
        }


def build_report(contract_path: Path, package_path: Path, model_path: Path, block_index: int) -> dict[str, Any]:
    # Adapter authenticates the frozen contract and package before any model
    # tensor is reconstructed.  Missing inputs therefore produce an explicit
    # failure rather than a substitute software model.
    adapter = load_adapter()
    bundle = adapter.load_authenticated_package(contract_path, package_path, model_path)
    report: dict[str, Any] = {
        "schema": "tinystories-1m-attention-softmax-software-oracle-v1",
        "status": "supplementary_non_authoritative",
        "authority": {
            "functional_equivalence": False,
            "qdq_equivalence": False,
            "rtl_equivalence": False,
            "hardware_equivalence": False,
            "optimization_acceptance": False,
        },
        "scope": {
            "execution": "authenticated dequantized package weights in PyTorch float32",
            "trace": "complete causal score and softmax rows for block 0 prompt token-step",
            "sequence": "frozen contract prompt only; final prompt row is the next-token step",
        },
        "identity": {
            "contract_path": str(contract_path),
            "contract_sha256": sha256_file(contract_path),
            "package_path": str(package_path),
            "package_manifest_sha256": sha256_file(package_path / "manifest.json"),
            "package_weights_sha256": sha256_file(package_path / "weights.bin"),
            "package_scales_sha256": sha256_file(package_path / "scales.bin"),
            "package_calibration_ids_sha256": sha256_file(package_path / "calibration_ids.bin"),
            "package_receipt_sha256": sha256_file(package_path / "receipt.json"),
            "adapter_sha256": sha256_file(ADAPTER),
            "adapter_receipt_sha256": bundle.receipt["receipt_sha256"],
        },
        "trace": _score_row_oracle(bundle, block_index),
    }
    report["sha256"] = canonical_sha256({key: value for key, value in report.items() if key != "sha256"})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--package", type=Path, default=PACKAGE_DEFAULT)
    parser.add_argument("--model-path", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--block-index", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(args.contract, args.package, args.model_path, args.block_index)
    except (OracleError, OSError, RuntimeError, ValueError) as error:
        # CLI failure is intentionally nonzero and never emits a plausible
        # oracle artifact when authenticated inputs are unavailable.
        parser.error(str(error))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "sha256": report["sha256"], "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
