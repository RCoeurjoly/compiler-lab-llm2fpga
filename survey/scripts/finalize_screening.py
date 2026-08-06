#!/usr/bin/env python3
"""Validate controlled Phase-1 decisions and consolidate project families."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
        "project_family_key",
        "family_is_primary_work",
        "family_grouping_basis",
        "route_family_final",
    }
)

NAMED_SYSTEM_KEY_PATTERN = re.compile(
    r"named-system:[a-z0-9][a-z0-9_-]*\Z"
)

EXPLICIT_NON_MERGES = (
    (
        ("REC-8079DF7689E5D2AD", "REC-361ADBB8874502B6"),
        "The later particle-physics paper neither cites the earlier audio paper "
        "nor identifies it as a predecessor; shared naming and authors are "
        "insufficient with no direct release, version, or extension evidence.",
    ),
    (
        ("REC-1D91E09883329FFA", "REC-A53433EACA5A3E39"),
        "The later paper cites a conference predecessor, but the cited "
        "conference predecessor is a different 2021 work; neither paper "
        "identifies the other as a release or extension.",
    ),
    (
        ("REC-F95950AEA19221D0", "REC-6099EE66504F6EF2"),
        "Both works use hls4ml in particle-physics transformer implementations, "
        "but shared use of hls4ml is insufficient without an explicit "
        "cross-citation or stated release/extension relationship.",
    ),
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


def project_family_id_for_key(project_family_key: str) -> str:
    """Return the stable public identifier derived from a canonical family key."""

    digest = hashlib.sha256(
        f"project-family:{project_family_key}".encode("utf-8")
    ).hexdigest()
    return f"PF-{digest[:16].upper()}"


def _validate_project_family_assignments(rows: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate keys before deriving stable project-family IDs."""

    _require_columns(
        rows,
        {"record_id", "work_id", "project_family_id", "project_family_key"},
        "project-family assignments",
    )
    normalized = rows.copy()
    for column in ("project_family_id", "project_family_key"):
        normalized[column] = (
            normalized[column].fillna("").astype(str).str.strip()
        )

    has_id = normalized["project_family_id"].ne("")
    has_key = normalized["project_family_key"].ne("")
    if not has_id.equals(has_key):
        raise ValueError(
            "project_family_id and project_family_key must either both be "
            "present or both be blank"
        )

    linked = normalized.loc[has_key].copy()
    if linked.empty:
        return normalized

    keys_per_id = linked.groupby("project_family_id")[
        "project_family_key"
    ].nunique()
    ambiguous_ids = sorted(keys_per_id.loc[keys_per_id.ne(1)].index)
    if ambiguous_ids:
        raise ValueError(
            "every project_family_id must have exactly one project_family_key: "
            + ", ".join(ambiguous_ids)
        )

    keys_per_work = linked.groupby("work_id")["project_family_key"].nunique()
    split_works = sorted(keys_per_work.loc[keys_per_work.ne(1)].index)
    if split_works:
        raise ValueError(
            "every linked work must belong to exactly one project family key: "
            + ", ".join(str(work_id) for work_id in split_works)
        )

    for project_family_key, group in linked.groupby(
        "project_family_key", sort=True
    ):
        work_ids = sorted(set(group["work_id"].astype(str)))
        if project_family_key.startswith("named-system:"):
            if not NAMED_SYSTEM_KEY_PATTERN.fullmatch(project_family_key):
                raise ValueError(
                    "project_family_key must be canonical named-system:<slug>: "
                    + project_family_key
                )
            if len(work_ids) < 2:
                raise ValueError(
                    "named-system project_family_key must link multiple works: "
                    + project_family_key
                )
            continue
        if len(work_ids) != 1 or project_family_key != work_ids[0]:
            raise ValueError(
                "single-work project_family_key must equal work_id: "
                + project_family_key
            )

    expected_ids = linked["project_family_key"].map(project_family_id_for_key)
    if not linked["project_family_id"].equals(expected_ids):
        raise ValueError(
            "project_family_id must be derived from project_family_key"
        )

    return normalized


