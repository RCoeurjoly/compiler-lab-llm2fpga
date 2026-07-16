#!/usr/bin/env python3
"""Extract non-executable nonlinear provenance fragments from frozen RC MLIR."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess  # Kept in the declared standard-library dependency set.
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_RE = re.compile(
    r"^\s*(?P<results>%[-A-Za-z0-9_.$]+(?:\s*,\s*%[-A-Za-z0-9_.$]+)*)\s*=\s*"
    r'(?P<op>"[^"]+"|[A-Za-z_][-A-Za-z0-9_.$]*(?:\.[-A-Za-z0-9_.$]+)*)'
)
SSA_RE = re.compile(r"%[-A-Za-z0-9_.$]+")

REQUIRED_FAMILIES = {
    "attention-softmax": (
        "torch.aten.max.dim",
        "torch.aten.sub.Tensor",
        "torch.aten.exp",
        "torch.aten.sum.dim_IntList",
        "torch.aten.div.Tensor",
    ),
    "tanh-gelu": ("torch.aten.pow.Tensor_Scalar", "torch.aten.tanh"),
    "layernorm": (
        "torch.aten.rsqrt",
        "torch.aten.sum.dim_IntList",
        "torch.aten.div.Scalar",
    ),
}
REQUIRED_FLAT_SCF_OPS = ("math.exp", "math.fpowi", "math.tanh", "math.rsqrt")


@dataclass(frozen=True)
class Operation:
    line_number: int
    text: str
    results: list[str]
    op: str
    operands: list[str]


@dataclass(frozen=True)
class Slice:
    family: str
    occurrence: int
    anchor_operation: str
    first_line: int
    last_line: int
    lines: list[str]
    retained_external_values: list[str]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operation_name(match: re.Match[str]) -> str:
    name = match.group("op")
    return name[1:-1] if name.startswith('"') else name


def parse_operations(lines: list[str]) -> list[Operation]:
    operations: list[Operation] = []
    for line_number, line in enumerate(lines, start=1):
        match = RESULT_RE.match(line)
        if match is None:
            continue
        results = SSA_RE.findall(match.group("results"))
        rhs = line[match.end() :]
        operations.append(
            Operation(
                line_number=line_number,
                text=line,
                results=results,
                op=operation_name(match),
                operands=SSA_RE.findall(rhs),
            )
        )
    if not operations:
        raise ValueError("no SSA-producing operations were recognized in Torch-MLIR")
    return operations


def first_after(
    operations: list[Operation], start: int, op: str, stop: int | None = None
) -> int | None:
    limit = len(operations) if stop is None else stop
    for index in range(start + 1, limit):
        if operations[index].op == op:
            return index
    return None


def preceding_dequantize(operations: list[Operation], index: int) -> int:
    for candidate in range(index, -1, -1):
        if operations[candidate].op == "torch.aten.dequantize.tensor":
            return candidate
    raise ValueError("missing preceding torch.aten.dequantize.tensor")


def first_quantize_after(operations: list[Operation], index: int) -> int:
    for candidate in range(index + 1, len(operations)):
        if operations[candidate].op == "torch.aten.quantize_per_tensor":
            return candidate
    raise ValueError("missing following torch.aten.quantize_per_tensor")


def consumes(operation: Operation, value: str) -> bool:
    return value in operation.operands


def require_result(operation: Operation, label: str) -> str:
    if not operation.results:
        raise ValueError(f"{label} has no SSA result")
    return operation.results[0]


def new_slice(
    lines: list[str],
    operations: list[Operation],
    family: str,
    occurrence: int,
    anchor_index: int,
    first_index: int,
    last_index: int,
) -> Slice:
    first_line = operations[first_index].line_number
    last_line = operations[last_index].line_number
    fragment_operations = operations[first_index : last_index + 1]
    defined = {
        value for operation in fragment_operations for value in operation.results
    }
    used = {
        value for operation in fragment_operations for value in operation.operands
    }
    return Slice(
        family=family,
        occurrence=occurrence,
        anchor_operation=operations[anchor_index].op,
        first_line=first_line,
        last_line=last_line,
        lines=lines[first_line - 1 : last_line],
        retained_external_values=sorted(used - defined),
    )


def extract_softmax(
    lines: list[str], operations: list[Operation]
) -> list[Slice]:
    slices: list[Slice] = []
    for anchor_index, maximum in enumerate(operations):
        if maximum.op != "torch.aten.max.dim":
            continue
        sub_index = first_after(operations, anchor_index, "torch.aten.sub.Tensor")
        if sub_index is None or not consumes(
            operations[sub_index], require_result(maximum, maximum.op)
        ):
            continue
        exp_index = first_after(operations, sub_index, "torch.aten.exp")
        if exp_index is None or not consumes(
            operations[exp_index], require_result(operations[sub_index], operations[sub_index].op)
        ):
            continue
        sum_index = first_after(operations, exp_index, "torch.aten.sum.dim_IntList")
        if sum_index is None or not consumes(
            operations[sum_index], require_result(operations[exp_index], operations[exp_index].op)
        ):
            continue
        div_index = first_after(operations, sum_index, "torch.aten.div.Tensor")
        if div_index is None:
            continue
        exp_value = require_result(operations[exp_index], operations[exp_index].op)
        sum_value = require_result(operations[sum_index], operations[sum_index].op)
        if not (consumes(operations[div_index], exp_value) and consumes(operations[div_index], sum_value)):
            continue
        slices.append(
            new_slice(
                lines,
                operations,
                "attention-softmax",
                len(slices),
                anchor_index,
                preceding_dequantize(operations, anchor_index),
                div_index,
            )
        )
    return slices


def extract_tanh_gelu(
    lines: list[str], operations: list[Operation]
) -> list[Slice]:
    slices: list[Slice] = []
    for anchor_index, power in enumerate(operations):
        if power.op != "torch.aten.pow.Tensor_Scalar":
            continue
        next_rsqrt = first_after(operations, anchor_index, "torch.aten.rsqrt")
        tanh_index = first_after(
            operations, anchor_index, "torch.aten.tanh", stop=next_rsqrt
        )
        if tanh_index is None:
            continue
        quantize_index = first_quantize_after(operations, tanh_index)
        slices.append(
            new_slice(
                lines,
                operations,
                "tanh-gelu",
                len(slices),
                anchor_index,
                preceding_dequantize(operations, anchor_index),
                quantize_index,
            )
        )
    return slices


def extract_layernorm(
    lines: list[str], operations: list[Operation]
) -> list[Slice]:
    slices: list[Slice] = []
    for anchor_index, rsqrt in enumerate(operations):
        if rsqrt.op != "torch.aten.rsqrt":
            continue
        add_index = anchor_index - 1
        while add_index >= 0 and operations[add_index].op != "torch.aten.add.Scalar":
            add_index -= 1
        if add_index < 0 or not consumes(rsqrt, require_result(operations[add_index], operations[add_index].op)):
            continue
        div_index = add_index - 1
        while div_index >= 0 and operations[div_index].op != "torch.aten.div.Scalar":
            div_index -= 1
        if div_index < 0 or not consumes(operations[add_index], require_result(operations[div_index], operations[div_index].op)):
            continue
        sum_index = div_index - 1
        while sum_index >= 0 and operations[sum_index].op != "torch.aten.sum.dim_IntList":
            sum_index -= 1
        if sum_index < 0 or not consumes(operations[div_index], require_result(operations[sum_index], operations[sum_index].op)):
            continue
        broadcast_index = first_after(operations, anchor_index, "torch.aten.broadcast_to")
        if broadcast_index is None or not consumes(
            operations[broadcast_index], require_result(rsqrt, rsqrt.op)
        ):
            continue
        quantize_index = first_quantize_after(operations, broadcast_index)
        slices.append(
            new_slice(
                lines,
                operations,
                "layernorm",
                len(slices),
                anchor_index,
                preceding_dequantize(operations, sum_index),
                quantize_index,
            )
        )
    return slices


def extract_family(
    lines: list[str], operations: list[Operation], family: str
) -> list[Slice]:
    extractors = {
        "attention-softmax": extract_softmax,
        "tanh-gelu": extract_tanh_gelu,
        "layernorm": extract_layernorm,
    }
    try:
        slices = extractors[family](lines, operations)
    except KeyError as error:
        raise ValueError(f"unknown nonlinear family: {family}") from error
    if not slices:
        raise ValueError(f"missing required nonlinear family: {family}")
    return slices


def write_fragment(path: Path, source_sha256: str, slice_: Slice) -> None:
    retained = ", ".join(slice_.retained_external_values) or "(none)"
    contents = "\n".join(
        [
            "// GENERATED: non-executable provenance fragment; not a semantic replacement.",
            f"// source_sha256: {source_sha256}",
            f"// source_range: {slice_.first_line}-{slice_.last_line}",
            f"// family: {slice_.family}",
            f"// retained_external_values: {retained}",
            *slice_.lines,
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def count_flat_scf_nonlinears(text: str) -> dict[str, int]:
    counts = {
        operation: len(re.findall(rf"\b{re.escape(operation)}\b", text))
        for operation in REQUIRED_FLAT_SCF_OPS
    }
    for operation, count in counts.items():
        if count == 0:
            raise ValueError(f"missing required flat-SCF operation: {operation}")
    return dict(sorted(counts.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract frozen-RC nonlinear provenance fragments without creating executable replacements."
    )
    parser.add_argument("--torch-mlir", required=True, type=Path)
    parser.add_argument("--flat-scf", required=True, type=Path)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    torch_text = args.torch_mlir.read_text(encoding="utf-8")
    flat_scf_text = args.flat_scf.read_text(encoding="utf-8")
    lines = torch_text.splitlines()
    operations = parse_operations(lines)
    source_sha = sha256(args.torch_mlir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    composites: list[dict[str, Any]] = []
    for family in REQUIRED_FAMILIES:
        for slice_ in extract_family(lines, operations, family):
            fragment = Path("slices") / f"{family}-{slice_.occurrence}.mlirfrag"
            write_fragment(args.out_dir / fragment, source_sha, slice_)
            composites.append(
                {
                    "family": slice_.family,
                    "occurrence": slice_.occurrence,
                    "anchor_operation": slice_.anchor_operation,
                    "source_range": [slice_.first_line, slice_.last_line],
                    "retained_external_values": slice_.retained_external_values,
                    "fragment": str(fragment),
                    "executable": False,
                    "semantic_replacement": False,
                }
            )

    write_json(
        args.out_dir / "slices.json",
        {
            "schema_version": 1,
            "model_key": args.model_key,
            "source": {
                "path": str(args.torch_mlir),
                "sha256": source_sha,
                "stage": "torch-mlir",
            },
            "composites": composites,
        },
    )
    write_json(
        args.out_dir / "primitive-observations.json",
        {
            "schema_version": 1,
            "model_key": args.model_key,
            "source": {
                "path": str(args.flat_scf),
                "sha256": sha256(args.flat_scf),
                "stage": "flat-scf",
            },
            "op_counts": count_flat_scf_nonlinears(flat_scf_text),
        },
    )


if __name__ == "__main__":
    main()
