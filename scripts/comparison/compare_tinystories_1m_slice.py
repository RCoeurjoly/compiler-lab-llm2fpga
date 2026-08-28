#!/usr/bin/env python3
"""Fail-closed comparison of a TinyStories-1M compiler slice and reference.

The harness deliberately separates evidence collection from judgement.  It
never calculates an efficiency delta until the two runs have the same frozen
contract, exact named checkpoint tensors, and final token sequence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "tinystories-1m-slice-comparison-v1"
RESOURCE_FIELDS = ("lut", "ff", "bram", "dsp", "memory_bits")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def manifest_contract_status(contract_path: Path, manifest: dict[str, Any]) -> str:
    """Return the manifest/contract binding status without trusting either path."""
    binding = manifest.get("contract")
    if not isinstance(binding, dict) or not isinstance(binding.get("sha256"), str):
        return "contract_mismatch"
    return "aligned" if binding["sha256"] == sha256_file(contract_path) else "contract_mismatch"


def _contract_identity(contract: dict[str, Any]) -> dict[str, Any]:
    """The whole Task 1 contract is identity, including ABI and reference."""
    return contract


def _reason(message: str) -> list[str]:
    return [message]


def _base_result(contract: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "model": contract.get("model", {}).get("name"),
        "contract_identity": _contract_identity(contract),
        "slice": {
            "kind": manifest.get("slice", {}).get("kind"),
            "status": manifest.get("slice", {}).get("status", manifest.get("status")),
            "manifest_status": manifest.get("status"),
        },
        "status": "incomplete",
        "reasons": [],
        "functional": {"checkpoint_status": "unavailable", "output_status": "unavailable", "first_mismatch": None},
        "resources": None,
        "timing": None,
        "waste_map": [],
        "inputs": {},
    }


def _same_contract(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    return json.dumps(_contract_identity(expected), sort_keys=True, separators=(",", ":")) == json.dumps(_contract_identity(observed), sort_keys=True, separators=(",", ":"))


def _validate_evidence(side: dict[str, Any], label: str) -> list[str]:
    missing: list[str] = []
    for field in ("checkpoint_tensors", "output_tokens"):
        if field not in side or not side[field]:
            missing.append(f"{label}.{field} unavailable")
    return missing


def _first_checkpoint_mismatch(reference: dict[str, Any], compiler: dict[str, Any]) -> dict[str, Any] | None:
    ref = reference["checkpoint_tensors"]
    comp = compiler["checkpoint_tensors"]
    for name in sorted(set(ref) | set(comp)):
        if ref.get(name) != comp.get(name):
            return {"checkpoint": name, "reference": ref.get(name), "compiler": comp.get(name)}
    return None


def _report_provenance_is_complete(report: dict[str, Any]) -> bool:
    return isinstance(report.get("path"), str) and bool(report["path"]) and isinstance(report.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", report["sha256"]) is not None and isinstance(report.get("measurement_id"), str) and bool(report["measurement_id"])


def _resource_deltas(reference: dict[str, Any], compiler: dict[str, Any]) -> dict[str, Any] | None:
    ref = reference.get("resources")
    comp = compiler.get("resources")
    if not isinstance(ref, dict) or not isinstance(comp, dict) or not _report_provenance_is_complete(ref) or not _report_provenance_is_complete(comp) or any(not isinstance(ref.get(field), (int, float)) or isinstance(ref.get(field), bool) or not isinstance(comp.get(field), (int, float)) or isinstance(comp.get(field), bool) for field in RESOURCE_FIELDS):
        return None
    result: dict[str, Any] = {"reference": {field: ref[field] for field in RESOURCE_FIELDS}, "compiler": {field: comp[field] for field in RESOURCE_FIELDS}, "reports": {"reference": {field: ref[field] for field in ("path", "sha256", "measurement_id")}, "compiler": {field: comp[field] for field in ("path", "sha256", "measurement_id")}}}
    for field in RESOURCE_FIELDS:
        result[f"{field}_delta"] = comp[field] - ref[field]
    return result


def _timing_deltas(reference: dict[str, Any], compiler: dict[str, Any]) -> dict[str, Any] | None:
    ref = reference.get("timing")
    comp = compiler.get("timing")
    required = ("max_frequency_mhz", "critical_paths", "cycles_per_token", "interface_overhead_cycles")
    if not isinstance(ref, dict) or not isinstance(comp, dict) or any(field not in ref or field not in comp for field in required):
        return None
    if not _report_provenance_is_complete(ref) or not _report_provenance_is_complete(comp) or not isinstance(ref["max_frequency_mhz"], (int, float)) or not isinstance(comp["max_frequency_mhz"], (int, float)) or not ref["critical_paths"] or not comp["critical_paths"] or not isinstance(ref["cycles_per_token"], int) or not isinstance(comp["cycles_per_token"], int) or not isinstance(ref["interface_overhead_cycles"], int) or not isinstance(comp["interface_overhead_cycles"], int):
        return None
    return {
        "max_frequency_mhz": {"reference": ref["max_frequency_mhz"], "compiler": comp["max_frequency_mhz"], "delta": comp["max_frequency_mhz"] - ref["max_frequency_mhz"]},
        "critical_paths": {"reference": ref["critical_paths"], "compiler": comp["critical_paths"]},
        "cycles_per_token": {"reference": ref["cycles_per_token"], "compiler": comp["cycles_per_token"]},
        "cycles_per_token_delta": comp["cycles_per_token"] - ref["cycles_per_token"],
        "interface_overhead_cycles": {"reference": ref["interface_overhead_cycles"], "compiler": comp["interface_overhead_cycles"]},
        "reports": {"reference": {field: ref[field] for field in ("path", "sha256", "measurement_id")}, "compiler": {field: comp[field] for field in ("path", "sha256", "measurement_id")}},
    }


def _waste_map(compiler: dict[str, Any], resources: dict[str, Any]) -> list[dict[str, Any]]:
    annotations = compiler.get("provenance", {}).get("annotations", [])
    result: list[dict[str, Any]] = []
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        resource = annotation.get("resource")
        measured_delta = annotation.get("measured_delta")
        if resource not in RESOURCE_FIELDS or not isinstance(measured_delta, (int, float)) or isinstance(measured_delta, bool):
            continue
        delta = resources.get(f"{resource}_delta")
        if not isinstance(delta, (int, float)) or delta <= 0 or measured_delta <= 0 or measured_delta > delta:
            continue
        if not all(annotation.get(key) for key in ("kind", "module", "source_operation", "compiler_stage", "measurement_id")) or annotation["measurement_id"] != compiler.get("resources", {}).get("measurement_id"):
            continue
        result.append({
            "kind": annotation["kind"],
            "module": annotation["module"],
            "source_operation": annotation["source_operation"],
            "resource": resource,
            "measured_delta": measured_delta,
            "compiler_stage": annotation["compiler_stage"],
            "evidence": "compiler provenance annotation and measured resource delta",
        })
    return sorted(result, key=lambda item: (-item["measured_delta"], item["module"]))


def compare(reference: dict[str, Any], compiler: dict[str, Any], slice_manifest: dict[str, Any], *, frozen_contract: dict[str, Any], frozen_contract_sha256: str, quantization: str | None = None) -> dict[str, Any]:
    """Compare two explicit evidence objects, returning a fail-closed result."""
    contract = reference.get("contract", {})
    result = _base_result(contract, slice_manifest)
    if slice_manifest.get("status") != "ready":
        result["reasons"] = _reason(f"slice manifest is not ready: {slice_manifest.get('status')}")
        return result
    if not _same_contract(contract, compiler.get("contract", {})):
        result.update(status="contract_mismatch", reasons=_reason("compiler contract identity or quantization differs from reference"))
        return result
    if quantization is not None and quantization != contract.get("quantization"):
        result.update(status="contract_mismatch", reasons=_reason("requested quantization differs from frozen contract quantization"))
        return result
    missing = _validate_evidence(reference, "reference") + _validate_evidence(compiler, "compiler")
    if missing:
        result["reasons"] = missing
        return result
    if not _same_contract(frozen_contract, contract) or not _same_contract(frozen_contract, compiler.get("contract", {})):
        result.update(status="contract_mismatch", reasons=_reason("reference or compiler contract differs from frozen Task 1 contract"))
        return result
    if not isinstance(frozen_contract_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", frozen_contract_sha256) is None or reference.get("contract_sha256") != frozen_contract_sha256 or compiler.get("contract_sha256") != frozen_contract_sha256:
        result.update(status="contract_mismatch", reasons=_reason("reference or compiler contract SHA-256 differs from frozen Task 1 contract"))
        return result
    mismatch = _first_checkpoint_mismatch(reference, compiler)
    if mismatch is not None:
        result.update(status="functional_mismatch", reasons=_reason("exact checkpoint tensors differ"))
        result["functional"] = {"checkpoint_status": "mismatch", "output_status": "not_compared", "first_mismatch": mismatch}
        return result
    if reference["output_tokens"] != compiler["output_tokens"]:
        result.update(status="functional_mismatch", reasons=_reason("final output tokens differ"))
        result["functional"] = {"checkpoint_status": "matched", "output_status": "mismatch", "first_mismatch": {"checkpoint": "final_output_tokens", "reference": reference["output_tokens"], "compiler": compiler["output_tokens"]}}
        return result
    result["functional"] = {"checkpoint_status": "matched", "output_status": "matched", "first_mismatch": None}
    resources = _resource_deltas(reference, compiler)
    timing = _timing_deltas(reference, compiler)
    if resources is None or timing is None:
        absent = []
        if resources is None:
            absent.append("complete resource statistics unavailable")
        if timing is None:
            absent.append("complete timing statistics unavailable")
        result["reasons"] = absent
        return result
    result.update(status="aligned", reasons=[], resources=resources, timing=timing, waste_map=_waste_map(compiler, resources))
    return result


def parse_yosys_statistics(path: Path) -> dict[str, Any]:
    """Parse common Yosys JSON/stat report forms, retaining raw provenance."""
    raw = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {"path": str(path), "sha256": sha256_file(path)}
    try:
        value = json.loads(raw)
        statistics = value.get("statistics", {}) if isinstance(value, dict) else {}
        if isinstance(statistics, dict) and "num_memory_bits" in statistics:
            result.update({
                "lut": None,
                "ff": None,
                "bram": None,
                "dsp": None,
                "memory_bits": statistics["num_memory_bits"],
                "structural_cells": statistics.get("num_cells_by_type", {}),
                "scope": value.get("scope"),
            })
            return result
        modules = value.get("modules") if isinstance(value, dict) else None
        if isinstance(modules, dict) and modules:
            module = modules.get("top") if isinstance(modules.get("top"), dict) else next((entry for entry in modules.values() if isinstance(entry, dict)), {})
            cell_types = module.get("num_cells_by_type", {}) if isinstance(module, dict) else {}
            if isinstance(cell_types, dict):
                def count_matching(*prefixes: str) -> int:
                    return sum(number for name, number in cell_types.items() if isinstance(number, int) and any(str(name).upper().lstrip("$").startswith(prefix) for prefix in prefixes))
                result.update({"lut": count_matching("LUT"), "ff": count_matching("FD", "FF"), "bram": count_matching("RAMB", "BRAM"), "dsp": count_matching("DSP"), "memory_bits": module.get("num_memory_bits"), "structural_cells": cell_types})
                return result
        cells = value.get("cells", value.get("resources", value)) if isinstance(value, dict) else {}
        if isinstance(cells, dict):
            normalized = {str(key).lower(): number for key, number in cells.items() if isinstance(number, (int, float))}
            result.update({"lut": normalized.get("lut", normalized.get("lut6")), "ff": normalized.get("ff", normalized.get("fdre")), "bram": normalized.get("bram", normalized.get("ramb36e1")), "dsp": normalized.get("dsp", normalized.get("dsp48e1")), "memory_bits": normalized.get("memory_bits"), "structural_cells": None})
            return result
    except json.JSONDecodeError:
        pass
    patterns = {"lut": r"\b(?:LUT|LUTs)\s*:\s*(\d+)", "ff": r"\b(?:FF|FDRE)\s*:\s*(\d+)", "bram": r"\b(?:BRAM|RAMB(?:18|36))\w*\s*:\s*(\d+)", "dsp": r"\b(?:DSP|DSP48)\w*\s*:\s*(\d+)", "memory_bits": r"\bmemory_bits\s*:\s*(\d+)"}
    for name, pattern in patterns.items():
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        result[name] = int(match.group(1)) if match else None
    result["structural_cells"] = None
    return result


def parse_nextpnr_timing(path: Path) -> dict[str, Any]:
    """Parse a nextpnr timing receipt without discarding its original hash/path."""
    raw = path.read_text(encoding="utf-8")
    result: dict[str, Any] = {"path": str(path), "sha256": sha256_file(path), "critical_paths": []}
    mhz = re.search(r"(?:Max(?:imum)? frequency|Max frequency)\s*[:=]\s*([0-9.]+)\s*MHz", raw, flags=re.IGNORECASE)
    result["max_frequency_mhz"] = float(mhz.group(1)) if mhz else None
    for match in re.finditer(r"(?:critical path|path delay).*?([0-9.]+)\s*ns", raw, flags=re.IGNORECASE):
        result["critical_paths"].append({"delay_ns": float(match.group(1)), "raw": match.group(0)})
    for name, pattern in (("cycles_per_token", r"cycles[_ /-]*per[_ /-]*token\s*[:=]\s*(\d+)"), ("interface_overhead_cycles", r"interface[_ /-]*overhead[_ /-]*cycles\s*[:=]\s*(\d+)")):
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        result[name] = int(match.group(1)) if match else None
    return result


def _read_optional(path: str | None) -> dict[str, Any] | None:
    return load_json(Path(path)) if path else None


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--slice-manifest", type=Path, required=True)
    parser.add_argument("--reference-evidence")
    parser.add_argument("--compiler-evidence")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    contract = load_json(args.contract)
    manifest = load_json(args.slice_manifest)
    if manifest_contract_status(args.contract, manifest) != "aligned":
        result = _base_result(contract, manifest)
        result.update(status="contract_mismatch", reasons=_reason("slice manifest contract SHA-256 differs from supplied frozen contract"))
    else:
        reference = _read_optional(args.reference_evidence) or {"contract": contract}
        compiler = _read_optional(args.compiler_evidence) or {"contract": contract}
        frozen_sha256 = sha256_file(args.contract)
        result = compare(reference, compiler, manifest, frozen_contract=contract, frozen_contract_sha256=frozen_sha256)
    result["inputs"] = {
        "contract": {"path": str(args.contract), "sha256": sha256_file(args.contract)},
        "slice_manifest": {"path": str(args.slice_manifest), "sha256": sha256_file(args.slice_manifest)},
        "reference_evidence": {"path": str(args.reference_evidence), "sha256": sha256_file(Path(args.reference_evidence))} if args.reference_evidence else None,
        "compiler_evidence": {"path": str(args.compiler_evidence), "sha256": sha256_file(Path(args.compiler_evidence))} if args.compiler_evidence else None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
