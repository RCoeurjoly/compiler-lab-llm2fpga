#!/usr/bin/env python3
"""Probe the first real fixed-profile TinyStories transformer-block lowering.

This command consumes the content-authenticated Task 3l handoff and inspects
the actual ``torch.export`` graph.  It is intentionally fail closed: the
fixed-hardware profile defines activation Q/DQ and GEMV arithmetic, but it does
not define executable fixed-point LayerNorm, softmax, or GELU semantics.  A
twelve-checkpoint example is an oracle for one input, not an operator
specification.  Consequently no MLIR, SystemVerilog, RTLIL, simulation, or
alignment claim is emitted until the first missing semantic is authenticated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.comparison import fixed_hardware_qdq_profile as fixed_qdq  # noqa: E402


SCHEMA = "tinystories-1m-fixed-profile-slice-lowering-v1"
EXPECTED = {
    "contract": "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf",
    "profile": "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6",
    "qdq": "a274d61ec5f634fac8fb501339ddfe7ae4bf774d950840498d54c32b90d79e77",
    "exported_program": "389964a2f39a8256bc824b58b60f681bd136f2868633125e8872ce9791c8e73e",
    "adapter_receipt": "276915df4d14d8934e642851ce560cae0bf59d6785ec2ccf776c576a98d2b229",
    "numeric_trace": "d83df8e12aa2658709b78a47849e29e19ef4e95b57bb052654377d541f04f215",
    "package_receipt": "aa546aa3956fd5de207af647ed4cf280d26c8477e9f308f9f0b39c1a2b90cca2",
}
EXPECTED_ADAPTER_RECEIPT_SELF_HASH = "c6df8bbe4caa8a9078e5e70e77db06f2c474b8b4e497ece9f28cde38b870033a"
EXPECTED_FIRST_TARGET = "aten.layer_norm.default"


class FixedProfileSliceLoweringError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise FixedProfileSliceLoweringError("artifact_missing", f"{path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FixedProfileSliceLoweringError("invalid_json", f"{label}: {error}") from error
    if not isinstance(value, dict):
        raise FixedProfileSliceLoweringError("invalid_json", f"{label} must contain an object")
    return value


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FixedProfileSliceLoweringError(code, message)


def _require_hash(path: Path, expected: str, code: str) -> str:
    actual = sha256_file(path)
    require(actual == expected, code, f"{path}: {actual} != {expected}")
    return actual


def validate_inputs(
    *,
    contract_path: Path,
    profile_path: Path,
    qdq_path: Path,
    task2_path: Path,
    lowering_dir: Path,
    exported_program: Path,
) -> dict[str, Any]:
    """Validate the exact Task 3l handoff before loading executable content."""

    contract_path = Path(contract_path)
    profile_path = Path(profile_path)
    qdq_path = Path(qdq_path)
    task2_path = Path(task2_path)
    lowering_dir = Path(lowering_dir)
    exported_program = Path(exported_program)

    hashes = {
        "contract_sha256": _require_hash(contract_path, EXPECTED["contract"], "contract_identity_mismatch"),
        "profile_sha256": _require_hash(profile_path, EXPECTED["profile"], "profile_identity_mismatch"),
        "qdq_receipt_sha256": _require_hash(qdq_path, EXPECTED["qdq"], "qdq_identity_mismatch"),
        # Check the archive before torch.export is allowed to deserialize it.
        "exported_program_sha256": _require_hash(
            exported_program, EXPECTED["exported_program"], "exported_program_identity_mismatch"
        ),
    }
    try:
        profile = fixed_qdq.validate_profile(profile_path, contract_path, qdq_path)
    except fixed_qdq.FixedHardwareProfileError as error:
        raise FixedProfileSliceLoweringError(error.code, str(error)) from error

    attempt_path = lowering_dir / "lowering-attempt.json"
    adapter_path = lowering_dir / "adapter-receipt.json"
    trace_path = lowering_dir / "numeric-trace.json"
    package_receipt_path = lowering_dir / "package-receipt.json"
    staged_profile_path = lowering_dir / "fixed-hardware-qdq-profile.json"
    staged_contract_path = lowering_dir / "canonical-contract.json"
    attempt = load_json(attempt_path, "Task 3l lowering attempt")
    adapter = load_json(adapter_path, "Task 3l adapter receipt")
    task2 = load_json(task2_path, "Task 2 slice metadata")

    hashes.update({
        "lowering_attempt_sha256": sha256_file(attempt_path),
        "adapter_receipt_sha256": _require_hash(
            adapter_path, EXPECTED["adapter_receipt"], "adapter_receipt_identity_mismatch"
        ),
        "numeric_trace_sha256": _require_hash(
            trace_path, EXPECTED["numeric_trace"], "numeric_trace_identity_mismatch"
        ),
        "package_receipt_sha256": _require_hash(
            package_receipt_path, EXPECTED["package_receipt"], "package_receipt_identity_mismatch"
        ),
        "task2_metadata_sha256": sha256_file(task2_path),
    })
    _require_hash(staged_profile_path, EXPECTED["profile"], "staged_profile_identity_mismatch")
    _require_hash(staged_contract_path, EXPECTED["contract"], "staged_contract_identity_mismatch")

    require(
        attempt.get("schema") == "tinystories-1m-authenticated-package-lowering-v1"
        and attempt.get("status") == "unsupported"
        and attempt.get("failure", {}).get("code") == "fixed_hardware_qdq_compiler_lowering_not_implemented",
        "task3l_handoff_mismatch",
        "Task 3l must be the authenticated fixed-profile unsupported handoff",
    )
    package_export = attempt.get("package_export")
    require(isinstance(package_export, dict), "task3l_handoff_mismatch", "package export hashes missing")
    require(
        package_export == {
            "adapter_receipt_sha256": EXPECTED["adapter_receipt"],
            "exported_program_sha256": EXPECTED["exported_program"],
            "numeric_trace_sha256": EXPECTED["numeric_trace"],
            "package_receipt_sha256": EXPECTED["package_receipt"],
        },
        "task3l_handoff_mismatch",
        "Task 3l artifact hashes differ",
    )
    require(
        adapter.get("receipt_sha256") == EXPECTED_ADAPTER_RECEIPT_SELF_HASH
        and adapter.get("identity", {}).get("contract_sha256") == EXPECTED["contract"]
        and adapter.get("artifacts", {}).get("exported_program", {}).get("sha256") == EXPECTED["exported_program"]
        and adapter.get("artifacts", {}).get("numeric_trace", {}).get("sha256") == EXPECTED["numeric_trace"],
        "adapter_receipt_content_mismatch",
        "adapter receipt is not bound to the canonical contract and export",
    )
    require(
        task2.get("schema") == "tinystories-1m-compiler-slice-manifest-v1"
        and task2.get("model") == "TinyStories-1M"
        and task2.get("slice", {}).get("kind") == "one_transformer_block_token_step",
        "task2_metadata_mismatch",
        "Task 2 metadata does not name the required slice",
    )
    require(
        profile.get("board_authenticated") is False,
        "board_authority_mismatch",
        "this lowering task must preserve unresolved board authority",
    )
    return {
        **hashes,
        "task2_metadata": {
            "schema": task2["schema"],
            "status": task2.get("status"),
            "slice_kind": task2["slice"]["kind"],
            "sha256": hashes["task2_metadata_sha256"],
        },
    }


def _target_name(target: Any) -> str:
    text = str(target)
    # torch overloads stringify as ``aten.layer_norm.default``.  Keep the
    # representation strict enough to make graph changes visible.
    match = re.search(r"aten\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?", text)
    return match.group(0) if match else text


def inspect_exported_program(path: Path) -> list[dict[str, Any]]:
    """Load a content-checked PT2 archive and return deterministic graph ops."""

    try:
        import torch

        exported = torch.export.load(Path(path))
    except Exception as error:
        raise FixedProfileSliceLoweringError("exported_program_load_failed", str(error)) from error
    operations: list[dict[str, Any]] = []
    for graph_index, node in enumerate(exported.graph_module.graph.nodes):
        if node.op != "call_function":
            continue
        operations.append({
            "graph_index": graph_index,
            "name": str(node.name),
            "target": _target_name(node.target),
        })
    require(bool(operations), "exported_program_graph_empty", "no call_function nodes")
    return operations


def classify_block_lowering(
    profile: Mapping[str, Any], operations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return the first profile semantic that the compiler cannot implement."""

    semantics = profile.get("semantics")
    require(isinstance(semantics, dict), "fixed_semantics_missing", "profile semantics missing")
    activation = semantics.get("activation_conversion")
    accumulation = semantics.get("accumulation")
    weight_scale = semantics.get("weight_scale")
    require(
        isinstance(activation, dict)
        and isinstance(accumulation, dict)
        and isinstance(weight_scale, dict),
        "fixed_semantics_missing",
        "activation Q/DQ or GEMV semantics missing",
    )
    layer_norm = next((dict(item) for item in operations if item.get("target") == EXPECTED_FIRST_TARGET), None)
    require(layer_norm is not None, "block_boundary_not_found", "aten.layer_norm.default absent from export")

    # The authenticated profile deliberately contains no LayerNorm algorithm.
    # Its two checkpoint tensors cannot define rounding/overflow for other
    # inputs, so they are not sufficient to synthesize this operation.
    if "layer_norm" not in semantics:
        return {
            "status": "unsupported",
            "semantically_defined_prefix": ["block.input.activation_qdq"],
            "first_unsupported_operation": {
                **layer_norm,
                "checkpoint": "block.ln_1",
                "output_checkpoint": "block.ln_1.output",
                "code": "fixed_layer_norm_semantics_unavailable",
                "missing_semantics": [
                    "mean_reduction_order_and_width",
                    "variance_reduction_order_and_width",
                    "epsilon_representation",
                    "inverse_square_root_algorithm",
                    "gamma_beta_rounding_saturation_and_overflow",
                ],
                "reason": (
                    "the authenticated fixed-hardware profile gives LayerNorm input/output checkpoints "
                    "but no executable fixed-point LayerNorm semantics; example values cannot define an operator"
                ),
            },
        }
    raise FixedProfileSliceLoweringError(
        "unreviewed_layer_norm_semantics",
        "profile unexpectedly defines LayerNorm; add an independently reviewed lowering before proceeding",
    )


