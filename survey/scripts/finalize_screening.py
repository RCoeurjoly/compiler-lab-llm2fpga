#!/usr/bin/env python3
"""Validate controlled Phase-1 decisions and consolidate project families."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd


FINAL_LEVELS = frozenset({"A", "B", "C", "D", "X"})
ROUTE_FAMILIES = frozenset(
    {
        "MLIR_CIRCT",
        "PARAMETERIZED_RTL",
        "HLS",
        "DATAFLOW",
        "OVERLAY",
        "CPU_FPGA_FALLBACK",
    }
)
CONTROLLED_EXCLUSIONS = frozenset(
    {
        "X_NOT_FPGA",
        "X_LLM_FOR_EDA",
        "X_TRAINING_ONLY",
        "X_NON_LM_MODEL",
        "X_VIT_NO_TRANSFER",
        "X_ASIC_GPU_ONLY",
        "X_PERFORMANCE_MODEL_ONLY",
        "X_SECONDARY",
        "X_NO_EVIDENCE",
        "X_DUPLICATE",
        "X_RETRACTED",
    }
)

DECISION_REQUIRED_COLUMNS = frozenset(
    {
        "record_id",
        "work_id",
        "final_level",
        "include_final",
        "exclusion_code",
        "reviewer",
        "review_basis",
        "evidence_location",
        "decision_notes",
        "project_family_id",
        "family_is_primary_work",
        "family_grouping_basis",
        "route_family_final",
    }
)


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _parse_bool(value: object, *, column: str, record_id: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{column} must be Boolean for {record_id}")


def _nonblank(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].fillna("").astype(str).str.strip().ne("")


def validate_decisions(
    mapping: pd.DataFrame, decisions: pd.DataFrame
) -> pd.DataFrame:
    """Return mapping rows joined to one valid controlled final decision each."""

    _require_columns(mapping, {"record_id", "work_id"}, "mapping")
    _require_columns(decisions, DECISION_REQUIRED_COLUMNS, "decisions")

    if mapping["record_id"].duplicated().any():
        raise ValueError("mapping must contain exactly one row per record_id")
    expected_ids = mapping["record_id"].astype(str).tolist()
    actual_ids = decisions["record_id"].astype(str).tolist()
    if len(actual_ids) != len(expected_ids) or set(actual_ids) != set(expected_ids):
        raise ValueError("every source record requires exactly one decision")
    if decisions["record_id"].duplicated().any():
        raise ValueError("every source record requires exactly one decision")

    ordered = decisions.set_index("record_id").loc[expected_ids].reset_index().copy()
    expected_work = mapping.set_index("record_id").loc[expected_ids, "work_id"].astype(str)
    actual_work = ordered.set_index("record_id")["work_id"].astype(str)
    if not expected_work.equals(actual_work):
        raise ValueError("decision work_id must match the frozen mapping")

    ordered["final_level"] = (
        ordered["final_level"].fillna("").astype(str).str.strip().str.upper()
    )
    invalid_levels = ordered.loc[
        ~ordered["final_level"].isin(FINAL_LEVELS), ["record_id", "final_level"]
    ]
    if not invalid_levels.empty:
        raise ValueError(
            "final_level must be exactly one of A/B/C/D/X: "
            + invalid_levels.to_dict(orient="records").__repr__()
        )

    ordered["include_final"] = [
        _parse_bool(value, column="include_final", record_id=str(record_id))
        for value, record_id in zip(
            ordered["include_final"], ordered["record_id"], strict=True
        )
    ]
    is_x = ordered["final_level"].eq("X")
    if (is_x & ordered["include_final"]).any():
        raise ValueError("X records must be excluded")
    if ((~is_x) & (~ordered["include_final"])).any():
        raise ValueError("A-D records must be included")

    ordered["exclusion_code"] = (
        ordered["exclusion_code"].fillna("").astype(str).str.strip().str.upper()
    )
    invalid_exclusions = is_x & ~ordered["exclusion_code"].isin(
        CONTROLLED_EXCLUSIONS
    )
    if invalid_exclusions.any():
        raise ValueError("every X record requires one controlled exclusion code")
    if ((~is_x) & ordered["exclusion_code"].ne("")).any():
        raise ValueError("A-D records cannot have an exclusion code")

    ordered["route_family_final"] = (
        ordered["route_family_final"].fillna("").astype(str).str.strip().str.upper()
    )
    invalid_routes = ordered["route_family_final"].ne("") & ~ordered[
        "route_family_final"
    ].isin(ROUTE_FAMILIES)
    if invalid_routes.any():
        raise ValueError("route_family_final must be a controlled route family")
    if (is_x & ordered["route_family_final"].ne("")).any():
        raise ValueError("X records cannot have a final route family")

    ordered["project_family_id"] = (
        ordered["project_family_id"].fillna("").astype(str).str.strip()
    )
    ordered["family_grouping_basis"] = (
        ordered["family_grouping_basis"].fillna("").astype(str).str.strip()
    )
    has_family = ordered["project_family_id"].ne("")
    if ((~is_x) & ~has_family).any():
        raise ValueError("every included record requires a project family")
    if (has_family & ordered["family_grouping_basis"].eq("")).any():
        raise ValueError("every project family link requires a grouping basis")
    work_ids = set(mapping["work_id"].fillna("").astype(str))
    if ordered.loc[has_family, "project_family_id"].isin(work_ids).any():
        raise ValueError("project_family_id must be distinct from work_id")
    invalid_excluded_family = is_x & has_family & ordered["exclusion_code"].ne(
        "X_DUPLICATE"
    )
    if invalid_excluded_family.any():
        raise ValueError("only X_DUPLICATE records may retain a project family")
    for value, record_id in zip(
        ordered.loc[has_family, "family_is_primary_work"],
        ordered.loc[has_family, "record_id"],
        strict=True,
    ):
        _parse_bool(
            value,
            column="family_is_primary_work",
            record_id=str(record_id),
        )

    for column in ("reviewer", "review_basis", "evidence_location"):
        if not _nonblank(ordered, column).all():
            raise ValueError(f"every final decision requires a nonblank {column}")

    join_keys = {"record_id", "work_id"}
    decision_columns = [
        "record_id",
        "work_id",
        *sorted(DECISION_REQUIRED_COLUMNS - join_keys),
    ]
    source = mapping.copy()
    source_conflicts = (set(source.columns) & set(decision_columns)) - join_keys
    source_renames = {column: f"{column}_source" for column in source_conflicts}
    conflicting_renames = set(source_renames.values()) & set(source.columns)
    if conflicting_renames:
        raise ValueError(
            "mapping already contains reserved source columns: "
            + ", ".join(sorted(conflicting_renames))
        )
    source = source.rename(columns=source_renames)
    screened = source.merge(
        ordered[decision_columns],
        on=["record_id", "work_id"],
        how="left",
        validate="one_to_one",
    )
    return screened


def _json_list(values: Iterable[object]) -> str:
    normalized = sorted(
        {str(value).strip() for value in values if str(value).strip()}
    )
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def make_project_families(screened: pd.DataFrame) -> pd.DataFrame:
    """Return one traceable row per project-family/work relationship."""

    required = {
        "record_id",
        "work_id",
        "preferred_record_id",
        "title",
        "final_level",
        "include_final",
        "project_family_id",
        "family_is_primary_work",
        "family_grouping_basis",
        "evidence_location",
        "route_family_final",
    }
    _require_columns(screened, required, "screened decisions")

    rows = screened.copy()
    rows["project_family_id"] = (
        rows["project_family_id"].fillna("").astype(str).str.strip()
    )
    rows = rows.loc[rows["project_family_id"].ne("")].copy()
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "project_family_id",
                "primary_work_id",
                "work_id",
                "is_primary_work",
                "preferred_record_id",
                "record_ids_json",
                "title",
                "level_final",
                "route_family",
                "family_grouping_basis",
                "evidence_sources_json",
            ]
        )

    rows["family_is_primary_work"] = [
        _parse_bool(
            value,
            column="family_is_primary_work",
            record_id=str(record_id),
        )
        for value, record_id in zip(
            rows["family_is_primary_work"], rows["record_id"], strict=True
        )
    ]

    relations: list[dict[str, object]] = []
    for (family_id, work_id), group in rows.groupby(
        ["project_family_id", "work_id"], sort=True
    ):
        primary_values = set(group["family_is_primary_work"].tolist())
        if len(primary_values) != 1:
            raise ValueError(
                f"family/work relation has inconsistent primary status: "
                f"{family_id}/{work_id}"
            )
        included = group.loc[group["final_level"].isin(["A", "B", "C", "D"])]
        if included.empty:
            raise ValueError(
                f"project family {family_id} links work {work_id} without an "
                "included primary manifestation"
            )
        levels = sorted(set(included["final_level"].astype(str)))
        routes = sorted(
            {
                str(value).strip()
                for value in included["route_family_final"]
                if str(value).strip()
            }
        )
        bases = sorted(
            {
                str(value).strip()
                for value in group["family_grouping_basis"]
                if str(value).strip()
            }
        )
        preferred_id = str(included.iloc[0]["preferred_record_id"])
        preferred_rows = included.loc[included["record_id"].eq(preferred_id)]
        chosen = preferred_rows.iloc[0] if not preferred_rows.empty else included.iloc[0]
        relations.append(
            {
                "project_family_id": str(family_id),
                "work_id": str(work_id),
                "is_primary_work": primary_values.pop(),
                "preferred_record_id": preferred_id,
                "record_ids_json": _json_list(group["record_id"]),
                "title": str(chosen["title"]),
                "level_final": levels[0] if len(levels) == 1 else ";".join(levels),
                "route_family": routes[0] if len(routes) == 1 else ";".join(routes),
                "family_grouping_basis": ";".join(bases),
                "evidence_sources_json": _json_list(group["evidence_location"]),
            }
        )

    families = pd.DataFrame(relations).sort_values(
        ["project_family_id", "work_id"], kind="stable"
    )
    primary = (
        families.loc[families["is_primary_work"]]
        .groupby("project_family_id")["work_id"]
        .agg(list)
    )
    all_family_ids = sorted(set(families["project_family_id"]))
    invalid = [
        family_id
        for family_id in all_family_ids
        if len(primary.get(family_id, [])) != 1
    ]
    if invalid:
        raise ValueError(
            "every project family requires exactly one primary work: "
            + ", ".join(invalid)
        )
    primary_by_family = {
        family_id: work_ids[0] for family_id, work_ids in primary.items()
    }
    families.insert(
        1,
        "primary_work_id",
        families["project_family_id"].map(primary_by_family),
    )
    return families.reset_index(drop=True)


def _markdown_cell(value: object) -> str:
    return (
        str(value)
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("|", "\\|")
        .strip()
    )


def _count_table(counts: pd.Series, ordered_values: Iterable[str]) -> list[str]:
    lines = ["| Disposition | Records |", "|---|---:|"]
    for value in ordered_values:
        lines.append(f"| {value} | {int(counts.get(value, 0))} |")
    return lines


def _make_screening_audit(
    screened: pd.DataFrame, families: pd.DataFrame
) -> str:
    final_counts = screened["final_level"].value_counts()
    exclusion_counts = screened.loc[
        screened["final_level"].eq("X"), "exclusion_code"
    ].value_counts()
    duplicate_rows = screened.loc[
        screened["dedup_rule"].fillna("").astype(str).ne("unique")
        | ~screened["is_preferred_manifestation"].map(
            lambda value: _parse_bool(
                value,
                column="is_preferred_manifestation",
                record_id="audit-row",
            )
        )
    ]

    lines = [
        "# Controlled Phase-1 screening audit",
        "",
        "This audit is generated from the frozen Phase-1 mapping and the "
        "controlled reviewer decisions. Automatic levels and scores remain "
        "source metadata and never substitute for `final_level`.",
        "",
        "## Reconciliation",
        "",
        f"- Source manifestations: {len(screened)}",
        f"- Bibliographic work IDs: {screened['work_id'].nunique()}",
        f"- Included A-D manifestations: {int(screened['include_final'].sum())}",
        f"- Excluded X manifestations: {int(screened['final_level'].eq('X').sum())}",
        f"- Included project families: {families['project_family_id'].nunique() if not families.empty else 0}",
        "",
        "## Final counts",
        "",
        *_count_table(final_counts, ("A", "B", "C", "D", "X")),
        "",
        "## Controlled exclusion counts",
        "",
        *_count_table(exclusion_counts, sorted(CONTROLLED_EXCLUSIONS)),
        "",
        "## Duplicate/version decisions",
        "",
        "Every source manifestation remains in `screening_decisions.csv`. "
        "Non-preferred duplicate manifestations use `X_DUPLICATE`; the family "
        "map retains their record evidence beside the preferred manifestation.",
        "",
        "| Work ID | Record ID | Preferred record | Dedup rule | Final | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    if duplicate_rows.empty:
        lines.append("| — | — | — | unique-only fixture | — | — |")
    else:
        for row in duplicate_rows.sort_values(
            ["work_id", "record_index"], kind="stable"
        ).itertuples(index=False):
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        row.work_id,
                        row.record_id,
                        row.preferred_record_id,
                        row.dedup_rule,
                        row.final_level,
                        row.evidence_location,
                    )
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Project-family consolidation",
            "",
            "Project-family IDs are distinct from bibliographic `work_id` values. "
            "For conservative single-work families, the stable identifier is "
            "`PF-` followed by the first 16 uppercase hexadecimal characters of "
            "SHA-256(`project-family:` + `work_id`). "
            "The default is a conservative single-work family, explicitly marked "
            "`single_work_family`; multiple works share a family only when paper "
            "text identifies a named extension or release relationship. Repository "
            "URL equality is never used as family evidence.",
            "",
            "## Reviewer sample / re-review design",
            "",
            "The controlled pass is recorded as `codex-title-abstract-screen`. "
            "All provisional A and C records, conflicts, and route-boundary cases "
            "were individually adjudicated; material ambiguity was checked against "
            "the locally cached PDF and marked `title_abstract+local_full_text`. "
            "Obvious exclusions may retain `title_abstract` as their accurate basis.",
            "",
            "The frozen repeat-review set is every final A/C record plus the stable "
            "20% sample of B/D/X for which the first byte of SHA-256(record_id) is "
            "below 51. A second independent or one-week-delayed blind pass has not "
            "been represented as completed; downstream reporting must preserve this "
            "single-reviewer limitation until that pass is performed.",
            "",
            "## Unresolved but non-blocking uncertainty",
            "",
            "- Route-family labels describe the closest frozen route vocabulary; "
            "Level D components may intentionally have no route family.",
            "- Single-work project families are conservative: absence of explicit "
            "cross-work release evidence is not evidence that no broader project "
            "relationship exists.",
            "- The delayed or independent repeat-review sample remains a reporting "
            "limitation, not an invented agreement statistic.",
            "",
            "## Decision evidence paths",
            "",
            "Every final disposition and reviewer basis is listed below; these paths "
            "are also machine-readable in `screening_decisions.csv`.",
            "",
            "| Record ID | Final | Reviewer | Basis | Evidence location |",
            "|---|---|---|---|---|",
        ]
    )
    for row in screened.sort_values("record_index", kind="stable").itertuples(
        index=False
    ):
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row.record_id,
                    row.final_level,
                    row.reviewer,
                    row.review_basis,
                    row.evidence_location,
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_screening_outputs(screened: pd.DataFrame, out_dir: Path) -> None:
    """Write deterministic exclusion, family, and audit evidence products."""

    out_dir.mkdir(parents=True, exist_ok=True)
    exclusion_columns = [
        "record_index",
        "record_id",
        "work_id",
        "title",
        "auto_level",
        "screen_priority_score",
        "final_level",
        "exclusion_code",
        "reviewer",
        "review_basis",
        "evidence_location",
        "decision_notes",
        "preferred_record_id",
        "is_preferred_manifestation",
        "dedup_rule",
        "preferred_manifestation_rationale",
    ]
    exclusions = screened.loc[
        screened["final_level"].eq("X"), exclusion_columns
    ].sort_values("record_index", kind="stable")
    exclusions.to_csv(
        out_dir / "phase1_exclusions.csv", index=False, lineterminator="\n"
    )

    families = make_project_families(screened)
    families.to_csv(
        out_dir / "project_families.csv", index=False, lineterminator="\n"
    )
    (out_dir / "screening_audit.md").write_text(
        _make_screening_audit(screened, families), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate controlled Phase-1 decisions and build audit outputs"
    )
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=461)
    args = parser.parse_args()

    mapping = pd.read_csv(args.mapping, keep_default_na=False)
    decisions = pd.read_csv(args.decisions, keep_default_na=False)
    if len(mapping) != args.expected_records:
        raise SystemExit(
            f"Expected {args.expected_records} frozen records; found {len(mapping)}"
        )
    screened = validate_decisions(mapping, decisions)
    write_screening_outputs(screened, args.out)
    counts = screened["final_level"].value_counts().sort_index().to_dict()
    print(json.dumps({"records": len(screened), "final_levels": counts}, indent=2))


if __name__ == "__main__":
    main()