def _contains_local_path_reference(evidence: str) -> bool:
    for segment in evidence.split(";"):
        token = segment.strip()
        lowered = token.lower()
        if lowered.startswith(("source_url=https://", "source_url=http://")):
            continue
        key, separator, raw_value = token.partition("=")
        value = raw_value.strip() if separator else token
        lowered_value = value.lower()
        if key.strip().lower() in {
            "file",
            "file_path",
            "local_cache",
            "local_path",
            "path",
        }:
            return True
        if lowered_value.startswith(("/", "~/", "file://")):
            return True
        if (
            len(value) >= 3
            and value[1] == ":"
            and value[2] in {"/", "\\"}
        ):
            return True
        if lowered_value.endswith(".pdf") and ("/" in value or "\\" in value):
            return True
    return False


def _validate_title_abstract_evidence(record_id: str, evidence: str) -> None:
    expected = (
        "survey/build/phase1_mapping.csv#record_id="
        f"{record_id}:title+abstract"
    )
    mapping_reference = evidence.split(";", 1)[0].strip()
    if _contains_local_path_reference(evidence):
        raise ValueError(
            "title/abstract evidence cannot contain a local path for "
            f"{record_id}"
        )
    if not mapping_reference.startswith("survey/build/phase1_mapping.csv#"):
        raise ValueError(
            "portable title/abstract evidence must use a frozen mapping path "
            f"for {record_id}"
        )
    if mapping_reference != expected:
        raise ValueError(
            "title/abstract evidence must point to its own frozen mapping record "
            f"for {record_id}"
        )


