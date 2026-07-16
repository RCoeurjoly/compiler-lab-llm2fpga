"""Shared, standard PT2E W8A8 export helpers for the RC structural study."""

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

from quantized_rc_study_input import (
    load_full_token_ids,
    map_full_token_ids_to_reduced_vocab,
)


STUDY_CONTEXT_LENGTH = 8


def require_study_context_length() -> None:
    configured = os.environ.get("TINYSTORIES_RC_STUDY_CONTEXT_LENGTH")
    if configured is not None and int(configured) != STUDY_CONTEXT_LENGTH:
        raise ValueError(
            "quantized RC study only supports the frozen eight-token context"
        )


def study_example_inputs(vocab_size: int | None = None) -> tuple[torch.Tensor, ...]:
    require_study_context_length()
    token_ids = load_full_token_ids()
    if vocab_size is not None:
        token_ids = map_full_token_ids_to_reduced_vocab(token_ids, vocab_size)
    return (torch.tensor([token_ids], dtype=torch.long),)


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
        raise RuntimeError("expected output quantize_per_tensor")

    output_node.args = ((quantized,),)
    graph.lint()

    graph_signature = copy.deepcopy(exported.graph_signature)
    if len(graph_signature.output_specs) != 1:
        raise RuntimeError("expected one TinyStories output")
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


def export_pt2e_w8a8(
    model: torch.nn.Module,
    example_inputs: tuple[torch.Tensor, ...],
    calibration_inputs: tuple[tuple[torch.Tensor, ...], ...],
) -> torch.export.ExportedProgram:
    """Export a static XNNPACK W8A8 model using the supplied frozen inputs."""

    exported = torch.export.export(model, example_inputs, strict=False)
    quantizer = XNNPACKQuantizer().set_global(
        get_symmetric_quantization_config(
            is_dynamic=False,
            act_qmin=-128,
            act_qmax=127,
            weight_qmin=-128,
            weight_qmax=127,
        )
    )
    prepared = prepare_pt2e(exported.module(), quantizer)
    with torch.no_grad():
        for calibration_input in calibration_inputs:
            prepared(*calibration_input)
    quantized = convert_pt2e(prepared)
    move_exported_model_to_eval(quantized)
    return _strip_trailing_output_dequantize(
        torch.export.export(quantized, example_inputs, strict=False)
    )
