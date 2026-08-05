#!/usr/bin/env python3
"""Audit the frozen RC memory receipts against the pinned UberDDR3 user port."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import importlib.util
from pathlib import Path
from typing import Any, Mapping, Sequence


MEMORY_PORT_COUNT = 146
LEARNED_PORTS = tuple(range(25)) + tuple(range(27, 46))
TOKEN_PORT, OUTPUT_PORT = 25, 26
SCRATCH_PORTS = tuple(range(46, MEMORY_PORT_COUNT))
SHA256 = re.compile(r"[0-9a-f]{64}")
SCHEMA = "rc-ddr3-compatibility-v1"
UBERDDR3_REVISION = "4a51b9671347130759c9980d6756918f084e2124"
WISHBONE = {
    "address_unit_bytes": 16,
    "data_width_bits": 128,
    "max_outstanding": 1,
    "read_only": True,
    "response": "ack-after-accepted-read",
    "write_supported": False,
}
PROVEN_ZERO_WRITE_ENABLE_SHA256 = hashlib.sha256(b"1'd0").hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _normalise_memory_abi(receipt: object) -> dict[str, Any]:
    if isinstance(receipt, list):
        rows = receipt
        canonical = _canonical(rows)
        receipt = {"schema": "rc-sv-memory-abi-v1", "ports": rows,
                   "canonical_json": canonical, "sha256": _sha(canonical)}
    if not isinstance(receipt, dict):
        raise ValueError("memory ABI receipt must be an object or canonical port array")
    keys = {"schema", "ports", "canonical_json", "sha256"}
    if set(receipt) != keys or receipt.get("schema") != "rc-sv-memory-abi-v1":
        raise ValueError("memory ABI receipt has an unsupported schema")
    rows, canonical, digest = receipt["ports"], receipt["canonical_json"], receipt["sha256"]
    if not isinstance(rows, list) or not isinstance(canonical, str) or not _is_sha(digest):
        raise ValueError("memory ABI receipt is malformed")
    if canonical != _canonical(rows) or _sha(canonical) != digest:
        raise ValueError("memory ABI receipt canonical JSON or SHA-256 does not match")
    if len(rows) != MEMORY_PORT_COUNT:
        raise ValueError("memory ABI receipt must contain all 146 ports")
    expected_keys = {"number", "width", "depth", "kind", "write_enable_sha256"}
    for number, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != expected_keys or row.get("number") != number:
            raise ValueError("memory ABI receipt port rows are not ordered 0 through 145")
        if (not isinstance(row["width"], int) or isinstance(row["width"], bool)
                or row["width"] <= 0 or not isinstance(row["depth"], int)
                or isinstance(row["depth"], bool) or row["depth"] <= 0
                or not _is_sha(row["write_enable_sha256"])):
            raise ValueError("memory ABI receipt has an invalid port shape or write-enable digest")
        expected = "image" if number in LEARNED_PORTS else (
            "token" if number == TOKEN_PORT else "output" if number == OUTPUT_PORT else "scratch")
        if row["kind"] != expected:
            raise ValueError("memory ABI receipt has a changed memory classification")
        if number in LEARNED_PORTS and row["write_enable_sha256"] != PROVEN_ZERO_WRITE_ENABLE_SHA256:
            raise ValueError("learned-tensor write-enable lacks authenticated proven-zero evidence")
    if (rows[TOKEN_PORT]["width"], rows[TOKEN_PORT]["depth"]) != (64, 8):
        raise ValueError("memory ABI receipt has wrong token dimensions")
    if (rows[OUTPUT_PORT]["width"], rows[OUTPUT_PORT]["depth"]) != (8, 64):
        raise ValueError("memory ABI receipt has wrong output dimensions")
    return dict(receipt)


def _normalise_bindings(receipt: object) -> dict[str, Any]:
    required = {"schema", "flat_scf_sha256", "pre_calyx_sha256", "image_sha256",
                "image_manifest_sha256", "memory_abi_sha256", "ports"}
    if isinstance(receipt, dict) and set(receipt) == required:
        payload = receipt
        canonical = _canonical(payload)
        receipt = {**payload, "canonical_json": canonical, "sha256": _sha(canonical)}
    if not isinstance(receipt, dict) or set(receipt) != required | {"canonical_json", "sha256"}:
        raise ValueError("Calyx memory binding receipt has an unsupported schema")
    if receipt.get("schema") != "rc-calyx-external-memory-bindings-v1":
        raise ValueError("Calyx memory binding receipt has an unsupported schema")
    payload = {key: receipt[key] for key in required}
    if (not all(_is_sha(receipt[field]) for field in required - {"schema", "ports"})
            or receipt["canonical_json"] != _canonical(payload)
            or _sha(receipt["canonical_json"]) != receipt["sha256"]):
        raise ValueError("Calyx memory binding receipt canonical JSON or SHA-256 does not match")
    rows = receipt["ports"]
    row_keys = {"port", "ordinal", "global", "source_shape", "lowered_shape", "shape_transform",
                "word_count", "words_u32", "raw_sha256", "image_segment_aliases"}
    if not isinstance(rows, list) or len(rows) != 19:
        raise ValueError("Calyx memory binding receipt must contain ports 27 through 45")
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != row_keys or row["port"] != 27 + ordinal or row["ordinal"] != ordinal:
            raise ValueError("Calyx memory binding receipt rows are not ordered by port")
        if not isinstance(row["word_count"], int) or row["word_count"] <= 0 or not _is_sha(row["raw_sha256"]):
            raise ValueError("Calyx memory binding receipt has malformed binding data")
        words = row["words_u32"]
        if not isinstance(words, list) or len(words) != row["word_count"] or any(
                not isinstance(word, int) or isinstance(word, bool) or not 0 <= word <= 0xffffffff for word in words):
            raise ValueError("Calyx memory binding receipt has malformed f32 words")
        raw = b"".join(word.to_bytes(4, "little") for word in words)
        if _sha_bytes(raw) != row["raw_sha256"]:
            raise ValueError("Calyx memory binding receipt has a wrong raw SHA-256")
    return dict(receipt)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_closure_digest(source_closure: object | None, uberddr3_root: Path | None) -> str | None:
    if source_closure is None:
        return None
    if not isinstance(source_closure, Mapping) or uberddr3_root is None:
        raise ValueError("DDR3 source closure must be an object")
    materializer_path = Path(__file__).with_name("materialize_ddr3_source_closure.py")
    spec = importlib.util.spec_from_file_location("ddr3_source_closure", materializer_path)
    if spec is None or spec.loader is None:
        raise ValueError("unable to load the Task 1 source-closure validator")
    materializer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(materializer)
    try:
        materializer.verify_manifest(uberddr3_root, source_closure)
    except ValueError as error:
        raise ValueError(f"DDR3 source closure fails Task 1 validation: {error}") from error
    return _sha(_canonical(source_closure))


def _sv_source_sha256(sv_sources: Sequence[Path]) -> str:
    """Use the extractor's byte-framed source hash for audit-time binding."""
    extractor_path = Path(__file__).with_name("extract_rc_sv_routing_evidence.py")
    spec = importlib.util.spec_from_file_location("rc_sv_routing_evidence", extractor_path)
    if spec is None or spec.loader is None:
        raise ValueError("unable to load the SV routing evidence extractor")
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    return extractor.source_sha256(sv_sources)


