#!/usr/bin/env python3
"""Build the deterministic native stateful-serving RC reference receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import torch

from TinyStories.rc_serving_contract import argmax_lowest, load_trace
from TinyStories.rc_serving_evidence import run_native_trace
from TinyStories.rc_serving_source import build_source_model


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_reference(model_path: Path, trace_path: Path) -> dict[str, object]:
    trace = load_trace(trace_path)
    model = build_source_model(model_path)
    with torch.no_grad():
        receipt = run_native_trace(model, trace)
        generated = model.generate(
            torch.tensor([trace.prompt_token_ids], dtype=torch.long),
            attention_mask=torch.ones(
                (1, trace.phases[0].cache_length_after), dtype=torch.long
            ),
            do_sample=False,
            max_new_tokens=2,
            use_cache=True,
            eos_token_id=None,
        )
    generated_tokens = [int(value) for value in generated[0, -2:].tolist()]
    chained_tokens = [
        int(receipt["phases"][0]["greedy_token_id"]),
        int(receipt["phases"][1]["greedy_token_id"]),
    ]
    if generated_tokens != chained_tokens:
        raise ValueError(
            "native generate tokens disagree with chained greedy decode: "
            f"{generated_tokens!r} != {chained_tokens!r}"
        )
    receipt["generate_conformance"] = {
        "status": "pass",
        "generated_token_ids": generated_tokens,
        "chained_token_ids": chained_tokens,
    }
    receipt["source"] = {
        "model_path": str(model_path),
        "config_sha256": _sha256_json(model.config.to_dict()),
        "torch_version": torch.__version__,
    }
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            build_reference(args.model_path, args.trace),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
