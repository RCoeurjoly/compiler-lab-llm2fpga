#!/usr/bin/env python3
"""Record RC-derived ordinary-float binding evidence without a float gate."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any


NON_GATING_POLICY = (
    "informational source inventory only; float presence or count does not decide lowering acceptance"
)

FORM_SPECS = {
    "arith.addf.f32": ("arith.addf", r"\barith\.addf\b.*:\s*f32"),
    "arith.subf.f32": ("arith.subf", r"\barith\.subf\b.*:\s*f32"),
    "arith.mulf.f32": ("arith.mulf", r"\barith\.mulf\b.*:\s*f32"),
    "arith.divf.f32": ("arith.divf", r"\barith\.divf\b.*:\s*f32"),
    "arith.cmpf.ugt.f32": ("arith.cmpf", r"\barith\.cmpf ugt,.*:\s*f32"),
    "arith.sitofp.i32-to-f32": ("arith.sitofp", r"\barith\.sitofp\b.*i32 to f32"),
    "arith.fptosi.f32-to-i8": ("arith.fptosi", r"\barith\.fptosi\b.*f32 to i8"),
    "arith.uitofp.i1-to-f32": ("arith.uitofp", r"\barith\.uitofp\b.*i1 to f32"),
}

CALYX_WRAPPER_MODULES = {
    "std_addFN",
    "std_mulFN",
    "std_divSqrtFN",
    "std_compareFN",
    "std_intToFp",
    "std_fpToInt",
}
HARDFLOAT_IMPLEMENTATION_MODULES = {
    "addRecFN",
    "mulRecFN",
    "divSqrtRecFNToRaw_small",
    "compareRecFN",
    "iNToRecFN",
    "recFNToIN",
    "fNToRecFN",
    "recFNToFN",
}
MRC_SPECS = {
    "addf-f32": {"form_id": "arith.addf.f32", "expected_wrapper": "std_addFN"},
    "subf-f32": {"form_id": "arith.subf.f32", "expected_wrapper": "std_addFN"},
    "mulf-f32": {"form_id": "arith.mulf.f32", "expected_wrapper": "std_mulFN"},
    "divf-f32": {"form_id": "arith.divf.f32", "expected_wrapper": "std_divSqrtFN"},
    "cmpf-ugt-f32": {
        "form_id": "arith.cmpf.ugt.f32",
        "expected_wrapper": "std_compareFN",
    },
    "sitofp-i32-f32": {
        "form_id": "arith.sitofp.i32-to-f32",
        "expected_wrapper": "std_intToFp",
    },
    "fptosi-f32-i8": {
        "form_id": "arith.fptosi.f32-to-i8",
        "expected_wrapper": "std_fpToInt",
    },
    "uitofp-i1-f32": {
        "form_id": "arith.uitofp.i1-to-f32",
        "expected_wrapper": "std_intToFp",
    },
}

ERROR_RE = re.compile(r"(^|: )error:", re.MULTILINE)
FLOAT_OPERATION_RE = re.compile(
    r"\b(?:arith\.[A-Za-z0-9_]*f|arith\.(?:sitofp|uitofp|fptosi)|math\.[A-Za-z0-9_]+)\b"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observe_rc_forms(flat_scf: Path) -> dict[str, object]:
    lines = flat_scf.read_text(encoding="utf-8").splitlines()
    forms: dict[str, dict[str, object]] = {
        form_id: {"operation": operation, "count": 0, "line": None, "text": None}
        for form_id, (operation, _pattern) in FORM_SPECS.items()
    }
    unclassified: set[str] = set()

    for line_number, line in enumerate(lines, 1):
        matching_form_ids = {
            form_id
            for form_id, (_operation, pattern) in FORM_SPECS.items()
            if re.search(pattern, line)
        }
        for form_id in matching_form_ids:
            form = forms[form_id]
            form["count"] = int(form["count"]) + 1
            if form["line"] is None:
                form["line"] = line_number
                form["text"] = line.strip()

        for operation in FLOAT_OPERATION_RE.findall(line):
            is_declared_here = any(
                FORM_SPECS[form_id][0] == operation for form_id in matching_form_ids
            )
            if not is_declared_here:
                unclassified.add(operation)

    return {
        "source_sha256": sha256_file(flat_scf),
        "source_path": str(flat_scf),
        "policy": NON_GATING_POLICY,
        "forms": forms,
        "unclassified_float_operations": sorted(unclassified),
    }


def require_observed_forms(report: dict[str, object]) -> None:
    forms = report["forms"]
    if not isinstance(forms, dict):
        raise ValueError("inventory has no declared forms")
    for form_id in FORM_SPECS:
        form = forms.get(form_id)
        if not isinstance(form, dict) or form.get("count") == 0:
            raise ValueError(f"frozen RC no longer contains observed form: {form_id}")


def run_command(
    label: str, command: list[str], log_path: Path, output_path: Path | None
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
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


def binding_status(
    circt_attempt: dict[str, object], native_sv_ok: bool, modules: set[str]
) -> str:
    if circt_attempt.get("status") != "accepted":
        return "not-attempted"
    if not native_sv_ok:
        return "native-export-rejected"
    if modules & CALYX_WRAPPER_MODULES and modules & HARDFLOAT_IMPLEMENTATION_MODULES:
        return "accepted-with-hardfloat-binding"
    return "accepted-without-recorded-hardfloat-binding"
