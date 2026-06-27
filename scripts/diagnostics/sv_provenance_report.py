#!/usr/bin/env python3
"""Fast approximate provenance report for emitted SystemVerilog bundles."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, deque
from pathlib import Path
from typing import Any


IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_$]*\b")
MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b")
ENDMODULE_RE = re.compile(r"^\s*endmodule\b")
ASSIGN_RE = re.compile(r"^\s*assign\b")
NUMERIC_SUFFIX_RE = re.compile(r"(?:[_$](?:\d+|bb\d+|stage\d+|block\d+))+$")
GENERIC_IDENTIFIER_RE = re.compile(
    r"^(?:clock|clk|reset|rst|in\d*(?:_(?:valid|ready))?|out\d*(?:_(?:valid|ready))?)$"
)
SV_KEYWORDS = {
    "always_comb",
    "always_ff",
    "assign",
    "begin",
    "case",
    "default",
    "else",
    "end",
    "endcase",
    "endmodule",
    "function",
    "if",
    "import",
    "input",
    "logic",
    "module",
    "output",
    "package",
    "parameter",
    "signed",
    "wire",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-filelist", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-count", type=int, default=20)
    parser.add_argument("--cluster-lines", type=int, default=200)
    return parser.parse_args()


def filelist_entries(path: Path) -> list[Path]:
    entries = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(Path(line))
    return entries


def normalize_stem(identifier: str) -> str:
    stem = NUMERIC_SUFFIX_RE.sub("", identifier)
    stem = re.sub(r"(?:_\d+)+$", "", stem)
    return stem or identifier


def should_count_identifier(identifier: str) -> bool:
    if identifier in SV_KEYWORDS:
        return False
    if identifier.startswith("__"):
        return False
    if GENERIC_IDENTIFIER_RE.match(identifier):
        return False
    return not identifier[0].isdigit()


def top_cluster_rows(
    clusters: list[dict[str, Any]], total_assign_lines: int, top_count: int
) -> list[dict[str, Any]]:
    rows = sorted(
        clusters,
        key=lambda row: (row["assign_lines"], row["bytes"]),
        reverse=True,
    )[:top_count]
    for row in rows:
        row["pct_assign_lines"] = (
            round((row["assign_lines"] * 100.0) / total_assign_lines, 2)
            if total_assign_lines
            else None
        )
    return rows


def top_rows(counter: Counter[str], total: int, top_count: int, key: str) -> list[dict[str, Any]]:
    rows = []
    for name, count in counter.most_common(top_count):
        rows.append(
            {
                key: name,
                "count": count,
                "pct": round((count * 100.0) / total, 2) if total else None,
            }
        )
    return rows


def top_module_rows(
    modules: Counter[str], module_bytes: Counter[str], top_count: int
) -> list[dict[str, Any]]:
    rows = []
    total_lines = sum(modules.values())
    total_bytes = sum(module_bytes.values())
    for name, lines in modules.most_common(top_count):
        byte_count = module_bytes[name]
        rows.append(
            {
                "module": name,
                "lines": lines,
                "bytes": byte_count,
                "pct_lines": round((lines * 100.0) / total_lines, 2)
                if total_lines
                else None,
                "pct_bytes": round((byte_count * 100.0) / total_bytes, 2)
                if total_bytes
                else None,
            }
        )
    return rows


def analyze_file(path: Path, top_count: int, cluster_lines: int) -> dict[str, Any]:
    line_count = 0
    byte_count = 0
    identifiers: Counter[str] = Counter()
    stems: Counter[str] = Counter()
    modules: Counter[str] = Counter()
    module_bytes: Counter[str] = Counter()
    long_lines: list[dict[str, Any]] = []
    assignment_clusters: list[dict[str, Any]] = []
    assignment_window: deque[dict[str, Any]] = deque()
    total_assign_lines = 0
    current_module = "<outside-module>"

    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line_count += 1
            byte_count += len(raw)
            text = raw.decode("utf-8", errors="ignore")

            module_match = MODULE_RE.match(text)
            if module_match is not None:
                current_module = module_match.group(1)

            modules[current_module] += 1
            module_bytes[current_module] += len(raw)

            if ENDMODULE_RE.match(text):
                current_module = "<outside-module>"

            stripped = text.strip()
            long_lines.append(
                {
                    "file": str(path),
                    "line": line_number,
                    "bytes": len(raw),
                    "prefix": stripped[:160],
                }
            )
            long_lines.sort(key=lambda row: row["bytes"], reverse=True)
            del long_lines[top_count:]

            for identifier in IDENT_RE.findall(text):
                if not should_count_identifier(identifier):
                    continue
                identifiers[identifier] += 1
                stems[normalize_stem(identifier)] += 1

            if path.name == "main.sv" and ASSIGN_RE.match(stripped):
                total_assign_lines += 1
                line_stems = Counter(
                    normalize_stem(identifier)
                    for identifier in IDENT_RE.findall(text)
                    if should_count_identifier(identifier)
                )
                assignment_window.append(
                    {
                        "line": line_number,
                        "bytes": len(raw),
                        "stems": line_stems,
                        "prefix": stripped[:160],
                    }
                )
                if len(assignment_window) > cluster_lines:
                    assignment_window.popleft()
                if len(assignment_window) == cluster_lines:
                    cluster_stems: Counter[str] = Counter()
                    byte_total = 0
                    for entry in assignment_window:
                        cluster_stems.update(entry["stems"])
                        byte_total += entry["bytes"]
                    dominant_stem, dominant_count = (
                        cluster_stems.most_common(1)[0]
                        if cluster_stems
                        else ("<none>", 0)
                    )
                    assignment_clusters.append(
                        {
                            "file": str(path),
                            "line_start": assignment_window[0]["line"],
                            "line_end": assignment_window[-1]["line"],
                            "assign_lines": cluster_lines,
                            "bytes": byte_total,
                            "dominant_stem": dominant_stem,
                            "dominant_stem_count": dominant_count,
                            "first_line": assignment_window[0]["prefix"],
                            "last_line": assignment_window[-1]["prefix"],
                        }
                    )

    return {
        "path": str(path),
        "bytes": byte_count,
        "lines": line_count,
        "identifiers": identifiers,
        "stems": stems,
        "modules": modules,
        "module_bytes": module_bytes,
        "long_lines": long_lines,
        "assignment_clusters": assignment_clusters,
        "total_assign_lines": total_assign_lines,
    }


def pct(part: int, whole: int) -> float | None:
    if whole == 0:
        return None
    return round((part * 100.0) / whole, 2)


def build_report(entries: list[Path], top_count: int, cluster_lines: int) -> dict[str, Any]:
    total_bytes = 0
    total_lines = 0
    identifiers: Counter[str] = Counter()
    stems: Counter[str] = Counter()
    modules: Counter[str] = Counter()
    module_bytes: Counter[str] = Counter()
    files = []
    long_lines = []
    assignment_clusters = []
    total_assign_lines = 0

    for entry in entries:
        if not entry.exists():
            files.append({"path": str(entry), "missing": True})
            continue
        analyzed = analyze_file(entry, top_count, cluster_lines)
        total_bytes += analyzed["bytes"]
        total_lines += analyzed["lines"]
        identifiers.update(analyzed["identifiers"])
        stems.update(analyzed["stems"])
        modules.update(analyzed["modules"])
        module_bytes.update(analyzed["module_bytes"])
        assignment_clusters.extend(analyzed["assignment_clusters"])
        total_assign_lines += analyzed["total_assign_lines"]
        files.append(
            {
                "path": analyzed["path"],
                "bytes": analyzed["bytes"],
                "lines": analyzed["lines"],
                "pct_bytes": None,
                "pct_lines": None,
            }
        )
        long_lines.extend(analyzed["long_lines"])

    for row in files:
        if row.get("missing"):
            continue
        row["pct_bytes"] = pct(row["bytes"], total_bytes)
        row["pct_lines"] = pct(row["lines"], total_lines)

    files.sort(key=lambda row: row.get("bytes", 0), reverse=True)
    long_lines.sort(key=lambda row: row["bytes"], reverse=True)
    long_lines = long_lines[:top_count]
    main = next((row for row in files if Path(row["path"]).name == "main.sv"), None)

    report = {
        "report_kind": "sv-provenance-report",
        "bundle": {
            "file_count": len(entries),
            "total_bytes": total_bytes,
            "total_lines": total_lines,
        },
        "main_sv": main,
        "top_files_by_bytes": files[:top_count],
        "top_modules_by_lines": top_module_rows(modules, module_bytes, top_count),
        "top_symbol_stems_by_occurrence": top_rows(
            stems, sum(stems.values()), top_count, "stem"
        ),
        "top_symbols_by_occurrence": top_rows(
            identifiers, sum(identifiers.values()), top_count, "symbol"
        ),
        "top_main_assignment_clusters_by_lines": top_cluster_rows(
            assignment_clusters, total_assign_lines, top_count
        ),
        "top_long_lines": long_lines,
    }
    report["reviewer_summary_lines"] = reviewer_summary_lines(report)
    return report


def format_int(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:,}"


def reviewer_summary_lines(report: dict[str, Any]) -> list[str]:
    bundle = report["bundle"]
    main = report.get("main_sv") or {}
    top_stems = report.get("top_symbol_stems_by_occurrence") or []
    top_modules = report.get("top_modules_by_lines") or []
    top_clusters = report.get("top_main_assignment_clusters_by_lines") or []

    lines = [
        "status: ok",
        "SV provenance report is approximate and based on streaming text heuristics.",
        "sv bundle: "
        f"{format_int(bundle.get('file_count'))} files, "
        f"{format_int(bundle.get('total_bytes'))} bytes, "
        f"{format_int(bundle.get('total_lines'))} lines; "
        f"main.sv {format_int(main.get('bytes'))} bytes / "
        f"{format_int(main.get('lines'))} lines",
    ]
    if top_stems:
        lines.append(
            "top symbol stems: "
            + ", ".join(
                f"{row['stem']}={format_int(row['count'])}"
                for row in top_stems[:5]
            )
        )
    if top_modules:
        lines.append(
            "top modules by lines: "
            + ", ".join(
                f"{row['module']}={format_int(row['lines'])}"
                for row in top_modules[:5]
            )
        )
    if top_clusters:
        lines.append(
            "top main assignment clusters: "
            + ", ".join(
                f"{row['dominant_stem']}@{row['line_start']}-{row['line_end']}="
                f"{format_int(row['assign_lines'])} assigns"
                for row in top_clusters[:5]
            )
        )
    return lines


def main() -> None:
    args = parse_args()
    entries = filelist_entries(Path(args.input_filelist))
    report = build_report(entries, args.top_count, args.cluster_lines)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
