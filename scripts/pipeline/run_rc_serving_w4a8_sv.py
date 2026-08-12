#!/usr/bin/env python3
"""Simulate one generated W4A8 serving phase against its frozen oracle."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import math
import re
import struct
import subprocess
import time
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class SemanticMemory:
    number: int
    shape: tuple[int, ...]
    width: int


@dataclasses.dataclass(frozen=True)
class SvMemoryPort:
    number: int
    width: int
    depth: int


@dataclasses.dataclass(frozen=True)
class PhaseRoles:
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    logits: int
    cache_outputs: tuple[int, ...]


_ELEMENT_WIDTHS = {"i1": 1, "i8": 8, "i64": 64, "f32": 32}


def parse_flat_scf_abi(source: str) -> tuple[SemanticMemory, ...]:
    match = re.search(r"\bfunc\.func\s+@main\s*\((.*?)\)\s*\{", source, re.DOTALL)
    if match is None:
        raise ValueError("flat SCF does not define func.func @main")
    items: list[SemanticMemory] = []
    pattern = re.compile(r"%arg(?P<number>\d+)\s*:\s*memref<(?P<body>[^>]+)>")
    for argument in pattern.finditer(match.group(1)):
        fields = argument.group("body").split("x")
        element = fields[-1]
        if element not in _ELEMENT_WIDTHS:
            raise ValueError(f"unsupported semantic memory element type: {element}")
        shape = tuple(int(value) for value in fields[:-1]) or (1,)
        items.append(
            SemanticMemory(
                number=int(argument.group("number")),
                shape=shape,
                width=_ELEMENT_WIDTHS[element],
            )
        )
    if not items or [item.number for item in items] != list(range(len(items))):
        raise ValueError("semantic memories are not a complete zero-based sequence")
    return tuple(items)


def phase_roles(phase: str, *, semantic_port_count: int) -> PhaseRoles:
    input_counts = {"prefill-8": 28, "decode-8": 32, "decode-9": 32}
    try:
        input_count = input_counts[phase]
    except KeyError as error:
        raise ValueError(f"unsupported W4A8 serving phase: {phase}") from error
    if semantic_port_count != input_count + 5:
        raise ValueError(
            f"{phase} requires {input_count + 5} semantic memories, got "
            f"{semantic_port_count}"
        )
    outputs = tuple(range(input_count, semantic_port_count))
    return PhaseRoles(
        inputs=tuple(range(input_count)),
        outputs=outputs,
        logits=outputs[0],
        cache_outputs=outputs[1:],
    )


def memory_words(payload: bytes, *, width: int) -> list[str]:
    if width == 1:
        if any(value not in (0, 1) for value in payload):
            raise ValueError("i1 memory payload must contain only zero or one bytes")
        return [str(value) for value in payload]
    if width % 8:
        raise ValueError(f"unsupported non-byte memory width: {width}")
    byte_width = width // 8
    if len(payload) % byte_width:
        raise ValueError(
            f"memory payload byte count must be a multiple of {byte_width} for "
            f"width {width}"
        )
    digits = byte_width * 2
    return [
        f"{int.from_bytes(payload[offset:offset + byte_width], 'little'):0{digits}x}"
        for offset in range(0, len(payload), byte_width)
    ]


def parse_sv_memory_ports(source: str) -> tuple[SvMemoryPort, ...]:
    module = re.search(r"\bmodule\s+main_1\s*\((.*?)\)\s*;", source, re.DOTALL)
    if module is None:
        raise ValueError("SV does not define module main_1")
    declaration = re.compile(
        r"\b(?P<direction>input|output)\s+(?:wire\s+)?logic"
        r"(?:\s+signed)?(?:\s+\[\s*(?P<hi>\d+)\s*:\s*(?P<lo>\d+)\s*\])?"
        r"\s+arg_mem_(?P<number>\d+)_(?P<pin>addr0|content_en|write_en|write_data|read_data|done)\b"
    )
    pins: dict[int, dict[str, tuple[str, int]]] = {}
    for match in declaration.finditer(module.group(1)):
        width = (
            int(match.group("hi")) - int(match.group("lo")) + 1
            if match.group("hi") is not None else 1
        )
        port_pins = pins.setdefault(int(match.group("number")), {})
        port_pins[match.group("pin")] = (match.group("direction"), width)
    if not pins or sorted(pins) != list(range(len(pins))):
        raise ValueError("SV memories are not a complete zero-based sequence")
    expected = {"addr0", "content_en", "write_en", "write_data", "read_data", "done"}
    result: list[SvMemoryPort] = []
    for number in range(len(pins)):
        port = pins[number]
        if set(port) != expected:
            raise ValueError(f"arg_mem_{number} does not expose the six memory pins")
        width = port["read_data"][1]
        if port["write_data"][1] != width:
            raise ValueError(f"arg_mem_{number} read/write widths disagree")
        result.append(SvMemoryPort(number, width, 1 << port["addr0"][1]))
    return tuple(result)


def validate_abi(
    semantic: tuple[SemanticMemory, ...], rtl: tuple[SvMemoryPort, ...]
) -> None:
    if len(rtl) < len(semantic):
        raise ValueError("RTL exposes fewer memories than the semantic ABI")
    for memory in semantic:
        port = rtl[memory.number]
        if port.width != memory.width:
            raise ValueError(
                f"arg_mem_{memory.number} width {port.width} does not match "
                f"semantic width {memory.width}"
            )
        required_depth = math.prod(memory.shape)
        if port.depth < required_depth:
            raise ValueError(
                f"arg_mem_{memory.number} depth {port.depth} is smaller than "
                f"semantic depth {required_depth}"
            )


def runtime_values(exported: object) -> tuple[object, ...]:
    positional, keyword = exported.example_inputs
    if keyword:
        raise ValueError("W4A8 phase fixture requires positional example inputs")
    user_inputs = iter(positional)
    values: list[object] = []
    for spec in exported.graph_signature.input_specs:
        kind = spec.kind.name
        if kind == "PARAMETER":
            continue
        if kind == "USER_INPUT":
            try:
                values.append(next(user_inputs))
            except StopIteration as error:
                raise ValueError("graph signature has more user inputs than examples") from error
            continue
        if kind == "BUFFER":
            value = exported.state_dict.get(spec.target)
            if value is None:
                value = exported.constants.get(spec.target)
            if value is None:
                raise ValueError(f"missing persistent buffer {spec.target}")
            values.append(value)
            continue
        raise ValueError(f"unsupported ExportedProgram input kind: {kind}")
    try:
        next(user_inputs)
    except StopIteration:
        pass
    else:
        raise ValueError("example inputs remain after graph signature traversal")
    return tuple(values)


def tensor_payload(tensor: object) -> tuple[bytes, str, tuple[int, ...]]:
    value = tensor.detach().cpu().contiguous()
    dtype = str(value.dtype)
    shape = tuple(value.shape)
    flat = _flatten(value.tolist())
    formats = {
        "torch.int8": "b",
        "torch.int64": "q",
        "torch.float32": "f",
    }
    if dtype == "torch.bool":
        return bytes(int(item) for item in flat), dtype, shape
    try:
        fmt = formats[dtype]
    except KeyError as error:
        raise ValueError(f"unsupported W4A8 fixture tensor dtype: {dtype}") from error
    return struct.pack(f"<{len(flat)}{fmt}", *flat), dtype, shape


def _flatten(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        return [value]
    result: list[object] = []
    for item in value:
        result.extend(_flatten(item))
    return result


def render_fixture(
    rtl: tuple[SvMemoryPort, ...], roles: PhaseRoles, *, timeout_cycles: int
) -> str:
    if timeout_cycles <= 0:
        raise ValueError("timeout_cycles must be positive")
    declarations: list[str] = []
    connections: list[str] = []
    service: list[str] = []
    initialization: list[str] = []
    for port in rtl:
        addr_width = max(1, (port.depth - 1).bit_length())
        number = port.number
        declarations.extend(
            [
                f"logic [{port.width - 1}:0] mem{number} [0:{port.depth - 1}];",
                f"wire [{addr_width - 1}:0] a{number}_addr;",
                f"wire a{number}_en, a{number}_we;",
                f"wire [{port.width - 1}:0] a{number}_wdata;",
                f"logic [{port.width - 1}:0] a{number}_rdata;",
                f"logic a{number}_done;",
            ]
        )
        connections.extend(
            [
                f".arg_mem_{number}_addr0(a{number}_addr)",
                f".arg_mem_{number}_content_en(a{number}_en)",
                f".arg_mem_{number}_write_en(a{number}_we)",
                f".arg_mem_{number}_write_data(a{number}_wdata)",
                f".arg_mem_{number}_read_data(a{number}_rdata)",
                f".arg_mem_{number}_done(a{number}_done)",
            ]
        )
        service.extend(
            [
                f"  if (reset) begin a{number}_done <= 0; a{number}_rdata <= '0; end",
                f"  else if (a{number}_en) begin",
                f"    a{number}_done <= 1;",
                f"    if (a{number}_we) mem{number}[a{number}_addr] <= a{number}_wdata;",
                f"    else a{number}_rdata <= mem{number}[a{number}_addr];",
                "  end else a%d_done <= 0;" % number,
            ]
        )
        initialization.append(
            f"  for (int i = 0; i < {port.depth}; i++) mem{number}[i] = '0;"
        )
        if number in roles.inputs:
            initialization.append(f'  $readmemh("mem{number}.hex", mem{number});')
    dumps = [f'  $writememh("out{number}.hex", mem{number});' for number in roles.outputs]
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "module tb;",
            "logic clk = 0, reset = 1, go = 0; wire done;",
            "integer timeout_counter = 0;",
            "always #5 clk = ~clk;",
            *declarations,
            "always_ff @(posedge clk) begin",
            *service,
            "end",
            "main_1 dut(.clk(clk), .reset(reset), .go(go), .done(done),",
            "  " + ",\n  ".join(connections) + ");",
            "initial begin",
            *initialization,
            "  repeat (3) @(posedge clk);",
            "  @(negedge clk); reset = 0; go = 1;",
            f"  while (!done && timeout_counter < {timeout_cycles}) begin",
            "    @(posedge clk); timeout_counter = timeout_counter + 1;",
            "  end",
            "  if (!done) $fatal(1, \"TIMEOUT cycles=%0d\", timeout_counter);",
            "  @(negedge clk); go = 0; repeat (2) @(posedge clk);",
            *dumps,
            "  $display(\"DONE cycles=%0d\", timeout_counter);",
            "  $finish;",
            "end",
            "endmodule",
            "",
        ]
    )


def decode_hex_words(source: str, *, width: int, count: int) -> bytes:
    if width == 1:
        byte_width = 1
    elif width % 8 == 0:
        byte_width = width // 8
    else:
        raise ValueError(f"unsupported output memory width: {width}")
    words = [
        token
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
        for token in line.split()
    ]
    if len(words) < count:
        raise ValueError(f"output memory has {len(words)} words, expected at least {count}")
    payload = bytearray()
    for word in words[:count]:
        if "x" in word.lower() or "z" in word.lower():
            raise ValueError(f"output memory contains unknown word: {word}")
        value = int(word, 16)
        payload.extend(value.to_bytes(byte_width, "little"))
    return bytes(payload)


def normalize_simulation_sv(source: str) -> str:
    normalizer_path = Path(__file__).with_name("run_rc_sv_equivalence.py")
    spec = importlib.util.spec_from_file_location("_rc_sv_equivalence_normalizer", normalizer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load simulation normalizer from {normalizer_path}")
    normalizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(normalizer)
    return normalizer._normalized_sv_text(source)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _float_metrics(actual: bytes, expected: bytes) -> dict[str, object]:
    if len(actual) != len(expected) or len(actual) % 4:
        raise ValueError("float comparison payload sizes disagree")
    count = len(actual) // 4
    lhs = struct.unpack(f"<{count}f", actual)
    rhs = struct.unpack(f"<{count}f", expected)
    differences = [abs(a - b) for a, b in zip(lhs, rhs)]
    return {
        "element_count": count,
        "max_abs_error": max(differences, default=0.0),
        "mean_abs_error": sum(differences) / count if count else 0.0,
        "actual_sha256": _sha256(actual),
        "expected_sha256": _sha256(expected),
        "bit_exact": actual == expected,
    }


def _run(args: argparse.Namespace) -> int:
    # Importing PT2E registration is required before torch.export.load can
    # resolve quantized_decomposed operators from the frozen archive.
    import torch
    from torch.ao.quantization.quantize_pt2e import convert_pt2e  # noqa: F401

    args.work_dir.mkdir(parents=True, exist_ok=True)
    sv_source = args.sv.read_text(encoding="utf-8")
    semantic = parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    rtl = parse_sv_memory_ports(sv_source)
    validate_abi(semantic, rtl)
    roles = phase_roles(args.phase, semantic_port_count=len(semantic))
    exported = torch.export.load(args.exported)
    values = runtime_values(exported)
    if len(values) != len(roles.inputs):
        raise ValueError(
            f"archive has {len(values)} runtime values, ABI requires {len(roles.inputs)}"
        )
    inputs = []
    for number, tensor in zip(roles.inputs, values):
        payload, dtype, shape = tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape:
            # Rank-zero tensors are represented by one-element Calyx memories.
            if not (shape == () and memory.shape == (1,)):
                raise ValueError(
                    f"arg_mem_{number} tensor shape {shape} != semantic {memory.shape}"
                )
        words = memory_words(payload, width=memory.width)
        (args.work_dir / f"mem{number}.hex").write_text(
            "\n".join(words) + "\n", encoding="ascii"
        )
        inputs.append(
            {"port": number, "shape": list(shape), "dtype": dtype, "sha256": _sha256(payload)}
        )
    fixture = render_fixture(rtl, roles, timeout_cycles=args.timeout_cycles)
    fixture_path = args.work_dir / "tb.sv"
    fixture_path.write_text(fixture, encoding="utf-8")
    normalized_sv_path = args.work_dir / "main.normalized.sv"
    normalized_sv_path.write_text(normalize_simulation_sv(sv_source), encoding="utf-8")
    compile_log = args.work_dir / "verilator-build.log"
    compile_command = [
        args.verilator,
        "--binary",
        "--top-module", "tb",
        "--Mdir", str(args.work_dir / "obj_dir"),
        "-Wno-fatal",
        "-Wno-WIDTHEXPAND",
        "-Wno-WIDTHTRUNC",
        "-j", str(args.jobs),
        str(normalized_sv_path),
        str(fixture_path),
    ]
    started = time.monotonic()
    with compile_log.open("w", encoding="utf-8") as log:
        compiled = subprocess.run(compile_command, stdout=log, stderr=subprocess.STDOUT)
    compile_seconds = time.monotonic() - started
    if compiled.returncode:
        raise RuntimeError(f"Verilator compilation failed; see {compile_log}")
    simulation_log = args.work_dir / "simulation.log"
    started = time.monotonic()
    with simulation_log.open("w", encoding="utf-8") as log:
        simulated = subprocess.run(
            [str(args.work_dir / "obj_dir/Vtb")],
            cwd=args.work_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    simulation_seconds = time.monotonic() - started
    if simulated.returncode:
        raise RuntimeError(f"RTL simulation failed; see {simulation_log}")
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    expected_records = [reference["last_logits"], *reference["cache_leaves"]]
    comparisons = []
    for number, memory, record in zip(roles.outputs, semantic[len(roles.inputs):], expected_records):
        expected = bytes.fromhex(record["little_endian_hex"])
        actual = decode_hex_words(
            (args.work_dir / f"out{number}.hex").read_text(encoding="ascii"),
            width=memory.width,
            count=math.prod(memory.shape),
        )
        metrics = _float_metrics(actual, expected)
        metrics.update({"port": number, "shape": list(memory.shape), "dtype": record["dtype"]})
        comparisons.append(metrics)
    passed = all(item["max_abs_error"] <= args.atol for item in comparisons)
    report = {
        "schema": "rc-serving-w4a8-sv-equivalence-v1",
        "phase": args.phase,
        "status": "pass" if passed else "mismatch",
        "atol": args.atol,
        "semantic_port_count": len(semantic),
        "rtl_port_count": len(rtl),
        "inputs": inputs,
        "comparisons": comparisons,
        "compile_seconds": compile_seconds,
        "simulation_seconds": simulation_seconds,
        "artifacts": {
            "sv": str(args.sv), "flat_scf": str(args.flat_scf),
            "exported": str(args.exported), "reference": str(args.reference),
        },
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("prefill-8", "decode-8", "decode-9"))
    parser.add_argument("--sv", required=True, type=Path)
    parser.add_argument("--flat-scf", required=True, type=Path)
    parser.add_argument("--exported", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout-cycles", type=int, default=100_000_000)
    parser.add_argument("--atol", type=float, default=1e-4)
    args = parser.parse_args()
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(_run(args))


if __name__ == "__main__":
    main()
