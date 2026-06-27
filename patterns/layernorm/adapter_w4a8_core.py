from __future__ import annotations

import torch


EXPORT_STRICT = False


class LayerNormW4A8Core(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        inv_std = [
            int(round(128.0 / ((variance + 1.0) ** 0.5)))
            for variance in range(256)
        ]
        self.register_buffer(
            "inv_std_lut_i16", torch.tensor(inv_std, dtype=torch.int16)
        )
        self.register_buffer(
            "gamma_i16", torch.tensor([128, 120, 136, 112], dtype=torch.int16)
        )
        self.register_buffer(
            "beta_i32", torch.tensor([0, -2, 1, 3], dtype=torch.int32)
        )
        self.register_buffer("mean_shift_i32", torch.tensor(2, dtype=torch.int32))
        self.register_buffer("norm_shift_i32", torch.tensor(7, dtype=torch.int32))
        self.register_buffer("qmin_i32", torch.tensor(-128, dtype=torch.int32))
        self.register_buffer("qmax_i32", torch.tensor(127, dtype=torch.int32))

    def forward(self, x_i8: torch.Tensor) -> torch.Tensor:
        x_i32 = x_i8.to(torch.int32)
        x0 = x_i32[:, :, 0:1]
        x1 = x_i32[:, :, 1:2]
        x2 = x_i32[:, :, 2:3]
        x3 = x_i32[:, :, 3:4]
        mean_i32 = torch.bitwise_right_shift(
            x0 + x1 + x2 + x3, self.mean_shift_i32
        )
        c0 = x0 - mean_i32
        c1 = x1 - mean_i32
        c2 = x2 - mean_i32
        c3 = x3 - mean_i32
        centered_i32 = torch.cat((c0, c1, c2, c3), dim=-1)
        variance_i32 = torch.bitwise_right_shift(
            c0 * c0 + c1 * c1 + c2 * c2 + c3 * c3, self.mean_shift_i32
        )
        variance_clamped_i32 = torch.minimum(
            torch.maximum(variance_i32, torch.tensor(0, dtype=torch.int32)),
            torch.tensor(255, dtype=torch.int32),
        )
        lut_i16 = self.inv_std_lut_i16.reshape(1, 1, 256).expand(
            variance_clamped_i32.shape[0], variance_clamped_i32.shape[1], 256
        )
        inv_std_i32 = torch.gather(
            lut_i16, -1, variance_clamped_i32.to(torch.int64)
        ).to(torch.int32)
        normalized_i32 = torch.bitwise_right_shift(
            centered_i32 * inv_std_i32, self.norm_shift_i32
        )
        scaled_i32 = torch.bitwise_right_shift(
            normalized_i32 * self.gamma_i16.to(torch.int32), self.norm_shift_i32
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
