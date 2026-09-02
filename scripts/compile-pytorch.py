#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
import time
from pathlib import Path

from torch_mlir.fx import export_and_import
import torch


FIXED_BACKEND_PIPELINE = (
    "builtin.module(llm2fpga-legalize-exact-serial-gemv,"
    "func.func(torch-match-quantized-custom-ops),"
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)


def load_custom_op_library(path: Path) -> None:
    """Execute a compiler-selected torch.library registration before PT2 load."""

    if not path.is_file():
        raise SystemExit(f"custom-op library is missing: {path}")
    spec = importlib.util.spec_from_file_location("_llm2fpga_custom_ops", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load custom-op library: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def legalize_exact_serial_gemv(
    raw_mlir: str, torch_mlir_opt: Path, pass_plugin: Path
) -> tuple[str, int]:
    """Legalize the raw custom boundary before Torch's fixed backend pipeline."""

    if not torch_mlir_opt.is_file():
        raise SystemExit(f"torch-mlir-opt is missing: {torch_mlir_opt}")
    if not pass_plugin.is_file():
        raise SystemExit(f"exact serial-GEMV pass plugin is missing: {pass_plugin}")

    with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-import-") as temporary:
        raw_path = Path(temporary) / "raw.mlir"
        legalized_path = Path(temporary) / "legalized.mlir"
        raw_path.write_text(raw_mlir, encoding="utf-8")
        start_ns = time.perf_counter_ns()
        completed = subprocess.run(
            [
                str(torch_mlir_opt),
                "--allow-unregistered-dialect",
                f"--load-pass-plugin={pass_plugin}",
                f"--pass-pipeline={FIXED_BACKEND_PIPELINE}",
                str(raw_path),
                "-o",
                str(legalized_path),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        elapsed_ns = time.perf_counter_ns() - start_ns
        if completed.returncode != 0:
            detail = completed.stderr or completed.stdout
            raise SystemExit(f"exact serial-GEMV legalization failed:\n{detail}")
        return legalized_path.read_text(encoding="utf-8"), elapsed_ns


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
    parser.add_argument("--torch-mlir-opt", type=Path)
    parser.add_argument("--pass-plugin", type=Path)
    parser.add_argument("--custom-op-library", type=Path)
    args = parser.parse_args()
    if (args.torch_mlir_opt is None) != (args.pass_plugin is None):
        parser.error("--torch-mlir-opt and --pass-plugin must be supplied together")
    if (args.pass_plugin is None) != (args.custom_op_library is None):
        parser.error(
            "--custom-op-library is required exactly when --pass-plugin is supplied"
        )

    exported_path = args.exported_program_dir / "exported.pt2"
    # Registers quantized_decomposed ops needed when loading PT2E exports.
    import torch.ao.quantization.quantize_pt2e  # noqa: F401

    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    if args.custom_op_library is not None:
        load_custom_op_library(args.custom_op_library)

    load_start_ns = time.perf_counter_ns()
    exported = torch.export.load(exported_path)
    load_elapsed_ns = time.perf_counter_ns() - load_start_ns

    import_start_ns = time.perf_counter_ns()
    import_output_type = "raw" if args.pass_plugin is not None else args.output_type
    module = export_and_import(exported, output_type=import_output_type)
    import_elapsed_ns = time.perf_counter_ns() - import_start_ns

    render_start_ns = time.perf_counter_ns()
    mlir_text = str(module)
    render_elapsed_ns = time.perf_counter_ns() - render_start_ns
    legalize_elapsed_ns = 0
    if args.pass_plugin is not None:
        mlir_text, legalize_elapsed_ns = legalize_exact_serial_gemv(
            mlir_text, args.torch_mlir_opt, args.pass_plugin
        )
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
                    "exact_serial_gemv_legalize_elapsed_ns": legalize_elapsed_ns,
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
