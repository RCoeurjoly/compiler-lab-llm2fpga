#!/usr/bin/env python3
"""Run the bounded, non-approximate nonlinear lowering evidence matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ERROR_RE = re.compile(r"(^|: )error:", re.MULTILINE)
FLOAT_OP_RE = re.compile(
    r"\b(?:math\.[A-Za-z0-9_]+|arith\.[A-Za-z0-9_]*f[A-Za-z0-9_]*)\b"
)
INTEGER_TOSA_RE = re.compile(r"\btosa\.(?:table|rescale|apply_rescale)\b")
OP_RE = re.compile(
    r"\b(?:torch|tosa|math|arith|linalg|scf|memref|tensor|func)\.[A-Za-z0-9_.]+\b"
)
TYPE_RE = re.compile(r"\b(?:f16|f32|f64|bf16|i[0-9]+|ui[0-9]+)\b")

ROUTE_DOCUMENTATION = {
    "circt-scf-to-calyx": {
        "kind": "upstream-tool",
        "reference": "https://circt.llvm.org/docs/Passes/",
        "claim_boundary": "observed CIRCT acceptance is compiler-capability evidence only",
    },
    "mlir-canonicalize-and-math": {
        "kind": "upstream-tool",
        "reference": "https://mlir.llvm.org/docs/Passes/",
        "claim_boundary": "pass completion does not establish PT2E equivalence",
    },
    "torch-mlir-tosa": {
        "kind": "upstream-tool",
        "reference": "https://github.com/llvm/torch-mlir",
        "claim_boundary": "Torch-to-TOSA conversion is representation evidence only",
    },
    "mlir-tosa": {
        "kind": "upstream-specification-and-tool",
        "reference": "https://mlir.llvm.org/docs/Dialects/TOSA/",
        "claim_boundary": "a TOSA table or rescale form is not automatically exact relative to PT2E",
    },
    "llm2fpga-zero-point-compatibility": {
        "kind": "repository-local-pass",
        "reference": "tools/mlir-passes/LegalizePt2eTosaZeroPoint.cpp",
        "claim_boundary": "local compatibility transformation; not an upstream standard route",
    },
}
REQUIRED_PRIMITIVES = {"exp", "tanh", "fpowi-cube", "sqrt"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(
    label: str,
    command: list[str],
    log_path: Path,
    output_path: Path | None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    """Run one non-shell command and reject diagnostics even at exit code zero."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, env=env
        )
        stdout, stderr, exit_code = (
            completed.stdout,
            completed.stderr,
            completed.returncode,
        )
    except OSError as error:
        stdout, stderr, exit_code = "", f"{error}\n", 127
    log_text = stdout + stderr
    log_path.write_text(log_text, encoding="utf-8")
    diagnostic_error = bool(ERROR_RE.search(log_text))
    output_exists = (
        output_path is not None
        and output_path.is_file()
        and output_path.stat().st_size > 0
    )
    return {
        "label": label,
        "command": command,
        "exit_code": exit_code,
        "diagnostic_error": diagnostic_error,
        "output_exists": output_exists,
        "status": (
            "accepted"
            if exit_code == 0 and not diagnostic_error and output_exists
            else "rejected"
        ),
        "log": str(log_path),
        "output": None if output_path is None else str(output_path),
    }


def skipped_attempt(label: str, blocked_by: str) -> dict[str, object]:
    return {
        "label": label,
        "status": "skipped",
        "reason": f"blocked by rejected route: {blocked_by}",
        "exit_code": None,
        "diagnostic_error": False,
        "output_exists": False,
        "log": None,
        "output": None,
    }


def bash_script_command(script: str, *args: str) -> list[str]:
    """Run repository pipeline helpers like the established Nix pipeline."""

    return ["bash", script, *args]


def not_run_oracle() -> dict[str, str]:
    return {
        "status": "not-run",
        "reason": "no executable transformed candidate at the PT2E raw-code boundary",
    }


