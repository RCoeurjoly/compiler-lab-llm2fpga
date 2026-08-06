#!/usr/bin/env python3
"""Deterministically select and render the conservative deep-review sample."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


SCORE_LIMITS = {
    "causal_lm_relevance_score": 3,
    "distinct_route_score": 2,
    "artifact_availability_score": 2,
    "open_toolchain_migration_score": 2,
    "quantitative_evidence_score": 1,
}

RQ_COLUMNS = [
    "rq1_input_frontend",
    "rq1_source_irs",
    "rq1_intermediate_irs",
    "rq1_backend",
    "rq1_architecture",
    "rq1_control_model",
    "rq1_generation_mode",
    "rq2_model_family",
    "rq2_prefill",
    "rq2_decode",
    "rq2_token_loop",
    "rq2_attention",
    "rq2_ffn",
    "rq2_normalization",
    "rq2_rope",
    "rq2_kv_cache",
    "rq2_softmax",
    "rq2_sampling",
    "rq2_completeness",
    "rq3_frontend",
    "rq3_passes",
    "rq3_rtl",
    "rq3_hls",
    "rq3_runtime",
    "rq3_tests",
    "rq3_reuse_notes",
    "rq4_source_openness",
    "rq4_hls_openness",
    "rq4_synthesis_openness",
    "rq4_place_and_route_openness",
    "rq4_required_closed_tools_or_ip",
    "rq4_vendor_primitives",
    "rq4_migration_work",
    "rq5_minimum_model",
    "rq5_precision",
    "rq5_shape",
    "rq5_memory",
    "rq5_device",
    "rq5_resource",
    "rq5_clock",
    "rq5_throughput",
    "rq5_latency",
    "rq5_power",
    "rq6_reference_model",
    "rq6_vectors",
    "rq6_simulators",
    "rq6_formal_support",
    "rq6_environment",
    "rq6_interfaces",
    "rq6_reproduction_status",
]

DEEP_REVIEW_COLUMNS = [
    "project_family_id",
    "title",
    "level_final",
    "route_family",
    "preferred_record_id",
    "publication_year",
    "mandatory_reason",
    *SCORE_LIMITS,
    "selection_score",
    *RQ_COLUMNS,
    "evidence_locations",
    "notes",
]

EVIDENCE_REQUIRED_COLUMNS = [
    "level_final",
    "route_family",
    "mandatory_reason",
    *SCORE_LIMITS,
    *RQ_COLUMNS,
]

MANDATORY_REASONS = {
    "supported_level_a",
    "distinct_executable_c_route",
    "compiler_lab_artifact_control",
    "open_block_artifact",
    "route_incompatibility_case",
}

EXPECTED_ROUTE_FAMILIES = {
    "MLIR_CIRCT",
    "PARAMETERIZED_RTL",
    "HLS",
    "DATAFLOW",
    "OVERLAY",
    "CPU_FPGA_FALLBACK",
}


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _integer(value: object, field: str) -> int:
    text = _text(value)
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError(f"{field} must be an integer")
    return int(text)


def score_family(family: pd.Series) -> int:
    """Return the frozen 0--10 protocol score for one family."""

    total = 0
    for field, maximum in SCORE_LIMITS.items():
        value = _integer(family.get(field, ""), field)
        if value < 0 or value > maximum:
            raise ValueError(f"{field} must be between 0 and {maximum}")
        total += value
    return total


def _portable_evidence(location: str) -> bool:
    return bool(
        re.match(r"^https://[^\s]+(?:#|;locator=)[^\s]+$", location)
        and "@" not in location.split("https://", 1)[-1].split("/", 1)[0]
        and not re.search(r"(?:file://|/home/|/tmp/|[A-Za-z]:\\)", location)
    )


def _parse_evidence(value: object, family_id: str) -> dict[str, str]:
    try:
        evidence = json.loads(_text(value))
    except json.JSONDecodeError as error:
        raise ValueError(f"{family_id}: evidence_locations must be valid JSON") from error
    if not isinstance(evidence, dict):
        raise ValueError(f"{family_id}: evidence_locations must be a JSON object")
    normalized = {str(key): _text(location) for key, location in evidence.items()}
    for field, location in normalized.items():
        if not location or not _portable_evidence(location):
            raise ValueError(
                f"{family_id}: {field} lacks a portable URL and exact locator"
            )
    return normalized


def validate_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Validate the complete manual RQ1--RQ6 schema and evidence contract."""

    if list(reviews.columns) != DEEP_REVIEW_COLUMNS:
        raise ValueError(
            "reviews must use the exact deep-review schema; "
            f"expected={DEEP_REVIEW_COLUMNS}, found={list(reviews.columns)}"
        )
    cleaned = reviews.copy().fillna("")
    if cleaned.empty or cleaned["project_family_id"].duplicated().any():
        raise ValueError("reviews require one unique project_family_id per row")

    for index, row in cleaned.iterrows():
        family_id = _text(row["project_family_id"])
        if not family_id:
            raise ValueError("project_family_id cannot be blank")
        reason = _text(row["mandatory_reason"])
        reasons = {part for part in reason.split("|") if part}
        unknown = reasons - MANDATORY_REASONS
        if unknown:
            raise ValueError(f"{family_id}: unknown mandatory_reason {sorted(unknown)}")
        score = score_family(row)
        stored_score = _integer(row["selection_score"], "selection_score")
        if stored_score != score:
            raise ValueError(
                f"{family_id}: selection_score {stored_score} does not equal {score}"
            )
        evidence = _parse_evidence(row["evidence_locations"], family_id)
        for field in EVIDENCE_REQUIRED_COLUMNS:
            value = _text(row[field])
            if not value:
                continue
            if field in SCORE_LIMITS and _integer(value, field) == 0:
                continue
            if field not in evidence:
                raise ValueError(
                    f"{family_id}: non-empty decision-critical {field} lacks evidence"
                )
        cleaned.loc[index, "evidence_locations"] = json.dumps(
            evidence, sort_keys=True, separators=(",", ":")
        )
    return cleaned


