"""Torch-exportable fixed q/k projection boundary for TinyStories-1M."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import torch

Q_BOUNDARY = "transformer.h.0.attn.attention.q_proj.output"
K_BOUNDARY = "transformer.h.0.attn.attention.k_proj.output"


class FixedQKTraceExportError(RuntimeError):
    def __init__(self, code: str, unsupported_op: str, message: str):
        super().__init__(f"{code}: {unsupported_op}: {message}")
        self.code = code
        self.unsupported_op = unsupported_op


def _round_away(value: torch.Tensor) -> torch.Tensor:
    return torch.where(value < 0, torch.ceil(value - 0.5), torch.floor(value + 0.5))


def _validate_scale_list(scales: list[int]) -> None:
    if not scales or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 or v >= (1 << 24) for v in scales):
        raise ValueError("scales must be positive unsigned 24-bit integers")


def _boundary_scales_q24(boundary: Mapping[str, Any]) -> list[int]:
    scales = boundary.get("scales")
    if not isinstance(scales, list) or len(scales) != 64:
        raise ValueError("activation_scale_width_mismatch")
    result = [int(round(float(value) * (1 << 24))) for value in scales]
    _validate_scale_list(result)
    return result


def qk_scales_q24_from_boundaries(boundaries: Mapping[str, Any]) -> tuple[list[int], list[int]]:
    q_boundary = boundaries.get(Q_BOUNDARY)
    k_boundary = boundaries.get(K_BOUNDARY)
    if not isinstance(q_boundary, Mapping) or not isinstance(k_boundary, Mapping):
        raise ValueError("qk_activation_boundaries_missing")
    return _boundary_scales_q24(q_boundary), _boundary_scales_q24(k_boundary)


def fixed_qdq(value: torch.Tensor, scales_q24: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Return int8 codes and q16.16 dequantized values, channel-wise."""
    if value.shape[-1] != scales_q24.numel():
        raise ValueError("scale_width_mismatch")
    # Validate eager callers directly; export receives constructor-validated
    # constant buffers and cannot evaluate data-dependent Python branches.
    if not torch.compiler.is_compiling():
        if scales_q24.dtype != torch.int64 or scales_q24.numel() == 0:
            raise ValueError("scales must be positive unsigned 24-bit integers")
        if bool(torch.any((scales_q24 <= 0) | (scales_q24 >= (1 << 24))).item()):
            raise ValueError("scales must be positive unsigned 24-bit integers")
    scales = scales_q24.reshape((1,) * (value.ndim - 1) + (-1,)).to(torch.int64)
    q16 = _round_away(value * 65536.0).to(torch.int64)
    numerator = q16 * 256
    magnitude = (torch.abs(numerator) + scales // 2) // scales
    codes = torch.where(numerator < 0, -magnitude, magnitude)
    codes = torch.clamp(codes, -128, 127).to(torch.int8)
    dequant_num = codes.to(torch.int64) * scales
    dequant_mag = (torch.abs(dequant_num) + 128) // 256
    dequant = torch.where(dequant_num < 0, -dequant_mag, dequant_mag)
    return codes, dequant


class FixedQKProjection(torch.nn.Module):
    """Wrap q/k projections with the authenticated fixed QDQ boundary."""

    def __init__(self, q_proj: torch.nn.Module, k_proj: torch.nn.Module, q_scales_q24: list[int], k_scales_q24: list[int]):
        super().__init__()
        for scales in (q_scales_q24, k_scales_q24):
            _validate_scale_list(scales)
        self.q_proj = q_proj
        self.k_proj = k_proj
        self.register_buffer("q_scales_q24", torch.tensor(q_scales_q24, dtype=torch.int64))
        self.register_buffer("k_scales_q24", torch.tensor(k_scales_q24, dtype=torch.int64))

    def forward(self, hidden: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        q_float = self.q_proj(hidden)
        k_float = self.k_proj(hidden)
        q_codes, q_fixed = fixed_qdq(q_float, self.q_scales_q24)
        k_codes, k_fixed = fixed_qdq(k_float, self.k_scales_q24)
        return q_codes, q_fixed, k_codes, k_fixed


class FixedQKBlockZeroTokenStepTrace(torch.nn.Module):
    """Block-0 token trace with q/k fixed QDQ inserted before score matmul."""

    checkpoint_names = (
        "block.input",
        "block.ln_1.output",
        "block.attention.q.int8",
        "block.attention.q.dequant_q16_16",
        "block.attention.k.int8",
        "block.attention.k.dequant_q16_16",
        "block.attention.v",
        "block.attention.output",
        "block.residual.attention",
        "block.ln_2.output",
        "block.mlp.fc_in",
        "block.mlp.activation",
        "block.mlp.fc_out",
        "block.output",
    )

    def __init__(self, model: torch.nn.Module, q_scales_q24: list[int], k_scales_q24: list[int]):
        super().__init__()
        _validate_scale_list(q_scales_q24)
        _validate_scale_list(k_scales_q24)
        self.transformer = model.transformer
        self.num_heads = int(model.config.num_heads)
        self.head_dim = int(model.config.hidden_size // model.config.num_heads)
        if len(q_scales_q24) != self.num_heads * self.head_dim or len(k_scales_q24) != self.num_heads * self.head_dim:
            raise ValueError("activation_scale_width_mismatch")
        self.register_buffer("q_scales_q24", torch.tensor(q_scales_q24, dtype=torch.int64))
        self.register_buffer("k_scales_q24", torch.tensor(k_scales_q24, dtype=torch.int64))

    def forward(self, input_ids: torch.Tensor) -> tuple[torch.Tensor, ...]:
        batch, sequence = input_ids.shape
        positions = torch.arange(sequence, device=input_ids.device).unsqueeze(0).expand(batch, sequence)
        hidden = self.transformer.drop(self.transformer.wte(input_ids) + self.transformer.wpe(positions))
        block = self.transformer.h[0]
        block_input = hidden[:, -1, :]
        ln_1 = block.ln_1(hidden)
        attention = block.attn.attention

        q_float = attention.q_proj(ln_1)
        k_float = attention.k_proj(ln_1)
        q_codes_flat, q_fixed_flat = fixed_qdq(q_float, self.q_scales_q24)
        k_codes_flat, k_fixed_flat = fixed_qdq(k_float, self.k_scales_q24)

        q_codes = q_codes_flat.view(batch, sequence, self.num_heads, self.head_dim).transpose(1, 2)
        k_codes = k_codes_flat.view(batch, sequence, self.num_heads, self.head_dim).transpose(1, 2)
        q_fixed = q_fixed_flat.view(batch, sequence, self.num_heads, self.head_dim).transpose(1, 2)
        k_fixed = k_fixed_flat.view(batch, sequence, self.num_heads, self.head_dim).transpose(1, 2)
        q_for_scores = q_fixed.to(torch.float32) / 65536.0
        k_for_scores = k_fixed.to(torch.float32) / 65536.0

        v = attention.v_proj(ln_1).view(batch, sequence, self.num_heads, self.head_dim).transpose(1, 2)
        scores = torch.matmul(q_for_scores, k_for_scores.transpose(-1, -2))
        causal = torch.ones((sequence, sequence), dtype=torch.bool, device=input_ids.device).tril()
        scores = torch.where(causal, scores, torch.full_like(scores, torch.finfo(scores.dtype).min))
        probabilities = torch.softmax(scores, dim=-1)
        merged = torch.matmul(probabilities, v).transpose(1, 2).contiguous().view(batch, sequence, -1)
        attention_output_all = attention.out_proj(merged)
        residual_attention_all = hidden + attention_output_all
        ln_2_all = block.ln_2(residual_attention_all)
        fc_in_all = block.mlp.c_fc(ln_2_all)
        activation_all = block.mlp.act(fc_in_all)
        fc_out_all = block.mlp.c_proj(activation_all)
        block_output_all = residual_attention_all + fc_out_all
        return (
            block_input[0],
            ln_1[0, -1],
            q_codes[0, :, -1, :],
            q_fixed[0, :, -1, :],
            k_codes[0, :, -1, :],
            k_fixed[0, :, -1, :],
            v[0, :, -1, :],
            attention_output_all[0, -1],
            residual_attention_all[0, -1],
            ln_2_all[0, -1],
            fc_in_all[0, -1],
            activation_all[0, -1],
            fc_out_all[0, -1],
            block_output_all[0, -1],
        )


def export_block0_fixed_qk_trace(
    module: FixedQKBlockZeroTokenStepTrace, prompt: torch.Tensor
) -> torch.export.ExportedProgram:
    try:
        return torch.export.export(module, (prompt,), strict=False)
    except Exception as error:
        raise FixedQKTraceExportError(
            "torch_export_fixed_qk_qdq_unsupported",
            "TinyStories.fixed_qk_trace.fixed_qdq",
            str(error),
        ) from error


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_probe_metadata(bundle: Any, profile_path: Path | str, module: FixedQKBlockZeroTokenStepTrace) -> dict[str, Any]:
    profile_path = Path(profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    checkpoints = {
        "block.input": {"shape": [64], "dtype": "torch.float32"},
        "block.ln_1.output": {"shape": [64], "dtype": "torch.float32"},
        "block.attention.q.int8": {"shape": [16, 4], "dtype": "torch.int8", "scale": "per-head/per-channel q8.24"},
        "block.attention.q.dequant_q16_16": {"shape": [16, 4], "dtype": "torch.int64", "scale": "signed q16.16"},
        "block.attention.k.int8": {"shape": [16, 4], "dtype": "torch.int8", "scale": "per-head/per-channel q8.24"},
        "block.attention.k.dequant_q16_16": {"shape": [16, 4], "dtype": "torch.int64", "scale": "signed q16.16"},
        "block.attention.v": {"shape": [16, 4], "dtype": "torch.float32"},
        "block.attention.output": {"shape": [64], "dtype": "torch.float32"},
        "block.residual.attention": {"shape": [64], "dtype": "torch.float32"},
        "block.ln_2.output": {"shape": [64], "dtype": "torch.float32"},
        "block.mlp.fc_in": {"shape": [256], "dtype": "torch.float32"},
        "block.mlp.activation": {"shape": [256], "dtype": "torch.float32"},
        "block.mlp.fc_out": {"shape": [64], "dtype": "torch.float32"},
        "block.output": {"shape": [64], "dtype": "torch.float32"},
    }
    return {
        "schema": "tinystories-1m-block0-fixed-qk-trace-probe-v1",
        "status": "probe_boundary_only",
        "claims": {
            "compiler_equivalence": False,
            "rtl_equivalence": False,
            "hardware_inference": False,
            "full_block_semantics": False,
        },
        "identity": {
            "contract_sha256": bundle.receipt["identity"]["contract_sha256"],
            "package_manifest_sha256": bundle.receipt["identity"]["package"]["manifest_sha256"],
            "profile_artifact_sha256": _sha256_file(profile_path),
            "profile_sha256": profile.get("profile_sha256"),
            "block_index": 0,
            "token_index": len(bundle.contract["reference"]["prompt_tokens"]) - 1,
            "prompt_tokens": bundle.contract["reference"]["prompt_tokens"],
        },
        "qk_boundaries": {"q": Q_BOUNDARY, "k": K_BOUNDARY},
        "checkpoint_order": list(module.checkpoint_names),
        "checkpoints": checkpoints,
        "note": (
            "Only q/k projection QDQ and its placement before attention scores are represented here; "
            "LayerNorm, softmax, GELU, and remaining block semantics are not fixed-profile equivalence claims."
        ),
    }
