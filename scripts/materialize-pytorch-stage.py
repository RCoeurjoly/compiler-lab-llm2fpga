#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType

import torch


def load_adapter(path: Path) -> ModuleType:
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load adapter module from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(path.parent))
        except ValueError:
            pass
    return module


def tensor_summary(value: object) -> dict[str, object]:
    if not isinstance(value, torch.Tensor):
        return {"type": type(value).__name__, "repr": repr(value)}
    return {
        "type": "torch.Tensor",
        "dtype": str(value.dtype),
        "shape": list(value.shape),
        "requires_grad": value.requires_grad,
    }


def relevant_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith("TINYSTORIES_")
    }


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_common_files(out_dir: Path, adapter_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(adapter_path, out_dir / "adapter.py")


def adapter_exported_program(
    adapter: ModuleType, model_path: str | None
) -> tuple[torch.export.ExportedProgram, str, object]:
    export_program = getattr(adapter, "export_program", None)
    build_model = getattr(adapter, "build_model", None)
    example_inputs = getattr(adapter, "example_inputs", None)

    if export_program is not None:
        exported = export_program(model_path)
        return exported, "adapter.export_program", getattr(exported, "example_inputs", None)

    if build_model is None or example_inputs is None:
        raise SystemExit(
            "adapter must define export_program(model_path) or "
            "build_model(model_path) plus example_inputs()"
        )

    model = build_model(model_path).eval()
    inputs = tuple(example_inputs())
    exported = torch.export.export(
        model,
        inputs,
        strict=getattr(adapter, "EXPORT_STRICT", True),
    )
    return exported, "torch.export.export(build_model(...), example_inputs())", inputs


def flattened_input_summaries(inputs: object) -> list[dict[str, object]]:
    if not isinstance(inputs, tuple):
        return []
    args_tuple = inputs[0] if inputs and isinstance(inputs[0], tuple) else inputs
    return [tensor_summary(value) for value in args_tuple]


def materialize_model(args: argparse.Namespace, adapter: ModuleType) -> None:
    build_model = getattr(adapter, "build_model", None)
    example_inputs = getattr(adapter, "example_inputs", None)
    if build_model is None:
        raise SystemExit("model stage requires adapter.build_model(model_path)")

    model = build_model(args.model_path).eval()
    inputs = tuple(example_inputs()) if example_inputs is not None else ()
    (args.out_dir / "model-repr.txt").write_text(repr(model) + "\n", encoding="utf-8")
    write_json(
        args.out_dir / "manifest.json",
        {
            "stage": "pytorch-model",
            "adapter": str(args.adapter),
            "adapter_copy": "adapter.py",
            "model_path": args.model_path,
            "model_type": type(model).__name__,
            "example_inputs": flattened_input_summaries(inputs),
            "environment": relevant_environment(),
            "files": {"model_repr": "model-repr.txt"},
        },
    )


def materialize_quantized(args: argparse.Namespace, adapter: ModuleType) -> None:
    export_program = getattr(adapter, "export_program", None)
    if export_program is None:
        write_json(
            args.out_dir / "manifest.json",
            {
                "stage": "pytorch-quantized",
                "status": "unavailable",
                "reason": "adapter has no quantized export_program stage",
                "adapter": str(args.adapter),
                "adapter_copy": "adapter.py",
                "model_path": args.model_path,
                "environment": relevant_environment(),
            },
        )
        return

    quantized_graph = args.out_dir / "quantized-graph.txt"
    os.environ.setdefault("TINYSTORIES_DUMP_PT2E_QUANTIZED_GRAPH", str(quantized_graph))
    exported = export_program(args.model_path)
    (args.out_dir / "post-quant-exported-graph.txt").write_text(
        str(exported.graph) + "\n", encoding="utf-8"
    )
    write_json(
        args.out_dir / "manifest.json",
        {
            "stage": "pytorch-quantized",
            "adapter": str(args.adapter),
            "adapter_copy": "adapter.py",
            "model_path": args.model_path,
            "status": "materialized",
            "environment": relevant_environment(),
            "files": {
                "quantized_graph": "quantized-graph.txt",
                "post_quant_exported_graph": "post-quant-exported-graph.txt",
            },
        },
    )


def materialize_exported(args: argparse.Namespace, adapter: ModuleType) -> None:
    exported, export_source, inputs = adapter_exported_program(adapter, args.model_path)
    torch.export.save(exported, args.out_dir / "exported.pt2")
    (args.out_dir / "exported-program.txt").write_text(
        str(exported) + "\n", encoding="utf-8"
    )
    (args.out_dir / "graph.txt").write_text(str(exported.graph) + "\n", encoding="utf-8")
    (args.out_dir / "graph-module.py").write_text(
        exported.graph_module.code + "\n", encoding="utf-8"
    )
    (args.out_dir / "graph-signature.txt").write_text(
        str(exported.graph_signature) + "\n", encoding="utf-8"
    )
    write_json(
        args.out_dir / "manifest.json",
        {
            "stage": "pytorch-exported",
            "adapter": str(args.adapter),
            "adapter_copy": "adapter.py",
            "model_path": args.model_path,
            "export_source": export_source,
            "exported_program_type": type(exported).__name__,
            "example_inputs": flattened_input_summaries(inputs),
            "environment": relevant_environment(),
            "files": {
                "serialized_exported_program": "exported.pt2",
                "exported_program": "exported-program.txt",
                "graph": "graph.txt",
                "graph_module": "graph-module.py",
                "graph_signature": "graph-signature.txt",
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize PyTorch pipeline stages.")
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--model-path")
    parser.add_argument(
        "--stage",
        required=True,
        choices=("model", "quantized", "exported"),
    )
    args = parser.parse_args()

    write_common_files(args.out_dir, args.adapter)
    adapter = load_adapter(args.adapter)

    if args.stage == "model":
        materialize_model(args, adapter)
    elif args.stage == "quantized":
        materialize_quantized(args, adapter)
    else:
        materialize_exported(args, adapter)


if __name__ == "__main__":
    main()
