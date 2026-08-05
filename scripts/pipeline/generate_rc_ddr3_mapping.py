#!/usr/bin/env python3
"""Generate a hash-bound, learned-tensor-only RC-to-DDR3 byte map."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "audit_rc_ddr3_compatibility.py"
spec = importlib.util.spec_from_file_location("rc_ddr3_audit", AUDIT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load {AUDIT_PATH}")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

SCHEMA = "rc-ddr3-learned-tensor-mapping-v1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_compatibility(receipt: object) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("DDR3 compatibility receipt must be an object")
    required = {"schema", "memory_abi_sha256", "calyx_memory_bindings_sha256", "wishbone", "ports", "learned_tensor_ports"}
    optional = {"ddr3_source_closure_sha256"}
    if set(receipt) - {"canonical_json", "sha256"} not in (required, required | optional):
        raise ValueError("DDR3 compatibility receipt has an unsupported schema")
    payload = {key: value for key, value in receipt.items() if key not in ("canonical_json", "sha256")}
    if receipt.get("schema") != "rc-ddr3-compatibility-v1" or receipt.get("canonical_json") != _canonical(payload) or receipt.get("sha256") != _sha(receipt["canonical_json"]):
        raise ValueError("DDR3 compatibility receipt canonical JSON or SHA-256 does not match")
    if receipt["wishbone"] != audit.WISHBONE or len(receipt["ports"]) != 146:
        raise ValueError("DDR3 compatibility receipt has a changed transport contract")
    learned = receipt["learned_tensor_ports"]
    expected = [row for row in receipt["ports"] if row.get("classification") == "ddr3-learned-tensor"]
    if learned != expected or [row.get("port") for row in learned] != list(audit.LEARNED_PORTS):
        raise ValueError("DDR3 compatibility receipt has a changed learned-tensor ordering")
    return receipt


def _image_segments(image: bytes, manifest: object) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("segments"), list):
        raise ValueError("image manifest has malformed segments")
    result = {}
    for segment in manifest["segments"]:
        if (not isinstance(segment, dict) or set(segment) != {"name", "offset", "byte_length", "source_category", "dtype", "shape"}
                or not isinstance(segment["name"], str) or segment["name"] in result
                or not isinstance(segment["offset"], int) or not isinstance(segment["byte_length"], int)
                or segment["offset"] < 0 or segment["byte_length"] <= 0
                or segment["offset"] + segment["byte_length"] > len(image)):
            raise ValueError("image manifest has malformed segments")
        result[segment["name"]] = segment
    return result


def _fixed_image_segment_name(port: int) -> str:
    if port < 21:
        return f"state/_frozen_param{port}"
    return {
        21: "state/transformer.h.0.attn.attention.bias",
        22: "state/transformer.h.0.attn.attention.lifted_tensor_0",
        23: "state/transformer.h.1.attn.attention.bias",
        24: "state/transformer.h.1.attn.attention.lifted_tensor_1",
    }[port]


def generate_mapping(compatibility: object, calyx_memory_bindings: object,
                     image: bytes, image_manifest_bytes: bytes) -> dict[str, Any]:
    compatibility = _validate_compatibility(compatibility)
    bindings = audit._normalise_bindings(calyx_memory_bindings)
    if bindings["sha256"] != compatibility["calyx_memory_bindings_sha256"]:
        raise ValueError("DDR3 compatibility receipt does not bind this Calyx memory binding receipt")
    if not isinstance(image, bytes) or hashlib.sha256(image).hexdigest() != bindings["image_sha256"]:
        raise ValueError("source image SHA-256 does not match the Calyx memory binding receipt")
    if (not isinstance(image_manifest_bytes, bytes)
            or hashlib.sha256(image_manifest_bytes).hexdigest() != bindings["image_manifest_sha256"]):
        raise ValueError("source image manifest SHA-256 does not match the Calyx memory binding receipt")
    try:
        image_manifest = json.loads(image_manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("source image manifest is not valid JSON") from error
    segments = _image_segments(image, image_manifest)
    binding_rows = {row["port"]: row for row in bindings["ports"]}
    ports = []
    for contract in compatibility["learned_tensor_ports"]:
        width, depth = contract["width_bits"], contract["depth_words"]
        if width % 8:
            raise ValueError("DDR3 mapping requires byte-addressable learned-tensor widths")
        byte_length = width // 8 * depth
        port = contract["port"]
        source = "calyx-memory-binding" if port in binding_rows else "image-memory"
        if port in binding_rows:
            binding = binding_rows[port]
            candidates = [segments[name] for name in binding["image_segment_aliases"] if name in segments]
            if len(candidates) != 1:
                raise ValueError("Calyx binding must identify exactly one source image segment")
            segment = candidates[0]
            raw = image[segment["offset"]:segment["offset"] + segment["byte_length"]]
            expected = b"".join(word.to_bytes(4, "little") for word in binding["words_u32"])
            if raw != expected:
                raise ValueError("Calyx binding source image segment does not preserve frozen bytes")
        else:
            try:
                segment = segments[_fixed_image_segment_name(port)]
            except KeyError as error:
                raise ValueError("immutable RC port is missing its authoritative source image segment") from error
        if segment["byte_length"] != byte_length:
            raise ValueError("source image byte layout does not match immutable RC port dimensions")
        dtype_widths = {"float32": 32, "int8": 8, "uint8": 8, "int16": 16, "int32": 32}
        if segment["dtype"] not in dtype_widths or width != dtype_widths[segment["dtype"]]:
            raise ValueError("immutable RC port width does not match authoritative source-image dtype")
        row = {"port": port, "logical_byte_address": segment["offset"],
               "wishbone_word_address": segment["offset"] // 16, "width_bits": width,
               "depth_words": depth, "byte_length": byte_length,
               "source_segment": segment["name"], "byte_order": "little-endian",
               "lane_order": "low-address-byte-is-lane-0", "source": source}
        if port in binding_rows:
            row["raw_sha256"] = binding_rows[port]["raw_sha256"]
        ports.append(row)
    local = [row["port"] for row in compatibility["ports"] if row["classification"] != "ddr3-learned-tensor"]
    payload = {"schema": SCHEMA, "compatibility_sha256": compatibility["sha256"],
               "memory_abi_sha256": compatibility["memory_abi_sha256"],
               "calyx_memory_bindings_sha256": bindings["sha256"],
               "wishbone": compatibility["wishbone"], "ports": ports,
               "local_port_exclusions": local, "source_image_sha256": bindings["image_sha256"]}
    if "ddr3_source_closure_sha256" in compatibility:
        payload["ddr3_source_closure_sha256"] = compatibility["ddr3_source_closure_sha256"]
    canonical = _canonical(payload)
    return {**payload, "canonical_json": canonical, "sha256": _sha(canonical)}


def render_manifest(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compatibility", required=True, type=Path)
    parser.add_argument("--calyx-memory-bindings", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--image-manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = generate_mapping(json.loads(args.compatibility.read_text()),
                                json.loads(args.calyx_memory_bindings.read_text()),
                                args.image.read_bytes(), args.image_manifest.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_manifest(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
