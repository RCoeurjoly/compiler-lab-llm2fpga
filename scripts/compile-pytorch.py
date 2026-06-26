#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from torch_mlir.fx import export_and_import
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a PyTorch model adapter into torch-mlir text."
    )
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--exported-program-dir", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model-path")
    parser.add_argument(
        "--output-type",
        choices=("raw", "torch"),
        default="torch",
        help="torch-mlir import stage to emit",
    )
    args = parser.parse_args()

    if args.exported_program_dir is not None:
        exported_path = args.exported_program_dir / "exported.pt2"
        # Registers quantized_decomposed ops needed when loading PT2E exports.
        import torch.ao.quantization.quantize_pt2e  # noqa: F401

        try:
            import transformers.modeling_outputs  # noqa: F401
        except ImportError:
            pass

        exported = torch.export.load(exported_path)
        module = export_and_import(exported, output_type=args.output_type)
        mlir_text = str(module)
        args.out.write_text(mlir_text, encoding="utf-8")
        print(mlir_text)
        return

    if args.adapter is None:
        raise SystemExit("--adapter is required unless --exported-program-dir is provided")

    adapter = load_adapter(args.adapter)

    build_mlir_module = getattr(adapter, "build_mlir_module", None)
    if build_mlir_module is not None:
        module_or_text = build_mlir_module(args.model_path, args.output_type)
        mlir_text = str(module_or_text)
        args.out.write_text(mlir_text, encoding="utf-8")
        print(mlir_text)
        return

    export_program = getattr(adapter, "export_program", None)
    if export_program is not None:
        exported = export_program(args.model_path)
    else:
        build_model = getattr(adapter, "build_model", None)
        example_inputs = getattr(adapter, "example_inputs", None)
        if build_model is None or example_inputs is None:
            raise SystemExit(
                f"{args.adapter} must define export_program(model_path) or "
                "build_model(model_path) plus example_inputs()"
            )

        model = build_model(args.model_path).eval()
        exported = torch.export.export(
            model,
            tuple(example_inputs()),
            strict=getattr(adapter, "EXPORT_STRICT", True),
        )
    module = export_and_import(exported, output_type=args.output_type)
    mlir_text = str(module)
    args.out.write_text(mlir_text, encoding="utf-8")
    print(mlir_text)


if __name__ == "__main__":
    main()
