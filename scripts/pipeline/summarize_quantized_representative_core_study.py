#!/usr/bin/env python3
"""Summarize and deterministically select a quantized RC study candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Torch-MLIR quantized representative-core results."
    )
    parser.add_argument("--full-stage", required=True, type=Path)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def parse_candidate(value: str) -> tuple[str, Path]:
    key, separator, path = value.partition("=")
    if not separator or not key or not path:
        raise ValueError("--candidate must have the form KEY=QUALIFICATION_DIRECTORY")
    return key, Path(path)


def candidate_summary(key: str, directory: Path) -> dict[str, Any]:
    report = load_json(directory / "report.json")
    if report.get("schema_version") != 1:
        raise ValueError(f"unsupported report schema in {directory}")
    return {
        "key": key,
        "qualification_directory": str(directory),
        "candidate_label": report.get("candidate_label"),
        "eligible": report.get("eligible") is True,
        "coverage_complete": (report.get("coverage") or {}).get("complete") is True,
        "lowering_speedup": (report.get("metrics") or {}).get("lowering_speedup"),
        "torch_mlir_import_speedup": (report.get("metrics") or {}).get(
            "torch_mlir_import_speedup"
        ),
        "ir_size_ratio": (report.get("metrics") or {}).get("ir_size_ratio"),
        "failure_reasons": report.get("failure_reasons") or [],
    }


def eligible_selection_key(candidate: dict[str, Any]) -> tuple[float, float, str]:
    speedup = candidate["lowering_speedup"]
    size_ratio = candidate["ir_size_ratio"]
    if not isinstance(speedup, (int, float)) or not isinstance(size_ratio, (int, float)):
        raise ValueError(f"eligible candidate {candidate['key']} has invalid metrics")
    return (-float(speedup), float(size_ratio), candidate["key"])


def structural_selection_key(candidate: dict[str, Any]) -> tuple[float, float, str]:
    speedup = candidate["lowering_speedup"]
    size_ratio = candidate["ir_size_ratio"]
    if not isinstance(speedup, (int, float)) or not isinstance(size_ratio, (int, float)):
        raise ValueError(
            f"coverage-complete candidate {candidate['key']} has invalid metrics"
        )
    return (float(size_ratio), -float(speedup), candidate["key"])


def build_summary(full_stage: Path, candidate_args: list[str]) -> dict[str, Any]:
    full_metrics = load_json(full_stage / "metrics.json")
    full_fingerprint = load_json(full_stage / "fingerprint.json")
    if full_metrics.get("schema_version") != 1:
        raise ValueError("unsupported full metrics schema")
    if full_fingerprint.get("schema_version") != 1:
        raise ValueError("unsupported full fingerprint schema")

    candidates = [candidate_summary(*parse_candidate(value)) for value in candidate_args]
    coverage_valid = [
        candidate for candidate in candidates if candidate["coverage_complete"]
    ]
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    structural_finalist = (
        min(coverage_valid, key=structural_selection_key) if coverage_valid else None
    )
    selected = min(eligible, key=eligible_selection_key) if eligible else None
    outcome = (
        "candidate-selected"
        if selected is not None
        else "coverage-valid-finalist-without-speed-eligibility"
        if structural_finalist is not None
        else "no-qualifying-candidate"
    )
    return {
        "schema_version": 1,
        "scope": "Torch-MLIR only; not an FPGA resource or equivalence result",
        "full_stage": {
            "directory": str(full_stage),
            "label": full_fingerprint.get("label"),
            "fingerprint_sha256": full_fingerprint.get("input_sha256"),
            "metrics": full_metrics,
        },
        "candidates": candidates,
        "structural_finalist": structural_finalist,
        "selected_candidate": selected,
        "outcome": outcome,
    }


def markdown_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Quantized Representative-Core PT2E W8A8 Study",
        "",
        f"- Scope: {payload['scope']}",
        f"- Outcome: `{payload['outcome']}`",
        f"- Full model label: `{payload['full_stage']['label']}`",
        "",
        "| candidate | coverage | end-to-end speedup | import speedup | IR size ratio | eligible |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for candidate in payload["candidates"]:
        speedup = candidate["lowering_speedup"]
        import_speedup = candidate["torch_mlir_import_speedup"]
        size_ratio = candidate["ir_size_ratio"]
        speedup_text = (
            f"{speedup:.3f}x" if isinstance(speedup, (int, float)) else "unknown"
        )
        import_speedup_text = (
            f"{import_speedup:.3f}x"
            if isinstance(import_speedup, (int, float))
            else "unknown"
        )
        ratio_text = (
            f"{size_ratio:.6f}" if isinstance(size_ratio, (int, float)) else "unknown"
        )
        lines.append(
            f"| {candidate['key']} | {candidate['coverage_complete']} | {speedup_text} | {import_speedup_text} | {ratio_text} | {candidate['eligible']} |"
        )
    selected = payload["selected_candidate"]
    structural_finalist = payload["structural_finalist"]
    lines.extend(["", "## Selection", ""])
    if selected is None:
        lines.append("No candidate met both full-derived coverage and 10x/0.10 gates.")
    else:
        lines.append(
            f"Selected `{selected['key']}`: highest measured eligible lowering speedup; IR size is the deterministic tie-breaker."
        )
    if structural_finalist is not None and selected is None:
        lines.append(
            f"Coverage-valid structural finalist: `{structural_finalist['key']}`. It is the smallest serialized-MLIR candidate with complete coverage, and is not called an iteration surrogate until it also meets the speed gate."
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    payload = build_summary(args.full_stage, args.candidate)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown_out.write_text(markdown_summary(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
