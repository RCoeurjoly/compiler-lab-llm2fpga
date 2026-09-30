#!/usr/bin/env python3
"""Build the accepted full16 BRAM image from pinned model weights and SV."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


NORMALIZED_SHA256 = "1dace267751f67943ee9884887ef20b350c43f214abcd4c7d83771837fff4e8c"
IMAGE_RECORDS_SHA256 = "092f8dfa927b7d30c189f62ef1dc5109103949262be52524db07f326b9f67d12"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    repo, postpass, package, snapshot, out = map(Path, sys.argv[1:])
    sys.path.insert(0, str(repo))
    from scripts.pipeline import run_bram_production_sv as runner
    from scripts.pipeline.prepare_tinystories_1m_bram_image import staticize_sv
    from scripts.pipeline.fix_sv_synthesis_frontend import normalize
    from TinyStories import capture_fixed_point_model_token_step_oracle as capture

    artifact = runner.production.generate_production_kernel(generation_steps=16)
    bundle = capture.exact_adapter.load_successor_exact_model(
        capture.DEFAULT_CONTRACT, package, snapshot, capture.DEFAULT_GENERATION)
    tensors = runner.base.materialize_model_sources(artifact, bundle)
    assert len(tensors) == 89, "unexpected immutable source-memory count"
    out.mkdir()
    records = {}
    for name, tensor in tensors.items():
        width = int(artifact.provenance["source_memories"][name]["width"])
        digits = (width + 3) // 4
        mask = (1 << width) - 1
        path = out / f"image-{name}.hex"
        path.write_text("".join(f"{int(value) & mask:0{digits}x}\n" for value in tensor.reshape(-1).tolist()))
        records[name] = {"width": width, "elements": tensor.numel(),
                         "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())}
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    assert sha256(canonical) == IMAGE_RECORDS_SHA256, "model image differs from accepted 89-memory image"
    generated = (postpass / "model.sv").read_text()
    normalized, frontend = normalize(staticize_sv(generated, set(tensors)))
    assert sha256(normalized.encode()) == NORMALIZED_SHA256, "staticized SV differs from accepted image"
    (out / "model-static-init-normalized.sv").write_text(normalized)
    receipt = {
        "status": "source-rebuilt-accepted-two-rom-static-image",
        "generation_steps": 16,
        "source_memories": records,
        "image_records_sha256": IMAGE_RECORDS_SHA256,
        "generated_sv_sha256": sha256(generated.encode()),
        "normalized_sv_sha256": sha256(normalized.encode()),
        "frontend_normalization": frontend,
        "limits": ["Image and staticized SV only; synthesis, route, bitstream and board not rebuilt."],
    }
    (out / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
