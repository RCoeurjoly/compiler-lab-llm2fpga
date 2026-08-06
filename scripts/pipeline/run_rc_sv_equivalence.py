#!/usr/bin/env python3
"""Run the V=6 RC Calyx-SV memory-service fixture against its PT2E oracle.

The Calyx backend exposes the caller-owned flat-SCF buffers as ``arg_mem_N``
ports on ``main_1``.  This fixture supplies those memories, initializes the
frozen integer state from the checked image, drives the token buffer, and
compares the six final int8 codes and argmax token for every frozen corpus
case.  It deliberately fails if the expected functional ports are absent.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


NORMALIZER_MIN_ASSIGNMENT_CHARS = 20_000
NORMALIZER_PAGE_TERMS = 128
CACHE_METADATA_FILENAME = "compile-metadata.json"
STRICT_CACHE_SCHEMA_VERSION = 8
STRICT_FIXTURE_SCHEMA = "rc-observable-shard-fixture-v3"
STRICT_RESULT_SCHEMA = "rc-observable-verilator-shard-v3"
FROZEN_FOUR_SCHEMA = "rc-observable-frozen-four-v3"
STRICT_SEQUENCE_SCHEMA = "rc-observable-sparse-sequence-v1"
F32_CONSTANT_BITS_SCHEMA = "rc-calyx-f32-constant-bits-v1"
CALYX_MEMORY_BINDINGS_SCHEMA = "rc-calyx-external-memory-bindings-v1"
VOCAB_SIZE = 6
CONTEXT_LENGTH = 8
MEMORY_PORT_COUNT = 146
TOKEN_PORT = 25
OUTPUT_PORT = 26
IMAGE_PORTS = frozenset(range(25)) | frozenset(range(27, 46))
SCRATCH_PORTS = frozenset(range(46, MEMORY_PORT_COUNT))
IMMUTABLE_PORTS = IMAGE_PORTS | frozenset({TOKEN_PORT})
MUTABLE_PORTS = frozenset({OUTPUT_PORT}) | SCRATCH_PORTS
STRICT_RUNTIME_MEMORY_PORTS = tuple(range(46))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _strict_runtime_memory_sha256_payloads(payloads: dict[int, bytes]) -> str:
    """Hash one complete in-memory snapshot of strict fixture memories."""

    if set(payloads) != set(STRICT_RUNTIME_MEMORY_PORTS):
        raise RuntimeError("strict runtime memory payloads must cover mem0 through mem45")
    digest = hashlib.sha256()
    digest.update(b"rc-observable-runtime-mem-v1\0")
    for number in STRICT_RUNTIME_MEMORY_PORTS:
        name = f"mem{number}.hex".encode("utf-8")
        payload = payloads[number]
        digest.update(len(name).to_bytes(2, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _strict_runtime_memory_payloads(root: Path) -> dict[int, bytes]:
    """Read one complete snapshot of all files loaded by the strict fixture."""

    payloads: dict[int, bytes] = {}
    for number in STRICT_RUNTIME_MEMORY_PORTS:
        path = root / f"mem{number}.hex"
        if not path.is_file():
            raise RuntimeError(f"strict runtime memory file is missing: {path}")
        payloads[number] = path.read_bytes()
    return payloads


def _strict_runtime_memory_sha256(root: Path) -> str:
    """Hash every materialized memory file consumed by the strict fixture."""

    return _strict_runtime_memory_sha256_payloads(_strict_runtime_memory_payloads(root))


class MemoryPort:
    __slots__ = ("number", "width", "depth", "kind", "write_enable_sha256")

    def __init__(
        self,
        *,
        number: int,
        width: int,
        depth: int,
        kind: str,
        write_enable_sha256: str,
    ) -> None:
        self.number = number
        self.width = width
        self.depth = depth
        self.kind = kind
        self.write_enable_sha256 = write_enable_sha256


def _strip_sv_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def _matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                break
    raise RuntimeError(f"unterminated {opening}{closing} delimiter in main_1")


def _main_1_parts(source: str) -> tuple[str, str]:
    """Return the exact ``main_1`` header and body, excluding other modules."""
    source = _strip_sv_comments(source)
    matches = list(re.finditer(r"\bmodule\s+main_1\s*\(", source))
    if not matches:
        raise RuntimeError("SV does not define module main_1")
    if len(matches) != 1:
        raise RuntimeError("SV must define exactly one module main_1")
    match = matches[0]
    header_open = source.find("(", match.start())
    header_close = _matching_delimiter(source, header_open, "(", ")")
    header_end = source.find(";", header_close)
    if header_end < 0:
        raise RuntimeError("main_1 port header is missing its terminating semicolon")
    endmodule = re.search(r"\bendmodule\b", source[header_end + 1:])
    if endmodule is None:
        raise RuntimeError("main_1 is missing endmodule")
    body_end = header_end + 1 + endmodule.start()
    return source[header_open + 1:header_close], source[header_end + 1:body_end]


def _strip_outer_parentheses(expression: str) -> str:
    expression = expression.strip()
    while expression.startswith("(") and expression.endswith(")"):
        try:
            closing = _matching_delimiter(expression, 0, "(", ")")
        except RuntimeError:
            return expression
        if closing != len(expression) - 1:
            return expression
        expression = expression[1:-1].strip()
    return expression


def _write_enable_leaf_kind(expression: str) -> str:
    expression = _strip_outer_parentheses(expression)
    if re.fullmatch(r"1'[bBoOdDhH]0", expression):
        return "zero"
    if re.fullmatch(r"1'[bBoOdDhH]1", expression):
        return "one"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", expression):
        return "dynamic"
    raise RuntimeError(f"unsupported write-enable syntax: {expression!r}")


def _write_enable_is_proven_zero(expression: str) -> bool:
    """Classify the limited generated-Calyx write-enable grammar safely.

    A flat ternary may have arbitrary condition expressions, but its result
    leaves must be explicit one-bit constants or a simple dynamic signal.  A
    dynamic leaf is mutable; only all-zero leaves are immutable.  Anything
    outside that grammar rejects the frozen ABI instead of guessing.
    """
    expression = _strip_outer_parentheses(expression)
    parsed = _flat_priority_ternary(expression)
    if parsed is None:
        leaves = [expression]
    else:
        pairs, fallback = parsed
        leaves = [value for _, value in pairs] + [fallback]
    kinds = [_write_enable_leaf_kind(leaf) for leaf in leaves]
    return all(kind == "zero" for kind in kinds)


def _memory_abi(source: str) -> dict[int, MemoryPort]:
    """Derive the frozen 146-port memory ABI from ``main_1`` only."""
    header, body = _main_1_parts(source)
    declaration = re.compile(
        r"\b(?P<direction>input|output)\s+logic"
        r"(?:\s+signed)?"
        r"(?:\s+\[\s*(?P<hi>\d+)\s*:\s*(?P<lo>\d+)\s*\])?"
        r"\s+arg_mem_(?P<number>\d+)_(?P<pin>addr0|content_en|write_en|write_data|read_data|done)\b"
    )
    declarations: dict[int, dict[str, tuple[str, int]]] = {}
    for match in declaration.finditer(header):
        number = int(match.group("number"))
        pin = match.group("pin")
        hi, lo = match.group("hi"), match.group("lo")
        width = int(hi) - int(lo) + 1 if hi is not None else 1
        if width <= 0:
            raise RuntimeError(f"invalid arg_mem_{number}_{pin} packed width")
        pins = declarations.setdefault(number, {})
        if pin in pins:
            raise RuntimeError(f"duplicate main_1 declaration for arg_mem_{number}_{pin}")
        pins[pin] = (match.group("direction"), width)

    expected_numbers = set(range(MEMORY_PORT_COUNT))
    declared_numbers = set(declarations)
    if declared_numbers != expected_numbers:
        missing = sorted(expected_numbers - declared_numbers)
        unexpected = sorted(declared_numbers - expected_numbers)
        raise RuntimeError(
            "frozen memory ABI requires exactly arg_mem_0 through arg_mem_145 "
            f"(missing={missing}, unexpected={unexpected})"
        )

    required_pins = {
        "addr0": ("output", None),
        "content_en": ("output", 1),
        "write_en": ("output", 1),
        "write_data": ("output", None),
        "read_data": ("input", None),
        "done": ("input", 1),
    }
    all_external_pins = re.findall(r"\barg_mem_(\d+)_([A-Za-z0-9_]+)\b", header)
    for raw_number, pin in all_external_pins:
        number = int(raw_number)
        if number not in expected_numbers or pin not in required_pins:
            raise RuntimeError(f"unclassified external port arg_mem_{number}_{pin}")
    dimensions: dict[int, tuple[int, int]] = {}
    for number in sorted(expected_numbers):
        pins = declarations[number]
        if set(pins) != set(required_pins):
            raise RuntimeError(
                f"arg_mem_{number} must expose exactly the six ABI pins; "
                f"got {sorted(pins)}"
            )
        for pin, (direction, fixed_width) in required_pins.items():
            actual_direction, actual_width = pins[pin]
            if actual_direction != direction or (
                fixed_width is not None and actual_width != fixed_width
            ):
                raise RuntimeError(
                    f"arg_mem_{number}_{pin} has incompatible direction or width"
                )
        if pins["write_data"][1] != pins["read_data"][1]:
            raise RuntimeError(f"arg_mem_{number} read/write widths disagree")
        dimensions[number] = (
            pins["read_data"][1],
            1 << pins["addr0"][1],
        )

    assignment = re.compile(
        r"\bassign\s+arg_mem_(?P<number>\d+)_write_en\s*=\s*"
        r"(?P<expression>.*?);",
        re.DOTALL,
    )
    write_enables: dict[int, str] = {}
    for match in assignment.finditer(body):
        number = int(match.group("number"))
        if number in write_enables:
            raise RuntimeError(f"duplicate write-enable assignment for arg_mem_{number}")
        write_enables[number] = re.sub(r"\s+", "", match.group("expression"))
    if set(write_enables) != expected_numbers:
        missing = sorted(expected_numbers - set(write_enables))
        unexpected = sorted(set(write_enables) - expected_numbers)
        raise RuntimeError(
            "frozen memory ABI is missing or has unexpected write-enable assignments "
            f"(missing={missing}, unexpected={unexpected})"
        )

    abi: dict[int, MemoryPort] = {}
    for number in sorted(expected_numbers):
        expression = write_enables[number]
        proven_zero = _write_enable_is_proven_zero(expression)
        expected_immutable = number in IMMUTABLE_PORTS
        if proven_zero != expected_immutable:
            expected = "immutable zero" if expected_immutable else "mutable"
            actual = "immutable zero" if proven_zero else "mutable"
            raise RuntimeError(
                f"frozen memory ABI changed at arg_mem_{number}: "
                f"expected {expected}, observed {actual}"
            )
        if number in IMAGE_PORTS:
            kind = "image"
        elif number == TOKEN_PORT:
            kind = "token"
        elif number == OUTPUT_PORT:
            kind = "output"
        elif number in SCRATCH_PORTS:
            kind = "scratch"
        else:
            raise RuntimeError(f"unclassified external arg_mem_{number}")
        width, depth = dimensions[number]
        abi[number] = MemoryPort(
            number=number,
            width=width,
            depth=depth,
            kind=kind,
            write_enable_sha256=hashlib.sha256(expression.encode("utf-8")).hexdigest(),
        )

    if (abi[TOKEN_PORT].width, abi[TOKEN_PORT].depth) != (64, 8):
        raise RuntimeError("arg_mem_25 must be the 64-bit, eight-token input buffer")
    if (abi[OUTPUT_PORT].width, abi[OUTPUT_PORT].depth) != (8, 64):
        raise RuntimeError("arg_mem_26 must be the 8-bit, 64-word output buffer")
    return abi


def _memory_abi_receipt(abi: dict[int, MemoryPort]) -> dict:
    rows = [
        {
            "number": port.number,
            "width": port.width,
            "depth": port.depth,
            "kind": port.kind,
            "write_enable_sha256": port.write_enable_sha256,
        }
        for _, port in sorted(abi.items())
    ]
    canonical_json = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "rc-sv-memory-abi-v1",
        "ports": rows,
        "canonical_json": canonical_json,
        "sha256": hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    }


def _expected_memory_kind(number: int) -> str:
    if number in IMAGE_PORTS:
        return "image"
    if number == TOKEN_PORT:
        return "token"
    if number == OUTPUT_PORT:
        return "output"
    if number in SCRATCH_PORTS:
        return "scratch"
    raise RuntimeError(f"unclassified external arg_mem_{number}")


def _validate_memory_abi_receipt(receipt: object) -> dict:
    """Validate the complete canonical ABI evidence retained by a cache."""
    if not isinstance(receipt, dict):
        raise RuntimeError("memory ABI receipt must be an object")
    if set(receipt) != {"schema", "ports", "canonical_json", "sha256"}:
        raise RuntimeError("memory ABI receipt has an unexpected schema")
    if receipt["schema"] != "rc-sv-memory-abi-v1":
        raise RuntimeError("memory ABI receipt has an unsupported schema")
    rows = receipt["ports"]
    canonical_json = receipt["canonical_json"]
    digest = receipt["sha256"]
    if not isinstance(rows, list) or not isinstance(canonical_json, str):
        raise RuntimeError("memory ABI receipt has malformed rows")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("memory ABI receipt has an invalid SHA-256")
    try:
        canonical_rows = json.loads(canonical_json)
    except json.JSONDecodeError as error:
        raise RuntimeError("memory ABI receipt has invalid canonical JSON") from error
    if canonical_rows != rows:
        raise RuntimeError("memory ABI receipt canonical JSON does not match its rows")
    if json.dumps(rows, sort_keys=True, separators=(",", ":")) != canonical_json:
        raise RuntimeError("memory ABI receipt JSON is not canonical")
    if hashlib.sha256(canonical_json.encode("utf-8")).hexdigest() != digest:
        raise RuntimeError("memory ABI receipt SHA-256 does not match canonical JSON")
    if len(rows) != MEMORY_PORT_COUNT:
        raise RuntimeError("memory ABI receipt must contain all 146 ports")
    required_row_keys = {
        "number",
        "width",
        "depth",
        "kind",
        "write_enable_sha256",
    }
    for expected_number, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != required_row_keys:
            raise RuntimeError("memory ABI receipt has a malformed port row")
        if (
            not isinstance(row["number"], int)
            or isinstance(row["number"], bool)
            or row["number"] != expected_number
        ):
            raise RuntimeError("memory ABI receipt port rows are not ordered 0 through 145")
        for field in ("width", "depth"):
            value = row[field]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise RuntimeError(f"memory ABI receipt has invalid {field}")
        if row["kind"] != _expected_memory_kind(expected_number):
            raise RuntimeError("memory ABI receipt has a changed memory classification")
        if not isinstance(row["write_enable_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", row["write_enable_sha256"]
        ):
            raise RuntimeError("memory ABI receipt has an invalid write-enable digest")
    token = rows[TOKEN_PORT]
    output = rows[OUTPUT_PORT]
    if (token["width"], token["depth"]) != (64, 8):
        raise RuntimeError("memory ABI receipt has wrong token dimensions")
    if (output["width"], output["depth"]) != (8, 64):
        raise RuntimeError("memory ABI receipt has wrong output dimensions")
    return receipt


def _flat_memref_element_type(type_text: str) -> tuple[list[int], str]:
    parts = type_text.strip().split("x")
    element_type = parts[-1]
    dimensions = parts[:-1]
    if any(not re.fullmatch(r"[1-9][0-9]*", dimension) for dimension in dimensions):
        raise RuntimeError(f"unsupported global memref shape: {type_text}")
    return [int(dimension) for dimension in dimensions], element_type


def _parse_flat_scf_f32_globals(source: str) -> dict[str, dict]:
    """Parse source globals without interpreting textual floating-point values."""

    resource_pattern = re.compile(
        r'(?m)^\s*(?P<name>[A-Za-z_.$][A-Za-z0-9_.$-]*)\s*:\s*'
        r'"(?P<hex>0x[0-9A-Fa-f]+)"\s*,?\s*$'
    )
    resources: dict[str, str] = {}
    for match in resource_pattern.finditer(source):
        name = match.group("name")
        if name in resources:
            raise RuntimeError(f"duplicate dense resource definition: {name}")
        resources[name] = match.group("hex")

    declaration_pattern = re.compile(
        r'(?m)^\s*memref\.global\b[^\n]*?'
        r'@(?P<symbol>[A-Za-z_.$][A-Za-z0-9_.$-]*)\s*:\s*'
        r'memref<(?P<type>[^>]+)>\s*=\s*'
        r'(?P<initializer>dense_resource<[^>]+>|dense<[^>]+>)'
    )
    globals_by_symbol: dict[str, dict] = {}
    for match in declaration_pattern.finditer(source):
        symbol = match.group("symbol")
        if symbol in globals_by_symbol:
            raise RuntimeError(f"duplicate source global: {symbol}")
        shape, element_type = _flat_memref_element_type(match.group("type"))
        globals_by_symbol[symbol] = {
            "symbol": symbol,
            "shape": shape,
            "element_type": element_type,
            "initializer": match.group("initializer").strip(),
            "resources": resources,
        }
    if not globals_by_symbol:
        raise RuntimeError("flat-SCF contains no supported memref globals")
    return globals_by_symbol


def _source_global_raw_f32(global_info: dict) -> bytes:
    if global_info["element_type"] != "f32":
        raise RuntimeError(f"source global @{global_info['symbol']} is not f32")
    shape = global_info["shape"]
    initializer = global_info["initializer"]
    expected_payload_bytes = 4 * math.prod(shape)
    resource = re.fullmatch(
        r"dense_resource<([A-Za-z_.$][A-Za-z0-9_.$-]*)>", initializer
    )
    if resource is not None:
        resource_name = resource.group(1)
        try:
            encoded = global_info["resources"][resource_name]
        except KeyError as error:
            raise RuntimeError(
                f"source global @{global_info['symbol']} references a missing dense resource"
            ) from error
        try:
            framed = bytes.fromhex(encoded[2:])
        except ValueError as error:
            raise RuntimeError("dense resource has malformed hexadecimal bytes") from error
        if not framed.startswith(b"\x04\x00\x00\x00"):
            raise RuntimeError("dense resource has malformed f32 framing")
        if len(framed) != 4 + expected_payload_bytes:
            raise RuntimeError("dense resource payload length does not match its f32 shape")
        return framed[4:]
    if shape == [] and initializer in ("dense<0.000000e+00>", "dense<0.0>"):
        return b"\x00\x00\x00\x00"
    raise RuntimeError(
        f"source global @{global_info['symbol']} has an unsupported inline f32 initializer"
    )


def _parse_pre_calyx_f32_get_globals(lowered: str) -> list[tuple[str, list[int]]]:
    pattern = re.compile(
        r"(?m)^\s*%(?P<result>[0-9]+)\s*=\s*memref\.get_global\s+"
        r"@(?P<symbol>[A-Za-z_.$][A-Za-z0-9_.$-]*)\s*:\s*"
        r"memref<(?P<type>[^>]+)>\s*$"
    )
    matches = list(pattern.finditer(lowered))
    if len(matches) != lowered.count("memref.get_global"):
        raise RuntimeError("pre-Calyx contains a malformed or unsupported get_global")
    results = [int(match.group("result")) for match in matches]
    if results != list(range(len(matches))):
        raise RuntimeError("pre-Calyx get_global results are not ordered from zero")
    ordered: list[tuple[str, list[int]]] = []
    for match in matches:
        shape, element_type = _flat_memref_element_type(match.group("type"))
        if element_type != "f32":
            raise RuntimeError("pre-Calyx external get_global is not f32")
        ordered.append((match.group("symbol"), shape))
    return ordered


def _matching_image_f32_aliases(raw: bytes, image: bytes, manifest: dict) -> list[str]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("segments"), list):
        raise RuntimeError("image manifest has malformed segments")
    aliases: list[str] = []
    seen_names: set[str] = set()
    for segment in manifest["segments"]:
        if not isinstance(segment, dict):
            raise RuntimeError("image manifest contains a malformed segment")
        name = segment.get("name")
        if not isinstance(name, str) or not name or name in seen_names:
            raise RuntimeError("image manifest segment names must be unique strings")
        seen_names.add(name)
        if (
            segment.get("source_category") != "state"
            or segment.get("dtype") != "float32"
        ):
            continue
        offset = segment.get("offset")
        byte_length = segment.get("byte_length")
        shape = segment.get("shape")
        if (
            not isinstance(offset, int) or isinstance(offset, bool) or offset < 0
            or not isinstance(byte_length, int) or isinstance(byte_length, bool)
            or byte_length < 0
            or not isinstance(shape, list)
            or any(
                not isinstance(dimension, int)
                or isinstance(dimension, bool)
                or dimension <= 0
                for dimension in shape
            )
            or byte_length != 4 * math.prod(shape)
            or offset + byte_length > len(image)
        ):
            raise RuntimeError("image manifest has a malformed float32 state segment")
        if byte_length == len(raw) and image[offset : offset + byte_length] == raw:
            aliases.append(name)
    return sorted(aliases)


def _canonical_calyx_memory_bindings(
    rows: list[dict],
    flat_scf: bytes,
    pre_calyx: bytes,
    image: bytes,
    manifest: dict,
    abi: dict[int, MemoryPort],
    manifest_bytes: bytes | None = None,
) -> dict:
    """Return a binding receipt tied to the exact manifest artifact when supplied."""

    if manifest_bytes is None:
        # Isolated in-memory callers have no source artifact to retain.  Strict
        # equivalence always supplies its exact --manifest bytes below.
        manifest_bytes = json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    elif not isinstance(manifest_bytes, bytes):
        raise RuntimeError("Calyx memory binding manifest bytes must be bytes")
    else:
        try:
            decoded_manifest = json.loads(manifest_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "Calyx memory binding manifest bytes are not valid JSON"
            ) from error
        if decoded_manifest != manifest:
            raise RuntimeError(
                "Calyx memory binding manifest bytes do not match decoded manifest"
            )
    payload = {
        "schema": CALYX_MEMORY_BINDINGS_SCHEMA,
        "flat_scf_sha256": _sha256_bytes(flat_scf),
        "pre_calyx_sha256": _sha256_bytes(pre_calyx),
        "image_sha256": _sha256_bytes(image),
        "image_manifest_sha256": _sha256_bytes(manifest_bytes),
        "memory_abi_sha256": _memory_abi_receipt(abi)["sha256"],
        "ports": rows,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    receipt = {
        **payload,
        "canonical_json": canonical_json,
        "sha256": _sha256_bytes(canonical_json.encode("utf-8")),
    }
    return _validate_calyx_memory_bindings_receipt(receipt)


def _build_calyx_memory_bindings(
    *,
    flat_scf: bytes,
    pre_calyx: bytes,
    image: bytes,
    manifest: dict,
    abi: dict[int, MemoryPort],
    manifest_bytes: bytes | None = None,
) -> dict:
    try:
        source = flat_scf.decode("utf-8")
        lowered = pre_calyx.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("source IR must be valid UTF-8") from error
    globals_by_symbol = _parse_flat_scf_f32_globals(source)
    ordered = _parse_pre_calyx_f32_get_globals(lowered)
    if len(ordered) != 19:
        raise RuntimeError("pre-Calyx must externalize exactly 19 f32 globals")
    rows = []
    for ordinal, (symbol, lowered_shape) in enumerate(ordered):
        port = 27 + ordinal
        try:
            global_info = globals_by_symbol[symbol]
        except KeyError as error:
            raise RuntimeError(f"pre-Calyx references missing source global @{symbol}") from error
        initializer = global_info["initializer"]
        if port == 27:
            if global_info["shape"] != [] or initializer not in (
                "dense<0.000000e+00>", "dense<0.0>"
            ):
                raise RuntimeError("port 27 must be the exact inline scalar f32 zero")
        elif not initializer.startswith("dense_resource<"):
            raise RuntimeError("inline f32 zero is supported only at port 27")
        source_shape = global_info["shape"]
        if source_shape == lowered_shape:
            shape_transform = "identity"
        elif source_shape and lowered_shape == [math.prod(source_shape)]:
            shape_transform = "contiguous-flatten"
        else:
            raise RuntimeError(
                "pre-Calyx f32 shape disagrees with supported source shape transform"
            )
        if port == 27 and shape_transform != "identity":
            raise RuntimeError("port 27 scalar shape transform must be identity")
        raw = _source_global_raw_f32(global_info)
        if len(raw) != 4 * math.prod(lowered_shape):
            raise RuntimeError("pre-Calyx f32 shape disagrees with source bytes")
        try:
            abi_port = abi[port]
        except KeyError as error:
            raise RuntimeError(f"SV ABI is missing external f32 port {port}") from error
        if abi_port.width != 32 or abi_port.depth < len(raw) // 4:
            raise RuntimeError("SV ABI cannot hold external f32 global")
        aliases = _matching_image_f32_aliases(raw, image, manifest)
        if not aliases and port != 27:
            raise RuntimeError("external f32 global has no byte-identical image segment")
        rows.append({
            "port": port,
            "ordinal": ordinal,
            "global": symbol,
            "source_shape": source_shape,
            "lowered_shape": lowered_shape,
            "shape_transform": shape_transform,
            "word_count": len(raw) // 4,
            "words_u32": [
                int.from_bytes(raw[index : index + 4], "little")
                for index in range(0, len(raw), 4)
            ],
            "raw_sha256": _sha256_bytes(raw),
            "image_segment_aliases": aliases,
        })
    return _canonical_calyx_memory_bindings(
        rows, flat_scf, pre_calyx, image, manifest, abi, manifest_bytes
    )


def _validate_calyx_memory_bindings_receipt(receipt: object) -> dict:
    if not isinstance(receipt, dict):
        raise RuntimeError("Calyx memory binding receipt must be an object")
    payload_keys = {
        "schema", "flat_scf_sha256", "pre_calyx_sha256", "image_sha256",
        "image_manifest_sha256", "memory_abi_sha256", "ports",
    }
    if set(receipt) != payload_keys | {"canonical_json", "sha256"}:
        raise RuntimeError("Calyx memory binding receipt has an unexpected schema")
    if receipt["schema"] != CALYX_MEMORY_BINDINGS_SCHEMA:
        raise RuntimeError("Calyx memory binding receipt has an unsupported schema")
    for field in (
        "flat_scf_sha256", "pre_calyx_sha256", "image_sha256",
        "image_manifest_sha256", "memory_abi_sha256", "sha256",
    ):
        if not isinstance(receipt[field], str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt[field]
        ):
            raise RuntimeError(f"Calyx memory binding receipt has invalid {field}")
    canonical_json = receipt["canonical_json"]
    if not isinstance(canonical_json, str):
        raise RuntimeError("Calyx memory binding receipt has malformed canonical JSON")
    payload = {key: receipt[key] for key in payload_keys}
    try:
        decoded = json.loads(canonical_json)
    except json.JSONDecodeError as error:
        raise RuntimeError("Calyx memory binding receipt has invalid canonical JSON") from error
    if decoded != payload:
        raise RuntimeError("Calyx memory binding receipt canonical JSON does not match its rows")
    if json.dumps(payload, sort_keys=True, separators=(",", ":")) != canonical_json:
        raise RuntimeError("Calyx memory binding receipt JSON is not canonical")
    if _sha256_bytes(canonical_json.encode("utf-8")) != receipt["sha256"]:
        raise RuntimeError("Calyx memory binding receipt SHA-256 does not match canonical JSON")
    rows = receipt["ports"]
    if not isinstance(rows, list) or len(rows) != 19:
        raise RuntimeError("Calyx memory binding receipt must contain ports 27 through 45")
    row_keys = {
        "port", "ordinal", "global", "source_shape", "lowered_shape",
        "shape_transform", "word_count", "words_u32", "raw_sha256",
        "image_segment_aliases",
    }
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != row_keys:
            raise RuntimeError("Calyx memory binding receipt has a malformed port row")
        if row["port"] != 27 + ordinal or row["ordinal"] != ordinal:
            raise RuntimeError("Calyx memory binding receipt rows are not ordered by port")
        if not isinstance(row["global"], str) or not re.fullmatch(
            r"[A-Za-z_.$][A-Za-z0-9_.$-]*", row["global"]
        ):
            raise RuntimeError("Calyx memory binding receipt has an invalid global symbol")
        source_shape = row["source_shape"]
        lowered_shape = row["lowered_shape"]
        if any(
            not isinstance(shape, list)
            or any(
                not isinstance(dimension, int)
                or isinstance(dimension, bool)
                or dimension <= 0
                for dimension in shape
            )
            for shape in (source_shape, lowered_shape)
        ):
            raise RuntimeError("Calyx memory binding receipt has an invalid shape")
        if source_shape == lowered_shape:
            expected_shape_transform = "identity"
        elif source_shape and lowered_shape == [math.prod(source_shape)]:
            expected_shape_transform = "contiguous-flatten"
        else:
            raise RuntimeError(
                "Calyx memory binding receipt has an unsupported shape transform"
            )
        if row["shape_transform"] != expected_shape_transform or (
            row["port"] == 27 and expected_shape_transform != "identity"
        ):
            raise RuntimeError(
                "Calyx memory binding receipt has an invalid shape transform"
            )
        words = row["words_u32"]
        word_count = row["word_count"]
        if (
            not isinstance(word_count, int) or isinstance(word_count, bool)
            or word_count != math.prod(source_shape)
            or word_count != math.prod(lowered_shape)
            or not isinstance(words, list) or len(words) != word_count
            or any(
                not isinstance(word, int) or isinstance(word, bool)
                or not 0 <= word <= 0xFFFFFFFF
                for word in words
            )
        ):
            raise RuntimeError("Calyx memory binding receipt has malformed f32 words")
        raw = b"".join(word.to_bytes(4, "little") for word in words)
        if row["raw_sha256"] != _sha256_bytes(raw):
            raise RuntimeError("Calyx memory binding receipt has a wrong raw SHA-256")
        aliases = row["image_segment_aliases"]
        if (
            not isinstance(aliases, list)
            or any(not isinstance(alias, str) or not alias for alias in aliases)
            or aliases != sorted(set(aliases))
            or (not aliases and row["port"] != 27)
        ):
            raise RuntimeError("Calyx memory binding receipt has malformed image aliases")
    return receipt


def _context_index(token_ids: list[int]) -> int:
    if len(token_ids) != CONTEXT_LENGTH or any(
        not isinstance(token, int) or token < 0 or token >= VOCAB_SIZE
        for token in token_ids
    ):
        raise RuntimeError(
            f"token context must contain exactly {CONTEXT_LENGTH} values in [0, {VOCAB_SIZE})"
        )
    index = 0
    for token in token_ids:
        index = index * VOCAB_SIZE + token
    return index


def _ports(source: str) -> dict[int, tuple[int, int]]:
    result: dict[int, tuple[int, int]] = {}
    pattern = re.compile(
        r"(?:input|output) logic(?: \[(\d+):(\d+)\])? arg_mem_(\d+)_(addr0|read_data)"
    )
    widths: dict[int, dict[str, int]] = {}
    for hi, lo, number, kind in pattern.findall(source):
        width = int(hi) - int(lo) + 1 if hi else 1
        widths.setdefault(int(number), {})[kind] = width
    for number, values in widths.items():
        if "addr0" in values and "read_data" in values:
            result[number] = (values["read_data"], 1 << values["addr0"])
    return result


def _hex_words(payload: bytes, width: int, depth: int) -> list[str]:
    byte_width = (width + 7) // 8
    return [
        int.from_bytes(
            payload[i * byte_width : (i + 1) * byte_width].ljust(byte_width, b"\0"),
            "little",
        ).to_bytes(byte_width, "big").hex()
        for i in range(depth)
    ]


def _case_index(reference: dict, case_id: str) -> int:
    for index, case in enumerate(reference["results"]):
        if case["case_id"] == case_id:
            return index
    raise RuntimeError(f"unknown reference case: {case_id}")


def _runtime_args(args: argparse.Namespace, reference: dict) -> list[str]:
    result = [
        f"+heartbeat_cycles={args.heartbeat_cycles}",
        f"+timeout_cycles={args.timeout_cycles}",
        f"+stop_after_output={int(args.stop_after_output)}",
        f"+trace_output_writes={int(args.trace_output_writes)}",
    ]
    if args.case_id is not None and not getattr(args, "static_fixture_case", False):
        result.append(f"+case_index={_case_index(reference, args.case_id)}")
    return result


def _fixture_cache_identity(args: argparse.Namespace) -> dict[str, str | None]:
    if (
        getattr(args, "equivalence_shard", None) is not None
        or getattr(args, "equivalence_sequence", None) is not None
    ):
        # The oracle is runtime data.  Binding a particular shard here would
        # force a recompilation for every proof partition and make a cache hit
        # misleadingly depend on payload rather than fixture behavior.
        return {
            "mode": "observable-shard-generic",
            "fixture_schema": STRICT_FIXTURE_SCHEMA,
        }
    static_fixture_case = getattr(args, "static_fixture_case", False)
    return {
        "mode": "static-case" if static_fixture_case else "runtime-select",
        "case_id": args.case_id if static_fixture_case else None,
    }


def _materialize_diagnostic_fixture_memories(
    image: bytes,
    manifest: dict,
    root: Path,
    ports: dict[int, tuple[int, int]],
) -> None:
    """Write the frozen image-backed memories shared by both fixture modes."""

    segment_by_name = {s["name"]: s for s in manifest["segments"]}
    for number in range(21):
        name = f"state/_frozen_param{number}"
        segment = segment_by_name[name]
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )
    # The first 25 external memories are the frozen state plus four exported
    # non-parameter constants: one attention mask and one lifted f32 constant
    # per transformer layer.  They are part of the image-backed ABI and must
    # not be left as zero-filled scratch memory.
    constant_segments = {
        21: "state/transformer.h.0.attn.attention.bias",
        22: "state/transformer.h.0.attn.attention.lifted_tensor_0",
        23: "state/transformer.h.1.attn.attention.bias",
        24: "state/transformer.h.1.attn.attention.lifted_tensor_1",
    }
    for number, name in constant_segments.items():
        segment = segment_by_name[name]
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )

    # The remaining read-only argument memories are float state tensors that
    # the lowering kept external.  Their ordering is part of the frozen ABI.
    used_names = set(constant_segments.values())
    external_element_counts = {2, 8, 18, 12}
    remaining = [
        segment
        for segment in manifest["segments"]
        if segment["name"] not in used_names
        and segment["source_category"] == "state"
        and segment["dtype"] == "float32"
        and math.prod(segment["shape"]) in external_element_counts
    ]
    for number in range(28, 46):
        width, depth = ports[number]
        expected_elements = {44: 18, 45: 12}.get(number, depth)
        candidates = [
            segment
            for segment in remaining
            if len(segment["shape"]) > 0
            and math.prod(segment["shape"]) == expected_elements
            and width == 32
        ]
        candidates.sort(key=lambda segment: segment["name"])
        if not candidates:
            raise RuntimeError(
                f"cannot uniquely map constant arg_mem_{number}: "
                f"width={width}, capacity={depth}, candidates="
                f"{[segment['name'] for segment in candidates]}"
            )
        segment = candidates[0]
        remaining.remove(segment)
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )
    if remaining:
        raise RuntimeError(
            f"unmapped external image segments: {[segment['name'] for segment in remaining]}"
        )
    # The ABI reserves arg_mem_27 for a lowered scalar absent from the image.
    (root / "mem27.hex").write_text("00000000\n", encoding="ascii")
    for number in (TOKEN_PORT, OUTPUT_PORT):
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join("0" for _ in range(depth)) + "\n", encoding="ascii"
        )


def _materialize_fixture_memories(
    image: bytes,
    manifest: dict,
    root: Path,
    ports: dict[int, tuple[int, int]],
    calyx_memory_bindings: object,
) -> None:
    """Materialize strict fixture memories from a validated binding receipt."""

    receipt = _validate_calyx_memory_bindings_receipt(calyx_memory_bindings)
    segment_by_name = {segment["name"]: segment for segment in manifest["segments"]}
    for number in range(21):
        name = f"state/_frozen_param{number}"
        segment = segment_by_name[name]
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )
    constant_segments = {
        21: "state/transformer.h.0.attn.attention.bias",
        22: "state/transformer.h.0.attn.attention.lifted_tensor_0",
        23: "state/transformer.h.1.attn.attention.bias",
        24: "state/transformer.h.1.attn.attention.lifted_tensor_1",
    }
    for number, name in constant_segments.items():
        segment = segment_by_name[name]
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )
    for row in receipt["ports"]:
        number = row["port"]
        width, depth = ports[number]
        if width != 32 or depth < row["word_count"]:
            raise RuntimeError("fixture memory dimensions disagree with binding receipt")
        words = [f"{word:08x}" for word in row["words_u32"]]
        words.extend("00000000" for _ in range(depth - len(words)))
        (root / f"mem{number}.hex").write_text(
            "\n".join(words) + "\n", encoding="ascii"
        )
    for number in (TOKEN_PORT, OUTPUT_PORT):
        _, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join("0" for _ in range(depth)) + "\n", encoding="ascii"
        )


def _fixture(
    sv: str,
    image: bytes,
    manifest: dict,
    reference: dict,
    root: Path,
    timeout_cycles: int = 1_000_000,
    heartbeat_cycles: int = 100_000,
    case_id: str | None = None,
    stop_after_output: bool = False,
    trace_output_writes: bool = False,
    static_case_id: str | None = None,
    memory_abi: dict[int, MemoryPort] | None = None,
) -> Path:
    if timeout_cycles <= 0:
        raise ValueError("timeout_cycles must be positive")
    if heartbeat_cycles < 0:
        raise ValueError("heartbeat_cycles must be nonnegative")
    abi = _memory_abi(sv) if memory_abi is None else memory_abi
    abi_receipt = _memory_abi_receipt(abi)
    ports = {
        number: (port.width, port.depth)
        for number, port in sorted(abi.items())
    }
    if set(ports) != set(range(MEMORY_PORT_COUNT)):
        raise RuntimeError("fixture requires a complete frozen 146-port memory ABI")
    (root / "memory-abi.json").write_text(
        abi_receipt["canonical_json"] + "\n", encoding="utf-8"
    )
    _materialize_diagnostic_fixture_memories(image, manifest, root, ports)

    declarations: list[str] = []
    connections: list[str] = []
    initialization: list[str] = []
    for number, (width, depth) in sorted(ports.items()):
        addr_width = max(1, (depth - 1).bit_length())
        declarations += [
            f"logic [{width-1}:0] mem{number} [0:{depth-1}];",
            f"wire [{addr_width-1}:0] a{number}_addr; wire a{number}_en, a{number}_we;",
            f"wire [{width-1}:0] a{number}_wdata; logic [{width-1}:0] a{number}_rdata; logic a{number}_done;",
        ]
        connections += [
            f".arg_mem_{number}_addr0(a{number}_addr), .arg_mem_{number}_content_en(a{number}_en),",
            f".arg_mem_{number}_write_en(a{number}_we), .arg_mem_{number}_write_data(a{number}_wdata),",
            f".arg_mem_{number}_read_data(a{number}_rdata), .arg_mem_{number}_done(a{number}_done),",
        ]
        initialization.append(f"for (int i=0; i<{depth}; i++) mem{number}[i] = '0;")
    memory_enable_terms = " | ".join(f"a{number}_en" for number in sorted(ports))
    for number in range(46):
        initialization.append(f'$readmemh("mem{number}.hex", mem{number});')

    immutable_ports = [
        number for number, port in sorted(abi.items())
        if port.kind in ("image", "token")
    ]
    mutable_ports = [
        number for number, port in sorted(abi.items())
        if port.kind in ("output", "scratch")
    ]
    reset_task = [
        "task automatic reset_transaction(input longint unsigned context_index);",
        "  longint unsigned token_value;",
        "  begin",
        "    reset = 1'b1;",
        "    go = 1'b0;",
        "    timeout_counter = 0;",
    ]
    for number in mutable_ports:
        _, depth = ports[number]
        reset_task.append(f"    for (int i=0; i<{depth}; i++) mem{number}[i] = '0;")
    reset_task += [
        f"    for (int i=0; i<{CONTEXT_LENGTH}; i++) mem{TOKEN_PORT}[i] = '0;",
        "    token_value = context_index;",
        f"    for (int token_slot={CONTEXT_LENGTH - 1}; token_slot>=0; token_slot=token_slot-1) begin",
        f"      mem{TOKEN_PORT}[token_slot] = token_value % {VOCAB_SIZE};",
        f"      token_value = token_value / {VOCAB_SIZE};",
        "    end",
        "    repeat (3) @(posedge clk);",
        "    @(negedge clk);",
        "    reset = 1'b0;",
        "  end",
        "endtask",
    ]

    if case_id is not None:
        _case_index(reference, case_id)
    static_case_index = (
        _case_index(reference, static_case_id)
        if static_case_id is not None
        else None
    )
    case_items = list(enumerate(reference["results"]))
    if static_case_index is not None:
        case_items = [(static_case_index, reference["results"][static_case_index])]
    case_blocks = []
    for index, case in case_items:
        tokens = case["token_ids"]
        expected = case["output_codes_i8"]
        context_index = _context_index(tokens)
        guard = (
            "begin\n"
            if static_case_index is not None
            else f"if (selected_case_index < 0 || selected_case_index == {index}) begin\n"
        )
        case_blocks.append(
            guard
            + f"  reset_transaction(64'd{context_index}); go = 1;\n"
            + f"  timeout_counter = 0; while (!done && timeout_counter < timeout_cycles && (!stop_after_output || output_write_count == 0)) begin @(posedge clk); timeout_counter = timeout_counter + 1; if (heartbeat_cycles > 0) begin if ((timeout_counter % heartbeat_cycles) == 0) $display(\"HEARTBEAT {case['case_id']} cycles=%0d state=%0d inner_state=%0d go_int=%b signal_reg=%b awaited_done=%b mem_en=%b done=%b requests=%0d mem_completions=%0d output_writes=%0d last_port=%0d completions=%0d\", timeout_counter, dut.fsm0_out, dut.fsm_out, dut.tdcc_go_out, dut.signal_reg_out, dut.wrapper_early_reset_static_seq180_done_out, any_mem_en, done, request_count, memory_completion_count, output_write_count, last_request_port, completion_count); end end go = 0; if (!done && output_write_count == 0) begin $display(\"TIMEOUT {case['case_id']} %0d\", timeout_counter); $finish; end repeat (2) @(posedge clk);\n"
            + f'  $display("RESULT {case["case_id"]} %0d %0d %0d %0d %0d %0d", '
            + ", ".join(f"$signed(mem26[{(len(tokens) - 1) * len(expected) + i}])" for i in range(6))
            + ");\n"
            + "end"
        )
    text = (
        "`timescale 1ns/1ps\nmodule tb;\n"
        f"localparam string RC_MEMORY_ABI_SHA256 = \"{abi_receipt['sha256']}\";\n"
        "integer timeout_counter, last_request_port;\n"
        "integer memory_completion_count, output_write_count;\n"
        "logic [5:0] output_write_mask; logic immutable_write_seen;\n"
        + "\n".join(declarations)
        + "\n"
    )
    text += f"integer timeout_cycles = {timeout_cycles}; integer heartbeat_cycles = {heartbeat_cycles}; "
    if static_case_index is None:
        text += "integer selected_case_index = -1; "
    text += (
        f"integer stop_after_output = {int(stop_after_output)}; "
        f"integer trace_output_writes = {int(trace_output_writes)};\n"
    )
    text += "logic clk=0, reset=0, go=0; wire done; integer request_count=0, completion_count=0; wire any_mem_en = " + memory_enable_terms + "; always #5 clk=~clk;\n"
    text += "\n".join(reset_task) + "\n"
    text += "always_ff @(posedge clk) begin\n"
    text += "  if (reset) begin output_write_count <= 0; last_request_port <= -1; output_write_mask <= '0; immutable_write_seen <= 1'b0; end\n"
    for n in ports:
        text += f"  if (reset) begin a{n}_done <= 1'b0; a{n}_rdata <= '0; end\n"
        if n in immutable_ports:
            text += (
                f"  else if (a{n}_en && a{n}_we) begin immutable_write_seen <= 1'b1; "
                f'$display("IMMUTABLE_WRITE port={n} addr=%0d", a{n}_addr); '
                f'$fatal(1, "DUT attempted write to immutable port {n}"); end\n'
            )
        text += f"  else if (a{n}_en) begin a{n}_done <= 1'b1; last_request_port <= {n};"
        text += f" if (!a{n}_we) a{n}_rdata <= mem{n}[a{n}_addr];"
        if n == 26:
            text += " else begin mem26[a26_addr] <= a26_wdata; output_write_count <= output_write_count + 1; if (a26_addr >= 6'd42 && a26_addr < 6'd48) output_write_mask <= output_write_mask | (6'b000001 << (a26_addr - 6'd42)); if (trace_output_writes != 0) $display(\"OUTWRITE addr=%0d data=%0d\", a26_addr, $signed(a26_wdata)); end end\n"
        else:
            text += f" else mem{n}[a{n}_addr] <= a{n}_wdata; end\n"
        text += f"  else a{n}_done <= 1'b0;\n"
    text += "end\n"
    text += "always_ff @(posedge clk) begin\n"
    text += "  if (reset) begin request_count <= 0; completion_count <= 0; memory_completion_count <= 0; end\n"
    text += "  else begin if (any_mem_en) request_count <= request_count + 1; if (done) completion_count <= completion_count + 1; if (" + " | ".join(f"a{n}_done" for n in ports) + ") memory_completion_count <= memory_completion_count + 1; end\n"
    text += "end\n"
    connections[-1] = connections[-1].rstrip(",")
    text += "main_1 dut(.clk(clk), .reset(reset), .go(go), .done(done),\n" + "\n".join(connections) + ");\n"
    text += "initial begin\n"
    text += "  $display(\"ABI_RECEIPT sha256=%s\", RC_MEMORY_ABI_SHA256);\n"
    text += "  if ($value$plusargs(\"timeout_cycles=%d\", timeout_cycles) && timeout_cycles <= 0) timeout_cycles = 1;\n"
    text += "  if ($value$plusargs(\"heartbeat_cycles=%d\", heartbeat_cycles) && heartbeat_cycles < 0) heartbeat_cycles = 0;\n"
    if static_case_index is None:
        text += (
            "  if ($value$plusargs(\"case_index=%d\", selected_case_index) "
            f"&& (selected_case_index < -1 || selected_case_index >= {len(reference['results'])})) selected_case_index = -1;\n"
        )
    text += "  if ($value$plusargs(\"stop_after_output=%d\", stop_after_output)) stop_after_output = (stop_after_output != 0);\n"
    text += "  if ($value$plusargs(\"trace_output_writes=%d\", trace_output_writes)) trace_output_writes = (trace_output_writes != 0);\n"
    text += "  " + "\n  ".join(initialization)
    text += "\n  " + "\n  ".join(case_blocks)
    text += "\n  $finish;\nend\nendmodule\n"
    path = root / "tb.sv"
    path.write_text(text, encoding="utf-8")
    return path


def _strict_fixture(
    sv: str,
    image: bytes,
    manifest: dict,
    root: Path,
    *,
    cycle_bound: int,
    calyx_memory_bindings: dict,
    memory_abi: dict[int, MemoryPort] | None = None,
) -> Path:
    """Render the payload-neutral, runtime-streamed observable-shard fixture.

    Unlike :func:`_fixture`, this path deliberately takes no reference JSON or
    case IDs.  The only context-specific data reaches the compiled model as
    an oracle file plus shard range at runtime.
    """

    if cycle_bound <= 0:
        raise ValueError("cycle_bound must be positive")
    abi = _memory_abi(sv) if memory_abi is None else memory_abi
    abi_receipt = _memory_abi_receipt(abi)
    calyx_memory_bindings = _validate_calyx_memory_bindings_receipt(
        calyx_memory_bindings
    )
    ports = {
        number: (port.width, port.depth)
        for number, port in sorted(abi.items())
    }
    if set(ports) != set(range(MEMORY_PORT_COUNT)):
        raise RuntimeError("fixture requires a complete frozen 146-port memory ABI")
    (root / "memory-abi.json").write_text(
        abi_receipt["canonical_json"] + "\n", encoding="utf-8"
    )
    _materialize_fixture_memories(
        image, manifest, root, ports, calyx_memory_bindings
    )

    declarations: list[str] = []
    connections: list[str] = []
    initialization: list[str] = []
    for number, (width, depth) in sorted(ports.items()):
        addr_width = max(1, (depth - 1).bit_length())
        declarations += [
            f"logic [{width - 1}:0] mem{number} [0:{depth - 1}];",
            f"wire [{addr_width - 1}:0] a{number}_addr; wire a{number}_en, a{number}_we;",
            f"wire [{width - 1}:0] a{number}_wdata; logic [{width - 1}:0] a{number}_rdata; logic a{number}_done;",
        ]
        connections += [
            f".arg_mem_{number}_addr0(a{number}_addr), .arg_mem_{number}_content_en(a{number}_en),",
            f".arg_mem_{number}_write_en(a{number}_we), .arg_mem_{number}_write_data(a{number}_wdata),",
            f".arg_mem_{number}_read_data(a{number}_rdata), .arg_mem_{number}_done(a{number}_done),",
        ]
        initialization.append(f"for (int i=0; i<{depth}; i++) mem{number}[i] = '0;")
    for number in range(46):
        initialization.append(f'$readmemh("mem{number}.hex", mem{number});')
    memory_enable_terms = " | ".join(f"a{number}_en" for number in sorted(ports))
    immutable_ports = [
        number for number, port in sorted(abi.items())
        if port.kind in ("image", "token")
    ]
    mutable_ports = [
        number for number, port in sorted(abi.items())
        if port.kind in ("output", "scratch")
    ]
    reset_task = [
        "task automatic reset_transaction(input longint unsigned next_context_index);",
        "  longint unsigned token_value;",
        "  begin",
        "    reset = 1'b1;",
        "    go = 1'b0;",
        "    timeout_counter = 0;",
        "    settling = 1'b0;",
    ]
    for number in mutable_ports:
        _, depth = ports[number]
        reset_task.append(f"    for (int i=0; i<{depth}; i++) mem{number}[i] = '0;")
    reset_task += [
        f"    for (int i=0; i<{CONTEXT_LENGTH}; i++) mem{TOKEN_PORT}[i] = '0;",
        "    token_value = next_context_index;",
        f"    for (int token_slot={CONTEXT_LENGTH - 1}; token_slot>=0; token_slot=token_slot-1) begin",
        f"      mem{TOKEN_PORT}[token_slot] = token_value % {VOCAB_SIZE};",
        f"      token_value = token_value / {VOCAB_SIZE};",
        "    end",
        "    repeat (3) @(posedge clk);",
        "    @(negedge clk);",
        "    reset = 1'b0;",
        "  end",
        "endtask",
    ]

    text = (
        "`timescale 1ns/1ps\nmodule tb;\n"
        f"localparam string RC_MEMORY_ABI_SHA256 = \"{abi_receipt['sha256']}\";\n"
        f"localparam string RC_CALYX_MEMORY_BINDINGS_SHA256 = \"{calyx_memory_bindings['sha256']}\";\n"
        f"localparam string RC_OBSERVABLE_FIXTURE_SCHEMA = \"{STRICT_FIXTURE_SCHEMA}\";\n"
        "integer timeout_counter, last_request_port;\n"
        "integer memory_completion_count, output_write_count;\n"
        "logic [5:0] final_write_mask, final_write_mask_before_settle;\n"
        "logic immutable_write_seen, settling, late_final_write, done_seen;\n"
        "logic [63:0] expected_record, trailing_record;\n"
        "logic signed [7:0] best_code;\n"
        "longint unsigned shard_start, shard_count, sequence_count, record_count, context_index, ordinal;\n"
        "longint unsigned clock_cycle = 0, launch_cycle, done_cycle;\n"
        "longint unsigned case_cycles, min_cycles, max_cycles;\n"
        "integer oracle_fd, oracle_scan_status, context_index_fd, context_index_scan_status, lane, best_index, completed_cases, completion_count_at_done;\n"
        "logic sequence_mode;\n"
        "string oracle_path, context_index_path;\n"
        + "\n".join(declarations)
        + "\n"
    )
    text += f"integer cycle_bound = {cycle_bound};\n"
    text += (
        "logic clk=0, reset=0, go=0; wire done; integer request_count=0, completion_count=0; "
        f"wire any_mem_en = {memory_enable_terms}; always #5 clk=~clk;\n"
    )
    text += "\n".join(reset_task) + "\n"
    text += "task automatic case_fail(input string reason);\n"
    text += "  begin\n"
    text += (
        '    $display("CASE_FAIL index=%0d reason=%s cycles=%0d expected_codes=%0d,%0d,%0d,%0d,%0d,%0d observed_codes=%0d,%0d,%0d,%0d,%0d,%0d expected_token=%0d observed_token=%0d write_mask=%b", '
        "context_index, reason, case_cycles, $signed(expected_record[7:0]), $signed(expected_record[15:8]), $signed(expected_record[23:16]), $signed(expected_record[31:24]), $signed(expected_record[39:32]), $signed(expected_record[47:40]), $signed(mem26[42]), $signed(mem26[43]), $signed(mem26[44]), $signed(mem26[45]), $signed(mem26[46]), $signed(mem26[47]), expected_record[55:48], best_index, final_write_mask);\n"
    )
    text += '    $fatal(1, "observable shard case failed: %s", reason);\n'
    text += "  end\nendtask\n"
    text += "always_ff @(posedge clk) begin clock_cycle <= clock_cycle + 1; end\n"
    text += "always @(posedge clk) begin\n"
    text += (
        "  if (reset) begin output_write_count <= 0; last_request_port <= -1; "
        "final_write_mask <= '0; immutable_write_seen <= 1'b0; late_final_write <= 1'b0; end\n"
    )
    for number in ports:
        text += f"  if (reset) begin a{number}_done <= 1'b0; a{number}_rdata <= '0; end\n"
        if number in immutable_ports:
            text += (
                f"  else if (a{number}_en && a{number}_we) begin immutable_write_seen <= 1'b1; "
                f'$display("IMMUTABLE_WRITE port={number} addr=%0d", a{number}_addr); '
                f'$fatal(1, "DUT attempted write to immutable port {number}"); end\n'
            )
        text += f"  else if (a{number}_en) begin a{number}_done <= 1'b1; last_request_port <= {number};"
        text += f" if (!a{number}_we) a{number}_rdata <= mem{number}[a{number}_addr];"
        if number == OUTPUT_PORT:
            text += (
                " else begin mem26[a26_addr] <= a26_wdata; output_write_count <= output_write_count + 1; "
                "if (a26_addr >= 6'd42 && a26_addr < 6'd48) begin "
                "final_write_mask <= final_write_mask | (6'b000001 << (a26_addr - 6'd42)); "
                "if (settling) late_final_write <= 1'b1; end end end\n"
            )
        else:
            text += f" else mem{number}[a{number}_addr] <= a{number}_wdata; end\n"
        text += f"  else a{number}_done <= 1'b0;\n"
    text += "end\n"
    text += "always_ff @(posedge clk) begin\n"
    text += "  if (reset) begin request_count <= 0; completion_count <= 0; memory_completion_count <= 0; end\n"
    text += (
        "  else begin if (any_mem_en) request_count <= request_count + 1; "
        "if (done) completion_count <= completion_count + 1; if ("
        + " | ".join(f"a{number}_done" for number in ports)
        + ") memory_completion_count <= memory_completion_count + 1; end\n"
    )
    text += "end\n"
    connections[-1] = connections[-1].rstrip(",")
    text += "main_1 dut(.clk(clk), .reset(reset), .go(go), .done(done),\n" + "\n".join(connections) + ");\n"
    text += "initial begin\n"
    text += "  $display(\"ABI_RECEIPT sha256=%s fixture=%s\", RC_MEMORY_ABI_SHA256, RC_OBSERVABLE_FIXTURE_SCHEMA);\n"
    text += "  " + "\n  ".join(initialization) + "\n"
    text += "  if (!$value$plusargs(\"oracle_file=%s\", oracle_path)) begin context_index = 0; case_cycles = 0; case_fail(\"MISSING_ORACLE_FILE\"); end\n"
    text += "  sequence_mode = $value$plusargs(\"context_index_file=%s\", context_index_path);\n"
    text += "  if (sequence_mode) begin\n"
    text += "    if (!$value$plusargs(\"sequence_count=%d\", sequence_count) || sequence_count == 0) begin context_index = 0; case_cycles = 0; case_fail(\"INVALID_SEQUENCE_COUNT\"); end\n"
    text += '    context_index_fd = $fopen(context_index_path, "r");\n'
    text += "    if (context_index_fd == 0) begin context_index = 0; case_cycles = 0; case_fail(\"CONTEXT_INDEX_OPEN_FAILED\"); end\n"
    text += "    record_count = sequence_count; shard_start = 0; shard_count = 0;\n"
    text += "  end else begin\n"
    text += "    if (!$value$plusargs(\"shard_start=%d\", shard_start)) begin context_index = 0; case_cycles = 0; case_fail(\"MISSING_SHARD_START\"); end\n"
    text += "    if (!$value$plusargs(\"shard_count=%d\", shard_count) || shard_count == 0) begin context_index = shard_start; case_cycles = 0; case_fail(\"INVALID_SHARD_COUNT\"); end\n"
    text += "    record_count = shard_count; sequence_count = 0; context_index_fd = 0;\n"
    text += "  end\n"
    text += "  if (!$value$plusargs(\"cycle_bound=%d\", cycle_bound) || cycle_bound <= 0) begin context_index = shard_start; case_cycles = 0; case_fail(\"INVALID_CYCLE_BOUND\"); end\n"
    text += '  oracle_fd = $fopen(oracle_path, "r");\n'
    text += "  if (oracle_fd == 0) begin context_index = shard_start; case_cycles = 0; case_fail(\"ORACLE_OPEN_FAILED\"); end\n"
    text += "  completed_cases = 0; min_cycles = 0; max_cycles = 0;\n"
    text += "  for (ordinal = 0; ordinal < record_count; ordinal = ordinal + 1) begin\n"
    text += "    if (sequence_mode) begin context_index_scan_status = $fscanf(context_index_fd, \"%d\", context_index); if (context_index_scan_status != 1) begin context_index = 0; case_cycles = 0; case_fail(\"CONTEXT_INDEX_MISSING_OR_MALFORMED\"); end end else context_index = shard_start + ordinal;\n"
    text += "    case_cycles = 0; launch_cycle = 0; done_cycle = 0; done_seen = 1'b0; completion_count_at_done = 0; expected_record = '0;\n"
    text += '    oracle_scan_status = $fscanf(oracle_fd, "%h", expected_record);\n'
    text += "    if (oracle_scan_status != 1) case_fail(\"ORACLE_RECORD_MISSING_OR_MALFORMED\");\n"
    text += "    if (expected_record[63:56] !== 8'd0) case_fail(\"ORACLE_RECORD_RESERVED_BITS\");\n"
    text += "    if (expected_record[55:48] >= 8'd6) case_fail(\"ORACLE_RECORD_TOKEN_RANGE\");\n"
    text += "    best_index = 0; best_code = $signed(expected_record[7:0]);\n"
    text += "    for (lane = 1; lane < 6; lane = lane + 1) begin if ($signed(expected_record[8*lane +: 8]) > best_code) begin best_code = $signed(expected_record[8*lane +: 8]); best_index = lane; end end\n"
    text += "    if (best_index != expected_record[55:48]) case_fail(\"ORACLE_RECORD_ARGMAX\");\n"
    text += "    reset_transaction(context_index);\n"
    text += "    launch_cycle = clock_cycle;\n"
    text += "    go = 1'b1;\n"
    text += "    while (!done && case_cycles < cycle_bound) begin @(posedge clk); case_cycles = case_cycles + 1; if (heartbeat_cycles > 0 && (case_cycles % heartbeat_cycles) == 0) $display(\"HEARTBEAT context=%0d cycles=%0d done=%0d clock=%0d\", context_index, case_cycles, done, clock_cycle); end\n"
    text += "    if (!done) case_fail(\"TIMEOUT\");\n"
    text += "    done_seen = done;\n"
    text += "    go = 1'b0;\n"
    text += "    @(negedge clk);\n"
    text += "    done_cycle = clock_cycle;\n"
    text += "    completion_count_at_done = completion_count;\n"
    text += "    if (immutable_write_seen) case_fail(\"IMMUTABLE_WRITE\");\n"
    text += "    if (!(final_write_mask == 6'b111111)) case_fail(\"MISSING_FINAL_WRITE\");\n"
    text += "    final_write_mask_before_settle = final_write_mask; settling = 1'b1;\n"
    text += "    repeat (2) @(posedge clk);\n"
    text += "    @(negedge clk); settling = 1'b0;\n"
    text += "    if (late_final_write || final_write_mask != final_write_mask_before_settle) case_fail(\"LATE_FINAL_WRITE\");\n"
    text += "    best_index = 0; best_code = $signed(mem26[42]);\n"
    text += "    for (lane = 0; lane < 6; lane = lane + 1) begin\n"
    text += "      if ($signed(mem26[42 + lane]) !== $signed(expected_record[8*lane +: 8])) begin case_fail(\"RAW_CODE\"); end\n"
    text += "      if (lane > 0 && $signed(mem26[42 + lane]) > best_code) begin best_code = $signed(mem26[42 + lane]); best_index = lane; end\n"
    text += "    end\n"
    text += "    if (best_index != expected_record[55:48]) case_fail(\"ARGMAX\");\n"
    text += (
        '    $display("CASE_PASS index=%0d cycles=%0d expected_codes=%0d,%0d,%0d,%0d,%0d,%0d observed_codes=%0d,%0d,%0d,%0d,%0d,%0d expected_token=%0d observed_token=%0d done=%0d completion_count=%0d within_bound=%0d reset_complete=1 reset_cycles=3 reset_ordinal=%0d write_mask=%b", '
        "context_index, case_cycles, $signed(expected_record[7:0]), $signed(expected_record[15:8]), $signed(expected_record[23:16]), $signed(expected_record[31:24]), $signed(expected_record[39:32]), $signed(expected_record[47:40]), $signed(mem26[42]), $signed(mem26[43]), $signed(mem26[44]), $signed(mem26[45]), $signed(mem26[46]), $signed(mem26[47]), expected_record[55:48], best_index, done_seen, completion_count_at_done, (case_cycles <= cycle_bound), ordinal + 1, final_write_mask);\n"
    )
    text += "    completed_cases = completed_cases + 1;\n"
    text += "    if (completed_cases == 1 || case_cycles < min_cycles) min_cycles = case_cycles;\n"
    text += "    if (completed_cases == 1 || case_cycles > max_cycles) max_cycles = case_cycles;\n"
    text += "  end\n"
    text += '  oracle_scan_status = $fscanf(oracle_fd, "%h", trailing_record);\n'
    text += "  if (oracle_scan_status != -1) begin context_index = sequence_mode ? 0 : shard_start + shard_count; case_cycles = 0; case_fail(\"TRAILING_ORACLE_RECORD\"); end\n"
    text += "  $fclose(oracle_fd);\n"
    text += "  if (sequence_mode) begin context_index_scan_status = $fscanf(context_index_fd, \"%d\", context_index); if (context_index_scan_status != -1) begin case_cycles = 0; case_fail(\"TRAILING_CONTEXT_INDEX\"); end $fclose(context_index_fd); end\n"
    text += '  if (sequence_mode) $display("SEQUENCE_PASS count=%0d completed=%0d resets=%0d min_cycles=%0d max_cycles=%0d", sequence_count, completed_cases, completed_cases, min_cycles, max_cycles);\n'
    text += '  else $display("SHARD_PASS start=%0d count=%0d completed=%0d min_cycles=%0d max_cycles=%0d", shard_start, shard_count, completed_cases, min_cycles, max_cycles);\n'
    text += "  $finish;\nend\nendmodule\n"
    path = root / "tb.sv"
    path.write_text(text, encoding="utf-8")
    return path


class ShardOutputError(RuntimeError):
    """A terminal strict-fixture record that must become durable evidence."""

    def __init__(self, message: str, *, counterexample: dict | None = None) -> None:
        super().__init__(message)
        self.counterexample = counterexample


_CASE_PASS_RECORD = re.compile(
    r"^CASE_PASS index=(?P<index>\d+) cycles=(?P<cycles>\d+) "
    r"expected_codes=(?P<expected>-?\d+(?:,-?\d+){5}) "
    r"observed_codes=(?P<observed>-?\d+(?:,-?\d+){5}) "
    r"expected_token=(?P<expected_token>\d+) "
    r"observed_token=(?P<observed_token>\d+) "
    r"(?:done=(?P<done>[01]) completion_count=(?P<completion_count>\d+) "
    r"within_bound=(?P<within_bound>[01]) reset_complete=(?P<reset_complete>[01]) "
    r"reset_cycles=(?P<reset_cycles>\d+) reset_ordinal=(?P<reset_ordinal>\d+) )?"
    r"write_mask=(?P<write_mask>[01]{6})$"
)
_CASE_FAIL_RECORD = re.compile(
    r"^CASE_FAIL index=(?P<index>\d+) reason=(?P<reason>\S+)(?P<details>.*)$"
)
_IMMUTABLE_WRITE_RECORD = re.compile(
    r"^IMMUTABLE_WRITE port=(?P<port>\d+) addr=(?P<addr>\d+)$"
)
_SHARD_PASS_RECORD = re.compile(
    r"^SHARD_PASS start=(?P<start>\d+) count=(?P<count>\d+) "
    r"completed=(?P<completed>\d+) min_cycles=(?P<min_cycles>\d+) "
    r"max_cycles=(?P<max_cycles>\d+)$"
)
_SEQUENCE_PASS_RECORD = re.compile(
    r"^SEQUENCE_PASS count=(?P<count>\d+) completed=(?P<completed>\d+) "
    r"resets=(?P<resets>\d+) min_cycles=(?P<min_cycles>\d+) "
    r"max_cycles=(?P<max_cycles>\d+)$"
)
_ABI_RECEIPT_RECORD = re.compile(
    r"^ABI_RECEIPT sha256=(?P<sha256>[0-9a-f]{64}) "
    r"fixture=(?P<fixture>[A-Za-z0-9_.-]+)$"
)
_STRICT_RECORD_PREFIXES = (
    "CASE_PASS",
    "CASE_FAIL",
    "SHARD_PASS",
    "SEQUENCE_PASS",
    "ABI_RECEIPT",
    "IMMUTABLE_WRITE",
)


def _lowest_argmax(codes: list[int]) -> int:
    best_index = 0
    for index in range(1, len(codes)):
        if codes[index] > codes[best_index]:
            best_index = index
    return best_index


def _parse_signed_codes(rendered: str) -> list[int]:
    try:
        codes = [int(value) for value in rendered.split(",")]
    except ValueError as error:
        raise RuntimeError("CASE_PASS contains malformed signed int8 codes") from error
    if len(codes) != VOCAB_SIZE or any(not -128 <= code <= 127 for code in codes):
        raise RuntimeError("CASE_PASS contains invalid signed int8 codes")
    return codes


def _parse_terminal_integer(rendered: str, record_kind: str) -> int:
    try:
        return int(rendered)
    except ValueError as error:
        raise RuntimeError(f"{record_kind} contains a malformed decimal integer") from error


def _parse_shard_output(
    output: str,
    *,
    expected_count: int,
    expected_start: int = 0,
    cycle_bound: int,
    _expected_indexes: list[int] | None = None,
    _sequence: bool = False,
    _require_lifecycle_evidence: bool = False,
) -> dict:
    """Accept only a complete, contiguous strict-fixture terminal transcript."""

    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count <= 0
        or not isinstance(expected_start, int)
        or isinstance(expected_start, bool)
        or expected_start < 0
        or not isinstance(cycle_bound, int)
        or isinstance(cycle_bound, bool)
        or cycle_bound <= 0
    ):
        raise ValueError(
            "expected shard range and cycle bound must be non-empty positive integer values"
        )
    if _expected_indexes is not None:
        if (
            len(_expected_indexes) != expected_count
            or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in _expected_indexes)
        ):
            raise ValueError("expected sequence indexes must be nonnegative integers")
        requested_indexes = list(_expected_indexes)
    else:
        requested_indexes = list(range(expected_start, expected_start + expected_count))
    case_records: list[dict] = []
    shard_record: dict[str, int] | None = None
    sequence_record: dict[str, int] | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        immutable_write = _IMMUTABLE_WRITE_RECORD.fullmatch(line)
        if immutable_write is not None:
            raise ShardOutputError(
                "DUT attempted an immutable-memory write",
                counterexample={
                    "reason": "IMMUTABLE_WRITE",
                    "port": _parse_terminal_integer(
                        immutable_write.group("port"), "IMMUTABLE_WRITE"
                    ),
                    "address": _parse_terminal_integer(
                        immutable_write.group("addr"), "IMMUTABLE_WRITE"
                    ),
                    "record": line,
                },
            )
        failed = _CASE_FAIL_RECORD.fullmatch(line)
        if failed is not None:
            counterexample = {
                "index": _parse_terminal_integer(
                    failed.group("index"), "CASE_FAIL"
                ),
                "reason": failed.group("reason"),
                "record": line,
            }
            if failed.group("details"):
                counterexample["details"] = failed.group("details").strip()
            raise ShardOutputError(
                f"CASE_FAIL index={counterexample['index']} reason={counterexample['reason']}",
                counterexample=counterexample,
            )
        passed = _CASE_PASS_RECORD.fullmatch(line)
        if passed is not None:
            if shard_record is not None:
                raise RuntimeError("CASE_PASS appears after SHARD_PASS")
            if sequence_record is not None:
                raise RuntimeError("CASE_PASS appears after SEQUENCE_PASS")
            expected_codes = _parse_signed_codes(passed.group("expected"))
            observed_codes = _parse_signed_codes(passed.group("observed"))
            expected_token = _parse_terminal_integer(
                passed.group("expected_token"), "CASE_PASS"
            )
            observed_token = _parse_terminal_integer(
                passed.group("observed_token"), "CASE_PASS"
            )
            cycles = _parse_terminal_integer(passed.group("cycles"), "CASE_PASS")
            if not 1 <= cycles <= cycle_bound:
                raise RuntimeError("CASE_PASS cycles are outside the requested cycle bound")
            if not 0 <= expected_token < VOCAB_SIZE or not 0 <= observed_token < VOCAB_SIZE:
                raise RuntimeError("CASE_PASS contains an out-of-range token ID")
            if expected_codes != observed_codes:
                raise RuntimeError("CASE_PASS claims unequal expected and observed raw codes")
            if expected_token != _lowest_argmax(expected_codes):
                raise RuntimeError("CASE_PASS expected token is not the lowest-index argmax")
            if observed_token != _lowest_argmax(observed_codes):
                raise RuntimeError("CASE_PASS observed token is not the lowest-index argmax")
            if passed.group("write_mask") != "111111":
                raise RuntimeError("CASE_PASS does not contain every final output write")
            lifecycle_values = {
                name: passed.group(name)
                for name in (
                    "done", "completion_count", "within_bound", "reset_complete",
                    "reset_cycles", "reset_ordinal",
                )
            }
            if _require_lifecycle_evidence and any(value is None for value in lifecycle_values.values()):
                raise RuntimeError("CASE_PASS lacks explicit done/completion/bound/reset evidence")
            lifecycle: dict | None = None
            if all(value is not None for value in lifecycle_values.values()):
                parsed_lifecycle = {
                    name: _parse_terminal_integer(value, "CASE_PASS")
                    for name, value in lifecycle_values.items()
                    if value is not None
                }
                ordinal = len(case_records) + 1
                if (
                    parsed_lifecycle["done"] != 1
                    or parsed_lifecycle["completion_count"] != 1
                    or parsed_lifecycle["within_bound"] != 1
                    or parsed_lifecycle["reset_complete"] != 1
                    or parsed_lifecycle["reset_cycles"] != 3
                    or parsed_lifecycle["reset_ordinal"] != ordinal
                ):
                    raise RuntimeError("CASE_PASS has invalid done/completion/bound/reset evidence")
                lifecycle = {
                    "done": True,
                    "completion_count": parsed_lifecycle["completion_count"],
                    "within_bound": True,
                    "reset": {
                        "complete": True,
                        "cycles": parsed_lifecycle["reset_cycles"],
                        "ordinal": parsed_lifecycle["reset_ordinal"],
                    },
                }
            case_records.append({
                "index": _parse_terminal_integer(passed.group("index"), "CASE_PASS"),
                "cycles": cycles,
                "expected_codes_i8": expected_codes,
                "observed_codes_i8": observed_codes,
                "expected_token": expected_token,
                "observed_token": observed_token,
                "write_mask": passed.group("write_mask"),
                **({"completion": lifecycle, "reset": lifecycle["reset"]} if lifecycle is not None else {}),
            })
            continue
        shard = _SHARD_PASS_RECORD.fullmatch(line)
        if shard is not None:
            if shard_record is not None:
                raise RuntimeError("duplicate SHARD_PASS record")
            shard_record = {
                name: _parse_terminal_integer(shard.group(name), "SHARD_PASS")
                for name in shard.groupdict()
            }
            continue
        sequence = _SEQUENCE_PASS_RECORD.fullmatch(line)
        if sequence is not None:
            if sequence_record is not None:
                raise RuntimeError("duplicate SEQUENCE_PASS record")
            sequence_record = {
                name: _parse_terminal_integer(sequence.group(name), "SEQUENCE_PASS")
                for name in sequence.groupdict()
            }
            continue
        abi_receipt = _ABI_RECEIPT_RECORD.fullmatch(line)
        if abi_receipt is not None:
            if abi_receipt.group("fixture") != STRICT_FIXTURE_SCHEMA:
                raise RuntimeError("ABI_RECEIPT fixture schema does not match strict fixture")
            continue
        for prefix in _STRICT_RECORD_PREFIXES:
            if line == prefix or line.startswith(prefix + " "):
                raise RuntimeError(f"malformed strict terminal record beginning {prefix}")

    if not case_records:
        raise RuntimeError("missing CASE_PASS record")
    actual_indexes = [record["index"] for record in case_records]
    if len(actual_indexes) != expected_count:
        raise RuntimeError("missing CASE_PASS record or unexpected extra CASE_PASS record")
    if actual_indexes != requested_indexes:
        qualifier = "ordered in the requested sequence" if _sequence else "contiguous in the requested shard"
        raise RuntimeError(f"CASE_PASS indexes are not {qualifier}")
    if _sequence:
        if shard_record is not None:
            raise RuntimeError("sparse sequence emitted SHARD_PASS")
        if sequence_record is None:
            raise RuntimeError("missing SEQUENCE_PASS record")
        if (
            sequence_record["count"] != expected_count
            or sequence_record["completed"] != expected_count
            or sequence_record["resets"] != expected_count
        ):
            raise RuntimeError("SEQUENCE_PASS does not match the requested sequence")
        terminal_record = sequence_record
    else:
        if sequence_record is not None:
            raise RuntimeError("contiguous shard emitted SEQUENCE_PASS")
        if shard_record is None:
            raise RuntimeError("missing SHARD_PASS record")
        if (
            shard_record["start"] != expected_start
            or shard_record["count"] != expected_count
            or shard_record["completed"] != expected_count
        ):
            raise RuntimeError("SHARD_PASS does not match the requested shard")
        terminal_record = shard_record
    latencies = [record["cycles"] for record in case_records]
    if (
        terminal_record["min_cycles"] != min(latencies)
        or terminal_record["max_cycles"] != max(latencies)
    ):
        raise RuntimeError("SHARD_PASS latency summary does not match CASE_PASS records")
    return {
        "cases": case_records,
        "completed": expected_count,
        "min_cycles": terminal_record["min_cycles"],
        "max_cycles": terminal_record["max_cycles"],
        **({"reset_count": sequence_record["resets"]} if _sequence else {}),
    }


def _parse_sequence_output(
    output: str, *, expected_indexes: list[int], cycle_bound: int
) -> dict:
    """Parse one Vtb process over an explicitly ordered sparse context sequence."""

    return _parse_shard_output(
        output,
        expected_count=len(expected_indexes),
        expected_start=0,
        cycle_bound=cycle_bound,
        _expected_indexes=expected_indexes,
        _sequence=True,
        _require_lifecycle_evidence=True,
    )


def _frozen_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError(f"{label} must be a SHA-256")
    return value


def _frozen_oracle_image_provenance(oracle: object, *, label: str) -> tuple[str, str]:
    """Extract the independently verified raw image/manifest hashes from an oracle."""

    if not isinstance(oracle, dict):
        raise RuntimeError(f"{label}: strict provenance oracle is malformed")
    if oracle.get("kind") == "sparse-sequence":
        components = oracle.get("components")
        if not isinstance(components, list) or not components:
            raise RuntimeError(f"{label}: strict provenance oracle components are malformed")
    else:
        components = [oracle]
    provenance: set[tuple[str, str]] = set()
    for component in components:
        try:
            artifacts = component["receipt"]["artifacts"]
            image_sha256 = artifacts["image_sha256"]
            manifest_sha256 = artifacts["image_manifest_sha256"]
        except (KeyError, TypeError) as error:
            raise RuntimeError(
                f"{label}: strict provenance oracle lacks image-manifest evidence"
            ) from error
        provenance.add((
            _frozen_sha256(
                image_sha256,
                label=f"{label}: strict provenance oracle image_sha256",
            ),
            _frozen_sha256(
                manifest_sha256,
                label=f"{label}: strict provenance oracle image_manifest_sha256",
            ),
        ))
    if len(provenance) != 1:
        raise RuntimeError(
            f"{label}: strict provenance oracle components disagree on image manifest"
        )
    return next(iter(provenance))


def _strict_frozen_receipt_identity(receipt: object, *, proof_sha256: str, label: str) -> dict:
    """Validate and reduce one pass receipt to its frozen-gate identity.

    The reducer must not treat matching output codes as a proof when the two
    runs were produced from different source memories, ABI, fixture, or cache.
    Canonical binding and ABI receipts are validated before their hashes become
    identity fields, so an attacker cannot compare self-attested digests only.
    """

    _frozen_sha256(proof_sha256, label="frozen reducer proof")
    if not isinstance(receipt, dict):
        raise RuntimeError(f"{label}: strict receipt is not an object")
    if receipt.get("schema") != STRICT_RESULT_SCHEMA:
        raise RuntimeError(f"{label}: strict provenance schema is unsupported")
    f32_constant_bits = receipt.get("f32_constant_bits")
    if (
        not isinstance(f32_constant_bits, dict)
        or f32_constant_bits.get("sha256") != proof_sha256
    ):
        raise RuntimeError(f"{label}: strict provenance f32_constant_bits is invalid")
    try:
        bindings = _validate_calyx_memory_bindings_receipt(
            receipt.get("calyx_memory_bindings")
        )
    except RuntimeError as error:
        raise RuntimeError(
            f"{label}: strict provenance calyx_memory_bindings is invalid: {error}"
        ) from error
    try:
        memory_abi = _validate_memory_abi_receipt(receipt.get("memory_abi"))
    except RuntimeError as error:
        raise RuntimeError(
            f"{label}: strict provenance memory_abi is invalid: {error}"
        ) from error
    if bindings["memory_abi_sha256"] != memory_abi["sha256"]:
        raise RuntimeError(
            f"{label}: strict provenance calyx_memory_bindings does not bind memory_abi"
        )

    inputs = receipt.get("inputs")
    input_keys = {
        "sv_sha256", "image_sha256", "manifest_sha256", "flat_scf_sha256",
        "pre_calyx_sha256",
    }
    if not isinstance(inputs, dict) or set(inputs) != input_keys:
        raise RuntimeError(f"{label}: strict provenance inputs are malformed")
    for field in sorted(input_keys):
        _frozen_sha256(inputs[field], label=f"{label}: strict provenance inputs.{field}")
    oracle_image_sha256, oracle_manifest_sha256 = _frozen_oracle_image_provenance(
        receipt.get("oracle"), label=label
    )
    if inputs["image_sha256"] != oracle_image_sha256:
        raise RuntimeError(
            f"{label}: strict provenance inputs.image_sha256 does not match oracle evidence"
        )
    if inputs["manifest_sha256"] != oracle_manifest_sha256:
        raise RuntimeError(
            f"{label}: strict provenance inputs.manifest_sha256 does not match oracle evidence"
        )
    if bindings["image_manifest_sha256"] != inputs["manifest_sha256"]:
        raise RuntimeError(
            f"{label}: strict provenance calyx_memory_bindings does not bind "
            "inputs.manifest_sha256"
        )
    for field in ("sv_sha256", "image_sha256", "flat_scf_sha256", "pre_calyx_sha256"):
        binding_field = field
        if field == "sv_sha256":
            continue
        if bindings[binding_field] != inputs[field]:
            raise RuntimeError(
                f"{label}: strict provenance calyx_memory_bindings does not bind inputs.{field}"
            )

    sv = receipt.get("sv")
    if not isinstance(sv, dict) or set(sv) != {"raw_sha256", "normalized_sha256"}:
        raise RuntimeError(f"{label}: strict provenance sv is malformed")
    for field in ("raw_sha256", "normalized_sha256"):
        _frozen_sha256(sv[field], label=f"{label}: strict provenance sv.{field}")
    if sv["raw_sha256"] != inputs["sv_sha256"]:
        raise RuntimeError(f"{label}: strict provenance sv does not bind inputs.sv_sha256")
    fixture_sha256 = _frozen_sha256(
        receipt.get("fixture_sha256"), label=f"{label}: strict provenance fixture_sha256"
    )

    configuration = receipt.get("configuration")
    configuration_keys = {
        "verilate_jobs", "build_jobs", "verilator_threads",
        "verilator_output_split", "verilator_output_split_cfuncs",
        "fixture_schema", "f32_constant_bits_sha256", "calyx_memory_bindings_sha256",
    }
    if not isinstance(configuration, dict) or set(configuration) != configuration_keys:
        raise RuntimeError(f"{label}: strict provenance configuration is malformed")
    for field in (
        "verilate_jobs", "build_jobs", "verilator_threads",
        "verilator_output_split", "verilator_output_split_cfuncs",
    ):
        value = configuration[field]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise RuntimeError(
                f"{label}: strict provenance configuration.{field} is invalid"
            )
    if (
        configuration["fixture_schema"] != STRICT_FIXTURE_SCHEMA
        or configuration["f32_constant_bits_sha256"] != proof_sha256
        or configuration["calyx_memory_bindings_sha256"] != bindings["sha256"]
    ):
        raise RuntimeError(f"{label}: strict provenance configuration is inconsistent")

    cache_identity = receipt.get("cache_identity")
    expected_cache_identity = {
        "fixture": {
            "mode": "observable-shard-generic",
            "fixture_schema": STRICT_FIXTURE_SCHEMA,
        },
        "f32_constant_bits_sha256": proof_sha256,
        "calyx_memory_bindings_sha256": bindings["sha256"],
    }
    if cache_identity != expected_cache_identity:
        raise RuntimeError(f"{label}: strict provenance cache_identity is invalid")
    try:
        cache_hashes = _strict_cache_hashes(receipt.get("cache_hashes"))
    except RuntimeError as error:
        raise RuntimeError(
            f"{label}: strict provenance cache_hashes are invalid: {error}"
        ) from error
    expected_cache_hashes = {
        "raw_sv_sha256": sv["raw_sha256"],
        "normalized_sv_sha256": sv["normalized_sha256"],
        "fixture_sha256": fixture_sha256,
        "memory_abi_sha256": _sha256_bytes(
            (memory_abi["canonical_json"] + "\n").encode("utf-8")
        ),
        "calyx_memory_bindings_sha256": bindings["sha256"],
    }
    for field, expected in expected_cache_hashes.items():
        if cache_hashes[field] != expected:
            raise RuntimeError(
                f"{label}: strict provenance cache_hashes.{field} is inconsistent"
            )

    runner_sha256 = _frozen_sha256(
        receipt.get("runner_sha256"), label=f"{label}: strict provenance runner_sha256"
    )
    simulator = receipt.get("simulator")
    if (
        not isinstance(simulator, dict)
        or set(simulator) != {"name", "version"}
        or simulator["name"] != "verilator"
        or not isinstance(simulator["version"], str)
        or not simulator["version"]
    ):
        raise RuntimeError(f"{label}: strict provenance simulator is invalid")
    cycle_bound = receipt.get("cycle_bound")
    if not isinstance(cycle_bound, int) or isinstance(cycle_bound, bool) or cycle_bound <= 0:
        raise RuntimeError(f"{label}: strict provenance cycle_bound is invalid")
    return {
        "calyx_memory_bindings": bindings["sha256"],
        "memory_abi": memory_abi["sha256"],
        "inputs": dict(inputs),
        "sv": dict(sv),
        "fixture_sha256": fixture_sha256,
        "configuration": dict(configuration),
        "cache_identity": cache_identity,
        "cache_hashes": cache_hashes,
        "runner_sha256": runner_sha256,
        "simulator": dict(simulator),
        "cycle_bound": cycle_bound,
    }


def _validate_frozen_case_lifecycle(case: object, *, label: str) -> tuple[dict, dict]:
    """Require one receipt's lifecycle evidence to describe one valid launch."""

    if not isinstance(case, dict):
        raise RuntimeError(f"{label}: lifecycle case is not an object")
    completion = case.get("completion")
    reset = case.get("reset")
    if not isinstance(completion, dict):
        raise RuntimeError(f"{label}: lifecycle completion is missing")
    if not isinstance(reset, dict):
        raise RuntimeError(f"{label}: lifecycle reset is missing")
    if completion.get("done") is not True:
        raise RuntimeError(f"{label}: lifecycle completion.done must be true")
    completion_count = completion.get("completion_count")
    if type(completion_count) is not int or completion_count != 1:
        raise RuntimeError(
            f"{label}: lifecycle completion.completion_count must equal one"
        )
    if completion.get("within_bound") is not True:
        raise RuntimeError(f"{label}: lifecycle completion.within_bound must be true")
    nested_reset = completion.get("reset")
    if nested_reset != reset:
        raise RuntimeError(f"{label}: lifecycle reset differs from completion.reset")
    if reset.get("complete") is not True:
        raise RuntimeError(f"{label}: lifecycle reset.complete must be true")
    reset_cycles = reset.get("cycles")
    if type(reset_cycles) is not int or reset_cycles != 3:
        raise RuntimeError(f"{label}: lifecycle reset.cycles must equal three")
    ordinal = reset.get("ordinal")
    if type(ordinal) is not int or ordinal <= 0:
        raise RuntimeError(f"{label}: lifecycle reset.ordinal is invalid")
    return completion, reset


