#!/usr/bin/env python3
"""Run the exact stateful TinyStories-1M token-step acceptance gate."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLOCK_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json"
)
DEFAULT_ATTENTION_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json"
)
DEFAULT_MLP_FIXTURE = (
    ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
DEFAULT_RECEIPT = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-token-step-sv-receipt.json"
)
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_token_step_to_calyx.py"


def _load_lowerer():
    spec = importlib.util.spec_from_file_location(
        "fixed_point_token_step_calyx_cli", LOWERER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed-point token-step lowerer unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_receipt(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid token-step receipt: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError("token-step receipt must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block-fixture", type=Path, default=DEFAULT_BLOCK_FIXTURE)
    parser.add_argument(
        "--attention-fixture", type=Path, default=DEFAULT_ATTENTION_FIXTURE
    )
    parser.add_argument("--mlp-fixture", type=Path, default=DEFAULT_MLP_FIXTURE)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--two-transactions", action="store_true")
    parser.add_argument("--yosys-stat", action="store_true")
    args = parser.parse_args()
    if not args.two_transactions:
        parser.error("the bounded acceptance command requires --two-transactions")
    if not args.yosys_stat:
        parser.error("the bounded acceptance command requires --yosys-stat")

    block_fixture = args.block_fixture.resolve()
    attention_fixture = args.attention_fixture.resolve()
    mlp_fixture = args.mlp_fixture.resolve()
    receipt_path = args.receipt.resolve()
    lowerer = _load_lowerer()
    artifact = lowerer.generate_token_step_kernel(
        block_fixture, attention_fixture, mlp_fixture
    )

    previous = None
    if receipt_path.is_file():
        previous = _load_receipt(receipt_path)
        lowerer.validate_token_step_receipt(
            previous,
            block_fixture,
            attention_fixture,
            mlp_fixture,
            verify_artifacts=False,
        )
    receipt = lowerer.run_token_step_sv(
        artifact, block_fixture, attention_fixture, mlp_fixture
    )
    if previous is not None and previous != receipt:
        raise RuntimeError("regenerated token-step receipt differs from authority")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    written = _load_receipt(receipt_path)
    lowerer.validate_token_step_receipt(
        written, block_fixture, attention_fixture, mlp_fixture
    )
    if written != receipt:
        raise RuntimeError("written token-step receipt differs from acceptance")

    print(
        json.dumps(
            {
                "status": "passed",
                "receipt": str(receipt_path),
                "receipt_sha256": receipt["receipt_sha256"],
                "transactions": receipt["transactions"],
                "cycles": receipt["execution"]["cycles"],
                "yosys": receipt["synthesis"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