def make_unsupported_report(
    *, profile: Mapping[str, Any], operations: Sequence[Mapping[str, Any]], evidence: Mapping[str, Any]
) -> dict[str, Any]:
    classification = classify_block_lowering(profile, operations)
    trace = profile.get("software_trace")
    require(isinstance(trace, dict), "software_trace_missing", "profile trace missing")
    checkpoints = trace.get("checkpoints")
    require(isinstance(checkpoints, dict) and len(checkpoints) == 12, "software_trace_incomplete", "expected 12 checkpoints")
    evidence_dict = dict(evidence)
    task2 = evidence_dict.pop("task2_metadata", {
        "schema": "tinystories-1m-compiler-slice-manifest-v1",
        "status": "unavailable",
        "slice_kind": "one_transformer_block_token_step",
        "sha256": None,
    })
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "model": "TinyStories-1M",
        "slice": {"kind": "one_transformer_block_token_step", "block_index": 0, "token_index": 3},
        "status": "unsupported",
        "alignment_status": "unaligned",
        "board_authenticated": False,
        "profile": {
            "name": profile.get("profile"),
            "status": profile.get("status"),
            "profile_sha256": profile.get("profile_sha256"),
        },
        "evidence": evidence_dict,
        "task2_metadata": task2,
        "graph": {
            "exported_program_sha256": evidence_dict.get("exported_program_sha256"),
            "call_function_count": len(operations),
            "operation_sequence_sha256": canonical_sha256(list(operations)),
        },
        "semantically_defined_prefix": classification["semantically_defined_prefix"],
        "first_unsupported_operation": classification["first_unsupported_operation"],
        "software_trace": {
            "status": "authenticated_profile_trace_validated",
            "checkpoint_count": len(checkpoints),
            "checkpoint_order": trace.get("checkpoint_order"),
            "sha256": trace.get("sha256"),
        },
        "compiler_artifacts": {"mlir": None, "systemverilog": None, "rtlil": None},
        "compiler_slice_equivalence": {
            "status": "not_run",
            "reason_code": "compiler_slice_not_emitted",
        },
        "provenance": {
            "reference_role": "content_authenticated_behavioral_oracle_only",
            "reference_source_or_rtl_copied": False,
            "compiler_source": "LLM2FPGA",
            "llm_assistance_disclosure_required": True,
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--fixed-qdq-profile", required=True, type=Path)
    parser.add_argument("--qdq-receipt", required=True, type=Path)
    parser.add_argument("--task2-metadata", required=True, type=Path)
    parser.add_argument("--lowering-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    exported_program = args.lowering_dir / "exported.pt2"
    evidence = validate_inputs(
        contract_path=args.contract,
        profile_path=args.fixed_qdq_profile,
        qdq_path=args.qdq_receipt,
        task2_path=args.task2_metadata,
        lowering_dir=args.lowering_dir,
        exported_program=exported_program,
    )
    operations = inspect_exported_program(exported_program)
    profile = load_json(args.fixed_qdq_profile, "fixed-hardware Q/DQ profile")
    report = make_unsupported_report(profile=profile, operations=operations, evidence=evidence)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
