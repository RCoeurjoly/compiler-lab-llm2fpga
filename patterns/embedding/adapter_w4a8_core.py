from __future__ import annotations

import torch
import torch.nn.functional as F


EXPORT_STRICT = False


class EmbeddingW4A8Core(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        weight = torch.arange(-16, 16, dtype=torch.int8).reshape(8, 4)
        self.register_buffer("weight_i8", torch.clamp(weight, -8, 7))

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        return F.embedding(token_ids, self.weight_i8)


def example_inputs() -> tuple[torch.Tensor]:
    return (torch.tensor([[0, 3]], dtype=torch.long),)


def build_model(model_path: str | None = None) -> torch.nn.Module:
    del model_path
    return EmbeddingW4A8Core().eval()


def export_program(model_path: str | None = None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    return torch.export.export(model, example_inputs(), strict=EXPORT_STRICT)


__all__ = ["build_model", "example_inputs", "export_program"]
