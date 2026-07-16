"""Structure-preserving TinyStories PT2E W8A8 representative-core adapter."""

from __future__ import annotations

import os

import torch
from transformers import AutoConfig, AutoModelForCausalLM

from pt2e_w8a8_study import export_pt2e_w8a8, study_example_inputs


EXPORT_STRICT = False

DEFAULT_VOCAB_SIZE = 32
DEFAULT_NUM_LAYERS = 2
DEFAULT_MAX_POSITION_EMBEDDINGS = 8
DEFAULT_WINDOW_SIZE = 4
DEFAULT_HIDDEN_SIZE = 4
DEFAULT_NUM_HEADS = 1


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def attention_types_for_layers(num_layers: int) -> list[list[object]]:
    pattern = ["global", "local"]
    full_repeats, remainder = divmod(num_layers, len(pattern))
    attention_types: list[list[object]] = []
    if full_repeats:
        attention_types.append([pattern, full_repeats])
    if remainder:
        attention_types.append([pattern[:remainder], 1])
    return attention_types


def representative_core_config(model_path: str | None) -> object:
    if model_path is None:
        raise RuntimeError("TinyStories adapter requires --model-path")

    config = AutoConfig.from_pretrained(model_path, local_files_only=True)
    config.vocab_size = env_int("TINYSTORIES_RC_STUDY_VOCAB_SIZE", DEFAULT_VOCAB_SIZE)
    config.num_layers = env_int("TINYSTORIES_RC_STUDY_NUM_LAYERS", DEFAULT_NUM_LAYERS)
    config.max_position_embeddings = env_int(
        "TINYSTORIES_RC_STUDY_MAX_POSITION_EMBEDDINGS",
        DEFAULT_MAX_POSITION_EMBEDDINGS,
    )
    config.window_size = env_int("TINYSTORIES_RC_STUDY_WINDOW_SIZE", DEFAULT_WINDOW_SIZE)
    config.hidden_size = env_int("TINYSTORIES_RC_STUDY_HIDDEN_SIZE", DEFAULT_HIDDEN_SIZE)
    config.num_heads = env_int("TINYSTORIES_RC_STUDY_NUM_HEADS", DEFAULT_NUM_HEADS)
    if config.num_layers < 2:
        raise ValueError("RC study requires both global and local attention layers")
    if config.hidden_size % config.num_heads:
        raise ValueError("RC hidden size must be divisible by its head count")
    if config.max_position_embeddings < 8:
        raise ValueError("RC study requires an eight-position context")

    config.attention_types = attention_types_for_layers(config.num_layers)
    config.attention_layers = config.expand_attention_types_params(config.attention_types)
    config.use_cache = False
    config.bos_token_id = config.vocab_size - 1
    config.eos_token_id = config.vocab_size - 1
    return config


def build_model(model_path: str | None) -> torch.nn.Module:
    config = representative_core_config(model_path)
    torch.manual_seed(0)
    return AutoModelForCausalLM.from_config(config).eval()


def example_inputs() -> tuple[torch.Tensor, ...]:
    vocab_size = env_int("TINYSTORIES_RC_STUDY_VOCAB_SIZE", DEFAULT_VOCAB_SIZE)
    return study_example_inputs(vocab_size=vocab_size)


def export_program(model_path: str | None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    inputs = study_example_inputs(vocab_size=model.config.vocab_size)
    return export_pt2e_w8a8(model, inputs, (inputs,))
