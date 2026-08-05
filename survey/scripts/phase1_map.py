#!/usr/bin/env python3
"""Normalize, classify, and transparently deduplicate the frozen survey corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from rapidfuzz.fuzz import ratio


OUTPUT_NAMES = (
    "records_normalized.csv",
    "duplicate_groups.csv",
    "works_deduplicated.csv",
    "phase1_mapping.csv",
    "phase1_mapping.parquet",
    "phase1_uncertain.csv",
    "flow_counts.json",
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list, tuple)):
        return _json(value)
    return str(value).strip()


def _first(record: dict[str, object], *names: str) -> object:
    for name in names:
        if name in record and record[name] not in (None, "", [], {}):
            return record[name]
    return ""


def _string_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, dict):
        return [_json(value)]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"\s*;\s*", text) if part.strip()]


def _author_list(value: object) -> list[str]:
    items = value if isinstance(value, (list, tuple)) else [value]
    authors: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = _text(_first(item, "name", "full_name", "display_name"))
        else:
            name = _text(item)
        if name:
            authors.append(name)
    return authors


def _repository_url(record: dict[str, object]) -> str:
    explicit = _text(_first(record, "repo_url", "code_url", "repository_url", "github"))
    if explicit:
        return explicit.rstrip(".,;:)")
    searchable = "\n".join(
        _text(record.get(name)) for name in ("title", "abstract", "summary", "description")
    )
    match = re.search(
        r"https?://(?:www\.)?(?:github|gitlab)\.com/[^\s<>\"'\])},;]+",
        searchable,
        re.IGNORECASE,
    )
    return match.group().rstrip(".,;:)") if match else ""


def extract_records(catalogue: object) -> list[tuple[str, dict[str, object]]]:
    """Return version-preserving ``(catalog_key, record)`` pairs.

    Both the pinned mapping-shaped ``papers`` object and the protocol's list
    schema are accepted. Input order is retained as source provenance.
    """

    container: object = catalogue
    if isinstance(catalogue, dict):
        for name in ("papers", "records", "items", "entries", "catalog"):
            if name in catalogue:
                container = catalogue[name]
                break
    if isinstance(container, dict):
        pairs: list[tuple[str, dict[str, object]]] = []
        for key, value in container.items():
            if not isinstance(value, dict):
                raise ValueError(f"catalogue record {key!r} is not a mapping")
            pairs.append((str(key), dict(value)))
        return pairs
    if isinstance(container, list):
        pairs = []
        seen: set[str] = set()
        for index, value in enumerate(container):
            if not isinstance(value, dict):
                raise ValueError(f"catalogue record {index} is not a mapping")
            base = normalize_arxiv(_text(_first(value, "arxiv_id", "arxiv")))
            version = _integer(_first(value, "version", "arxiv_version"))
            source_id = _text(_first(value, "record_id", "id", "paper_id"))
            key = _text(_first(value, "catalog_key"))
            if not key and base:
                key = f"{base}v{version}" if version is not None else base
            if not key:
                key = source_id
            if not key:
                key = f"record-{index:06d}"
            if key in seen:
                suffix = hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:12]
                key = f"{key}#{suffix}"
                if key in seen:
                    key = f"{key}-{index:06d}"
            seen.add(key)
            pairs.append((key, dict(value)))
        return pairs
    raise ValueError("could not locate a mapping or list of catalogue records")


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"-\s*\n\s*", "", value)
    value = value.lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


normalize_text = normalize_title


def normalize_doi(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    value = re.sub(r"^doi\s*:\s*", "", value)
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .;,)")


def normalize_arxiv(value: str) -> str:
    match = re.search(
        r"(?:arxiv\s*:\s*|(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?",
        (value or "").lower(),
    )
    return match.group(1) if match else ""


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _year(*values: object) -> int | None:
    for value in values:
        match = re.search(r"\b(?:19|20)\d{2}\b", _text(value))
        if match:
            return int(match.group())
    return None


def _authoritative_ids(record: dict[str, object]) -> dict[str, str]:
    aliases = {
        "openalex": ("openalex_id", "openalex"),
        "semantic_scholar": (
            "semantic_scholar_id",
            "semanticscholar_id",
            "s2_id",
        ),
        "pubmed": ("pubmed_id", "pmid"),
    }
    result: dict[str, str] = {}
    for authority, names in aliases.items():
        value = _text(_first(record, *names)).lower()
        if value:
            value = re.sub(r"^https?://[^/]+/", "", value).strip(" /.")
            result[authority] = value
    return result


def canonicalize_record(record_key: str, record: dict[str, object]) -> dict[str, object]:
    """Canonicalize one source manifestation without discarding raw metadata."""

    raw_json = _json(record)
    base_arxiv = normalize_arxiv(
        " ".join(
            [
                record_key,
                _text(_first(record, "arxiv_id", "arxiv")),
                _text(_first(record, "abs_url", "url", "paper_url", "pdf_url")),
            ]
        )
    )
    version = _integer(_first(record, "version", "arxiv_version"))
    version_match = re.search(r"v(\d+)(?:\.pdf)?$", record_key.lower())
    if version is None and version_match:
        version = int(version_match.group(1))
    version_id = f"{base_arxiv}v{version}" if base_arxiv and version is not None else record_key
    title = _text(_first(record, "title", "paper_title", "name"))
    abstract = _text(_first(record, "abstract", "summary", "description"))
    authors = _author_list(_first(record, "authors", "author"))
    normalized_authors = [normalize_title(author) for author in authors]
    categories = _string_list(_first(record, "categories", "category"))
    query_ids = _string_list(_first(record, "query_ids", "queries", "query_id"))
    cache = record.get("cache") if isinstance(record.get("cache"), dict) else {}
    assert isinstance(cache, dict)
    doi = normalize_doi(_text(_first(record, "doi", "DOI", "doi_url")))
    publication_year = _year(
        _first(record, "year", "publication_year"),
        _first(record, "published_at", "published", "date"),
    )
    record_hash = hashlib.sha256(record_key.encode("utf-8")).hexdigest()[:16].upper()
    return {
        "record_index": -1,
        "record_id": f"REC-{record_hash}",
        "source_record_id": _text(_first(record, "record_id", "id", "paper_id")),
        "catalog_key": record_key,
        "arxiv_version_id": version_id,
        "arxiv_id": base_arxiv,
        "arxiv_version": version,
        "title": title,
        "title_normalized": normalize_title(title),
        "abstract": abstract,
        "abstract_length": len(abstract),
        "authors": "; ".join(authors),
        "authors_json": _json(authors),
        "authors_normalized_json": _json(normalized_authors),
        "first_author_normalized": normalized_authors[0] if normalized_authors else "",
        "categories_json": _json(categories),
        "primary_category": _text(_first(record, "primary_category")),
        "keywords": _text(_first(record, "keywords", "tags", "topics")),
        "publication_year": publication_year,
        "published_at": _text(_first(record, "published_at", "published", "date")),
        "updated_at": _text(_first(record, "updated_at", "updated")),
        "retrieved_at": _text(_first(record, "retrieved_at")),
        "doi": doi,
        "authoritative_ids_json": _json(_authoritative_ids(record)),
        "abs_url": _text(_first(record, "abs_url", "url", "paper_url")),
        "pdf_url": _text(_first(record, "pdf_url")),
        "source_url": _text(_first(record, "source_url", "paper_url", "abs_url", "url", "pdf_url")),
        "repo_url": _repository_url(record),
        "license_url": _text(_first(record, "license_url")),
        "journal_ref": _text(_first(record, "journal_ref", "venue", "journal")),
        "query_ids_json": _json(query_ids),
        "catalog_query_id": _text(record.get("_catalog_query_id")),
        "cache_sha256": _text(cache.get("sha256")),
        "cache_json": _json(cache),
        "raw_record_json": raw_json,
    }


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> bool:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return False
        if left_root > right_root:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        return True


_RULE_CONFIDENCE = {
    "exact_doi": 1.0,
    "exact_arxiv": 1.0,
    "exact_authoritative_id": 1.0,
    "exact_title": 0.99,
    "fuzzy_title_95": 0.95,
    "fuzzy_title_92": 0.92,
}
_RULE_ORDER = {rule: number for number, rule in enumerate(_RULE_CONFIDENCE)}


def _source_groups(record: dict[str, object]) -> list[str]:
    groups: list[str] = []
    if record["doi"]:
        groups.append(f"doi:{record['doi']}")
    if record["arxiv_id"]:
        groups.append(f"arxiv:{record['arxiv_id']}")
    authoritative = json.loads(str(record["authoritative_ids_json"]))
    groups.extend(f"{key}:{value}" for key, value in sorted(authoritative.items()))
    if record["title_normalized"]:
        title_hash = hashlib.sha256(str(record["title_normalized"]).encode()).hexdigest()[:16]
        groups.append(f"title_sha256:{title_hash}")
    return groups


def _distinctive_subtitle(title: str) -> str:
    pieces = re.split(r"\s*[:—–]\s*", title, maxsplit=1)
    return normalize_title(pieces[1]) if len(pieces) == 2 and len(pieces[1].split()) >= 3 else ""


def _manifestation_rank(record: dict[str, object]) -> tuple[object, ...]:
    combined = normalize_title(f"{record['title']} {record['abstract']}")
    corrected = bool(re.search(r"\b(corrected|correction|corrigendum|revised)\b", combined))
    peer_reviewed = bool(record["doi"] or record["journal_ref"])
    artifact = bool(record["repo_url"])
    withdrawn = bool(re.search(r"\b(withdrawn|retracted)\b", combined))
    if corrected and peer_reviewed and artifact and not withdrawn:
        tier = 4
    elif peer_reviewed and not withdrawn:
        tier = 3
    elif record["arxiv_id"] and not withdrawn:
        tier = 2
    elif record["repo_url"] and not withdrawn:
        tier = 1
    else:
        tier = 0
    return (
        tier,
        int(record["arxiv_version"] or 0),
        str(record["updated_at"]),
        str(record["record_id"]),
    )


def _manifestation_rationale(record: dict[str, object]) -> str:
    tier = _manifestation_rank(record)[0]
    return {
        4: "corrected peer-reviewed manifestation with public artifact; latest version breaks ties",
        3: "peer-reviewed manifestation; latest version breaks ties",
        2: "latest non-withdrawn preprint",
        1: "repository manuscript",
        0: "best available non-preferred manifestation metadata",
    }[int(tier)]


def _pair_identity_conflict(
    left: dict[str, object],
    right: dict[str, object],
    attempted_rule: str,
) -> dict[str, object] | None:
    """Return independent contradictory identity evidence, if conclusive."""

    conflicting_fields: list[str] = []
    identifier_conflicts: list[str] = []
    if left["doi"] and right["doi"] and left["doi"] != right["doi"]:
        identifier_conflicts.append("doi")
    if left["arxiv_id"] and right["arxiv_id"] and left["arxiv_id"] != right["arxiv_id"]:
        identifier_conflicts.append("arxiv_id")
    left_authorities = json.loads(str(left["authoritative_ids_json"]))
    right_authorities = json.loads(str(right["authoritative_ids_json"]))
    for authority in sorted(set(left_authorities) & set(right_authorities)):
        if left_authorities[authority] != right_authorities[authority]:
            identifier_conflicts.append(f"authoritative_id:{authority}")

    left_title, right_title = str(left["title_normalized"]), str(right["title_normalized"])
    similarity = (
        float(ratio(left_title, right_title)) if left_title and right_title else None
    )
    title_conflict = similarity is not None and similarity < 70
    first_author_conflict = bool(
        left["first_author_normalized"]
        and right["first_author_normalized"]
        and left["first_author_normalized"] != right["first_author_normalized"]
    )
    if title_conflict:
        conflicting_fields.append("title")
    if first_author_conflict:
        conflicting_fields.append("first_author")
    conflicting_fields = identifier_conflicts + conflicting_fields

    conclusive = False
    if attempted_rule in {"exact_doi", "exact_arxiv", "exact_authoritative_id"}:
        conclusive = bool(identifier_conflicts and title_conflict and first_author_conflict)
    elif attempted_rule == "exact_title":
        conclusive = bool(len(identifier_conflicts) >= 2 and first_author_conflict)
    elif attempted_rule in {"fuzzy_title_95", "fuzzy_title_92"}:
        conclusive = bool(len(identifier_conflicts) >= 2 and first_author_conflict)
    if not conclusive:
        return None
    return {
        "left_record_id": left["record_id"],
        "right_record_id": right["record_id"],
        "conflicting_fields": conflicting_fields,
        "similarity": similarity,
    }


def deduplicate(
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Apply ordered identity rules and return works plus full record lineage."""

    uf = _UnionFind(len(records))
    evidence: dict[int, list[dict[str, object]]] = defaultdict(list)

    def component_members(index: int) -> list[int]:
        root = uf.find(index)
        return [candidate for candidate in range(len(records)) if uf.find(candidate) == root]

    def try_add_edge(
        left: int,
        right: int,
        rule: str,
        details: dict[str, object],
    ) -> bool:
        left_members = component_members(left)
        right_members = component_members(right)
        conflicts = [
            conflict
            for left_member in left_members
            for right_member in right_members
            if (
                conflict := _pair_identity_conflict(
                    records[left_member], records[right_member], rule
                )
            )
            is not None
        ]
        if conflicts:
            conflict_fields = sorted(
                {
                    field
                    for conflict in conflicts
                    for field in conflict["conflicting_fields"]
                }
            )
            conflict_evidence = {
                "rule": "contradictory_identity",
                "attempted_rule": rule,
                "alternative": "manual_adjudication",
                "component_level": len(left_members) > 1 or len(right_members) > 1,
                "conflicting_fields": conflict_fields,
                "conflicting_record_pairs": conflicts,
                **details,
            }
            evidence[left].append(
                {"other_record_id": records[right]["record_id"], **conflict_evidence}
            )
            evidence[right].append(
                {"other_record_id": records[left]["record_id"], **conflict_evidence}
            )
            return False
        item_left = {"other_record_id": records[right]["record_id"], "rule": rule, **details}
        item_right = {"other_record_id": records[left]["record_id"], "rule": rule, **details}
        evidence[left].append(item_left)
        evidence[right].append(item_right)
        uf.union(left, right)
        return True

    exact_rules: list[tuple[str, Any]] = [
        ("exact_doi", lambda row: [("doi", row["doi"])] if row["doi"] else []),
        ("exact_arxiv", lambda row: [("arxiv", row["arxiv_id"])] if row["arxiv_id"] else []),
        (
            "exact_authoritative_id",
            lambda row: list(json.loads(str(row["authoritative_ids_json"])).items()),
        ),
        (
            "exact_title",
            lambda row: [("title", row["title_normalized"])] if row["title_normalized"] else [],
        ),
    ]
    for rule, key_function in exact_rules:
        indexes: dict[tuple[str, str], list[int]] = {}
        for index, record in enumerate(records):
            for namespace, value in key_function(record):
                key = (str(namespace), str(value))
                if key in indexes:
                    for other in indexes[key]:
                        details = {
                            "identity_namespace": key[0],
                            "identity_value": key[1],
                        }
                        if not any(
                            item["other_record_id"] == records[other]["record_id"]
                            and item["rule"] == rule
                            for item in evidence[index]
                        ):
                            try_add_edge(other, index, rule, details)
                    indexes[key].append(index)
                else:
                    indexes[key] = [index]

    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if uf.find(left) == uf.find(right):
                continue
            left_title = str(records[left]["title_normalized"])
            right_title = str(records[right]["title_normalized"])
            if not left_title or not right_title:
                continue
            similarity = float(ratio(left_title, right_title))
            left_authors = set(json.loads(str(records[left]["authors_normalized_json"])))
            right_authors = set(json.loads(str(records[right]["authors_normalized_json"])))
            author_overlap = sorted(left_authors & right_authors)
            same_first_author = bool(
                records[left]["first_author_normalized"]
                and records[left]["first_author_normalized"]
                == records[right]["first_author_normalized"]
            )
            left_year, right_year = records[left]["publication_year"], records[right]["publication_year"]
            year_difference = (
                abs(int(left_year) - int(right_year))
                if left_year is not None and right_year is not None
                else None
            )
            left_prefix = str(records[left]["doi"]).split("/", 1)[0] if records[left]["doi"] else ""
            right_prefix = str(records[right]["doi"]).split("/", 1)[0] if records[right]["doi"] else ""
            doi_prefix_match = bool(left_prefix and left_prefix == right_prefix)
            subtitle_left = _distinctive_subtitle(str(records[left]["title"]))
            subtitle_right = _distinctive_subtitle(str(records[right]["title"]))
            distinctive_subtitle_match = bool(subtitle_left and subtitle_left == subtitle_right)
            identifier_support = bool(
                doi_prefix_match
                or (
                    records[left]["arxiv_id"]
                    and records[left]["arxiv_id"] == records[right]["arxiv_id"]
                )
                or distinctive_subtitle_match
            )
            details = {
                "similarity": similarity,
                "same_first_author": same_first_author,
                "matching_authors": author_overlap,
                "year_difference": year_difference,
                "doi_prefix_match": doi_prefix_match,
                "distinctive_subtitle_match": distinctive_subtitle_match,
            }
            if similarity >= 95 and same_first_author and year_difference is not None and year_difference <= 1:
                try_add_edge(left, right, "fuzzy_title_95", details)
            elif similarity >= 92 and len(author_overlap) >= 2 and identifier_support:
                try_add_edge(left, right, "fuzzy_title_92", details)
            elif similarity >= 85:
                manual_left = {"other_record_id": records[right]["record_id"], "rule": "manual_adjudication_candidate", **details}
                manual_right = {"other_record_id": records[left]["record_id"], "rule": "manual_adjudication_candidate", **details}
                evidence[left].append(manual_left)
                evidence[right].append(manual_right)

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        groups[uf.find(index)].append(index)

    works: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    for members in sorted(groups.values(), key=lambda values: min(values)):
        preferred = max(members, key=lambda index: _manifestation_rank(records[index]))
        member_ids = sorted(str(records[index]["record_id"]) for index in members)
        work_digest = hashlib.sha256("\n".join(member_ids).encode()).hexdigest()[:16].upper()
        work_id = f"WORK-{work_digest}"
        rationale = _manifestation_rationale(records[preferred])
        source_groups = sorted({group for index in members for group in _source_groups(records[index])})
        works.append(
            {
                "work_id": work_id,
                "preferred_record_id": records[preferred]["record_id"],
                "preferred_manifestation_rationale": rationale,
                "source_record_count": len(members),
                "source_record_ids_json": _json(member_ids),
                "source_group_ids_json": _json(source_groups),
                "title": records[preferred]["title"],
                "title_normalized": records[preferred]["title_normalized"],
                "authors": records[preferred]["authors"],
                "publication_year": records[preferred]["publication_year"],
                "doi": records[preferred]["doi"],
                "arxiv_id": records[preferred]["arxiv_id"],
            }
        )
        for index in members:
            record_evidence = sorted(
                evidence[index],
                key=lambda item: (
                    _RULE_ORDER.get(str(item["rule"]), 99),
                    str(item["other_record_id"]),
                ),
            )
            merge_evidence = [item for item in record_evidence if item["rule"] in _RULE_ORDER]
            if index == preferred:
                rule = "preferred_manifestation" if len(members) > 1 else "unique"
                confidence = 1.0
            elif merge_evidence:
                rule = str(merge_evidence[0]["rule"])
                confidence = max(
                    _RULE_CONFIDENCE[rule],
                    float(merge_evidence[0].get("similarity", 0.0)) / 100.0,
                )
            else:
                rule = "grouped_transitively"
                confidence = 0.92
            similarities = [float(item["similarity"]) for item in record_evidence if "similarity" in item]
            lineage.append(
                {
                    "work_id": work_id,
                    "record_id": records[index]["record_id"],
                    "preferred_record_id": records[preferred]["record_id"],
                    "is_preferred_manifestation": index == preferred,
                    "dedup_rule": rule,
                    "dedup_confidence": confidence,
                    "candidate_similarity": max(similarities) if similarities else None,
                    "dedup_evidence_json": _json(record_evidence),
                    "preferred_manifestation_rationale": rationale,
                    "source_group_ids_json": _json(_source_groups(records[index])),
                }
            )
    return works, lineage


