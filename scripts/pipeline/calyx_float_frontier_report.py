#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


FLOAT_OP_RE = re.compile(
    r"\b("
    r"arith\.(?:sitofp|uitofp|fptosi|mulf|divf|addf|subf|cmpf|maximumf|minimumf|truncf)"
    r"|math\.[A-Za-z0-9_]+"
    r")\b"
)
FLOAT_TYPE_RE = re.compile(r"\b(?:f16|f32|f64)\b")
UNSUPPORTED_CALYX_FLOAT_OPS = {
    "arith.uitofp",
    "math.exp",
    "math.rsqrt",
}


def build_report(input_path: Path, sample_limit: int) -> dict[str, object]:
    op_counts: Counter[str] = Counter()
    unsupported_counts: Counter[str] = Counter()
    float_type_lines = 0
    samples: list[dict[str, object]] = []
    unsupported_samples: list[dict[str, object]] = []

    for lineno, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        ops = FLOAT_OP_RE.findall(line)
        unsupported_ops = [op for op in ops if op in UNSUPPORTED_CALYX_FLOAT_OPS]
        for op in ops:
            op_counts[op] += 1
        for op in unsupported_ops:
            unsupported_counts[op] += 1
        if FLOAT_TYPE_RE.search(line):
            float_type_lines += 1
        if ops and len(samples) < sample_limit:
            samples.append(
                {
                    "line": lineno,
                    "ops": ops,
                    "text": line.strip(),
                }
            )
        if unsupported_ops and len(unsupported_samples) < sample_limit:
            unsupported_samples.append(
                {
                    "line": lineno,
                    "ops": unsupported_ops,
                    "text": line.strip(),
                }
            )

    total_float_ops = sum(op_counts.values())
    total_unsupported_ops = sum(unsupported_counts.values())
    return {
        "input": str(input_path),
        "status": (
            "has-unsupported-calyx-float-frontier"
            if total_unsupported_ops
            else "has-float-frontier"
            if total_float_ops
            else "ok"
        ),
        "total_float_ops": total_float_ops,
        "total_unsupported_ops": total_unsupported_ops,
        "float_type_lines": float_type_lines,
        "op_counts": dict(sorted(op_counts.items())),
        "unsupported_ops": dict(sorted(unsupported_counts.items())),
        "samples": samples,
        "unsupported_samples": unsupported_samples,
    }


def compact_manifest_summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "status": report["status"],
        "total_float_ops": report["total_float_ops"],
        "total_unsupported_ops": report["total_unsupported_ops"],
        "unsupported_ops": report["unsupported_ops"],
    }


def merge_manifest(manifest_path: Path, report: dict[str, object]) -> None:
    if not manifest_path.is_file():
        raise SystemExit(f"missing manifest JSON: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["float_frontier"] = compact_manifest_summary(report)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report Calyx-incompatible float operations before Calyx lowering."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument(
        "--manifest-json",
        type=Path,
        help="Optionally merge a compact float-frontier summary into this manifest.",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"missing input MLIR: {args.input}")
    if args.sample_limit < 0:
        raise SystemExit("--sample-limit must be non-negative")

    report = build_report(args.input, args.sample_limit)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.manifest_json is not None:
        merge_manifest(args.manifest_json, report)


if __name__ == "__main__":
    main()
