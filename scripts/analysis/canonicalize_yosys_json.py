#!/usr/bin/env python3
"""Prove Yosys JSON identity modulo authenticated physical source paths."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex


class NetlistMismatch(ValueError):
    """The inputs differ outside permitted physical source-path spelling."""


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def synthesis_sources(script):
    lines = [line.strip() for line in script.read_text().splitlines()
             if line.strip().startswith("read_verilog -sv")]
    if len(lines) != 1:
        raise NetlistMismatch("expected exactly one read_verilog -sv command")
    sources = [Path(token) for token in shlex.split(lines[0])
               if token.endswith((".v", ".sv"))]
    if not sources:
        raise NetlistMismatch("synthesis script has no HDL sources")
    for source in sources:
        if not source.is_file() or source.is_symlink():
            raise NetlistMismatch(f"missing or symlinked synthesis source: {source}")
    return sources


def _source_rows(script):
    rows = []
    for index, source in enumerate(synthesis_sources(script)):
        data = source.read_bytes()
        rows.append({"index": index, "physical_path": str(source),
                     "bytes": len(data), "sha256": _sha256(data)})
    return rows


def _replacements(rows):
    return sorted(((row["physical_path"], f"@source/{row['index']:02d}")
                   for row in rows), key=lambda pair: len(pair[0]), reverse=True)


def _normalize_string(value, replacements):
    for physical, logical in replacements:
        value = value.replace(physical, logical)
    return value


def _normalize(value, replacements):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            normalized_key = _normalize_string(key, replacements)
            if normalized_key in result:
                raise NetlistMismatch(f"source-path normalization collides at key: {normalized_key}")
            result[normalized_key] = _normalize(child, replacements)
        return result
    if isinstance(value, list):
        return [_normalize(child, replacements) for child in value]
    if isinstance(value, str):
        return _normalize_string(value, replacements)
    return value


def _classify(left, right, left_replacements, right_replacements, counts):
    if isinstance(left, dict) and isinstance(right, dict):
        left_items = [(_normalize_string(key, left_replacements), key, value)
                      for key, value in left.items()]
        right_items = [(_normalize_string(key, right_replacements), key, value)
                       for key, value in right.items()]
        if [item[0] for item in left_items] != [item[0] for item in right_items]:
            counts["ordering"] += 1
        left_by_key = {item[0]: item[1:] for item in left_items}
        right_by_key = {item[0]: item[1:] for item in right_items}
        if set(left_by_key) != set(right_by_key):
            counts["unexplained"] += 1
            return
        for key in left_by_key:
            left_raw_key, left_value = left_by_key[key]
            right_raw_key, right_value = right_by_key[key]
            if left_raw_key != right_raw_key:
                counts["source_path_keys"] += 1
            _classify(left_value, right_value, left_replacements,
                      right_replacements, counts)
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            counts["unexplained"] += 1
            return
        for left_value, right_value in zip(left, right):
            _classify(left_value, right_value, left_replacements,
                      right_replacements, counts)
        return
    if left != right:
        if (isinstance(left, str) and isinstance(right, str) and
                _normalize_string(left, left_replacements) ==
                _normalize_string(right, right_replacements)):
            counts["source_path_values"] += 1
        else:
            counts["unexplained"] += 1


def compare_netlists(left_netlist, left_script, right_netlist, right_script):
    left_netlist, left_script = Path(left_netlist), Path(left_script)
    right_netlist, right_script = Path(right_netlist), Path(right_script)
    left_rows, right_rows = _source_rows(left_script), _source_rows(right_script)
    left_hashes = [(row["bytes"], row["sha256"]) for row in left_rows]
    right_hashes = [(row["bytes"], row["sha256"]) for row in right_rows]
    if left_hashes != right_hashes:
        raise NetlistMismatch("ordered source SHA-256 sequence differs")

    left_raw, right_raw = left_netlist.read_bytes(), right_netlist.read_bytes()
    left_design, right_design = json.loads(left_raw), json.loads(right_raw)
    left_replacements, right_replacements = _replacements(left_rows), _replacements(right_rows)
    left_canonical = _normalize(left_design, left_replacements)
    right_canonical = _normalize(right_design, right_replacements)
    left_bytes = json.dumps(left_canonical, sort_keys=True, separators=(",", ":")).encode()
    right_bytes = json.dumps(right_canonical, sort_keys=True, separators=(",", ":")).encode()

    counts = {"source_path_values": 0, "source_path_keys": 0,
              "ordering": 0, "unexplained": 0}
    _classify(left_design, right_design, left_replacements,
              right_replacements, counts)
    if left_bytes != right_bytes or counts["unexplained"]:
        raise NetlistMismatch(
            "canonical netlists differ: " + json.dumps(counts, sort_keys=True))

    canonical_hash = _sha256(left_bytes)
    return {
        "schema": "yosys-json-source-path-canonical-proof-v1",
        "source_count": len(left_rows),
        "source_sha256": [row["sha256"] for row in left_rows],
        "raw": {
            "left": {"bytes": len(left_raw), "sha256": _sha256(left_raw)},
            "right": {"bytes": len(right_raw), "sha256": _sha256(right_raw)},
        },
        "scripts": {
            "left_sha256": _sha256(left_script.read_bytes()),
            "right_sha256": _sha256(right_script.read_bytes()),
        },
        "canonical_equal": True,
        "canonical_bytes": len(left_bytes),
        "canonical_sha256": {"left": canonical_hash, "right": canonical_hash},
        "difference_classes": counts,
        "sources": [
            {"index": left["index"], "bytes": left["bytes"],
             "sha256": left["sha256"], "left_path": left["physical_path"],
             "right_path": right["physical_path"]}
            for left, right in zip(left_rows, right_rows)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-netlist", required=True, type=Path)
    parser.add_argument("--left-script", required=True, type=Path)
    parser.add_argument("--right-netlist", required=True, type=Path)
    parser.add_argument("--right-script", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    proof = compare_netlists(args.left_netlist, args.left_script,
                             args.right_netlist, args.right_script)
    output = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
