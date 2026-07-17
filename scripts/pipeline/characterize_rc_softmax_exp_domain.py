#!/usr/bin/env python3
"""Measure Softmax exponent-input domains of the frozen PT2E RC export.

This module observes the exported graph; it never rewrites or substitutes an
operation.  The derived value is an analysis-only ``x - max(x)`` quantity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from TinyStories.rc_working_contract import RC_WORKING_PIPELINE_ALIAS, RC_WORKING_SOURCE_MODEL_KEY

VOCAB_SIZE = 6
CONTEXT_LENGTH = 8
TOTAL_CONTEXTS = VOCAB_SIZE ** CONTEXT_LENGTH
MAX_WORDS = 256


def context_from_index(index: int) -> list[int]:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < TOTAL_CONTEXTS:
        raise ValueError(f"context index outside [0, {TOTAL_CONTEXTS}): {index!r}")
    result = [0] * CONTEXT_LENGTH
    for pos in range(CONTEXT_LENGTH - 1, -1, -1):
        result[pos] = index % VOCAB_SIZE
        index //= VOCAB_SIZE
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_receipt(exported_program_dir: Path) -> dict[str, object]:
    exported = exported_program_dir / "exported.pt2"
    manifest = exported_program_dir / "manifest.json"
    if not exported.is_file() or not manifest.is_file():
        raise ValueError("frozen exported program requires exported.pt2 and manifest.json")
    return {"source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
            "pipeline_alias": RC_WORKING_PIPELINE_ALIAS,
            "exported_program_sha256": sha256_file(exported),
            "export_manifest_sha256": sha256_file(manifest),
            "analyzer_sha256": sha256_file(Path(__file__))}


@dataclass(frozen=True)
class SoftmaxBoundary:
    node_name: str
    dim: int
    scale: float
    zero_point: int
    quant_min: int
    quant_max: int
    dtype: str


def _text(target: object) -> str:
    return str(target)


def _is_softmax(node: object) -> bool:
    return "aten.softmax.int" in _text(getattr(node, "target", ""))


def _is_dequant(node: object) -> bool:
    return "quantized_decomposed.dequantize_per_tensor.default" in _text(getattr(node, "target", ""))


def _is_quant(node: object) -> bool:
    return "quantized_decomposed.quantize_per_tensor.default" in _text(getattr(node, "target", ""))


def discover_softmax_boundaries(graph_module: object) -> dict[str, SoftmaxBoundary]:
    found: dict[str, SoftmaxBoundary] = {}
    for node in getattr(graph_module, "graph").nodes:
        if not _is_softmax(node):
            continue
        args = tuple(getattr(node, "args", ()))
        if not args or not _is_dequant(args[0]):
            raise ValueError(f"Softmax {node.name} lacks immediate quantized dequantize")
        dequant = args[0]
        qargs = tuple(getattr(dequant, "args", ()))
        if not qargs or not _is_quant(qargs[0]):
            raise ValueError(f"Softmax {node.name} lacks immediate quantize source")
        dargs = qargs
        if len(dargs) < 6:
            raise ValueError(f"Softmax {node.name} quantization parameters are incomplete")
        scale, zero, qmin, qmax, dtype = dargs[1:6]
        dim = args[1] if len(args) > 1 else -1
        if float(scale) != 2.0 ** -12 or int(zero) != -124 or (int(qmin), int(qmax)) != (-128, 127):
            raise ValueError(f"Softmax {node.name} has unexpected affine quantization")
        found[node.name] = SoftmaxBoundary(node.name, int(dim), float(scale), int(zero), int(qmin), int(qmax), str(dtype))
    if len(found) != 2:
        raise ValueError(f"expected exactly two quantized Softmax sites, found {len(found)}")
    return found


def f32_bit_words(tensor: object) -> set[int]:
    import torch
    if tensor.dtype != torch.float32:
        raise ValueError("bit accounting accepts f32 tensors only")
    return {int(x) & 0xffffffff for x in tensor.detach().contiguous().cpu().view(torch.int32).reshape(-1).tolist()}


def derived_pre_exp_operand(value: object, dim: int) -> object:
    import torch
    if value.dtype != torch.float32:
        raise ValueError(f"Softmax input must be f32, got {value.dtype}")
    return value - torch.amax(value, dim=dim, keepdim=True)


class _Accumulator:
    def __init__(self, boundary: SoftmaxBoundary) -> None:
        self.boundary = boundary
        self.input_bits: set[int] = set()
        self.derived_bits: set[int] = set()
        self.input_count = self.derived_count = self.positive = 0
        self.nan = self.inf = 0
        self.minimum = self.maximum = None

    def observe(self, value: object) -> None:
        import torch
        derived = derived_pre_exp_operand(value, self.boundary.dim)
        self.input_count += int(value.numel()); self.derived_count += int(derived.numel())
        self.input_bits |= f32_bit_words(value); self.derived_bits |= f32_bit_words(derived)
        self.positive += int((derived > 0).sum().item())
        self.nan += int(torch.isnan(derived).sum().item()); self.inf += int(torch.isinf(derived).sum().item())
        finite = derived[torch.isfinite(derived)]
        if finite.numel():
            lo, hi = float(finite.min().item()), float(finite.max().item())
            self.minimum = lo if self.minimum is None else min(self.minimum, lo)
            self.maximum = hi if self.maximum is None else max(self.maximum, hi)
        if len(self.input_bits) > MAX_WORDS or len(self.derived_bits) > MAX_WORDS:
            raise ValueError(f"{self.boundary.node_name} exceeded {MAX_WORDS} distinct f32 words")

    def result(self) -> dict[str, object]:
        return {"boundary": self.boundary.__dict__, "input_value_count": self.input_count,
                "derived_pre_exp_value_count": self.derived_count, "derived_pre_exp_positive_count": self.positive,
                "derived_pre_exp_nan_count": self.nan, "derived_pre_exp_infinity_count": self.inf,
                "derived_pre_exp_finite_min": self.minimum, "derived_pre_exp_finite_max": self.maximum,
                "input_bits": sorted(f"0x{x:08x}" for x in self.input_bits),
                "derived_pre_exp_bits": sorted(f"0x{x:08x}" for x in self.derived_bits)}


def _load(path: Path) -> Any:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401
    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    return torch.export.load(path / "exported.pt2").module()


def characterize_shard(exported_program_dir: Path, start: int, stop: int) -> dict[str, object]:
    import torch
    module = _load(exported_program_dir)
    boundaries = discover_softmax_boundaries(module)
    accumulators = {name: _Accumulator(boundary) for name, boundary in boundaries.items()}
    class Observer(torch.fx.Interpreter):
        def call_function(self, target: object, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
            node = self.fetch_args((self._current_node,)) if False else None
            return super().call_function(target, args, kwargs)
        def run_node(self, node: object) -> Any:
            self._current_node = node.name
            if node.name in accumulators and _is_softmax(node):
                # Interpreter.env contains the already evaluated immediate operand.
                value = self.env[node.args[0]]
                accumulators[node.name].observe(value)
            return super().run_node(node)
    observer = Observer(module)
    started = time.monotonic()
    with torch.inference_mode():
        for index in range(start, stop):
            observer.run(torch.tensor([context_from_index(index)], dtype=torch.long))
    return {"schema_version": 1, "kind": "softmax-exp-domain-shard", "receipt": source_receipt(exported_program_dir),
            "enumeration": {"radix": VOCAB_SIZE, "context_length": CONTEXT_LENGTH, "total_contexts": TOTAL_CONTEXTS, "start": start, "stop": stop},
            "sites": {name: acc.result() for name, acc in accumulators.items()}, "metrics": {"seconds": time.monotonic() - started}}


def merge_shards(shards: list[dict[str, object]]) -> dict[str, object]:
    if not shards: raise ValueError("no shards")
    ordered = sorted(shards, key=lambda x: x["enumeration"]["start"])
    receipt = ordered[0]["receipt"]; expected = 0; merged: dict[str, dict[str, object]] = {}
    for shard in ordered:
        enum = shard["enumeration"]
        if shard["receipt"] != receipt or enum["start"] != expected: raise ValueError("coverage or receipt mismatch")
        expected = enum["stop"]
        for name, site in shard["sites"].items():
            out = merged.setdefault(name, {"input_value_count": 0, "derived_pre_exp_value_count": 0,
                "derived_pre_exp_positive_count": 0, "derived_pre_exp_nan_count": 0,
                "derived_pre_exp_infinity_count": 0, "input_bits": [],
                "derived_pre_exp_bits": [], "boundary": site["boundary"]})
            for key in ("input_value_count", "derived_pre_exp_value_count", "derived_pre_exp_positive_count", "derived_pre_exp_nan_count", "derived_pre_exp_infinity_count"):
                out[key] = out.get(key, 0) + site[key]
            out["input_bits"] = sorted(set(out.get("input_bits", [])) | set(site["input_bits"]))
            out["derived_pre_exp_bits"] = sorted(set(out.get("derived_pre_exp_bits", [])) | set(site["derived_pre_exp_bits"]))
            out["boundary"] = site["boundary"]
    if expected != TOTAL_CONTEXTS: raise ValueError("coverage is incomplete")
    return {"schema_version": 1, "kind": "softmax-exp-domain-summary", "receipt": receipt,
            "coverage": {"start": 0, "stop": TOTAL_CONTEXTS, "complete": True}, "sites": merged}


def main() -> None:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "characterize"):
        p = sub.add_parser(name); p.add_argument("--exported-program-dir", type=Path, required=True)
        if name == "characterize": p.add_argument("--start", type=int, required=True); p.add_argument("--stop", type=int, required=True); p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("merge"); p.add_argument("--shard", action="append", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        import torch
        print(json.dumps({"receipt": source_receipt(args.exported_program_dir), "sites": {k: v.__dict__ for k, v in discover_softmax_boundaries(_load(args.exported_program_dir)).items()}}, indent=2, sort_keys=True)); return
    if args.command == "characterize":
        if not 0 <= args.start < args.stop <= TOTAL_CONTEXTS: raise SystemExit("invalid shard")
        result = characterize_shard(args.exported_program_dir, args.start, args.stop)
    else:
        result = merge_shards([json.loads(p.read_text()) for p in args.shard])
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__": main()