def _port_contract(number: int, row: Mapping[str, Any]) -> dict[str, Any]:
    if number in LEARNED_PORTS:
        classification = "ddr3-learned-tensor"
    elif number == TOKEN_PORT:
        classification = "local-token-input"
    elif number == OUTPUT_PORT:
        classification = "local-output"
    else:
        classification = "local-mutable-scratch"
    address_bits = max(1, math.ceil(math.log2(row["depth"])))
    return {"port": number, "classification": classification, "kind": row["kind"],
            "width_bits": row["width"], "depth_words": row["depth"], "address_bits": address_bits,
            "pins": {"addr0": "output", "content_en": "output", "write_en": "output",
                     "write_data": "output", "read_data": "input", "done": "input"},
            "completion": {"max_outstanding": 1, "request_order": "in-order",
                           "response": "one-done-per-accepted-request"}}


def audit_compatibility(memory_abi: object, calyx_memory_bindings: object,
                        source_closure: object | None = None,
                        uberddr3_root: Path | None = None,
                        sv_evidence: object | None = None,
                        sv_sources: Sequence[Path] | None = None) -> dict[str, Any]:
    """Validate receipt linkage and return the immutable DDR3 routing contract."""
    abi = _normalise_memory_abi(memory_abi)
    bindings = _normalise_bindings(calyx_memory_bindings)
    if bindings["memory_abi_sha256"] != abi["sha256"]:
        raise ValueError("Calyx memory binding receipt does not bind this memory ABI receipt")
    evidence_keys = {"schema", "source_sha256", "memory_abi_sha256", "ports", "completion", "canonical_json", "sha256"}
    if not isinstance(sv_evidence, Mapping) or set(sv_evidence) != evidence_keys:
        raise ValueError("DDR3 routing requires explicit SV-derived ABI evidence")
    payload = {key: sv_evidence[key] for key in evidence_keys - {"canonical_json", "sha256"}}
    if (sv_evidence["schema"] != "rc-sv-routing-evidence-v1"
            or sv_evidence["canonical_json"] != _canonical(payload)
            or sv_evidence["sha256"] != _sha(sv_evidence["canonical_json"])):
        raise ValueError("SV-derived ABI evidence has an invalid canonical hash")
    if not _is_sha(sv_evidence["source_sha256"]) or sv_evidence["memory_abi_sha256"] != abi["sha256"]:
        raise ValueError("SV-derived ABI evidence does not bind this memory ABI receipt")
    if sv_sources is not None and sv_evidence["source_sha256"] != _sv_source_sha256(sv_sources):
        raise ValueError("SV-derived ABI evidence source hash does not match the supplied SV bytes")
    if sv_evidence["completion"] != {"max_outstanding": 1, "response": "one-done-per-accepted-request"}:
        raise ValueError("SV-derived ABI evidence lacks the required completion semantics")
    evidence_ports = sv_evidence["ports"]
    if not isinstance(evidence_ports, list) or len(evidence_ports) != MEMORY_PORT_COUNT:
        raise ValueError("SV-derived ABI evidence lacks all parsed memory ports")
    for number, evidence in enumerate(evidence_ports):
        if (not isinstance(evidence, Mapping) or evidence.get("port") != number
                or evidence.get("pins") != {"addr0": "output", "content_en": "output", "write_en": "output", "write_data": "output", "read_data": "input", "done": "input"}
                or (number in LEARNED_PORTS and evidence.get("write_enable") != "proven-zero")):
            raise ValueError("SV-derived ABI evidence has unverified pins or write-enable semantics")
    for port in LEARNED_PORTS:
        row = abi["ports"][port]
        if row["width"] % 8 or row["width"] > WISHBONE["data_width_bits"]:
            raise ValueError("learned-tensor width is incompatible with the 128-bit DDR3 user port")
    for binding in bindings["ports"]:
        abi_row = abi["ports"][binding["port"]]
        if abi_row["width"] != 32 or binding["word_count"] * 4 > (
                abi_row["width"] // 8 * abi_row["depth"]):
            raise ValueError("Calyx binding does not fit its immutable RC memory port")
    closure_digest = _source_closure_digest(source_closure, uberddr3_root)
    rows = [_port_contract(number, row) for number, row in enumerate(abi["ports"])]
    payload: dict[str, Any] = {"schema": SCHEMA, "memory_abi_sha256": abi["sha256"],
                               "calyx_memory_bindings_sha256": bindings["sha256"], "wishbone": WISHBONE,
                               "ports": rows,
                               "learned_tensor_ports": [row for row in rows if row["classification"] == "ddr3-learned-tensor"]}
    if closure_digest is not None:
        payload["ddr3_source_closure_sha256"] = closure_digest
    canonical = _canonical(payload)
    return {**payload, "canonical_json": canonical, "sha256": _sha(canonical)}


def render_receipt(receipt: Mapping[str, Any]) -> str:
    return json.dumps(receipt, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-abi", required=True, type=Path)
    parser.add_argument("--calyx-memory-bindings", required=True, type=Path)
    parser.add_argument("--sv-evidence", required=True, type=Path)
    parser.add_argument("--sv", required=True, action="append", type=Path,
                        help="generated SV input used to extract --sv-evidence; repeat for each source")
    parser.add_argument("--ddr3-source-closure", type=Path)
    parser.add_argument("--uberddr3-root", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.ddr3_source_closure and args.uberddr3_root is None:
        parser.error("--uberddr3-root is required with --ddr3-source-closure for Task 1 validation")
    closure = json.loads(args.ddr3_source_closure.read_text()) if args.ddr3_source_closure else None
    receipt = audit_compatibility(json.loads(args.memory_abi.read_text()),
                                  json.loads(args.calyx_memory_bindings.read_text()), closure,
                                  args.uberddr3_root, json.loads(args.sv_evidence.read_text()), args.sv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_receipt(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
