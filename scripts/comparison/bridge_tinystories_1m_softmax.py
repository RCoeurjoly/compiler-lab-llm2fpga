#!/usr/bin/env python3
"""Bridge the authenticated TinyStories-1M attention softmax boundary.

This is deliberately a *boundary* bridge, not an RTL implementation.  It
accepts a package-aware SCF/MLIR textual artifact only when the artifact
contains the complete stabilized attention pattern (row-max subtraction,
exponential, reduction, normalization, and causal-prefix evidence).  The
result is a custom operation with the recovered kev-gpt arithmetic contract;
all hashes are carried into the IR and report.  A lone ``math.exp`` is never
enough to create a bridge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
SOFTMAX_DIAGNOSTIC_SHA256 = "ef052961445168cc8e05b2522ce3cd05e11cd21235ab876907d6a4c6344a05ca"
CUSTOM_OP = "llm2fpga.attention_softmax_fixed"


class SoftmaxBridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SoftmaxBridgeError(code, message)


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise SoftmaxBridgeError("artifact_missing", f"{path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise SoftmaxBridgeError("noncanonical_value", str(error)) from error
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SoftmaxBridgeError("invalid_json", f"{label}: {error}") from error
    require(isinstance(value, dict), "invalid_json", f"{label} must be an object")
    return value


def load_evidence(contract_path: Path, diagnostic_path: Path) -> dict[str, Any]:
    """Authenticate the frozen model/package identity and recovered contract."""

    require(sha256_file(contract_path) == CONTRACT_SHA256, "contract_identity_mismatch", str(contract_path))
    require(sha256_file(diagnostic_path) == SOFTMAX_DIAGNOSTIC_SHA256, "diagnostic_identity_mismatch", str(diagnostic_path))
    contract = _load_json(contract_path, "contract")
    diagnostic = _load_json(diagnostic_path, "softmax diagnostic")
    require(contract.get("model", {}).get("name") == "TinyStories-1M", "contract_model_mismatch", "model name")
    require(contract.get("model", {}).get("source_revision") == "ac533fb8b4f69c71894bf96badfe11e6294d9fcf", "contract_model_mismatch", "source revision")
    package = contract.get("package")
    require(isinstance(package, dict), "contract_package_missing", "package")
    for key in ("manifest_sha256", "sha256"):
        require(isinstance(package.get(key), str) and len(package[key]) == 64, "contract_package_mismatch", key)
    reference = diagnostic.get("reference", {})
    recovered = reference.get("contract") if isinstance(reference, dict) else None
    require(isinstance(recovered, dict), "softmax_contract_missing", "diagnostic reference contract")
    expected = {
        "score": {"post_shift": 24, "output_encoding": "signed 32-bit fixed point with 8 fractional bits", "causal_mask": "implicit prefix time_index <= position; no mask port"},
        "exponential": {"lut_entries": 4096, "output_encoding": "unsigned 21-bit fixed point with 20 fractional bits (Q1.20)", "zero_delta_value": 1048576},
        "normalization": {"sum_bits": 64, "division": "unsigned restoring magnitude, sign reapplied; truncates toward zero"},
    }
    for section, fields in expected.items():
        actual = recovered.get(section)
        require(isinstance(actual, dict), "softmax_contract_mismatch", section)
        for key, value in fields.items():
            require(actual.get(key) == value, "softmax_contract_mismatch", f"{section}.{key}")
    return {
        "contract_sha256": CONTRACT_SHA256,
        "diagnostic_sha256": SOFTMAX_DIAGNOSTIC_SHA256,
        "package_manifest_sha256": package["manifest_sha256"],
        "package_weights_sha256": package["sha256"],
        "package_scales_sha256": package.get("files", {}).get("scales.bin"),
        "package_calibration_ids_sha256": package.get("files", {}).get("calibration_ids.bin"),
        "model_revision": contract["model"]["source_revision"],
        "contract": recovered,
    }


def _pattern_evidence(graph: str) -> dict[str, Any]:
    """Require all semantic edges around the exact stabilized softmax site."""

    checks = {
        "stabilization": r"(?:subf|subi|sub)\b[^\n]*(?:score|scores)[^\n]*(?:max|row_max)|score\s*-\s*row_max",
        "exp": r"math\.exp",
        "exp_store": r"(?:store|memref\.store)[^\n]*exp",
        "sum": r"(?:addf|addi|add)\b[^\n]*(?:sum|old_sum|exp_sum)",
        "division": r"(?:divf|divi|div|division)[^\n]*(?:exp|sum|prob)",
        "causal": r"(?:time_index|position)[^\n]*(?:<=|le|prefix)|causal",
    }
    missing = [label for label, pattern in checks.items() if re.search(pattern, graph, re.IGNORECASE) is None]
    require(not missing, "pattern_not_proven", "missing semantic edges: " + ", ".join(missing))
    exp_sites = list(re.finditer(r"math\.exp", graph))
    require(len(exp_sites) == 1, "pattern_not_proven", f"expected one stabilized exp site, found {len(exp_sites)}")
    line = graph[: exp_sites[0].start()].count("\n") + 1
    return {"exp_site_line": line, "matched_edges": list(checks)}


def bridge_graph(graph: str, evidence: Mapping[str, Any], *, source_name: str) -> dict[str, Any]:
    require(isinstance(graph, str) and graph, "graph_missing", source_name)
    require(set(evidence) >= {"contract_sha256", "diagnostic_sha256", "package_manifest_sha256", "package_weights_sha256"}, "evidence_missing", "package/contract hashes")
    pattern = _pattern_evidence(graph)
    attributes = {
        "score_width": 32,
        "score_fraction_bits": 8,
        "score_post_shift": 24,
        "causal_mask": "prefix_time_index_le_position",
        "exp_lut_entries": 4096,
        "exp_width": 21,
        "exp_fraction_bits": 20,
        "exp_zero_delta_value": 1048576,
        "sum_width": 64,
        "normalization": "unsigned_restoring_magnitude_signed_reapply",
        "division_rounding": "truncation_toward_zero",
    }
    descriptor = {
        "schema": "llm2fpga-tinystories-1m-softmax-op-v1",
        "op": CUSTOM_OP,
        "operand_types": ["tensor<16x32xi32>", "i32"],
        "result_types": ["tensor<16x32xi32>"],
        "attributes": attributes,
        "source": {"artifact": source_name, "sha256": hashlib.sha256(graph.encode()).hexdigest(), **pattern},
        "evidence": {key: evidence[key] for key in ("contract_sha256", "diagnostic_sha256", "package_manifest_sha256", "package_weights_sha256", "package_scales_sha256", "package_calibration_ids_sha256", "model_revision")},
    }
    descriptor["sha256"] = canonical_sha256({key: value for key, value in descriptor.items() if key != "sha256"})
    return descriptor


def render_custom_op(descriptor: Mapping[str, Any]) -> str:
    require(descriptor.get("op") == CUSTOM_OP, "descriptor_mismatch", "operation")
    require(descriptor.get("sha256") == canonical_sha256({key: value for key, value in descriptor.items() if key != "sha256"}), "descriptor_hash_mismatch", "descriptor")
    attrs = descriptor["attributes"]
    manifest = ", ".join(f'{key} = "{value}"' for key, value in descriptor["evidence"].items())
    rendered_attrs = ", ".join(
        f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value} : i64"
        for key, value in attrs.items()
    )
    return (
        f"module attributes {{llm2fpga.bridge_manifest = {{{manifest}}}}} {{\n"
        "  func.func @tinystories_1m_attention_softmax(%scores: tensor<16x32xi32>, %position: i32) -> tensor<16x32xi32> {\n"
        f'    %0 = "{CUSTOM_OP}"(%scores, %position) <{{{rendered_attrs}}}> : (tensor<16x32xi32>, i32) -> tensor<16x32xi32>\n'
        "    return %0 : tensor<16x32xi32>\n  }\n}\n"
    )


def make_report(descriptor: Mapping[str, Any], graph: str, mlir: str) -> dict[str, Any]:
    require(mlir == render_custom_op(descriptor), "rendered_mlir_mismatch", "custom operation")
    return {
        "schema": "tinystories-1m-softmax-compiler-bridge-v1",
        "model": "TinyStories-1M",
        "status": "unsupported",
        "alignment_status": "custom_op_emitted_backend_unverified",
        "board_authenticated": False,
        "source": descriptor["source"],
        "custom_op": dict(descriptor),
        "compiler_artifacts": {"mlir": {"kind": "custom_op_ir", "sha256": hashlib.sha256(mlir.encode()).hexdigest()}, "systemverilog": None, "rtlil": None},
        "first_unsupported_operation": {"target": CUSTOM_OP, "code": "softmax_backend_lowering_not_implemented", "pipeline_stage": "custom_op_to_linalg_or_calyx", "reason": "the exact stabilized softmax boundary is authenticated, but no backend legalization or execution is claimed"},
        "claims": {"functional_equivalence": False, "rtl_equivalence": False, "timing_closure": False, "hardware_inference": False, "reference_source_or_rtl_copied": False},
        "provenance": {"reference_role": "content_authenticated_behavioral_oracle_only", "llm_assistance_disclosure_required": True},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--diagnostic", required=True, type=Path)
    parser.add_argument("--mlir-out", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    graph = args.graph.read_text(encoding="utf-8")
    evidence = load_evidence(args.contract, args.diagnostic)
    descriptor = bridge_graph(graph, evidence, source_name=str(args.graph))
    mlir = render_custom_op(descriptor)
    report = make_report(descriptor, graph, mlir)
    report["sha256"] = canonical_sha256({key: value for key, value in report.items() if key != "sha256"})
    args.mlir_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.mlir_out.write_text(mlir, encoding="utf-8")
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