def _frozen_four_summary(
    case_names: list[str],
    fresh_receipts: dict[str, dict],
    sequential_receipt: dict,
    proof_sha256: str,
) -> dict:
    """Reduce fresh and one-process receipts only when their evidence agrees."""

    if (
        not isinstance(case_names, list)
        or not case_names
        or any(not isinstance(name, str) or not name for name in case_names)
        or len(case_names) != len(set(case_names))
    ):
        raise RuntimeError("frozen reducer requires unique case names")
    if not isinstance(fresh_receipts, dict):
        raise RuntimeError("frozen reducer fresh receipts are malformed")
    _frozen_sha256(proof_sha256, label="frozen reducer proof")
    if not isinstance(sequential_receipt, dict):
        raise RuntimeError("sequential-reset receipt is incomplete or has wrong proof binding")
    sequential_f32_constant_bits = sequential_receipt.get("f32_constant_bits")
    if (
        sequential_receipt.get("status") != "pass"
        or sequential_receipt.get("completed") != len(case_names)
        or sequential_receipt.get("reset_count") != len(case_names)
    ):
        raise RuntimeError("sequential-reset receipt is incomplete")
    if (
        not isinstance(sequential_f32_constant_bits, dict)
        or sequential_f32_constant_bits.get("sha256") != proof_sha256
    ):
        raise RuntimeError(
            "sequential-reset receipt has malformed or wrong f32_constant_bits proof binding"
        )
    sequential_identity = _strict_frozen_receipt_identity(
        sequential_receipt, proof_sha256=proof_sha256, label="sequential-reset"
    )
    sequential_cases = sequential_receipt.get("cases")
    sequential_oracle = sequential_receipt.get("oracle")
    if not isinstance(sequential_cases, list) or len(sequential_cases) != len(case_names):
        raise RuntimeError("sequential-reset receipt has wrong case count")
    if (
        not isinstance(sequential_oracle, dict)
        or sequential_oracle.get("kind") != "sparse-sequence"
        or not isinstance(sequential_oracle.get("components"), list)
        or len(sequential_oracle["components"]) != len(case_names)
    ):
        raise RuntimeError("sequential-reset receipt lacks ordered component provenance")
    compared: list[dict] = []
    comparison_fields = (
        "index", "cycles", "expected_codes_i8", "observed_codes_i8",
        "expected_token", "observed_token", "write_mask",
    )
    completion_fields = ("done", "completion_count", "within_bound")
    reset_fields = ("complete", "cycles")
    provenance_fields = (
        "memory_abi", "calyx_memory_bindings", "inputs", "sv", "fixture_sha256",
        "configuration", "cache_identity", "cache_hashes", "runner_sha256",
        "simulator", "cycle_bound",
    )
    for ordinal, (name, sequential_case) in enumerate(
        zip(case_names, sequential_cases), start=1
    ):
        fresh = fresh_receipts.get(name)
        fresh_f32_constant_bits = (
            fresh.get("f32_constant_bits") if isinstance(fresh, dict) else None
        )
        if (
            not isinstance(fresh, dict)
            or fresh.get("status") != "pass"
            or fresh.get("completed") != 1
            or not isinstance(fresh.get("cases"), list)
            or len(fresh["cases"]) != 1
        ):
            raise RuntimeError(f"{name}: fresh receipt is incomplete")
        if (
            not isinstance(fresh_f32_constant_bits, dict)
            or fresh_f32_constant_bits.get("sha256") != proof_sha256
        ):
            raise RuntimeError(
                f"{name}: fresh receipt has malformed or wrong f32_constant_bits proof binding"
            )
        fresh_identity = _strict_frozen_receipt_identity(
            fresh, proof_sha256=proof_sha256, label=f"{name}: fresh"
        )
        for field in provenance_fields:
            if fresh_identity[field] != sequential_identity[field]:
                raise RuntimeError(
                    f"{name}: {field} differs between fresh and sequential receipt"
                )
        fresh_case = fresh["cases"][0]
        fresh_completion, fresh_reset = _validate_frozen_case_lifecycle(
            fresh_case, label=f"{name}: fresh"
        )
        sequential_completion, sequential_reset = _validate_frozen_case_lifecycle(
            sequential_case, label=f"{name}: sequential"
        )
        fresh_oracle = fresh.get("oracle")
        sequential_component = sequential_oracle["components"][ordinal - 1]
        if (
            not isinstance(fresh_oracle, dict)
            or fresh_oracle.get("metadata_sha256") != sequential_component.get("metadata_sha256")
            or fresh_oracle.get("payload_sha256") != sequential_component.get("payload_sha256")
        ):
            raise RuntimeError(f"{name}: case/oracle provenance differs between fresh and sequential receipt")
        for field in comparison_fields:
            if fresh_case.get(field) != sequential_case.get(field):
                raise RuntimeError(f"{name}: {field} differs between fresh and sequential receipt")
        for field in completion_fields:
            if fresh_completion.get(field) != sequential_completion.get(field):
                raise RuntimeError(f"{name}: completion {field} differs between fresh and sequential receipt")
        for field in reset_fields:
            if fresh_reset.get(field) != sequential_reset.get(field):
                raise RuntimeError(f"{name}: reset {field} differs between fresh and sequential receipt")
        if fresh_reset.get("ordinal") != 1 or sequential_reset.get("ordinal") != ordinal:
            raise RuntimeError(f"{name}: reset ordinal evidence is invalid")
        compared.append({
            "case": name,
            "index": fresh_case["index"],
            "fresh": fresh_case,
            "sequential": sequential_case,
        })
    return {
        "schema": FROZEN_FOUR_SCHEMA,
        "status": "pass",
        "f32_constant_bits_sha256": proof_sha256,
        "fresh_receipts": [fresh_receipts[name] for name in case_names],
        "sequential_reset": sequential_receipt,
        "comparisons": compared,
    }