def _matched(patterns: Iterable[object], text: str) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        expression = str(pattern)
        if re.search(expression, text, re.IGNORECASE):
            matches.append(expression)
    return matches


def classify_record(record: dict[str, object], config: dict[str, object]) -> dict[str, object]:
    combined = normalize_title(f"{record['title']}\n{record['abstract']}\n{record['keywords']}")
    term_keys = (
        "fpga_terms",
        "lm_terms",
        "compiler_terms",
        "component_terms",
        "end_to_end_terms",
        "negative_terms",
    )
    matches = {
        key.removesuffix("_terms"): _matched(config.get(key, []), combined)
        for key in term_keys
    }
    direct_lane = bool(matches["fpga"] and matches["lm"])
    hardware_match = bool(re.search(r"\b(?:rtl|hardware|verilog|systemverilog|vhdl)\b", combined))
    compiler_lane = bool(matches["compiler"] and (matches["fpga"] or hardware_match))
    component_lane = bool(matches["fpga"] and matches["component"])
    if direct_lane and matches["end_to_end"]:
        auto_level = "A"
    elif direct_lane:
        auto_level = "B"
    elif compiler_lane:
        auto_level = "C"
    elif component_lane:
        auto_level = "D"
    else:
        auto_level = "X"

    if re.search(r"\b(?:mlir|circt|torch mlir)\b", combined):
        route = "MLIR_CIRCT"
    elif re.search(r"high level synthesis|\bhls\b", combined):
        route = "HLS"
    elif re.search(r"\bdataflow\b", combined):
        route = "DATAFLOW"
    elif re.search(r"\boverlay\b|instruction set", combined):
        route = "OVERLAY"
    elif re.search(r"\b(?:cpu fpga|host fpga|offload)\b", combined):
        route = "CPU_FPGA_FALLBACK"
    elif re.search(r"\b(?:rtl|verilog|systemverilog|vhdl|generator|parameterized)\b", combined):
        route = "PARAMETERIZED_RTL"
    else:
        route = ""

    lm_score_terms = [
        term
        for term in matches["lm"]
        if any(
            marker in term.lower()
            for marker in ("large language model", "llm", "gpt", "causal language model")
        )
    ]
    transformer_attention_terms = [
        term
        for term in matches["lm"]
        if any(marker in term.lower() for marker in ("transformer", "attention", "bert"))
    ]
    unrelated_terms = [
        term
        for term in matches["negative"]
        if "cryptograph" in term.lower() or "post[- ]quantum" in term.lower()
    ]
    llm_for_eda_terms = [
        term for term in matches["negative"] if term not in unrelated_terms
    ]
    training_expression = r"\btraining(?: only)?\b|training-only"
    training_terms = (
        [training_expression]
        if re.search(training_expression, combined) and not re.search(r"\binference\b", combined)
        else []
    )
    identifier_terms = []
    if record["doi"]:
        identifier_terms.append(f"doi:{record['doi']}")
    if record["arxiv_id"]:
        identifier_terms.append(f"arxiv:{record['arxiv_id']}")

    score_inputs = (
        ("fpga_term", matches["fpga"], 4),
        ("llm_or_causal_lm_term", lm_score_terms, 4),
        ("transformer_or_attention_term", transformer_attention_terms, 3),
        ("compiler_or_generator_term", matches["compiler"], 3),
        ("end_to_end_term", matches["end_to_end"], 2),
        ("component_term", matches["component"], 2),
        ("public_code_url", [str(record["repo_url"])] if record["repo_url"] else [], 2),
        ("doi_or_arxiv_identifier", identifier_terms, 1),
        ("llm_for_eda_pattern", llm_for_eda_terms, -5),
        ("unrelated_workload_pattern", unrelated_terms, -4),
        ("training_only_pattern", training_terms, -3),
    )
    score_evidence = [
        {
            "category": category,
            "matched_terms": list(terms),
            "weight": weight,
            "contribution": weight,
        }
        for category, terms, weight in score_inputs
        if terms
    ]
    score = sum(int(item["contribution"]) for item in score_evidence)
    lm_or_causal = bool(lm_score_terms)
    positive_lane_count = sum((direct_lane, compiler_lane, component_lane))
    generic_only = bool(matches["fpga"] and matches["lm"] and not (
        lm_or_causal or matches["compiler"] or matches["component"] or matches["end_to_end"]
    ))
    special_review = bool(re.search(r"vision transformer|\bvit\b|encoder only|training", combined))
    manual_reasons: list[str] = []
    if int(record["abstract_length"]) < 200:
        manual_reasons.append("short_or_missing_abstract")
    if any(matches[name] for name in ("fpga", "lm", "compiler", "component", "end_to_end")) and matches["negative"]:
        manual_reasons.append("positive_and_negative_terms")
    if positive_lane_count > 1:
        manual_reasons.append("multiple_positive_lanes")
    if generic_only:
        manual_reasons.append("generic_terms_only")
    if matches["compiler"] and not matches["fpga"]:
        manual_reasons.append("non_fpga_compiler")
    if special_review:
        manual_reasons.append("vision_encoder_or_training")
    if auto_level == "X":
        manual_reasons.append("no_positive_lane")
    result = {
        "direct_lane": direct_lane,
        "compiler_lane": compiler_lane,
        "component_lane": component_lane,
        "auto_level": auto_level,
        "auto_route_family": route,
        "screen_priority_score": score,
        "score_evidence_json": _json(score_evidence),
        "needs_manual_review": bool(manual_reasons),
        "manual_review_reasons_json": _json(sorted(set(manual_reasons))),
    }
    for name in matches:
        result[f"matched_{name}_terms_json"] = _json(matches[name])
    return result


