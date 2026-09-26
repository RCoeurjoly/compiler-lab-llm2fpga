#!/usr/bin/env python3
"""Verify the authenticated three-phase RC token/cache composition contract.

This is intentionally a compiler-side gate.  It does not compose or execute
RTL; it proves that independently lowered phase artifacts can be connected
without changing the frozen serving ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PHASES = ("prefill-8", "decode-8", "decode-9")
SCHEMA = "rc-serving-w4a8-compiler-phase-abi-v1"
ELEMENT_WIDTHS = {"i1": 1, "i8": 8, "i32": 32, "i64": 64, "f32": 32}


def _shape(text: str) -> tuple[int, ...]:
    fields = text.split("x")
    element = fields.pop()
    if element not in ELEMENT_WIDTHS:
        raise ValueError(f"unsupported element type {element}")
    return tuple(int(field) for field in fields) or (1,)


def phase_shapes(flat_scf: Path) -> tuple[tuple[int, ...], ...]:
    source = flat_scf.read_text(encoding="utf-8")
    match = re.search(r"\bfunc\.func\s+@main\s*\((.*?)\)\s*\{", source, re.DOTALL)
    if match is None:
        raise ValueError(f"{flat_scf}: missing func.func @main")
    args = re.findall(r"%arg(\d+)\s*:\s*memref<([^>]+)>", match.group(1))
    if [int(number) for number, _ in args] != list(range(len(args))):
        raise ValueError(f"{flat_scf}: semantic memory arguments are not dense")
    return tuple(_shape(body) for _, body in args)


def verify(abi_path: Path, flat_scf_paths: dict[str, Path], sv_paths: dict[str, Path] | None = None) -> dict[str, object]:
    abi_bytes = abi_path.read_bytes()
    abi = json.loads(abi_bytes)
    if abi.get("schema") != SCHEMA:
        raise ValueError("unsupported phase ABI schema")
    phases = abi.get("phases")
    if not isinstance(phases, list) or tuple(p.get("name") for p in phases) != PHASES:
        raise ValueError("phase ABI order is not canonical")
    reports = []
    expected_cache_shapes = {
        phase["name"]: tuple(tuple(leaf["shape"]) for leaf in phase["cache_leaves"])
        for phase in phases
    }
    for phase in phases:
        name = phase["name"]
        shapes = phase_shapes(flat_scf_paths[name])
        if len(shapes) != 37:
            raise ValueError(f"{name}: expected 32 inputs and 5 outputs, got {len(shapes)}")
        output_shapes = shapes[32:]
        # The frozen readback ABI stores only the selected-token logits, while
        # the phase graph retains the sequence dimension internally.
        logits_shape = (1, 8, 6) if name == "prefill-8" else (1, 1, 6)
        expected = (logits_shape, *expected_cache_shapes[name])
        if output_shapes != expected:
            raise ValueError(f"{name}: output shapes disagree with phase ABI")
        if shapes[0] != ((8,) if name == "prefill-8" else (1,)):
            raise ValueError(f"{name}: token input shape is not canonical")
        if name != "prefill-8":
            input_cache = shapes[28:32]
            previous = "prefill-8" if name == "decode-8" else "decode-8"
            if input_cache != expected_cache_shapes[previous]:
                raise ValueError(f"{name}: cache input does not match {previous} output")
        report = {
            "name": name,
            "flat_scf": str(flat_scf_paths[name]),
            "flat_scf_sha256": hashlib.sha256(flat_scf_paths[name].read_bytes()).hexdigest(),
            "semantic_memories": len(shapes),
            "input_count": 32,
            "output_count": 5,
            "token_input_shape": list(shapes[0]),
            "cache_input_shapes": [list(shape) for shape in shapes[28:32]],
            "cache_output_shapes": [list(shape) for shape in output_shapes[1:]],
        }
        if sv_paths is not None:
            sv = sv_paths[name].read_text(encoding="utf-8")
            if not re.search(r"\bmodule\s+main_1\s*\(", sv):
                raise ValueError(f"{name}: generated SV has no main_1 component")
            report["sv"] = str(sv_paths[name])
            report["sv_sha256"] = hashlib.sha256(sv_paths[name].read_bytes()).hexdigest()
        reports.append(report)
    return {
        "schema": "llm2fpga.rc-serving-phase-abi-verification-v1",
        "status": "pass",
        "abi": str(abi_path),
        "abi_sha256": hashlib.sha256(abi_bytes).hexdigest(),
        "phase_order": list(PHASES),
        "cache_chain": ["prefill-8 -> decode-8", "decode-8 -> decode-9"],
        "phases": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--abi", required=True, type=Path)
    parser.add_argument("--prefill-flat-scf", required=True, type=Path)
    parser.add_argument("--decode8-flat-scf", required=True, type=Path)
    parser.add_argument("--decode9-flat-scf", required=True, type=Path)
    parser.add_argument("--prefill-sv", type=Path)
    parser.add_argument("--decode8-sv", type=Path)
    parser.add_argument("--decode9-sv", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    flat = {"prefill-8": args.prefill_flat_scf, "decode-8": args.decode8_flat_scf, "decode-9": args.decode9_flat_scf}
    sv_values = (args.prefill_sv, args.decode8_sv, args.decode9_sv)
    sv = None if all(value is None for value in sv_values) else dict(zip(PHASES, sv_values))
    if sv is not None and any(value is None for value in sv_values):
        raise SystemExit("provide all three SV paths or none")
    report = verify(args.abi, flat, sv)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
