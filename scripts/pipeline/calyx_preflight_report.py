#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROHIBITED_PATTERNS = {
    "arith.uitofp": re.compile(r"\barith\.uitofp\b"),
    "memref.collapse_shape": re.compile(r"\bmemref\.collapse_shape\b"),
    "memref.copy": re.compile(r"\bmemref\.copy\b"),
    "memref.expand_shape": re.compile(r"\bmemref\.expand_shape\b"),
    "memref.reinterpret_cast": re.compile(r"\bmemref\.reinterpret_cast\b"),
}


def build_report(text: str) -> dict[str, object]:
    prohibited_ops = {
        name: count
        for name, pattern in PROHIBITED_PATTERNS.items()
        if (count := len(pattern.findall(text)))
    }
    return {
        "status": "blocked" if prohibited_ops else "ok",
        "prohibited_ops": prohibited_ops,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report prohibited operations at the SCF-to-Calyx boundary."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"missing input MLIR: {args.input}")

    report = build_report(args.input.read_text(encoding="utf-8"))
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 1 if args.require_clean and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
