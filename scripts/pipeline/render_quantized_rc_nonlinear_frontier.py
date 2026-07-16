#!/usr/bin/env python3
"""Render the bounded conclusion from nonlinear lowering matrix evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_PRIMITIVES = (
    ("exp", "math.exp"),
    ("tanh", "math.tanh"),
    ("fpowi-cube", "math.fpowi"),
    ("sqrt", "math.sqrt"),
)
LIMITS = [
    "No SV, DDR3, host, board, or FPGA-utilization claim is made by this result."
]


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_routes(routes: list[dict[str, object]]) -> None:
    for route in routes:
        if route.get("semantic_classification") != "exact":
            continue
        route_id = str(route.get("route_id", "")).lower()
        if "scout" in route_id or "approx" in route_id:
            raise ValueError("approximate or scout route cannot be exact")
        comparison = route.get("oracle_comparison")
        if not isinstance(comparison, dict) or comparison.get("status") != "pass":
            raise ValueError("exact route requires a passing oracle comparison")


def attempt_status(route: dict[str, object]) -> str:
    attempt = route.get("attempt")
    return str(attempt.get("status")) if isinstance(attempt, dict) else "not-run"


def circt_status(route: dict[str, object]) -> str:
    calyx = route.get("calyx")
    if isinstance(calyx, dict):
        return str(calyx.get("status"))
    return str(route.get("circt_status", "not-run"))


def route_is_validated(route: dict[str, object]) -> bool:
    comparison = route.get("oracle_comparison")
    return (
        attempt_status(route) == "accepted"
        and circt_status(route) == "accepted"
        and route.get("semantic_classification") == "exact"
        and isinstance(comparison, dict)
        and comparison.get("status") == "pass"
    )


def route_operation(route: dict[str, object], default: str) -> str:
    census = route.get("census")
    if isinstance(census, dict):
        float_ops = census.get("float_ops")
        if isinstance(float_ops, list) and float_ops:
            return str(float_ops[0])
    return default


def primitive_routes(matrix: dict[str, object], primitive: str) -> list[dict[str, object]]:
    routes = matrix.get("routes")
    if not isinstance(routes, list):
        raise ValueError("matrix has no route list")
    return [
        route
        for route in routes
        if isinstance(route, dict)
        and route.get("scope") == "primitive"
        and route.get("primitive") == primitive
    ]


def first_remaining_frontier(matrix: dict[str, object]) -> dict[str, object]:
    for primitive, default_operation in REQUIRED_PRIMITIVES:
        routes = primitive_routes(matrix, primitive)
        for route in routes:
            if attempt_status(route) == "rejected" or circt_status(route) == "rejected":
                return {
                    "primitive": primitive,
                    "operation": route_operation(route, default_operation),
                    "route_id": route.get("route_id"),
                    "attempt_status": attempt_status(route),
                    "circt_status": circt_status(route),
                    "reason": "named standard route did not produce a valid Calyx-accepted artifact",
                }
        if not any(route_is_validated(route) for route in routes):
            route = routes[0] if routes else {}
            return {
                "primitive": primitive,
                "operation": route_operation(route, default_operation),
                "route_id": route.get("route_id", "no-recorded-route"),
                "attempt_status": attempt_status(route),
                "circt_status": circt_status(route),
                "reason": "no named route has both Calyx acceptance and a passing frozen-oracle comparison",
            }
    return {}


def recommendation(matrix: dict[str, object]) -> dict[str, str]:
    first = first_remaining_frontier(matrix)
    if not first:
        return {
            "kind": "standard-route-integration",
            "reason": "every required primitive has a Calyx-accepted route with a passing frozen-oracle comparison",
        }
    return {
        "kind": "upstream-compiler-or-hardware-work",
        "reason": f"{first['operation']} remains at the first named standard-route boundary; no approximation is implied by this result",
    }


def family_payload(matrix: dict[str, object], primitive: str, operation: str) -> dict[str, object]:
    routes = primitive_routes(matrix, primitive)
    summaries: list[dict[str, object]] = []
    for route in routes:
        census = route.get("census")
        representation = (
            census.get("representation", "unknown")
            if isinstance(census, dict)
            else "unknown"
        )
        comparison = route.get("oracle_comparison")
        summaries.append(
            {
                "route_id": route.get("route_id"),
                "documentation_id": route.get("documentation_id"),
                "transform_status": attempt_status(route),
                "representation": representation,
                "circt_status": circt_status(route),
                "oracle_comparison_status": (
                    comparison.get("status", "not-run")
                    if isinstance(comparison, dict)
                    else "not-run"
                ),
                "semantic_classification": route.get("semantic_classification"),
            }
        )
    return {
        "family": primitive,
        "source_operation": operation,
        "validated": any(route_is_validated(route) for route in routes),
        "routes": summaries,
    }


def build_result(
    matrix: dict[str, object], slices: dict[str, object], reference: dict[str, object]
) -> dict[str, object]:
    routes_value = matrix.get("routes")
    if not isinstance(routes_value, list) or not all(
        isinstance(route, dict) for route in routes_value
    ):
        raise ValueError("matrix routes must be objects")
    routes = [route for route in routes_value if isinstance(route, dict)]
    validate_routes(routes)
    reference_results = reference.get("results")
    if not isinstance(reference_results, list):
        raise ValueError("reference has no result list")
    case_ids = [
        row.get("case_id")
        for row in reference_results
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    ]
    if len(case_ids) != len(reference_results):
        raise ValueError("reference result case IDs must be strings")
    families = [
        family_payload(matrix, primitive, operation)
        for primitive, operation in REQUIRED_PRIMITIVES
    ]
    first = first_remaining_frontier(matrix)
    status = "standard-route-advance" if not first else "blocked-standard-route-frontier"
    return {
        "schema_version": 1,
        "status": status,
        "model_key": matrix.get("model_key"),
        "oracle": {
            "case_ids": case_ids,
            "comparison": matrix.get("oracle", {}).get("comparison", {})
            if isinstance(matrix.get("oracle"), dict)
            else {},
        },
        "provenance": {
            "source": matrix.get("source", {}),
            "inputs": matrix.get("inputs", {}),
            "tools": matrix.get("tools", {}),
            "route_documentation": matrix.get("route_documentation", {}),
            "composite_count": len(slices.get("composites", []))
            if isinstance(slices.get("composites"), list)
            else 0,
        },
        "families": families,
        "first_remaining_frontier": first,
        "recommendation": recommendation(matrix),
        "limits": LIMITS,
    }


def route_summary(family: dict[str, object]) -> tuple[str, str, str, str, str]:
    routes = family.get("routes")
    if not isinstance(routes, list) or not routes:
        return ("no recorded route", "unknown", "not-run", "not-run", "none")
    route_names = "; ".join(str(route.get("route_id")) for route in routes)
    representations = "; ".join(
        sorted({str(route.get("representation")) for route in routes})
    )
    circt = "; ".join(sorted({str(route.get("circt_status")) for route in routes}))
    oracle = "; ".join(
        sorted({str(route.get("oracle_comparison_status")) for route in routes})
    )
    documentation = "; ".join(
        sorted({str(route.get("documentation_id")) for route in routes})
    )
    return route_names, representations, circt, oracle, documentation


def markdown_scalar(value: object) -> str:
    return str(value).replace("|", "\\|")


def render_markdown(payload: dict[str, object]) -> str:
    provenance = payload.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    inputs = provenance.get("inputs")
    inputs = inputs if isinstance(inputs, dict) else {}
    tools = provenance.get("tools")
    tools = tools if isinstance(tools, dict) else {}
    lines = [
        "# Quantized RC Nonlinear Lowering Frontier",
        "",
        f"**Status:** `{payload['status']}`",
        "",
        "## Fixed unit and oracle",
        "",
        f"- Model key: `{payload.get('model_key')}`.",
        "- Frozen corpus cases: "
        + ", ".join(f"`{case_id}`" for case_id in payload.get("oracle", {}).get("case_ids", [])),
        "- The comparison boundary is six final raw int8 codes plus the lowest-index argmax token ID for every frozen case.",
        "",
        "## Inputs and tool provenance",
        "",
    ]
    for name, record in sorted(inputs.items()):
        if isinstance(record, dict):
            lines.append(
                f"- `{name}`: SHA-256 `{record.get('sha256')}`, path `{record.get('path')}`."
            )
    for name, record in sorted(tools.items()):
        if isinstance(record, dict):
            lines.append(f"- `{name}`: `{record.get('path')}` (exit `{record.get('exit_code')}`).")
    lines.extend(
        [
            "",
            "## Nonlinear family evidence",
            "",
            "| Family | Source operation | Route results | Representation | CIRCT | Oracle comparison | Route documentation |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    families = payload.get("families")
    if isinstance(families, list):
        for family in families:
            if not isinstance(family, dict):
                continue
            routes, representation, circt, oracle, documentation = route_summary(family)
            lines.append(
                "| "
                + " | ".join(
                    markdown_scalar(value)
                    for value in (
                        family.get("family"),
                        family.get("source_operation"),
                        routes,
                        representation,
                        circt,
                        oracle,
                        documentation,
                    )
                )
                + " |"
            )
    first = payload.get("first_remaining_frontier")
    lines.extend(["", "## First remaining frontier", ""])
    if isinstance(first, dict) and first:
        lines.extend(
            [
                f"- Operation: `{first.get('operation')}`.",
                f"- Route: `{first.get('route_id')}`.",
                f"- Boundary: {first.get('reason')}",
            ]
        )
    else:
        lines.append("- None: every required primitive met the configured standard-route gate.")
    recommendation = payload.get("recommendation")
    lines.extend(["", "## Recommendation", ""])
    if isinstance(recommendation, dict):
        lines.extend(
            [
                f"- Kind: `{recommendation.get('kind')}`.",
                f"- Reason: {recommendation.get('reason')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Explicit limits",
            "",
            "- Provenance fragments are not numerical equivalence evidence and are not executable semantic replacements.",
            *[f"- {limit}" for limit in payload.get("limits", [])],
            "- No approximation, resource-scout transform, or changed PyTorch oracle is used by this result.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--slices", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-markdown", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    payload = build_result(
        load_object(args.matrix), load_object(args.slices), load_object(args.reference)
    )
    write_json(args.out_json, payload)
    args.out_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.out_markdown.write_text(render_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
