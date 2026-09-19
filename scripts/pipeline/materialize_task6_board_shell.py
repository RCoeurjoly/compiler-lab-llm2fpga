#!/usr/bin/env python3
"""Materialize the receipt-linked, immutable Task 6 board-shell source closure.

The repaired LLM2FPGA files are vendored verbatim from e368449 Git objects.
Dependencies come only from the exact historical loader Nix derivations, never
from an ambient checkout. This does not claim a clean PCIe upstream revision:
the historical endpoint was a dirty-tree snapshot, now pinned by every byte.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = Path(__file__).with_name("task6_board_shell_pins.json")


def _digest(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked pinned source: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(row):
    name = row["source"]
    if name.startswith("/nix/store/"):
        path = Path(name)
        if not path.resolve().is_relative_to("/nix/store"):
            raise ValueError("source escapes immutable store")
        return path
    if name.startswith("third_party/task6-e368449/"):
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT / "third_party/task6-e368449"):
            raise ValueError("source escapes vendored Git snapshot")
        return path
    raise ValueError("ambient checkout and temporary source paths are forbidden")


def verify_manifest(manifest):
    """Reject any revised identity, input path, profile, source hash or tool pin."""
    pins = json.loads(PINS.read_text())
    if manifest != pins:
        raise ValueError("manifest differs from the committed board-shell pins")
    for row in manifest["sources"]:
        path = _source(row)
        if _digest(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise ValueError(f"source SHA-256/size mismatch: {row['logical_path']}")


def build_manifest():
    manifest = json.loads(PINS.read_text())
    verify_manifest(manifest)
    return manifest


def verify_materialized(out, manifest):
    verify_manifest(manifest)
    for row in manifest["sources"]:
        path = out / row["logical_path"]
        if _digest(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise ValueError(f"materialized SHA-256/size mismatch: {row['logical_path']}")


def materialize(out, manifest):
    verify_manifest(manifest)
    for row in manifest["sources"]:
        target = out / row["logical_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_source(row).read_bytes())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    verify_materialized(out, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest()
    if args.verify:
        verify_materialized(args.out, manifest)
    else:
        materialize(args.out, manifest)


if __name__ == "__main__":
    main()
