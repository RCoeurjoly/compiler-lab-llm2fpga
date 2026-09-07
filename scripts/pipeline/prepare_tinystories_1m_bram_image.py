#!/usr/bin/env python3
"""Materialize the production model image for synthesis-time BRAM init.

The normal Verilator harness preloads authenticated tensors from host files.
That is not a board image: synthesis ignores the dynamic DATA plusarg used by
the generated SV.  This tool emits width-correct hex files and a staticized SV
copy whose immutable source memories use those files through ``$readmemh``.
Mutable scratch memories are deliberately not initialized here; reset and the
compiler schedule own them.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def staticize_sv(source: str, source_names: set[str]) -> str:
    """Make the generated initial block synthesis-visible and source-only."""
    source = re.sub(r"^string DATA;\nint CODE;\n", "", source, count=1, flags=re.M)
    source = re.sub(r"^\s*CODE = \$value\$plusargs\([^\n]*\n", "", source, count=1, flags=re.M)
    source = re.sub(r"^\s*\$display\(\"DATA[^\n]*\n", "", source, count=1, flags=re.M)
    # Calyx emits simulation-only onehot/fatal guards.  The synthesis frontend
    # used for the board image does not implement these system tasks.
    source = re.sub(
        r"always_comb begin\n\s*if\(~\$onehot0\(\{[^}]+\}\)\) begin\n\s*\$fatal\([^;]+\);\n\s*end\nend\n",
        "",
        source,
    )

    def replace_read(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in source_names:
            return ""
        return f'    $readmemh("image-{name}.hex", {name}.mem);'

    source = re.sub(
        r"^\s*\$readmemh\(\{DATA, \"/(\w+)\.dat\"\}, \1\.mem\);$",
        replace_read,
        source,
        flags=re.M,
    )
    # The generated final block writes every memory back to host files.  It is
    # simulation-only and must not survive into synthesis.
    source = re.sub(r"\nfinal begin\n.*?\nend\n(?=logic )", "\n", source, count=1, flags=re.S)
    return source


def materialize(output: Path, *, sv: Path | None = None) -> dict[str, object]:
    production = load(ROOT / "scripts/pipeline/lower_fixed_point_model_bram_production.py", "bram_image_production")
    capture = load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "bram_image_capture")
    artifact = production.generate_production_kernel()
    bundle = capture.exact_adapter.load_successor_exact_model(
        capture.DEFAULT_CONTRACT, capture.DEFAULT_PACKAGE,
        capture.DEFAULT_MODEL, capture.DEFAULT_GENERATION,
    )
    tensors = production.base.materialize_model_sources(artifact, bundle)
    output.mkdir(parents=True, exist_ok=True)
    records: dict[str, object] = {}
    for name, tensor in tensors.items():
        width = int(artifact.provenance["source_memories"][name]["width"])
        mask = (1 << width) - 1
        digits = max(1, (width + 3) // 4)
        path = output / f"image-{name}.hex"
        values = tensor.reshape(-1).tolist()
        path.write_text("".join(f"{int(value) & mask:0{digits}x}\n" for value in values))
        records[name] = {
            "width": width,
            "elements": len(values),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    if sv is None:
        raise ValueError("sv_required")
    original = sv.read_text()
    static = staticize_sv(original, set(tensors))
    static_path = output / "model-static-init.sv"
    static_path.write_text(static)
    manifest: dict[str, object] = {
        "schema": "tinystories-1m-bram-static-image-v1",
        "futil_sha256": artifact.provenance["futil_sha256"],
        "source_memories": records,
        "generated_sv_sha256": sha256(sv),
        "static_sv_sha256": sha256(static_path),
        "static_sv": str(static_path),
        "claims": {"synthesis_image_ready": True, "bitstream_verified": False},
    }
    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output.resolve(), sv=args.sv.resolve()), indent=2))


if __name__ == "__main__":
    main()
