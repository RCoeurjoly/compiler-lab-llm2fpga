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


def generate_mapping(compatibility: object, calyx_memory_bindings: object) -> dict[str, Any]:
    compatibility = _validate_compatibility(compatibility)
    bindings = audit._normalise_bindings(calyx_memory_bindings)
    if bindings["sha256"] != compatibility["calyx_memory_bindings_sha256"]:
        raise ValueError("DDR3 compatibility receipt does not bind this Calyx memory binding receipt")
    binding_rows = {row["port"]: row for row in bindings["ports"]}
    byte_address = 0
    ports = []
    for contract in compatibility["learned_tensor_ports"]:
        width, depth = contract["width_bits"], contract["depth_words"]
        if width % 8:
            raise ValueError("DDR3 mapping requires byte-addressable learned-tensor widths")
        byte_length = width // 8 * depth
        padded_length = ((byte_length + 15) // 16) * 16
        port = contract["port"]
        source = "calyx-memory-binding" if port in binding_rows else "image-memory"
        row = {"port": port, "logical_byte_address": byte_address,
               "wishbone_word_address": byte_address // 16, "width_bits": width,
               "depth_words": depth, "byte_length": byte_length,
               "reserved_byte_length": padded_length, "byte_order": "little-endian",
               "lane_order": "low-address-byte-is-lane-0", "source": source}
        if port in binding_rows:
            row["raw_sha256"] = binding_rows[port]["raw_sha256"]
        ports.append(row)
        byte_address += padded_length
    local = [row["port"] for row in compatibility["ports"] if row["classification"] != "ddr3-learned-tensor"]
    payload = {"schema": SCHEMA, "compatibility_sha256": compatibility["sha256"],
               "memory_abi_sha256": compatibility["memory_abi_sha256"],
               "calyx_memory_bindings_sha256": bindings["sha256"],
               "wishbone": compatibility["wishbone"], "ports": ports,
               "local_port_exclusions": local, "total_reserved_bytes": byte_address}
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
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = generate_mapping(json.loads(args.compatibility.read_text()),
                                json.loads(args.calyx_memory_bindings.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_manifest(manifest), encoding="utf-8")


if __name__ == "__main__":
    main()
