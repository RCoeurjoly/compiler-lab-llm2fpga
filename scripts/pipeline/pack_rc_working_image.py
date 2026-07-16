#!/usr/bin/env python3
"""Pack all tensor state of the fixed quantized RC into one immutable image."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ALIGNMENT_BYTES = 64
BYTE_ORDER = "little"
_DTYPE_WIDTHS = {
    "bool": 1,
    "int8": 1,
    "uint8": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
    "int64": 8,
    "uint64": 8,
    "float16": 2,
    "float32": 4,
    "float64": 8,
    "bfloat16": 2,
}


def _align(offset: int, alignment: int = ALIGNMENT_BYTES) -> int:
    return ((offset + alignment - 1) // alignment) * alignment


def _canonical_dtype(dtype: object) -> str:
    value = str(dtype)
    if value.startswith("torch."):
        value = value.removeprefix("torch.")
    if value not in _DTYPE_WIDTHS:
        raise ValueError(f"unsupported tensor dtype for RC image: {dtype}")
    return value


def _tensor_bytes(tensor: Any) -> tuple[str, list[int], bytes]:
    try:
        cpu_tensor = tensor.detach().cpu().contiguous()
        dtype = _canonical_dtype(cpu_tensor.dtype)
        shape = [int(dimension) for dimension in cpu_tensor.shape]
        payload = cpu_tensor.numpy().tobytes(order="C")
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("RC image accepts only contiguous CPU tensor values") from error

    element_count = 1
    for dimension in shape:
        if dimension < 0:
            raise ValueError("tensor shape cannot contain a negative dimension")
        element_count *= dimension
    expected_length = element_count * _DTYPE_WIDTHS[dtype]
    if len(payload) != expected_length:
        raise ValueError(
            f"tensor byte length {len(payload)} does not match {dtype}{tuple(shape)}"
        )
    return dtype, shape, payload


def _split_name(qualified_name: str) -> tuple[str, str]:
    if not isinstance(qualified_name, str):
        raise ValueError("tensor image name must be a string")
    category, separator, source_name = qualified_name.partition("/")
    if separator != "/" or category not in {"constants", "state"} or not source_name:
        raise ValueError(
            "tensor image name must have the form 'state/name' or 'constants/name'"
        )
    return category, source_name


def pack_named_tensors(
    named_tensors: Mapping[str, Any], *, exported_program_sha256: str | None = None
) -> tuple[dict[str, object], bytes]:
    """Return a deterministic 64-byte-aligned image and its manifest."""

    if sys.byteorder != BYTE_ORDER:
        raise ValueError("RC image packing currently requires a little-endian host")

    entries: list[tuple[str, str, str, Any]] = []
    for qualified_name, tensor in named_tensors.items():
        category, source_name = _split_name(qualified_name)
        entries.append((category, source_name, qualified_name, tensor))
    entries.sort(key=lambda entry: (entry[0], entry[1]))

    image = bytearray()
    segments: list[dict[str, object]] = []
    for category, source_name, qualified_name, tensor in entries:
        offset = _align(len(image))
        image.extend(b"\x00" * (offset - len(image)))
        dtype, shape, payload = _tensor_bytes(tensor)
        image.extend(payload)
        segments.append(
            {
                "name": qualified_name,
                "source_category": category,
                "source_name": source_name,
                "dtype": dtype,
                "shape": shape,
                "offset": offset,
                "byte_length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "quantization": None,
            }
        )

    payload = bytes(image)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "byte_order": BYTE_ORDER,
        "alignment_bytes": ALIGNMENT_BYTES,
        "segments": segments,
        "image_sha256": hashlib.sha256(payload).hexdigest(),
    }
    if exported_program_sha256 is not None:
        manifest["exported_program_sha256"] = exported_program_sha256
    return manifest, payload


def verify_image_bytes(manifest: Mapping[str, object], image_bytes: bytes) -> None:
    """Reject image bytes that do not exactly match the checked-in manifest."""

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported RC image manifest schema")
    if manifest.get("byte_order") != BYTE_ORDER:
        raise ValueError("RC image manifest must use little-endian encoding")
    if manifest.get("alignment_bytes") != ALIGNMENT_BYTES:
        raise ValueError("RC image manifest must use 64-byte alignment")
    expected_image_sha256 = manifest.get("image_sha256")
    observed_image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    if expected_image_sha256 != observed_image_sha256:
        raise ValueError("RC image SHA-256 does not match its manifest")

    segments = manifest.get("segments")
    if not isinstance(segments, list):
        raise ValueError("RC image manifest segments must be a list")
    seen_names: set[str] = set()
    previous_offset = -1
    for segment in segments:
        if not isinstance(segment, Mapping):
            raise ValueError("RC image manifest segment must be an object")
        name = segment.get("name")
        if not isinstance(name, str) or name in seen_names:
            raise ValueError("RC image segment names must be unique strings")
        _split_name(name)
        seen_names.add(name)
        offset = segment.get("offset")
        byte_length = segment.get("byte_length")
        if (
            not isinstance(offset, int)
            or not isinstance(byte_length, int)
            or offset < 0
            or byte_length < 0
            or offset % ALIGNMENT_BYTES != 0
            or offset < previous_offset
        ):
            raise ValueError("RC image segment offsets must be aligned and ordered")
        end = offset + byte_length
        if end > len(image_bytes):
            raise ValueError(f"RC image segment {name} exceeds image bounds")
        if segment.get("sha256") != hashlib.sha256(image_bytes[offset:end]).hexdigest():
            raise ValueError(f"RC image segment {name} SHA-256 does not match")
        previous_offset = offset


def exported_named_tensors(exported: Any) -> dict[str, Any]:
    """Return every tensor the exported program supplies as state or constants."""

    named: dict[str, Any] = {}
    for category, values in (
        ("state", getattr(exported, "state_dict", None)),
        ("constants", getattr(exported, "constants", None)),
    ):
        if not isinstance(values, Mapping):
            raise ValueError(f"exported program has no mapping of {category}")
        for source_name, tensor in values.items():
            if not isinstance(source_name, str) or not source_name:
                raise ValueError(f"exported {category} name must be a non-empty string")
            qualified_name = f"{category}/{source_name}"
            if qualified_name in named:
                raise ValueError(f"duplicate exported tensor name: {qualified_name}")
            _tensor_bytes(tensor)
            named[qualified_name] = tensor
    return named


def _load_exported_program(exported_program_dir: Path) -> Any:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401

    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    return torch.export.load(exported_program_dir / "exported.pt2")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exported-program-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    exported_path = args.exported_program_dir / "exported.pt2"
    exported = _load_exported_program(args.exported_program_dir)
    manifest, image_bytes = pack_named_tensors(
        exported_named_tensors(exported),
        exported_program_sha256=hashlib.sha256(exported_path.read_bytes()).hexdigest(),
    )
    verify_image_bytes(manifest, image_bytes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "rc-image.bin").write_bytes(image_bytes)
    _write_json(args.out_dir / "rc-image-manifest.json", manifest)


if __name__ == "__main__":
    main()
