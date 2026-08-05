"""Native Hugging Face source model and fixed serving-call helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModelForCausalLM

from .rc_serving_contract import (
    HIDDEN_SIZE,
    MAX_POSITION_EMBEDDINGS,
    NUM_HEADS,
    NUM_LAYERS,
    SERVING_RC_MODEL_KEY,
    VOCAB_SIZE,
    WINDOW_SIZE,
    ServingPhase,
    ServingTrace,
    argmax_lowest,
)


def attention_types_for_layers(num_layers: int) -> list[list[object]]:
    pattern = ["global", "local"]
    full_repeats, remainder = divmod(num_layers, len(pattern))
    attention_types: list[list[object]] = []
    if full_repeats:
        attention_types.append([pattern, full_repeats])
    if remainder:
        attention_types.append([pattern[:remainder], 1])
    return attention_types


def build_source_model(model_path: str | Path) -> torch.nn.Module:
    config = AutoConfig.from_pretrained(model_path, local_files_only=True)
    config.vocab_size = VOCAB_SIZE
    config.num_layers = NUM_LAYERS
    config.max_position_embeddings = MAX_POSITION_EMBEDDINGS
    config.window_size = WINDOW_SIZE
    config.hidden_size = HIDDEN_SIZE
    config.num_heads = NUM_HEADS
    config.attention_types = attention_types_for_layers(config.num_layers)
    config.attention_layers = config.expand_attention_types_params(
        config.attention_types
    )
    config.use_cache = True
    config.bos_token_id = VOCAB_SIZE - 1
    config.eos_token_id = VOCAB_SIZE - 1
    config.pad_token_id = VOCAB_SIZE - 1
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_config(config).eval()
    if model.config.model_type != "gpt_neo":
        raise ValueError(
            f"{SERVING_RC_MODEL_KEY} requires the pinned GPT-Neo TinyStories config"
        )
    return model


def native_call_kwargs(
    phase: ServingPhase, past_key_values: object | None
) -> dict[str, object]:
    return {
        "past_key_values": past_key_values,
        "use_cache": True,
        "return_dict": False,
        "attention_mask": torch.ones(
            (1, phase.cache_length_after), dtype=torch.long
        ),
        "cache_position": torch.tensor(
            phase.cache_positions, dtype=torch.long
        ),
    }


def run_native_call(
    model: object,
    phase: ServingPhase,
    input_ids: torch.Tensor,
    past_key_values: object | None,
) -> tuple[torch.Tensor, object]:
    if tuple(input_ids.shape) != (1, phase.input_length):
        raise ValueError(
            f"{phase.name} expects input shape [1, {phase.input_length}]"
        )
    with torch.no_grad():
        output = model(
            input_ids, **native_call_kwargs(phase, past_key_values)
        )
    if not isinstance(output, tuple) or len(output) < 2:
        raise RuntimeError("native source model did not return logits and cache")
    logits, returned_cache = output[0], output[1]
    if not isinstance(logits, torch.Tensor):
        raise RuntimeError("native source model logits are not a tensor")
    if tuple(logits.shape) != (1, phase.input_length, VOCAB_SIZE):
        raise RuntimeError(
            f"{phase.name} returned unexpected logits shape {tuple(logits.shape)}"
        )
    return logits, returned_cache


@dataclass(frozen=True)
class PhaseInvocation:
    phase: ServingPhase
    input_ids: torch.Tensor
    past_key_values: object | None
    trace: ServingTrace


def _greedy_token(logits: torch.Tensor) -> int:
    return argmax_lowest(logits[0, -1, :].detach().cpu().tolist())


def fresh_phase_invocation(
    model: object, trace: ServingTrace, phase_name: str
) -> PhaseInvocation:
    phases = {phase.name: phase for phase in trace.phases}
    try:
        phase = phases[phase_name]
    except KeyError as error:
        raise ValueError(f"unknown trace phase: {phase_name!r}") from error

    prompt = torch.tensor([trace.prompt_token_ids], dtype=torch.long)
    prefill = phases["prefill-8"]
    prefill_logits, cache = run_native_call(model, prefill, prompt, None)
    if phase.name == "prefill-8":
        return PhaseInvocation(phase, prompt, None, trace)

    token_8 = _greedy_token(prefill_logits)
    decode_8 = phases["decode-8"]
    decode_8_input = torch.tensor([[token_8]], dtype=torch.long)
    cache_8 = cache
    decode_8_logits, cache_9 = run_native_call(
        model, decode_8, decode_8_input, cache_8
    )
    if phase.name == "decode-8":
        return PhaseInvocation(phase, decode_8_input, cache_8, trace)

    token_9 = _greedy_token(decode_8_logits)
    decode_9_input = torch.tensor([[token_9]], dtype=torch.long)
    return PhaseInvocation(phase, decode_9_input, cache_9, trace)
