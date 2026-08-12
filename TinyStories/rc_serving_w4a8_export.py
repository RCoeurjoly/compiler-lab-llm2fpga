"""Freeze signed W4 tensors from converted PT2E serving-phase programs."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import torch
from torch.ao.quantization import move_exported_model_to_eval
from torch.ao.quantization.quantize_pt2e import convert_pt2e, prepare_pt2e
from torch.ao.quantization.quantizer.xnnpack_quantizer import (
    XNNPACKQuantizer,
    get_symmetric_quantization_config,
)

from .rc_serving_w4a8_contract import (
    ACTIVATION_BITS,
    ACTIVATION_MAX,
    ACTIVATION_MIN,
    NIBBLE_ORDER,
    PADDING_MODE,
    PHASE_NAMES,
    ROUNDING_MODE,
    SATURATION_MODE,
    W4A8_MODEL_KEY,
    WEIGHT_BITS,
    WEIGHT_MAX,
    WEIGHT_MIN,
    validate_manifest,
)
from .rc_serving_contract import load_trace
from .rc_serving_w4a8_cache_abi import TensorCachePhaseWrapper, flatten_dynamic_cache
from .rc_serving_evidence import enable_hf_dynamic_cache_export_support, tensor_record
from .rc_serving_w4a8_source import build_w4a8_source_model, fresh_w4a8_phase_invocation


@dataclass(frozen=True)
class FrozenTensorRecord:
    name: str
    shape: tuple[int, ...]
    bits: int
    signed: bool
    element_count: int
    packed_byte_count: int
    sha256: str
    offset: int
    phases: tuple[str, ...]
    source_names: tuple[str, ...]

    def manifest_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "shape": list(self.shape),
            "bits": self.bits,
            "signed": self.signed,
            "element_count": self.element_count,
            "packed_byte_count": self.packed_byte_count,
            "sha256": self.sha256,
            "offset": self.offset,
            "phases": list(self.phases),
            "source_names": list(self.source_names),
        }


def convert_w4a8_program(
    model: torch.nn.Module,
    example_inputs: tuple[object, ...],
    example_kwargs: Mapping[str, object] | None = None,
) -> torch.export.ExportedProgram:
    kwargs = dict(example_kwargs or {})
    exported = torch.export.export(model, example_inputs, kwargs=kwargs, strict=False)
    quantizer = XNNPACKQuantizer().set_global(
        get_symmetric_quantization_config(
            is_dynamic=False,
            act_qmin=ACTIVATION_MIN,
            act_qmax=ACTIVATION_MAX,
            weight_qmin=WEIGHT_MIN,
            weight_qmax=WEIGHT_MAX,
        )
    )
    prepared = prepare_pt2e(exported.module(), quantizer)
    with torch.no_grad():
        prepared(*example_inputs, **kwargs)
    converted = convert_pt2e(prepared)
    move_exported_model_to_eval(converted)
    return torch.export.export(converted, example_inputs, kwargs=kwargs, strict=False)


def integer_weight_tensors(exported: object) -> dict[str, torch.Tensor]:
    return dict(_named_integer_weights(exported))


def phase_bundle_manifest(phase_digests: Mapping[str, str]) -> dict[str, object]:
    if tuple(phase_digests) != PHASE_NAMES:
        raise ValueError("converted phases are not in canonical order")
    return {
        "schema_version": 1,
        "artifact_kind": "w4a8-serving-phase-bundle",
        "model_key": W4A8_MODEL_KEY,
        "numeric_format": "pt2e-static-w4a8",
        "converted_phases": [
            {
                "name": name,
                "path": name,
                "exported_program_sha256": phase_digests[name],
            }
            for name in PHASE_NAMES
        ],
    }


def pack_signed_nibbles(values: torch.Tensor) -> bytes:
    flat = values.detach().cpu().contiguous().reshape(-1).to(torch.int64)
    integers = [int(value) for value in flat.tolist()]
    if any(value < WEIGHT_MIN or value > WEIGHT_MAX for value in integers):
        raise ValueError("weight tensor contains a value outside signed W4 range")
    packed = bytearray()
    for index in range(0, len(integers), 2):
        even = integers[index] & 0xF
        odd = integers[index + 1] & 0xF if index + 1 < len(integers) else 0
        packed.append(even | (odd << 4))
    return bytes(packed)


def _named_integer_weights(exported: object) -> list[tuple[str, torch.Tensor]]:
    placeholder_targets: dict[str, str] = {}
    signature = getattr(exported, "graph_signature", None)
    for spec in getattr(signature, "input_specs", ()):
        argument = getattr(spec, "arg", None)
        target = getattr(spec, "target", None)
        argument_name = getattr(argument, "name", None)
        if isinstance(argument_name, str) and isinstance(target, str):
            placeholder_targets[argument_name] = target
    bound_names: set[str] = set()
    graph = getattr(exported, "graph", None)
    if graph is not None:
        for node in graph.nodes:
            target = str(getattr(node, "target", ""))
            args = getattr(node, "args", ())
            if (
                "quantized_decomposed.dequantize_per_tensor.default" in target
                and len(args) >= 5
                and args[3] == WEIGHT_MIN
                and args[4] == WEIGHT_MAX
                and isinstance(args[0], torch.fx.Node)
            ):
                placeholder = str(args[0].target)
                bound_names.add(placeholder_targets.get(placeholder, placeholder))
    found: list[tuple[str, torch.Tensor]] = []
    for category in ("state_dict", "constants"):
        values = getattr(exported, category, None)
        if not isinstance(values, Mapping):
            raise ValueError(f"converted program has no {category} mapping")
        for name, tensor in values.items():
            if (
                isinstance(name, str)
                and isinstance(tensor, torch.Tensor)
                and tensor.dtype in (torch.int8, torch.uint8)
                and (name in bound_names or "weight" in name.lower())
            ):
                found.append((f"{category}/{name}", tensor))
    return sorted(found, key=lambda item: item[0])


def quantized_tensor_records(
    exported_phases: Mapping[str, object],
) -> tuple[tuple[FrozenTensorRecord, ...], bytes]:
    if tuple(exported_phases) != PHASE_NAMES:
        raise ValueError("converted phases are not in canonical order")
    grouped: dict[tuple[tuple[int, ...], bytes], list[tuple[str, str]]] = {}
    for phase, exported in exported_phases.items():
        for source_name, tensor in _named_integer_weights(exported):
            packed = pack_signed_nibbles(tensor)
            key = (tuple(int(value) for value in tensor.shape), packed)
            grouped.setdefault(key, []).append((phase, source_name))
    if not grouped:
        raise ValueError("converted programs contain no signed W4 weight tensors")

    image = bytearray()
    records: list[FrozenTensorRecord] = []
    ordered = sorted(grouped.items(), key=lambda item: (hashlib.sha256(item[0][1]).hexdigest(), item[0][0]))
    for ordinal, ((shape, packed), references) in enumerate(ordered):
        digest = hashlib.sha256(packed).hexdigest()
        records.append(
            FrozenTensorRecord(
                name=f"weight_{ordinal:04d}_{digest[:12]}",
                shape=shape,
                bits=WEIGHT_BITS,
                signed=True,
                element_count=math.prod(shape),
                packed_byte_count=len(packed),
                sha256=digest,
                offset=len(image),
                phases=tuple(dict.fromkeys(phase for phase, _ in references)),
                source_names=tuple(f"{phase}:{name}" for phase, name in references),
            )
        )
        image.extend(packed)
    return tuple(records), bytes(image)


def write_frozen_tensor_bundle(
    exported_phases: Mapping[str, object], out_dir: Path
) -> None:
    records, image = quantized_tensor_records(exported_phases)
    payload = {
        "schema_version": 1,
        "model_key": W4A8_MODEL_KEY,
        "quantization": {
            "weights": {"bits": WEIGHT_BITS, "signed": True, "minimum": WEIGHT_MIN, "maximum": WEIGHT_MAX},
            "activations": {"bits": ACTIVATION_BITS, "signed": True, "minimum": ACTIVATION_MIN, "maximum": ACTIVATION_MAX},
            "rounding": ROUNDING_MODE,
            "saturation": SATURATION_MODE,
        },
        "packing": {"nibble_order": NIBBLE_ORDER, "padding": PADDING_MODE},
        "phases": list(PHASE_NAMES),
        "tensors": [record.manifest_record() for record in records],
        "weights_sha256": hashlib.sha256(image).hexdigest(),
        "weights_byte_count": len(image),
    }
    validate_manifest(payload)
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "weights.bin").write_bytes(image)
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def materialize_w4a8_bundle(model_path: Path, trace_path: Path, out_dir: Path) -> None:
    trace = load_trace(trace_path)
    out_dir.mkdir(parents=True, exist_ok=False)
    converted_phases: dict[str, torch.export.ExportedProgram] = {}
    phase_digests: dict[str, str] = {}
    enable_hf_dynamic_cache_export_support()
    for phase_name in PHASE_NAMES:
        torch._dynamo.reset()
        model = build_w4a8_source_model(model_path)
        invocation = fresh_w4a8_phase_invocation(model, trace, phase_name)
        cache_inputs = (
            ()
            if invocation.past_key_values is None
            else flatten_dynamic_cache(invocation.past_key_values, expected_layers=2)
        )
        wrapper = TensorCachePhaseWrapper(model, invocation.phase, expected_layers=2)
        example_inputs = (invocation.input_ids,) + cache_inputs
        converted = convert_w4a8_program(wrapper, example_inputs)
        phase_dir = out_dir / phase_name
        phase_dir.mkdir()
        exported_path = phase_dir / "exported.pt2"
        torch.export.save(converted, exported_path)
        (phase_dir / "graph.txt").write_text(str(converted.graph) + "\n", encoding="utf-8")
        (phase_dir / "graph-module.py").write_text(converted.graph_module.code + "\n", encoding="utf-8")
        (phase_dir / "graph-signature.txt").write_text(str(converted.graph_signature) + "\n", encoding="utf-8")
        with torch.no_grad():
            output = converted.module()(*example_inputs)
        if not isinstance(output, tuple) or len(output) != 5 or not isinstance(output[0], torch.Tensor):
            raise RuntimeError(f"{phase_name} converted program did not return logits and cache")
        _write_json(
            phase_dir / "reference.json",
            {
                "name": phase_name,
                "input_token_ids": [int(value) for value in invocation.input_ids[0].tolist()],
                "last_logits": tensor_record(output[0][0, -1, :]),
                "cache_leaves": [tensor_record(tensor) for tensor in output[1:]],
            },
        )
        digest = hashlib.sha256(exported_path.read_bytes()).hexdigest()
        phase_digests[phase_name] = digest
        converted_phases[phase_name] = converted

    frozen_dir = out_dir / "frozen"
    write_frozen_tensor_bundle(converted_phases, frozen_dir)
    bundle = phase_bundle_manifest(phase_digests)
    bundle["frozen_manifest"] = "frozen/manifest.json"
    bundle["weights"] = "frozen/weights.bin"
    _write_json(out_dir / "manifest.json", bundle)
