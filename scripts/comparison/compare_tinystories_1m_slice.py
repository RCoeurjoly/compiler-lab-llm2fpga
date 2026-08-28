#!/usr/bin/env python3
"""Fail-closed comparison of a TinyStories-1M compiler slice and reference.

The harness deliberately separates evidence collection from judgement.  It
never calculates an efficiency delta until the two runs have the same frozen
contract, exact named checkpoint tensors, and final token sequence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "tinystories-1m-slice-comparison-v1"
SLICE_SCHEMA = "tinystories-1m-compiler-slice-manifest-v1"
SLICE_KIND = "one_transformer_block_token_step"
TRACE_SCHEMA = "tinystories-1m-transformer-block-token-step-trace-v1"
MAX_SLICE_MODULES = 4096
RESOURCE_FIELDS = ("lut", "ff", "bram", "dsp", "memory_bits")
MEASUREMENT_BINDING_FIELDS = (
    "side",
    "measurement_kind",
    "contract_sha256",
    "slice_manifest_sha256",
    "artifact_path",
    "artifact_sha256",
    "measurement_id",
)
CHECKPOINT_SHAPES = {
    "block.input": (64,),
    "block.ln_1.output": (64,),
    "block.attention.q": (16, 4),
    "block.attention.k": (16, 4),
    "block.attention.v": (16, 4),
    "block.attention.output": (64,),
    "block.residual.attention": (64,),
    "block.ln_2.output": (64,),
    "block.mlp.fc_in": (256,),
    "block.mlp.activation": (256,),
    "block.mlp.fc_out": (64,),
    "block.output": (64,),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _path_matches_hash(path_value: Any, digest: Any) -> bool:
    if not isinstance(path_value, str) or not path_value or not _valid_sha256(digest):
        return False
    path = Path(path_value)
    try:
        return path.is_file() and sha256_file(path) == digest
    except OSError:
        return False


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


def _tensor_shape(value: Any) -> tuple[int, ...] | None:
    """Return a rectangular numeric tensor shape, or None for invalid data."""
    if isinstance(value, bool) or (not isinstance(value, (int, float)) and not isinstance(value, list)):
        return None
    if isinstance(value, (int, float)):
        return () if math.isfinite(value) else None
    if not value:
        return None
    child_shapes = [_tensor_shape(item) for item in value]
    if any(shape is None for shape in child_shapes) or len(set(child_shapes)) != 1:
        return None
    return (len(value),) + child_shapes[0]


def _output_tokens_are_valid(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(token, int) and not isinstance(token, bool) and 0 <= token <= 0xFFFF for token in value)


def _manifest_contract_identity(contract: dict[str, Any]) -> dict[str, Any] | None:
    model = contract.get("model")
    package = contract.get("package")
    if not isinstance(model, dict) or not isinstance(package, dict):
        return None
    model_keys = ("name", "source_model_id", "source_revision")
    package_keys = ("sha256", "manifest_sha256")
    if any(not isinstance(model.get(key), str) or not model[key] for key in model_keys):
        return None
    if any(not _valid_sha256(package.get(key)) for key in package_keys):
        return None
    return {
        "model": {key: model[key] for key in model_keys},
        "package": {key: package[key] for key in package_keys},
    }


def _validate_ready_slice_manifest(
    manifest: dict[str, Any], contract: dict[str, Any], contract_path: Path, contract_sha256: str
) -> list[str]:
    reasons: list[str] = []
    expected_identity = _manifest_contract_identity(contract)
    if manifest.get("schema") != SLICE_SCHEMA:
        reasons.append("slice manifest schema is not the Task 2 schema")
    if manifest.get("status") != "ready":
        reasons.append(f"slice manifest is not ready: {manifest.get('status')}")
    contract_model = contract.get("model")
    contract_model_name = contract_model.get("name") if isinstance(contract_model, dict) else None
    if manifest.get("model") != "TinyStories-1M" or manifest.get("model") != contract_model_name:
        reasons.append("slice manifest model is not the frozen TinyStories-1M model")
    binding = manifest.get("contract")
    bound_contract_path = binding.get("path") if isinstance(binding, dict) else None
    contract_path_matches = (
        isinstance(bound_contract_path, str)
        and bool(bound_contract_path)
        and Path(bound_contract_path).resolve() == contract_path.resolve()
    )
    if not isinstance(binding, dict) or not contract_path_matches or binding.get("sha256") != contract_sha256 or binding.get("identity") != expected_identity:
        reasons.append("slice manifest is not bound to the frozen contract identity")

    metadata = manifest.get("source_metadata")
    if not isinstance(metadata, dict) or not _path_matches_hash(metadata.get("path"), metadata.get("sha256")):
        reasons.append("slice source metadata is absent or its content hash does not match")
    else:
        try:
            metadata_value = load_json(Path(metadata["path"]))
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            metadata_value = {}
        if metadata_value.get("contract_identity") != expected_identity:
            reasons.append("slice source metadata does not bind the frozen contract identity")

    slice_value = manifest.get("slice")
    if not isinstance(slice_value, dict) or slice_value.get("kind") != SLICE_KIND:
        reasons.append("slice kind is not one complete transformer-block token-step")
        return reasons
    closure = slice_value.get("dependency_closure")
    artifacts = slice_value.get("artifacts")
    anchor = slice_value.get("anchor_module")
    if (
        not isinstance(closure, list)
        or not closure
        or len(closure) > MAX_SLICE_MODULES
        or any(not isinstance(name, str) or not name for name in closure)
        or len(set(closure)) != len(closure)
        or not isinstance(anchor, str)
        or anchor not in closure
    ):
        reasons.append("slice dependency closure is empty, malformed, or unbounded")
        return reasons
    if not isinstance(artifacts, list) or len(artifacts) != len(closure):
        reasons.append("slice artifacts do not exactly cover the dependency closure")
        return reasons
    modules: list[Any] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            reasons.append("slice artifact record is malformed")
            continue
        modules.append(artifact.get("module"))
        if not _path_matches_hash(artifact.get("source"), artifact.get("source_sha256")):
            reasons.append(f"slice source hash is unauthenticated for module {artifact.get('module')!r}")
        if not _path_matches_hash(artifact.get("extracted"), artifact.get("sha256")):
            reasons.append(f"slice artifact hash is unauthenticated for module {artifact.get('module')!r}")
    if modules != closure:
        reasons.append("slice artifact modules do not exactly match the ordered dependency closure")
    if reasons:
        return reasons

    # A collection of self-consistent hashes is not proof that the files are
    # the RTL slice named by the manifest.  Reuse Task 2's parser and closure
    # algorithm to derive the subject again from the authenticated sources.
    extractor_path = Path(__file__).with_name("extract_tinystories_1m_block_slice.py")
    spec = importlib.util.spec_from_file_location("tinystories_1m_slice_extractor_for_validation", extractor_path)
    if spec is None or spec.loader is None:
        return ["Task 2 RTL parser is unavailable"]
    extractor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extractor)
    source_paths = list(dict.fromkeys(Path(artifact["source"]) for artifact in artifacts))
    try:
        parsed_modules = extractor.parse_modules(source_paths)
        parsed_anchor = extractor.select_anchor(parsed_modules)
        parsed_closure = extractor.dependency_closure(parsed_anchor, parsed_modules)
    except (OSError, UnicodeError, extractor.ExtractionError) as error:
        return [f"slice sources do not parse as a bounded Task 2 RTL module closure: {error}"]
    if parsed_anchor != anchor:
        reasons.append("slice anchor module does not match the anchor derived from RTL")
    if parsed_closure != closure:
        reasons.append("slice dependency closure does not match the closure derived from RTL")
    for artifact in artifacts:
        module_name = artifact["module"]
        parsed_module = parsed_modules.get(module_name)
        if parsed_module is None:
            reasons.append(f"slice module {module_name!r} is absent from its authenticated RTL source")
            continue
        try:
            extracted_text = Path(artifact["extracted"]).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            reasons.append(f"slice extracted content is unreadable for module {module_name!r}")
            continue
        expected_text = parsed_module[1].rstrip() + "\n"
        if extracted_text != expected_text:
            reasons.append(f"slice extracted module content differs from Task 2 extraction for module {module_name!r}")
    return reasons


def _expected_trace_identity(
    contract: dict[str, Any], contract_sha256: str, manifest: dict[str, Any]
) -> dict[str, Any] | None:
    reference = contract.get("reference")
    prompt_tokens = reference.get("prompt_tokens") if isinstance(reference, dict) else None
    if not _output_tokens_are_valid(prompt_tokens):
        return None
    return {
        "model": "TinyStories-1M",
        "contract_sha256": contract_sha256,
        "slice_kind": SLICE_KIND,
        "slice_manifest_sha256": canonical_sha256(manifest),
        "block_index": 0,
        "token_index": len(prompt_tokens) - 1,
        "input_tokens_sha256": canonical_sha256(prompt_tokens),
    }


def _validate_trace(
    side: dict[str, Any], label: str, expected_identity: dict[str, Any] | None
) -> list[str]:
    trace = side.get("trace")
    if not isinstance(trace, dict) or set(trace) != {"schema", "identity", "checkpoints", "sha256"}:
        return [f"{label}.trace unavailable or malformed"]
    if trace.get("schema") != TRACE_SCHEMA or trace.get("identity") != expected_identity:
        return [f"{label}.trace identity is not bound to the complete frozen token-step slice"]
    supplied_trace_sha = trace.get("sha256")
    hashed_trace = {key: value for key, value in trace.items() if key != "sha256"}
    if not _valid_sha256(supplied_trace_sha) or supplied_trace_sha != canonical_sha256(hashed_trace):
        return [f"{label}.trace content hash does not match"]
    checkpoints = trace.get("checkpoints")
    if not isinstance(checkpoints, dict) or set(checkpoints) != set(CHECKPOINT_SHAPES):
        return [f"{label}.trace checkpoints do not exactly cover the required token-step schema"]
    values: dict[str, Any] = {}
    for name, expected_shape in CHECKPOINT_SHAPES.items():
        checkpoint = checkpoints.get(name)
        if not isinstance(checkpoint, dict) or set(checkpoint) != {"shape", "values", "sha256"}:
            return [f"{label}.trace checkpoint {name!r} is malformed"]
        shape = checkpoint.get("shape")
        value = checkpoint.get("values")
        payload = {"shape": shape, "values": value}
        if (
            shape != list(expected_shape)
            or _tensor_shape(value) != expected_shape
            or not _valid_sha256(checkpoint.get("sha256"))
            or checkpoint["sha256"] != canonical_sha256(payload)
        ):
            return [f"{label}.trace checkpoint {name!r} shape, value, or content hash is invalid"]
        values[name] = value
    if side.get("checkpoint_tensors") != values:
        return [f"{label}.checkpoint_tensors are not bound to the authenticated trace"]
    return []


def _validate_evidence(
    side: dict[str, Any], label: str, expected_trace_identity: dict[str, Any] | None
) -> list[str]:
    missing: list[str] = []
    missing.extend(_validate_trace(side, label, expected_trace_identity))
    if not _output_tokens_are_valid(side.get("output_tokens")):
        missing.append(f"{label}.output_tokens unavailable or malformed")
    return missing


def _first_checkpoint_mismatch(reference: dict[str, Any], compiler: dict[str, Any]) -> dict[str, Any] | None:
    ref = reference["trace"]["checkpoints"]
    comp = compiler["trace"]["checkpoints"]
    for name in CHECKPOINT_SHAPES:
        if ref.get(name) != comp.get(name):
            return {"checkpoint": name, "reference": ref.get(name, {}).get("values"), "compiler": comp.get(name, {}).get("values")}
    return None


def _report_provenance_is_complete(
    report: dict[str, Any],
    parsed: dict[str, Any],
    *,
    side: str,
    measurement_kind: str,
    contract_sha256: str,
    slice_manifest_sha256: str,
) -> bool:
    if not (
        isinstance(report.get("path"), str)
        and bool(report["path"])
        and _valid_sha256(report.get("sha256"))
        and isinstance(report.get("measurement_id"), str)
        and bool(report["measurement_id"])
    ):
        return False
    expected = {
        "side": side,
        "measurement_kind": measurement_kind,
        "contract_sha256": contract_sha256,
        "slice_manifest_sha256": slice_manifest_sha256,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        return False
    if any(parsed.get(key) != report.get(key) for key in MEASUREMENT_BINDING_FIELDS):
        return False
    return (
        _path_matches_hash(report["path"], report["sha256"])
        and _path_matches_hash(report.get("artifact_path"), report.get("artifact_sha256"))
    )


def _resource_measurement_is_valid(
    report: dict[str, Any], *, side: str, contract_sha256: str, slice_manifest_sha256: str
) -> bool:
    if not isinstance(report.get("path"), str) or not report["path"]:
        return False
    if any(not isinstance(report.get(field), int) or isinstance(report.get(field), bool) or report[field] < 0 for field in RESOURCE_FIELDS):
        return False
    try:
        parsed = parse_yosys_statistics(Path(report["path"]))
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    if not _report_provenance_is_complete(
        report,
        parsed,
        side=side,
        measurement_kind="resources",
        contract_sha256=contract_sha256,
        slice_manifest_sha256=slice_manifest_sha256,
    ):
        return False
    return all(parsed.get(field) == report[field] for field in RESOURCE_FIELDS)


def _resource_deltas(
    reference: dict[str, Any], compiler: dict[str, Any], *, contract_sha256: str, slice_manifest_sha256: str
) -> dict[str, Any] | None:
    ref = reference.get("resources")
    comp = compiler.get("resources")
    if (
        not isinstance(ref, dict)
        or not isinstance(comp, dict)
        or not _resource_measurement_is_valid(ref, side="reference", contract_sha256=contract_sha256, slice_manifest_sha256=slice_manifest_sha256)
        or not _resource_measurement_is_valid(comp, side="compiler", contract_sha256=contract_sha256, slice_manifest_sha256=slice_manifest_sha256)
    ):
        return None
    provenance_fields = ("path", "sha256", *MEASUREMENT_BINDING_FIELDS)
    result: dict[str, Any] = {"reference": {field: ref[field] for field in RESOURCE_FIELDS}, "compiler": {field: comp[field] for field in RESOURCE_FIELDS}, "reports": {"reference": {field: ref[field] for field in provenance_fields}, "compiler": {field: comp[field] for field in provenance_fields}}}
    for field in RESOURCE_FIELDS:
        result[f"{field}_delta"] = comp[field] - ref[field]
    return result


def _timing_deltas(
    reference: dict[str, Any], compiler: dict[str, Any], *, contract_sha256: str, slice_manifest_sha256: str
) -> dict[str, Any] | None:
    ref = reference.get("timing")
    comp = compiler.get("timing")
    required = ("max_frequency_mhz", "critical_paths", "cycles_per_token", "interface_overhead_cycles")
    if not isinstance(ref, dict) or not isinstance(comp, dict) or any(field not in ref or field not in comp for field in required):
        return None
    if not _timing_measurement_is_valid(ref, side="reference", contract_sha256=contract_sha256, slice_manifest_sha256=slice_manifest_sha256) or not _timing_measurement_is_valid(comp, side="compiler", contract_sha256=contract_sha256, slice_manifest_sha256=slice_manifest_sha256):
        return None
    provenance_fields = ("path", "sha256", *MEASUREMENT_BINDING_FIELDS)
    return {
        "max_frequency_mhz": {"reference": ref["max_frequency_mhz"], "compiler": comp["max_frequency_mhz"], "delta": comp["max_frequency_mhz"] - ref["max_frequency_mhz"]},
        "critical_paths": {"reference": ref["critical_paths"], "compiler": comp["critical_paths"]},
        "clock_domains": {"reference": ref["clock_domains"], "compiler": comp["clock_domains"]},
        "cycles_per_token": {"reference": ref["cycles_per_token"], "compiler": comp["cycles_per_token"]},
        "cycles_per_token_delta": comp["cycles_per_token"] - ref["cycles_per_token"],
        "interface_overhead_cycles": {"reference": ref["interface_overhead_cycles"], "compiler": comp["interface_overhead_cycles"]},
        "reports": {"reference": {field: ref[field] for field in provenance_fields}, "compiler": {field: comp[field] for field in provenance_fields}},
    }


def _positive_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _critical_path_records(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not value:
        return None
    records: list[dict[str, Any]] = []
    required = {"clock_domain", "from", "to", "delay_ns"}
    for path in value:
        if not isinstance(path, dict) or set(path) != required:
            return None
        if any(not isinstance(path.get(field), str) or not path[field] for field in ("clock_domain", "from", "to")):
            return None
        if not _positive_finite_number(path.get("delay_ns")):
            return None
        records.append(dict(path))
    return records


def _clock_domain_records(value: Any, critical_paths: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not value:
        return None
    records: list[dict[str, Any]] = []
    names: set[str] = set()
    for clock in value:
        if not isinstance(clock, dict) or set(clock) != {"name", "max_frequency_mhz"}:
            return None
        name = clock.get("name")
        frequency = clock.get("max_frequency_mhz")
        if not isinstance(name, str) or not name or name in names or not _positive_finite_number(frequency):
            return None
        names.add(name)
        records.append(dict(clock))
    path_domains = {path["clock_domain"] for path in critical_paths}
    if path_domains != names:
        return None
    return records


def _timing_measurement_is_valid(
    report: dict[str, Any], *, side: str, contract_sha256: str, slice_manifest_sha256: str
) -> bool:
    if not isinstance(report.get("path"), str) or not report["path"] or not _positive_finite_number(report.get("max_frequency_mhz")):
        return False
    cycles = report.get("cycles_per_token")
    overhead = report.get("interface_overhead_cycles")
    critical_paths = _critical_path_records(report.get("critical_paths"))
    clock_domains = _clock_domain_records(report.get("clock_domains"), critical_paths or [])
    if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles <= 0:
        return False
    if not isinstance(overhead, int) or isinstance(overhead, bool) or overhead < 0 or overhead > cycles:
        return False
    if critical_paths is None or clock_domains is None:
        return False
    if report["max_frequency_mhz"] != min(clock["max_frequency_mhz"] for clock in clock_domains):
        return False
    try:
        parsed = parse_nextpnr_timing(Path(report["path"]))
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    if not _report_provenance_is_complete(
        report,
        parsed,
        side=side,
        measurement_kind="timing",
        contract_sha256=contract_sha256,
        slice_manifest_sha256=slice_manifest_sha256,
    ):
        return False
    return (
        parsed.get("max_frequency_mhz") == report["max_frequency_mhz"]
        and parsed.get("critical_paths") == critical_paths
        and parsed.get("clock_domains") == clock_domains
        and parsed.get("cycles_per_token") == cycles
        and parsed.get("interface_overhead_cycles") == overhead
        and parsed.get("measurement_id") == report.get("measurement_id")
    )


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
            "measurement_id": annotation["measurement_id"],
            "evidence": "compiler provenance annotation and measured resource delta",
        })
    return sorted(result, key=lambda item: (-item["measured_delta"], item["module"]))


def compare(reference: dict[str, Any], compiler: dict[str, Any], slice_manifest: dict[str, Any], *, frozen_contract: dict[str, Any], frozen_contract_path: Path, frozen_contract_sha256: str, quantization: str | None = None) -> dict[str, Any]:
    """Compare two explicit evidence objects, returning a fail-closed result."""
    contract = reference.get("contract", {})
    result = _base_result(contract, slice_manifest)
    if not frozen_contract_path.is_file() or sha256_file(frozen_contract_path) != frozen_contract_sha256 or not _same_contract(load_json(frozen_contract_path), frozen_contract):
        result.update(status="contract_mismatch", reasons=_reason("supplied frozen contract content or SHA-256 does not match its file"))
        return result
    if slice_manifest.get("contract", {}).get("sha256") != frozen_contract_sha256:
        result.update(status="contract_mismatch", reasons=_reason("slice manifest contract SHA-256 differs from supplied frozen Task 1 contract"))
        return result
    manifest_reasons = _validate_ready_slice_manifest(slice_manifest, frozen_contract, frozen_contract_path, frozen_contract_sha256)
    if manifest_reasons:
        result["reasons"] = manifest_reasons
        return result
    if not _same_contract(contract, compiler.get("contract", {})):
        result.update(status="contract_mismatch", reasons=_reason("compiler contract identity or quantization differs from reference"))
        return result
    if quantization is not None and quantization != contract.get("quantization"):
        result.update(status="contract_mismatch", reasons=_reason("requested quantization differs from frozen contract quantization"))
        return result
    trace_identity = _expected_trace_identity(frozen_contract, frozen_contract_sha256, slice_manifest)
    missing = _validate_evidence(reference, "reference", trace_identity) + _validate_evidence(compiler, "compiler", trace_identity)
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
    expected_tokens = frozen_contract.get("reference", {}).get("tokens")
    if not isinstance(expected_tokens, list) or reference["output_tokens"] != expected_tokens:
        result.update(status="functional_mismatch", reasons=_reason("final output tokens differ from the frozen Task 1 reference"))
        result["functional"] = {"checkpoint_status": "matched", "output_status": "mismatch", "first_mismatch": {"checkpoint": "final_output_tokens", "reference": expected_tokens, "compiler": compiler["output_tokens"]}}
        return result
    result["functional"] = {"checkpoint_status": "matched", "output_status": "matched", "first_mismatch": None}
    measurement_reports = [
        side.get(kind)
        for side in (reference, compiler)
        for kind in ("resources", "timing")
    ]
    if any(not isinstance(report, dict) for report in measurement_reports):
        result["reasons"] = ["resource or timing evidence is unavailable or malformed"]
        return result
    measurement_ids = [report.get("measurement_id") for report in measurement_reports]
    if any(not isinstance(identity, str) or not identity for identity in measurement_ids) or len(set(measurement_ids)) != len(measurement_ids):
        result["reasons"] = ["resource and timing measurement identities must be present and distinct across both sides"]
        return result
    slice_manifest_sha256 = canonical_sha256(slice_manifest)
    resources = _resource_deltas(
        reference,
        compiler,
        contract_sha256=frozen_contract_sha256,
        slice_manifest_sha256=slice_manifest_sha256,
    )
    timing = _timing_deltas(
        reference,
        compiler,
        contract_sha256=frozen_contract_sha256,
        slice_manifest_sha256=slice_manifest_sha256,
    )
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
        evidence_binding = value.get("evidence_binding") if isinstance(value, dict) else None
        if isinstance(evidence_binding, dict):
            result.update({key: evidence_binding.get(key) for key in MEASUREMENT_BINDING_FIELDS})
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
    result: dict[str, Any] = {"path": str(path), "sha256": sha256_file(path), "critical_paths": [], "clock_domains": []}
    mhz = re.search(r"(?:Max(?:imum)? frequency|Max frequency)\s*[:=]\s*([0-9.]+)\s*MHz", raw, flags=re.IGNORECASE)
    result["max_frequency_mhz"] = float(mhz.group(1)) if mhz else None
    for match in re.finditer(r"clock domain ['\"]([^'\"]+)['\"] max frequency\s*[:=]\s*([0-9.]+)\s*MHz", raw, flags=re.IGNORECASE):
        result["clock_domains"].append({"name": match.group(1), "max_frequency_mhz": float(match.group(2))})
    path_pattern = r"critical path domain=['\"]([^'\"]+)['\"] from=['\"]([^'\"]+)['\"] to=['\"]([^'\"]+)['\"] delay\s*=\s*([0-9.]+)\s*ns"
    for match in re.finditer(path_pattern, raw, flags=re.IGNORECASE):
        result["critical_paths"].append({"clock_domain": match.group(1), "from": match.group(2), "to": match.group(3), "delay_ns": float(match.group(4))})
    for name, pattern in (("cycles_per_token", r"cycles[_ /-]*per[_ /-]*token\s*[:=]\s*(\d+)"), ("interface_overhead_cycles", r"interface[_ /-]*overhead[_ /-]*cycles\s*[:=]\s*(\d+)")):
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        result[name] = int(match.group(1)) if match else None
    token_patterns = {
        "side": r"^side\s*[:=]\s*([A-Za-z0-9_.:-]+)\s*$",
        "measurement_kind": r"^measurement_kind\s*[:=]\s*([A-Za-z0-9_.:-]+)\s*$",
        "contract_sha256": r"^contract_sha256\s*[:=]\s*([0-9a-f]{64})\s*$",
        "slice_manifest_sha256": r"^slice_manifest_sha256\s*[:=]\s*([0-9a-f]{64})\s*$",
        "artifact_path": r"^artifact_path\s*[:=]\s*(\S(?:.*\S)?)\s*$",
        "artifact_sha256": r"^artifact_sha256\s*[:=]\s*([0-9a-f]{64})\s*$",
        "measurement_id": r"^measurement_id\s*[:=]\s*([A-Za-z0-9_.:-]+)\s*$",
    }
    for name, pattern in token_patterns.items():
        match = re.search(pattern, raw, flags=re.MULTILINE)
        result[name] = match.group(1) if match else None
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
    elif manifest.get("status") == "contract_mismatch":
        failure = manifest.get("failure")
        detail = failure.get("reason") if isinstance(failure, dict) and isinstance(failure.get("reason"), str) else "source artifact identity differs from the frozen contract"
        result = _base_result(contract, manifest)
        result.update(status="contract_mismatch", reasons=_reason(f"compiler artifact metadata does not match the frozen contract: {detail}"))
    else:
        reference = _read_optional(args.reference_evidence) or {"contract": contract}
        compiler = _read_optional(args.compiler_evidence) or {"contract": contract}
        frozen_sha256 = sha256_file(args.contract)
        result = compare(reference, compiler, manifest, frozen_contract=contract, frozen_contract_path=args.contract, frozen_contract_sha256=frozen_sha256)
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