def _write_frozen_four_failure(
    summary_path: Path,
    *,
    error: Exception,
    proof_sha256: str | None,
    fresh_receipts: dict[str, dict],
    sequential_receipt: dict | None,
    fresh_receipt_specs: list[str] | None = None,
    sequential_receipt_path: Path | None = None,
) -> None:
    """Persist reducer failure evidence even when receipt loading did not finish."""

    counterexample = {
        "schema": FROZEN_FOUR_SCHEMA,
        "status": "fail",
        "stage": "frozen_reducer",
        "error": str(error),
        "proof": {"f32_constant_bits_sha256": proof_sha256},
        "fresh_receipts": fresh_receipts,
        "sequential_reset": sequential_receipt,
    }
    if fresh_receipt_specs is not None:
        counterexample["fresh_receipt_specs"] = list(fresh_receipt_specs)
    if sequential_receipt_path is not None:
        counterexample["sequential_receipt_path"] = str(sequential_receipt_path)
    _write_json(summary_path.with_name("counterexample.json"), counterexample)
    _write_json(summary_path, {
        "schema": FROZEN_FOUR_SCHEMA,
        "status": "fail",
        "failure": counterexample,
    })


def _write_frozen_four_summary(
    summary_path: Path,
    case_names: list[str],
    fresh_receipts: dict[str, dict],
    sequential_receipt: dict,
    proof_sha256: str,
) -> dict:
    """Write a frozen summary or durable reducer counterexample beside it."""

    try:
        summary = _frozen_four_summary(
            case_names, fresh_receipts, sequential_receipt, proof_sha256
        )
    except (RuntimeError, TypeError, AttributeError, KeyError, IndexError) as error:
        _write_frozen_four_failure(
            summary_path,
            error=error,
            proof_sha256=proof_sha256,
            fresh_receipts=fresh_receipts,
            sequential_receipt=sequential_receipt,
        )
        raise
    _write_json(summary_path, summary)
    return summary


