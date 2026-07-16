#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
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
        "--timing-json",
        type=Path,
        help="optional JSON output for export loading, Torch-MLIR import, and rendering times",
    )
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

    load_start_ns = time.perf_counter_ns()
    exported = torch.export.load(exported_path)
    load_elapsed_ns = time.perf_counter_ns() - load_start_ns

    import_start_ns = time.perf_counter_ns()
    module = export_and_import(exported, output_type=args.output_type)
    import_elapsed_ns = time.perf_counter_ns() - import_start_ns

    render_start_ns = time.perf_counter_ns()
    mlir_text = str(module)
    render_elapsed_ns = time.perf_counter_ns() - render_start_ns
    args.out.write_text(mlir_text, encoding="utf-8")
    if args.timing_json is not None:
        args.timing_json.parent.mkdir(parents=True, exist_ok=True)
        args.timing_json.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "torch_export_load_elapsed_ns": load_elapsed_ns,
                    "torch_mlir_import_elapsed_ns": import_elapsed_ns,
                    "mlir_text_render_elapsed_ns": render_elapsed_ns,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print(mlir_text)


if __name__ == "__main__":
    main()
