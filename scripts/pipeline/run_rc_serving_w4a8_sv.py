#!/usr/bin/env python3
"""Simulate one generated W4A8 serving phase against its frozen oracle."""

from __future__ import annotations

import dataclasses
import math
import re
import struct


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
