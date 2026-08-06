#!/usr/bin/env python3
"""Render deterministic D13--D15 survey figures from frozen evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import pandas as pd


if __package__ in {None, ""}:
    # A direct file invocation otherwise exposes survey/scripts, rather than
    # the repository root, on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from survey.scripts.common import load_scope


ROOT = Path(__file__).resolve().parents[2]
ROUTE_TAXONOMY = (
    "MLIR_CIRCT",
    "PARAMETERIZED_RTL",
    "HLS",
    "DATAFLOW",
    "OVERLAY",
    "CPU_FPGA_FALLBACK",
)
FINAL_LEVELS = {"A": 30, "B": 57, "C": 75, "D": 68, "X": 231}


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _load_json(path: Path) -> dict[str, object]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON evidence: {path}") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON evidence must be an object: {path}")
    return loaded


def _integer(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        raise ValueError(f"final flow count {key} must be an integer")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"final flow count {key} must be an integer") from error


def _validate_final_flow(flow: Mapping[str, object]) -> None:
    expected = {
        "input_records": 461,
        "candidate_unique_works": 456,
        "duplicate_manifestations": 5,
        "included_records": 230,
        "excluded_records": 231,
    }
    for key, value in expected.items():
        if _integer(flow, key) != value:
            raise ValueError(f"final flow count {key} must be {value}")
    levels = flow.get("final_levels")
    if not isinstance(levels, Mapping):
        raise ValueError("final_flow_counts.json is missing final_levels")
    normalized_levels = {str(key): int(value) for key, value in levels.items()}
    if normalized_levels != FINAL_LEVELS:
        raise ValueError(
            "final_flow_counts.json must contain final A=30/B=57/C=75/D=68/X=231"
        )
    if sum(normalized_levels.values()) != _integer(flow, "input_records"):
        raise ValueError("final screening levels do not reconcile to source records")


def _node(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\[[^\[\]\n]+\])?", value.strip()))


def validate_mermaid(source: str) -> None:
    """Reject structurally malformed offline Mermaid flowchart source."""

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines or lines[0] not in {"flowchart TD", "flowchart LR"}:
        raise ValueError("Mermaid source must begin with a supported flowchart declaration")
    if len(lines) < 2:
        raise ValueError("Mermaid source must contain at least one edge")
    for line in lines[1:]:
        if line.count("-->") != 1:
            raise ValueError(f"Mermaid edge must contain exactly one -->: {line}")
        source_node, target_node = (part.strip() for part in line.split("-->", 1))
        if not _node(source_node) or not _node(target_node):
            raise ValueError(f"Mermaid node is malformed: {line}")


def render_corpus_flow(flow: Mapping[str, object]) -> str:
    """Render D13 from the adjudicated final counts, never Phase-1 auto levels."""

    _validate_final_flow(flow)
    return "\n".join(
        (
            "flowchart TD",
            'source["Commit-pinned catalogue: 461 source records"] --> normalized["Normalized records: 461"]',
            'normalized --> works["Deduplicated works: 456 unique works; 5 duplicate manifestations"]',
            'works --> levels["Final screening: A: 30; B: 57; C: 75; D: 68; X: 231"]',
            'levels --> included["Included records: 230"]',
            'levels --> excluded["Excluded records: 231"]',
        )
    ) + "\n"


def _route_taxonomy_from_scope(root: Path) -> tuple[str, ...]:
    scope = load_scope(root / "survey/config/scope.yaml")
    routes = scope.get("route_families")
    if not isinstance(routes, list) or tuple(str(route) for route in routes) != ROUTE_TAXONOMY:
        raise ValueError("scope route taxonomy does not match the frozen protocol")
    return ROUTE_TAXONOMY


def build_route_family_comparison(root: Path) -> tuple[pd.DataFrame, int]:
    """Return D14 counts for the frozen taxonomy and unassigned primary families."""

    taxonomy = _route_taxonomy_from_scope(root)
    final_flow = _load_json(root / "survey/build/final_flow_counts.json")
    _validate_final_flow(final_flow)
    families = pd.read_csv(root / "survey/build/project_families.csv")
    reviews = pd.read_csv(root / "survey/build/deep_review.csv")
    required_family = {"project_family_id", "is_primary_work", "route_family"}
    required_review = {"project_family_id", "route_family"}
    if missing := sorted(required_family - set(families.columns)):
        raise ValueError(f"project_families.csv is missing columns: {missing}")
    if missing := sorted(required_review - set(reviews.columns)):
        raise ValueError(f"deep_review.csv is missing columns: {missing}")
    primary = families.loc[
        families["is_primary_work"].map(lambda value: _text(value).lower()).eq("true")
    ].copy()
    expected_families = _integer(final_flow, "project_family_count")
    if primary["project_family_id"].nunique() != expected_families:
        raise ValueError("primary project-family rows do not match final_flow_counts.json")
    if len(reviews) != 36 or not 25 <= len(reviews) <= 40:
        raise ValueError("deep review must contain 25--40 rows and currently be 36")
    primary_routes = primary["route_family"].map(_text)
    review_routes = reviews["route_family"].map(_text)
    unknown_primary = set(primary_routes) - {"", *taxonomy}
    unknown_review = set(review_routes) - set(taxonomy)
    if unknown_primary or unknown_review:
        raise ValueError(
            "route-family comparison contains values outside the frozen taxonomy"
        )
    rows = []
    for route in taxonomy:
        rows.append(
            {
                "route_family": route,
                "corpus_primary_families": int(primary_routes.eq(route).sum()),
                "reviewed_families": int(review_routes.eq(route).sum()),
            }
        )
    comparison = pd.DataFrame(rows)
    if int(comparison["reviewed_families"].sum()) != len(reviews):
        raise ValueError("reviewed route-family counts do not reconcile to deep review")
    return comparison, int(primary_routes.eq("").sum())


def render_route_family_comparison(
    comparison: pd.DataFrame, unassigned_primary_families: int
) -> str:
    """Render a human-readable D14 comparison with evidence provenance."""

    lines = [
        "# D14 route-family comparison",
        "",
        "This table is derived from `survey/build/project_families.csv` primary "
        "family rows and the 36 rows in `survey/build/deep_review.csv`. It keeps "
        "the six route-family values frozen in `survey/config/scope.yaml`; blank "
        "source-family assignments are counted separately rather than becoming a "
        "seventh taxonomy value.",
        "",
        "| Route family | Corpus primary families | Reviewed families/control rows |",
        "| --- | ---: | ---: |",
    ]
    for row in comparison.to_dict(orient="records"):
        lines.append(
            "| {route_family} | {corpus_primary_families} | {reviewed_families} |".format(
                **row
            )
        )
    lines.extend(
        (
            "",
            f"Unassigned primary-family rows: **{unassigned_primary_families}**; "
            "they are not recast as a route family.",
            "",
            "Evidence: `survey/build/project_families.csv`; "
            "`survey/build/deep_review.csv`; `survey/config/scope.yaml`.",
            "",
        )
    )
    return "\n".join(lines)


def render_timeline() -> str:
    """Render the protocol's canonical sequence without invented calendar dates."""

    return "\n".join(
        (
            "flowchart LR",
            'scope["Freeze scope and catalogue amendment"] --> triage["Automated triage"]',
            'triage --> screening["Manual screening"]',
            'screening --> lineage["Deduplication and lineage"]',
            'lineage --> review["Deep review and extraction"]',
            'review --> audit["Artifact and repository audit"]',
            'audit --> compatibility["Route compatibility"]',
            'compatibility --> mlir["MLIR/CIRCT sub-survey"]',
            'mlir --> decision["Decision matrix and report"]',
        )
    ) + "\n"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<OUTPUT_DIR>" if path.suffix == "" else f"<OUTPUT_DIR>/{path.name}"


