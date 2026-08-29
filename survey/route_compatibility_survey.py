#!/usr/bin/env python3
"""Generate a route-compatibility survey over the arXiv paper catalog.

Unlike the previous metadata-only pass, this version classifies papers from
full-text PDF content extracted via `pdftotext`, with a fallback to metadata
fields if PDF text cannot be loaded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import shlex
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


RoutePattern = Tuple[str, re.Pattern]


ROUTE_TERMS: Dict[str, Tuple[str, ...]] = {
    "mlir_circt": (
        "mlir",
        "circt",
        "torch-mlir",
        "tosa",
        "linalg",
        "handshake",
        "calyx",
        "affine",
        "tensor",
        "llvm",
        "iree",
    ),
    "hls": (
        "high-level synthesis",
        "high level synthesis",
        " hls",
        "vivado hls",
        "vitis hls",
        "hls4ml",
        "llvm",
        "chisel",
    ),
    "overlay": (
        "overlay",
        "reconfigurable overlay",
        "overlay processor",
        "instruction set",
        "microarchitecture",
        "micro architecture",
        "domain-specific instruction",
        "programmable overlay",
    ),
    "param_rtl": (
        "systemverilog",
        "system verilog",
        "verilog",
        "vhdl",
        " rtl",
        "synthesizable",
        "fpga ip",
        "hardware description",
        "register-transfer",
    ),
    "dataflow": (
        "dataflow",
        "streaming",
        "pipeline",
        "systolic",
        "operator fusion",
        "spatial accelerator",
        "memory hierarchy",
        "double buffering",
        "tiling",
    ),
    "cpu_fpga_fallback": (
        " cpu",
        "processing system",
        "offload",
        "hybrid",
        "host",
        "co-design",
        "ps ",
        "cpu-gpu",
        "cpu-fpga",
        "heterogeneous",
        "edge-server",
    ),
}

LLM_TERMS = (
    " llm",
    "large language model",
    "transformer",
    "attention",
    "gpt",
    "kv cache",
    "token",
    "autoregressive",
    "prefill",
    "decode",
    "inference",
)

DEFAULT_REUSE_SEARCH_COLUMNS = (
    "title",
    "llm_relevance_hits",
    "mlir_circt_hits",
    "hls_hits",
    "overlay_hits",
    "param_rtl_hits",
    "dataflow_hits",
    "cpu_fpga_fallback_hits",
    "route_notes",
    "llm_relevance_score",
)

MIN_REUSE_SEARCH_SCORE = 1e-12



SECTION_BOUNDARY_PATTERNS = (
    re.compile(r"\n\s*references?\s*\n", re.IGNORECASE),
    re.compile(r"\n\s*acknowledg?ements?\s*\n", re.IGNORECASE),
    re.compile(r"\n\s*acknowledgment\s*\n", re.IGNORECASE),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compile_term(term: str) -> re.Pattern:
    pattern = re.escape(term).replace(r"\ ", r"\s+")
    return re.compile(pattern, re.IGNORECASE)


def compile_term_set(terms: Iterable[str]) -> List[Tuple[str, re.Pattern]]:
    return [(t, compile_term(t)) for t in terms]


def compile_patterns() -> Dict[str, List[Tuple[str, re.Pattern]]]:
    return {route: compile_term_set(terms) for route, terms in ROUTE_TERMS.items()}


def compile_llm_patterns() -> List[Tuple[str, re.Pattern]]:
    return [(t, compile_term(t)) for t in LLM_TERMS]


def find_matches(text: str, terms: List[Tuple[str, re.Pattern]]) -> List[str]:
    return [raw for raw, pattern in terms if pattern.search(text)]


def route_level(score: float) -> str:
    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def top_route_candidates(route_levels: Dict[str, str], route_scores: Dict[str, float]) -> List[str]:
    ranked = [
        (route, route_levels[route], route_scores[route]) for route in route_scores
        if route_levels[route] != "none"
    ]
    ranked.sort(key=lambda x: (x[2], x[0]), reverse=True)
    return [f"{route}:{level}" for route, level, _ in ranked[:3]]


def truncate(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def strip_references(raw_text: str) -> str:
    cut = len(raw_text)
    for pattern in SECTION_BOUNDARY_PATTERNS:
        match = pattern.search(raw_text)
        if match:
            cut = min(cut, match.start())
    return raw_text[:cut]


def route_matches_from_pages(
    pages: List[str],
    terms: List[Tuple[str, re.Pattern]],
) -> Tuple[List[str], Dict[str, List[int]]]:
    hit_terms: List[str] = []
    hit_pages: Dict[str, List[int]] = {}
    seen_term = set()
    for page_no, page in enumerate(pages, start=1):
        normalized = " ".join(page.split())
        for raw, pattern in terms:
            if pattern.search(normalized):
                if raw not in seen_term:
                    hit_terms.append(raw)
                    seen_term.add(raw)
                hit_pages.setdefault(raw, [])
                if page_no not in hit_pages[raw]:
                    hit_pages[raw].append(page_no)
    return hit_terms, hit_pages


def parse_label_filter(raw: str) -> set[str]:
    raw = (raw or "").strip().lower()
    if raw in {"", "all"}:
        return set()
    values = {v.strip() for v in raw.split(",") if v.strip()}
    allowed = {"high", "medium", "low", "none"}
    if not values.issubset(allowed):
        bad = values.difference(allowed)
        raise ValueError(f"invalid reuse labels in --search-reusable-filter: {sorted(bad)}")
    return values


def parse_keyword_terms(raw_query: str) -> List[str]:
    raw_query = raw_query.strip()
    if not raw_query:
        return []
    terms: List[str] = []
    try:
        terms = [t for t in shlex.split(raw_query) if t.strip()]
    except ValueError:
        terms = [raw_query]
    if len(terms) == 1 and "," in terms[0]:
        terms = [t.strip() for t in terms[0].split(",")]
    return [t.lower() for t in terms if t.strip()]


def row_keyword_haystack(row: Dict[str, str], fields: Tuple[str, ...]) -> str:
    parts: List[str] = []
    for field in fields:
        value = row.get(field, "")
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


def filter_rows_by_keywords(
    rows: List[Dict[str, str]],
    keywords: List[str],
    keyword_fields: Tuple[str, ...],
    mode: str,
    min_matches: int,
) -> List[Dict[str, str]]:
    if not keywords:
        return list(rows)
    mode = mode.lower()
    selected: List[Dict[str, str]] = []
    required = len(keywords) if mode == "all" else min_matches
    for row in rows:
        haystack = row_keyword_haystack(row, keyword_fields)
        matches = sum(1 for kw in keywords if kw.lower() in haystack)
        if mode == "all":
            if matches >= required:
                selected.append(row)
            continue
        if matches >= required:
            selected.append(row)
    return selected


def tokenize_for_relevance(text: str) -> List[str]:
    return re.findall(r"[a-z0-9][a-z0-9._/-]*", text.lower())


def build_tfidf(corpus: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    document_tokens = [tokenize_for_relevance(doc) for doc in corpus]
    docs = len(document_tokens)
    if docs == 0:
        return [], {}

    df: Dict[str, int] = defaultdict(int)
    tf_documents: List[Dict[str, int]] = []
    for tokens in document_tokens:
        counts: Dict[str, int] = defaultdict(int)
        for token in tokens:
            counts[token] += 1
        tf_documents.append(counts)
        for token in set(tokens):
            df[token] += 1

    idf: Dict[str, float] = {}
    for token, freq in df.items():
        idf[token] = math.log((1 + docs) / (1 + freq)) + 1.0

    vectors: List[Dict[str, float]] = []
    for counts in tf_documents:
        total = sum(counts.values()) or 1
        vector: Dict[str, float] = {}
        norm = 0.0
        for token, freq in counts.items():
            weight = (freq / total) * idf[token]
            vector[token] = weight
            norm += weight * weight
        # Keep a stable vector for cosine operations.
        vector["_norm"] = math.sqrt(norm)
        vectors.append(vector)
    return vectors, idf


def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float], norm1: float, norm2: float) -> float:
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    total = 0.0
    for token, w1 in v1.items():
        if token == "_norm":
            continue
        w2 = v2.get(token)
        if w2 is not None:
            total += w1 * w2
    return total / (norm1 * norm2)


def rank_by_tfidf(rows: List[Dict[str, str]], query: str, fields: Tuple[str, ...]) -> List[Tuple[Dict[str, str], float]]:
    if not rows:
        return []
    docs = [row_keyword_haystack(row, fields) for row in rows]
    vectors, idf = build_tfidf(docs)
    if not vectors:
        return [(row, 0.0) for row in rows]
    query_tokens = tokenize_for_relevance(query.lower())
    if not query_tokens:
        return [(row, 0.0) for row in rows]

    q_counts: Dict[str, int] = defaultdict(int)
    for token in query_tokens:
        q_counts[token] += 1
    total = sum(q_counts.values()) or 1

    qvec: Dict[str, float] = {}
    qnorm = 0.0
    for token, freq in q_counts.items():
        weight = (freq / total) * idf.get(token, math.log((1 + len(rows)) / 1) + 1.0)
        qvec[token] = weight
        qnorm += weight * weight
    qnorm = math.sqrt(qnorm)

    scored: List[Tuple[Dict[str, str], float]] = []
    for row, vector in zip(rows, vectors):
        score = cosine_similarity(qvec, vector, qnorm, vector.get("_norm", 0.0))
        scored.append((row, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def rank_by_semantic_transformer(
    rows: List[Dict[str, str]],
    query: str,
    fields: Tuple[str, ...],
    top_k: int,
) -> List[Tuple[Dict[str, str], float]]:
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "semantic search requested, but sentence-transformers is unavailable in this environment"
        ) from exc

    docs = [row_keyword_haystack(row, fields) for row in rows]
    model = SentenceTransformer("all-MiniLM-L6-v2")
    doc_emb = model.encode(docs, normalize_embeddings=True, show_progress_bar=False)
    q_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]

    scores: List[Tuple[Dict[str, str], float]] = []
    for row, d in zip(rows, doc_emb):
        score = float(np.dot(d, q_emb))
        scores.append((row, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores[:top_k]


def extract_pdf_text(
    papers_root: Path,
    paper_id: str,
    paper: Dict[str, object],
    pdftotext: str,
) -> Tuple[str, str, int, str, bool]:
    cache = paper.get("cache")
    filename = None
    if isinstance(cache, dict):
        candidate = cache.get("filename")
        if isinstance(candidate, str):
            filename = candidate
    if filename is None:
        filename = f"{paper_id}.pdf"

    pdf_path = papers_root / filename
    if not pdf_path.exists():
        return "", str(pdf_path), 0, "", False
    if not pdftotext:
        return "", str(pdf_path), 0, "", False

    cmd = [pdftotext, "-enc", "UTF-8", "-layout", str(pdf_path), "-"]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return "", str(pdf_path), 0, f"pdftotext_failed:{stderr[:200]}", False
    except FileNotFoundError:
        return "", str(pdf_path), 0, "pdftotext_missing", False

    raw = proc.stdout
    pages = raw.split("\x0c")
    page_count = len([p for p in pages if p.strip()])
    digest = sha256_file(pdf_path)
    return raw, str(pdf_path), page_count, digest, True


def reusable_score(llm_relevance: int, route_scores: Dict[str, float]) -> str:
    best_route = max(route_scores.values()) if route_scores else 0
    if best_route == 0:
        return "none"
    if llm_relevance >= 1 and best_route >= 3:
        return "high"
    if llm_relevance >= 1 and best_route >= 2:
        return "medium"
    if llm_relevance >= 1 and best_route >= 1:
        return "low"
    if best_route >= 4:
        return "low"
    return "low" if best_route >= 1 else "none"


def normalize_route_rows(
    records: Iterable[Tuple[str, Dict[str, object]]],
    papers_root: Path,
    pdftotext: str,
) -> List[Dict[str, str]]:
    compiled = compile_patterns()
    llm_compiled = compile_llm_patterns()
    rows: List[Dict[str, str]] = []

    for paper_id, paper in records:
        title = str(paper.get("title", "") or "")
        abstract = str(paper.get("abstract", "") or "")
        categories = paper.get("categories", [])
        category_text = " ".join(categories) if isinstance(categories, list) else str(categories)
        full_metadata = " ".join([title, abstract, category_text])

        pdf_text, pdf_path, pdf_pages, pdf_sha256, pdf_ok = extract_pdf_text(
            papers_root,
            paper_id,
            paper,
            pdftotext,
        )
        source = "full_paper"
        if not pdf_text:
            source = "metadata_fallback"
            scanned_text = full_metadata
            pages = [" ".join(scanned_text.split())]
        else:
            scanned_text = strip_references(pdf_text)
            pages = scanned_text.split("\x0c")

        # Keep title and abstract in scope for stable matching when PDF text is noisy.
        scanned_with_metadata = f"{full_metadata} {scanned_text}".lower()

        llm_hits = find_matches(scanned_with_metadata, llm_compiled)
        llm_relevance = len(llm_hits)
        llm_relevance_score = llm_relevance / len(LLM_TERMS)

        route_scores: Dict[str, float] = {}
        route_levels: Dict[str, str] = {}
        route_hits: Dict[str, str] = {}
        route_pages: Dict[str, str] = {}
        route_evidence: Dict[str, str] = {}

        for route, pats in compiled.items():
            hits, hit_pages = route_matches_from_pages(pages, pats)
            # Metadata terms should still influence the route score when PDF extraction
            # fails or is incomplete.
            meta_hits = find_matches(full_metadata.lower(), pats)
            for term in meta_hits:
                if term not in hits:
                    hits.append(term)
                hit_pages.setdefault(term, [])

            hits = sorted(set(hits), key=lambda t: hits.index(t) if t in hits else 0)
            score = float(len(hits))
            route_scores[route] = score
            route_levels[route] = route_level(score)
            route_hits[route] = ";".join(hits)

            evidence_parts = []
            for term in hits:
                pages_for_term = sorted(set(hit_pages.get(term, [])))
                if pages_for_term:
                    evidence_parts.append(f"{term}@p{','.join(str(p) for p in pages_for_term)}")
            route_pages[route] = ";".join(evidence_parts)
            page_hits_text = ";".join(
                truncate(p.replace("\x0c", " "), 80) for p in evidence_parts[:5]
            )
            route_evidence[route] = page_hits_text

        candidate_list = top_route_candidates(route_levels, route_scores)
        reusable = reusable_score(llm_relevance, route_scores)

        published = str(paper.get("published_at", "") or "")
        year = published[:4] if len(published) >= 4 and published[:4].isdigit() else ""
        primary_cat = str(paper.get("primary_category", "") or "")

        top_route = candidate_list[0] if candidate_list else "none:none"
        top_route_key = top_route.split(":")[0] if top_route != "none:none" else ""
        top_evidence = route_pages.get(top_route_key, "")

        note = (
            f"{top_route} via {top_evidence}"
            if candidate_list
            else "no explicit route hints found in full-paper scan"
        )

        rows.append(
            {
                "arxiv_id": paper_id,
                "base_arxiv_id": paper_id.split("v")[0],
                "title": title,
                "published_year": year,
                "primary_category": primary_cat,
                "all_categories": "|".join(categories) if isinstance(categories, list) else "",
                "pdf_path": pdf_path,
                "pdf_sha256": pdf_sha256,
                "pdf_pages": str(pdf_pages),
                "pdf_scanned": "yes" if pdf_ok else "no",
                "pdf_status": "ok" if pdf_ok else "unavailable_or_failed",
                "survey_scope": source,
                "llm_relevance_hits": ";".join(llm_hits),
                "llm_relevance_score": f"{llm_relevance_score:.2f}",
                "mlir_circt_level": route_levels["mlir_circt"],
                "mlir_circt_hits": route_hits["mlir_circt"],
                "mlir_circt_pages": route_pages["mlir_circt"],
                "mlir_circt_evidence": route_evidence["mlir_circt"],
                "hls_level": route_levels["hls"],
                "hls_hits": route_hits["hls"],
                "hls_pages": route_pages["hls"],
                "hls_evidence": route_evidence["hls"],
                "overlay_level": route_levels["overlay"],
                "overlay_hits": route_hits["overlay"],
                "overlay_pages": route_pages["overlay"],
                "overlay_evidence": route_evidence["overlay"],
                "param_rtl_level": route_levels["param_rtl"],
                "param_rtl_hits": route_hits["param_rtl"],
                "param_rtl_pages": route_pages["param_rtl"],
                "param_rtl_evidence": route_evidence["param_rtl"],
                "dataflow_level": route_levels["dataflow"],
                "dataflow_hits": route_hits["dataflow"],
                "dataflow_pages": route_pages["dataflow"],
                "dataflow_evidence": route_evidence["dataflow"],
                "cpu_fpga_fallback_level": route_levels["cpu_fpga_fallback"],
                "cpu_fpga_fallback_hits": route_hits["cpu_fpga_fallback"],
                "cpu_fpga_fallback_pages": route_pages["cpu_fpga_fallback"],
                "cpu_fpga_fallback_evidence": route_evidence["cpu_fpga_fallback"],
                "realistically_reusable": reusable,
                "top_route_candidates": ";".join(candidate_list),
                "route_notes": note,
            }
        )

    return rows


def load_catalogue(path: Path) -> List[Tuple[str, Dict[str, object]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    papers = payload.get("papers", {})
    if not isinstance(papers, dict):
        raise ValueError("Expected catalog.json with top-level \"papers\" dictionary")
    return list(papers.items())


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    if not rows:
        raise RuntimeError("No rows generated")
    headers = list(rows[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def load_rows_from_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(row) for row in reader]
    if not rows:
        raise RuntimeError(f"precomputed survey CSV is empty: {path}")
    return rows


def write_summary(rows: List[Dict[str, str]], out_path: Path) -> None:
    route_stats = defaultdict(int)
    reusable_stats = defaultdict(int)
    by_scope = defaultdict(int)
    by_pdf_status = defaultdict(int)

    for row in rows:
        reusable_stats[row["realistically_reusable"]] += 1
        by_scope[row["survey_scope"]] += 1
        by_pdf_status[row["pdf_status"]] += 1
        if row["mlir_circt_level"] in {"high", "medium"}:
            route_stats["mlir_circt"] += 1
        if row["hls_level"] in {"high", "medium"}:
            route_stats["hls"] += 1
        if row["overlay_level"] in {"high", "medium"}:
            route_stats["overlay"] += 1
        if row["param_rtl_level"] in {"high", "medium"}:
            route_stats["param_rtl"] += 1
        if row["dataflow_level"] in {"high", "medium"}:
            route_stats["dataflow"] += 1
        if row["cpu_fpga_fallback_level"] in {"high", "medium"}:
            route_stats["cpu_fpga_fallback"] += 1

    top_candidates = [
        row for row in rows
        if row["realistically_reusable"] in {"high", "medium"}
    ]
    top_candidates.sort(
        key=lambda r: (
            0 if r["realistically_reusable"] == "high" else 1,
            r["top_route_candidates"],
            r["arxiv_id"],
        )
    )

    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Route-compatibility Survey Summary\n\n")
        f.write(f"- Generated UTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"- Total records: {len(rows)}\n\n")
        f.write("## Scope & input status\n\n")
        f.write("| Scope | Count |\n|---|---:|\n")
        for scope in sorted(by_scope):
            f.write(f"| {scope} | {by_scope[scope]} |\n")
        f.write("\n| PDF status | Count |\n|---|---:|\n")
        for status in sorted(by_pdf_status):
            f.write(f"| {status} | {by_pdf_status[status]} |\n")

        f.write("\n## Route hints (high/medium classification)\n\n")
        f.write("| Route | Count |\n|---|---:|\n")
        for route in ["mlir_circt", "hls", "overlay", "param_rtl", "dataflow", "cpu_fpga_fallback"]:
            f.write(f"| {route} | {route_stats.get(route, 0)} |\n")
        f.write("\n## Overall reusability labels\n\n")
        f.write("| Label | Count |\n|---|---:|\n")
        for label in ["high", "medium", "low", "none"]:
            f.write(f"| {label} | {reusable_stats.get(label, 0)} |\n")
        f.write("\n## High/medium reusable candidate shortlist\n\n")
        f.write("| arxiv_id | title | reusable | routes | llm_relevance_hits |\n")
        f.write("|---|---|---|---|---|\n")
        for row in top_candidates:
            f.write(
                f"| {row['arxiv_id']} | {row['title']} | {row['realistically_reusable']} | "
                f"{row['top_route_candidates']} | {row['llm_relevance_hits']} |\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("LLM-inference-on-FPGA-papers/data/catalog.json"),
        help="Path to LLM-inference-on-FPGA-papers catalog.json",
    )
    parser.add_argument(
        "--papers-root",
        type=Path,
        default=Path("LLM-inference-on-FPGA-papers/papers"),
        help="Root directory containing cached PDFs",
    )
    parser.add_argument(
        "--pdftotext",
        type=Path,
        default=Path("/usr/bin/pdftotext"),
        help="pdftotext executable path",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("survey/route-compatibility-survey.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("survey/route-compatibility-survey.md"),
        help="Output summary path",
    )
    parser.add_argument(
        "--reusable-out",
        type=Path,
        default=Path("survey/route-compatibility-reusable-candidates.csv"),
        help="Optional reusable-candidate CSV output path",
    )
    parser.add_argument(
        "--precomputed-csv",
        type=Path,
        help="Reuse an existing route-compatibility-survey CSV instead of re-running PDF scans",
    )
    parser.add_argument(
        "--search-out",
        type=Path,
        default=Path("survey/route-compatibility-search-results.csv"),
        help="Optional reusable-search CSV output path",
    )
    parser.add_argument(
        "--query-keywords",
        help="Space- or comma-separated keyword search terms",
    )
    parser.add_argument(
        "--keyword-match-mode",
        choices=["any", "all"],
        default="any",
        help="Keyword filter mode: any (default) or all",
    )
    parser.add_argument(
        "--keyword-min-matches",
        type=int,
        default=1,
        help="Minimum keyword matches in --keyword-match-mode any",
    )
    parser.add_argument(
        "--search-columns",
        default=",".join(DEFAULT_REUSE_SEARCH_COLUMNS),
        help="Comma-separated fields used for keyword/semantic search",
    )
    parser.add_argument(
        "--query-semantic",
        help="Semantic query text for ranking papers (uses sentence-transformers when available, falls back to tf-idf)",
    )
    parser.add_argument(
        "--semantic-top-k",
        type=int,
        default=120,
        help="How many semantic matches to keep",
    )
    parser.add_argument(
        "--search-reusable-filter",
        default="high,medium",
        help="Comma-separated reuse labels to keep for search output; use 'all' for no filter",
    )
    parser.add_argument(
        "--search-no-reusable-filter",
        action="store_true",
        help="Disable search filter (run search on all rows)",
    )
    parser.add_argument(
        "--fallback-keyword-only",
        action="store_true",
        help="When semantic query is requested but semantic libs are unavailable, do keyword-only matching with the same terms",
    )
    args = parser.parse_args()

    pdftotext = ""
    if args.precomputed_csv:
        rows = load_rows_from_csv(args.precomputed_csv)
    else:
        pdftotext = str(args.pdftotext) if args.pdftotext.exists() else ""
        records = load_catalogue(args.catalog)
        rows = normalize_route_rows(records, args.papers_root, pdftotext)

    write_csv(rows, args.csv)
    write_summary(rows, args.summary)
    reusable_rows = [r for r in rows if r["realistically_reusable"] in {"high", "medium"}]
    if args.reusable_out:
        fieldnames = [
            "arxiv_id",
            "base_arxiv_id",
            "title",
            "realistically_reusable",
            "top_route_candidates",
            "llm_relevance_hits",
            "llm_relevance_score",
            "mlir_circt_level",
            "hls_level",
            "overlay_level",
            "param_rtl_level",
            "dataflow_level",
            "cpu_fpga_fallback_level",
            "pdf_status",
            "pdf_path",
            "pdf_pages",
        ]
        args.reusable_out.parent.mkdir(parents=True, exist_ok=True)
        with args.reusable_out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in reusable_rows:
                w.writerow({k: row[k] for k in fieldnames})
        print(f"wrote reusable candidates to {args.reusable_out}")

    # Optional reuse discovery pass: filter + rank rows with keywords and/or semantic query.
    if args.query_keywords or args.query_semantic:
        search_columns = tuple(col.strip() for col in args.search_columns.split(",") if col.strip())
        filtered = list(rows)
        if not args.search_no_reusable_filter:
            try:
                allowed_labels = parse_label_filter(args.search_reusable_filter)
            except ValueError as exc:
                raise SystemExit(str(exc))
            if allowed_labels:
                filtered = [r for r in filtered if r["realistically_reusable"] in allowed_labels]

        keyword_terms = parse_keyword_terms(args.query_keywords or "")
        if keyword_terms:
            filtered = filter_rows_by_keywords(
                filtered,
                keyword_terms,
                search_columns,
                args.keyword_match_mode,
                args.keyword_min_matches,
            )

        semantic_rows: List[Tuple[Dict[str, str], float]]
        if args.query_semantic:
            try:
                semantic_rows = rank_by_semantic_transformer(
                    filtered,
                    args.query_semantic,
                    search_columns,
                    args.semantic_top_k,
                )
            except RuntimeError:
                if args.fallback_keyword_only:
                    keyword_terms = parse_keyword_terms(args.query_semantic)
                    if keyword_terms:
                        baseline = filter_rows_by_keywords(
                            filtered,
                            keyword_terms,
                            search_columns,
                            "any",
                            1,
                        )
                        semantic_rows = [(row, 1.0) for row in baseline[: args.semantic_top_k]]
                    else:
                        semantic_rows = [(row, 0.0) for row in filtered]
                else:
                    semantic_rows = rank_by_tfidf(
                        filtered,
                        args.query_semantic,
                        search_columns,
                    )
        else:
            semantic_rows = [(row, 1.0) for row in filtered]

        # Always ensure deterministic output ordering by score first.
        semantic_rows.sort(key=lambda item: item[1], reverse=True)

        # If semantic query wasn't provided, keep full rows in the same order.
        if not args.query_semantic and keyword_terms:
            pass

        # Optional score cutoff for zero matches can be raised from the caller.
        semantic_rows = [(r, s) for r, s in semantic_rows if s >= MIN_REUSE_SEARCH_SCORE]
        # Preserve top-k semantics for semantic branch.
        if args.query_semantic:
            semantic_rows = semantic_rows[: args.semantic_top_k]

        # Add score to rows for a stable export format.
        search_out_rows = []
        for row, score in semantic_rows:
            copy_row = dict(row)
            copy_row["search_score"] = f"{score:.6f}"
            search_out_rows.append(copy_row)

        if args.search_out:
            search_out_fieldnames = list(search_out_rows[0].keys()) if search_out_rows else [
                "arxiv_id",
                "title",
                "search_score",
            ]
            args.search_out.parent.mkdir(parents=True, exist_ok=True)
            with args.search_out.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=search_out_fieldnames)
                w.writeheader()
                for row in search_out_rows:
                    w.writerow(row)
            print(f"wrote reuse search to {args.search_out}")

    print(f"wrote {len(rows)} rows to {args.csv}")
    print(f"wrote summary to {args.summary}")
    if not args.precomputed_csv and not pdftotext:
        print("warning: pdftotext not found; fallback used for all papers")


if __name__ == "__main__":
    main()
