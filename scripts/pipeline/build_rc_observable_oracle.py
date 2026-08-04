#!/usr/bin/env python3
"""Generate and validate durable PT2E observable-oracle shards for the RC."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.rc_working_contract import argmax_lowest, validate_output_tensor  # noqa: E402


VOCAB_SIZE = 6
CONTEXT_LENGTH = 8
TOTAL_CONTEXTS = VOCAB_SIZE ** CONTEXT_LENGTH
_HEX_DIGITS = frozenset("0123456789abcdef")
SCHEMA_VERSION = 1
RECORD_FORMAT = {
    "word_hex_characters": 16,
    "line_bytes": 17,
    "code_lanes": VOCAB_SIZE,
    "code_bits": 8,
    "token_bits": [48, 55],
    "reserved_bits": [56, 63],
}
ENUMERATION_KIND = "base-six-lexical-rightmost-fastest"


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def context_from_index(index: int) -> list[int]:
    """Decode a lexical base-six ordinal with the rightmost token fastest."""

    if not _is_plain_int(index) or not 0 <= index < TOTAL_CONTEXTS:
        raise ValueError(f"context index must be in [0, {TOTAL_CONTEXTS})")
    tokens = [0] * CONTEXT_LENGTH
    for position in range(CONTEXT_LENGTH - 1, -1, -1):
        tokens[position] = index % VOCAB_SIZE
        index //= VOCAB_SIZE
    return tokens


def index_from_context(tokens: Sequence[int]) -> int:
    """Encode an eight-token lexical base-six context."""

    if isinstance(tokens, (str, bytes)) or len(tokens) != CONTEXT_LENGTH:
        raise ValueError(f"context requires exactly {CONTEXT_LENGTH} token IDs")
    value = 0
    for token in tokens:
        if not _is_plain_int(token) or not 0 <= token < VOCAB_SIZE:
            raise ValueError(f"context token IDs must be in [0, {VOCAB_SIZE})")
        value = value * VOCAB_SIZE + token
    return value


def pack_record(codes: Sequence[int], token_id: int) -> str:
    """Pack six signed int8 codes and an argmax token into one 64-bit word."""

    if (
        isinstance(codes, (str, bytes))
        or len(codes) != VOCAB_SIZE
        or any(not _is_plain_int(value) or not -128 <= value <= 127 for value in codes)
    ):
        raise ValueError("record requires six signed int8 codes")
    if not _is_plain_int(token_id) or not 0 <= token_id < VOCAB_SIZE:
        raise ValueError("record token ID outside vocabulary")
    if token_id != argmax_lowest(codes):
        raise ValueError("record token ID must equal the lowest-index argmax")
    value = sum((code & 0xFF) << (8 * lane) for lane, code in enumerate(codes))
    value |= token_id << 48
    return f"{value:016x}"


def unpack_record(word: str) -> tuple[list[int], int]:
    """Validate and decode one fixed-width observable-oracle word."""

    if (
        not isinstance(word, str)
        or len(word) != 16
        or any(character not in _HEX_DIGITS for character in word)
    ):
        raise ValueError("record must be 16 lowercase hexadecimal characters")
    value = int(word, 16)
    if value >> 56:
        raise ValueError("record reserved bits must be zero")
    token_id = (value >> 48) & 0xFF
    if token_id >= VOCAB_SIZE:
        raise ValueError("record token ID outside vocabulary")
    codes = []
    for lane in range(VOCAB_SIZE):
        code = (value >> (8 * lane)) & 0xFF
        codes.append(code - 0x100 if code >= 0x80 else code)
    if token_id != argmax_lowest(codes):
        raise ValueError("record token ID must equal the lowest-index argmax")
    return codes, token_id


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_range(start: int, stop: int) -> None:
    if (
        not _is_plain_int(start)
        or not _is_plain_int(stop)
        or not 0 <= start < stop <= TOTAL_CONTEXTS
    ):
        raise ValueError(f"shard range must be non-empty within [0, {TOTAL_CONTEXTS}]")


def _evaluated_record(
    evaluator: Callable[[list[int]], Any], tokens: list[int]
) -> tuple[list[int], int]:
    result = evaluator(tokens)
    if not isinstance(result, tuple) or len(result) != 2:
        raise ValueError("oracle evaluator must return (six int8 codes, token ID)")
    codes, token_id = result
    # pack_record is the common validator for injected and PT2E evaluators.
    pack_record(codes, token_id)
    return list(codes), token_id


def _preflight_reference(
    evaluator: Callable[[list[int]], Any], reference: Mapping[str, object] | None
) -> None:
    if reference is None:
        return
    rows = reference.get("results")
    if not isinstance(rows, list):
        raise ValueError("reference must contain a results list")
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("reference result must be an object")
        token_ids = row.get("token_ids")
        expected_codes = row.get("output_codes_i8")
        expected_token = row.get("token_id")
        try:
            tokens = list(token_ids)  # type: ignore[arg-type]
            index_from_context(tokens)
            expected_word = pack_record(expected_codes, expected_token)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise ValueError("reference result has invalid observable fields") from error
        observed_codes, observed_token = _evaluated_record(evaluator, tokens)
        if pack_record(observed_codes, observed_token) != expected_word:
            raise ValueError("reference preflight observable mismatch")


def _payload_name(start: int, stop: int) -> str:
    return f"shard-{start}-{stop}.hex"


def verify_payload(payload_path: Path, payload: Mapping[str, object]) -> None:
    """Reopen a payload and reject malformed lines or inconsistent metadata."""

    records = payload.get("records")
    byte_count = payload.get("bytes")
    digest = payload.get("sha256")
    if (
        not _is_plain_int(records)
        or records < 0
        or not _is_plain_int(byte_count)
        or byte_count != records * RECORD_FORMAT["line_bytes"]
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in _HEX_DIGITS for character in digest)
    ):
        raise ValueError("payload metadata is invalid")
    observed_digest = hashlib.sha256()
    observed_records = 0
    observed_bytes = 0
    with payload_path.open("rb") as source:
        while line := source.read(RECORD_FORMAT["line_bytes"]):
            if len(line) != RECORD_FORMAT["line_bytes"] or line[-1:] != b"\n":
                raise ValueError("payload line must contain one word and newline")
            try:
                word = line[:-1].decode("ascii")
            except UnicodeDecodeError as error:
                raise ValueError("payload word must be ASCII hexadecimal") from error
            unpack_record(word)
            observed_digest.update(line)
            observed_records += 1
            observed_bytes += len(line)
    if observed_records != records or observed_bytes != byte_count:
        raise ValueError("payload record count or size does not match metadata")
    if observed_digest.hexdigest() != digest:
        raise ValueError("payload SHA-256 does not match metadata")


def generate_shard(
    *,
    evaluator: Callable[[list[int]], Any],
    start: int,
    stop: int,
    output_dir: Path,
    receipt: Mapping[str, object],
    reference: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Stream one verified lexical shard from a batch-one observable evaluator."""

    _validate_range(start, stop)
    if not isinstance(receipt, Mapping):
        raise ValueError("oracle receipt must be an object")
    _preflight_reference(evaluator, reference)
    payload_name = _payload_name(start, stop)
    metadata_name = f"shard-{start}-{stop}.json"
    payload_path = output_dir / payload_name
    metadata_path = output_dir / metadata_name
    output_dir.mkdir(parents=True, exist_ok=True)
    if payload_path.exists() or metadata_path.exists():
        raise FileExistsError("refusing to overwrite an existing oracle shard")

    started = time.monotonic()
    digest = hashlib.sha256()
    records = 0
    with payload_path.open("xb") as destination:
        for index in range(start, stop):
            codes, token_id = _evaluated_record(evaluator, context_from_index(index))
            line = (pack_record(codes, token_id) + "\n").encode("ascii")
            destination.write(line)
            digest.update(line)
            records += 1
    payload = {
        "file": payload_name,
        "sha256": digest.hexdigest(),
        "records": records,
        "bytes": records * RECORD_FORMAT["line_bytes"],
    }
    verify_payload(payload_path, payload)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "receipt": dict(receipt),
        "enumeration": {
            "kind": ENUMERATION_KIND,
            "start": start,
            "stop": stop,
            "total_contexts": TOTAL_CONTEXTS,
        },
        "record_format": RECORD_FORMAT,
        "payload": payload,
        "elapsed_seconds": time.monotonic() - started,
    }
    metadata_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def verify_shard(metadata_path: Path) -> dict[str, object]:
    """Validate a completed metadata receipt and its adjacent payload."""

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("oracle metadata must be an object")
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported oracle metadata schema")
    if metadata.get("status") != "complete":
        raise ValueError("oracle metadata is incomplete")
    if metadata.get("record_format") != RECORD_FORMAT:
        raise ValueError("oracle record format does not match")
    enumeration = metadata.get("enumeration")
    payload = metadata.get("payload")
    if not isinstance(enumeration, Mapping) or not isinstance(payload, Mapping):
        raise ValueError("oracle metadata lacks enumeration or payload")
    start, stop = enumeration.get("start"), enumeration.get("stop")
    _validate_range(start, stop)  # type: ignore[arg-type]
    if (
        enumeration.get("kind") != ENUMERATION_KIND
        or enumeration.get("total_contexts") != TOTAL_CONTEXTS
        or payload.get("file") != _payload_name(start, stop)
        or payload.get("records") != stop - start
    ):
        raise ValueError("oracle metadata enumeration does not match payload")
    verify_payload(metadata_path.parent / str(payload["file"]), payload)
    return metadata


