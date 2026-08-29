#!/usr/bin/env python3
"""Build a fail-closed receipt for a complete TinyStories-1M block comparison.

This is an evidence ledger, not a simulator or a synthesis estimator.  It
records exactly which sides of the one-transformer-block token-step
comparison have authenticated evidence.  A missing compiler RTL, Yosys
report, nextpnr report, or runtime measurement remains ``unavailable``;
numbers are never inferred from an unrelated artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "tinystories-1m-complete-block-comparison-receipt-v1"
SLICE_KIND = "one_transformer_block_token_step"
SLICE_SCHEMA = "tinystories-1m-compiler-slice-manifest-v1"
TRACE_SCHEMA = "tinystories-1m-transformer-block-token-step-trace-v1"
# This is the schema emitted by probe_tinystories_1m_qk_qdq.py.  The probe is
# deliberately only an observation; it cannot satisfy the complete-block
# functional gate below.
FIXED_QK_TRACE_SCHEMA = "tinystories-1m-compiler-qk-qdq-probe-v1"
CHECKPOINTS = (
    ("block.input", (64,)),
    ("block.ln_1.output", (64,)),
    ("block.attention.q.int8", (16, 4)),
    ("block.attention.q.dequant_q16_16", (16, 4)),
    ("block.attention.k.int8", (16, 4)),
    ("block.attention.k.dequant_q16_16", (16, 4)),
    ("block.attention.v", (16, 4)),
    ("block.attention.output", (64,)),
    ("block.residual.attention", (64,)),
    ("block.ln_2.output", (64,)),
    ("block.mlp.fc_in", (256,)),
    ("block.mlp.activation", (256,)),
    ("block.mlp.fc_out", (64,)),
    ("block.output", (64,)),
)
METRIC_KINDS = ("resources", "timing", "memory", "latency", "throughput")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key != "sha256"}
    return {**body, "sha256": canonical_sha256(body)}


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _shape(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return () if math.isfinite(value) else None
    if not isinstance(value, list) or not value:
        return None
    children = [_shape(item) for item in value]
    if any(item is None for item in children) or len(set(children)) != 1:
        return None
    return (len(value),) + children[0]


def _valid_trace(trace: Any, expected_identity: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(trace, dict) or set(trace) != {"schema", "identity", "checkpoints", "sha256"}:
        return False, "trace is missing the authenticated schema, identity, checkpoints, or hash"
    if trace["schema"] != TRACE_SCHEMA or trace["identity"] != expected_identity:
        return False, "trace identity is not bound to the frozen contract and slice"
    body = {key: value for key, value in trace.items() if key != "sha256"}
    if not valid_sha256(trace.get("sha256")) or trace["sha256"] != canonical_sha256(body):
        return False, "trace content hash does not match"
    checkpoints = trace.get("checkpoints")
    expected_names = {name for name, _ in CHECKPOINTS}
    if not isinstance(checkpoints, dict) or set(checkpoints) != expected_names:
        return False, "trace does not cover the complete fixed-q/k block checkpoint order"
    for name, expected_shape in CHECKPOINTS:
        item = checkpoints[name]
        if not isinstance(item, dict) or set(item) != {"shape", "values", "sha256"}:
            return False, f"checkpoint {name!r} is malformed"
        payload = {"shape": item["shape"], "values": item["values"]}
        if item["shape"] != list(expected_shape) or _shape(item["values"]) != expected_shape:
            return False, f"checkpoint {name!r} has the wrong shape"
        if not valid_sha256(item.get("sha256")) or item["sha256"] != canonical_sha256(payload):
            return False, f"checkpoint {name!r} content hash does not match"
    return True, "authenticated complete block trace"


def _side_trace(side: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    trace = side.get("trace")
    ok, reason = _valid_trace(trace, identity)
    if not ok:
        return {"status": "unavailable", "reason": reason}
    tokens = side.get("output_tokens")
    if not isinstance(tokens, list) or not tokens or any(not isinstance(token, int) or isinstance(token, bool) for token in tokens):
        return {"status": "unavailable", "reason": "output token sequence is unavailable or malformed"}
    return {
        "status": "available",
        "reason": "authenticated complete block trace and output tokens",
        "trace_sha256": trace["sha256"],
        "checkpoint_sha256": {name: trace["checkpoints"][name]["sha256"] for name, _ in CHECKPOINTS},
        "output_tokens": tokens,
    }


def _metric_domain_valid(kind: str, value: Any) -> bool:
    """Require a nonempty finite numeric measurement domain.

    Negative slack is meaningful for timing; capacity, memory, latency, and
    throughput measurements cannot be negative.
    """
    numeric: list[float] = []

    def visit(item: Any) -> bool:
        if isinstance(item, bool):
            return True
        if isinstance(item, (int, float)):
            if not math.isfinite(item):
                return False
            numeric.append(float(item))
            return True
        if isinstance(item, str):
            return bool(item)
        if isinstance(item, list):
            return bool(item) and all(visit(child) for child in item)
        if isinstance(item, dict):
            return bool(item) and all(isinstance(key, str) and key and visit(child) for key, child in item.items())
        return False

    if not visit(value) or not numeric:
        return False
    return kind == "timing" or all(number >= 0 for number in numeric)


def _metric_record(side: dict[str, Any], kind: str, *, side_name: str, contract_sha256: str, slice_sha256: str) -> dict[str, Any]:
    value = side.get(kind)
    if value is None:
        return {"status": "unavailable", "reason": f"no {kind} receipt supplied"}
    if not isinstance(value, dict):
        return {"status": "unavailable", "reason": f"{kind} receipt is not an object"}
    required = {"path", "sha256", "measurement_id", "binding", "value"}
    if set(value) != required:
        return {"status": "unavailable", "reason": f"{kind} receipt lacks a value, file hash, or provenance binding"}
    path = Path(value["path"])
    binding = value["binding"]
    expected = {
        "side": side_name,
        "measurement_kind": kind,
        "contract_sha256": contract_sha256,
        "slice_manifest_sha256": slice_sha256,
        "measurement_id": value["measurement_id"],
    }
    if not isinstance(binding, dict) or any(binding.get(key) != expected[key] for key in expected):
        return {"status": "unavailable", "reason": f"{kind} receipt provenance binding is invalid"}
    try:
        digest = sha256_file(path)
    except (OSError, UnicodeError):
        return {"status": "unavailable", "reason": f"{kind} receipt artifact is unreadable"}
    if not valid_sha256(value["sha256"]) or value["sha256"] != digest:
        return {"status": "unavailable", "reason": f"{kind} receipt artifact hash does not match"
        }
    try:
        report = load_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return {"status": "unavailable", "reason": f"{kind} receipt artifact is not canonical JSON evidence"}
    expected_report = {
        "measurement_id": value["measurement_id"],
        "binding": binding,
        "value": value["value"],
    }
    if report != expected_report:
        return {"status": "unavailable", "reason": f"{kind} receipt value is not bound to the hashed artifact"}
    if not _metric_domain_valid(kind, value["value"]):
        return {"status": "unavailable", "reason": f"{kind} receipt value is outside the valid measurement domain"}
    return {"status": "available", "path": str(path), "sha256": digest, "measurement_id": value["measurement_id"], "value": value["value"]}


def _provenance_record(side: dict[str, Any]) -> dict[str, Any]:
    value = side.get("provenance")
    if not isinstance(value, dict):
        return {"status": "unavailable", "reason": "provenance disclosure is absent"}
    required = ("source", "llm_assistance_disclosure", "reference_role")
    if any(not isinstance(value.get(key), str) or not value[key] for key in required):
        return {"status": "unavailable", "reason": "provenance disclosure is incomplete"}
    return {"status": "available", **{key: value[key] for key in required}, "annotations": value.get("annotations", [])}


def build_receipt(
    contract: dict[str, Any],
    contract_sha256: str,
    slice_manifest: dict[str, Any],
    slice_manifest_sha256: str,
    reference: dict[str, Any],
    compiler: dict[str, Any],
    *,
    fixed_qk_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a receipt; unavailable evidence always remains explicitly so."""
    prompt = contract.get("reference", {}).get("prompt_tokens")
    token_index = len(prompt) - 1 if isinstance(prompt, list) and prompt else None
    identity = {
        "model": "TinyStories-1M",
        "contract_sha256": contract_sha256,
        "slice_kind": SLICE_KIND,
        "slice_manifest_sha256": slice_manifest_sha256,
        "block_index": 0,
        "token_index": token_index,
        "input_tokens_sha256": canonical_sha256(prompt) if isinstance(prompt, list) else None,
    }
    functional = {"reference": _side_trace(reference, identity), "compiler": _side_trace(compiler, identity)}
    if functional["reference"]["status"] == functional["compiler"]["status"] == "available":
        checkpoint_mismatch = next(
            (name for name, _ in CHECKPOINTS
             if functional["reference"]["checkpoint_sha256"][name]
             != functional["compiler"]["checkpoint_sha256"][name]),
            None,
        )
        if checkpoint_mismatch is not None:
            functional.update(status="mismatch", first_mismatch={"checkpoint": checkpoint_mismatch, "reason": "reference/compiler checkpoint content differs"})
        elif functional["reference"]["output_tokens"] == functional["compiler"]["output_tokens"]:
            expected_tokens = contract.get("reference", {}).get("tokens")
            if isinstance(expected_tokens, list) and functional["reference"]["output_tokens"] != expected_tokens:
                functional.update(status="mismatch", first_mismatch={"checkpoint": "final_output_tokens", "reason": "output differs from frozen contract reference"})
            else:
                functional.update(status="matched", first_mismatch=None)
        else:
            functional.update(status="mismatch", first_mismatch={"checkpoint": "final_output_tokens"})
    else:
        functional.update(status="unavailable", first_mismatch=None)
    evidence: dict[str, Any] = {"functional": functional}
    for kind in METRIC_KINDS:
        reference_metric = _metric_record(reference, kind, side_name="reference", contract_sha256=contract_sha256, slice_sha256=slice_manifest_sha256)
        compiler_metric = _metric_record(compiler, kind, side_name="compiler", contract_sha256=contract_sha256, slice_sha256=slice_manifest_sha256)
        evidence[kind] = {"reference": reference_metric, "compiler": compiler_metric, "status": "available" if reference_metric["status"] == compiler_metric["status"] == "available" else "unavailable"}
    evidence["provenance"] = {"reference": _provenance_record(reference), "compiler": _provenance_record(compiler)}
    slice_accepted = (
        slice_manifest.get("schema") == SLICE_SCHEMA
        and slice_manifest.get("status") == "accepted"
        and slice_manifest.get("model") == "TinyStories-1M"
        and isinstance(slice_manifest.get("slice"), dict)
        and slice_manifest["slice"].get("kind") == SLICE_KIND
        and slice_manifest["slice"].get("status") == "accepted"
    )
    complete = slice_accepted and functional["status"] == "matched" and all(evidence[kind]["status"] == "available" for kind in METRIC_KINDS) and all(evidence["provenance"][side]["status"] == "available" for side in ("reference", "compiler"))
    reasons = []
    if not slice_accepted:
        reasons.append("slice manifest schema, model, kind, or accepted status is invalid")
    if functional["status"] != "matched":
        reasons.append("complete reference/compiler functional traces and matching output are unavailable")
    reasons.extend(f"{kind} evidence is unavailable or invalid on one or both sides" for kind in METRIC_KINDS if evidence[kind]["status"] != "available")
    if evidence["provenance"]["reference"]["status"] != "available" or evidence["provenance"]["compiler"]["status"] != "available":
        reasons.append("both sides lack complete provenance disclosure")
    observations = {"fixed_qk_probe": None}
    if isinstance(fixed_qk_probe, dict):
        observations["fixed_qk_probe"] = {
            "status": "available" if fixed_qk_probe.get("schema") == FIXED_QK_TRACE_SCHEMA else "unavailable",
            "schema": fixed_qk_probe.get("schema"),
            "claims": fixed_qk_probe.get("claims"),
            "note": "probe boundary evidence; not a complete compiler/reference equivalence result",
        }
    return seal({
        "schema": SCHEMA,
        "status": "complete" if complete else "incomplete",
        "model": "TinyStories-1M",
        "slice": {"kind": SLICE_KIND, "manifest_status": slice_manifest.get("status"), "manifest_sha256": slice_manifest_sha256},
        "identity": identity,
        "evidence": evidence,
        "observations": observations,
        "claims": {"functional_equivalence": complete, "resource_comparison": complete, "timing_comparison": complete, "optimization": False, "rtl_equivalence": False, "hardware_inference": False},
        "blocking_reasons": reasons,
    })


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON constant: {value}")),
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--slice-manifest", type=Path, required=True)
    parser.add_argument("--reference-evidence", type=Path)
    parser.add_argument("--compiler-evidence", type=Path)
    parser.add_argument("--fixed-qk-probe", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    contract = load_json(args.contract)
    manifest = load_json(args.slice_manifest)
    contract_digest = sha256_file(args.contract)
    manifest_digest = sha256_file(args.slice_manifest)
    reference = load_json(args.reference_evidence) if args.reference_evidence else {}
    compiler = load_json(args.compiler_evidence) if args.compiler_evidence else {}
    probe = load_json(args.fixed_qk_probe) if args.fixed_qk_probe else None
    receipt = build_receipt(contract, contract_digest, manifest, manifest_digest, reference, compiler, fixed_qk_probe=probe)
    def input_record(path: Path | None) -> dict[str, str] | None:
        return {"path": str(path), "sha256": sha256_file(path)} if path is not None else None

    receipt["inputs"] = {
        "contract": input_record(args.contract),
        "slice_manifest": input_record(args.slice_manifest),
        "reference_evidence": input_record(args.reference_evidence),
        "compiler_evidence": input_record(args.compiler_evidence),
        "fixed_qk_probe": input_record(args.fixed_qk_probe),
    }
    receipt = seal(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
