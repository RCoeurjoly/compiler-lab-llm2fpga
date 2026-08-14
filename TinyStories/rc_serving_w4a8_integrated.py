"""One-call stateful W4A8 serving program and its exact observation helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import torch

from .rc_serving_contract import (
    NUM_LAYERS,
    PHASE_NAMES,
    PREFILL_LENGTH,
    VOCAB_SIZE,
    phase_by_name,
    load_trace,
    validate_token_ids,
)
from .rc_serving_source import native_call_kwargs
from .rc_serving_w4a8_cache_abi import (
    flatten_dynamic_cache,
    reconstruct_dynamic_cache,
)
from .rc_serving_w4a8_integrated_contract import IntegratedObservation
from .rc_serving_w4a8_integrated_contract import (
    build_readback_manifest,
    write_integrated_observation,
)
from .rc_serving_w4a8_export import convert_w4a8_program
from .rc_serving_evidence import enable_hf_dynamic_cache_export_support, tensor_record
from .rc_serving_w4a8_source import build_w4a8_source_model


_PHASES = tuple(phase_by_name(name) for name in PHASE_NAMES)
_TENSOR_CACHE_ABI_PATHS = (
    "['key_cache']/[0]",
    "['value_cache']/[0]",
    "['key_cache']/[1]",
    "['value_cache']/[1]",
)


def native_cache_records_in_tensor_abi_order(
    leaves: Sequence[Mapping[str, object]],
) -> list[object]:
    """Map native pytree K-all/V-all records to layer-local K/V ABI order."""

    by_path: dict[str, object] = {}
    for leaf in leaves:
        path = leaf.get("path")
        if not isinstance(path, str) or path not in _TENSOR_CACHE_ABI_PATHS:
            raise ValueError(f"unexpected native cache leaf path: {path!r}")
        if path in by_path:
            raise ValueError(f"duplicate native cache leaf path: {path}")
        if "tensor" not in leaf:
            raise ValueError(f"native cache leaf {path} has no tensor record")
        by_path[path] = leaf["tensor"]
    if set(by_path) != set(_TENSOR_CACHE_ABI_PATHS):
        raise ValueError("native cache record does not contain two K/V layers")
    return [by_path[path] for path in _TENSOR_CACHE_ABI_PATHS]


class IntegratedW4A8Module(torch.nn.Module):
    """Run prefill and two cached greedy decode steps in one forward call."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def _phase(
        self,
        input_ids: torch.Tensor,
        phase_index: int,
        cache_leaves: tuple[torch.Tensor, ...],
    ) -> tuple[torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...]]:
        phase = _PHASES[phase_index]
        cache = (
            None
            if phase_index == 0
            else reconstruct_dynamic_cache(cache_leaves, expected_layers=NUM_LAYERS)
        )
        output = self.model(input_ids, **native_call_kwargs(phase, cache))
        if not isinstance(output, tuple) or len(output) < 2:
            raise RuntimeError("integrated source model did not return logits and cache")
        logits, returned_cache = output[0], output[1]
        if not isinstance(logits, torch.Tensor):
            raise RuntimeError("integrated source logits are not a tensor")
        expected_shape = (1, phase.input_length, VOCAB_SIZE)
        if tuple(logits.shape) != expected_shape:
            raise RuntimeError(
                f"{phase.name} returned logits shape {tuple(logits.shape)}, "
                f"expected {expected_shape}"
            )
        last_logits = logits[:, -1, :]
        token = torch.argmax(last_logits, dim=-1, keepdim=True)
        leaves = flatten_dynamic_cache(returned_cache, expected_layers=NUM_LAYERS)
        return token, last_logits, leaves

    def forward(self, prompt: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if tuple(prompt.shape) != (1, PREFILL_LENGTH):
            raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")

        token_8, logits_8, cache_8 = self._phase(prompt, 0, ())
        token_9, logits_9, cache_9 = self._phase(token_8, 1, cache_8)
        token_10, logits_10, cache_10 = self._phase(token_9, 2, cache_9)
        return (
            token_8,
            token_9,
            token_10,
            logits_8,
            *cache_8,
            logits_9,
            *cache_9,
            logits_10,
            *cache_10,
        )


def convert_integrated_w4a8_program(
    module: torch.nn.Module, prompt: torch.Tensor
) -> torch.export.ExportedProgram:
    """PT2E-convert and export the complete one-call serving module once."""

    if tuple(prompt.shape) != (1, PREFILL_LENGTH):
        raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")
    converted = convert_w4a8_program(module, (prompt,))
    output = converted.module()(prompt)
    if not isinstance(output, tuple) or len(output) != 18:
        raise RuntimeError("integrated exported program must return 18 tensors")
    return converted


def run_integrated_eager(
    module: IntegratedW4A8Module, prompt: torch.Tensor
) -> IntegratedObservation:
    if tuple(prompt.shape) != (1, PREFILL_LENGTH):
        raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")
    with torch.no_grad():
        flat = module(prompt)
    return integrated_observation_from_outputs(prompt, flat)


def integrated_observation_from_outputs(
    prompt: torch.Tensor, flat: Sequence[torch.Tensor]
) -> IntegratedObservation:
    """Convert the public 18-tensor output ABI into its durable observation."""

    if tuple(prompt.shape) != (1, PREFILL_LENGTH):
        raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")
    prompt_ids = validate_token_ids(
        tuple(int(value) for value in prompt.reshape(-1).tolist()), PREFILL_LENGTH
    )
    if len(flat) != 18:
        raise RuntimeError("integrated module must return exactly 18 tensors")

    tokens = tuple(int(value.item()) for value in flat[:3])
    logits: list[tuple[int | float, ...]] = []
    phase_caches: list[tuple[torch.Tensor, ...]] = []
    for offset in (3, 8, 13):
        phase_logits = flat[offset].detach().cpu().contiguous().reshape(-1)
        if phase_logits.numel() != VOCAB_SIZE:
            raise RuntimeError("integrated phase logits do not match vocabulary size")
        logits.append(tuple(phase_logits.tolist()))
        phase_caches.append(
            tuple(
                tensor.detach().cpu().contiguous().clone()
                for tensor in flat[offset + 1 : offset + 5]
            )
        )
    return IntegratedObservation(
        prompt_token_ids=prompt_ids,
        phase_tokens=tokens,
        phase_logits=(logits[0], logits[1], logits[2]),
        phase_cache_leaves=tuple(phase_caches),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quantized_nodes(exported: torch.export.ExportedProgram) -> list[torch.fx.Node]:
    return [
        node
        for node in exported.graph.nodes
        if "quantized_decomposed" in str(node.target)
    ]


def _qparam_signature(node: torch.fx.Node) -> tuple[str, tuple[str, ...]]:
    return str(node.target), tuple(str(value) for value in node.args[1:6])


def assert_frozen_phase_qparams_equal(
    integrated: torch.export.ExportedProgram,
    phase_programs: Sequence[torch.export.ExportedProgram],
) -> int:
    if len(phase_programs) != len(PHASE_NAMES):
        raise ValueError("qparam comparison requires three phase programs")
    integrated_nodes = _quantized_nodes(integrated)
    phase_nodes = [_quantized_nodes(program) for program in phase_programs]
    if any(len(nodes) != 163 for nodes in phase_nodes):
        raise AssertionError("frozen phase programs must each contain 163 q/dq nodes")
    if len(integrated_nodes) != sum(len(nodes) for nodes in phase_nodes):
        raise AssertionError("integrated program does not contain 489 q/dq nodes")

    integrated_shared = [
        node for node in integrated_nodes if not node.meta.get("stack_trace")
    ]
    offset = 0
    for phase_index, nodes in enumerate(phase_nodes):
        reference_shared = [node for node in nodes if not node.meta.get("stack_trace")]
        candidate = integrated_shared[offset : offset + len(reference_shared)]
        if list(map(_qparam_signature, candidate)) != list(
            map(_qparam_signature, reference_shared)
        ):
            raise AssertionError(f"{PHASE_NAMES[phase_index]} shared qparams differ")
        offset += len(reference_shared)
    if offset != len(integrated_shared):
        raise AssertionError("integrated shared qparam partition is incomplete")

    markers = (
        "token_8, logits_8",
        "token_9, logits_9",
        "token_10, logits_10",
    )
    for phase_index, (nodes, marker) in enumerate(zip(phase_nodes, markers)):
        reference_call = [node for node in nodes if node.meta.get("stack_trace")]
        integrated_call = [
            node
            for node in integrated_nodes
            if marker in str(node.meta.get("stack_trace", ""))
        ]
        if list(map(_qparam_signature, integrated_call)) != list(
            map(_qparam_signature, reference_call)
        ):
            raise AssertionError(f"{PHASE_NAMES[phase_index]} call-site qparams differ")
    return len(integrated_nodes)


def _outputs_equal(
    expected: Sequence[torch.Tensor], actual: Sequence[torch.Tensor]
) -> bool:
    return len(expected) == len(actual) and all(
        torch.equal(before, after) for before, after in zip(expected, actual)
    )


def materialize_integrated_bundle(
    model_path: Path,
    trace_path: Path,
    phase_oracle: Path,
    out_dir: Path,
) -> None:
    if out_dir.exists():
        raise FileExistsError(f"integrated output directory already exists: {out_dir}")
    enable_hf_dynamic_cache_export_support()
    trace = load_trace(trace_path)
    prompt = torch.tensor([trace.prompt_token_ids], dtype=torch.long)
    module = IntegratedW4A8Module(build_w4a8_source_model(model_path))
    converted = convert_integrated_w4a8_program(module, prompt)
    with torch.no_grad():
        converted_outputs = converted.module()(prompt)
    observation = integrated_observation_from_outputs(prompt, converted_outputs)

    phase_programs = []
    for phase in PHASE_NAMES:
        exported_path = phase_oracle / phase / "exported.pt2"
        if not exported_path.is_file():
            raise FileNotFoundError(f"missing frozen phase program: {exported_path}")
        phase_programs.append(torch.export.load(exported_path))
    qdq_count = assert_frozen_phase_qparams_equal(converted, phase_programs)

    prefill_reference = json.loads(
        (phase_oracle / "prefill-8" / "reference.json").read_text(encoding="utf-8")
    )
    prefill_equal = (
        tensor_record(converted_outputs[3].reshape(-1))
        == prefill_reference["last_logits"]
        and [tensor_record(converted_outputs[4 + index]) for index in range(4)]
        == prefill_reference["cache_leaves"]
    )
    if not prefill_equal:
        raise AssertionError("integrated W4A8 prefill differs from frozen phase oracle")

    phase_shapes = {
        phase: {
            "token": [],
            "logits": [VOCAB_SIZE],
            "cache": [list(tensor.shape) for tensor in observation.phase_cache_leaves[index]],
        }
        for index, phase in enumerate(PHASE_NAMES)
    }
    manifest = build_readback_manifest(phase_shapes)

    out_dir.mkdir(parents=True)
    exported_path = out_dir / "exported.pt2"
    torch.export.save(converted, exported_path)
    reloaded = torch.export.load(exported_path)
    with torch.no_grad():
        reloaded_outputs = reloaded.module()(prompt)
    save_reload_equal = _outputs_equal(converted_outputs, reloaded_outputs)
    if not save_reload_equal:
        raise AssertionError("saved integrated program changed its outputs")

    graph_text = str(converted.graph) + "\n"
    (out_dir / "graph.txt").write_text(graph_text, encoding="utf-8")
    (out_dir / "readback-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    observation_path = out_dir / "observation.json"
    write_integrated_observation(observation_path, observation, manifest)
    receipt = {
        "schema": "rc-serving-w4a8-integrated-export-receipt-v1",
        "artifact_kind": "single-integrated-w4a8-exported-program",
        "exported_program_count": 1,
        "output_tensor_count": len(converted_outputs),
        "quantized_decomposed_node_count": qdq_count,
        "frozen_phase_qparams_equal": True,
        "frozen_prefill_equal": prefill_equal,
        "phase_decode_oracle_status": "superseded-by-w4a8-cache-chained-observation",
        "save_reload_equal": save_reload_equal,
        "model_path": str(model_path),
        "phase_oracle_path": str(phase_oracle),
        "trace_sha256": _sha256(trace_path),
        "exported_program_sha256": _sha256(exported_path),
        "graph_sha256": hashlib.sha256(graph_text.encode()).hexdigest(),
        "observation_sha256": _sha256(observation_path),
        "torch_version": torch.__version__,
    }
    (out_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _first_sequence_mismatch(expected: Sequence[object], actual: Sequence[object]) -> int:
    if len(expected) != len(actual):
        return min(len(expected), len(actual))
    return next(
        (index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
        -1,
    )


def assert_integrated_observation_equal(
    expected: IntegratedObservation, actual: IntegratedObservation
) -> None:
    if tuple(expected.prompt_token_ids) != tuple(actual.prompt_token_ids):
        raise AssertionError("integrated prompt token IDs differ")
    if expected.phase_tokens != actual.phase_tokens:
        index = _first_sequence_mismatch(expected.phase_tokens, actual.phase_tokens)
        phase = PHASE_NAMES[index] if index < len(PHASE_NAMES) else "length"
        raise AssertionError(f"{phase} selected token differs")

    for phase_index, phase in enumerate(PHASE_NAMES):
        expected_logits = expected.phase_logits[phase_index]
        actual_logits = actual.phase_logits[phase_index]
        mismatch = _first_sequence_mismatch(expected_logits, actual_logits)
        if mismatch != -1:
            raise AssertionError(f"{phase} logits differ at flat index {mismatch}")

        expected_leaves = expected.phase_cache_leaves[phase_index]
        actual_leaves = actual.phase_cache_leaves[phase_index]
        if len(expected_leaves) != len(actual_leaves):
            raise AssertionError(f"{phase} cache leaf count differs")
        for leaf_index, (expected_tensor, actual_tensor) in enumerate(
            zip(expected_leaves, actual_leaves)
        ):
            if tuple(expected_tensor.shape) != tuple(actual_tensor.shape):
                raise AssertionError(f"{phase} cache leaf {leaf_index} shape differs")
            equal = torch.eq(expected_tensor, actual_tensor).reshape(-1)
            if not bool(torch.all(equal)):
                mismatch = int(torch.nonzero(~equal, as_tuple=False)[0].item())
                raise AssertionError(
                    f"{phase} cache leaf {leaf_index} differs at flat index {mismatch}"
                )
