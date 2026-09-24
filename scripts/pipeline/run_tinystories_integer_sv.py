#!/usr/bin/env python3
"""Simulate the compiler-generated integer RC through its memory ABI."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time


def _load_helpers(path: Path | None = None):
    path = path or Path(__file__).with_name("run_rc_serving_w4a8_sv.py")
    spec = importlib.util.spec_from_file_location("rc_sv_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _exported_values(exported_path: Path):
    import torch

    archive = exported_path / "exported.pt2" if exported_path.is_dir() else exported_path
    exported = torch.export.load(archive)
    positional, keyword = exported.example_inputs
    if keyword:
        raise ValueError("integer RC requires positional example inputs")
    user_inputs = iter(positional)
    values = []
    for spec in exported.graph_signature.input_specs:
        if spec.kind.name == "BUFFER":
            value = exported.state_dict.get(spec.target)
            if value is None:
                raise ValueError(f"missing buffer {spec.target}")
            values.append(value)
        elif spec.kind.name == "USER_INPUT":
            values.append(next(user_inputs))
    return values


def run(args: argparse.Namespace) -> dict[str, object]:
    helpers = _load_helpers(args.helpers)
    semantic = helpers.parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    rtl = helpers.parse_sv_memory_ports(args.sv.read_text(encoding="utf-8"))
    if len(semantic) != 52:
        raise ValueError(f"integer RC expects 52 semantic memories, found {len(semantic)}")
    if len(semantic) > len(rtl):
        raise ValueError("generated SV exposes fewer memories than flat-SCF")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    values = _exported_values(args.exported)
    if len(values) != 51:
        raise ValueError(f"expected 50 buffers plus one token input, found {len(values)}")
    inputs = []
    for number, tensor in enumerate(values):
        payload, dtype, shape = helpers.tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape and not (shape == () and memory.shape == (1,)):
            raise ValueError(f"arg_mem_{number} shape {shape} != {memory.shape}")
        (args.work_dir / f"mem{number}.hex").write_text(
            "\n".join(helpers.memory_words(payload, width=memory.width)) + "\n", encoding="ascii"
        )
        inputs.append({"port": number, "dtype": dtype, "shape": list(shape),
                       "sha256": hashlib.sha256(payload).hexdigest()})
    globals_ = helpers.parse_flat_scf_global_bindings(
        args.flat_scf.read_text(encoding="utf-8"), first_port=len(semantic)
    )
    for binding in globals_:
        width = rtl[binding.port].width
        digits = width // 4
        (args.work_dir / f"mem{binding.port}.hex").write_text(
            "\n".join(f"{word:0{digits}x}" for word in binding.words) + "\n",
            encoding="ascii",
        )
    roles = helpers.PhaseRoles(inputs=tuple(range(51)), outputs=(51,), logits=51, cache_outputs=())
    fixture = helpers.render_fixture(
        rtl, roles, timeout_cycles=args.timeout_cycles,
        initialized_ports=tuple(binding.port for binding in globals_),
    )
    fixture_path = args.work_dir / "tb.sv"
    fixture_path.write_text(fixture, encoding="utf-8")
    normalized = args.work_dir / "main.normalized.sv"
    normalized.write_text(
        helpers.normalize_simulation_sv(
            args.sv.read_text(encoding="utf-8"), args.normalizer
        ),
        encoding="utf-8",
    )
    compile_log = args.work_dir / "verilator-build.log"
    compile_cmd = [args.verilator, "--binary", "--top-module", "tb", "--Mdir",
                   str(args.work_dir / "obj_dir"), "-Wno-fatal", "-Wno-WIDTHEXPAND",
                   "-Wno-WIDTHTRUNC", "-j", str(args.jobs), str(normalized), str(fixture_path)]
    started = time.monotonic()
    with compile_log.open("w", encoding="utf-8") as log:
        result = subprocess.run(compile_cmd, stdout=log, stderr=subprocess.STDOUT)
    compile_seconds = time.monotonic() - started
    if result.returncode:
        raise RuntimeError(f"Verilator compilation failed; see {compile_log}")
    simulation_log = args.work_dir / "simulation.log"
    started = time.monotonic()
    with simulation_log.open("w", encoding="utf-8") as log:
        result = subprocess.run([str(args.work_dir / "obj_dir/Vtb")], cwd=args.work_dir,
                                stdout=log, stderr=subprocess.STDOUT)
    simulation_seconds = time.monotonic() - started
    if result.returncode:
        raise RuntimeError(f"RTL simulation failed; see {simulation_log}")
    expected = json.loads(args.reference.read_text(encoding="utf-8"))["pytorch_output_i8"][0][0]
    actual = bytes.fromhex("".join((args.work_dir / "out51.hex").read_text().split()))
    expected_bytes = bytes(value & 0xFF for value in expected)
    report = {
        "schema": "tinystories-integer-rc-sv-equivalence-v1",
        "status": "pass" if actual == expected_bytes else "mismatch",
        "semantic_memory_count": len(semantic), "rtl_memory_count": len(rtl),
        "input_count": len(values), "output_port": 51,
        "expected_output_i8": expected, "actual_output_hex": actual.hex(),
        "expected_output_sha256": hashlib.sha256(expected_bytes).hexdigest(),
        "actual_output_sha256": hashlib.sha256(actual).hexdigest(),
        "compile_seconds": compile_seconds, "simulation_seconds": simulation_seconds,
        "artifacts": {"sv": str(args.sv), "flat_scf": str(args.flat_scf),
                      "exported": str(args.exported), "reference": str(args.reference)},
        "inputs": inputs, "global_bindings": [binding.symbol for binding in globals_],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--flat-scf", type=Path, required=True)
    parser.add_argument("--exported", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--helpers", type=Path)
    parser.add_argument("--normalizer", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout-cycles", type=int, default=10_000_000)
    args = parser.parse_args()
    if args.jobs <= 0 or args.timeout_cycles <= 0:
        parser.error("jobs and timeout-cycles must be positive")
    print(json.dumps(run(args), sort_keys=True))


if __name__ == "__main__":
    main()
