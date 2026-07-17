#!/usr/bin/env python3
"""Evaluate Softmax exponentiation candidates without rewriting the PT2E graph.

This is a numerical candidate harness.  It is deliberately separate from the
canonical compiler route: a passing candidate here is necessary, not sufficient,
for MLIR/CIRCT integration.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from typing import Callable, Sequence


Vector = Sequence[float]
ExpFn = Callable[[float], float]


def exact_exp(x: float) -> float:
    return math.exp(x)


def _range_reduce(x: float) -> tuple[int, float]:
    """Return n,r with x = n*ln(2)+r and r near zero."""
    n = math.floor(x / math.log(2.0) + 0.5)
    return n, x - n * math.log(2.0)


def polynomial_exp(x: float, order: int = 5) -> float:
    n, r = _range_reduce(x)
    value = 1.0
    for degree in range(order, 0, -1):
        value = 1.0 + r * value / degree
    return math.ldexp(value, n)


def lut_exp(x: float, entries: int = 256, lo: float = -8.0) -> float:
    """Piecewise-linear table over the stabilized Softmax domain [lo, 0]."""
    if x <= lo:
        return math.exp(lo)
    if x >= 0.0:
        return 1.0
    position = (x - lo) * (entries - 1) / -lo
    left = int(math.floor(position))
    fraction = position - left
    step = -lo / (entries - 1)
    return (1.0 - fraction) * math.exp(lo + left * step) + fraction * math.exp(lo + (left + 1) * step)


def cordic_exp(x: float, iterations: int = 12) -> float:
    """Exponent approximation using a fixed Taylor/Horner iteration budget.

    This is a numerical stand-in for a hardware iterative unit, not a claim
    that CIRCT or Calyx already provides an exponential primitive.
    """
    return polynomial_exp(x, order=max(2, min(iterations, 12)))


def streaming_softmax(row: Vector, exp_fn: ExpFn = exact_exp) -> list[float]:
    """Online-style max/normalization calculation with no materialized exp row."""
    maximum = max(row)
    total = 0.0
    for value in row:
        total += exp_fn(value - maximum)
    return [exp_fn(value - maximum) / total for value in row]


def softmax(row: Vector, exp_fn: ExpFn = exact_exp) -> list[float]:
    maximum = max(row)
    values = [exp_fn(value - maximum) for value in row]
    total = sum(values)
    return [value / total for value in values]


@dataclass(frozen=True)
class Candidate:
    name: str
    exp_fn: ExpFn
    implementation_class: str


def candidates() -> tuple[Candidate, ...]:
    return (
        Candidate("streaming-exact", exact_exp, "streaming; exact arithmetic oracle"),
        Candidate("lut-256", lut_exp, "piecewise-linear LUT; domain [-8,0]"),
        Candidate("polynomial-5", lambda x: polynomial_exp(x, 5), "range-reduced Horner polynomial"),
        Candidate("cordic-12", lambda x: cordic_exp(x, 12), "fixed-iteration exp stand-in"),
    )


def evaluate(rows: Sequence[Vector]) -> dict[str, object]:
    reference = [softmax(row, exact_exp) for row in rows]
    output: dict[str, object] = {"row_count": len(rows), "row_widths": sorted({len(row) for row in rows}), "candidates": {}}
    for candidate in candidates():
        values = [streaming_softmax(row, candidate.exp_fn) for row in rows]
        errors = [abs(a - b) for expected, observed in zip(reference, values) for a, b in zip(expected, observed)]
        output["candidates"][candidate.name] = {
            "implementation_class": candidate.implementation_class,
            "max_abs_softmax_error": max(errors, default=0.0),
            "mean_abs_softmax_error": sum(errors) / len(errors) if errors else 0.0,
            "finite": all(math.isfinite(value) for row in values for value in row),
            "rows_sum_to_one": all(abs(sum(row) - 1.0) <= 1e-12 for row in values),
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=str, help="JSON file containing arrays of stabilized-score rows")
    parser.add_argument("--out", type=str)
    args = parser.parse_args()
    rows = json.loads(open(args.rows).read()) if args.rows else [[0.0, -0.5, -1.0, -2.0, -4.0, -8.0]]
    result = evaluate(rows)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
