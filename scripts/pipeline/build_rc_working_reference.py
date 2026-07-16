#!/usr/bin/env python3
"""Build the frozen PT2E W8A8 numerical oracle for the TinyStories working RC."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.rc_working_contract import (  # noqa: E402
    RC_WORKING_PIPELINE_ALIAS,
    RC_WORKING_SOURCE_MODEL_KEY,
    canonical_result,
    load_corpus,
    tokenize,
    validate_output_qparams,
    validate_output_tensor,
)


def _single_output_node(exported: Any) -> Any:
    output_node = next(
        (node for node in exported.graph.nodes if getattr(node, "op", None) == "output"),
        None,
    )
    if output_node is None:
        raise ValueError("exported PT2E graph has no output node")
    if not getattr(output_node, "args", None):
        raise ValueError("exported PT2E output node has no result")
    returned = output_node.args[0]
    if not isinstance(returned, (tuple, list)) or len(returned) != 1:
        raise ValueError("working RC export must return one output tensor")
    return returned[0]


def _is_quantize_per_tensor(target: object) -> bool:
    return "quantized_decomposed.quantize_per_tensor.default" in str(target)


def extract_terminal_output_qparams(exported: Any) -> dict[str, float | int]:
    """Read output scale and zero point from the terminal PT2E quantize op."""

    quantized_output = _single_output_node(exported)
    if getattr(quantized_output, "op", None) != "call_function" or not _is_quantize_per_tensor(
        getattr(quantized_output, "target", None)
    ):
        raise ValueError("working RC output must be terminal quantize_per_tensor")
    args = getattr(quantized_output, "args", ())
    if len(args) < 3:
        raise ValueError("terminal quantize_per_tensor has no scale/zero point")
    scale, zero_point = args[1], args[2]
    if not isinstance(scale, (int, float)) or isinstance(scale, bool):
        raise ValueError("terminal output quantization scale must be scalar")
    if not isinstance(zero_point, int) or isinstance(zero_point, bool):
        raise ValueError("terminal output quantization zero point must be an integer")
    validate_output_qparams(float(scale), zero_point)
    return {"scale": float(scale), "zero_point": zero_point}


def _load_exported_program(exported_program_dir: Path) -> Any:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401

    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    return torch.export.load(exported_program_dir / "exported.pt2")


def _output_tensor(output: Any) -> Any:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("building an RC reference requires PyTorch") from error

    if isinstance(output, torch.Tensor):
        return output
    logits = getattr(output, "logits", None)
    if isinstance(logits, torch.Tensor):
        return logits
    raise ValueError("working RC module did not return a tensor or .logits tensor")


def _example_input_ids(exported: Any) -> list[list[int]]:
    example_inputs = getattr(exported, "example_inputs", ())
    args = example_inputs[0] if example_inputs and isinstance(example_inputs[0], tuple) else example_inputs
    if not isinstance(args, tuple) or len(args) != 1:
        raise ValueError("working RC export must carry one example token input")
    tensor = args[0]
    try:
        return [[int(value) for value in row] for row in tensor.detach().cpu().tolist()]
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("working RC example input is not an integer tensor") from error


def build_reference(
    exported_program_dir: Path,
    corpus_path: Path,
    source_model_key: str = RC_WORKING_SOURCE_MODEL_KEY,
    pipeline_alias: str = RC_WORKING_PIPELINE_ALIAS,
) -> dict[str, object]:
    """Execute every frozen prompt and return the canonical raw-int8 oracle."""

    if source_model_key != RC_WORKING_SOURCE_MODEL_KEY:
        raise ValueError("reference must use the exact structural-finalist source model")
    if pipeline_alias != RC_WORKING_PIPELINE_ALIAS:
        raise ValueError("reference must use the exact working-RC pipeline alias")

    import torch

    exported_path = exported_program_dir / "exported.pt2"
    manifest_path = exported_program_dir / "manifest.json"
    exported = _load_exported_program(exported_program_dir)
    output_qparams = extract_terminal_output_qparams(exported)
    corpus = load_corpus(corpus_path)
    module = exported.module()
    results: list[dict[str, object]] = []
    corpus_records: list[dict[str, object]] = []
    with torch.no_grad():
        for case in corpus:
            token_ids = tokenize(case["text"])
            tensor = _output_tensor(module(torch.tensor([token_ids], dtype=torch.long)))
            if str(tensor.dtype) != "torch.int8":
                raise ValueError(f"working RC output must be int8, got {tensor.dtype}")
            validate_output_tensor(tensor)
            codes = [int(value) for value in tensor[0, 7, :].detach().cpu().tolist()]
            results.append(
                canonical_result(
                    case_id=case["id"],
                    token_ids=token_ids,
                    output_codes_i8=codes,
                    output_scale=output_qparams["scale"],
                    output_zero_point=output_qparams["zero_point"],
                )
            )
            corpus_records.append(
                {"id": case["id"], "text": case["text"], "token_ids": token_ids}
            )

    manifest_bytes = manifest_path.read_bytes()
    return {
        "schema_version": 1,
        "source_model_key": source_model_key,
        "pipeline_alias": pipeline_alias,
        "exported_program_sha256": hashlib.sha256(exported_path.read_bytes()).hexdigest(),
        "export_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "export_manifest": json.loads(manifest_bytes),
        "calibration_input_ids": _example_input_ids(exported),
        "corpus": corpus_records,
        "output_qparams": output_qparams,
        "results": results,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exported-program-dir", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--source-model-key", default=RC_WORKING_SOURCE_MODEL_KEY
    )
    parser.add_argument("--pipeline-alias", default=RC_WORKING_PIPELINE_ALIAS)
    args = parser.parse_args()
    _write_json(
        args.out,
        build_reference(
            args.exported_program_dir,
            args.corpus,
            args.source_model_key,
            args.pipeline_alias,
        ),
    )


if __name__ == "__main__":
    main()
