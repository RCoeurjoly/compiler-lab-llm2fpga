#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from torch_mlir.fx import export_and_import
import torch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a serialized PyTorch ExportedProgram into torch-mlir text."
    )
    parser.add_argument("--exported-program-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--output-type",
        choices=("raw", "torch"),
        default="torch",
        help="torch-mlir import stage to emit",
    )
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
