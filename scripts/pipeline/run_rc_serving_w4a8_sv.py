#!/usr/bin/env python3
"""Simulate one generated W4A8 serving phase against its frozen oracle."""

from __future__ import annotations

import dataclasses
import re


@dataclasses.dataclass(frozen=True)
class SemanticMemory:
    number: int
    shape: tuple[int, ...]
    width: int


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
