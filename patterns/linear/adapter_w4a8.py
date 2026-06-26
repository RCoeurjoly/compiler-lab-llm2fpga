from __future__ import annotations

import copy
import os

import torch
from torch.ao.quantization import move_exported_model_to_eval
from torch.ao.quantization.quantize_pt2e import convert_pt2e, prepare_pt2e
from torch.ao.quantization.quantizer.xnnpack_quantizer import (
    XNNPACKQuantizer,
    get_symmetric_quantization_config,
)
from torch.export.graph_signature import TensorArgument

from inputs import example_inputs
from model import build_model as build_pattern_model


EXPORT_STRICT = False


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def qrange(bits: int) -> tuple[int, int]:
    if bits < 2:
        raise ValueError(f"quantization bits must be >= 2; got {bits}")
    qmax = (1 << (bits - 1)) - 1
    return -(qmax + 1), qmax


def build_model(model_path: str | None = None) -> torch.nn.Module:
    del model_path
    return build_pattern_model()


def strip_trailing_output_dequantize(
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
        raise RuntimeError("expected a single output spec")
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


def export_program(model_path: str | None = None) -> torch.export.ExportedProgram:
    model = build_model(model_path)
    inputs = tuple(example_inputs())
    exported = torch.export.export(model, inputs, strict=EXPORT_STRICT)

    activation_bits = env_int("TINYSTORIES_PYTORCHAO_ACTIVATION_BITS", 8)
    weight_bits = env_int("TINYSTORIES_PYTORCHAO_WEIGHT_BITS", 4)
    activation_qmin, activation_qmax = qrange(activation_bits)
    weight_qmin, weight_qmax = qrange(weight_bits)
    quantizer = XNNPACKQuantizer().set_global(
        get_symmetric_quantization_config(
            is_dynamic=False,
            act_qmin=activation_qmin,
            act_qmax=activation_qmax,
            weight_qmin=weight_qmin,
            weight_qmax=weight_qmax,
        )
    )

    prepared = prepare_pt2e(exported.module(), quantizer)
    with torch.no_grad():
        prepared(*inputs)
    quantized = convert_pt2e(prepared)
    move_exported_model_to_eval(quantized)

    quantized_exported = torch.export.export(
        quantized,
        inputs,
        strict=EXPORT_STRICT,
    )
    return strip_trailing_output_dequantize(quantized_exported)


__all__ = ["build_model", "example_inputs", "export_program"]
