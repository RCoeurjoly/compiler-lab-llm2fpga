#!/usr/bin/env python3
"""Simulate one generated W4A8 serving phase against its frozen oracle."""

from __future__ import annotations

import dataclasses
import math
import re


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
