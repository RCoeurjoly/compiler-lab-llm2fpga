from __future__ import annotations

from inputs import example_inputs
from model import build_model as build_pattern_model


def build_model(model_path: str | None = None):
    del model_path
    return build_pattern_model()


__all__ = ["build_model", "example_inputs"]