def _load_frozen_reducer_receipt(path: Path, *, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot load frozen reducer {label}: {path}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"frozen reducer {label} is not a JSON object: {path}")
    return payload


def _run_frozen_four_reducer(args: argparse.Namespace) -> None:
    """Load Nix-produced receipts and persist a frozen-gate summary or failure."""

    if args.result_json is None:
        raise RuntimeError("--reduce-frozen-four requires --result-json")
    proof_sha256: str | None = None
    case_names: list[str] = []
    fresh_receipts: dict[str, dict] = {}
    sequential_receipt: dict | None = None
    try:
        if args.f32_constant_bits is None:
            raise RuntimeError("--reduce-frozen-four requires --f32-constant-bits")
        if args.sequential_receipt is None:
            raise RuntimeError("--reduce-frozen-four requires --sequential-receipt")
        if not args.fresh_receipt:
            raise RuntimeError("--reduce-frozen-four requires at least one --fresh-receipt")
        proof_sha256 = _sha256_path(args.f32_constant_bits)
        for specification in args.fresh_receipt:
            name, delimiter, rendered_path = specification.partition("=")
            if (
                delimiter != "="
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name)
                or not rendered_path
                or name in fresh_receipts
            ):
                raise RuntimeError(
                    "--fresh-receipt must be a unique NAME=PATH pair with an ASCII case name"
                )
            fresh_receipts[name] = _load_frozen_reducer_receipt(
                Path(rendered_path), label=f"fresh receipt {name}"
            )
            case_names.append(name)
        sequential_receipt = _load_frozen_reducer_receipt(
            args.sequential_receipt, label="sequential receipt"
        )
    except (
        OSError, RuntimeError, ValueError, json.JSONDecodeError,
        TypeError, AttributeError, KeyError, IndexError,
    ) as error:
        _write_frozen_four_failure(
            args.result_json,
            error=error,
            proof_sha256=proof_sha256,
            fresh_receipts=fresh_receipts,
            sequential_receipt=sequential_receipt,
            fresh_receipt_specs=args.fresh_receipt,
            sequential_receipt_path=args.sequential_receipt,
        )
        raise
    assert proof_sha256 is not None
    assert sequential_receipt is not None
    summary = _write_frozen_four_summary(
        args.result_json,
        case_names,
        fresh_receipts,
        sequential_receipt,
        proof_sha256,
    )
    print(json.dumps(summary, sort_keys=True))