def _manual_queue_rank(row: dict[str, object]) -> int:
    level = str(row["auto_level"])
    if level == "A":
        return 1
    if level == "C":
        return 2
    reasons = set(json.loads(str(row.get("manual_review_reasons_json", "[]"))))
    if reasons & {"short_or_missing_abstract", "positive_and_negative_terms"}:
        return 3
    return {"B": 4, "D": 5, "X": 6}.get(level, 7)


def prioritize_uncertain(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for source in rows:
        row = dict(source)
        row["manual_queue_rank"] = _manual_queue_rank(row)
        ranked.append(row)
    return sorted(
        ranked,
        key=lambda row: (
            int(row["manual_queue_rank"]),
            -int(row["screen_priority_score"]),
            int(row["record_index"]),
        ),
    )


NORMALIZED_FIELDS = [
    "record_index", "record_id", "source_record_id", "catalog_key", "arxiv_version_id", "arxiv_id",
    "arxiv_version", "title", "title_normalized", "abstract", "abstract_length",
    "authors", "authors_json", "authors_normalized_json", "first_author_normalized",
    "categories_json", "primary_category", "keywords", "publication_year", "published_at",
    "updated_at", "retrieved_at", "doi", "authoritative_ids_json", "abs_url", "pdf_url",
    "source_url", "repo_url", "license_url", "journal_ref", "query_ids_json",
    "catalog_query_id", "cache_sha256", "cache_json", "raw_record_json",
]
LINEAGE_FIELDS = [
    "work_id", "record_id", "preferred_record_id", "is_preferred_manifestation",
    "dedup_rule", "dedup_confidence", "candidate_similarity", "dedup_evidence_json",
    "preferred_manifestation_rationale", "source_group_ids_json",
]
TRIAGE_FIELDS = [
    "direct_lane", "compiler_lane", "component_lane", "auto_level", "auto_route_family",
    "screen_priority_score", "score_evidence_json", "needs_manual_review", "manual_queue_rank",
    "manual_review_reasons_json",
    "matched_fpga_terms_json", "matched_lm_terms_json", "matched_compiler_terms_json",
    "matched_component_terms_json", "matched_end_to_end_terms_json", "matched_negative_terms_json",
]
MANUAL_FIELDS = [
    "manual_level", "manual_route_family", "include_final", "exclusion_code", "reviewer", "review_notes",
]
MAPPING_FIELDS = ["work_id"] + NORMALIZED_FIELDS + [field for field in LINEAGE_FIELDS if field not in {"work_id", "record_id"}] + TRIAGE_FIELDS + MANUAL_FIELDS
WORK_FIELDS = [
    "work_id", "preferred_record_id", "preferred_manifestation_rationale", "source_record_count",
    "source_record_ids_json", "source_group_ids_json", "title", "title_normalized", "authors",
    "publication_year", "doi", "arxiv_id",
]


def _pa_type(field: str) -> pa.DataType:
    if field in {"record_index", "arxiv_version", "abstract_length", "publication_year", "screen_priority_score", "manual_queue_rank"}:
        return pa.int64()
    if field in {"direct_lane", "compiler_lane", "component_lane", "needs_manual_review", "is_preferred_manifestation"}:
        return pa.bool_()
    if field in {"dedup_confidence", "candidate_similarity"}:
        return pa.float64()
    return pa.string()


PARQUET_SCHEMA = pa.schema(
    [pa.field(field, _pa_type(field), nullable=True) for field in MAPPING_FIELDS],
    metadata={b"survey_schema": b"phase1_mapping_v1"},
)


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _validate_existing_output(out: Path, catalog_hash: str, config_hash: str, count: int) -> None:
    existing_products = [out / name for name in (*OUTPUT_NAMES, "phase1_run.json") if (out / name).exists()]
    if not existing_products:
        return
    manifest_path = out / "phase1_run.json"
    if not manifest_path.is_file():
        raise ValueError("refusing to overwrite Phase-1 products without phase1_run.json provenance")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (catalog_hash, config_hash, count)
    found = (
        manifest.get("input_sha256", {}).get("catalog"),
        manifest.get("input_sha256", {}).get("config"),
        manifest.get("counts", {}).get("input_records"),
    )
    if found != expected:
        raise ValueError(
            "refusing to overwrite Phase-1 products generated from a different input hash or count"
        )


def run_phase1(
    catalog_path: Path,
    config_path: Path,
    out: Path,
    expected_records: int,
) -> dict[str, object]:
    catalog_path, config_path, out = Path(catalog_path), Path(config_path), Path(out)
    raw_bytes = catalog_path.read_bytes()
    config_bytes = config_path.read_bytes()
    catalogue = json.loads(raw_bytes)
    config = yaml.safe_load(config_bytes)
    if not isinstance(config, dict):
        raise ValueError("scope configuration must be a mapping")
    extracted = extract_records(catalogue)
    if len(extracted) != expected_records:
        raise ValueError(f"expected {expected_records} records; found {len(extracted)}")
    snapshot = config.get("snapshot")
    frozen_count = snapshot.get("expected_records") if isinstance(snapshot, dict) else None
    if frozen_count != expected_records:
        raise ValueError(
            f"expected-records {expected_records} disagrees with frozen scope count {frozen_count}"
        )
    catalog_hash = hashlib.sha256(raw_bytes).hexdigest()
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    _validate_existing_output(out, catalog_hash, config_hash, len(extracted))

    query_id = _text(catalogue.get("query_id")) if isinstance(catalogue, dict) else ""
    normalized: list[dict[str, object]] = []
    for index, (key, source) in enumerate(extracted):
        row = canonicalize_record(key, source)
        row["record_index"] = index
        row["catalog_query_id"] = query_id
        normalized.append(row)
    if len({str(row["record_id"]) for row in normalized}) != len(normalized):
        raise ValueError("stable record_id collision detected")

    works, lineage = deduplicate(normalized)
    lineage_by_record = {str(row["record_id"]): row for row in lineage}
    mapping: list[dict[str, object]] = []
    for record in normalized:
        row = {
            **record,
            **lineage_by_record[str(record["record_id"])],
            **classify_record(record, config),
            **{field: "" for field in MANUAL_FIELDS},
        }
        evidence = json.loads(str(row["dedup_evidence_json"]))
        if any(
            item.get("rule") in {"manual_adjudication_candidate", "contradictory_identity"}
            for item in evidence
        ):
            reasons = json.loads(str(row["manual_review_reasons_json"]))
            if any(item.get("rule") == "contradictory_identity" for item in evidence):
                reasons.append("contradictory_exact_identity")
            else:
                reasons.append("fuzzy_identity_candidate")
            row["manual_review_reasons_json"] = _json(sorted(set(reasons)))
            row["needs_manual_review"] = True
        mapping.append(row)
    for row in mapping:
        row["manual_queue_rank"] = _manual_queue_rank(row)
    uncertain = prioritize_uncertain([row for row in mapping if row["needs_manual_review"]])
    duplicate_record_count = sum(1 for row in works if int(row["source_record_count"]) > 1)
    duplicate_manifestations = sum(int(row["source_record_count"]) - 1 for row in works)
    level_counts = {level: sum(row["auto_level"] == level for row in mapping) for level in ("A", "B", "C", "D", "X")}
    route_values = list(config.get("route_families", []))
    route_counts = {str(route): sum(row["auto_route_family"] == route for row in mapping) for route in route_values}
    route_counts["UNRESOLVED"] = sum(not row["auto_route_family"] for row in mapping)
    counts: dict[str, object] = {
        "input_records": len(normalized),
        "candidate_unique_works": len(works),
        "duplicate_work_groups": duplicate_record_count,
        "duplicate_manifestations": duplicate_manifestations,
        "manual_review_queue": len(uncertain),
        "auto_levels": level_counts,
        "auto_route_families": route_counts,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{out.name}.phase1-", dir=out.parent) as directory:
        staging = Path(directory)
        _write_csv(staging / "records_normalized.csv", normalized, NORMALIZED_FIELDS)
        _write_csv(staging / "duplicate_groups.csv", lineage, LINEAGE_FIELDS)
        _write_csv(staging / "works_deduplicated.csv", works, WORK_FIELDS)
        _write_csv(staging / "phase1_mapping.csv", mapping, MAPPING_FIELDS)
        table = pa.Table.from_pylist(mapping, schema=PARQUET_SCHEMA)
        pq.write_table(
            table,
            staging / "phase1_mapping.parquet",
            compression="NONE",
            use_dictionary=False,
            write_statistics=True,
            data_page_version="1.0",
            version="2.6",
        )
        _write_csv(staging / "phase1_uncertain.csv", uncertain, MAPPING_FIELDS)
        (staging / "flow_counts.json").write_text(
            json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        output_hashes = {name: _sha256(staging / name) for name in OUTPUT_NAMES}
        summary_text = json.dumps(counts, indent=2, sort_keys=True) + "\n"
        run_manifest = {
            "schema_version": 1,
            "command": [
                "survey-phase1",
                "--catalog", _stable_path(catalog_path),
                "--config", _stable_path(config_path),
                "--out", "<OUT_DIR>",
                "--expected-records", str(expected_records),
            ],
            "input_sha256": {"catalog": catalog_hash, "config": config_hash},
            "output_sha256": output_hashes,
            "counts": counts,
            "stdout": summary_text,
            "stderr": "",
        }
        (staging / "phase1_run.json").write_text(
            json.dumps(run_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        out.mkdir(parents=True, exist_ok=True)
        for name in (*OUTPUT_NAMES, "phase1_run.json"):
            os.replace(staging / name, out / name)
    print(summary_text, end="")
    return run_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, required=True)
    args = parser.parse_args()
    run_phase1(args.catalog, args.config, args.out, args.expected_records)


if __name__ == "__main__":
    main()
