#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FLOAT_OPS = [
    "arith.sitofp",
    "arith.mulf",
    "arith.addf",
    "arith.divf",
    "math.roundeven",
    "arith.fptosi",
]


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def diagnose(stage: str, input_path: Path) -> dict[str, object]:
    text = input_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    first_quantized_matmul_line: int | None = None
    float_ops_after_quantized_matmul: list[dict[str, object]] = []

    for index, line in enumerate(lines, start=1):
        if first_quantized_matmul_line is None:
            if "linalg.quantized_matmul" in line:
                first_quantized_matmul_line = index
            continue

        for op in FLOAT_OPS:
            if op in line:
                float_ops_after_quantized_matmul.append(
                    {
                        "line": index,
                        "op": op,
                        "text": line.strip(),
                    }
                )

    hard_failures = []
    if float_ops_after_quantized_matmul:
        first = float_ops_after_quantized_matmul[0]
        hard_failures.append(
            {
                "stage": stage,
                "kind": "float-after-quantized-matmul",
                "evidence": f"{first['op']} at line {first['line']}",
            }
        )

    return {
        "stage": stage,
        "artifact": str(input_path),
        "bytes": input_path.stat().st_size,
        "lines": len(lines),
        "saw_quantized_matmul": first_quantized_matmul_line is not None,
        "first_quantized_matmul_line": first_quantized_matmul_line,
        "float_ops_after_quantized_matmul": float_ops_after_quantized_matmul,
        "hard_failures": hard_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose float leakage after linalg.quantized_matmul."
    )
    parser.add_argument("--stage", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--fail-on-float-after-quantized-matmul", action="store_true")
    args = parser.parse_args()

    report = diagnose(args.stage, args.input)
    write_json(args.out, report)

    if args.fail_on_float_after_quantized_matmul and report["hard_failures"]:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
