"""Build a deterministic DDR3 image map for the authenticated TinyStories image.

The compiler emits one ``image-*.hex`` file per immutable tensor.  This tool
does not reinterpret tensor values: it records the source file bytes exactly,
packs each logical element at its declared hex width, and assigns 16-byte
aligned DDR3 byte ranges in canonical filename order.  The resulting manifest
is the contract shared by a future PCIe/JTAG loader and the accelerator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LINE_BYTES = 16


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tensor_record(path: Path, offset: int) -> tuple[dict[str, object], int]:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines or any(any(c not in "0123456789abcdefABCDEF" for c in x) for x in lines):
        raise ValueError(f"invalid hex image: {path}")
    digits = len(lines[0])
    if any(len(x) != digits for x in lines):
        raise ValueError(f"inconsistent element width: {path}")
    element_bytes = (digits + 1) // 2
    # Hex files contain one numeric element per line; the compiler image ABI
    # stores each element little-endian in the byte-addressed memory image.
    payload = b"".join(int(x, 16).to_bytes(element_bytes, "little") for x in lines)
    aligned = (len(payload) + LINE_BYTES - 1) // LINE_BYTES * LINE_BYTES
    record = {
        "name": path.name.removeprefix("image-").removesuffix(".hex"),
        "source": str(path),
        "source_sha256": digest(path),
        "elements": len(lines),
        "hex_digits_per_element": digits,
        "element_bytes": element_bytes,
        "payload_bytes": len(payload),
        "ddr3_offset": offset,
        "ddr3_padded_bytes": aligned,
        "ddr3_line_count": aligned // LINE_BYTES,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }
    return record, offset + aligned


def build(image_dir: Path) -> dict[str, object]:
    files = sorted(image_dir.glob("image-*.hex"), key=lambda p: p.name)
    if not files:
        raise ValueError(f"no image-*.hex files in {image_dir}")
    records: list[dict[str, object]] = []
    offset = 0
    for path in files:
        record, offset = tensor_record(path, offset)
        records.append(record)
    manifest: dict[str, object] = {
        "schema": "tinystories-1m-ddr3-model-image-v1",
        "model": "TinyStories-1M",
        "image_directory": str(image_dir),
        "line_bytes": LINE_BYTES,
        "address_order": "canonical lexical image filename",
        "tensor_count": len(records),
        "image_bytes": offset,
        "line_count": offset // LINE_BYTES,
        "tensors": records,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = build(args.image_dir)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: manifest[k] for k in ("tensor_count", "image_bytes", "line_count", "manifest_sha256")}))


if __name__ == "__main__":
    main()
