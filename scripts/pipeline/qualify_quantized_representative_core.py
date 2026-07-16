#!/usr/bin/env python3
"""Apply structural and iteration-speed gates to a quantized RC candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MIN_LOWERING_SPEEDUP = 10.0
MAX_IR_SIZE_RATIO = 0.10
PREFERRED_LOWERING_SPEEDUP = 100.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify a Torch-MLIR representative-core candidate."
    )
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline-metrics", required=True, type=Path)
    parser.add_argument("--candidate-metrics", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def fingerprint_set(payload: dict[str, Any], field: str) -> set[str]:
    values = payload.get(field)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"fingerprint field {field} must be a list of strings")
    return set(values)


def metric(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"metric {field} must be a positive integer")
    return value


def optional_metric(payload: dict[str, Any], field: str) -> int | None:
    if field not in payload:
        return None
    return metric(payload, field)


def qualify(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> dict[str, Any]:
    if baseline.get("schema_version") != 1 or candidate.get("schema_version") != 1:
        raise ValueError("unsupported fingerprint schema")
    if (
        baseline_metrics.get("schema_version") != 1
        or candidate_metrics.get("schema_version") != 1
    ):
        raise ValueError("unsupported metrics schema")

    missing_operation_names = sorted(
        fingerprint_set(baseline, "operation_names")
        - fingerprint_set(candidate, "operation_names")
    )
    missing_operation_signatures = sorted(
        fingerprint_set(baseline, "operation_signatures")
        - fingerprint_set(candidate, "operation_signatures")
    )
    missing_producer_consumer_edges = sorted(
        fingerprint_set(baseline, "producer_consumer_edges")
        - fingerprint_set(candidate, "producer_consumer_edges")
    )

    baseline_elapsed_ns = metric(baseline_metrics, "lowering_elapsed_ns")
    candidate_elapsed_ns = metric(candidate_metrics, "lowering_elapsed_ns")
    baseline_mlir_bytes = metric(baseline_metrics, "mlir_bytes")
    candidate_mlir_bytes = metric(candidate_metrics, "mlir_bytes")
    baseline_import_elapsed_ns = optional_metric(
        baseline_metrics, "torch_mlir_import_elapsed_ns"
    )
    candidate_import_elapsed_ns = optional_metric(
        candidate_metrics, "torch_mlir_import_elapsed_ns"
    )
    if (baseline_import_elapsed_ns is None) != (candidate_import_elapsed_ns is None):
        raise ValueError("both metrics must either include or omit Torch-MLIR import time")
    lowering_speedup = baseline_elapsed_ns / candidate_elapsed_ns
    ir_size_ratio = candidate_mlir_bytes / baseline_mlir_bytes
    import_speedup = (
        baseline_import_elapsed_ns / candidate_import_elapsed_ns
        if baseline_import_elapsed_ns is not None
        and candidate_import_elapsed_ns is not None
        else None
    )

    failure_reasons: list[str] = []
    if missing_operation_names:
        failure_reasons.append("missing_operation_names")
    if missing_operation_signatures:
        failure_reasons.append("missing_operation_signatures")
    if missing_producer_consumer_edges:
        failure_reasons.append("missing_producer_consumer_edges")
    if lowering_speedup < MIN_LOWERING_SPEEDUP:
        failure_reasons.append("lowering_speedup_below_10x")
    if ir_size_ratio > MAX_IR_SIZE_RATIO:
        failure_reasons.append("ir_size_ratio_above_0.10")

    coverage_complete = not (
        missing_operation_names
        or missing_operation_signatures
        or missing_producer_consumer_edges
    )
    eligible = coverage_complete and not failure_reasons
    return {
        "schema_version": 1,
        "baseline_label": baseline.get("label"),
        "candidate_label": candidate.get("label"),
        "scope": "Torch-MLIR only; not an FPGA resource or equivalence result",
        "coverage": {
            "complete": coverage_complete,
            "missing_operation_names": missing_operation_names,
            "missing_operation_signatures": missing_operation_signatures,
            "missing_producer_consumer_edges": missing_producer_consumer_edges,
        },
        "metrics": {
            "baseline_lowering_elapsed_ns": baseline_elapsed_ns,
            "candidate_lowering_elapsed_ns": candidate_elapsed_ns,
            "lowering_speedup": lowering_speedup,
            "baseline_mlir_bytes": baseline_mlir_bytes,
            "candidate_mlir_bytes": candidate_mlir_bytes,
            "ir_size_ratio": ir_size_ratio,
            "baseline_torch_mlir_import_elapsed_ns": baseline_import_elapsed_ns,
            "candidate_torch_mlir_import_elapsed_ns": candidate_import_elapsed_ns,
            "torch_mlir_import_speedup": import_speedup,
        },
        "thresholds": {
            "minimum_lowering_speedup": MIN_LOWERING_SPEEDUP,
            "maximum_ir_size_ratio": MAX_IR_SIZE_RATIO,
            "preferred_lowering_speedup": PREFERRED_LOWERING_SPEEDUP,
        },
        "eligible": eligible,
        "operationally_valuable": eligible
        and lowering_speedup >= PREFERRED_LOWERING_SPEEDUP,
        "failure_reasons": failure_reasons,
    }


def markdown_report(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    metrics = payload["metrics"]
    thresholds = payload["thresholds"]
    lines = [
        "# Quantized Representative-Core Qualification",
        "",
        f"- Baseline: `{payload['baseline_label']}`",
        f"- Candidate: `{payload['candidate_label']}`",
        f"- Scope: {payload['scope']}",
        f"- Eligible: `{payload['eligible']}`",
        f"- Operationally valuable (>= {thresholds['preferred_lowering_speedup']:.0f}x): `{payload['operationally_valuable']}`",
        "",
        "## Measured gates",
        "",
        f"- Lowering speedup: `{metrics['lowering_speedup']:.3f}x` (minimum `{thresholds['minimum_lowering_speedup']:.0f}x`)",
        (
            "- Torch-MLIR import speedup: `unknown`"
            if metrics["torch_mlir_import_speedup"] is None
            else f"- Torch-MLIR import speedup: `{metrics['torch_mlir_import_speedup']:.3f}x` (diagnostic only; eligibility still uses end-to-end lowering)"
        ),
        f"- Serialized MLIR size ratio: `{metrics['ir_size_ratio']:.6f}` (maximum `{thresholds['maximum_ir_size_ratio']:.2f}`)",
        f"- Structural coverage complete: `{coverage['complete']}`",
        "",
        "## Missing full-model structure",
        "",
    ]
    for key in (
        "missing_operation_names",
        "missing_operation_signatures",
        "missing_producer_consumer_edges",
    ):
        values = coverage[key]
        lines.append(f"- {key}: {', '.join(values) if values else 'none'}")
    lines.extend(["", "## Failure reasons", ""])
    lines.extend(f"- {reason}" for reason in payload["failure_reasons"])
    if not payload["failure_reasons"]:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    payload = qualify(
        load_json(args.baseline),
        load_json(args.candidate),
        load_json(args.baseline_metrics),
        load_json(args.candidate_metrics),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown_out.write_text(markdown_report(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
