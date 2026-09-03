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
COMPOSED_RECEIPT = ROOT / "artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-sv-receipt.json"


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
    mode.add_argument("--composed", action="store_true", help="observe composed GEMV and requantization outputs")
    parser.add_argument("--yosys-stat", action="store_true", help="run Yosys stat on generated SystemVerilog")
    args = parser.parse_args()
    lowerer = _lowerer()
    if args.composed:
        if args.row is not None or args.output is not None:
            parser.error("--composed does not accept --row or --output")
        result = lowerer.run_composed_slice_sv(args.schema, args.fixture)
        COMPOSED_RECEIPT.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written = json.loads(COMPOSED_RECEIPT.read_text(encoding="utf-8"))
        unsigned = {
            key: value for key, value in written.items() if key != "receipt_sha256"
        }
        if written != result or written.get("receipt_sha256") != lowerer._canonical_sha256(unsigned):
            raise RuntimeError("written composed generated-SV receipt failed self-verification")
        if args.yosys_stat:
            sv_path = result["generated_artifacts"]["synthesis_sv"]["path"]
            yosys = subprocess.run(
                ["yosys", "-p", f"read_verilog -sv {sv_path}; hierarchy -top main; stat"],
                text=True,
                capture_output=True,
                check=False,
                timeout=600,
            )
            if yosys.returncode != 0:
                raise RuntimeError(f"Yosys stat failed: {yosys.stderr.strip()}")
    elif args.requantize:
        if args.row is not None or args.output is not None:
            parser.error("--requantize does not accept --row or --output")
        if args.yosys_stat:
            parser.error("--yosys-stat is supported only with --full-gemv or --composed")
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
            parser.error("--row and --output are required unless a whole-slice mode is used")
        if args.yosys_stat:
            parser.error("--yosys-stat is supported only with --full-gemv or --composed")
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
