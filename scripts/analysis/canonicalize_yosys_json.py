#!/usr/bin/env python3
"""Prove Yosys JSON identity modulo authenticated physical source paths."""
import argparse
import hashlib
import json
from pathlib import Path
import re
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


_RESERVED_SOURCE_TOKEN = re.compile(r"@source/\d{2,}")
_SOURCE_COORDINATE = r"\d+(?:\.\d+)?"
_SOURCE_LOCATION = rf":{_SOURCE_COORDINATE}(?:-{_SOURCE_COORDINATE})?"
_GENERATED_LOCATION = re.compile(
    rf"{_SOURCE_LOCATION}\$\d+")
_PROVENANCE_ATTRIBUTES = {"src", "module_src", "cell_src"}


def _reject_reserved_tokens(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if _RESERVED_SOURCE_TOKEN.search(key):
                raise NetlistMismatch(
                    f"reserved canonical source token in raw key at {path!r}")
            _reject_reserved_tokens(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_reserved_tokens(child, path + (index,))
    elif isinstance(value, str) and _RESERVED_SOURCE_TOKEN.search(value):
        raise NetlistMismatch(
            f"reserved canonical source token in raw value at {path!r}")


def _normalize_generated_key(key, child, context, replacements):
    if context not in ("cells", "netnames") or not isinstance(child, dict):
        return key
    result = key
    for physical, logical in replacements:
        function_marker = f"$func${physical}"
        attributes = child.get("attributes", {})
        hdlname = attributes.get("hdlname") if isinstance(attributes, dict) else None
        public_generated_function = (
            context == "netnames" and child.get("hide_name") == 0 and
            isinstance(hdlname, str) and function_marker in key and
            function_marker in hdlname and
            key.split(function_marker, 1)[1] ==
            hdlname.split(function_marker, 1)[1] and
            _GENERATED_LOCATION.match(key.split(function_marker, 1)[1]))
        if child.get("hide_name") != 1 and not public_generated_function:
            continue
        start = 0
        while True:
            index = result.find(physical, start)
            if index < 0:
                break
            prefix = result[:index]
            suffix = result[index + len(physical):]
            generated_prefix = re.search(r"\$[^$\s]*\$$", prefix)
            if generated_prefix and _GENERATED_LOCATION.match(suffix):
                result = result[:index] + logical + suffix
                start = index + len(logical)
            else:
                start = index + len(physical)
    return result


def _normalize_attribute(field, value, replacements):
    if not isinstance(value, str):
        return value
    if field in _PROVENANCE_ATTRIBUTES:
        # Yosys source provenance is a pipe-separated list of
        # <filename>:<line>[.<column>][-<line>[.<column>]] tokens.
        for physical, logical in replacements:
            source_token = re.compile(
                rf"(^|\|){re.escape(physical)}"
                rf"(?={_SOURCE_LOCATION}(?:\||$))")
            value = source_token.sub(
                lambda match: match.group(1) + logical, value)
        return value
    if field == "hdlname":
        for physical, logical in replacements:
            # Generated functions spell their source as
            # $func$<filename>:<location>$<id>[.<local-name>].
            function_token = re.compile(
                rf"(\$func\$){re.escape(physical)}"
                rf"(?={_GENERATED_LOCATION.pattern}(?:\.|$))")
            value = function_token.sub(
                lambda match: match.group(1) + logical, value)
    return value


def _normalize(value, replacements, path=()):
    if isinstance(value, dict):
        result = {}
        context = path[-1] if path else None
        for key, child in value.items():
            normalized_key = _normalize_generated_key(
                key, child, context, replacements)
            if normalized_key in result:
                raise NetlistMismatch(f"source-path normalization collides at key: {normalized_key}")
            if context == "attributes":
                normalized_child = _normalize_attribute(key, child, replacements)
            else:
                normalized_child = _normalize(child, replacements, path + (normalized_key,))
            result[normalized_key] = normalized_child
        return result
    if isinstance(value, list):
        return [_normalize(child, replacements, path + (index,))
                for index, child in enumerate(value)]
    return value


def _classify(left, right, left_replacements, right_replacements, counts):
    _classify_at(left, right, left_replacements, right_replacements, counts, ())


def _classify_at(left, right, left_replacements, right_replacements, counts, path):
    if isinstance(left, dict) and isinstance(right, dict):
        context = path[-1] if path else None
        left_items = [(_normalize_generated_key(key, value, context, left_replacements), key, value)
                      for key, value in left.items()]
        right_items = [(_normalize_generated_key(key, value, context, right_replacements), key, value)
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
                counts["generated_keys"][context] += 1
            _classify_at(left_value, right_value, left_replacements,
                         right_replacements, counts, path + (key,))
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            counts["unexplained"] += 1
            return
        for left_value, right_value in zip(left, right):
            _classify_at(left_value, right_value, left_replacements,
                         right_replacements, counts, path + (0,))
        return
    if left != right:
        field = path[-1] if path else None
        is_attribute = len(path) >= 2 and path[-2] == "attributes"
        normalized_left = (_normalize_attribute(field, left, left_replacements)
                           if is_attribute else left)
        normalized_right = (_normalize_attribute(field, right, right_replacements)
                            if is_attribute else right)
        if normalized_left == normalized_right and left != right:
            counts["source_path_values"] += 1
            label = ("generated_function_hdlname" if field == "hdlname"
                     else field)
            counts["metadata_values"][label] += 1
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
    _reject_reserved_tokens(left_design)
    _reject_reserved_tokens(right_design)
    left_replacements, right_replacements = _replacements(left_rows), _replacements(right_rows)
    left_canonical = _normalize(left_design, left_replacements)
    right_canonical = _normalize(right_design, right_replacements)
    left_bytes = json.dumps(left_canonical, sort_keys=True, separators=(",", ":")).encode()
    right_bytes = json.dumps(right_canonical, sort_keys=True, separators=(",", ":")).encode()

    counts = {"source_path_values": 0, "source_path_keys": 0,
              "metadata_values": {"src": 0, "module_src": 0,
                                  "cell_src": 0,
                                  "generated_function_hdlname": 0},
              "generated_keys": {"cells": 0, "netnames": 0},
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
