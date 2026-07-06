from __future__ import annotations

"""Representative-core TinyStories adapter using PT2E static quantization."""

import copy
import os
from pathlib import Path
from types import MethodType

import torch
from torch import nn
import torch.nn.functional as F
from torch.ao.quantization import move_exported_model_to_eval
from torch.ao.quantization.quantize_pt2e import convert_pt2e, prepare_pt2e
from torch.ao.quantization.pt2e.representation.rewrite import (
    reference_representation_rewrite,
)
from torch.ao.quantization.quantizer.xnnpack_quantizer import (
    XNNPACKQuantizer,
    get_symmetric_quantization_config,
)
from torch.export.graph_signature import TensorArgument
from transformers import AutoConfig, AutoModelForCausalLM


EXPORT_STRICT = False

DEFAULT_VOCAB_SIZE = 32
DEFAULT_NUM_LAYERS = 2
DEFAULT_MAX_POSITION_EMBEDDINGS = 4
DEFAULT_WINDOW_SIZE = 2
DEFAULT_HIDDEN_SIZE = 2
DEFAULT_NUM_HEADS = 1


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def _qrange(bits: int) -> tuple[int, int]:
    if bits < 2:
        raise ValueError(f"PT2E static quant bits must be >= 2; got {bits}")
    qmax = (1 << (bits - 1)) - 1
    return -(qmax + 1), qmax


def _maybe_dump_quantized_graph(model: torch.nn.Module) -> None:
    dump_path = os.environ.get("TINYSTORIES_DUMP_PT2E_QUANTIZED_GRAPH")
    if dump_path is None:
        return

    graph_text = str(model.graph)
    if dump_path == "-":
        print(graph_text)
        return

    Path(dump_path).write_text(graph_text, encoding="utf-8")


def _maybe_reference_representation_rewrite(
    model: torch.fx.GraphModule,
) -> torch.fx.GraphModule:
    value = os.environ.get("TINYSTORIES_PT2E_REFERENCE_REPRESENTATION_REWRITE")
    if value is None or value in {"", "0", "false", "False"}:
        return model
    return reference_representation_rewrite(model)


def _reference_representation_rewrite_enabled() -> bool:
    value = os.environ.get("TINYSTORIES_PT2E_REFERENCE_REPRESENTATION_REWRITE")
    return value is not None and value not in {"", "0", "false", "False"}


def _materialize_missing_linear_biases(model: torch.nn.Module) -> None:
    for module in model.modules():
        if isinstance(module, torch.nn.Linear) and module.bias is None:
            module.bias = torch.nn.Parameter(torch.zeros(module.out_features))


class Int8Embedding(torch.nn.Module):
    def __init__(self, source: torch.nn.Embedding) -> None:
        super().__init__()
        weight = source.weight.detach()
        scale = torch.clamp(weight.abs().max() / 127.0, min=1.0e-12)
        weight_i8 = torch.clamp(torch.round(weight / scale), -128, 127).to(torch.int8)
        self.register_buffer("weight_i8", weight_i8)
        self.register_buffer("scale", scale.to(torch.float32))
        self.padding_idx = source.padding_idx
        self.max_norm = source.max_norm
        self.norm_type = source.norm_type
        self.scale_grad_by_freq = source.scale_grad_by_freq
        self.sparse = source.sparse

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        embedded_i8 = F.embedding(
            input_ids,
            self.weight_i8,
            self.padding_idx,
            self.max_norm,
            self.norm_type,
            self.scale_grad_by_freq,
            self.sparse,
        )
        return embedded_i8.to(torch.float32) * self.scale


def replace_embeddings_with_int8_lookup(model: torch.nn.Module) -> None:
    transformer = getattr(model, "transformer", None)
    if transformer is None:
        raise RuntimeError("expected TinyStories GPT-Neo model to expose .transformer")
    for name in ("wte", "wpe"):
        embedding = getattr(transformer, name, None)
        if not isinstance(embedding, torch.nn.Embedding):
            raise RuntimeError(f"expected transformer.{name} to be an Embedding")
        setattr(transformer, name, Int8Embedding(embedding))