def compare_oracle(
    reference: dict[str, object], candidate: dict[str, object]
) -> dict[str, object]:
    """Compare exactly six int8 codes and one token ID for every reference case."""

    expected_rows = reference.get("results")
    observed_rows = candidate.get("results")
    if not isinstance(expected_rows, list) or not isinstance(observed_rows, list):
        return {"status": "fail", "cases": [], "reason": "missing result list"}
    expected = {
        row.get("case_id"): row
        for row in expected_rows
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    observed = {
        row.get("case_id"): row
        for row in observed_rows
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    cases: list[dict[str, object]] = []
    for case_id in sorted(set(expected) | set(observed)):
        lhs = expected.get(case_id)
        rhs = observed.get(case_id)
        lhs_codes = lhs.get("output_codes_i8") if lhs is not None else None
        rhs_codes = rhs.get("output_codes_i8") if rhs is not None else None
        expected_shape_ok = isinstance(lhs_codes, list) and len(lhs_codes) == 6
        observed_shape_ok = isinstance(rhs_codes, list) and len(rhs_codes) == 6
        codes_match = (
            lhs is not None
            and rhs is not None
            and expected_shape_ok
            and observed_shape_ok
            and lhs_codes == rhs_codes
        )
        token_match = (
            lhs is not None
            and rhs is not None
            and "token_id" in lhs
            and "token_id" in rhs
            and lhs["token_id"] == rhs["token_id"]
        )
        cases.append(
            {
                "case_id": case_id,
                "codes_match": codes_match,
                "token_match": token_match,
                "expected_code_count": len(lhs_codes) if isinstance(lhs_codes, list) else None,
                "observed_code_count": len(rhs_codes) if isinstance(rhs_codes, list) else None,
            }
        )
    return {
        "status": (
            "pass"
            if cases and all(row["codes_match"] and row["token_match"] for row in cases)
            else "fail"
        ),
        "cases": cases,
    }


def validate_semantic_claim(row: dict[str, object]) -> None:
    if row["semantic_classification"] != "exact":
        return
    route_id = str(row["route_id"]).lower()
    if "scout" in route_id or "approx" in route_id:
        raise ValueError("approximate or scout route cannot be exact")
    comparison = row.get("oracle_comparison")
    if not isinstance(comparison, dict) or comparison.get("status") != "pass":
        raise ValueError("exact route requires a passing oracle comparison")


def operation_census(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    operations = Counter(OP_RE.findall(text))
    types = Counter(TYPE_RE.findall(text))
    float_ops = sorted(set(FLOAT_OP_RE.findall(text)))
    integer_tosa_forms = sorted(set(INTEGER_TOSA_RE.findall(text)))
    if integer_tosa_forms and float_ops:
        representation = "mixed"
    elif integer_tosa_forms:
        representation = "standard-integer-table"
    elif float_ops:
        representation = "float"
    else:
        representation = "unknown"
    return {
        "operation_counts": dict(sorted(operations.items())),
        "type_counts": dict(sorted(types.items())),
        "float_ops": float_ops,
        "integer_tosa_forms": integer_tosa_forms,
        "representation": representation,
    }


def route_row(
    *,
    route_id: str,
    scope: str,
    documentation_id: str,
    attempt: dict[str, object],
    input_path: Path,
    output_path: Path | None,
    primitive: str | None = None,
    calyx: dict[str, object] | None = None,
) -> dict[str, object]:
    census_path = output_path if attempt["status"] == "accepted" else input_path
    row: dict[str, object] = {
        "route_id": route_id,
        "scope": scope,
        "documentation_id": documentation_id,
        "primitive": primitive,
        "input": str(input_path),
        "attempt": attempt,
        "census": operation_census(census_path),
        "semantic_classification": "undetermined",
        "oracle_comparison": not_run_oracle(),
    }
    if calyx is not None:
        row["calyx"] = calyx
        row["circt_status"] = calyx["status"]
    return row


def run_circt(
    circt_opt: str, input_mlir: Path, out_dir: Path, label: str
) -> dict[str, object]:
    output = out_dir / "calyx.mlir"
    return run_command(
        label,
        [
            circt_opt,
            str(input_mlir),
            "--lower-scf-to-calyx=top-level-function=main",
            "-o",
            str(output),
        ],
        out_dir / "lower-scf-to-calyx.log",
        output,
    )


def run_primitive_routes(
    *,
    primitives: dict[str, Path],
    mlir_opt: str,
    circt_opt: str,
    commands_dir: Path,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    transformations = (
        (
            "upstream-canonicalize-cse",
            "mlir-canonicalize-and-math",
            ["--canonicalize", "--cse"],
            "normalized.mlir",
        ),
        (
            "upstream-convert-math-to-funcs",
            "mlir-canonicalize-and-math",
            ["--convert-math-to-funcs"],
            "functions.mlir",
        ),
        (
            "upstream-convert-math-to-libm",
            "mlir-canonicalize-and-math",
            ["--convert-math-to-libm"],
            "libm.mlir",
        ),
    )
    for primitive, input_mlir in sorted(primitives.items()):
        direct_dir = commands_dir / primitive / "direct-circt"
        direct = run_circt(circt_opt, input_mlir, direct_dir, "direct-circt")
        rows.append(
            route_row(
                route_id="direct-circt",
                scope="primitive",
                primitive=primitive,
                documentation_id="circt-scf-to-calyx",
                attempt=direct,
                input_path=input_mlir,
                output_path=input_mlir,
                calyx=direct,
            )
        )
        for route_id, documentation_id, passes, output_name in transformations:
            route_dir = commands_dir / primitive / route_id
            output = route_dir / output_name
            attempt = run_command(
                route_id,
                [mlir_opt, str(input_mlir), *passes, "-o", str(output)],
                route_dir / "transform.log",
                output,
            )
            if attempt["status"] == "accepted":
                calyx = run_circt(circt_opt, output, route_dir / "calyx", route_id)
            else:
                calyx = skipped_attempt("direct-circt", route_id)
            rows.append(
                route_row(
                    route_id=route_id,
                    scope="primitive",
                    primitive=primitive,
                    documentation_id=documentation_id,
                    attempt=attempt,
                    input_path=input_mlir,
                    output_path=output,
                    calyx=calyx,
                )
            )
    return rows


def full_route(
    *,
    route_id: str,
    documentation_id: str,
    attempt: dict[str, object],
    input_path: Path,
    output_path: Path | None,
    calyx: dict[str, object] | None = None,
) -> dict[str, object]:
    return route_row(
        route_id=route_id,
        scope="full-rc",
        documentation_id=documentation_id,
        attempt=attempt,
        input_path=input_path,
        output_path=output_path,
        calyx=calyx,
    )


def run_full_rc_routes(
    *,
    torch_mlir: Path,
    flat_scf: Path,
    torch_mlir_opt: str,
    mlir_opt: str,
    circt_opt: str,
    pass_plugin: str,
    linalg_to_scf_script: str,
    scf_to_flat_scf_script: str,
    flat_scf_blocker_report: str,
    commands_dir: Path,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    raw_tosa = commands_dir / "canonical-pt2e-torch-to-tosa" / "raw.tosa.mlir"
    torch_to_tosa = run_command(
        "canonical-pt2e-torch-to-tosa",
        [
            torch_mlir_opt,
            str(torch_mlir),
            "--torch-fuse-quantized-ops",
            "--torch-backend-to-tosa-backend-pipeline",
            "-o",
            str(raw_tosa),
        ],
        raw_tosa.parent / "transform.log",
        raw_tosa,
    )
    rows.append(
        full_route(
            route_id="canonical-pt2e-torch-to-tosa",
            documentation_id="torch-mlir-tosa",
            attempt=torch_to_tosa,
            input_path=torch_mlir,
            output_path=raw_tosa,
        )
    )

    raw_validated = commands_dir / "upstream-tosa-validate-raw" / "raw.validated.tosa.mlir"
    if torch_to_tosa["status"] == "accepted":
        raw_validate = run_command(
            "upstream-tosa-validate-raw",
            [
                mlir_opt,
                str(raw_tosa),
                "--pass-pipeline=builtin.module(tosa-validate)",
                "-o",
                str(raw_validated),
            ],
            raw_validated.parent / "validate.log",
            raw_validated,
        )
    else:
        raw_validate = skipped_attempt("upstream-tosa-validate-raw", "canonical-pt2e-torch-to-tosa")
    rows.append(
        full_route(
            route_id="upstream-tosa-validate-raw",
            documentation_id="mlir-tosa",
            attempt=raw_validate,
            input_path=raw_tosa if raw_tosa.exists() else torch_mlir,
            output_path=raw_validated,
        )
    )

    legalized_tosa = commands_dir / "local-pt2e-tosa-zero-point-legalization" / "legalized.tosa.mlir"
    if torch_to_tosa["status"] == "accepted":
        zero_point = run_command(
            "local-pt2e-tosa-zero-point-legalization",
            [
                mlir_opt,
                str(raw_tosa),
                f"--load-pass-plugin={pass_plugin}",
                "--pass-pipeline=builtin.module(llm2fpga-legalize-pt2e-tosa-zero-point,canonicalize,cse,tosa-validate)",
                "-o",
                str(legalized_tosa),
            ],
            legalized_tosa.parent / "legalize.log",
            legalized_tosa,
        )
    else:
        zero_point = skipped_attempt(
            "local-pt2e-tosa-zero-point-legalization", "canonical-pt2e-torch-to-tosa"
        )
    rows.append(
        full_route(
            route_id="local-pt2e-tosa-zero-point-legalization",
            documentation_id="llm2fpga-zero-point-compatibility",
            attempt=zero_point,
            input_path=raw_tosa if raw_tosa.exists() else torch_mlir,
            output_path=legalized_tosa,
        )
    )

    tosa_linalg = commands_dir / "upstream-tosa-to-linalg-and-arith" / "tosa.linalg.mlir"
    if zero_point["status"] == "accepted":
        tosa_to_linalg = run_command(
            "upstream-tosa-to-linalg-and-arith",
            [
                mlir_opt,
                str(legalized_tosa),
                "--tosa-to-linalg-pipeline",
                "--tosa-to-tensor",
                "--tosa-to-arith=include-apply-rescale",
                "--canonicalize",
                "--cse",
                "-o",
                str(tosa_linalg),
            ],
            tosa_linalg.parent / "lower.log",
            tosa_linalg,
        )
    else:
        tosa_to_linalg = skipped_attempt(
            "upstream-tosa-to-linalg-and-arith",
            "local-pt2e-tosa-zero-point-legalization",
        )
    rows.append(
        full_route(
            route_id="upstream-tosa-to-linalg-and-arith",
            documentation_id="mlir-tosa",
            attempt=tosa_to_linalg,
            input_path=legalized_tosa if legalized_tosa.exists() else torch_mlir,
            output_path=tosa_linalg,
        )
    )

    tosa_scf = commands_dir / "tosa-linalg-to-scf" / "model.scf.mlir"
    if tosa_to_linalg["status"] == "accepted":
        linalg_to_scf = run_command(
            "tosa-linalg-to-scf",
            bash_script_command(
                linalg_to_scf_script, mlir_opt, str(tosa_linalg), str(tosa_scf)
            ),
            tosa_scf.parent / "lower.log",
            tosa_scf,
        )
    else:
        linalg_to_scf = skipped_attempt(
            "tosa-linalg-to-scf", "upstream-tosa-to-linalg-and-arith"
        )
    rows.append(
        full_route(
            route_id="tosa-linalg-to-scf",
            documentation_id="mlir-tosa",
            attempt=linalg_to_scf,
            input_path=tosa_linalg if tosa_linalg.exists() else torch_mlir,
            output_path=tosa_scf,
        )
    )

    flat_dir = commands_dir / "tosa-scf-to-flat-scf"
    tosa_flat = flat_dir / "flat.scf.mlir"
    if linalg_to_scf["status"] == "accepted":
        flatten_env = os.environ.copy()
        flatten_env["FLAT_SCF_BLOCKER_REPORT"] = flat_scf_blocker_report
        scf_to_flat = run_command(
            "tosa-scf-to-flat-scf",
            bash_script_command(
                scf_to_flat_scf_script, mlir_opt, str(tosa_scf), str(flat_dir)
            ),
            flat_dir / "lower.log",
            tosa_flat,
            env=flatten_env,
        )
    else:
        scf_to_flat = skipped_attempt("tosa-scf-to-flat-scf", "tosa-linalg-to-scf")
    rows.append(
        full_route(
            route_id="tosa-scf-to-flat-scf",
            documentation_id="mlir-tosa",
            attempt=scf_to_flat,
            input_path=tosa_scf if tosa_scf.exists() else torch_mlir,
            output_path=tosa_flat,
        )
    )

    tosa_calyx_dir = commands_dir / "tosa-flat-scf-to-circt"
    if scf_to_flat["status"] == "accepted":
        tosa_calyx = run_circt(circt_opt, tosa_flat, tosa_calyx_dir, "tosa-flat-scf-to-circt")
    else:
        tosa_calyx = skipped_attempt("tosa-flat-scf-to-circt", "tosa-scf-to-flat-scf")
    rows.append(
        full_route(
            route_id="tosa-flat-scf-to-circt",
            documentation_id="circt-scf-to-calyx",
            attempt=tosa_calyx,
            input_path=tosa_flat if tosa_flat.exists() else flat_scf,
            output_path=tosa_calyx_dir / "calyx.mlir",
            calyx=tosa_calyx,
        )
    )

    direct_dir = commands_dir / "direct-linalg-flat-scf-to-circt"
    direct_calyx = run_circt(
        circt_opt, flat_scf, direct_dir, "direct-linalg-flat-scf-to-circt"
    )
    rows.append(
        full_route(
            route_id="direct-linalg-flat-scf-to-circt",
            documentation_id="circt-scf-to-calyx",
            attempt=direct_calyx,
            input_path=flat_scf,
            output_path=flat_scf,
            calyx=direct_calyx,
        )
    )
    return rows


def composite_rows(slices: dict[str, object]) -> list[dict[str, object]]:
    composites = slices.get("composites")
    if not isinstance(composites, list):
        raise ValueError("slices.json has no composite list")
    rows: list[dict[str, object]] = []
    for composite in composites:
        if not isinstance(composite, dict):
            raise ValueError("composite provenance entry must be an object")
        family = str(composite.get("family"))
        occurrence = composite.get("occurrence")
        rows.append(
            {
                "route_id": f"provenance-{family}-{occurrence}",
                "input_kind": "non-executable-provenance-fragment",
                "transform_status": "not-run",
                "reason": "fragment preserves source provenance and external values but is not an independently executable semantic replacement",
                "whole_rc_routes": [
                    "canonical-pt2e-torch-to-tosa",
                    "direct-linalg-flat-scf-to-circt",
                ],
                "fragment": composite,
            }
        )
    return rows


def tool_version(path: str) -> dict[str, object]:
    try:
        completed = subprocess.run(
            [path, "--version"], check=False, capture_output=True, text=True
        )
        output = (completed.stdout + completed.stderr).strip()
        return {"path": path, "exit_code": completed.returncode, "output": output}
    except OSError as error:
        return {"path": path, "exit_code": 127, "output": str(error)}


def parse_primitives(items: list[str]) -> dict[str, Path]:
    primitives: dict[str, Path] = {}
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name or not value:
            raise ValueError(f"primitive must use name=PATH: {item}")
        if name in primitives:
            raise ValueError(f"duplicate primitive: {name}")
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"missing primitive input: {path}")
        primitives[name] = path
    if set(primitives) != REQUIRED_PRIMITIVES:
        raise ValueError(
            "primitive keys must be exactly " + ", ".join(sorted(REQUIRED_PRIMITIVES))
        )
    return primitives


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--torch-mlir", required=True, type=Path)
    parser.add_argument("--flat-scf", required=True, type=Path)
    parser.add_argument("--slices", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--torch-mlir-opt", required=True)
    parser.add_argument("--mlir-opt", required=True)
    parser.add_argument("--circt-opt", required=True)
    parser.add_argument("--pass-plugin", required=True)
    parser.add_argument("--linalg-to-scf-script", required=True)
    parser.add_argument("--scf-to-flat-scf-script", required=True)
    parser.add_argument("--flat-scf-blocker-report", required=True)
    parser.add_argument("--primitive", action="append", default=[])
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")


def main() -> None:
    args = parse_args()
    for path, label in (
        (args.torch_mlir, "Torch-MLIR"),
        (args.flat_scf, "flat-SCF"),
        (args.slices, "slices"),
        (args.reference, "reference"),
    ):
        require_file(path, label)
    primitives = parse_primitives(args.primitive)
    slices = json.loads(args.slices.read_text(encoding="utf-8"))
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    if not isinstance(slices, dict) or not isinstance(reference, dict):
        raise ValueError("slices and reference inputs must be JSON objects")
    reference_results = reference.get("results")
    if not isinstance(reference_results, list):
        raise ValueError("reference has no result list")
    case_ids = [row.get("case_id") for row in reference_results if isinstance(row, dict)]
    if any(not isinstance(case_id, str) for case_id in case_ids):
        raise ValueError("reference result case IDs must be strings")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    commands_dir = args.out_dir / "commands"
    primitive_rows = run_primitive_routes(
        primitives=primitives,
        mlir_opt=args.mlir_opt,
        circt_opt=args.circt_opt,
        commands_dir=commands_dir / "primitives",
    )
    full_rows = run_full_rc_routes(
        torch_mlir=args.torch_mlir,
        flat_scf=args.flat_scf,
        torch_mlir_opt=args.torch_mlir_opt,
        mlir_opt=args.mlir_opt,
        circt_opt=args.circt_opt,
        pass_plugin=args.pass_plugin,
        linalg_to_scf_script=args.linalg_to_scf_script,
        scf_to_flat_scf_script=args.scf_to_flat_scf_script,
        flat_scf_blocker_report=args.flat_scf_blocker_report,
        commands_dir=commands_dir / "full-rc",
    )
    routes = primitive_rows + full_rows
    for route in routes:
        validate_semantic_claim(route)
    oracle = {
        "reference_sha256": sha256(args.reference),
        "case_ids": sorted(case_ids),
        "comparison": not_run_oracle(),
    }
    oracle_comparison = {
        "schema_version": 1,
        "model_key": slices.get("model_key"),
        **oracle,
    }
    write_json(args.out_dir / "oracle-comparison.json", oracle_comparison)
    matrix = {
        "schema_version": 1,
        "model_key": slices.get("model_key"),
        "source": {
            "path": str(args.torch_mlir),
            "sha256": sha256(args.torch_mlir),
            "stage": "torch-mlir",
        },
        "inputs": {
            "torch_mlir": {"path": str(args.torch_mlir), "sha256": sha256(args.torch_mlir)},
            "flat_scf": {"path": str(args.flat_scf), "sha256": sha256(args.flat_scf)},
            "slices": {"path": str(args.slices), "sha256": sha256(args.slices)},
            "reference": {"path": str(args.reference), "sha256": sha256(args.reference)},
        },
        "oracle": oracle,
        "tools": {
            "torch_mlir_opt": tool_version(args.torch_mlir_opt),
            "mlir_opt": tool_version(args.mlir_opt),
            "circt_opt": tool_version(args.circt_opt),
        },
        "route_documentation": ROUTE_DOCUMENTATION,
        "routes": routes,
        "composites": composite_rows(slices),
    }
    write_json(args.out_dir / "matrix.json", matrix)


if __name__ == "__main__":
    main()