def validate_decisions(
    mapping: pd.DataFrame, decisions: pd.DataFrame
) -> pd.DataFrame:
    """Return mapping rows joined to one valid controlled final decision each."""

    _require_columns(
        mapping,
        {
            "record_id",
            "work_id",
            "preferred_record_id",
            "is_preferred_manifestation",
            "pdf_url",
            "cache_sha256",
            "cache_json",
        },
        "mapping",
    )
    _require_columns(decisions, DECISION_REQUIRED_COLUMNS, "decisions")

    if mapping["record_id"].duplicated().any():
        raise ValueError("mapping must contain exactly one row per record_id")
    lineage = mapping[
        [
            "record_id",
            "work_id",
            "preferred_record_id",
            "is_preferred_manifestation",
        ]
    ].copy()
    lineage["is_preferred_manifestation"] = [
        _parse_bool(
            value,
            column="is_preferred_manifestation",
            record_id=str(record_id),
        )
        for value, record_id in zip(
            lineage["is_preferred_manifestation"],
            lineage["record_id"],
            strict=True,
        )
    ]
    for work_id, group in lineage.groupby("work_id", sort=False):
        preferred_rows = group.loc[group["is_preferred_manifestation"]]
        if len(preferred_rows) != 1:
            raise ValueError(
                f"work {work_id} must have exactly one preferred manifestation"
            )
        preferred_id = str(preferred_rows.iloc[0]["record_id"])
        recorded_preferred_ids = set(group["preferred_record_id"].astype(str))
        if recorded_preferred_ids != {preferred_id}:
            raise ValueError(
                f"work {work_id} has inconsistent preferred_record_id lineage"
            )
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
    requires_route = ordered["final_level"].isin({"A", "B", "C"})
    if (requires_route & ordered["route_family_final"].eq("")).any():
        raise ValueError("A-C records require a controlled final route family")

    ordered["family_grouping_basis"] = (
        ordered["family_grouping_basis"].fillna("").astype(str).str.strip()
    )
    ordered = _validate_project_family_assignments(ordered)
    has_family = ordered["project_family_key"].ne("")
    if ((~is_x) & ~has_family).any():
        raise ValueError("every included record requires a project family")
    if (has_family & ordered["family_grouping_basis"].eq("")).any():
        raise ValueError("every project family link requires a grouping basis")
    invalid_excluded_family = is_x & has_family & ordered["exclusion_code"].ne(
        "X_DUPLICATE"
    )
    if invalid_excluded_family.any():
        raise ValueError("only X_DUPLICATE records may retain a project family")
    ordered["family_is_primary_work"] = [
        _parse_bool(
            value,
            column="family_is_primary_work",
            record_id=str(record_id),
        )
        for value, record_id in zip(
            ordered["family_is_primary_work"],
            ordered["record_id"],
            strict=True,
        )
    ]
    if ((~has_family) & ordered["family_is_primary_work"]).any():
        raise ValueError("a record without a project family cannot be primary")
    if ((~has_family) & ordered["family_grouping_basis"].ne("")).any():
        raise ValueError(
            "a record without a project family cannot have a grouping basis"
        )

    preferred_by_record = lineage.set_index("record_id")[
        "is_preferred_manifestation"
    ]
    decision_is_preferred = ordered["record_id"].map(preferred_by_record)
    nonpreferred = ~decision_is_preferred
    invalid_nonpreferred = nonpreferred & (
        ordered["final_level"].ne("X")
        | ordered["exclusion_code"].ne("X_DUPLICATE")
    )
    if invalid_nonpreferred.any():
        raise ValueError(
            "non-preferred manifestations must be X/X_DUPLICATE"
        )
    invalid_preferred_duplicate = decision_is_preferred & ordered[
        "exclusion_code"
    ].eq("X_DUPLICATE")
    if invalid_preferred_duplicate.any():
        raise ValueError(
            "X_DUPLICATE is allowed only on non-preferred manifestations"
        )

    ordered_by_id = ordered.set_index("record_id")
    lineage_by_id = lineage.set_index("record_id")
    for duplicate in ordered.loc[nonpreferred].itertuples(index=False):
        preferred_id = str(
            lineage_by_id.loc[duplicate.record_id, "preferred_record_id"]
        )
        preferred = ordered_by_id.loc[preferred_id]
        if preferred["final_level"] == "X":
            if duplicate.project_family_id:
                raise ValueError(
                    "duplicates of an excluded preferred manifestation cannot "
                    "retain a project family"
                )
            continue
        if duplicate.project_family_key != preferred["project_family_key"]:
            raise ValueError(
                "a duplicate and its included preferred manifestation must share "
                "the same project family key"
            )
        if duplicate.project_family_id != preferred["project_family_id"]:
            raise ValueError(
                "a duplicate and its included preferred manifestation must share "
                "the same project family"
            )
        if duplicate.family_grouping_basis != preferred["family_grouping_basis"]:
            raise ValueError(
                "a duplicate and its preferred manifestation must share the same "
                "family grouping basis"
            )

    for column in ("reviewer", "review_basis", "evidence_location"):
        if not _nonblank(ordered, column).all():
            raise ValueError(f"every final decision requires a nonblank {column}")

    ordered["review_basis"] = (
        ordered["review_basis"].fillna("").astype(str).str.strip()
    )
    controlled_review_bases = {
        "title_abstract",
        "title_abstract+local_full_text",
    }
    if not ordered["review_basis"].isin(controlled_review_bases).all():
        raise ValueError("review_basis must use the controlled screening vocabulary")
    for decision in ordered.itertuples(index=False):
        _validate_title_abstract_evidence(
            str(decision.record_id), str(decision.evidence_location)
        )
    source_by_record = mapping.set_index("record_id")
    full_text_rows = ordered.loc[
        ordered["review_basis"].eq("title_abstract+local_full_text")
    ]
    for decision in full_text_rows.itertuples(index=False):
        source_row = source_by_record.loc[decision.record_id]
        source_url = str(source_row["pdf_url"]).strip()
        cache_sha256 = str(source_row["cache_sha256"]).strip().lower()
        try:
            cache_metadata = json.loads(str(source_row["cache_json"]))
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError(
                f"portable full-text evidence lacks cache metadata for "
                f"{decision.record_id}"
            ) from error
        if not isinstance(cache_metadata, dict):
            raise ValueError(
                f"portable full-text evidence lacks cache metadata for "
                f"{decision.record_id}"
            )
        cache_filename = str(cache_metadata.get("filename", "")).strip()
        valid_sha = len(cache_sha256) == 64 and all(
            character in "0123456789abcdef" for character in cache_sha256
        )
        evidence = str(decision.evidence_location)
        required_fragments = (
            f"source_url={source_url}",
            f"cache_filename={cache_filename}",
            f"cache_sha256={cache_sha256}",
            "locator=",
        )
        locator = evidence.split("locator=", 1)[-1].strip()
        if (
            not source_url.startswith(("https://", "http://"))
            or not cache_filename.endswith(".pdf")
            or not valid_sha
            or not locator
            or not all(fragment in evidence for fragment in required_fragments)
            or "/home/" in evidence
            or "LLM-inference-on-FPGA-papers/papers/" in evidence
            or _contains_local_path_reference(evidence)
        ):
            raise ValueError(
                "portable full-text evidence requires the stable source URL, "
                "cached PDF filename, cache SHA-256, and exact locator, and "
                "cannot contain a local path for "
                f"{decision.record_id}"
            )

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
        "project_family_key",
        "family_is_primary_work",
        "family_grouping_basis",
        "evidence_location",
        "route_family_final",
    }
    _require_columns(screened, required, "screened decisions")

    rows = _validate_project_family_assignments(screened)
    rows = rows.loc[rows["project_family_key"].ne("")].copy()
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "project_family_id",
                "project_family_key",
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

    families_per_work = rows.groupby("work_id")["project_family_key"].nunique()
    split_works = sorted(families_per_work.loc[families_per_work.ne(1)].index)
    if split_works:
        raise ValueError(
            "every linked work must belong to exactly one project family: "
            + ", ".join(str(work_id) for work_id in split_works)
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
    for (project_family_key, work_id), group in rows.groupby(
        ["project_family_key", "work_id"], sort=True
    ):
        family_id = project_family_id_for_key(str(project_family_key))
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
        if preferred_rows.empty:
            raise ValueError(
                f"project family {family_id} work {work_id} lacks its included "
                "preferred manifestation"
            )
        chosen = preferred_rows.iloc[0]
        relations.append(
            {
                "project_family_id": str(family_id),
                "project_family_key": str(project_family_key),
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


def _make_repeat_review_sample(screened: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    for level in ("A", "B", "C", "D", "X"):
        candidates = screened.loc[screened["final_level"].eq(level)].copy()
        candidates["sample_hash"] = candidates["record_id"].map(
            lambda record_id: hashlib.sha256(str(record_id).encode()).hexdigest()
        )
        candidates = candidates.sort_values(
            ["sample_hash", "record_id"], kind="stable"
        )
        if level in {"A", "C"}:
            count = len(candidates)
            candidates["selection_rule"] = "all final A/C"
        else:
            count = (len(candidates) + 4) // 5
            candidates["selection_rule"] = "lowest stable hashes; ceil(20%)"
        selected.append(candidates.iloc[:count])
    return pd.concat(selected, ignore_index=True)


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
    repeat_sample = _make_repeat_review_sample(screened)
    sample_counts = repeat_sample["final_level"].value_counts()
    multi_work_families = [
        group
        for _, group in families.groupby("project_family_id", sort=True)
        if len(group) > 1
    ]
    records_by_id = screened.set_index("record_id", drop=False)
    explicit_non_merge_rows = []
    for record_ids, rationale in EXPLICIT_NON_MERGES:
        if not set(record_ids).issubset(records_by_id.index):
            continue
        pair = records_by_id.loc[list(record_ids)]
        family_ids = pair["project_family_id"].astype(str).tolist()
        if len(set(family_ids)) != len(record_ids):
            raise ValueError(
                "an explicit conservative non-merge pair shares a project "
                f"family: {'; '.join(record_ids)}"
            )
        explicit_non_merge_rows.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    "; ".join(record_ids),
                    "; ".join(family_ids),
                    rationale,
                )
            )
            + " |"
        )

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
        "Non-preferred duplicate manifestations use `X_DUPLICATE`. When the "
        "preferred manifestation is included, the family map retains duplicate "
        "record evidence beside it; excluded groups remain traceable here and in "
        "the decision file.",
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
            "SHA-256(`project-family:` + `work_id`). Named multi-work families "
            "use the same derivation with a canonical `named-system:<slug>` key "
            "recorded in `project_family_key`; callers cannot choose IDs. "
            "The default is a conservative single-work family, explicitly marked "
            "`single_work_family`; multiple works share a family only when paper "
            "text identifies a named extension or release relationship. Repository "
            "URL equality is never used as family evidence.",
            "",
            f"Named multi-work families: {len(multi_work_families)}. Every linked "
            "bibliographic work remains a separate row in `project_families.csv`.",
            "",
            "| Project family | Family key | Primary work | Linked works | Grouping basis |",
            "|---|---|---|---|---|",
            *[
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        group.iloc[0]["project_family_id"],
                        group.iloc[0]["project_family_key"],
                        group.iloc[0]["primary_work_id"],
                        ";".join(group["work_id"].astype(str)),
                        group.iloc[0]["family_grouping_basis"],
                    )
                )
                + " |"
                for group in multi_work_families
            ],
            "",
            "## Explicit conservative non-merges",
            "",
            "Similar titles, authors, domains, or framework dependencies do not "
            "establish a shared implementation family without direct lineage "
            "evidence. These reviewed candidate pairs therefore remain separate.",
            "",
            "| Candidate records | Assigned families | Non-merge rationale |",
            "|---|---|---|",
            *(
                explicit_non_merge_rows
                or ["| — | — | No corpus-specific candidate pairs in this fixture. |"]
            ),
            "",
            "## Reviewer sample / re-review design",
            "",
            "The controlled pass is recorded as `codex-title-abstract-screen`. "
            "All provisional A and C records, conflicts, and route-boundary cases "
            "were individually adjudicated; material ambiguity was checked against "
            "the locally cached PDF and marked `title_abstract+local_full_text`. "
            "Obvious exclusions may retain `title_abstract` as their accurate basis.",
            "",
            "The frozen repeat-review set contains every final A/C record. Within "
            "each of B, D, and X independently, records are sorted by "
            "SHA-256(`record_id`) and the first `ceil(20%)` are selected. This "
            "gives an exact, deterministic stratified sample rather than a pooled "
            "Bernoulli approximation.",
            "The exact selected IDs are committed in "
            "`repeat_review_sample.csv` and enumerated below.",
            "",
            "| Level | Available | Frozen repeat-review sample |",
            "|---|---:|---:|",
            *[
                f"| {level} | {int(final_counts.get(level, 0))} | "
                f"{int(sample_counts.get(level, 0))} |"
                for level in ("A", "B", "C", "D", "X")
            ],
            "",
            "A second independent or one-week-delayed blind pass has not been "
            "represented as completed; downstream reporting must preserve this "
            "single-reviewer limitation until that pass is performed.",
            "",
            "| Record ID | Final | Selection rule | SHA-256(record_id) |",
            "|---|---|---|---|",
            *[
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        row.record_id,
                        row.final_level,
                        row.selection_rule,
                        row.sample_hash,
                    )
                )
                + " |"
                for row in repeat_sample.sort_values(
                    ["final_level", "sample_hash", "record_id"], kind="stable"
                ).itertuples(index=False)
            ],
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


