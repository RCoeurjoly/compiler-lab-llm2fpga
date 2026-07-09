from __future__ import annotations

"""Explicit-integer TinyStories representative-core hardware slice."""

import torch
import torch.nn.functional as F


EXPORT_STRICT = False


class RequantizedLinear(torch.nn.Module):
    def __init__(
        self,
        weight_i8: torch.Tensor,
        bias_i32: torch.Tensor,
        multiplier: int,
        shift: int,
    ) -> None:
        super().__init__()
        self.register_buffer("weight_i8", weight_i8.to(torch.int8))
        self.register_buffer("bias_i32", bias_i32.to(torch.int32))
        self.register_buffer(
            "requant_multiplier_i64", torch.tensor(multiplier, dtype=torch.int64)
        )
        self.register_buffer(
            "requant_round_i64", torch.tensor(1 << (shift - 1), dtype=torch.int64)
        )
        self.register_buffer("requant_shift_i64", torch.tensor(shift, dtype=torch.int64))
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


class TinyStoriesIntegerLayer(torch.nn.Module):
    def __init__(
        self,
        norm_gamma_i32: torch.Tensor,
        norm_beta_i32: torch.Tensor,
        fc_weight_i8: torch.Tensor,
        fc_bias_i32: torch.Tensor,
        proj_weight_i8: torch.Tensor,
        proj_bias_i32: torch.Tensor,
    ) -> None:
        super().__init__()
        self.register_buffer("gamma_i32", norm_gamma_i32.to(torch.int32))
        self.register_buffer("beta_i32", norm_beta_i32.to(torch.int32))
        self.register_buffer("mean_shift_i32", torch.tensor(1, dtype=torch.int32))
        self.register_buffer("variance_shift_i32", torch.tensor(1, dtype=torch.int32))
        self.register_buffer("norm_shift_i32", torch.tensor(7, dtype=torch.int32))
        self.register_buffer("inv_std_base_i32", torch.tensor(128, dtype=torch.int32))
        self.register_buffer("inv_std_min_i32", torch.tensor(1, dtype=torch.int32))
        self.register_buffer("activation_shift_i32", torch.tensor(6, dtype=torch.int32))
        self.register_buffer("qmin_i32", torch.tensor(-128, dtype=torch.int32))
        self.register_buffer("qmax_i32", torch.tensor(127, dtype=torch.int32))
        self.fc = RequantizedLinear(fc_weight_i8, fc_bias_i32, 1073741824, 30)
        self.proj = RequantizedLinear(proj_weight_i8, proj_bias_i32, 1073741824, 30)

    def _layernorm(self, x_i8: torch.Tensor) -> torch.Tensor:
        x_i32 = x_i8.to(torch.int32)
        sum_i32 = torch.sum(x_i32, dim=-1, keepdim=True).to(torch.int32)
        mean_i32 = torch.bitwise_right_shift(sum_i32, self.mean_shift_i32)
        centered_i32 = x_i32 - mean_i32
        sumsq_i32 = torch.sum(
            centered_i32 * centered_i32, dim=-1, keepdim=True
        ).to(torch.int32)
        variance_i32 = torch.bitwise_right_shift(sumsq_i32, self.mean_shift_i32)
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

    def _activation(self, x_i8: torch.Tensor) -> torch.Tensor:
        x_i32 = x_i8.to(torch.int32)
        quadratic_i32 = torch.bitwise_right_shift(
            x_i32 * x_i32, self.activation_shift_i32
        )
        activated_i32 = x_i32 + quadratic_i32
        clamped_i32 = torch.minimum(
            torch.maximum(activated_i32, self.qmin_i32), self.qmax_i32
        )
        return clamped_i32.to(torch.int8)

    def forward(self, x_i8: torch.Tensor) -> torch.Tensor:
        normalized_i8 = self._layernorm(x_i8)
        hidden_i8 = self._activation(self.fc(normalized_i8))
        projected_i8 = self.proj(hidden_i8)
        residual_i32 = x_i8.to(torch.int32) + projected_i8.to(torch.int32)
        clamped_i32 = torch.minimum(
            torch.maximum(residual_i32, self.qmin_i32), self.qmax_i32
        )
        return clamped_i32.to(torch.int8)


class TinyStoriesRepresentativeCoreW4A8Integer(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        token_weight = torch.tensor(
            [
                [-8, -2],
                [-6, 1],
                [-4, 3],
                [-2, 5],
                [0, 7],
                [2, -7],
                [4, -5],
                [6, -3],
            ],
            dtype=torch.int8,
        )
        position_weight = torch.tensor([[1, -1]], dtype=torch.int8)
        self.register_buffer("token_weight_i8", token_weight)
        self.register_buffer("position_weight_i8", position_weight)
        self.layer0 = TinyStoriesIntegerLayer(
            torch.tensor([128, 120], dtype=torch.int32),
            torch.tensor([0, 1], dtype=torch.int32),
            torch.tensor([[3, -2], [-1, 4]], dtype=torch.int8),
            torch.tensor([1, -2], dtype=torch.int32),
            torch.tensor([[2, 1], [-3, 2]], dtype=torch.int8),
            torch.tensor([0, 1], dtype=torch.int32),
        )
        self.layer1 = TinyStoriesIntegerLayer(
            torch.tensor([112, 136], dtype=torch.int32),
            torch.tensor([-1, 2], dtype=torch.int32),
            torch.tensor([[1, 3], [-4, 1]], dtype=torch.int8),
            torch.tensor([2, 0], dtype=torch.int32),
            torch.tensor([[3, -1], [1, 2]], dtype=torch.int8),
            torch.tensor([-1, 1], dtype=torch.int32),
        )

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        token_i8 = F.embedding(token_ids, self.token_weight_i8)
        position_ids = torch.zeros_like(token_ids)
        position_i8 = F.embedding(position_ids, self.position_weight_i8)
        x_i32 = token_i8.to(torch.int32) + position_i8.to(torch.int32)
        x_i8 = torch.minimum(
            torch.maximum(
                x_i32,
                torch.tensor(-128, dtype=torch.int32),
            ),
            torch.tensor(127, dtype=torch.int32),
        ).to(torch.int8)
        return self.layer1(self.layer0(x_i8))


def example_inputs() -> tuple[torch.Tensor]:
    return (torch.tensor([[3]], dtype=torch.long),)


def build_model(model_path: str | None = None) -> torch.nn.Module:
    del model_path
    return TinyStoriesRepresentativeCoreW4A8Integer().eval()


def export_program(model_path: str | None = None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    return torch.export.export(model, example_inputs(), strict=EXPORT_STRICT)


__all__ = ["build_model", "example_inputs", "export_program"]
