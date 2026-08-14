#!/usr/bin/env python3
"""Write durable XC7K480T evidence for one W4A8 RC-serving phase."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "llm2fpga.w4a8-xc7k480t-evidence.v1"
RESOURCE = re.compile(
    r"^Info:\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<used>\d+)\s*/\s*(?P<available>\d+)\s+(?P<pct>\d+)%\s*$"
)
TARGET = re.compile(r"target frequency (?P<mhz>\d+(?:\.\d+)?) MHz")
FMAX = re.compile(
    r"Max frequency for clock\s+'(?P<clock>[^']+)':\s*"
    r"(?P<mhz>\d+(?:\.\d+)?) MHz"
)
GNU_TIME = {
    "user_cpu_seconds": re.compile(
        r"^User time \(seconds\):\s*(?P<value>\d+(?:\.\d+)?)$", re.MULTILINE
    ),
    "system_cpu_seconds": re.compile(
        r"^System time \(seconds\):\s*(?P<value>\d+(?:\.\d+)?)$", re.MULTILINE
    ),
    "elapsed": re.compile(
        r"^Elapsed \(wall clock\) time .*?:\s*(?P<value>\S+)\s*$", re.MULTILINE
    ),
    "peak_rss_kbytes": re.compile(
        r"^Maximum resident set size \(kbytes\):\s*(?P<value>\d+)$", re.MULTILINE
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_status(path: Path) -> str:
    return read_text(path).strip() or "not-run: missing status receipt"


def status_kind(status: str) -> tuple[str, int | None]:
    try:
        code = int(status)
    except ValueError:
        return "not-run", None
    return ("success" if code == 0 else "failed"), code


def first_diagnostic(log: str, fallback: str) -> str:
    for line in log.splitlines():
        if line.startswith(("ERROR:", "Error:", "error:")):
            return line.split(":", 1)[1].strip()
    for line in log.splitlines():
        if line.strip():
            return line.strip()
    return fallback


def category(name: str) -> str | None:
    if name in {"SLICE_LUT", "SLICE_LUTX"}:
        return "clb_luts"
    if name in {"SLICE_FF", "SLICE_FFX"}:
        return "clb_ffs"
    if name.startswith("DSP48"):
        return "dsp"
    if name.startswith("RAMB36"):
        return "bram36"
    if name.startswith("RAMB18"):
        return "bram18"
    return None


def mapped_resources(path: Path | None) -> dict[str, int] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    modules = payload.get("modules", {}) if isinstance(payload, dict) else {}
    counts: dict[str, int] = {}
    if isinstance(modules, dict):
        # ``stat -json`` lists every elaborated module.  Counting all of them
        # would double-count cells below the measured top-level ``main``.
        top = next(
            (
                modules[name]
                for name in ("main", r"\main")
                if isinstance(modules.get(name), dict)
            ),
            None,
        )
        selected_modules = [top] if top is not None else modules.values()
        for module in selected_modules:
            if not isinstance(module, dict):
                continue
            cells = module.get("num_cells_by_type", {})
            if isinstance(cells, dict):
                for name, value in cells.items():
                    if isinstance(name, str) and type(value) is int:
                        counts[name] = counts.get(name, 0) + value
    if not counts and isinstance(payload, dict) and isinstance(
        payload.get("num_cells_by_type"), dict
    ):
        counts = {
            name: value for name, value in payload["num_cells_by_type"].items()
            if isinstance(name, str) and type(value) is int
        }
    resources = {key: 0 for key in ("clb_luts", "clb_ffs", "dsp", "bram36", "bram18")}
    for name, count in counts.items():
        if re.fullmatch(r"LUT[1-6](?:_2)?", name):
            resources["clb_luts"] += count
        elif name.startswith(("FD", "LD", "SD")):
            resources["clb_ffs"] += count
        elif name.startswith("DSP48"):
            resources["dsp"] += count
        elif name.startswith("RAMB36"):
            resources["bram36"] += count
        elif name.startswith("RAMB18"):
            resources["bram18"] += count
    return resources


def parse_nextpnr(log: str) -> tuple[dict[str, dict[str, int]], float | None, list[dict[str, object]]]:
    resources: dict[str, dict[str, int]] = {}
    target_mhz: float | None = None
    critical_paths: list[dict[str, object]] = []
    for line in log.splitlines():
        if match := RESOURCE.match(line):
            name = category(match.group("name"))
            if name is not None:
                resources[name] = {
                    "used": int(match.group("used")),
                    "available": int(match.group("available")),
                    "percent": int(match.group("pct")),
                }
        if match := TARGET.search(line):
            target_mhz = float(match.group("mhz"))
        if match := FMAX.search(line):
            critical_paths.append({
                "clock": match.group("clock"),
                "max_frequency_mhz": float(match.group("mhz")),
            })
    return resources, target_mhz, critical_paths


def load_json(path: Path | None) -> object:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def elapsed_seconds(value: str) -> float | None:
    try:
        parts = [float(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def time_receipt(path: Path | None, tool_status: str) -> dict[str, object]:
    if tool_status == "not-run":
        return {"status": "unavailable"}
    text = read_text(path)
    matches = {name: pattern.search(text) for name, pattern in GNU_TIME.items()}
    if not all(matches.values()):
        return {"status": "unavailable"}
    elapsed = elapsed_seconds(matches["elapsed"].group("value"))
    if elapsed is None:
        return {"status": "unavailable"}
    return {
        "status": "available",
        "elapsed_seconds": elapsed,
        "user_cpu_seconds": float(matches["user_cpu_seconds"].group("value")),
        "system_cpu_seconds": float(matches["system_cpu_seconds"].group("value")),
        "peak_rss_kbytes": int(matches["peak_rss_kbytes"].group("value")),
    }


def build_evidence(args: argparse.Namespace) -> dict[str, object]:
    yosys_status = read_status(args.yosys_status)
    nextpnr_status = read_status(args.nextpnr_status)
    yosys_kind, yosys_exit_status = status_kind(yosys_status)
    nextpnr_kind, nextpnr_exit_status = status_kind(nextpnr_status)
    yosys_log = read_text(args.yosys_log)
    nextpnr_log = read_text(args.nextpnr_log)
    placed, target_mhz, critical_paths = parse_nextpnr(nextpnr_log)
    fasm_present = args.fasm is not None and args.fasm.is_file() and args.fasm.stat().st_size > 0
    timing_available = nextpnr_kind == "success" and bool(critical_paths)
    over_capacity = any(item["used"] > item["available"] for item in placed.values())

    failure: dict[str, str] | None = None
    fit = "undetermined"
    if yosys_kind != "success":
        failure = {"stage": "yosys", "diagnostic": first_diagnostic(yosys_log, yosys_status)}
    elif nextpnr_kind == "not-run":
        failure = {"stage": "nextpnr", "diagnostic": nextpnr_status}
    elif nextpnr_kind == "failed":
        failure = {
            "stage": "nextpnr",
            "diagnostic": first_diagnostic(nextpnr_log, nextpnr_status),
        }
        if over_capacity:
            fit = "does-not-fit"
    elif fasm_present:
        fit = "fits"
    else:
        failure = {
            "stage": "nextpnr",
            "diagnostic": "nextpnr exited with status 0 without a nonempty FASM",
        }

    return {
        "schema": SCHEMA,
        "provenance": {
            "phase": args.phase,
            "source_path": str(args.source),
            "source_sha256": sha256(args.source),
            "normalized_path": str(args.normalized),
            "normalized_sha256": sha256(args.normalized),
            "normalization_receipt": load_json(args.normalization_receipt),
        },
        "tools": {
            "yosys": {
                "status": yosys_kind,
                "exit_status": yosys_exit_status,
                "log_path": str(args.yosys_log),
                "time": time_receipt(args.yosys_time, yosys_kind),
            },
            "nextpnr": {
                "status": nextpnr_kind,
                "exit_status": nextpnr_exit_status,
                "log_path": str(args.nextpnr_log),
                "time": time_receipt(args.nextpnr_time, nextpnr_kind),
                "fasm": "present" if fasm_present else "absent",
            },
        },
        "resources": {"mapped": mapped_resources(args.yosys_stat), "placed": placed},
        "timing": {
            "status": "available" if timing_available else "unavailable",
            "target_mhz": target_mhz,
            "target_period_ns": round(1000.0 / target_mhz, 6) if target_mhz else None,
            "critical_paths": critical_paths,
        },
        "fit": fit,
        "failure": failure,
        "failure_stage": None if failure is None else failure["stage"],
        "failure_diagnostic": None if failure is None else failure["diagnostic"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--normalized", type=Path, required=True)
    parser.add_argument("--normalization-receipt", type=Path)
    parser.add_argument("--yosys-stat", type=Path)
    parser.add_argument("--yosys-status", type=Path, required=True)
    parser.add_argument("--yosys-log", type=Path, required=True)
    parser.add_argument("--yosys-time", type=Path)
    parser.add_argument("--nextpnr-status", type=Path, required=True)
    parser.add_argument("--nextpnr-log", type=Path, required=True)
    parser.add_argument("--nextpnr-time", type=Path)
    parser.add_argument("--fasm", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out.write_text(
        json.dumps(build_evidence(args), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
