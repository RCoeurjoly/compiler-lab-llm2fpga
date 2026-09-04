#!/usr/bin/env python3
"""Run the exact generated-SV TinyStories-1M attention crossing gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json"
)
DEFAULT_MLP_FIXTURE = (
    ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
DEFAULT_RECEIPT = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-sv-receipt.json"
)
LOWERER = (
    ROOT / "scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py"
)


def _load_lowerer():
    spec = importlib.util.spec_from_file_location(
        "fixed_point_attention_crossing_calyx_cli", LOWERER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed-point attention crossing lowerer unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--mlp-fixture", type=Path, default=DEFAULT_MLP_FIXTURE)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--composed", action="store_true")
    parser.add_argument("--yosys-stat", action="store_true")
    args = parser.parse_args()
    if not args.composed:
        parser.error("the bounded acceptance command requires --composed")
    if not args.yosys_stat:
        parser.error("the bounded acceptance command requires --yosys-stat")

    receipt = _load_lowerer().run_composed_attention_sv(
        args.fixture.resolve(), args.mlp_fixture.resolve()
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "passed",
        "receipt": str(args.receipt.resolve()),
        "receipt_sha256": receipt["receipt_sha256"],
        "cycles": receipt["execution"]["cycles"],
        "observed_tensors": len(receipt["observed"]["checkpoints"]),
        "component_count": receipt["execution"]["component_count"],
        "yosys": {
            "status": receipt["synthesis"]["status"],
            "same_futil_sha256": receipt["synthesis"]["same_futil_sha256"],
            "synthesis_sv_sha256": receipt["synthesis"][
                "synthesis_sv_sha256"
            ],
            "resources": receipt["synthesis"]["resources"],
        },
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
