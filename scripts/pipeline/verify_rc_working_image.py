#!/usr/bin/env python3
"""Reconstruct a PT2E exported program solely from a checked RC image."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_packer_module() -> Any:
    path = Path(__file__).with_name("pack_rc_working_image.py")
    spec = importlib.util.spec_from_file_location("pack_rc_working_image", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack = _load_packer_module()


def _manifest_segments(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise ValueError("RC image manifest has no segment list")
    indexed: dict[str, Mapping[str, object]] = {}
    for segment in segments:
        if not isinstance(segment, Mapping):
            raise ValueError("RC image manifest segment must be an object")
        name = segment.get("name")
        if not isinstance(name, str) or name in indexed:
            raise ValueError("RC image manifest segment names must be unique")
        indexed[name] = segment
    return indexed


def reconstruct_state(
    exported: Any, manifest: Mapping[str, object], image_bytes: bytes
) -> dict[str, dict[str, Any]]:
    """Rebuild the state/constants mappings from image bytes and manifest only."""

    pack.verify_image_bytes(manifest, image_bytes)
    original_tensors = pack.exported_named_tensors(exported)
    segments = _manifest_segments(manifest)
    expected_names = set(original_tensors)
    missing = sorted(expected_names - set(segments))
    unexpected = sorted(set(segments) - expected_names)
    if missing:
        raise ValueError(f"RC image is missing exported state item(s): {', '.join(missing)}")
    if unexpected:
        raise ValueError(f"RC image has unexpected tensor item(s): {', '.join(unexpected)}")

    import torch

    reconstructed: dict[str, dict[str, Any]] = {"state_dict": {}, "constants": {}}
    for qualified_name in sorted(expected_names):
        original = original_tensors[qualified_name]
        segment = segments[qualified_name]
        category, source_name = qualified_name.split("/", 1)
        dtype, shape, _ = pack._tensor_bytes(original)
        if segment.get("dtype") != dtype or segment.get("shape") != shape:
            raise ValueError(f"RC image metadata does not match exported tensor {qualified_name}")
        offset = segment.get("offset")
        byte_length = segment.get("byte_length")
        if not isinstance(offset, int) or not isinstance(byte_length, int):
            raise ValueError(f"RC image segment {qualified_name} has invalid byte bounds")
        raw = image_bytes[offset : offset + byte_length]
        tensor = torch.frombuffer(bytearray(raw), dtype=original.dtype)
        tensor = tensor.reshape(tuple(shape)).clone()
        if isinstance(original, torch.nn.Parameter):
            tensor = torch.nn.Parameter(tensor, requires_grad=original.requires_grad)
        destination = "state_dict" if category == "state" else "constants"
        reconstructed[destination][source_name] = tensor
    return reconstructed


def rebuild_exported_program(exported: Any, reconstructed: Mapping[str, Mapping[str, Any]]) -> Any:
    """Create a validated ExportedProgram backed only by reconstructed tensors."""

    import torch

    state_dict = reconstructed.get("state_dict")
    constants = reconstructed.get("constants")
    if not isinstance(state_dict, Mapping) or not isinstance(constants, Mapping):
        raise ValueError("reconstructed RC image state is incomplete")
    return torch.export.ExportedProgram(
        exported.graph_module,
        copy.deepcopy(exported.graph),
        copy.deepcopy(exported.graph_signature),
        dict(state_dict),
        exported.range_constraints,
        exported.module_call_graph,
        exported.example_inputs,
        dict(constants),
        verifiers=exported.verifiers,
    )


def compare_reference_results(
    reference: Mapping[str, object], observed: list[Mapping[str, object]]
) -> dict[str, object]:
    """Require an observed raw-code vector and token ID for every oracle case."""

    expected_results = reference.get("results")
    if not isinstance(expected_results, list):
        raise ValueError("reference has no result list")
    expected_by_case: dict[str, Mapping[str, object]] = {}
    for expected in expected_results:
        if not isinstance(expected, Mapping):
            raise ValueError("reference result must be an object")
        case_id = expected.get("case_id")
        if not isinstance(case_id, str) or case_id in expected_by_case:
            raise ValueError("reference result case IDs must be unique strings")
        expected_by_case[case_id] = expected

    observed_by_case: dict[str, Mapping[str, object]] = {}
    for result in observed:
        case_id = result.get("case_id")
        if not isinstance(case_id, str) or case_id in observed_by_case:
            raise ValueError("observed result case IDs must be unique strings")
        observed_by_case[case_id] = result

    case_reports: list[dict[str, object]] = []
    for case_id in sorted(set(expected_by_case) | set(observed_by_case)):
        expected = expected_by_case.get(case_id)
        actual = observed_by_case.get(case_id)
        if expected is None or actual is None:
            case_reports.append(
                {
                    "case_id": case_id,
                    "status": "mismatch",
                    "reason": "missing expected or observed case",
                }
            )
            continue
        codes_match = expected.get("output_codes_i8") == actual.get("output_codes_i8")
        token_match = expected.get("token_id") == actual.get("token_id")
        case_reports.append(
            {
                "case_id": case_id,
                "status": "pass" if codes_match and token_match else "mismatch",
                "expected_codes_i8": expected.get("output_codes_i8"),
                "observed_codes_i8": actual.get("output_codes_i8"),
                "expected_token_id": expected.get("token_id"),
                "observed_token_id": actual.get("token_id"),
            }
        )
    return {
        "schema_version": 1,
        "status": "pass" if all(report["status"] == "pass" for report in case_reports) else "mismatch",
        "cases": case_reports,
    }


def _output_tensor(output: Any) -> Any:
    import torch

    if isinstance(output, torch.Tensor):
        return output
    logits = getattr(output, "logits", None)
    if isinstance(logits, torch.Tensor):
        return logits
    raise ValueError("replayed RC did not return a tensor or .logits tensor")


def replay_reference(
    exported: Any,
    manifest: Mapping[str, object],
    image_bytes: bytes,
    reference: Mapping[str, object],
    corpus_path: Path,
) -> dict[str, object]:
    """Rebuild state from the image and compare every corpus output to PT2E."""

    from TinyStories.rc_working_contract import (
        canonical_result,
        load_corpus,
        tokenize,
        validate_output_tensor,
    )

    expected_export_sha = reference.get("exported_program_sha256")
    manifest_export_sha = manifest.get("exported_program_sha256")
    if (
        not isinstance(expected_export_sha, str)
        or not isinstance(manifest_export_sha, str)
        or expected_export_sha != manifest_export_sha
    ):
        raise ValueError("reference and image manifest do not identify the same export")
    qparams = reference.get("output_qparams")
    if not isinstance(qparams, Mapping):
        raise ValueError("reference has no output quantization parameters")
    scale = qparams.get("scale")
    zero_point = qparams.get("zero_point")
    if not isinstance(scale, (int, float)) or not isinstance(zero_point, int):
        raise ValueError("reference output quantization parameters are invalid")

    reconstructed = reconstruct_state(exported, manifest, image_bytes)
    replayed = rebuild_exported_program(exported, reconstructed)
    import torch

    observed: list[dict[str, object]] = []
    with torch.no_grad():
        for case in load_corpus(corpus_path):
            token_ids = tokenize(case["text"])
            tensor = _output_tensor(
                replayed.module()(torch.tensor([token_ids], dtype=torch.long))
            )
            if str(tensor.dtype) != "torch.int8":
                raise ValueError(f"replayed RC output must be int8, got {tensor.dtype}")
            validate_output_tensor(tensor)
            observed.append(
                canonical_result(
                    case_id=case["id"],
                    token_ids=token_ids,
                    output_codes_i8=[
                        int(value) for value in tensor[0, 7, :].detach().cpu().tolist()
                    ],
                    output_scale=float(scale),
                    output_zero_point=zero_point,
                )
            )

    comparison = compare_reference_results(reference, observed)
    return {
        "schema_version": 1,
        "status": comparison["status"],
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "state_tensor_count": len(reconstructed["state_dict"]),
        "constant_tensor_count": len(reconstructed["constants"]),
        "replayed_program_type": type(replayed).__name__,
        "cases": comparison["cases"],
    }


def _load_exported_program(exported_program_dir: Path) -> Any:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401

    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    return torch.export.load(exported_program_dir / "exported.pt2")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exported-program-dir", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    image_bytes = args.image.read_bytes()
    exported = _load_exported_program(args.exported_program_dir)
    if (args.reference is None) != (args.corpus is None):
        raise SystemExit("--reference and --corpus must be supplied together")
    if args.reference is None:
        reconstructed = reconstruct_state(exported, manifest, image_bytes)
        replayed = rebuild_exported_program(exported, reconstructed)
        result: dict[str, object] = {
            "schema_version": 1,
            "status": "reconstructed",
            "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "state_tensor_count": len(reconstructed["state_dict"]),
            "constant_tensor_count": len(reconstructed["constants"]),
            "replayed_program_type": type(replayed).__name__,
        }
    else:
        result = replay_reference(
            exported,
            manifest,
            image_bytes,
            json.loads(args.reference.read_text(encoding="utf-8")),
            args.corpus,
        )
    _write_json(args.out, result)
    if result["status"] not in {"pass", "reconstructed"}:
        raise SystemExit("RC image replay differs from the frozen PT2E reference")


if __name__ == "__main__":
    main()