def _write_final_flow_counts(
    screened: pd.DataFrame,
    families: pd.DataFrame,
    out_dir: Path,
    *,
    mapping_path: Path,
) -> None:
    source_counts_path = out_dir / "flow_counts.json"
    source_run_path = out_dir / "phase1_run.json"
    if not source_counts_path.is_file() or not source_run_path.is_file():
        raise ValueError(
            "final flow counts require immutable flow_counts.json and "
            "phase1_run.json Phase-1 evidence"
        )

    source_counts_bytes = source_counts_path.read_bytes()
    source_run_bytes = source_run_path.read_bytes()
    if not mapping_path.is_file():
        raise ValueError("final flow counts require the supplied phase1 mapping file")
    mapping_bytes = mapping_path.read_bytes()
    source_counts = json.loads(source_counts_bytes)
    source_run = json.loads(source_run_bytes)
    if not isinstance(source_counts, dict) or not isinstance(source_run, dict):
        raise ValueError("Phase-1 count and run evidence must be JSON objects")

    required_source_counts = {
        "input_records",
        "candidate_unique_works",
        "duplicate_work_groups",
        "duplicate_manifestations",
        "manual_review_queue",
    }
    missing = sorted(required_source_counts - set(source_counts))
    if missing:
        raise ValueError(f"flow_counts.json is missing frozen counts: {missing}")
    output_hashes = source_run.get("output_sha256", {})
    expected_flow_hash = output_hashes.get("flow_counts.json", "")
    actual_flow_hash = hashlib.sha256(source_counts_bytes).hexdigest()
    if expected_flow_hash != actual_flow_hash:
        raise ValueError(
            "flow_counts.json no longer matches immutable phase1_run.json"
        )
    expected_mapping_hash = output_hashes.get("phase1_mapping.csv", "")
    actual_mapping_hash = hashlib.sha256(mapping_bytes).hexdigest()
    if expected_mapping_hash != actual_mapping_hash:
        raise ValueError(
            "phase1_mapping.csv no longer matches immutable phase1_run.json"
        )

    final_levels = screened["final_level"].value_counts()
    exclusions = screened.loc[
        screened["final_level"].eq("X"), "exclusion_code"
    ].value_counts()
    repeat_sample = _make_repeat_review_sample(screened)
    repeat_counts = repeat_sample["final_level"].value_counts()
    final_counts = dict(source_counts)
    final_counts.update(
        {
            "excluded_records": int(screened["final_level"].eq("X").sum()),
            "exclusion_counts": {
                code: int(exclusions.get(code, 0))
                for code in sorted(CONTROLLED_EXCLUSIONS)
            },
            "final_levels": {
                level: int(final_levels.get(level, 0))
                for level in ("A", "B", "C", "D", "X")
            },
            "final_screening_schema_version": 1,
            "included_records": int(screened["include_final"].sum()),
            "included_unique_works": int(
                screened.loc[screened["include_final"], "work_id"].nunique()
            ),
            "project_family_count": int(families["project_family_id"].nunique()),
            "repeat_review_sample_counts": {
                level: int(repeat_counts.get(level, 0))
                for level in ("A", "B", "C", "D", "X")
            },
            "source_phase1_flow_counts_sha256": actual_flow_hash,
            "source_phase1_mapping_sha256": actual_mapping_hash,
            "source_phase1_run": "survey/build/phase1_run.json",
            "source_phase1_run_sha256": hashlib.sha256(source_run_bytes).hexdigest(),
        }
    )
    (out_dir / "final_flow_counts.json").write_text(
        json.dumps(final_counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_screening_outputs(
    screened: pd.DataFrame, out_dir: Path, *, mapping_path: Path
) -> None:
    """Write deterministic products beside the immutable Phase-1 receipt."""

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
    repeat_sample = _make_repeat_review_sample(screened)
    repeat_sample[
        [
            "record_index",
            "record_id",
            "work_id",
            "title",
            "final_level",
            "reviewer",
            "review_basis",
            "evidence_location",
            "selection_rule",
            "sample_hash",
        ]
    ].sort_values(
        ["final_level", "sample_hash", "record_id"], kind="stable"
    ).to_csv(
        out_dir / "repeat_review_sample.csv", index=False, lineterminator="\n"
    )
    _write_final_flow_counts(
        screened, families, out_dir, mapping_path=mapping_path
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
    write_screening_outputs(screened, args.out, mapping_path=args.mapping)
    counts = screened["final_level"].value_counts().sort_index().to_dict()
    print(json.dumps({"records": len(screened), "final_levels": counts}, indent=2))


if __name__ == "__main__":
    main()