def _validate_merge_receipt(metadata: Mapping[str, object]) -> tuple[int, int]:
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("oracle merge received a changed schema")
    if metadata.get("status") != "complete":
        raise ValueError("oracle merge received an incomplete shard")
    if metadata.get("record_format") != RECORD_FORMAT:
        raise ValueError("oracle merge received a changed record format")
    enumeration = metadata.get("enumeration")
    payload = metadata.get("payload")
    if not isinstance(enumeration, Mapping) or not isinstance(payload, Mapping):
        raise ValueError("oracle merge received malformed metadata")
    start, stop = enumeration.get("start"), enumeration.get("stop")
    _validate_range(start, stop)  # type: ignore[arg-type]
    if (
        enumeration.get("kind") != ENUMERATION_KIND
        or enumeration.get("total_contexts") != TOTAL_CONTEXTS
        or payload.get("records") != stop - start
        or payload.get("bytes") != (stop - start) * RECORD_FORMAT["line_bytes"]
    ):
        raise ValueError("oracle merge received a payload count mismatch")
    digest = payload.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in _HEX_DIGITS for character in digest)
    ):
        raise ValueError("oracle merge received an invalid payload hash")
    return start, stop


def merge_oracle_receipts(receipts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Prove that complete, matching shard receipts cover the full RC domain."""

    if not receipts:
        raise ValueError("oracle merge needs at least one shard receipt")
    normalized = [dict(receipt) for receipt in receipts]
    first_receipt = normalized[0].get("receipt")
    if not isinstance(first_receipt, Mapping):
        raise ValueError("oracle merge received a missing receipt")
    ranges: list[tuple[int, int, dict[str, object]]] = []
    for metadata in normalized:
        if metadata.get("receipt") != first_receipt:
            raise ValueError("oracle merge received a changed receipt")
        start, stop = _validate_merge_receipt(metadata)
        ranges.append((start, stop, metadata))
    ranges.sort(key=lambda item: item[0])
    next_start = 0
    components: list[dict[str, object]] = []
    for start, stop, metadata in ranges:
        if start < next_start:
            raise ValueError("oracle merge found a duplicate or overlapping shard")
        if start > next_start:
            raise ValueError("oracle merge found a gap")
        payload = metadata["payload"]
        assert isinstance(payload, Mapping)
        components.append(
            {
                "start": start,
                "stop": stop,
                "payload_sha256": payload["sha256"],
                "payload_records": payload["records"],
            }
        )
        next_start = stop
    if next_start != TOTAL_CONTEXTS:
        raise ValueError("oracle merge found a gap before full coverage")
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt": dict(first_receipt),
        "record_format": RECORD_FORMAT,
        "coverage": {"start": 0, "stop": TOTAL_CONTEXTS, "complete": True},
        "shards": components,
    }


def merge_oracle_files(metadata_paths: Sequence[Path], output_path: Path) -> dict[str, object]:
    """Load verified shard metadata, merge it, and write a coverage receipt."""

    metadata = [verify_shard(path) for path in metadata_paths]
    merged = merge_oracle_receipts(metadata)
    output_path.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return merged


def _output_tensor(output: Any) -> Any:
    import torch

    if isinstance(output, torch.Tensor):
        return output
    logits = getattr(output, "logits", None)
    if isinstance(logits, torch.Tensor):
        return logits
    raise ValueError("working RC module did not return a tensor or .logits tensor")


def _pt2e_evaluator(exported_program_dir: Path) -> tuple[Callable[[list[int]], Any], dict[str, object]]:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401

    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    exported = torch.export.load(exported_program_dir / "exported.pt2")
    module = exported.module()

    def evaluate(tokens: list[int]) -> tuple[list[int], int]:
        index_from_context(tokens)
        with torch.inference_mode():
            output = _output_tensor(module(torch.tensor([tokens], dtype=torch.long)))
        if output.dtype != torch.int8:
            raise ValueError(f"working RC output must be torch.int8, got {output.dtype}")
        validate_output_tensor(output)
        codes = [int(value) for value in output[0, 7, :].detach().cpu().tolist()]
        return codes, argmax_lowest(codes)

    return evaluate, {
        "pytorch_version": torch.__version__,
        "pytorch_num_threads": torch.get_num_threads(),
    }


def _generation_receipt(args: argparse.Namespace, torch_receipt: Mapping[str, object]) -> dict[str, object]:
    artifacts = {
        "exported_program_sha256": _sha256_file(args.exported_program_dir / "exported.pt2"),
        "export_manifest_sha256": _sha256_file(args.exported_program_dir / "manifest.json"),
        "reference_sha256": _sha256_file(args.reference),
        "image_sha256": _sha256_file(args.image),
        "image_manifest_sha256": _sha256_file(args.image_manifest),
        "generator_sha256": _sha256_file(Path(__file__)),
        "contract_sha256": _sha256_file(REPO_ROOT / "TinyStories" / "rc_working_contract.py"),
    }
    return {
        "artifacts": artifacts,
        "python_version": platform.python_version(),
        **dict(torch_receipt),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    generate = subcommands.add_parser("generate", help="generate one verified oracle shard")
    generate.add_argument("--exported-program-dir", required=True, type=Path)
    generate.add_argument("--reference", required=True, type=Path)
    generate.add_argument("--image", required=True, type=Path)
    generate.add_argument("--image-manifest", required=True, type=Path)
    generate.add_argument("--output-dir", required=True, type=Path)
    generate.add_argument("--start", required=True, type=int)
    generate.add_argument("--stop", required=True, type=int)
    verify = subcommands.add_parser("verify", help="verify one existing oracle shard")
    verify.add_argument("--metadata", required=True, type=Path)
    merge = subcommands.add_parser("merge-oracle", help="merge complete oracle shard receipts")
    merge.add_argument("--metadata", required=True, nargs="+", type=Path)
    merge.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "generate":
        evaluator, torch_receipt = _pt2e_evaluator(args.exported_program_dir)
        reference = json.loads(args.reference.read_text(encoding="utf-8"))
        if not isinstance(reference, dict):
            raise ValueError("reference must be an object")
        result = generate_shard(
            evaluator=evaluator,
            start=args.start,
            stop=args.stop,
            output_dir=args.output_dir,
            receipt=_generation_receipt(args, torch_receipt),
            reference=reference,
        )
    elif args.command == "verify":
        result = verify_shard(args.metadata)
    else:
        result = merge_oracle_files(args.metadata, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
