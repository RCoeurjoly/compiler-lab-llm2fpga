#!/usr/bin/env python3
"""Authenticate the pre-consolidation compiler candidate and full input image."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    baseline = json.loads((root / "artifacts/diagnostics/2026-09-18-owner-mux-simulation/result.json").read_text())
    manifest = json.loads((root / "artifacts/diagnostics/tinystories-1m-ddr3-model-image-manifest.json").read_text())
    if not args.image.is_file():
        raise SystemExit("image authentication failed: missing file")
    image = args.image.read_bytes()
    image_hash = hashlib.sha256(image).hexdigest()
    if (len(image) != manifest["image_bytes"] or
            image_hash != manifest["image_sha256"] or
            image_hash != baseline["model_image_sha256"]):
        raise SystemExit("image authentication failed: size/hash mismatch")
    if not args.model.is_file() or hashlib.sha256(args.model.read_bytes()).hexdigest() != baseline["candidate_sha256"]:
        raise SystemExit("compiler authentication failed: not the frozen pre-consolidation candidate")
    print("PASS: authenticated compiler and complete image")


if __name__ == "__main__":
    main()
