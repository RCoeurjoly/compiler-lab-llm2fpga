#!/usr/bin/env python3
"""Compare Task 3 full TinyStories and representative-core utilization reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


THRESHOLD = 10.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--shape-json", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-md", required=True)
    parser.add_argument("--baseline-label", required=True)
    parser.add_argument("--candidate-label", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def metric(summary: dict[str, Any], old_key: str, new_key: str) -> float | None:
    usage = summary.get("usage")
    if isinstance(usage, dict):
        value = as_number(usage.get(old_key))
        if value is not None:
            return value
    resources = summary.get("resources")
    if isinstance(resources, dict):
        row = resources.get(new_key)
        if isinstance(row, dict):
            return as_number(row.get("used"))
    return None


def pct(summary: dict[str, Any], old_key: str, new_key: str) -> float | None:
    utilization = summary.get("utilization")
    if isinstance(utilization, dict):
        value = as_number(utilization.get(old_key))
        if value is not None:
            return value
    resources = summary.get("resources")
    if isinstance(resources, dict):
        row = resources.get(new_key)
        if isinstance(row, dict):
            return as_number(row.get("pct"))
    return None


def reduction_ratio(baseline: float | None, candidate: float | None) -> float | None:
    if baseline is None or candidate in (None, 0):
        return None
    return baseline / candidate


def ratio_status(ratio: float | None) -> str:
    if ratio is None:
        return "incomplete"
    return "pass" if ratio >= THRESHOLD else "failed-threshold"


def shape_ratio(shapes: dict[str, Any], field: str) -> float | None:
    full = (shapes.get("full_tinystories") or {}).get(field)
    core = (shapes.get("representative_core") or {}).get(field)
    full_n = as_number(full)
    core_n = as_number(core)
    if full_n is None or core_n in (None, 0):
        return None
    return full_n / core_n


def fmt(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Task 3 Representative-Core Parity",
        "",
        f"- status: `{payload['status']}`",
        f"- baseline: `{payload['baseline_label']}`",
        f"- candidate: `{payload['candidate_label']}`",
        f"- threshold: `{THRESHOLD:g}x` LUT and FF reduction",
        "",
        "| metric | baseline | representative core | reduction | threshold status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for key in ["lut_total", "ff_total"]:
        row = payload["hard_metrics"][key]
        lines.append(
            f"| {key} | {fmt(row['baseline'])} | {fmt(row['candidate'])} | "
            f"{fmt(row['reduction_ratio'])}x | {row['status']} |"
        )

    lines.extend(
        [
            "",
            "## Reported Context",
            "",
            f"- baseline LUT utilization: {fmt(payload['context']['baseline_lut_pct'])}%",
            f"- candidate LUT utilization: {fmt(payload['context']['candidate_lut_pct'])}%",
            f"- baseline FF utilization: {fmt(payload['context']['baseline_ff_pct'])}%",
            f"- candidate FF utilization: {fmt(payload['context']['candidate_ff_pct'])}%",
            f"- baseline BRAM36 equivalent: {fmt(payload['context']['baseline_bram36_equivalent'])}",
            f"- candidate BRAM36 equivalent: {fmt(payload['context']['candidate_bram36_equivalent'])}",
            "",
            "## Shape Ratios",
            "",
            "| field | full / representative-core ratio |",
            "| --- | ---: |",
        ]
    )
    for field, ratio in payload["shape_reduction_ratios"].items():
        lines.append(f"| {field} | {fmt(ratio)}x |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    baseline_dir = Path(args.baseline_dir)
    candidate_dir = Path(args.candidate_dir)
    baseline = load_json(baseline_dir / "summary.json")
    candidate = load_json(candidate_dir / "summary.json")
    shapes = load_json(Path(args.shape_json))

    baseline_lut = metric(baseline, "lut_total", "clb_luts")
    candidate_lut = metric(candidate, "lut_total", "clb_luts")
    baseline_ff = metric(baseline, "ff_total", "clb_ffs")
    candidate_ff = metric(candidate, "ff_total", "clb_ffs")
    lut_ratio = reduction_ratio(baseline_lut, candidate_lut)
    ff_ratio = reduction_ratio(baseline_ff, candidate_ff)

    metric_statuses = [ratio_status(lut_ratio), ratio_status(ff_ratio)]
    if "incomplete" in metric_statuses:
        status = "incomplete"
    elif all(item == "pass" for item in metric_statuses):
        status = "validated"
    else:
        status = "failed-threshold"

    payload = {
        "status": status,
        "baseline_label": args.baseline_label,
        "candidate_label": args.candidate_label,
        "thresholds": {
            "lut_reduction_min": THRESHOLD,
            "ff_reduction_min": THRESHOLD,
        },
        "hard_metrics": {
            "lut_total": {
                "baseline": baseline_lut,
                "candidate": candidate_lut,
                "reduction_ratio": lut_ratio,
                "status": ratio_status(lut_ratio),
            },
            "ff_total": {
                "baseline": baseline_ff,
                "candidate": candidate_ff,
                "reduction_ratio": ff_ratio,
                "status": ratio_status(ff_ratio),
            },
        },
        "context": {
            "baseline_lut_pct": pct(baseline, "lut_pct", "clb_luts"),
            "candidate_lut_pct": pct(candidate, "lut_pct", "clb_luts"),
            "baseline_ff_pct": pct(baseline, "ff_pct", "clb_ffs"),
            "candidate_ff_pct": pct(candidate, "ff_pct", "clb_ffs"),
            "baseline_bram36_equivalent": metric(
                baseline, "bram36_equivalent", "bram36_equiv"
            ),
            "candidate_bram36_equivalent": metric(
                candidate, "bram36_equivalent", "bram36_equiv"
            ),
        },
        "shape_metadata": shapes,
        "shape_reduction_ratios": {
            field: shape_ratio(shapes, field)
            for field in [
                "vocab_size",
                "hidden_size",
                "num_layers",
                "num_attention_heads",
                "max_position_embeddings",
            ]
        },
        "inputs": {
            "baseline_dir": str(baseline_dir),
            "candidate_dir": str(candidate_dir),
            "shape_json": args.shape_json,
        },
    }

    Path(args.summary_json).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.summary_md).write_text(build_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
