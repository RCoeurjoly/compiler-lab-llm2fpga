"""Direct torch.export support for the native stateful-serving trace."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

import torch

from .rc_serving_contract import SERVING_RC_MODEL_KEY, ServingPhase
from .rc_serving_evidence import (
    NativeCacheSnapshot,
    enable_hf_dynamic_cache_export_support,
    snapshot_native_cache,
    tensor_record,
)
from .rc_serving_source import (
    PhaseInvocation,
    build_source_model,
    fresh_phase_invocation,
    native_call_kwargs,
)


PHASE_NAMES = ("prefill-8", "decode-8", "decode-9")


def export_direct_phase(
    model: torch.nn.Module, invocation: PhaseInvocation
) -> torch.export.ExportedProgram:
    enable_hf_dynamic_cache_export_support()
    return torch.export.export(
        model,
        (invocation.input_ids,),
        kwargs=native_call_kwargs(
            invocation.phase, invocation.past_key_values
        ),
        strict=False,
    )


def _run_exported(
    exported: torch.export.ExportedProgram, invocation: PhaseInvocation
) -> tuple[torch.Tensor, object]:
    with torch.no_grad():
        output = exported.module()(
            invocation.input_ids,
            **native_call_kwargs(
                invocation.phase, invocation.past_key_values
            ),
        )
    if not isinstance(output, tuple) or len(output) < 2:
        raise RuntimeError("exported phase did not return logits and native cache")
    if not isinstance(output[0], torch.Tensor):
        raise RuntimeError("exported phase logits are not a tensor")
    return output[0], output[1]


def _phase_record(
    phase: ServingPhase,
    input_ids: torch.Tensor,
    logits: torch.Tensor,
    cache: NativeCacheSnapshot,
) -> dict[str, object]:
    last_logits = logits[0, -1, :].detach().cpu().contiguous()
    return {
        "name": phase.name,
        "input_token_ids": [int(value) for value in input_ids[0].tolist()],
        "cache_length_before": phase.cache_length_before,
        "cache_length_after": phase.cache_length_after,
        "cache_position": list(phase.cache_positions),
        "last_logits": tensor_record(last_logits),
        "greedy_token_id": int(
            max(
                range(last_logits.numel()),
                key=lambda index: (float(last_logits[index]), -index),
            )
        ),
        "cache_snapshot": cache.record(),
    }


def _require_equal(expected: object, actual: object, path: str) -> None:
    if expected != actual:
        raise ValueError(f"direct export mismatch at {path}")


def compare_eager_and_exported_phase(
    model: torch.nn.Module,
    exported: torch.export.ExportedProgram,
    invocation: PhaseInvocation,
    reference_phase: Mapping[str, object] | None = None,
) -> dict[str, object]:
    eager_invocation = fresh_phase_invocation(
        model, invocation.trace, invocation.phase.name
    )
    eager_logits, eager_cache = model(
        eager_invocation.input_ids,
        **native_call_kwargs(
            eager_invocation.phase, eager_invocation.past_key_values
        ),
    )
    if not isinstance(eager_logits, torch.Tensor):
        raise RuntimeError("eager phase logits are not a tensor")
    eager_snapshot = snapshot_native_cache(eager_cache)
    eager_record = _phase_record(
        eager_invocation.phase,
        eager_invocation.input_ids,
        eager_logits,
        eager_snapshot,
    )
    if reference_phase is not None:
        _require_equal(reference_phase, eager_record, "native-reference")

    exported_invocation = fresh_phase_invocation(
        model, invocation.trace, invocation.phase.name
    )
    exported_logits, exported_cache = _run_exported(
        exported, exported_invocation
    )
    if type(exported_cache) is not type(eager_cache):
        raise ValueError("direct export changed the native cache type")
    exported_snapshot = snapshot_native_cache(exported_cache)
    exported_record = _phase_record(
        exported_invocation.phase,
        exported_invocation.input_ids,
        exported_logits,
        exported_snapshot,
    )
    _require_equal(eager_record["last_logits"], exported_record["last_logits"], "logits")
    _require_equal(
        eager_record["greedy_token_id"],
        exported_record["greedy_token_id"],
        "greedy-token",
    )
    _require_equal(
        eager_record["cache_snapshot"],
        exported_record["cache_snapshot"],
        "cache",
    )
    _require_equal(
        eager_snapshot.schema,
        exported_snapshot.schema,
        "cache-schema",
    )
    return {
        "status": "pass",
        "phase": invocation.phase.name,
        "eager": eager_record,
        "exported": exported_record,
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_manifest(
    out_dir: Path, phase_digests: Mapping[str, str]
) -> dict[str, object]:
    if tuple(phase_digests) != PHASE_NAMES:
        raise ValueError("direct export bundle phases are not in fixed order")
    return {
        "schema_version": 1,
        "artifact_kind": "direct-native-cache-export-bundle",
        "model_key": SERVING_RC_MODEL_KEY,
        "numeric_format": "native-fp32-source",
        "quantization_status": "unproven",
        "phases": [
            {
                "name": name,
                "path": name,
                "exported_program_sha256": phase_digests[name],
            }
            for name in PHASE_NAMES
        ],
    }


def materialize_direct_export_bundle(
    model_path: Path,
    trace_path: Path,
    reference_path: Path,
    out_dir: Path,
) -> None:
    from .rc_serving_contract import load_trace

    trace = load_trace(trace_path)
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if reference.get("model_key") != SERVING_RC_MODEL_KEY:
        raise ValueError("native reference model key does not match")
    reference_phases = {
        phase["name"]: phase for phase in reference.get("phases", [])
    }
    if tuple(reference_phases) != PHASE_NAMES:
        raise ValueError("native reference does not contain all serving phases")

    out_dir.mkdir(parents=True, exist_ok=True)
    model = build_source_model(model_path)
    source_files = (
        "rc_serving_contract.py",
        "rc_serving_source.py",
        "rc_serving_evidence.py",
        "rc_serving_direct_export.py",
    )
    source_dir = out_dir / "source"
    source_dir.mkdir()
    source_root = Path(__file__).resolve().parents[1] / "TinyStories"
    for filename in source_files:
        (source_dir / filename).write_bytes(
            (source_root / filename).read_bytes()
        )

    phase_digests: dict[str, str] = {}
    for phase_name in PHASE_NAMES:
        invocation = fresh_phase_invocation(model, trace, phase_name)
        exported = export_direct_phase(model, invocation)
        phase_dir = out_dir / phase_name
        phase_dir.mkdir()
        torch.export.save(exported, phase_dir / "exported.pt2")
        (phase_dir / "exported-program.txt").write_text(
            str(exported) + "\n", encoding="utf-8"
        )
        (phase_dir / "graph.txt").write_text(
            str(exported.graph) + "\n", encoding="utf-8"
        )
        (phase_dir / "graph-module.py").write_text(
            exported.graph_module.code + "\n", encoding="utf-8"
        )
        (phase_dir / "graph-signature.txt").write_text(
            str(exported.graph_signature) + "\n", encoding="utf-8"
        )
        conformance = compare_eager_and_exported_phase(
            model, exported, invocation, reference_phases[phase_name]
        )
        (phase_dir / "conformance.json").write_text(
            json.dumps(conformance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (phase_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "artifact_kind": "direct-native-cache-export-phase",
                    "model_key": SERVING_RC_MODEL_KEY,
                    "phase": phase_name,
                    "numeric_format": "native-fp32-source",
                    "quantization_status": "unproven",
                    "serialized_exported_program": "exported.pt2",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        phase_digests[phase_name] = sha256_file(phase_dir / "exported.pt2")

    (out_dir / "reference.json").write_bytes(reference_path.read_bytes())
    (out_dir / "native-cache-schema.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "model_key": SERVING_RC_MODEL_KEY,
                "native_cache_schema": reference["native_cache_schema"],
                "cache_sequence_axis": reference["cache_sequence_axis"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(bundle_manifest(out_dir, phase_digests), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
