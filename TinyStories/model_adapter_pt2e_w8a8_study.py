"""Full TinyStories PT2E W8A8 export for the RC structural study."""

from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM

from pt2e_w8a8_study import export_pt2e_w8a8, study_example_inputs


EXPORT_STRICT = False


def build_model(model_path: str | None) -> torch.nn.Module:
    if model_path is None:
        raise RuntimeError("TinyStories adapter requires --model-path")
    return AutoModelForCausalLM.from_pretrained(
        model_path,
        use_cache=False,
        attn_implementation="eager",
        local_files_only=True,
    ).eval()


def example_inputs() -> tuple[torch.Tensor, ...]:
    return study_example_inputs()


def export_program(model_path: str | None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    inputs = example_inputs()
    return export_pt2e_w8a8(model, inputs, (inputs,))