def _decompose_out_dtype(model: torch.fx.GraphModule) -> torch.fx.GraphModule:
    graph = model.graph
    for node in list(graph.nodes):
        if node.op != "call_function" or node.target != torch.ops.higher_order.out_dtype:
            continue
        op, output_dtype, *op_args = node.args
        with graph.inserting_before(node):
            op_node = graph.call_function(op, args=tuple(op_args))
            to_node = graph.call_function(
                torch.ops.aten.to.dtype,
                args=(op_node, output_dtype),
            )
        node.replace_all_uses_with(to_node)
        graph.erase_node(node)
    graph.lint()
    model.recompile()
    return model


def _single_token_attn_without_causal_bias(
    self: torch.nn.Module,
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
    head_mask: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    query = query.to(torch.float32)
    key = key.to(torch.float32)

    attn_weights = torch.matmul(query, key.transpose(-1, -2))

    if attention_mask is not None:
        attn_weights = attn_weights + attention_mask[:, :, :, : key.shape[-2]]

    attn_weights = nn.functional.softmax(attn_weights, dim=-1)
    attn_weights = attn_weights.to(value.dtype)
    attn_weights = self.attn_dropout(attn_weights)

    if head_mask is not None:
        attn_weights = attn_weights * head_mask

    return torch.matmul(attn_weights, value), attn_weights


def replace_attention_with_hardware_friendly_attention(model: torch.nn.Module) -> None:
    for module in model.modules():
        if all(hasattr(module, name) for name in ("q_proj", "k_proj", "v_proj", "out_proj")):
            module._attn = MethodType(_single_token_attn_without_causal_bias, module)


def _no_single_token_causal_mask(
    self: torch.nn.Module,
    attention_mask: torch.Tensor | None,
    input_tensor: torch.Tensor,
    cache_position: torch.Tensor,
    past_key_values: object,
    output_attentions: bool = False,
) -> None:
    return None


def disable_single_token_causal_mask(model: torch.nn.Module) -> None:
    transformer = getattr(model, "transformer", None)
    if transformer is None:
        raise RuntimeError("expected TinyStories GPT-Neo model to expose .transformer")
    transformer._update_causal_mask = MethodType(_no_single_token_causal_mask, transformer)


def attention_types_for_layers(num_layers: int) -> list[list[object]]:
    pattern = ["global", "local"]
    full_repeats, remainder = divmod(num_layers, len(pattern))
    attention_types: list[list[object]] = []
    if full_repeats:
        attention_types.append([pattern, full_repeats])
    if remainder:
        attention_types.append([pattern[:remainder], 1])
    return attention_types


def _strip_trailing_output_dequantize(
    exported: torch.export.ExportedProgram,
) -> torch.export.ExportedProgram:
    graph = copy.deepcopy(exported.graph)
    output_node = next(node for node in graph.nodes if node.op == "output")
    returned = output_node.args[0]
    if not (
        isinstance(returned, tuple)
        and len(returned) == 1
        and isinstance(returned[0], torch.fx.Node)
    ):
        raise RuntimeError("expected a single-tensor model output")

    dequant = returned[0]
    if dequant.target != torch.ops.quantized_decomposed.dequantize_per_tensor.default:
        raise RuntimeError("expected trailing dequantize_per_tensor at model output")

    quantized = dequant.args[0]
    if not isinstance(quantized, torch.fx.Node):
        raise RuntimeError("expected quantized tensor node before output dequantize")
    if quantized.target != torch.ops.quantized_decomposed.quantize_per_tensor.default:
        raise RuntimeError("expected output dequantize to consume quantize_per_tensor")

    output_node.args = ((quantized,),)
    graph.lint()

    graph_signature = copy.deepcopy(exported.graph_signature)
    if len(graph_signature.output_specs) != 1:
        raise RuntimeError("expected a single output spec for TinyStories export")
    graph_signature.output_specs[0].arg = TensorArgument(name=quantized.name)

    return torch.export.ExportedProgram(
        exported.graph_module,
        graph,
        graph_signature,
        exported.state_dict,
        exported.range_constraints,
        exported.module_call_graph,
        exported.example_inputs,
        exported.constants,
        verifiers=exported.verifiers,
    )


def build_representative_core_config(model_path: str | None) -> object:
    if model_path is None:
        raise RuntimeError("TinyStories adapter requires --model-path")

    config = AutoConfig.from_pretrained(model_path, local_files_only=True)
    config.vocab_size = env_int("TINYSTORIES_CORE_VOCAB_SIZE", DEFAULT_VOCAB_SIZE)
    config.num_layers = env_int("TINYSTORIES_CORE_NUM_LAYERS", DEFAULT_NUM_LAYERS)
    config.max_position_embeddings = env_int(
        "TINYSTORIES_CORE_MAX_POSITION_EMBEDDINGS",
        DEFAULT_MAX_POSITION_EMBEDDINGS,
    )
    config.window_size = env_int("TINYSTORIES_CORE_WINDOW_SIZE", DEFAULT_WINDOW_SIZE)
    config.hidden_size = env_int("TINYSTORIES_CORE_HIDDEN_SIZE", DEFAULT_HIDDEN_SIZE)
    config.num_heads = env_int("TINYSTORIES_CORE_NUM_HEADS", DEFAULT_NUM_HEADS)
    config.attention_types = attention_types_for_layers(config.num_layers)
    config.attention_layers = config.expand_attention_types_params(config.attention_types)
    config.use_cache = False
    config.bos_token_id = config.vocab_size - 1
    config.eos_token_id = config.vocab_size - 1
    return config


def build_base_model_from_config(config: object) -> torch.nn.Module:
    torch.manual_seed(0)
    return AutoModelForCausalLM.from_config(config).eval()


def apply_model_simplifications(model: torch.nn.Module) -> torch.nn.Module:
    replace_embeddings_with_int8_lookup(model)
    replace_attention_with_hardware_friendly_attention(model)
    disable_single_token_causal_mask(model)
    return model


def build_model(model_path: str | None) -> torch.nn.Module:
    config = build_representative_core_config(model_path)
    model = build_base_model_from_config(config)
    return apply_model_simplifications(model)


def example_inputs() -> tuple[torch.Tensor, ...]:
    return (torch.zeros((1, 1), dtype=torch.long),)


def export_simplified_model(
    model: torch.nn.Module,
    inputs: tuple[torch.Tensor, ...],
) -> torch.export.ExportedProgram:
    return torch.export.export(
        model,
        inputs,
        strict=EXPORT_STRICT,
    )


def build_pt2e_quantizer() -> XNNPACKQuantizer:
    activation_bits = env_int("TINYSTORIES_PYTORCHAO_ACTIVATION_BITS", 8)
    weight_bits = env_int("TINYSTORIES_PYTORCHAO_WEIGHT_BITS", 8)
    activation_qmin, activation_qmax = _qrange(activation_bits)
    weight_qmin, weight_qmax = _qrange(weight_bits)
    return XNNPACKQuantizer().set_global(
        get_symmetric_quantization_config(
            is_dynamic=False,
            act_qmin=activation_qmin,
            act_qmax=activation_qmax,
            weight_qmin=weight_qmin,
            weight_qmax=weight_qmax,
        )
    )


def quantize_exported_program(
    exported: torch.export.ExportedProgram,
    inputs: tuple[torch.Tensor, ...],
) -> torch.fx.GraphModule:
    quantizer = build_pt2e_quantizer()
    prepared = prepare_pt2e(exported.module(), quantizer)
    with torch.no_grad():
        prepared(*inputs)
    return convert_pt2e(prepared)


def apply_quantized_export_cleanup(
    quantized: torch.fx.GraphModule,
    inputs: tuple[torch.Tensor, ...],
    use_reference_rewrite: bool,
) -> torch.export.ExportedProgram:
    cleaned = _maybe_reference_representation_rewrite(quantized)
    if use_reference_rewrite:
        cleaned = _decompose_out_dtype(cleaned)
    move_exported_model_to_eval(cleaned)
    exported = torch.export.export(
        cleaned,
        inputs,
        strict=EXPORT_STRICT,
    )
    if use_reference_rewrite:
        return exported
    return _strip_trailing_output_dequantize(exported)


def export_program(model_path: str | None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    use_reference_rewrite = _reference_representation_rewrite_enabled()
    if use_reference_rewrite:
        _materialize_missing_linear_biases(model)
    inputs = tuple(example_inputs())

    simplified = export_simplified_model(model, inputs)
    quantized = quantize_exported_program(simplified, inputs)
    _maybe_dump_quantized_graph(quantized)
    return apply_quantized_export_cleanup(quantized, inputs, use_reference_rewrite)
