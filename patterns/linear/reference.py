from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


PATTERN_DIR = Path(__file__).resolve().parent


def _load_symbol(module_name: str, symbol: str):
    module_path = PATTERN_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, symbol)


def expected_output() -> torch.Tensor:
    build_model = _load_symbol("model", "build_model")
    example_inputs = _load_symbol("inputs", "example_inputs")
    model = build_model()
    with torch.no_grad():
        return model(*example_inputs())
