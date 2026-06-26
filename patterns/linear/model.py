from __future__ import annotations

import torch


class LinearPattern(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(8, 4, bias=True)
        with torch.no_grad():
            weight = torch.arange(-16, 16, dtype=torch.float32).reshape(4, 8)
            self.linear.weight.copy_(weight / 32.0)
            self.linear.bias.copy_(torch.tensor([-0.25, -0.125, 0.125, 0.25]))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def build_model() -> torch.nn.Module:
    return LinearPattern().eval()
