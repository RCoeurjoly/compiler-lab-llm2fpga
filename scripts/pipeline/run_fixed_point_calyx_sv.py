#!/usr/bin/env python3
"""Generate and observe exact fixed-point Calyx SV backend gates."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_schema_to_calyx.py"


def _lowerer():
    spec = importlib.util.spec_from_file_location("fixed_point_schema_calyx", LOWERER)
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed-point Calyx lowerer is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--row", type=int)
    parser.add_argument("--output", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full-gemv", action="store_true", help="observe all 4x64 accumulator checkpoints")
    mode.add_argument("--requantize", action="store_true", help="observe all standalone requantization outputs")
    parser.add_argument("--yosys-stat", action="store_true", help="run Yosys stat on generated SystemVerilog")
    args = parser.parse_args()
    lowerer = _lowerer()
    if args.requantize:
        if args.row is not None or args.output is not None:
            parser.error("--requantize does not accept --row or --output")
        if args.yosys_stat:
            parser.error("--yosys-stat is supported only with --full-gemv")
        artifact = lowerer.generate_requantize_kernel(args.schema, args.fixture)
        observed = lowerer.run_requantize_sv(artifact, args.fixture)
        result = {
            "schema": "llm2fpga-fixed-point-calyx-requantize-generated-sv-observation-v1",
            **observed,
            "generated_artifacts": artifact.provenance["generated_sv_artifacts"],
        }
    elif args.full_gemv:
        if args.row is not None or args.output is not None:
            parser.error("--full-gemv does not accept --row or --output")
        artifact = lowerer.generate_full_gemv_kernel(args.schema, args.fixture)
        observed = lowerer.run_full_gemv_sv(artifact, args.fixture)
        result = {
            "schema": "llm2fpga-fixed-point-calyx-full-gemv-generated-sv-observation-v1",
            **observed,
            "generated_artifacts": artifact.provenance["generated_sv_artifacts"],
        }
        if args.yosys_stat:
            sv_path = artifact.provenance["generated_sv_artifacts"]["synthesis_sv"]
            yosys = subprocess.run(
                ["yosys", "-p", f"read_verilog -sv {sv_path}; hierarchy -top main; stat"],
                text=True,
                capture_output=True,
                check=False,
                timeout=600,
            )
            if yosys.returncode != 0:
                raise RuntimeError(f"Yosys stat failed: {yosys.stderr.strip()}")
            result["yosys_stat"] = yosys.stdout
    else:
        if args.row is None or args.output is None:
            parser.error("--row and --output are required unless --full-gemv is used")
        if args.yosys_stat:
            parser.error("--yosys-stat is supported only with --full-gemv")
        artifact = lowerer.generate_one_output_kernel(args.schema, args.fixture)
        observed = lowerer.run_generated_sv(artifact, args.fixture, args.row, args.output)
        result = {
            "schema": "llm2fpga-fixed-point-calyx-generated-sv-observation-v1",
            "row": args.row,
            "output": args.output,
            **observed,
            "generated_artifacts": artifact.provenance["generated_sv_artifacts"],
        }
    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