def _validate_oracle_image_provenance(
    metadata: dict,
    *,
    image_bytes: bytes,
    manifest_bytes: bytes,
) -> None:
    """Require the shard's Task-1 provenance to name these exact frozen files."""

    try:
        receipt = metadata["receipt"]
        artifacts = receipt["artifacts"]
        expected_image = artifacts["image_sha256"]
        expected_manifest = artifacts["image_manifest_sha256"]
    except (KeyError, TypeError) as error:
        raise RuntimeError("oracle shard lacks image/image-manifest provenance") from error
    actual_image = _sha256_bytes(image_bytes)
    actual_manifest = _sha256_bytes(manifest_bytes)
    if expected_image != actual_image:
        raise RuntimeError("oracle shard image_sha256 does not match --image")
    if expected_manifest != actual_manifest:
        raise RuntimeError("oracle shard image_manifest_sha256 does not match --manifest")


def _load_oracle_helper():
    configured = os.environ.get("RC_OBSERVABLE_ORACLE_HELPER")
    helper_path = Path(configured) if configured else Path(__file__).with_name("build_rc_observable_oracle.py")
    spec = importlib.util.spec_from_file_location("rc_observable_oracle", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load observable oracle helper: {helper_path}")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def _verified_equivalence_shard(metadata_path: Path) -> dict:
    """Use Task 1's on-disk verifier before exposing a payload to Verilator."""

    metadata_path = metadata_path.resolve()
    helper = _load_oracle_helper()
    try:
        metadata = helper.verify_shard(metadata_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid observable oracle shard: {metadata_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise RuntimeError("observable oracle verifier returned a non-object receipt")
    try:
        enumeration = metadata["enumeration"]
        payload = metadata["payload"]
        start = enumeration["start"]
        stop = enumeration["stop"]
        payload_name = payload["file"]
        payload_sha256 = payload["sha256"]
    except (KeyError, TypeError) as error:
        raise RuntimeError("verified oracle shard lacks range or payload fields") from error
    total_contexts = VOCAB_SIZE ** CONTEXT_LENGTH
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(stop, int)
        or isinstance(stop, bool)
        or not 0 <= start < stop <= total_contexts
        or not isinstance(payload_name, str)
        or not isinstance(payload_sha256, str)
    ):
        raise RuntimeError("verified oracle shard has invalid range or payload fields")
    payload_path = (metadata_path.parent / payload_name).resolve()
    if payload_path.parent != metadata_path.parent:
        raise RuntimeError("verified oracle payload escapes its metadata directory")
    return {
        "metadata": metadata,
        "metadata_path": metadata_path,
        "metadata_sha256": _sha256_path(metadata_path),
        "payload_path": payload_path,
        "payload_sha256": payload_sha256,
        "start": start,
        "stop": stop,
        "count": stop - start,
    }


def _verified_equivalence_sequence(
    metadata_paths: list[Path],
    runtime_root: Path | None,
    *,
    image_bytes: bytes,
    manifest_bytes: bytes,
) -> dict:
    """Verify and materialize an ordered sparse sequence of one-record shards."""

    if not metadata_paths:
        raise RuntimeError("strict sparse sequence requires at least one oracle shard")
    components = [_verified_equivalence_shard(path) for path in metadata_paths]
    if any(component["count"] != 1 for component in components):
        raise RuntimeError("strict sparse sequence accepts only one-record oracle shards")
    indexes = [component["start"] for component in components]
    if len(indexes) != len(set(indexes)):
        raise RuntimeError("strict sparse sequence contains duplicate context indexes")
    for component in components:
        _validate_oracle_image_provenance(
            component["metadata"],
            image_bytes=image_bytes,
            manifest_bytes=manifest_bytes,
        )
    identity = hashlib.sha256()
    identity.update((STRICT_SEQUENCE_SCHEMA + "\0").encode("ascii"))
    payload_parts: list[bytes] = []
    for component in components:
        payload = component["payload_path"].read_bytes()
        if _sha256_bytes(payload) != component["payload_sha256"]:
            raise RuntimeError(
                "strict sparse sequence component payload SHA-256 does not match "
                "its verified oracle receipt"
            )
        payload_parts.append(payload)
        identity.update(component["metadata_sha256"].encode("ascii"))
        identity.update(component["payload_sha256"].encode("ascii"))
        identity.update(component["start"].to_bytes(8, "big"))
    sequence_sha256 = identity.hexdigest()
    payload_bytes = b"".join(payload_parts)
    context_index_bytes = "".join(f"{index}\n" for index in indexes).encode("ascii")
    payload_path: Path | None = None
    context_index_path: Path | None = None
    if runtime_root is not None:
        runtime_root.mkdir(parents=True, exist_ok=True)
        payload_path = runtime_root / f"sequence-{sequence_sha256}.hex"
        context_index_path = runtime_root / f"sequence-{sequence_sha256}.indexes"
        payload_path.write_bytes(payload_bytes)
        context_index_path.write_bytes(context_index_bytes)
    result = {
        "kind": "sparse-sequence",
        "schema": STRICT_SEQUENCE_SCHEMA,
        "sequence_sha256": sequence_sha256,
        "components": components,
        "indexes": indexes,
        "count": len(components),
        "payload_path": payload_path,
        "payload_sha256": _sha256_bytes(payload_bytes),
        "context_index_path": context_index_path,
        "context_index_sha256": _sha256_bytes(context_index_bytes),
        "payload_bytes": payload_bytes,
        "context_index_bytes": context_index_bytes,
    }
    return result


def _module_prefix(source: str, position: int) -> str:
    module_start = source.rfind("module ", 0, position)
    endmodule_start = source.rfind("endmodule", 0, position)
    if module_start < 0 or endmodule_start > module_start:
        return ""
    return source[module_start:position]


def _declaration_before(source: str, position: int, name: str) -> re.Match[str] | None:
    declaration = re.compile(
        r"\b(?:logic|wire)(?P<signed>\s+signed)?"
        r"(?P<packed>\s+\[\s*(?P<hi>\d+)\s*:\s*(?P<lo>\d+)\s*\])?"
        + r"\s+" + re.escape(name) + r"\s*;"
    )
    matches = list(declaration.finditer(_module_prefix(source, position)))
    return matches[-1] if matches else None


def _temporary_prefix(name: str, expression: str) -> str:
    digest = hashlib.sha256(f"{name}\0{expression}".encode("utf-8")).hexdigest()[:12]
    return f"__llm2fpga_sim_{name}_{digest}"


def _render_or_pages(name: str, terms: list[str], prefix: str) -> str:
    values = terms
    lines: list[str] = []
    level = 0
    while len(values) > NORMALIZER_PAGE_TERMS:
        next_values = []
        for index in range(0, len(values), NORMALIZER_PAGE_TERMS):
            page = f"{prefix}_or_{level}_{index // NORMALIZER_PAGE_TERMS}"
            next_values.append(page)
            lines.extend([
                f"wire {page};",
                f"assign {page} = " + " | ".join(values[index:index + NORMALIZER_PAGE_TERMS]) + ";",
            ])
        values = next_values
        level += 1
    lines.append(f"assign {name} = " + " | ".join(values) + ";")
    return "\n".join(lines)


def _top_level_question(expression: str) -> int | None:
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    in_string = False
    escaped = False
    for index, character in enumerate(expression):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in depths:
            depths[character] += 1
        elif character in closing:
            depths[closing[character]] -= 1
            if depths[closing[character]] < 0:
                return None
        elif character == "?" and not any(depths.values()):
            return index
    return None


def _matching_ternary_colon(expression: str, question: int) -> int | None:
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    nested_ternaries = 0
    in_string = False
    escaped = False
    for index in range(question + 1, len(expression)):
        character = expression[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in depths:
            depths[character] += 1
        elif character in closing:
            depths[closing[character]] -= 1
            if depths[closing[character]] < 0:
                return None
        elif not any(depths.values()):
            if character == "?":
                nested_ternaries += 1
            elif character == ":":
                if nested_ternaries == 0:
                    return index
                nested_ternaries -= 1
    return None


def _flat_priority_ternary(expression: str) -> tuple[list[tuple[str, str]], str] | None:
    pairs: list[tuple[str, str]] = []
    rest = expression.strip()
    while True:
        question = _top_level_question(rest)
        if question is None:
            return (pairs, rest) if pairs and rest else None
        colon = _matching_ternary_colon(rest, question)
        if colon is None:
            return None
        condition = rest[:question].strip()
        true_value = rest[question + 1:colon].strip()
        if not condition or not true_value:
            return None
        pairs.append((condition, true_value))
        rest = rest[colon + 1:].strip()


def _unsigned_literal_width(expression: str) -> int | None:
    literal = re.fullmatch(r"(\d+)'[bBoOdDhH][0-9a-fA-F_xXzZ?]+", expression.strip())
    return int(literal.group(1)) if literal else None


def _priority_chain(pairs: list[tuple[str, str]], fallback: str) -> str:
    result = fallback
    for condition, true_value in reversed(pairs):
        result = f"{condition} ? {true_value} : {result}"
    return result


def _render_ternary_pages(
    name: str,
    packed_range: str,
    pairs: list[tuple[str, str]],
    default: str,
    prefix: str,
) -> str:
    chunks = [
        pairs[index:index + NORMALIZER_PAGE_TERMS]
        for index in range(0, len(pairs), NORMALIZER_PAGE_TERMS)
    ]
    page_names = {
        index: f"{prefix}_ternary_{index}"
        for index in range(1, len(chunks))
    }
    lines = [f"wire {packed_range} {page_names[index]};" for index in page_names]
    fallback = default
    for index in reversed(range(1, len(chunks))):
        page = page_names[index]
        lines.append(f"assign {page} = {_priority_chain(chunks[index], fallback)};")
        fallback = page
    lines.append(f"assign {name} = {_priority_chain(chunks[0], fallback)};")
    return "\n".join(lines)


def _normalize_large_or_assignments(source: str) -> str:
    """Page proven FSM expressions while preserving four-state SV operators.

    The raw Calyx output has exceptionally large scalar OR and priority ternary
    assignments.  The normalizer keeps ``|`` and ``?:`` in continuous assigns;
    it never replaces four-state expressions with procedural ``if`` logic.
    Ternaries are rewritten only when their packed type and every literal arm
    prove that the page nets cannot alter sizing or signedness.
    """
    pattern = re.compile(r"assign\s+(\w+)\s*=\s*(\S[^;]*);", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        name, expression = match.group(1), match.group(2)
        if len(match.group(0)) < NORMALIZER_MIN_ASSIGNMENT_CHARS:
            return match.group(0)
        prefix = _temporary_prefix(name, expression)
        if prefix in source:
            return match.group(0)
        declaration = _declaration_before(source, match.start(), name)
        if "?" in expression:
            parsed = _flat_priority_ternary(expression)
            if (
                declaration is None
                or declaration.group("signed") is not None
                or declaration.group("packed") is None
                or parsed is None
            ):
                return match.group(0)
            pairs, default = parsed
            width = int(declaration.group("hi")) - int(declaration.group("lo")) + 1
            if (
                len(pairs) <= NORMALIZER_PAGE_TERMS
                or width <= 0
                or _unsigned_literal_width(default) != width
                or any(_unsigned_literal_width(true_value) != width for _, true_value in pairs)
            ):
                return match.group(0)
            return _render_ternary_pages(
                name,
                declaration.group("packed").strip(),
                pairs,
                default,
                prefix,
            )
        if " | " not in expression:
            return match.group(0)
        if (
            declaration is None
            or declaration.group("signed") is not None
            or declaration.group("packed") is not None
        ):
            return match.group(0)
        terms = expression.split(" | ")
        if len(terms) <= NORMALIZER_PAGE_TERMS or not all(term.strip() for term in terms):
            return match.group(0)
        return _render_or_pages(name, terms, prefix)

    return pattern.sub(replace, source)


def _normalized_sv_text(source: str) -> str:
    """Render the exact simulation-only normalization written into a cache."""

    lexical = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    lexical = re.sub(r"//[^\n]*", "", lexical)
    lexical = _normalize_large_or_assignments(lexical)
    return lexical.replace(";", ";\n").replace(" | ", " |\n")


def _normalization_metrics(raw_source: str, normalized_source: str) -> dict[str, int]:
    page_wire_pattern = (
        r"\bwire\s+(?:\[[^]]+\]\s+)?__llm2fpga_sim_[A-Za-z0-9_]+\s*;"
    )
    page_wires = len(re.findall(page_wire_pattern, normalized_source))
    raw_page_wires = len(re.findall(page_wire_pattern, raw_source))
    return {
        "raw_sv_bytes": len(raw_source.encode("utf-8")),
        "normalized_sv_bytes": len(normalized_source.encode("utf-8")),
        "normalizer_page_wires": max(0, page_wires - raw_page_wires),
        "normalizer_added_always_comb_blocks": max(
            0,
            normalized_source.count("always_comb") - raw_source.count("always_comb"),
        ),
    }


def _resolved_verilator_jobs(args: argparse.Namespace) -> tuple[int, int]:
    legacy_jobs = getattr(args, "verilator_jobs", None)
    verilate_jobs = getattr(args, "verilate_jobs", None)
    build_jobs = getattr(args, "build_jobs", None)
    resolved_verilate_jobs = verilate_jobs if verilate_jobs is not None else legacy_jobs
    resolved_build_jobs = build_jobs if build_jobs is not None else legacy_jobs
    resolved_verilate_jobs = 4 if resolved_verilate_jobs is None else resolved_verilate_jobs
    resolved_build_jobs = 4 if resolved_build_jobs is None else resolved_build_jobs
    if resolved_verilate_jobs <= 0 or resolved_build_jobs <= 0:
        raise ValueError("Verilator and C++ build jobs must be positive")
    return (resolved_verilate_jobs, resolved_build_jobs)


def _verilator_codegen_command(
    args: argparse.Namespace,
    normalized_sv: Path,
    tb: Path,
    obj_dir: Path,
    verilate_jobs: int,
) -> list[str]:
    command = [
        args.verilator,
        "--cc",
        "--exe",
        "--main",
        "--timing",
        "--Wno-fatal",
        "-O3",
        "--output-split",
        str(args.verilator_output_split),
        "--output-split-cfuncs",
        str(args.verilator_output_split_cfuncs),
        "-CFLAGS",
        "-O3",
        "-j",
        str(verilate_jobs),
        "--top-module",
        "tb",
        str(normalized_sv),
        str(tb),
        "-Mdir",
        str(obj_dir),
    ]
    if args.verilator_threads > 1:
        command += ["--threads", str(args.verilator_threads)]
    return command


def _verilator_build_command(
    args: argparse.Namespace,
    obj_dir: Path,
    build_jobs: int,
) -> list[str]:
    return [args.make, "-C", str(obj_dir), "-f", "Vtb.mk", "-j", str(build_jobs), "Vtb"]


def _generated_cpp_metrics(obj_dir: Path) -> dict[str, int]:
    cpp_files = list(obj_dir.glob("*.cpp"))
    header_files = list(obj_dir.glob("*.h"))
    return {
        "generated_cpp_files": len(cpp_files),
        "generated_cpp_bytes": sum(path.stat().st_size for path in cpp_files),
        "generated_header_files": len(header_files),
        "generated_header_bytes": sum(path.stat().st_size for path in header_files),
    }


def _write_json(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _input_hashes(args: argparse.Namespace) -> dict[str, str]:
    names = ["sv", "image", "manifest"]
    if getattr(args, "reference", None) is not None:
        names.append("reference")
    strict = (
        getattr(args, "equivalence_shard", None) is not None
        or getattr(args, "equivalence_sequence", None) is not None
    )
    if strict:
        names.extend(("flat_scf", "pre_calyx"))
        snapshots = getattr(args, "strict_input_hashes", None)
        if snapshots is not None:
            expected_names = {f"{name}_sha256" for name in names}
            if (
                not isinstance(snapshots, dict)
                or set(snapshots) != expected_names
                or any(
                    not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    for digest in snapshots.values()
                )
            ):
                raise RuntimeError("strict preflight input snapshots are malformed")
            return dict(snapshots)
    return {
        f"{name}_sha256": _sha256_path(getattr(args, name))
        for name in names
    }


def _validate_f32_constant_bits_receipt(receipt: object, *, strict: bool) -> dict | None:
    """Validate the exact Calyx-to-Futil bit proof consumed by strict mode."""

    if receipt is None:
        if strict:
            raise RuntimeError("strict equivalence requires an f32 constant-bits receipt")
        return None
    if not isinstance(receipt, dict):
        raise RuntimeError("f32 constant-bits receipt must be a JSON object")
    if receipt.get("schema") != F32_CONSTANT_BITS_SCHEMA:
        raise RuntimeError("f32 constant-bits receipt has an unsupported schema")
    if receipt.get("status") != "pass" or receipt.get("mismatch_count") != 0:
        raise RuntimeError("f32 constant-bits receipt is not a zero-mismatch pass")
    for name in ("calyx_mlir_sha256", "futil_sha256"):
        value = receipt.get(name)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RuntimeError(f"f32 constant-bits receipt has invalid {name}")
    constants = receipt.get("constants")
    if not isinstance(constants, list) or not constants:
        raise RuntimeError("f32 constant-bits receipt has no constants")
    rows: list[tuple[str, str, int]] = []
    for constant in constants:
        if not isinstance(constant, dict):
            raise RuntimeError("f32 constant-bits receipt has an invalid constant row")
        component = constant.get("component")
        symbol = constant.get("symbol")
        word = constant.get("word_u32")
        if (
            not isinstance(component, str)
            or not component
            or not isinstance(symbol, str)
            or not symbol
            or not isinstance(word, int)
            or isinstance(word, bool)
            or not 0 <= word <= 0xFFFFFFFF
        ):
            raise RuntimeError("f32 constant-bits receipt has an invalid constant row")
        rows.append((component, symbol, word))
    keys = [(component, symbol) for component, symbol, _ in rows]
    if rows != sorted(rows) or len(keys) != len(set(keys)):
        raise RuntimeError("f32 constant-bits receipt constants are not sorted and unique")
    return receipt


def _load_f32_constant_bits_receipt(
    path: Path | None,
    *,
    strict: bool,
    calyx_mlir_path: Path | None = None,
    raw_futil_path: Path | None = None,
) -> dict | None:
    if path is None:
        return _validate_f32_constant_bits_receipt(None, strict=strict)
    resolved = path.resolve()
    try:
        payload = resolved.read_bytes()
        receipt = json.loads(payload)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot load f32 constant-bits receipt: {resolved}") from error
    receipt = _validate_f32_constant_bits_receipt(receipt, strict=strict)
    assert receipt is not None
    if strict and (calyx_mlir_path is None or raw_futil_path is None):
        raise RuntimeError(
            "strict equivalence requires exact Calyx MLIR and raw Futil proof artifacts"
        )
    proof_artifacts: dict[str, dict[str, str]] = {}
    for label, artifact_path, receipt_key in (
        ("Calyx MLIR", calyx_mlir_path, "calyx_mlir_sha256"),
        ("Futil", raw_futil_path, "futil_sha256"),
    ):
        if artifact_path is None:
            continue
        resolved_artifact = artifact_path.resolve()
        try:
            actual_sha256 = _sha256_path(resolved_artifact)
        except OSError as error:
            raise RuntimeError(f"cannot load exact {label} proof artifact: {resolved_artifact}") from error
        if actual_sha256 != receipt[receipt_key]:
            raise RuntimeError(
                f"exact {label} proof artifact SHA-256 does not match f32 constant-bits receipt"
            )
        proof_artifacts["calyx_mlir" if receipt_key == "calyx_mlir_sha256" else "raw_futil"] = {
            "path": str(resolved_artifact),
            "sha256": actual_sha256,
        }
    return {
        "path": str(resolved),
        "sha256": _sha256_bytes(payload),
        "calyx_mlir_sha256": receipt["calyx_mlir_sha256"],
        "futil_sha256": receipt["futil_sha256"],
        **proof_artifacts,
    }


def _compile_identity(
    args: argparse.Namespace,
    *,
    f32_constant_bits_sha256: str | None,
    calyx_memory_bindings_sha256: str | None = None,
) -> dict[str, object]:
    """Return compile-time proof identities without binding runtime oracle data."""

    for label, digest in (
        ("f32 constant-bits receipt", f32_constant_bits_sha256),
        ("Calyx memory bindings", calyx_memory_bindings_sha256),
    ):
        if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"invalid {label} SHA-256")
    return {
        "fixture": _fixture_cache_identity(args),
        "f32_constant_bits_sha256": f32_constant_bits_sha256,
        "calyx_memory_bindings_sha256": calyx_memory_bindings_sha256,
    }


def _runner_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _compiled_cache_metadata(
    args: argparse.Namespace,
    configuration: dict,
    timings: dict,
    artifacts: dict,
    binary: Path,
    root: Path,
    memory_abi_receipt: dict | None = None,
    calyx_memory_bindings: dict | None = None,
) -> dict:
    memory_abi_receipt = _validate_memory_abi_receipt(memory_abi_receipt)
    strict = (
        getattr(args, "equivalence_shard", None) is not None
        or getattr(args, "equivalence_sequence", None) is not None
    )
    if strict:
        calyx_memory_bindings = _validate_calyx_memory_bindings_receipt(
            calyx_memory_bindings
        )
    elif calyx_memory_bindings is not None:
        calyx_memory_bindings = _validate_calyx_memory_bindings_receipt(
            calyx_memory_bindings
        )
    try:
        binary_relative_path = binary.relative_to(root).as_posix()
    except ValueError as error:
        raise RuntimeError("compiled binary is outside its cache root") from error
    return {
        "schema_version": STRICT_CACHE_SCHEMA_VERSION,
        "runner_sha256": _runner_sha256(),
        "inputs": _input_hashes(args),
        "fixture": _fixture_cache_identity(args),
        "compile_identity": _compile_identity(
            args,
            f32_constant_bits_sha256=getattr(args, "f32_constant_bits_sha256", None),
            calyx_memory_bindings_sha256=(
                calyx_memory_bindings["sha256"]
                if calyx_memory_bindings is not None else None
            ),
        ),
        "memory_abi": memory_abi_receipt,
        **(
            {"calyx_memory_bindings": calyx_memory_bindings}
            if calyx_memory_bindings is not None else {}
        ),
        "fixture_defaults": {
            "timeout_cycles": args.timeout_cycles,
            "heartbeat_cycles": args.heartbeat_cycles,
            "stop_after_output": bool(getattr(args, "stop_after_output", False)),
            "trace_output_writes": bool(getattr(args, "trace_output_writes", False)),
        },
        "compile": {
            "simulator": args.simulator,
            "configuration": configuration,
            "timings": timings,
            "artifacts": artifacts,
            "binary_relative_path": binary_relative_path,
        },
    }


def _cache_metadata_path(root: Path) -> Path:
    return root / CACHE_METADATA_FILENAME


def _write_cache_metadata(root: Path, metadata: dict) -> None:
    _cache_metadata_path(root).write_text(
        json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_cache_metadata(
    args: argparse.Namespace, root: Path, verify_inputs: bool
) -> dict | None:
    path = _cache_metadata_path(root)
    if not path.is_file():
        if verify_inputs:
            raise RuntimeError(f"verified run-only requires {path}")
        return None
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        compile_metadata = metadata["compile"]
        cached_inputs = metadata["inputs"]
        cached_fixture = metadata["fixture"]
        cached_identity = metadata["compile_identity"]
        cached_fixture_defaults = metadata["fixture_defaults"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError(f"invalid cached compile metadata: {path}") from error
    if (
        metadata.get("schema_version") != STRICT_CACHE_SCHEMA_VERSION
        or not isinstance(compile_metadata, dict)
        or not isinstance(cached_inputs, dict)
        or not isinstance(cached_fixture, dict)
        or not isinstance(cached_identity, dict)
        or not isinstance(cached_fixture_defaults, dict)
        or not isinstance(compile_metadata.get("configuration"), dict)
        or not isinstance(compile_metadata.get("binary_relative_path"), str)
    ):
        raise RuntimeError(f"unsupported cached compile metadata: {path}")
    if compile_metadata.get("simulator") != args.simulator:
        raise RuntimeError(
            f"cached simulator does not match --simulator: {compile_metadata.get('simulator')}"
        )
    if cached_fixture != _fixture_cache_identity(args):
        raise RuntimeError("cached fixture does not match the requested fixture mode")
    strict = (
        getattr(args, "equivalence_shard", None) is not None
        or getattr(args, "equivalence_sequence", None) is not None
    )
    requested_bindings = getattr(args, "calyx_memory_bindings", None)
    if strict:
        try:
            requested_bindings = _validate_calyx_memory_bindings_receipt(
                requested_bindings
            )
            cached_bindings = _validate_calyx_memory_bindings_receipt(
                metadata["calyx_memory_bindings"]
            )
        except (KeyError, RuntimeError) as error:
            raise RuntimeError(
                f"invalid cached Calyx memory binding receipt: {path}: {error}"
            ) from error
        if cached_bindings != requested_bindings:
            raise RuntimeError(
                "cached Calyx memory binding receipt does not match exact source inputs"
            )
        expected_binding_sha256 = requested_bindings["sha256"]
        configuration = compile_metadata["configuration"]
        if configuration.get("calyx_memory_bindings_sha256") != expected_binding_sha256:
            raise RuntimeError(
                "cached strict configuration binding SHA-256 does not match rebuilt receipt"
            )
        expected_f32_sha256 = getattr(args, "f32_constant_bits_sha256", None)
        if configuration.get("f32_constant_bits_sha256") != expected_f32_sha256:
            raise RuntimeError(
                "cached strict configuration f32 constant-bits SHA-256 does not match exact proof"
            )
        cached_artifacts = compile_metadata.get("artifacts")
        if not isinstance(cached_artifacts, dict):
            raise RuntimeError("cached strict compile artifacts are malformed")
        if cached_artifacts.get("calyx_memory_bindings_sha256") != expected_binding_sha256:
            raise RuntimeError(
                "cached strict artifact binding SHA-256 does not match rebuilt receipt"
            )
        cached_timeout = cached_fixture_defaults.get("timeout_cycles")
        if type(cached_timeout) is not int or cached_timeout != args.timeout_cycles:
            raise RuntimeError(
                "cached strict fixture timeout default does not match --timeout-cycles"
            )
    if cached_identity != _compile_identity(
        args,
        f32_constant_bits_sha256=getattr(args, "f32_constant_bits_sha256", None),
        calyx_memory_bindings_sha256=(
            requested_bindings["sha256"] if requested_bindings is not None else None
        ),
    ):
        raise RuntimeError("cached compile identity does not match requested proof receipts")
    if "memory_abi" not in metadata:
        raise RuntimeError(f"invalid cached memory ABI receipt: {path}: missing receipt")
    cached_memory_abi = metadata["memory_abi"]
    try:
        _validate_memory_abi_receipt(cached_memory_abi)
    except RuntimeError as error:
        raise RuntimeError(f"invalid cached memory ABI receipt: {path}: {error}") from error
    if strict:
        expected_memory_abi = getattr(args, "memory_abi_receipt", None)
        try:
            expected_memory_abi = _validate_memory_abi_receipt(expected_memory_abi)
        except RuntimeError as error:
            raise RuntimeError(
                "strict run-only lacks a rebuilt memory ABI receipt"
            ) from error
        if cached_memory_abi != expected_memory_abi:
            raise RuntimeError(
                "cached memory ABI receipt does not match exact current SV inputs"
            )
    if verify_inputs:
        if metadata.get("runner_sha256") != _runner_sha256():
            raise RuntimeError("cached metadata mismatch for runner_sha256")
        for name, digest in _input_hashes(args).items():
            if cached_inputs.get(name) != digest:
                raise RuntimeError(f"cached metadata mismatch for {name}")
    return metadata


def _strict_runtime_args(
    args: argparse.Namespace,
    shard: dict,
    *,
    oracle_path: Path | None = None,
    context_index_path: Path | None = None,
) -> list[str]:
    """Build runtime plusargs from either verified sources or a private snapshot."""

    source_oracle = oracle_path if oracle_path is not None else shard.get("payload_path")
    if source_oracle is None:
        raise RuntimeError("strict runtime arguments require a materialized oracle payload")
    resolved_oracle = Path(source_oracle).resolve()
    if shard.get("kind") == "sparse-sequence":
        source_context = (
            context_index_path
            if context_index_path is not None
            else shard.get("context_index_path")
        )
        if source_context is None:
            raise RuntimeError(
                "strict sparse runtime arguments require a materialized context index"
            )
        resolved_context = Path(source_context).resolve()
        return [
            f"+oracle_file={resolved_oracle}",
            f"+context_index_file={resolved_context}",
            f"+sequence_count={shard['count']}",
            f"+cycle_bound={args.timeout_cycles}",
        ]
    return [
        f"+oracle_file={resolved_oracle}",
        f"+shard_start={shard['start']}",
        f"+shard_count={shard['count']}",
        f"+cycle_bound={args.timeout_cycles}",
    ]


def _strict_verified_runtime_payload(
    *,
    path: Path | None,
    payload: object,
    expected_sha256: object,
    label: str,
) -> bytes:
    """Read one oracle input only when it still matches verified provenance."""

    if not isinstance(expected_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_sha256
    ):
        raise RuntimeError(f"strict runtime {label} has an invalid verified SHA-256")
    if payload is None:
        if path is None:
            raise RuntimeError(f"strict runtime {label} has no source payload")
        source = Path(path)
        if not source.is_file():
            raise RuntimeError(f"strict runtime {label} is missing: {source}")
        payload = source.read_bytes()
    if not isinstance(payload, bytes):
        raise RuntimeError(f"strict runtime {label} is not bytes")
    if _sha256_bytes(payload) != expected_sha256:
        raise RuntimeError(
            f"strict runtime {label} SHA-256 does not match verified provenance"
        )
    return payload


@contextlib.contextmanager
def _strict_runtime_snapshot(
    *,
    args: argparse.Namespace,
    shard: dict,
    hashes: dict[str, str],
    binary_payload: bytes,
    binary_mode: int,
    memory_payloads: dict[int, bytes],
):
    """Execute a strict cached run from a private, rehashed input snapshot."""

    if _sha256_bytes(binary_payload) != hashes["binary_sha256"]:
        raise RuntimeError(
            "strict runtime executable payload SHA-256 does not match validated cache"
        )
    if type(binary_mode) is not int or not 0 <= binary_mode <= 0o777:
        raise RuntimeError("strict runtime executable mode is invalid")
    if _strict_runtime_memory_sha256_payloads(memory_payloads) != hashes[
        "runtime_memory_sha256"
    ]:
        raise RuntimeError(
            "strict runtime memory payloads do not match validated cache provenance"
        )
    sparse_sequence = shard.get("kind") == "sparse-sequence"
    oracle_payload = _strict_verified_runtime_payload(
        path=shard.get("payload_path"),
        payload=shard.get("payload_bytes") if sparse_sequence else None,
        expected_sha256=shard.get("payload_sha256"),
        label="oracle payload",
    )
    context_index_payload: bytes | None = None
    if sparse_sequence:
        context_index_payload = _strict_verified_runtime_payload(
            path=shard.get("context_index_path"),
            payload=shard.get("context_index_bytes"),
            expected_sha256=shard.get("context_index_sha256"),
            label="oracle context index",
        )

    with tempfile.TemporaryDirectory(prefix="rc-strict-runtime-") as directory:
        runtime_root = Path(directory)
        runtime_binary = runtime_root / "Vtb"
        runtime_binary.write_bytes(binary_payload)
        runtime_binary.chmod(binary_mode)
        if _sha256_path(runtime_binary) != hashes["binary_sha256"]:
            raise RuntimeError(
                "strict runtime executable snapshot SHA-256 does not match validated cache"
            )
        for number in STRICT_RUNTIME_MEMORY_PORTS:
            (runtime_root / f"mem{number}.hex").write_bytes(memory_payloads[number])
        if _strict_runtime_memory_sha256(runtime_root) != hashes["runtime_memory_sha256"]:
            raise RuntimeError(
                "strict runtime memory snapshot SHA-256 does not match validated cache"
            )
        runtime_oracle = runtime_root / "oracle.hex"
        runtime_oracle.write_bytes(oracle_payload)
        if _sha256_path(runtime_oracle) != shard["payload_sha256"]:
            raise RuntimeError(
                "strict runtime oracle snapshot SHA-256 does not match verified provenance"
            )
        runtime_context: Path | None = None
        if context_index_payload is not None:
            runtime_context = runtime_root / "context.indexes"
            runtime_context.write_bytes(context_index_payload)
            if _sha256_path(runtime_context) != shard["context_index_sha256"]:
                raise RuntimeError(
                    "strict runtime context-index snapshot SHA-256 does not match "
                    "verified provenance"
                )
        yield (
            runtime_root,
            runtime_binary,
            _strict_runtime_args(
                args,
                shard,
                oracle_path=runtime_oracle,
                context_index_path=runtime_context,
            ),
        )


def _strict_cache_hashes(artifacts: object) -> dict[str, str]:
    if not isinstance(artifacts, dict):
        raise RuntimeError("strict compiled cache lacks artifact hashes")
    required = (
        "raw_sv_sha256",
        "normalized_sv_sha256",
        "fixture_sha256",
        "binary_sha256",
        "memory_abi_sha256",
        "runtime_memory_sha256",
        "calyx_memory_bindings_sha256",
    )
    result: dict[str, str] = {}
    for name in required:
        value = artifacts.get(name)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RuntimeError(f"strict compiled cache has invalid {name}")
        result[name] = value
    return result


def _validate_strict_cached_file(
    path: Path,
    expected_sha256: str,
    *,
    label: str,
) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"strict cached {label} is missing: {path}")
    payload = path.read_bytes()
    actual_sha256 = _sha256_bytes(payload)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"strict cached {label} SHA-256 does not match metadata")
    return payload


def _strict_expected_fixture_artifacts(
    *,
    raw_sv: str,
    image: bytes,
    manifest: dict,
    memory_abi: dict[int, MemoryPort],
    calyx_memory_bindings: object,
    cycle_bound: int,
) -> tuple[dict[str, bytes], str]:
    """Materialize one isolated, exact snapshot of strict fixture inputs."""

    bindings = _validate_calyx_memory_bindings_receipt(calyx_memory_bindings)
    with tempfile.TemporaryDirectory(prefix="rc-strict-cache-expected-") as directory:
        expected_root = Path(directory)
        (expected_root / "main.sv").write_text(
            _normalized_sv_text(raw_sv), encoding="utf-8"
        )
        (expected_root / "external-memory-bindings.json").write_text(
            bindings["canonical_json"], encoding="utf-8"
        )
        _strict_fixture(
            raw_sv,
            image,
            manifest,
            expected_root,
            cycle_bound=cycle_bound,
            calyx_memory_bindings=bindings,
            memory_abi=memory_abi,
        )
        names = (
            "main.sv",
            "tb.sv",
            "memory-abi.json",
            "external-memory-bindings.json",
            *(f"mem{number}.hex" for number in STRICT_RUNTIME_MEMORY_PORTS),
        )
        expected = {
            name: (expected_root / name).read_bytes()
            for name in names
        }
        runtime_payloads = {
            number: expected[f"mem{number}.hex"]
            for number in STRICT_RUNTIME_MEMORY_PORTS
        }
        return expected, _strict_runtime_memory_sha256_payloads(runtime_payloads)


def _validate_strict_cached_artifacts(
    *,
    root: Path,
    binary: Path,
    hashes: dict[str, str],
    raw_sv: str,
    raw_sv_sha256: str,
    image: bytes,
    manifest: dict,
    memory_abi: dict[int, MemoryPort],
    cycle_bound: int,
    calyx_memory_bindings: object,
) -> tuple[bytes, int, dict[int, bytes]]:
    """Bind a strict run-only launch to exact current fixture inputs."""

    bindings = _validate_calyx_memory_bindings_receipt(calyx_memory_bindings)
    if hashes["calyx_memory_bindings_sha256"] != bindings["sha256"]:
        raise RuntimeError(
            "strict cached artifact binding SHA-256 does not match rebuilt receipt"
        )
    if hashes["raw_sv_sha256"] != raw_sv_sha256:
        raise RuntimeError(
            "strict cached raw SV SHA-256 does not match exact current input snapshot"
        )
    expected, expected_runtime_memory_sha256 = _strict_expected_fixture_artifacts(
        raw_sv=raw_sv,
        image=image,
        manifest=manifest,
        memory_abi=memory_abi,
        calyx_memory_bindings=bindings,
        cycle_bound=cycle_bound,
    )
    if hashes["runtime_memory_sha256"] != expected_runtime_memory_sha256:
        raise RuntimeError(
            "strict cached runtime-memory SHA-256 does not match exact current materialization"
        )

    binary_payload = _validate_strict_cached_file(
        binary, hashes["binary_sha256"], label="Vtb executable"
    )
    binary_mode = binary.stat().st_mode & 0o777
    normalized_sv = _validate_strict_cached_file(
        root / "main.sv", hashes["normalized_sv_sha256"], label="normalized main.sv"
    )
    fixture = _validate_strict_cached_file(
        root / "tb.sv", hashes["fixture_sha256"], label="tb.sv fixture"
    )
    cached_memory_abi_bytes = _validate_strict_cached_file(
        root / "memory-abi.json",
        hashes["memory_abi_sha256"],
        label="memory ABI receipt",
    )
    external_bindings = _validate_strict_cached_file(
        root / "external-memory-bindings.json",
        hashes["calyx_memory_bindings_sha256"],
        label="external memory bindings",
    )
    if normalized_sv != expected["main.sv"]:
        raise RuntimeError(
            "strict cached normalized main.sv does not equal exact current materialization"
        )
    if fixture != expected["tb.sv"]:
        raise RuntimeError(
            "strict cached tb.sv fixture does not equal exact current materialization"
        )
    if cached_memory_abi_bytes != expected["memory-abi.json"]:
        raise RuntimeError(
            "strict cached memory ABI receipt does not equal exact current materialization"
        )
    if external_bindings != expected["external-memory-bindings.json"]:
        raise RuntimeError(
            "strict cached external memory bindings do not equal rebuilt canonical receipt"
        )
    actual_memory_payloads = _strict_runtime_memory_payloads(root)
    actual_memory_sha256 = _strict_runtime_memory_sha256_payloads(actual_memory_payloads)
    if actual_memory_sha256 != expected_runtime_memory_sha256:
        raise RuntimeError(
            "strict runtime memory files do not equal exact current materialization"
        )
    for number in STRICT_RUNTIME_MEMORY_PORTS:
        if actual_memory_payloads[number] != expected[f"mem{number}.hex"]:
            raise RuntimeError(
                f"strict cached mem{number}.hex does not equal exact current materialization"
            )
    return binary_payload, binary_mode, actual_memory_payloads


def _simulator_version(args: argparse.Namespace) -> str:
    command = [args.verilator, "--version"]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return f"unavailable: {error}"
    rendered = (result.stdout or result.stderr).strip()
    return rendered.splitlines()[0] if rendered else f"exit={result.returncode}"


def _strict_result_paths(args: argparse.Namespace, root: Path) -> tuple[Path, Path]:
    receipt_path = args.result_json or root / "equivalence-receipt.json"
    counterexample_path = args.counterexample_json or receipt_path.with_name(
        "counterexample.json"
    )
    return receipt_path, counterexample_path


def _strict_receipt_base(
    *,
    args: argparse.Namespace,
    shard: dict,
    hashes: dict[str, str],
    f32_constant_bits: dict,
    calyx_memory_bindings: dict,
    memory_abi_receipt: dict,
    configuration: dict,
    timings: dict[str, float],
    output: str,
    wall_time_seconds: float,
) -> dict:
    calyx_memory_bindings = _validate_calyx_memory_bindings_receipt(
        calyx_memory_bindings
    )
    memory_abi_receipt = _validate_memory_abi_receipt(memory_abi_receipt)
    cache_hashes = _strict_cache_hashes(hashes)
    cache_identity = _compile_identity(
        args,
        f32_constant_bits_sha256=f32_constant_bits["sha256"],
        calyx_memory_bindings_sha256=calyx_memory_bindings["sha256"],
    )
    return {
        "schema": STRICT_RESULT_SCHEMA,
        "oracle": _strict_oracle_receipt(shard),
        "sv": {
            "raw_sha256": hashes["raw_sv_sha256"],
            "normalized_sha256": hashes["normalized_sv_sha256"],
        },
        "runner_sha256": _runner_sha256(),
        "inputs": _input_hashes(args),
        "f32_constant_bits": f32_constant_bits,
        "calyx_memory_bindings": calyx_memory_bindings,
        "fixture_sha256": hashes["fixture_sha256"],
        "memory_abi": memory_abi_receipt,
        "cache_identity": cache_identity,
        "cache_hashes": cache_hashes,
        "simulator": {
            "name": args.simulator,
            "version": _simulator_version(args),
        },
        "host": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        },
        "range": _strict_shard_range(shard),
        "cycle_bound": args.timeout_cycles,
        "configuration": configuration,
        "timings": timings,
        "wall_time_seconds": wall_time_seconds,
        "simulator_output_sha256": _sha256_bytes(output.encode("utf-8")),
    }


def _strict_oracle_receipt(shard: dict) -> dict:
    if shard.get("kind") == "sparse-sequence":
        result = {
            "kind": "sparse-sequence",
            "schema": shard["schema"],
            "sequence_sha256": shard["sequence_sha256"],
            "payload_sha256": shard["payload_sha256"],
            "context_index_sha256": shard["context_index_sha256"],
            "indexes": shard["indexes"],
            "components": [
                _strict_oracle_receipt(component)
                for component in shard["components"]
            ],
        }
        if shard.get("payload_path") is not None:
            result["payload_path"] = str(shard["payload_path"])
        if shard.get("context_index_path") is not None:
            result["context_index_path"] = str(shard["context_index_path"])
        return result
    metadata = shard["metadata"]
    return {
        "metadata_path": str(shard["metadata_path"]),
        "metadata_sha256": shard["metadata_sha256"],
        "payload_path": str(shard["payload_path"]),
        "payload_sha256": shard["payload_sha256"],
        "receipt": metadata["receipt"],
    }


def _strict_shard_range(shard: dict) -> dict:
    if shard.get("kind") == "sparse-sequence":
        return {"count": shard["count"], "indexes": shard["indexes"]}
    return {
        "start": shard["start"],
        "stop": shard["stop"],
        "count": shard["count"],
    }


def _strict_failure_receipt_base(
    *,
    args: argparse.Namespace,
    shard: dict,
    artifacts: dict[str, int | str],
    f32_constant_bits: dict,
    calyx_memory_bindings: dict | None,
    memory_abi_receipt: dict | None,
    configuration: dict,
    timings: dict[str, float],
    output: str,
    wall_time_seconds: float,
) -> dict:
    """Build the richest strict failure receipt available at a setup boundary."""

    hashes: dict[str, str] | None = None
    if memory_abi_receipt is not None and calyx_memory_bindings is not None:
        try:
            _validate_memory_abi_receipt(memory_abi_receipt)
            _validate_calyx_memory_bindings_receipt(calyx_memory_bindings)
            hashes = _strict_cache_hashes(artifacts)
        except (RuntimeError, TypeError):
            hashes = None
    if hashes is not None:
        return _strict_receipt_base(
            args=args,
            shard=shard,
            hashes=hashes,
            f32_constant_bits=f32_constant_bits,
            calyx_memory_bindings=calyx_memory_bindings,
            memory_abi_receipt=memory_abi_receipt,
            configuration=configuration,
            timings=timings,
            output=output,
            wall_time_seconds=wall_time_seconds,
        )
    base = {
        "schema": STRICT_RESULT_SCHEMA,
        "oracle": _strict_oracle_receipt(shard),
        "range": _strict_shard_range(shard),
        "runner_sha256": _runner_sha256(),
        "inputs": _input_hashes(args),
        "f32_constant_bits": f32_constant_bits,
        "simulator": {
            "name": args.simulator,
            "version": _simulator_version(args),
        },
        "host": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        },
        "cycle_bound": args.timeout_cycles,
        "configuration": configuration,
        "timings": dict(timings),
        "wall_time_seconds": wall_time_seconds,
        "simulator_output_sha256": _sha256_bytes(output.encode("utf-8")),
    }
    if artifacts:
        base["artifacts"] = dict(artifacts)
    if memory_abi_receipt is not None:
        base["memory_abi"] = memory_abi_receipt
    if calyx_memory_bindings is not None:
        base["calyx_memory_bindings"] = calyx_memory_bindings
    return base


def _write_strict_stage_failure(
    *,
    args: argparse.Namespace,
    shard: dict,
    artifacts: dict[str, int | str],
    f32_constant_bits: dict,
    calyx_memory_bindings: dict | None,
    memory_abi_receipt: dict | None,
    configuration: dict,
    timings: dict[str, float],
    stage: str,
    error: Exception,
    receipt_path: Path,
    counterexample_path: Path,
    wall_time_seconds: float,
    command: list[str] | None = None,
    output: str | None = None,
    returncode: int | None = None,
) -> None:
    """Persist a failed strict receipt without requiring complete provenance."""

    rendered_output = "" if output is None else output
    base = _strict_failure_receipt_base(
        args=args,
        shard=shard,
        artifacts=artifacts,
        f32_constant_bits=f32_constant_bits,
        calyx_memory_bindings=calyx_memory_bindings,
        memory_abi_receipt=memory_abi_receipt,
        configuration=configuration,
        timings=timings,
        output=rendered_output,
        wall_time_seconds=wall_time_seconds,
    )
    counterexample = {
        "status": "fail",
        "stage": stage,
        "error": str(error),
        "oracle": base["oracle"],
        "range": base["range"],
        "f32_constant_bits": f32_constant_bits,
    }
    if calyx_memory_bindings is not None:
        counterexample["calyx_memory_bindings"] = calyx_memory_bindings
    if command is not None:
        counterexample["command"] = command
    if output is not None:
        counterexample["output"] = output
    if returncode is not None:
        counterexample["returncode"] = returncode
    failed = dict(base)
    failed.update({"status": "fail", "failure": counterexample})
    _write_json(counterexample_path, counterexample)
    _write_json(receipt_path, failed)
    _write_json(args.timing_json, failed)


def _subprocess_error_output(
    error: OSError | subprocess.CalledProcessError,
) -> str:
    """Return captured command output without obscuring the original failure."""

    output = getattr(error, "stdout", None)
    if output is None:
        output = getattr(error, "output", None)
    if output is None:
        output = getattr(error, "stderr", None)
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output if isinstance(output, str) else ""


def _run_strict_equivalence(
    args: argparse.Namespace,
    *,
    verilate_jobs: int,
    build_jobs: int,
) -> None:
    """Compile or run a generic strict fixture against one verified shard."""

    assert args.work_dir is not None  # enforced at the CLI boundary
    args.work_dir.mkdir(parents=True, exist_ok=True)
    root = args.work_dir
    receipt_path, counterexample_path = _strict_result_paths(args, root)
    f32_constant_bits: dict | None = None
    calyx_memory_bindings: dict | None = None
    memory_abi_receipt: dict | None = None
    try:
        f32_constant_bits = _load_f32_constant_bits_receipt(
            args.f32_constant_bits,
            strict=True,
            calyx_mlir_path=args.f32_calyx_mlir,
            raw_futil_path=args.f32_raw_futil,
        )
        assert f32_constant_bits is not None
        args.f32_constant_bits_sha256 = f32_constant_bits["sha256"]
        image_bytes = args.image.read_bytes()
        manifest_bytes = args.manifest.read_bytes()
        manifest = json.loads(manifest_bytes)
        support_sv = [path.read_bytes() for path in args.support_sv]
        raw_sv_bytes = args.sv.read_bytes()
        if support_sv:
            raw_sv_bytes += b"\n" + b"\n".join(support_sv)
        raw_sv = raw_sv_bytes.decode("utf-8")
        for support in args.support_file:
            shutil.copy2(support, root / support.name)
        flat_scf_bytes = args.flat_scf.read_bytes()
        pre_calyx_bytes = args.pre_calyx.read_bytes()
        args.strict_input_hashes = {
            "sv_sha256": _sha256_bytes(raw_sv_bytes),
            "image_sha256": _sha256_bytes(image_bytes),
            "manifest_sha256": _sha256_bytes(manifest_bytes),
            "flat_scf_sha256": _sha256_bytes(flat_scf_bytes),
            "pre_calyx_sha256": _sha256_bytes(pre_calyx_bytes),
        }
        memory_abi = _memory_abi(raw_sv)
        memory_abi_receipt = _memory_abi_receipt(memory_abi)
        args.memory_abi_receipt = memory_abi_receipt
        calyx_memory_bindings = _build_calyx_memory_bindings(
            flat_scf=flat_scf_bytes,
            pre_calyx=pre_calyx_bytes,
            image=image_bytes,
            manifest=manifest,
            abi=memory_abi,
            manifest_bytes=manifest_bytes,
        )
        calyx_memory_bindings = _validate_calyx_memory_bindings_receipt(
            calyx_memory_bindings
        )
        args.calyx_memory_bindings = calyx_memory_bindings
        args.calyx_memory_bindings_sha256 = calyx_memory_bindings["sha256"]
        if not args.run_only:
            (root / "external-memory-bindings.json").write_text(
                calyx_memory_bindings["canonical_json"], encoding="utf-8"
            )
        if args.equivalence_sequence is not None:
            shard = _verified_equivalence_sequence(
                args.equivalence_sequence,
                None if args.run_only and not args.fixture_only else root,
                image_bytes=image_bytes,
                manifest_bytes=manifest_bytes,
            )
        else:
            shard = _verified_equivalence_shard(args.equivalence_shard)
            _validate_oracle_image_provenance(
                shard["metadata"], image_bytes=image_bytes, manifest_bytes=manifest_bytes
            )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        counterexample = {
            "status": "fail",
            "stage": "preflight",
            "error": str(error),
        }
        if f32_constant_bits is not None:
            counterexample["f32_constant_bits"] = f32_constant_bits
        if calyx_memory_bindings is not None:
            counterexample["calyx_memory_bindings"] = calyx_memory_bindings
        failed = {
            "schema": STRICT_RESULT_SCHEMA,
            "status": "fail",
            "failure": counterexample,
        }
        if f32_constant_bits is not None:
            failed["f32_constant_bits"] = f32_constant_bits
        if calyx_memory_bindings is not None:
            failed["calyx_memory_bindings"] = calyx_memory_bindings
        try:
            failed["inputs"] = _input_hashes(args)
        except OSError:
            pass
        _write_json(counterexample_path, counterexample)
        _write_json(receipt_path, failed)
        _write_json(args.timing_json, failed)
        raise RuntimeError(
            f"strict observable shard preflight failed; counterexample written to {counterexample_path}"
        ) from error
    post_preflight_start = time.perf_counter()
    timings: dict[str, float] = {}
    artifacts: dict[str, int | str] = {}
    validated_runtime_snapshot: tuple[bytes, int, dict[int, bytes]] | None = None
    configuration = {
        "verilate_jobs": verilate_jobs,
        "build_jobs": build_jobs,
        "verilator_threads": args.verilator_threads,
        "verilator_output_split": args.verilator_output_split,
        "verilator_output_split_cfuncs": args.verilator_output_split_cfuncs,
        "fixture_schema": STRICT_FIXTURE_SCHEMA,
        "f32_constant_bits_sha256": f32_constant_bits["sha256"],
        "calyx_memory_bindings_sha256": calyx_memory_bindings["sha256"],
    }
    normalized_sv = root / "main.sv"
    tb = root / "tb.sv"
    cached_compile: dict | None = None

    def fail_strict_stage(
        stage: str,
        error: Exception,
        *,
        command: list[str] | None = None,
        output: str | None = None,
        returncode: int | None = None,
    ) -> None:
        _write_strict_stage_failure(
            args=args,
            shard=shard,
            artifacts=artifacts,
            f32_constant_bits=f32_constant_bits,
            calyx_memory_bindings=calyx_memory_bindings,
            memory_abi_receipt=memory_abi_receipt,
            configuration=configuration,
            timings=timings,
            stage=stage,
            error=error,
            receipt_path=receipt_path,
            counterexample_path=counterexample_path,
            wall_time_seconds=time.perf_counter() - post_preflight_start,
            command=command,
            output=output,
            returncode=returncode,
        )
        raise RuntimeError(
            f"strict observable shard {stage} failed; "
            f"counterexample written to {counterexample_path}"
        ) from error

    if not args.run_only:
        fixture_setup_start = time.perf_counter()
        try:
            normalize_start = time.perf_counter()
            normalized_text = _normalized_sv_text(raw_sv)
            normalized_sv.write_text(normalized_text, encoding="utf-8")
            artifacts.update(_normalization_metrics(raw_sv, normalized_text))
            artifacts["raw_sv_sha256"] = args.strict_input_hashes["sv_sha256"]
            artifacts["normalized_sv_sha256"] = _sha256_bytes(normalized_text.encode("utf-8"))
            timings["normalization_seconds"] = time.perf_counter() - normalize_start
            fixture_start = time.perf_counter()
            tb = _strict_fixture(
                raw_sv,
                image_bytes,
                json.loads(manifest_bytes),
                root,
                cycle_bound=args.timeout_cycles,
                calyx_memory_bindings=calyx_memory_bindings,
                memory_abi=memory_abi,
            )
            artifacts["fixture_sha256"] = _sha256_path(tb)
            artifacts["memory_abi_sha256"] = _sha256_path(root / "memory-abi.json")
            artifacts["runtime_memory_sha256"] = _strict_runtime_memory_sha256(root)
            artifacts["calyx_memory_bindings_sha256"] = calyx_memory_bindings[
                "sha256"
            ]
            timings["fixture_generation_seconds"] = time.perf_counter() - fixture_start
        except Exception as error:
            timings["fixture_setup_seconds"] = time.perf_counter() - fixture_setup_start
            fail_strict_stage("fixture_setup", error)
    if args.fixture_only:
        print(json.dumps({
            "status": "strict-fixture",
            "work_dir": str(root),
            "inputs": _input_hashes(args),
            "runtime_args": _strict_runtime_args(args, shard),
            "memory_abi": memory_abi_receipt,
            "fixture_schema": STRICT_FIXTURE_SCHEMA,
            "f32_constant_bits": f32_constant_bits,
            "calyx_memory_bindings": calyx_memory_bindings,
        }, sort_keys=True))
        return
    binary = root / "obj_dir/Vtb"
    hashes: dict[str, str] | None = None
    if args.run_only:
        cache_validation_start = time.perf_counter()
        try:
            cached_metadata = _load_cache_metadata(args, root, verify_inputs=True)
            assert cached_metadata is not None
            cached_compile = cached_metadata["compile"]
            binary_relative_path = Path(cached_compile.get("binary_relative_path", ""))
            if (
                binary_relative_path.is_absolute()
                or ".." in binary_relative_path.parts
                or not binary_relative_path.parts
            ):
                raise RuntimeError("cached binary path is not relative to the cache root")
            binary = root / binary_relative_path
            if not binary.is_file():
                raise RuntimeError(f"cached binary is missing: {binary}")
            configuration = cached_compile["configuration"]
            artifacts = dict(cached_compile.get("artifacts", {}))
            hashes = _strict_cache_hashes(artifacts)
            validated_runtime_snapshot = _validate_strict_cached_artifacts(
                root=root,
                binary=binary,
                hashes=hashes,
                raw_sv=raw_sv,
                raw_sv_sha256=args.strict_input_hashes["sv_sha256"],
                image=image_bytes,
                manifest=manifest,
                memory_abi=memory_abi,
                cycle_bound=args.timeout_cycles,
                calyx_memory_bindings=calyx_memory_bindings,
            )
        except Exception as error:
            timings["cache_validation_seconds"] = (
                time.perf_counter() - cache_validation_start
            )
            fail_strict_stage("cache_validation", error)
    if memory_abi_receipt is None:
        stage = "cache_validation" if args.run_only else "fixture_setup"
        fail_strict_stage(
            stage, RuntimeError("a strict run requires a complete memory ABI receipt")
        )
    if not args.run_only:
        codegen_start = time.perf_counter()
        codegen_command = _verilator_codegen_command(
            args, normalized_sv, tb, root / "obj_dir", verilate_jobs
        )
        try:
            codegen = subprocess.run(
                codegen_command,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            timings["verilator_codegen_seconds"] = time.perf_counter() - codegen_start
            fail_strict_stage(
                "verilator_codegen",
                command=codegen_command,
                error=error,
                output=_subprocess_error_output(error),
                returncode=getattr(error, "returncode", None),
            )
        timings["verilator_codegen_seconds"] = time.perf_counter() - codegen_start
        if codegen.stdout:
            print(codegen.stdout, end="")
        try:
            artifacts.update(_generated_cpp_metrics(root / "obj_dir"))
        except Exception as error:
            fail_strict_stage("codegen_artifact_metrics", error)
        build_start = time.perf_counter()
        build_command = _verilator_build_command(args, root / "obj_dir", build_jobs)
        try:
            build = subprocess.run(
                build_command,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            timings["cpp_build_seconds"] = time.perf_counter() - build_start
            fail_strict_stage(
                "cpp_build",
                command=build_command,
                error=error,
                output=_subprocess_error_output(error),
                returncode=getattr(error, "returncode", None),
            )
        timings["cpp_build_seconds"] = time.perf_counter() - build_start
        if build.stdout:
            print(build.stdout, end="")
        try:
            timings["verilator_compile_seconds"] = (
                timings["verilator_codegen_seconds"] + timings["cpp_build_seconds"]
            )
            artifacts["binary_bytes"] = binary.stat().st_size
            artifacts["binary_sha256"] = _sha256_path(binary)
            _write_cache_metadata(
                root,
                _compiled_cache_metadata(
                    args,
                    configuration,
                    timings,
                    artifacts,
                    binary,
                    root,
                    memory_abi_receipt,
                    calyx_memory_bindings,
                ),
            )
            hashes = _strict_cache_hashes(artifacts)
        except Exception as error:
            fail_strict_stage("compile_cache_metadata", error)
    if hashes is None:
        stage = "cache_validation" if args.run_only else "compile_artifact_validation"
        try:
            hashes = _strict_cache_hashes(artifacts)
        except Exception as error:
            fail_strict_stage(stage, error)
    if args.compile_only:
        result = {
            "status": "strict-compiled",
            "binary": str(binary),
            "inputs": _input_hashes(args),
            "timings": timings,
            "artifacts": artifacts,
            "configuration": configuration,
            "memory_abi": memory_abi_receipt,
            "fixture_schema": STRICT_FIXTURE_SCHEMA,
            "f32_constant_bits": f32_constant_bits,
            "calyx_memory_bindings": calyx_memory_bindings,
        }
        print(json.dumps(result, sort_keys=True))
        _write_json(args.timing_json, result)
        return

    runtime_start = time.perf_counter()
    try:
        if args.run_only:
            if validated_runtime_snapshot is None:
                raise RuntimeError("strict cached runtime snapshot was not validated")
            binary_payload, binary_mode, memory_payloads = validated_runtime_snapshot
            with _strict_runtime_snapshot(
                args=args,
                shard=shard,
                hashes=hashes,
                binary_payload=binary_payload,
                binary_mode=binary_mode,
                memory_payloads=memory_payloads,
            ) as (runtime_root, runtime_binary, runtime_args):
                completed = subprocess.run(
                    [str(runtime_binary), *runtime_args],
                    cwd=str(runtime_root),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
        else:
            runtime_args = _strict_runtime_args(args, shard)
            completed = subprocess.run(
                [str(binary), *runtime_args],
                cwd=str(root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
    except (OSError, RuntimeError) as error:
        timings["simulation_launch_seconds"] = time.perf_counter() - runtime_start
        fail_strict_stage("simulation_launch", error)
    timings["simulation_seconds"] = time.perf_counter() - runtime_start
    output = completed.stdout or ""
    base = _strict_receipt_base(
        args=args,
        shard=shard,
        hashes=hashes,
        f32_constant_bits=f32_constant_bits,
        calyx_memory_bindings=calyx_memory_bindings,
        memory_abi_receipt=memory_abi_receipt,
        configuration=configuration,
        timings=timings,
        output=output,
        wall_time_seconds=timings["simulation_seconds"],
    )
    try:
        if shard.get("kind") == "sparse-sequence":
            parsed = _parse_sequence_output(
                output,
                expected_indexes=shard["indexes"],
                cycle_bound=args.timeout_cycles,
            )
        else:
            parsed = _parse_shard_output(
                output,
                expected_start=shard["start"],
                expected_count=shard["count"],
                cycle_bound=args.timeout_cycles,
                _require_lifecycle_evidence=True,
            )
        if completed.returncode != 0:
            raise ShardOutputError(
                f"simulator exited {completed.returncode} after a purported strict transcript"
            )
    except (RuntimeError, ValueError, OverflowError) as error:
        counterexample = {
            "status": "fail",
            "stage": "simulation_result",
            "error": str(error),
            "returncode": completed.returncode,
            "simulator_output": output.splitlines(),
            "oracle": base["oracle"],
            "range": base["range"],
            "f32_constant_bits": f32_constant_bits,
            "calyx_memory_bindings": base["calyx_memory_bindings"],
            "memory_abi": base["memory_abi"],
            "cache_identity": base["cache_identity"],
            "cache_hashes": base["cache_hashes"],
        }
        if isinstance(error, ShardOutputError) and error.counterexample is not None:
            counterexample["case"] = error.counterexample
        failed = dict(base)
        failed.update({"status": "fail", "failure": counterexample})
        _write_json(counterexample_path, counterexample)
        _write_json(receipt_path, failed)
        _write_json(args.timing_json, failed)
        raise RuntimeError(
            f"strict observable shard failed; counterexample written to {counterexample_path}"
        ) from error
    passed = dict(base)
    passed.update({"status": "pass", **parsed})
    if cached_compile is not None:
        passed["cached_compile"] = cached_compile
    _write_json(receipt_path, passed)
    _write_json(args.timing_json, passed)
    print(json.dumps(passed, sort_keys=True))


def main_from_args(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv", type=Path)
    parser.add_argument("--support-sv", type=Path, action="append", default=[])
    parser.add_argument("--support-file", type=Path, action="append", default=[])
    parser.add_argument("--image", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--flat-scf",
        type=Path,
        help="exact source flat-SCF MLIR used to derive strict memory bindings",
    )
    parser.add_argument(
        "--pre-calyx",
        type=Path,
        help="exact pre-Calyx MLIR used to order strict external memories",
    )
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--iverilog", default="iverilog")
    parser.add_argument("--vvp", default="vvp")
    parser.add_argument("--make", default="make")
    parser.add_argument("--simulator", choices=("verilator", "iverilog"), default="verilator")
    parser.add_argument("--verilator-jobs", type=int, help="set both Verilator and C++ build jobs")
    parser.add_argument("--verilate-jobs", type=int, help="Verilator front-end/code-generation jobs")
    parser.add_argument("--build-jobs", type=int, help="generated-C++ build jobs")
    parser.add_argument("--verilator-threads", type=int, default=1)
    parser.add_argument("--verilator-output-split", type=int, default=100)
    parser.add_argument("--verilator-output-split-cfuncs", type=int, default=50)
    parser.add_argument("--timeout-cycles", type=int, default=1_000_000)
    parser.add_argument("--heartbeat-cycles", type=int, default=0)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--counterexample-json", type=Path)
    parser.add_argument("--timing-json", type=Path)
    parser.add_argument(
        "--reduce-frozen-four",
        action="store_true",
        help="reduce strict fresh and sequential receipts into one durable frozen-gate summary",
    )
    parser.add_argument(
        "--fresh-receipt",
        action="append",
        default=[],
        help="ordered frozen-gate fresh receipt as NAME=PATH (repeatable)",
    )
    parser.add_argument(
        "--sequential-receipt",
        type=Path,
        help="one ordered sparse-sequence receipt for --reduce-frozen-four",
    )
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument(
        "--verify-cache",
        action="store_true",
        help="require run-only inputs to match metadata written by the compiled cache",
    )
    parser.add_argument("--fixture-only", action="store_true")
    parser.add_argument("--case-id", help="run only one reference case")
    parser.add_argument(
        "--static-fixture-case",
        action="store_true",
        help="compile only --case-id into the fixture instead of selecting it at runtime",
    )
    parser.add_argument("--stop-after-output", action="store_true")
    parser.add_argument("--trace-output-writes", action="store_true")
    parser.add_argument(
        "--equivalence-shard",
        type=Path,
        help="Task-1 oracle shard metadata for strict payload-neutral equivalence",
    )
    parser.add_argument(
        "--equivalence-sequence",
        type=Path,
        nargs="+",
        help="ordered one-record Task-1 oracle shards for one sparse reset sequence",
    )
    parser.add_argument(
        "--f32-constant-bits",
        type=Path,
        help="Task-2 exact Calyx-to-Futil constant-bit receipt required by strict equivalence",
    )
    parser.add_argument(
        "--f32-calyx-mlir",
        type=Path,
        help="exact normalized Calyx MLIR hashed by --f32-constant-bits",
    )
    parser.add_argument(
        "--f32-raw-futil",
        type=Path,
        help="exact raw CIRCT Futil hashed by --f32-constant-bits",
    )
    args = parser.parse_args(argv)
    if args.reduce_frozen_four:
        if any((
            args.compile_only,
            args.run_only,
            args.fixture_only,
            args.equivalence_shard is not None,
            args.equivalence_sequence is not None,
        )):
            parser.error("--reduce-frozen-four does not accept simulation controls")
        try:
            _run_frozen_four_reducer(args)
        except (
            OSError, RuntimeError, ValueError, json.JSONDecodeError,
            TypeError, AttributeError, KeyError, IndexError,
        ) as error:
            parser.error(str(error))
        return
    if args.fresh_receipt or args.sequential_receipt is not None:
        parser.error("--fresh-receipt and --sequential-receipt require --reduce-frozen-four")
    if sum(bool(value) for value in (args.compile_only, args.run_only, args.fixture_only)) > 1:
        parser.error("--compile-only, --run-only, and --fixture-only are mutually exclusive")
    if args.run_only and args.work_dir is None:
        parser.error("--run-only requires --work-dir")
    if args.verify_cache and not args.run_only:
        parser.error("--verify-cache requires --run-only")
    if args.static_fixture_case and args.case_id is None:
        parser.error("--static-fixture-case requires --case-id")
    if args.timeout_cycles <= 0:
        parser.error("--timeout-cycles must be positive")
    if args.heartbeat_cycles < 0:
        parser.error("--heartbeat-cycles must be nonnegative")
    if args.verilator_threads <= 0:
        parser.error("--verilator-threads must be positive")
    try:
        verilate_jobs, build_jobs = _resolved_verilator_jobs(args)
    except ValueError as error:
        parser.error(str(error))
    if args.equivalence_shard is not None and args.equivalence_sequence is not None:
        parser.error("--equivalence-shard and --equivalence-sequence are mutually exclusive")
    strict_equivalence = (
        args.equivalence_shard is not None or args.equivalence_sequence is not None
    )
    if strict_equivalence:
        if args.stop_after_output or args.trace_output_writes:
            parser.error(
                "--equivalence-shard rejects --stop-after-output and --trace-output-writes"
            )
        if args.case_id is not None or args.static_fixture_case:
            parser.error("strict equivalence rejects static reference-case controls")
        if args.reference is not None:
            parser.error("strict equivalence does not accept --reference")
        if (
            args.f32_constant_bits is None
            or args.f32_calyx_mlir is None
            or args.f32_raw_futil is None
        ):
            parser.error(
                "strict equivalence requires --f32-constant-bits --f32-calyx-mlir --f32-raw-futil"
            )
        missing_source_ir = [
            flag
            for flag, value in (
                ("--flat-scf", args.flat_scf),
                ("--pre-calyx", args.pre_calyx),
            )
            if value is None
        ]
        if missing_source_ir:
            parser.error(
                f"strict equivalence requires {' '.join(missing_source_ir)}"
            )
        if args.heartbeat_cycles != 0:
            parser.error("--equivalence-shard rejects heartbeat diagnostics")
        if args.simulator != "verilator":
            parser.error("--equivalence-shard requires --simulator verilator")
        if args.work_dir is None:
            parser.error("--equivalence-shard requires --work-dir for durable evidence")
        if args.run_only and not args.verify_cache:
            parser.error("strict --run-only requires --verify-cache")
        missing = [
            flag
            for flag, value in (
                ("--sv", args.sv),
                ("--image", args.image),
                ("--manifest", args.manifest),
            )
            if value is None
        ]
        if missing:
            parser.error(f"--equivalence-shard requires {' '.join(missing)}")
        _run_strict_equivalence(
            args, verilate_jobs=verilate_jobs, build_jobs=build_jobs
        )
        return
    missing = [
        flag
        for flag, value in (
            ("--sv", args.sv),
            ("--image", args.image),
            ("--manifest", args.manifest),
            ("--reference", args.reference),
        )
        if value is None
    ]
    if missing:
        parser.error(f"diagnostic mode requires {' '.join(missing)}")
    reference = json.loads(args.reference.read_text())
    if args.case_id is not None:
        _case_index(reference, args.case_id)
    if args.work_dir is None:
        work_context = tempfile.TemporaryDirectory(prefix="rc-sv-equiv-")
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        work_context = contextlib.nullcontext(str(args.work_dir))
    with work_context as directory:
        root = Path(directory)
        timings: dict[str, float] = {}
        artifacts: dict[str, int] = {}
        configuration = {
            "verilate_jobs": verilate_jobs,
            "build_jobs": build_jobs,
            "verilator_threads": args.verilator_threads,
            "verilator_output_split": args.verilator_output_split,
            "verilator_output_split_cfuncs": args.verilator_output_split_cfuncs,
        }
        normalized_sv = root / "main.sv"
        tb = root / "tb.sv"
        cached_compile: dict | None = None
        memory_abi_receipt: dict | None = None
        if not args.run_only:
            normalize_start = time.perf_counter()
            sv = args.sv.read_text(encoding="utf-8")
            if args.support_sv:
                sv += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in args.support_sv)
            memory_abi = _memory_abi(sv)
            memory_abi_receipt = _memory_abi_receipt(memory_abi)
            # CIRCT's native Calyx printer can emit a very large single line
            # of Verilog. This is a simulation-only lexical normalization.
            normalized_text = _normalized_sv_text(sv)
            normalized_sv.write_text(normalized_text, encoding="utf-8")
            artifacts.update(_normalization_metrics(sv, normalized_text))
            timings["normalization_seconds"] = time.perf_counter() - normalize_start
            fixture_start = time.perf_counter()
            tb = _fixture(
                sv,
                args.image.read_bytes(),
                json.loads(args.manifest.read_text()),
                reference,
                root,
                args.timeout_cycles,
                args.heartbeat_cycles,
                args.case_id,
                args.stop_after_output,
                args.trace_output_writes,
                args.case_id if args.static_fixture_case else None,
                memory_abi,
            )
            timings["fixture_generation_seconds"] = time.perf_counter() - fixture_start
        if args.fixture_only:
            print(json.dumps({
                "status": "fixture",
                "work_dir": str(root),
                "runtime_args": _runtime_args(args, reference),
                "memory_abi": memory_abi_receipt,
            }, sort_keys=True))
            return
        binary = root / ("obj_dir/Vtb" if args.simulator == "verilator" else "tb.vvp")
        if args.run_only:
            cached_metadata = _load_cache_metadata(args, root, args.verify_cache)
            if cached_metadata is not None:
                cached_compile = cached_metadata["compile"]
                memory_abi_receipt = cached_metadata["memory_abi"]
                binary_relative_path = Path(cached_compile.get("binary_relative_path", ""))
                if (
                    binary_relative_path.is_absolute()
                    or ".." in binary_relative_path.parts
                    or not binary_relative_path.parts
                ):
                    raise RuntimeError("cached binary path is not relative to the cache root")
                binary = root / binary_relative_path
                if not binary.is_file():
                    raise RuntimeError(f"cached binary is missing: {binary}")
                configuration = cached_compile["configuration"]
        if memory_abi_receipt is None:
            raise RuntimeError("a run requires a complete memory ABI receipt")
        if not args.run_only and args.simulator == "verilator":
            codegen_start = time.perf_counter()
            subprocess.run(
                _verilator_codegen_command(
                    args, normalized_sv, tb, root / "obj_dir", verilate_jobs
                ),
                check=True,
            )
            timings["verilator_codegen_seconds"] = time.perf_counter() - codegen_start
            artifacts.update(_generated_cpp_metrics(root / "obj_dir"))
            build_start = time.perf_counter()
            subprocess.run(
                _verilator_build_command(args, root / "obj_dir", build_jobs),
                check=True,
            )
            timings["cpp_build_seconds"] = time.perf_counter() - build_start
            timings["verilator_compile_seconds"] = (
                timings["verilator_codegen_seconds"] + timings["cpp_build_seconds"]
            )
            artifacts["binary_bytes"] = binary.stat().st_size
        elif not args.run_only and args.simulator == "iverilog":
            binary = root / "tb.vvp"
            iverilog_start = time.perf_counter()
            subprocess.run([args.iverilog, "-g2012", "-s", "tb", "-o", str(binary), str(normalized_sv), str(tb)], check=True)
            timings["iverilog_compile_seconds"] = time.perf_counter() - iverilog_start
        if not args.run_only:
            _write_cache_metadata(
                root,
                _compiled_cache_metadata(
                    args,
                    configuration,
                    timings,
                    artifacts,
                    binary,
                    root,
                    memory_abi_receipt,
                ),
            )
        if args.compile_only:
            result = {
                "status": "compiled",
                "binary": str(binary),
                "timings": timings,
                "artifacts": artifacts,
                "configuration": configuration,
                "memory_abi": memory_abi_receipt,
            }
            print(json.dumps(result, sort_keys=True))
            _write_json(args.timing_json, result)
            return
        run_kwargs = {"text": True, "cwd": str(root)}
        runtime_args = _runtime_args(args, reference)
        runtime_start = time.perf_counter()
        output = subprocess.check_output([str(binary), *runtime_args], **run_kwargs) if args.simulator == "verilator" else subprocess.check_output([args.vvp, str(binary), *runtime_args], **run_kwargs)
        timings["simulation_seconds"] = time.perf_counter() - runtime_start
        expected_rows = reference["results"]
        if args.case_id is not None:
            expected_rows = [row for row in expected_rows if row["case_id"] == args.case_id]
        expected = {row["case_id"]: row["output_codes_i8"] for row in expected_rows}
        expected_token_ids = {row["case_id"]: row["token_id"] for row in expected_rows}
        observed = {}
        for line in output.splitlines():
            match = re.match(r"RESULT (\S+) ([-0-9 ]+)$", line)
            if match:
                observed[match.group(1)] = [int(x) for x in match.group(2).split()]
        observed_token_ids = {
            case_id: max(range(len(codes)), key=lambda index: codes[index])
            for case_id, codes in observed.items()
        }
        if observed != expected or observed_token_ids != expected_token_ids:
            raise SystemExit(json.dumps({
                "status": "fail",
                "expected": expected,
                "observed": observed,
                "expected_token_ids": expected_token_ids,
                "observed_token_ids": observed_token_ids,
                "simulator_output": output.splitlines(),
            }, sort_keys=True))
        result = {
            "status": "pass",
            "cases": len(expected),
            "logits": 6,
            "token_ids": observed_token_ids,
            "timings": timings,
            "artifacts": artifacts,
            "configuration": configuration,
            "memory_abi": memory_abi_receipt,
        }
        if cached_compile is not None:
            result["cached_compile"] = cached_compile
        rendered = json.dumps(result, sort_keys=True)
        print(rendered)
        if args.result_json is not None:
            args.result_json.parent.mkdir(parents=True, exist_ok=True)
            args.result_json.write_text(rendered + "\n", encoding="utf-8")
        _write_json(args.timing_json, result)


def main() -> None:
    main_from_args(None)


if __name__ == "__main__":
    main()
