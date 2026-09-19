#!/usr/bin/env python3
"""Build and verify the authenticated fixed-width compiler DDR3 replay stream.

The response bytes are copied from the observed Wishbone transaction stream.
They are deliberately not reconstructed from the static model image: the trace
also includes runtime memory traffic.  The image hash binds this package to the
authenticated image receipt; ``verify_replay`` independently compares every
binary record with the source trace before the binary replaces its destination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import BinaryIO


REQUEST = re.compile(rb"Q ([0-9]+) ([0-9a-f]{8})\n\Z")
RESPONSE = re.compile(rb"R ([0-9]+) ([0-9a-f]{8}) ([0-9a-f]{32})\n\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
RECORD_BYTES = 20
MAX_TRACE_LINE_BYTES = 96
BYTE_ORDER = "little-endian uint32 address; Wishbone lane-order response bytes"


class TraceReplayError(ValueError):
    """The supplied trace or its authenticated bindings are not acceptable."""


def _read_line(stream: BinaryIO, digest, path: Path, line_number: int) -> bytes:
    line = stream.readline(MAX_TRACE_LINE_BYTES)
    if line:
        digest.update(line)
    if line and not line.endswith(b"\n"):
        raise TraceReplayError(f"{path}:{line_number}: record exceeds {MAX_TRACE_LINE_BYTES - 1} bytes")
    return line


def _bindings(bindings: dict[str, object]) -> dict[str, object]:
    expected = {"source_trace_sha256", "candidate_sha256", "image_sha256", "prompt", "token"}
    if set(bindings) != expected:
        raise TraceReplayError(f"bindings must contain exactly {sorted(expected)}")
    result = dict(bindings)
    for key in ("source_trace_sha256", "candidate_sha256", "image_sha256"):
        value = result[key]
        if not isinstance(value, str) or SHA256.fullmatch(value) is None:
            raise TraceReplayError(f"{key} must be a lowercase SHA-256 digest")
    prompt = result["prompt"]
    if (not isinstance(prompt, list) or not prompt or
            any(not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 0xffffffff
                for value in prompt)):
        raise TraceReplayError("prompt must be a non-empty list of uint32 token IDs")
    token = result["token"]
    if not isinstance(token, int) or isinstance(token, bool) or token < 0 or token > 0xffffffff:
        raise TraceReplayError("token must be a uint32 token ID")
    return result


def _request(line: bytes, path: Path, line_number: int, sequence: int) -> int:
    match = REQUEST.fullmatch(line)
    if match is None or int(match[1]) != sequence:
        raise TraceReplayError(f"{path}:{line_number}: malformed, reordered, or duplicate request")
    return int(match[2], 16)


def _response(line: bytes, path: Path, line_number: int, sequence: int, address: int) -> bytes:
    match = RESPONSE.fullmatch(line)
    if match is None or int(match[1]) != sequence:
        raise TraceReplayError(f"{path}:{line_number}: malformed, reordered, or duplicate response")
    if int(match[2], 16) != address:
        raise TraceReplayError(f"{path}:{line_number}: response address differs from request")
    # %032h prints the MSB first; Wishbone lane 0 is the least-significant byte.
    return bytes.fromhex(match[3].decode("ascii"))[::-1]


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def verify_replay(trace: Path, replay: Path, bindings: dict[str, object]) -> dict[str, object]:
    """Independently stream-compare every replay record with ``trace``."""
    checked = _bindings(bindings)
    source_digest, replay_digest = hashlib.sha256(), hashlib.sha256()
    records, line_number = 0, 0
    with trace.open("rb") as source, replay.open("rb") as binary:
        while True:
            line_number += 1
            request_line = _read_line(source, source_digest, trace, line_number)
            if not request_line:
                break
            address = _request(request_line, trace, line_number, records)
            line_number += 1
            response_line = _read_line(source, source_digest, trace, line_number)
            if not response_line:
                raise TraceReplayError(f"{trace}:{line_number}: missing response")
            expected = struct.pack("<I", address) + _response(
                response_line, trace, line_number, records, address)
            observed = binary.read(RECORD_BYTES)
            replay_digest.update(observed)
            if observed != expected:
                raise TraceReplayError(f"{replay}: replay record {records} differs from source trace")
            records += 1
        trailing = binary.read(1)
        replay_digest.update(trailing)
        if trailing:
            raise TraceReplayError(f"{replay}: trailing binary data after record {records}")
    if records == 0:
        raise TraceReplayError(f"{trace}: empty trace")
    source_sha256 = source_digest.hexdigest()
    if source_sha256 != checked["source_trace_sha256"]:
        raise TraceReplayError("source trace SHA-256 does not match authenticated binding")
    return {"records_compared": records, "source_trace_sha256": source_sha256,
            "binary_sha256": replay_digest.hexdigest()}


def build_replay(trace: Path, output: Path, bindings: dict[str, object]) -> dict[str, object]:
    """Convert one authenticated Q/R pair at a time into 20-byte replay records."""
    checked = _bindings(bindings)
    trace, output = Path(trace), Path(output)
    if not trace.is_file():
        raise TraceReplayError(f"missing trace: {trace}")
    if trace.resolve() == output.resolve():
        raise TraceReplayError("trace and replay output must be different files")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    temporary = Path(temporary_name)
    source_digest, binary_digest = hashlib.sha256(), hashlib.sha256()
    records, line_number = 0, 0
    try:
        with os.fdopen(descriptor, "wb") as binary, trace.open("rb") as source:
            while True:
                line_number += 1
                request_line = _read_line(source, source_digest, trace, line_number)
                if not request_line:
                    break
                address = _request(request_line, trace, line_number, records)
                line_number += 1
                response_line = _read_line(source, source_digest, trace, line_number)
                if not response_line:
                    raise TraceReplayError(f"{trace}:{line_number}: missing response")
                record = struct.pack("<I", address) + _response(
                    response_line, trace, line_number, records, address)
                binary.write(record)
                binary_digest.update(record)
                records += 1
            if records == 0:
                raise TraceReplayError(f"{trace}: empty trace")
            if source_digest.hexdigest() != checked["source_trace_sha256"]:
                raise TraceReplayError("source trace SHA-256 does not match authenticated binding")
            binary.flush()
            os.fsync(binary.fileno())
        verification = verify_replay(trace, temporary, checked)
        if verification["records_compared"] != records or verification["binary_sha256"] != binary_digest.hexdigest():
            raise TraceReplayError("independent replay verification disagrees with conversion")
        os.replace(temporary, output)
        _fsync_directory(output.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "schema": "tinystories-1m-compiler-trace-replay-v1",
        "record_count": records,
        "record_bytes": RECORD_BYTES,
        "binary_bytes": records * RECORD_BYTES,
        "binary_sha256": binary_digest.hexdigest(),
        "binary_artifact": str(output),
        "source_trace_sha256": checked["source_trace_sha256"],
        "candidate_sha256": checked["candidate_sha256"],
        "image_sha256": checked["image_sha256"],
        "prompt": checked["prompt"],
        "token": checked["token"],
        "byte_order": BYTE_ORDER,
        "verification": {"method": "independent source-trace-to-binary stream comparison",
                         **verification},
    }


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    payload = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--prompt", required=True, help="comma-separated uint32 token IDs")
    parser.add_argument("--token", type=int, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--source-trace-sha256", required=True,
                        help="SHA-256 from the authenticated trace receipt")
    args = parser.parse_args()
    try:
        prompt = [int(value, 10) for value in args.prompt.split(",")]
        manifest = build_replay(args.trace, args.output, {
            "source_trace_sha256": args.source_trace_sha256,
            "candidate_sha256": args.candidate_sha256,
            "image_sha256": args.image_sha256,
            "prompt": prompt,
            "token": args.token,
        })
        _write_manifest(args.manifest_output, manifest)
    except (OSError, TraceReplayError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
