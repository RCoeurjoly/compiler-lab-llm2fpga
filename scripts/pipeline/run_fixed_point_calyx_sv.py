#!/usr/bin/env python3
"""Generate and observe the Task-1 exact fixed-point Calyx SV kernel."""
from __future__ import annotations

import argparse
import importlib.util
import json
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
    parser.add_argument("--row", required=True, type=int)
    parser.add_argument("--output", required=True, type=int)
    args = parser.parse_args()
    lowerer = _lowerer()
    artifact = lowerer.generate_one_output_kernel(args.schema, args.fixture)
    observed = lowerer.run_generated_sv(artifact, args.fixture, args.row, args.output)
    print(
        json.dumps(
            {
                "schema": "llm2fpga-fixed-point-calyx-generated-sv-observation-v1",
                "row": args.row,
                "output": args.output,
                **observed,
                "generated_artifacts": artifact.provenance["generated_sv_artifacts"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