def write_figures(root: Path = ROOT, out: Path | None = None) -> dict[str, Path]:
    """Write deterministic D13--D15 artifacts and return their paths."""

    out = out or root / "survey/build"
    out.mkdir(parents=True, exist_ok=True)
    final_flow = _load_json(root / "survey/build/final_flow_counts.json")
    corpus_flow = render_corpus_flow(final_flow)
    validate_mermaid(corpus_flow)
    comparison, unassigned = build_route_family_comparison(root)
    timeline = render_timeline()
    validate_mermaid(timeline)

    corpus_flow_path = out / "corpus_flow.mmd"
    comparison_csv_path = out / "route_family_comparison.csv"
    comparison_md_path = out / "route_family_comparison.md"
    timeline_path = out / "timeline.mmd"
    _write_text(corpus_flow_path, corpus_flow)
    comparison.to_csv(comparison_csv_path, index=False, lineterminator="\n")
    _write_text(
        comparison_md_path,
        render_route_family_comparison(comparison, unassigned),
    )
    _write_text(timeline_path, timeline)
    return {
        "corpus_flow_mmd": corpus_flow_path,
        "route_family_comparison_csv": comparison_csv_path,
        "route_family_comparison_md": comparison_md_path,
        "timeline_mmd": timeline_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render deterministic survey figures")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    outputs = write_figures(root, args.out)
    print(json.dumps({name: _display_path(root, path) for name, path in outputs.items()}, indent=2))


if __name__ == "__main__":
    main()