def _primary_families(families: pd.DataFrame) -> pd.DataFrame:
    required = {
        "project_family_id",
        "is_primary_work",
        "preferred_record_id",
        "title",
        "level_final",
        "route_family",
    }
    missing = required - set(families.columns)
    if missing:
        raise ValueError(f"families missing required columns: {sorted(missing)}")
    flags = families["is_primary_work"].map(lambda value: _text(value).lower())
    primary = families.loc[flags.eq("true")].copy()
    if primary["project_family_id"].duplicated().any():
        raise ValueError("families contain duplicate primary project-family rows")
    return primary


def _ranked(rows: pd.DataFrame) -> pd.DataFrame:
    ranked = rows.copy()
    ranked["_publication_year"] = pd.to_numeric(
        ranked["publication_year"], errors="coerce"
    ).fillna(-1)
    return ranked.sort_values(
        by=[
            "artifact_availability_score",
            "distinct_route_score",
            "causal_lm_relevance_score",
            "_publication_year",
            "project_family_id",
        ],
        ascending=[False, False, False, False, True],
        kind="mergesort",
    ).drop(columns="_publication_year")


def _mandatory_mask(rows: pd.DataFrame) -> pd.Series:
    return rows["mandatory_reason"].map(lambda value: bool(_text(value)))


def _exception_routes(mandatory: pd.DataFrame, target: int) -> set[str]:
    exceptions: set[str] = set()
    cap = math.floor(target * 0.30)
    supported_a = mandatory[mandatory["mandatory_reason"].str.contains(
        r"(?:^|\|)supported_level_a(?:\||$)", regex=True
    )]
    for route, rows in supported_a.groupby("route_family"):
        if len(rows) > cap:
            exceptions.add(_text(route))
    return exceptions


