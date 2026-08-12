"""Deterministic source-model helpers for W4A8 serving conversion."""

from __future__ import annotations

from pathlib import Path

import torch

from .rc_serving_contract import ServingTrace, argmax_lowest
from .rc_serving_source import PhaseInvocation, build_source_model, run_native_call
from .rc_serving_w4a8_cache_abi import flatten_dynamic_cache, reconstruct_dynamic_cache


def build_w4a8_source_model(model_path: str | Path) -> torch.nn.Module:
    """Build the frozen FP source whose exported phases are PT2E-quantized."""

    torch.manual_seed(0)
    return build_source_model(model_path)


def snapshot_cache(cache: object, *, expected_layers: int) -> object:
    leaves = tuple(
        tensor.detach().clone()
        for tensor in flatten_dynamic_cache(cache, expected_layers=expected_layers)
    )
    return reconstruct_dynamic_cache(leaves, expected_layers=expected_layers)


def fresh_w4a8_phase_invocation(
    model: object, trace: ServingTrace, phase_name: str
) -> PhaseInvocation:
    phases = {phase.name: phase for phase in trace.phases}
    phase = phases[phase_name]
    prompt = torch.tensor([trace.prompt_token_ids], dtype=torch.long)
    prefill_logits, cache_8_mutable = run_native_call(
        model, phases["prefill-8"], prompt, None
    )
    if phase_name == "prefill-8":
        return PhaseInvocation(phase, prompt, None, trace)
    cache_8 = snapshot_cache(cache_8_mutable, expected_layers=2)
    token_8 = argmax_lowest(prefill_logits[0, -1, :].tolist())
    decode_8_input = torch.tensor([[token_8]], dtype=torch.long)
    if phase_name == "decode-8":
        return PhaseInvocation(phase, decode_8_input, cache_8, trace)
    decode_8_logits, cache_9_mutable = run_native_call(
        model, phases["decode-8"], decode_8_input, cache_8_mutable
    )
    cache_9 = snapshot_cache(cache_9_mutable, expected_layers=2)
    token_9 = argmax_lowest(decode_8_logits[0, -1, :].tolist())
    return PhaseInvocation(
        phase, torch.tensor([[token_9]], dtype=torch.long), cache_9, trace
    )
