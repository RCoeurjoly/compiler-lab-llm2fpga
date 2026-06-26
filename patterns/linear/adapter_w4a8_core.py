from __future__ import annotations

import torch


EXPORT_STRICT = False


class LinearW4A8Core(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        weight = torch.arange(-16, 16, dtype=torch.int8).reshape(4, 8)
        self.register_buffer("weight_i8", torch.clamp(weight, -8, 7))
        self.register_buffer(
            "bias_i32", torch.tensor([-32, -16, 16, 32], dtype=torch.int32)
        )
        self.register_buffer(
            "requant_multiplier_i64", torch.tensor(1787632017, dtype=torch.int64)
        )
        self.register_buffer(
            "requant_round_i64", torch.tensor(4294967296, dtype=torch.int64)
        )
        self.register_buffer("requant_shift_i64", torch.tensor(33, dtype=torch.int64))
        self.register_buffer("qmin_i32", torch.tensor(-128, dtype=torch.int32))
        self.register_buffer("qmax_i32", torch.tensor(127, dtype=torch.int32))

    def forward(self, x_i8: torch.Tensor) -> torch.Tensor:
        x_i32 = x_i8.to(torch.int32)
        weight_i32 = self.weight_i8.to(torch.int32)
        acc_i32 = torch.matmul(x_i32, weight_i32.t()) + self.bias_i32

        scaled_i64 = acc_i32.to(torch.int64) * self.requant_multiplier_i64
        rounded_i64 = scaled_i64 + self.requant_round_i64
        shifted_i32 = torch.bitwise_right_shift(
            rounded_i64, self.requant_shift_i64
        ).to(torch.int32)
        clamped_i32 = torch.minimum(
            torch.maximum(shifted_i32, self.qmin_i32), self.qmax_i32
        )
        return clamped_i32.to(torch.int8)


def example_inputs() -> tuple[torch.Tensor]:
    return (torch.arange(-4, 4, dtype=torch.int8).reshape(1, 8),)


def build_model(model_path: str | None = None) -> torch.nn.Module:
    del model_path
    return LinearW4A8Core().eval()


def export_program(model_path: str | None = None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    return torch.export.export(model, example_inputs(), strict=EXPORT_STRICT)


__all__ = ["build_model", "example_inputs", "export_program"]