def _select_for_size(
    eligible: pd.DataFrame,
    mandatory_ids: set[str],
    target: int,
    exception_routes: set[str],
) -> pd.DataFrame | None:
    cap = math.floor(target * 0.30)
    chosen = eligible[eligible["project_family_id"].isin(mandatory_ids)].copy()
    counts = chosen["route_family"].value_counts().to_dict()
    for route, count in counts.items():
        if route not in exception_routes and count > cap:
            return None
    if len(chosen) == target:
        return _ranked(chosen)
    for _, row in eligible.iterrows():
        family_id = _text(row["project_family_id"])
        if family_id in mandatory_ids:
            continue
        route = _text(row["route_family"])
        if route not in exception_routes and counts.get(route, 0) >= cap:
            continue
        chosen = pd.concat([chosen, row.to_frame().T], ignore_index=True)
        counts[route] = counts.get(route, 0) + 1
        if len(chosen) == target:
            return _ranked(chosen)
    return None


def select_families(families: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Select 25--40 families with mandatory coverage and route diversity."""

    reviews = validate_reviews(reviews)
    primary = _primary_families(families)
    controls = reviews[reviews["project_family_id"].str.startswith("CONTROL-")]
    corpus_reviews = reviews[~reviews.index.isin(controls.index)]
    unknown = set(corpus_reviews["project_family_id"]) - set(primary["project_family_id"])
    if unknown:
        raise ValueError(f"reviews reference unknown project families: {sorted(unknown)}")

    family_metadata = primary.set_index("project_family_id")
    for _, review in corpus_reviews.iterrows():
        source = family_metadata.loc[review["project_family_id"]]
        for field in ("title", "level_final", "route_family", "preferred_record_id"):
            if _text(review[field]) != _text(source[field]):
                raise ValueError(
                    f"{review['project_family_id']}: {field} disagrees with frozen families"
                )

    if not controls.empty:
        if list(controls["project_family_id"]) != ["CONTROL-COMPILER-LAB"]:
            raise ValueError("controlled extraction requires one compiler-lab control")
        all_a = set(primary.loc[primary["level_final"].eq("A"), "project_family_id"])
        supported_a = set(
            reviews.loc[
                reviews["mandatory_reason"].str.contains(
                    r"(?:^|\|)supported_level_a(?:\||$)", regex=True
                ),
                "project_family_id",
            ]
        )
        if supported_a != all_a:
            raise ValueError("controlled extraction must include every supported Level A family")
        c_routes = set(
            reviews.loc[
                reviews["level_final"].eq("C")
                & reviews["mandatory_reason"].str.contains(
                    r"(?:^|\|)distinct_executable_c_route(?:\||$)", regex=True
                ),
                "route_family",
            ]
        )
        if c_routes != EXPECTED_ROUTE_FAMILIES:
            raise ValueError("controlled extraction requires each executable C route")
        incompatibility_routes = set(
            reviews.loc[
                reviews["mandatory_reason"].str.contains(
                    r"(?:^|\|)route_incompatibility_case(?:\||$)", regex=True
                ),
                "route_family",
            ]
        )
        if incompatibility_routes != EXPECTED_ROUTE_FAMILIES:
            raise ValueError("controlled extraction requires one incompatibility case per route")
        if not reviews["mandatory_reason"].str.contains(
            r"(?:^|\|)open_block_artifact(?:\||$)", regex=True
        ).any():
            raise ValueError("controlled extraction requires an open block artifact")

    scored = reviews.copy()
    scored["selection_score"] = scored.apply(score_family, axis=1)
    mandatory = scored[_mandatory_mask(scored)]
    eligible = scored[(scored["selection_score"] >= 7) | _mandatory_mask(scored)]
    eligible = _ranked(eligible)
    if len(eligible) < 25:
        raise ValueError("at least 25 eligible project families are required")
    if len(mandatory) > 40:
        raise ValueError("mandatory project families exceed the 40-family ceiling")

    mandatory_ids = set(mandatory["project_family_id"])
    upper = min(40, len(eligible))
    selected: pd.DataFrame | None = None
    exception_routes: set[str] = set()
    for target in range(upper, 24, -1):
        if target < len(mandatory):
            break
        exception_routes = _exception_routes(mandatory, target)
        selected = _select_for_size(
            eligible, mandatory_ids, target, exception_routes
        )
        if selected is not None:
            break
    if selected is None:
        raise ValueError("no 25--40 family selection satisfies the route-family cap")

    selected = selected.sort_values("project_family_id", kind="mergesort").reset_index(
        drop=True
    )
    selected.attrs["route_cap_exception"] = "|".join(sorted(exception_routes))
    return selected[DEEP_REVIEW_COLUMNS]


def _unknown(value: object) -> str:
    return _text(value) or "not reported"


def render_markdown(selected: pd.DataFrame) -> str:
    exception = selected.attrs.get("route_cap_exception", "")
    counts = selected["route_family"].value_counts().sort_index()
    lines = [
        "# Deep-review family extraction",
        "",
        f"Selected project-family/control rows: **{len(selected)}**.",
        "",
        "Every populated RQ1–RQ6 value is linked to a portable exact locator in "
        "the CSV `evidence_locations` object. Blank CSV values are rendered as "
        "`not reported`; no blank is an inferred positive claim.",
        "",
        "Evidence status is recorded in `notes` as documented, observed, or inferred. "
        "No Task 5 repository audit or reproducibility conclusion is pre-claimed.",
        "",
        "## Composition",
        "",
    ]
    for route, count in counts.items():
        lines.append(f"- `{route}`: {count}")
    if exception:
        lines.extend(
            [
                "",
                "The 30% route-family cap has a protocol exception for "
                f"`{exception}` because the mandatory supported Level A families "
                "alone exceed the cap.",
            ]
        )
    lines.extend(
        [
            "",
            "## Selected families",
            "",
            "| CSV row | Family | Level | Route | Score | RQ2 completeness | "
            "RQ4 closed requirements | RQ6 reproduction status |",
            "|---:|---|---|---|---:|---|---|---|",
        ]
    )
    for index, row in selected.iterrows():
        csv_row = index + 2
        lines.append(
            f"| [row {csv_row}](deep_review.csv#L{csv_row}) | "
            f"{row['project_family_id']} — {row['title']} | {row['level_final']} | "
            f"{row['route_family']} | {row['selection_score']} | "
            f"{_unknown(row['rq2_completeness'])} | "
            f"{_unknown(row['rq4_required_closed_tools_or_ip'])} | "
            f"{_unknown(row['rq6_reproduction_status'])} |"
        )
    lines.extend(
        [
            "",
            "## Scope limitation",
            "",
            "This Task 4 extraction is deliberately limited to claims supported by "
            "the frozen paper/title/abstract evidence and the pinned compiler-lab "
            "control. Repository availability, licenses, dependency closure, and "
            "reproduction status remain `not reported` unless the row contains an "
            "exact citation. Task 5 performs the broader repository audit.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(selected: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    selected.to_csv(out / "deep_review.csv", index=False, lineterminator="\n")
    (out / "deep_review.md").write_text(render_markdown(selected), encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    families = pd.read_csv(args.families, dtype=str, keep_default_na=False)
    reviews = pd.read_csv(args.reviews, dtype=str, keep_default_na=False)
    selected = select_families(families, reviews)
    write_outputs(selected, args.out)
    print(f"selected: {len(selected)}")
    print("routes: " + ", ".join(
        f"{route}={count}"
        for route, count in selected["route_family"].value_counts().sort_index().items()
    ))
    exception = selected.attrs.get("route_cap_exception", "")
    print(f"route_cap_exception: {exception or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
