from __future__ import annotations

import torch


EXPORT_STRICT = False


class LayerNormW4A8Core(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.register_buffer(
            "gamma_i32", torch.tensor([128, 120, 136, 112], dtype=torch.int32)
        )
        self.register_buffer(
            "beta_i32", torch.tensor([0, -2, 1, 3], dtype=torch.int32)
        )
        self.register_buffer("mean_shift_i32", torch.tensor(2, dtype=torch.int32))
        self.register_buffer("variance_shift_i32", torch.tensor(1, dtype=torch.int32))
        self.register_buffer("norm_shift_i32", torch.tensor(7, dtype=torch.int32))
        self.register_buffer("inv_std_base_i32", torch.tensor(128, dtype=torch.int32))
        self.register_buffer("inv_std_min_i32", torch.tensor(1, dtype=torch.int32))
        self.register_buffer("qmin_i32", torch.tensor(-128, dtype=torch.int32))
        self.register_buffer("qmax_i32", torch.tensor(127, dtype=torch.int32))

    def forward(self, x_i8: torch.Tensor) -> torch.Tensor:
        x_i32 = x_i8.to(torch.int32)
        sum_i32 = torch.sum(x_i32, dim=-1, keepdim=True).to(torch.int32)
        mean_i32 = torch.bitwise_right_shift(
            sum_i32, self.mean_shift_i32
        )
        centered_i32 = x_i32 - mean_i32
        sumsq_i32 = torch.sum(
            centered_i32 * centered_i32, dim=-1, keepdim=True
        ).to(torch.int32)
        variance_i32 = torch.bitwise_right_shift(
            sumsq_i32, self.mean_shift_i32
        )
        variance_clamped_i32 = torch.minimum(
            torch.maximum(variance_i32, torch.tensor(0, dtype=torch.int32)),
            torch.tensor(255, dtype=torch.int32),
        )
        inv_std_drop_i32 = torch.bitwise_right_shift(
            variance_clamped_i32, self.variance_shift_i32
        )
        inv_std_i32 = torch.maximum(
            self.inv_std_base_i32 - inv_std_drop_i32, self.inv_std_min_i32
        )
        normalized_i32 = torch.bitwise_right_shift(
            centered_i32 * inv_std_i32, self.norm_shift_i32
        )
        scaled_i32 = torch.bitwise_right_shift(
            normalized_i32 * self.gamma_i32, self.norm_shift_i32
        )
        biased_i32 = scaled_i32 + self.beta_i32
        clamped_i32 = torch.minimum(
            torch.maximum(biased_i32, self.qmin_i32), self.qmax_i32
        )
        return clamped_i32.to(torch.int8)


def example_inputs() -> tuple[torch.Tensor]:
    return (torch.tensor([[[-12, -4, 5, 11]]], dtype=torch.int8),)


def build_model(model_path: str | None = None) -> torch.nn.Module:
    del model_path
    return LayerNormW4A8Core().eval()


def export_program(model_path: str | None = None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    return torch.export.export(model, example_inputs(), strict=EXPORT_STRICT)


__all__ = ["build_model", "example_inputs", "export_program"]
