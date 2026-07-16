#!/usr/bin/env python3
"""Record RC-derived ordinary-float binding evidence without a float gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


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
FUTIL_IMPORT_RE = re.compile(r'^import "([^"]+)";$', re.MULTILINE)
SV_MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b")


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


def parse_mrc_assignments(assignments: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for assignment in assignments:
        mrc_id, separator, raw_path = assignment.partition("=")
        if not separator or not mrc_id or not raw_path:
            raise ValueError(f"invalid MRC assignment: {assignment}")
        if mrc_id in parsed:
            raise ValueError(f"duplicate MRC ID: {mrc_id}")
        parsed[mrc_id] = Path(raw_path)
    expected = set(MRC_SPECS)
    observed = set(parsed)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        raise ValueError(f"missing MRC IDs: {', '.join(missing)}")
    if extra:
        raise ValueError(f"unknown MRC IDs: {', '.join(extra)}")
    return parsed


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def skipped_attempt(label: str, reason: str) -> dict[str, object]:
    return {
        "label": label,
        "status": "not-attempted",
        "reason": reason,
        "exit_code": None,
        "diagnostic_error": False,
        "output_exists": False,
        "log": None,
        "output": None,
    }


def run_yosys_slang(
    yosys: str, slang_plugin: str, source: Path, log_path: Path
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        yosys,
        "-m",
        slang_plugin,
        "-p",
        (
            "read_slang --threads 1 --no-proc --max-parse-depth 20000 "
            "--allow-merging-ansi-ports "
            f"--top main {source}; hierarchy -top main -check; stat"
        ),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except OSError as error:
        stdout, stderr, exit_code = "", f"{error}\n", 127
    log_text = stdout + stderr
    log_path.write_text(log_text, encoding="utf-8")
    diagnostic_error = bool(ERROR_RE.search(log_text))
    return {
        "label": "yosys-slang",
        "command": command,
        "exit_code": exit_code,
        "diagnostic_error": diagnostic_error,
        "output_exists": source.is_file() and source.stat().st_size > 0,
        "status": "accepted" if exit_code == 0 and not diagnostic_error else "rejected",
        "log": str(log_path),
        "output": str(source),
    }


def native_export_command(
    bash: Path,
    calyx_to_sv_script: Path,
    circt_translate: Path,
    calyx_bin: Path,
    calyx_lib: Path,
    calyx_dir: Path,
    native_dir: Path,
) -> list[str]:
    return [
        str(bash),
        str(calyx_to_sv_script),
        str(circt_translate),
        str(calyx_bin),
        str(calyx_lib),
        str(calyx_dir),
        str(native_dir),
    ]


def require_file(path: Path, description: str, *, executable: bool = False) -> None:
    if not path.is_file():
        raise ValueError(f"missing {description}: {path}")
    if executable and not os.access(path, os.X_OK):
        raise ValueError(f"not executable {description}: {path}")


def run_binding_evidence(
    *,
    flat_scf: Path,
    circt_opt: Path,
    circt_translate: Path,
    calyx_bin: Path,
    calyx_lib: Path,
    calyx_to_sv_script: Path,
    bash: Path,
    yosys: Path,
    yosys_slang_plugin: Path,
    mrcs: dict[str, Path],
    out_dir: Path,
) -> dict[str, object]:
    require_file(flat_scf, "flat-SCF source")
    for path, description in (
        (circt_opt, "circt-opt"),
        (circt_translate, "circt-translate"),
        (calyx_bin, "calyx"),
        (bash, "bash"),
        (yosys, "yosys"),
    ):
        require_file(path, description, executable=True)
    require_file(calyx_to_sv_script, "Calyx-to-SV script")
    require_file(yosys_slang_plugin, "Yosys Slang plugin")
    if not (calyx_lib / "primitives").is_dir():
        raise ValueError(f"missing Calyx primitives: {calyx_lib / 'primitives'}")
    for mrc_id, path in mrcs.items():
        require_file(path, f"MRC {mrc_id}")

    inventory = observe_rc_forms(flat_scf)
    require_observed_forms(inventory)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for mrc_id, spec in MRC_SPECS.items():
        source = mrcs[mrc_id]
        mrc_dir = out_dir / "mrcs" / mrc_id
        calyx_dir = mrc_dir / "calyx"
        calyx_mlir = calyx_dir / "model.calyx.mlir"
        circt = run_command(
            "circt-lower-scf-to-calyx",
            [
                str(circt_opt),
                str(source),
                "--lower-scf-to-calyx=top-level-function=main",
                "-o",
                str(calyx_mlir),
            ],
            calyx_dir / "lower-scf-to-calyx.log",
            calyx_mlir,
        )
        futil_imports: list[str] = []
        sv_modules: set[str] = set()
        native_sv: dict[str, object]
        yosys_slang: dict[str, object]
        if circt["status"] == "accepted":
            write_json(
                calyx_dir / "manifest.json",
                {"stage": "calyx", "status": "ok", "artifact": "model.calyx.mlir"},
            )
            native_dir = mrc_dir / "native-sv"
            native_sv_path = native_dir / "sv" / "main.sv"
            native_sv = run_command(
                "calyx-to-sv",
                native_export_command(
                    bash,
                    calyx_to_sv_script,
                    circt_translate,
                    calyx_bin,
                    calyx_lib,
                    calyx_dir,
                    native_dir,
                ),
                native_dir / "calyx-to-sv.log",
                native_sv_path,
            )
            futil = native_dir / "model.futil"
            if futil.is_file():
                futil_imports = sorted(FUTIL_IMPORT_RE.findall(futil.read_text(encoding="utf-8")))
            if native_sv_path.is_file() and native_sv_path.stat().st_size > 0:
                sv_modules = set(SV_MODULE_RE.findall(native_sv_path.read_text(encoding="utf-8")))
                yosys_slang = run_yosys_slang(
                    str(yosys),
                    str(yosys_slang_plugin),
                    native_sv_path,
                    native_dir / "yosys-slang.log",
                )
            else:
                yosys_slang = skipped_attempt("yosys-slang", "native SV was not valid")
        else:
            native_sv = skipped_attempt("calyx-to-sv", "CIRCT Calyx lowering was rejected")
            yosys_slang = skipped_attempt("yosys-slang", "CIRCT Calyx lowering was rejected")

        modules = sorted(sv_modules)
        expected_wrapper = str(spec["expected_wrapper"])
        rows.append(
            {
                "id": mrc_id,
                "form_id": spec["form_id"],
                "expected_wrapper": expected_wrapper,
                "expected_wrapper_observed": expected_wrapper in sv_modules,
                "input_sha256": sha256_file(source),
                "circt": circt,
                "futil_imports": futil_imports,
                "native_sv": native_sv,
                "yosys_slang": yosys_slang,
                "sv_modules": modules,
                "binding_status": binding_status(
                    circt,
                    native_sv["status"] == "accepted",
                    sv_modules,
                ),
            }
        )

    return {
        "schema_version": 1,
        "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
        "inventory": inventory,
        "mrcs": rows,
        "limits": [
            "The inventory is not a lowering gate.",
            "MRC capability and binding results are not RC functional-equivalence evidence.",
            "The complete RC still determines the next compiler frontier.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record Calyx/HardFloat binding evidence for RC-derived MRCs."
    )
    parser.add_argument("--flat-scf", required=True, type=Path)
    parser.add_argument("--circt-opt", required=True, type=Path)
    parser.add_argument("--circt-translate", required=True, type=Path)
    parser.add_argument("--calyx-bin", required=True, type=Path)
    parser.add_argument("--calyx-lib", required=True, type=Path)
    parser.add_argument("--calyx-to-sv-script", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--yosys", required=True, type=Path)
    parser.add_argument("--yosys-slang-plugin", required=True, type=Path)
    parser.add_argument("--mrc", required=True, action="append")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    mrcs = parse_mrc_assignments(args.mrc)
    report = run_binding_evidence(
        flat_scf=args.flat_scf,
        circt_opt=args.circt_opt,
        circt_translate=args.circt_translate,
        calyx_bin=args.calyx_bin,
        calyx_lib=args.calyx_lib,
        calyx_to_sv_script=args.calyx_to_sv_script,
        bash=args.bash,
        yosys=args.yosys,
        yosys_slang_plugin=args.yosys_slang_plugin,
        mrcs=mrcs,
        out_dir=args.out_dir,
    )
    write_json(args.out_dir / "report.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
