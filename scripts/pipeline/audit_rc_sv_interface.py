#!/usr/bin/env python3
"""Audit the fixed RC ABI without confusing it with a completed SV gate.

The exact PT2E W8A8 representative core already reaches flat-SCF with a
memref argument for tokens and a caller-provided memref for its raw int8
output.  This tool records that fact and, if SV is available, separately checks
whether the emitted top still exposes functional transport rather than only
the Calyx go/done control interface.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_ARGUMENT_COUNT = 27
TOKEN_ARGUMENT_INDEX = 25
OUTPUT_ARGUMENT_INDEX = 26
TOKEN_MEMREF_TYPE = "memref<1x8xi64>"
OUTPUT_MEMREF_TYPE = "memref<1x8x6xi8>"


def _matching_paren(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        character = text[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unclosed parenthesis")


def _main_signature(text: str) -> tuple[str, str]:
    match = re.search(r"\bfunc\.func\s+@main\s*\(", text)
    if match is None:
        raise ValueError("missing func.func @main")
    opening = text.find("(", match.start())
    closing = _matching_paren(text, opening)
    body_start = text.find("{", closing)
    if body_start < 0:
        raise ValueError("missing @main body")
    return text[opening + 1 : closing], text[closing + 1 : body_start]


def _function_arguments(signature: str) -> list[tuple[str, str]]:
    return re.findall(
        r"(%[A-Za-z_.$][A-Za-z0-9_.$]*|%arg[0-9]+)\s*:\s*([^,\n]+)",
        signature,
    )


def _blocked(reason: str) -> dict[str, object]:
    return {"status": "blocked-abi", "reason": reason}


def audit_flat_scf_abi(text: str) -> dict[str, object]:
    """Validate the actual fixed RC buffer ABI at the flat-SCF boundary."""
    try:
        signature, suffix = _main_signature(text)
    except ValueError as error:
        return _blocked(str(error))

    if "->" in suffix:
        return _blocked("@main has a function result; expected caller-owned output buffer")

    arguments = _function_arguments(signature)
    if len(arguments) != EXPECTED_ARGUMENT_COUNT:
        return _blocked(
            f"@main has {len(arguments)} arguments; expected {EXPECTED_ARGUMENT_COUNT}"
        )

    token_name, token_type = arguments[TOKEN_ARGUMENT_INDEX]
    output_name, output_type = arguments[OUTPUT_ARGUMENT_INDEX]
    if token_type != TOKEN_MEMREF_TYPE:
        return _blocked(
            f"argument {TOKEN_ARGUMENT_INDEX} is {token_type}; expected {TOKEN_MEMREF_TYPE}"
        )
    if output_type != OUTPUT_MEMREF_TYPE:
        return _blocked(
            f"argument {OUTPUT_ARGUMENT_INDEX} is {output_type}; expected {OUTPUT_MEMREF_TYPE}"
        )

    copy_pattern = re.compile(
        rf"\bmemref\.copy\s+%[^,\s]+\s*,\s*{re.escape(output_name)}\b"
    )
    store_pattern = re.compile(rf"\bmemref\.store\b[^\n]*{re.escape(output_name)}\[")
    if not copy_pattern.search(text) and not store_pattern.search(text):
        return _blocked(f"no memref.copy or memref.store writes {output_name}")

    return {
        "status": "flat-scf-abi-confirmed",
        "entry": "main",
        "argument_count": len(arguments),
        "function_result": "none",
        "token_input": {
            "argument_index": TOKEN_ARGUMENT_INDEX,
            "argument_name": token_name,
            "type": token_type,
            "shape": [1, 8],
            "element_type": "i64",
            "transport": "caller-owned-memref",
        },
        "output_buffer": {
            "argument_index": OUTPUT_ARGUMENT_INDEX,
            "argument_name": output_name,
            "type": output_type,
            "shape": [1, 8, 6],
            "element_type": "i8",
            "final_position": 7,
            "transport": "caller-owned-memref",
        },
        "materialization_required": False,
    }


def _module_ports(text: str, top_module: str) -> list[str]:
    match = re.search(rf"\bmodule\s+{re.escape(top_module)}\b", text)
    if match is None:
        raise ValueError(f"missing SystemVerilog module {top_module}")
    opening = text.find("(", match.end())
    if opening < 0:
        raise ValueError(f"module {top_module} has no ANSI port list")
    closing = _matching_paren(text, opening)
    port_text = text[opening + 1 : closing]
    return re.findall(
        r"\b(?:input|output|inout)\b[^,;()]*?\b([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:,|$)",
        port_text,
        flags=re.MULTILINE,
    )


def audit_sv_text(text: str, *, top_module: str) -> dict[str, object]:
    """Reject a Calyx top that exposes only clk/reset/go/done."""
    try:
        ports = _module_ports(text, top_module)
    except ValueError as error:
        return {"status": "blocked-missing-top", "reason": str(error)}

    lower_ports = {port.lower() for port in ports}
    control_ports = {"clk", "clock", "reset", "rst", "go", "done"}
    payload_ports = sorted(port for port in lower_ports if port not in control_ports)
    if not payload_ports:
        return {
            "status": "blocked-done-only",
            "top_module": top_module,
            "ports": ports,
            "missing": ["token", "raw-output"],
        }

    has_tokens = any("token" in port or "arg25" in port for port in lower_ports)
    has_output = any(
        marker in port
        for port in lower_ports
        for marker in ("logit", "result", "output", "arg26")
    )
    missing = []
    if not has_tokens:
        missing.append("token")
    if not has_output:
        missing.append("raw-output")
    if missing:
        return {
            "status": "blocked-missing-functional-io",
            "top_module": top_module,
            "ports": ports,
            "missing": missing,
        }
    return {
        "status": "pass",
        "top_module": top_module,
        "ports": ports,
        "functional_output_observable": True,
    }


def _first_error_line(log_path: Path | None) -> str | None:
    if log_path is None or not log_path.is_file():
        return None
    lines = log_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if "error:" in line:
            diagnostic = [line.strip()]
            for context_line in lines[index + 1 :]:
                context_line = context_line.strip()
                if context_line:
                    diagnostic.append(context_line)
                    break
            return "\n".join(diagnostic)
    return None


def audit_calyx_artifact(
    manifest_path: Path, log_path: Path | None
) -> dict[str, object]:
    if not manifest_path.is_file():
        return {
            "status": "missing-manifest",
            "reason": f"missing Calyx manifest: {manifest_path}",
        }
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {
            "status": "invalid-manifest",
            "reason": f"invalid Calyx manifest: {error}",
        }

    report: dict[str, object] = {
        "status": manifest.get("status", "unknown"),
        "reason": manifest.get("reason"),
        "float_frontier": manifest.get("float_frontier"),
    }
    first_diagnostic = _first_error_line(log_path)
    if first_diagnostic is not None:
        report["first_diagnostic"] = first_diagnostic
    return report


def build_report(
    flat_scf: Path,
    sv_sources: list[Path],
    top_module: str,
    calyx_manifest: Path | None = None,
    calyx_log: Path | None = None,
) -> dict[str, object]:
    report = audit_flat_scf_abi(flat_scf.read_text(encoding="utf-8"))
    if report["status"] != "flat-scf-abi-confirmed":
        report["sv_interface"] = {"status": "not-attempted"}
        return report

    if calyx_manifest is not None:
        calyx = audit_calyx_artifact(calyx_manifest, calyx_log)
        report["calyx"] = calyx
        if calyx["status"] != "ok":
            report["sv_interface"] = {
                "status": "blocked-before-sv",
                "reason": calyx.get("reason", "Calyx did not produce an artifact"),
            }
            return report

    if not sv_sources:
        report["sv_interface"] = {
            "status": "not-built",
            "reason": "no generated SV source was supplied to the audit",
        }
        return report

    missing_sources = [str(source) for source in sv_sources if not source.is_file()]
    if missing_sources:
        report["sv_interface"] = {
            "status": "not-built",
            "reason": "missing generated SV source",
            "missing_sources": missing_sources,
        }
        return report

    report["sv_interface"] = audit_sv_text(
        "\n".join(source.read_text(encoding="utf-8") for source in sv_sources),
        top_module=top_module,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the fixed RC flat-SCF and generated-SV functional ABI."
    )
    parser.add_argument("--flat-scf", type=Path, required=True)
    parser.add_argument("--sv-source", type=Path, action="append", default=[])
    parser.add_argument("--calyx-manifest", type=Path)
    parser.add_argument("--calyx-log", type=Path)
    parser.add_argument("--top-module", default="main")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.flat_scf.is_file():
        raise SystemExit(f"missing flat-SCF input: {args.flat_scf}")
    report = build_report(
        args.flat_scf,
        args.sv_source,
        args.top_module,
        args.calyx_manifest,
        args.calyx_log,
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["status"] == "flat-scf-abi-confirmed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
