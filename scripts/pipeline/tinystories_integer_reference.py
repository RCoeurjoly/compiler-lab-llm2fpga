#!/usr/bin/env python3
"""Emit PyTorch reference vectors for the explicit-integer TinyStories slice."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def load_adapter(adapter_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "tinystories_representative_core_w4a8_integer", adapter_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load adapter from {adapter_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    module = load_adapter(args.adapter)
    model = module.build_model().eval()
    inputs = module.example_inputs()

    import torch

    with torch.no_grad():
        output = model(*inputs)

    payload = {
        "model": "tinystories-representative-core-w4a8-integer",
        "input_token_ids": inputs[0].detach().cpu().to(dtype=torch.int64).tolist(),
        "pytorch_output_i8": output.detach().cpu().to(dtype=torch.int8).tolist(),
        "pytorch_output_shape": list(output.shape),
        "dtype": "int8",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
