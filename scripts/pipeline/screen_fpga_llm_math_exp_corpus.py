#!/usr/bin/env python3
"""Screen a caller-supplied FPGA-LLM paper cache without retaining paper text."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


SEMANTIC_TERMS = {
    "exp": r"\bexp(?:onential)?\b",
    "softmax": r"\bsoftmax\b",
    "maximum-subtraction": r"(?:subtract(?:ion)?[^\f]{0,80}maximum|maximum[^\f]{0,80}subtract)",
    "normalization": r"\b(?:layernorm|rmsnorm|normalization)\b",
}
IMPLEMENTATION_TERMS = {
    "lookup-table": r"\b(?:lookup table|lut)\b",
    "polynomial": r"\bpolynomial\b",
    "piecewise": r"\bpiecewise(?:[- ]linear)?\b",
    "range-reduction": r"\brange reduction\b",
    "floating-point": r"\bfloating[ -]point\b",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_catalog(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError(f"catalog must be a JSON object: {path}")
    if decoded.get("schema_version") != 1:
        raise ValueError("catalog schema_version must be 1")
    if not isinstance(decoded.get("papers"), dict):
        raise ValueError("catalog papers field must be a mapping")
    return decoded


def extract_pages(pdftotext: str, pdf: Path) -> list[str]:
    completed = subprocess.run(
        [pdftotext, "-enc", "UTF-8", "-layout", str(pdf), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"pdftotext failed for {pdf}: {detail}")
    pages = completed.stdout.split("\f")
    if pages and pages[-1] == "":
        pages.pop()
    return pages


def paper_metadata(paper: object) -> dict[str, object]:
    record = paper if isinstance(paper, dict) else {}
    return {
        "arxiv_id": record.get("arxiv_id"),
        "version": record.get("version"),
        "title": record.get("title"),
        "abs_url": record.get("abs_url"),
        "pdf_url": record.get("pdf_url"),
    }


def unavailable_paper(
    paper: object,
    *,
    cache_status: str,
    cache_filename: object = None,
    receipt_sha256: object = None,
    observed_sha256: object = None,
    byte_count: object = None,
) -> dict[str, object]:
    result = paper_metadata(paper)
    result.update(
        {
            "cache_status": cache_status,
            "cache_filename": cache_filename,
            "receipt_sha256": receipt_sha256,
            "observed_sha256": observed_sha256,
            "byte_count": byte_count,
            "term_pages": {},
            "term_counts": {},
            "deep_read_candidate": False,
        }
    )
    return result


def screen_paper(
    paper: object, papers_dir: Path, pdftotext: str
) -> dict[str, object]:
    record = paper if isinstance(paper, dict) else {}
    cache = record.get("cache")
    if not isinstance(cache, dict):
        return unavailable_paper(record, cache_status="missing-cache-receipt")

    filename = cache.get("filename")
    receipt_sha256 = cache.get("sha256")
    if not isinstance(filename, str) or not filename or not isinstance(receipt_sha256, str):
        return unavailable_paper(
            record,
            cache_status="missing-cache-receipt",
            cache_filename=filename,
            receipt_sha256=receipt_sha256,
        )

    pdf = papers_dir / filename
    if not pdf.is_file():
        return unavailable_paper(
            record,
            cache_status="missing",
            cache_filename=filename,
            receipt_sha256=receipt_sha256,
        )

    observed_sha256 = sha256_file(pdf)
    byte_count = pdf.stat().st_size
    if observed_sha256 != receipt_sha256:
        return unavailable_paper(
            record,
            cache_status="sha256-mismatch",
            cache_filename=filename,
            receipt_sha256=receipt_sha256,
            observed_sha256=observed_sha256,
            byte_count=byte_count,
        )

    term_pages: dict[str, list[int]] = {}
    term_counts: dict[str, int] = {}
    terms = {**SEMANTIC_TERMS, **IMPLEMENTATION_TERMS}
    for page_number, page in enumerate(extract_pages(pdftotext, pdf), 1):
        for name, pattern in terms.items():
            match_count = len(re.findall(pattern, page, flags=re.IGNORECASE))
            if match_count:
                term_pages.setdefault(name, []).append(page_number)
                term_counts[name] = term_counts.get(name, 0) + match_count

    result = paper_metadata(record)
    result.update(
        {
            "cache_status": "verified",
            "cache_filename": filename,
            "receipt_sha256": receipt_sha256,
            "observed_sha256": observed_sha256,
            "byte_count": byte_count,
            "term_pages": {
                name: term_pages[name] for name in sorted(term_pages)
            },
            "term_counts": {
                name: term_counts[name] for name in sorted(term_counts)
            },
            "deep_read_candidate": bool(
                set(term_pages).intersection(SEMANTIC_TERMS)
                and set(term_pages).intersection(IMPLEMENTATION_TERMS)
            ),
        }
    )
    return result


def screen_catalog(
    catalog_path: Path, papers_dir: Path, pdftotext: str
) -> dict[str, object]:
    catalog = load_catalog(catalog_path)
    papers = catalog["papers"]
    if not isinstance(papers, dict):
        raise ValueError("catalog papers field must be a mapping")

    screened: dict[str, dict[str, object]] = {}
    verified = 0
    unavailable = 0
    for key in sorted(papers):
        record = screen_paper(papers[key], papers_dir, pdftotext)
        screened[key] = record
        if record["cache_status"] == "verified":
            verified += 1
        else:
            unavailable += 1

    return {
        "schema_version": 1,
        "blocker": "math.exp",
        "terms": {
            "semantic": {
                name: SEMANTIC_TERMS[name] for name in sorted(SEMANTIC_TERMS)
            },
            "implementation": {
                name: IMPLEMENTATION_TERMS[name]
                for name in sorted(IMPLEMENTATION_TERMS)
            },
        },
        "corpus": {
            "catalog_sha256": sha256_file(catalog_path),
            "catalog_records": len(screened),
            "verified_pdf_records": verified,
            "unavailable_pdf_records": unavailable,
        },
        "papers": screened,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Screen an external FPGA-LLM PDF cache without retaining text."
    )
    parser.add_argument("--paper-root", required=True, type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--papers-dir", type=Path)
    parser.add_argument("--pdftotext", default="pdftotext")
    parser.add_argument("--out-json", required=True, type=Path)
    args = parser.parse_args(argv)

    catalog_path = args.catalog or args.paper_root / "data" / "catalog.json"
    papers_dir = args.papers_dir or args.paper_root / "papers"
    write_json(
        args.out_json,
        screen_catalog(catalog_path, papers_dir, args.pdftotext),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
