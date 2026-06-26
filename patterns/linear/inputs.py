from __future__ import annotations

import torch


def example_inputs() -> tuple[torch.Tensor]:
    return (
        torch.tensor(
            [[-1.0, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1.0]],
            dtype=torch.float32,
        ),
    )
