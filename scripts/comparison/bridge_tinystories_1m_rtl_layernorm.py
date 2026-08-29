#!/usr/bin/env python3
"""Bridge the authenticated TinyStories-1M LayerNorm op to compiler IR.

The bridge recognizes only the block-0/final-prompt-token LayerNorm shape and
parameter bindings emitted by the authenticated package adapter.  Its custom
op is an inspectable compiler contract for the independent Task 3o arithmetic
primitive; it is not reference RTL and it is not yet legal for the current
Torch-MLIR/Calyx backend.  The report therefore moves the fail-closed frontier
from missing LayerNorm semantics to the exact custom-op legalization hook.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = ROOT / "TinyStories/model_adapter_reference_package.py"
ADAPTER_SHA256 = "a8f24571cfabb99aea5fe92a8521a06aa6d71691e8acf5bc9c89adf2b6af3cff"
LAYER_NORM_PROFILE_SHA256 = "e035dc5835a3908fa687281089e75d1a9dac0f846f84950211ba2681f1259006"
LAYER_NORM_RECEIPT_SHA256 = "44bdd11a2e52831006c1eca6345916f248b94797d9fd2020c7b1f150530a0278"
LAYER_NORM_VECTOR_FILE_SHA256 = "750007e58f6303cbb0fe3b67c7a424d3d28ebd4c8bf4fc0428c3181c356c4c5e"
LAYER_NORM_VECTOR_SHA256 = "1b84d6194874f1f9e6074a99f06527aa01e633ecc6daf92340136a86806d6304"
LAYER_NORM_PRIMITIVE_SHA256 = "600a9ad83b2b5651dcf5666bbee6f36f0b3b5941ee7fafb9cc4538794f2e8eb5"
QDQ_PROFILE_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"
EXPORTED_PROGRAM_SHA256 = "389964a2f39a8256bc824b58b60f681bd136f2868633125e8872ce9791c8e73e"
ADAPTER_RECEIPT_FILE_SHA256 = "276915df4d14d8934e642851ce560cae0bf59d6785ec2ccf776c576a98d2b229"
ADAPTER_RECEIPT_SHA256 = "c6df8bbe4caa8a9078e5e70e77db06f2c474b8b4e497ece9f28cde38b870033a"
CUSTOM_OP = "llm2fpga.fixed_layer_norm_q16_16"
WIDTH = 64
SOURCE_SHAPE = [1, 4, WIDTH]
TOKEN_INDEX = 3
EPSILON = 1e-5
EPSILON_Q32 = 42950
CHECKPOINT_SHAPES: dict[str, tuple[int, ...]] = {
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


class LayerNormBridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise LayerNormBridgeError(code, message)


def canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise LayerNormBridgeError("noncanonical_value", str(error)) from error
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise LayerNormBridgeError("artifact_missing", f"{path}: {error}") from error


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LayerNormBridgeError("invalid_json", f"{label}: {error}") from error
    require(isinstance(value, dict), "invalid_json", f"{label} must contain an object")
    return value


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "module_load_failed", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _strict_int_tree(value: Any) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, list) and all(_strict_int_tree(item) for item in value)
    )


def _validate_checkpoint_identities(profile: Mapping[str, Any]) -> dict[str, str]:
    trace = profile.get("software_trace")
    require(isinstance(trace, dict), "checkpoint_trace_missing", "fixed Q/DQ software trace")
    require(
        trace.get("checkpoint_order") == list(CHECKPOINT_SHAPES),
        "checkpoint_identity_mismatch",
        "the package-adapter twelve-checkpoint order changed",
    )
    checkpoints = trace.get("checkpoints")
    require(
        isinstance(checkpoints, dict) and set(checkpoints) == set(CHECKPOINT_SHAPES),
        "checkpoint_identity_mismatch",
        "expected exactly the twelve package-adapter checkpoints",
    )
    identities: dict[str, str] = {}
    for name, shape in CHECKPOINT_SHAPES.items():
        checkpoint = checkpoints.get(name)
        require(isinstance(checkpoint, dict), "checkpoint_identity_mismatch", name)
        payload = {
            "shape": list(shape),
            "dtype": "signed_q16.16",
            "values": checkpoint.get("values"),
        }
        require(
            checkpoint.get("shape") == list(shape)
            and checkpoint.get("dtype") == "signed_q16.16"
            and _strict_int_tree(checkpoint.get("values"))
            and checkpoint.get("sha256") == canonical_sha256(payload),
            "checkpoint_identity_mismatch",
            name,
        )
        identities[name] = checkpoint["sha256"]
    trace_without_hash = {key: value for key, value in trace.items() if key != "sha256"}
    require(trace.get("sha256") == canonical_sha256(trace_without_hash), "checkpoint_trace_hash_mismatch", "software trace")
    return identities


def load_evidence(
    profile_path: Path,
    vector_path: Path,
    primitive_path: Path,
    qdq_profile_path: Path,
) -> dict[str, Any]:
    """Authenticate the Task 3o primitive/vector and their semantic inputs."""

    require(sha256_file(ADAPTER_PATH) == ADAPTER_SHA256, "package_adapter_identity_mismatch", str(ADAPTER_PATH))
    require(sha256_file(profile_path) == LAYER_NORM_PROFILE_SHA256, "layernorm_profile_identity_mismatch", str(profile_path))
    require(sha256_file(vector_path) == LAYER_NORM_VECTOR_FILE_SHA256, "layernorm_vector_identity_mismatch", str(vector_path))
    require(sha256_file(primitive_path) == LAYER_NORM_PRIMITIVE_SHA256, "layernorm_primitive_identity_mismatch", str(primitive_path))
    require(sha256_file(qdq_profile_path) == QDQ_PROFILE_SHA256, "qdq_profile_identity_mismatch", str(qdq_profile_path))

    profile = load_json(profile_path, "LayerNorm semantics receipt")
    vector = load_json(vector_path, "Task 3o LayerNorm vector")
    qdq_profile = load_json(qdq_profile_path, "fixed Q/DQ profile")
    require(
        profile.get("receipt_sha256")
        == canonical_sha256({key: value for key, value in profile.items() if key != "receipt_sha256"})
        == LAYER_NORM_RECEIPT_SHA256,
        "layernorm_profile_hash_mismatch",
        "Task 3n receipt self hash",
    )
    candidates = profile.get("candidate_profiles")
    rtl_profile = candidates.get("synthesizable_rtl") if isinstance(candidates, dict) else None
    require(isinstance(rtl_profile, dict), "rtl_profile_missing", "synthesizable_rtl")
    require(
        vector.get("schema") == "tinystories-1m-rtl-layernorm-vector-v1"
        and vector.get("profile") == "synthesizable_rtl"
        and vector.get("layernorm_receipt_sha256") == LAYER_NORM_RECEIPT_SHA256
        and vector.get("sha256") == LAYER_NORM_VECTOR_SHA256
        and vector.get("sha256") == canonical_sha256({key: value for key, value in vector.items() if key != "sha256"}),
        "layernorm_vector_content_mismatch",
        "Task 3o vector content or binding",
    )
    require(
        qdq_profile.get("profile_sha256")
        == canonical_sha256({key: value for key, value in qdq_profile.items() if key != "profile_sha256"}),
        "qdq_profile_hash_mismatch",
        "fixed Q/DQ profile self hash",
    )
    identities = _validate_checkpoint_identities(qdq_profile)

    primitive = _load_module(Path(primitive_path), "tinystories_1m_rtl_layernorm_primitive")
    bridge_result = primitive.fixed_layer_norm_rtl(
        vector.get("input_q16_16", []),
        vector.get("gamma_q16_16", []),
        vector.get("beta_q16_16", []),
        details=True,
    )
    software_result = vector.get("result")
    require(isinstance(software_result, dict), "layernorm_vector_content_mismatch", "result")
    software_hash = canonical_sha256(software_result)
    bridge_hash = canonical_sha256(bridge_result)
    require(bridge_result == software_result, "layernorm_numeric_trace_mismatch", f"{bridge_hash} != {software_hash}")
    return {
        "profile": "synthesizable_rtl",
        "format": "signed_q16.16_int32",
        "width": WIDTH,
        "profile_sha256": LAYER_NORM_PROFILE_SHA256,
        "profile_receipt_sha256": LAYER_NORM_RECEIPT_SHA256,
        "vector_file_sha256": LAYER_NORM_VECTOR_FILE_SHA256,
        "vector_sha256": LAYER_NORM_VECTOR_SHA256,
        "primitive_sha256": LAYER_NORM_PRIMITIVE_SHA256,
        "qdq_profile_sha256": QDQ_PROFILE_SHA256,
        "package_adapter_sha256": ADAPTER_SHA256,
        "checkpoint_identities": identities,
        "checkpoint_trace_sha256": qdq_profile["software_trace"]["sha256"],
        "arithmetic_profile": rtl_profile,
        "numeric_trace": {
            "status": "matched",
            "input_sha256": canonical_sha256({
                "input_q16_16": vector["input_q16_16"],
                "gamma_q16_16": vector["gamma_q16_16"],
                "beta_q16_16": vector["beta_q16_16"],
            }),
            "software_result_sha256": software_hash,
            "bridge_result_sha256": bridge_hash,
            "result": bridge_result,
        },
    }


def _target_name(target: Any) -> str:
    match = re.search(r"aten\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?", str(target))
    return match.group(0) if match else str(target)


def _tensor_metadata(node: Any, label: str) -> tuple[list[int], str]:
    value = getattr(node, "meta", {}).get("val")
    require(value is not None and hasattr(value, "shape") and hasattr(value, "dtype"), "export_metadata_missing", label)
    try:
        shape = [int(dimension) for dimension in value.shape]
    except (TypeError, ValueError) as error:
        raise LayerNormBridgeError("unsupported_dynamic_shape", label) from error
    return shape, str(value.dtype)


def inspect_exported_layernorm(exported_program: Path, adapter_receipt_path: Path, *, graph_index: int) -> dict[str, Any]:
    """Inspect the exact package-adapter export and recover one LayerNorm node."""

    require(sha256_file(exported_program) == EXPORTED_PROGRAM_SHA256, "exported_program_identity_mismatch", str(exported_program))
    require(
        sha256_file(adapter_receipt_path) == ADAPTER_RECEIPT_FILE_SHA256,
        "adapter_receipt_identity_mismatch",
        str(adapter_receipt_path),
    )
    receipt = load_json(adapter_receipt_path, "package adapter receipt")
    require(
        receipt.get("receipt_sha256")
        == canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})
        == ADAPTER_RECEIPT_SHA256,
        "adapter_receipt_content_mismatch",
        "receipt self hash",
    )
    require(
        receipt.get("artifacts", {}).get("exported_program", {}).get("sha256") == EXPORTED_PROGRAM_SHA256,
        "adapter_export_binding_mismatch",
        "receipt does not bind the PT2 archive",
    )
    mapping = receipt.get("tensor_mapping")
    require(isinstance(mapping, dict), "adapter_receipt_content_mismatch", "tensor mapping")
    for source, target in (
        ("blocks.0.ln1.weight", "transformer.h.0.ln_1.weight"),
        ("blocks.0.ln1.bias", "transformer.h.0.ln_1.bias"),
    ):
        entry = mapping.get(source)
        require(
            isinstance(entry, dict)
            and entry.get("target") == target
            and entry.get("shape") == [64]
            and entry.get("format") == "float32",
            "adapter_parameter_binding_mismatch",
            source,
        )
    try:
        import torch

        exported = torch.export.load(Path(exported_program))
    except Exception as error:
        raise LayerNormBridgeError("exported_program_load_failed", str(error)) from error
    nodes = list(exported.graph_module.graph.nodes)
    require(0 <= graph_index < len(nodes), "layernorm_node_missing", str(graph_index))
    node = nodes[graph_index]
    require(node.op == "call_function" and _target_name(node.target) == "aten.layer_norm.default", "layernorm_node_mismatch", str(node))
    args = list(node.args)
    require(4 <= len(args) <= 6, "unsupported_layernorm_signature", f"{len(args)} operands")
    input_shape, input_dtype = _tensor_metadata(args[0], "input")
    weight_shape, weight_dtype = _tensor_metadata(args[2], "weight")
    bias_shape, bias_dtype = _tensor_metadata(args[3], "bias")
    normalized_shape = [int(value) for value in args[1]] if isinstance(args[1], Sequence) else []
    epsilon = args[4] if len(args) >= 5 else EPSILON
    cudnn_enable = args[5] if len(args) >= 6 else True
    parameters = exported.graph_signature.inputs_to_parameters
    weight_parameter = parameters.get(args[2].name)
    bias_parameter = parameters.get(args[3].name)
    return {
        "graph_index": graph_index,
        "name": str(node.name),
        "target": _target_name(node.target),
        "input_shape": input_shape,
        "input_dtype": input_dtype,
        "normalized_shape": normalized_shape,
        "weight_shape": weight_shape,
        "weight_dtype": weight_dtype,
        "weight_parameter": weight_parameter,
        "bias_shape": bias_shape,
        "bias_dtype": bias_dtype,
        "bias_parameter": bias_parameter,
        "epsilon": epsilon,
        "cudnn_enable": cudnn_enable,
        "exported_program_sha256": EXPORTED_PROGRAM_SHA256,
        "adapter_receipt_sha256": ADAPTER_RECEIPT_FILE_SHA256,
    }


def bridge_source_op(source_op: Mapping[str, Any], evidence: Mapping[str, Any], *, token_index: int) -> dict[str, Any]:
    """Validate an aten LayerNorm and construct the fixed compiler custom op."""

    require(source_op.get("target") == "aten.layer_norm.default", "unsupported_source_operation", str(source_op.get("target")))
    require(source_op.get("input_shape") == SOURCE_SHAPE, "unsupported_source_shape", str(source_op.get("input_shape")))
    require(source_op.get("normalized_shape") == [WIDTH], "unsupported_normalized_shape", str(source_op.get("normalized_shape")))
    require(source_op.get("input_dtype") == "torch.float32", "unsupported_source_dtype", str(source_op.get("input_dtype")))
    require(source_op.get("weight_shape") == [WIDTH] and source_op.get("bias_shape") == [WIDTH], "unsupported_parameter_shape", "gamma/beta")
    require(
        source_op.get("weight_dtype") == "torch.float32" and source_op.get("bias_dtype") == "torch.float32",
        "unsupported_parameter_dtype",
        "gamma/beta",
    )
    require(math.isclose(source_op.get("epsilon", math.nan), EPSILON, rel_tol=0.0, abs_tol=0.0), "unsupported_epsilon", str(source_op.get("epsilon")))
    require(source_op.get("cudnn_enable") is True, "unsupported_layernorm_parameter", "cudnn_enable")
    require(
        source_op.get("weight_parameter") == "model.transformer.h.0.ln_1.weight"
        and source_op.get("bias_parameter") == "model.transformer.h.0.ln_1.bias",
        "parameter_binding_mismatch",
        "expected block-0 ln_1 gamma/beta",
    )
    require(token_index == TOKEN_INDEX, "unsupported_token_index", str(token_index))
    require(
        evidence.get("profile") == "synthesizable_rtl"
        and evidence.get("format") == "signed_q16.16_int32"
        and evidence.get("width") == WIDTH
        and evidence.get("numeric_trace", {}).get("status") == "matched",
        "bridge_evidence_mismatch",
        "Task 3o evidence",
    )
    attributes = {
        "normalized_width": WIDTH,
        "token_index": TOKEN_INDEX,
        "input_fraction_bits": 16,
        "input_width": 32,
        "parameter_fraction_bits": 16,
        "parameter_width": 32,
        "mean_accumulator_width": 64,
        "delta_width": 33,
        "square_width": 66,
        "variance_sum_width": 72,
        "variance_width": 64,
        "epsilon_q32": EPSILON_Q32,
        "reduction_order": "ascending_index_0_to_63",
        "sqrt": "floor_integer_restoring",
        "division": "signed_truncation_toward_zero",
        "affine_shift": 16,
        "output_width": 32,
        "output_overflow": "twos_complement_wrap",
    }
    descriptor: dict[str, Any] = {
        "schema": "llm2fpga-fixed-layer-norm-op-v1",
        "op": CUSTOM_OP,
        "operand_types": ["tensor<64xi32>"] * 3,
        "result_types": ["tensor<64xi32>"],
        "attributes": attributes,
        "source": dict(source_op),
        "evidence": {
            key: evidence[key]
            for key in (
                "profile_sha256",
                "profile_receipt_sha256",
                "vector_file_sha256",
                "vector_sha256",
                "primitive_sha256",
                "qdq_profile_sha256",
                "package_adapter_sha256",
                "checkpoint_trace_sha256",
            )
        },
        "checkpoint_identities": dict(evidence["checkpoint_identities"]),
    }
    descriptor["sha256"] = canonical_sha256(descriptor)
    return descriptor


def lower_custom_op_to_mlir(descriptor: Mapping[str, Any]) -> str:
    """Deterministic inspectable lowering hook to an unregistered MLIR op."""

    require(descriptor.get("schema") == "llm2fpga-fixed-layer-norm-op-v1", "bridge_descriptor_mismatch", "schema")
    require(descriptor.get("op") == CUSTOM_OP, "bridge_descriptor_mismatch", "op")
    require(
        descriptor.get("sha256") == canonical_sha256({key: value for key, value in descriptor.items() if key != "sha256"}),
        "bridge_descriptor_hash_mismatch",
        "custom op",
    )
    attrs = descriptor.get("attributes")
    require(isinstance(attrs, dict), "bridge_descriptor_mismatch", "attributes")
    required = {
        "normalized_width": WIDTH,
        "token_index": TOKEN_INDEX,
        "input_fraction_bits": 16,
        "input_width": 32,
        "parameter_fraction_bits": 16,
        "parameter_width": 32,
        "mean_accumulator_width": 64,
        "delta_width": 33,
        "square_width": 66,
        "variance_sum_width": 72,
        "variance_width": 64,
        "epsilon_q32": EPSILON_Q32,
        "reduction_order": "ascending_index_0_to_63",
        "sqrt": "floor_integer_restoring",
        "division": "signed_truncation_toward_zero",
        "affine_shift": 16,
        "output_width": 32,
        "output_overflow": "twos_complement_wrap",
    }
    require(attrs == required, "bridge_descriptor_mismatch", "arithmetic attributes")
    return (
        "module {\n"
        "  func.func @tinystories_1m_block0_ln1_token3("
        "%input: tensor<64xi32>, %gamma: tensor<64xi32>, %beta: tensor<64xi32>) "
        "-> tensor<64xi32> {\n"
        f"    %0 = \"{CUSTOM_OP}\"(%input, %gamma, %beta) <{{"
        "affine_shift = 16 : i64, delta_width = 33 : i64, division = \"signed_truncation_toward_zero\", "
        "epsilon_q32 = 42950 : i64, input_fraction_bits = 16 : i64, input_width = 32 : i64, "
        "mean_accumulator_width = 64 : i64, normalized_width = 64 : i64, output_overflow = \"twos_complement_wrap\", "
        "output_width = 32 : i64, parameter_fraction_bits = 16 : i64, parameter_width = 32 : i64, "
        "reduction_order = \"ascending_index_0_to_63\", sqrt = \"floor_integer_restoring\", "
        "square_width = 66 : i64, token_index = 3 : i64, variance_sum_width = 72 : i64, variance_width = 64 : i64"
        "}> : (tensor<64xi32>, tensor<64xi32>, tensor<64xi32>) -> tensor<64xi32>\n"
        "    return %0 : tensor<64xi32>\n"
        "  }\n"
        "}\n"
    )


def make_report(
    *, source_op: Mapping[str, Any], descriptor: Mapping[str, Any], mlir: str, evidence: Mapping[str, Any]
) -> dict[str, Any]:
    require(descriptor.get("op") == CUSTOM_OP, "bridge_descriptor_mismatch", "report op")
    return {
        "schema": "tinystories-1m-layernorm-compiler-bridge-v1",
        "model": "TinyStories-1M",
        "slice": {"kind": "one_transformer_block_token_step", "block_index": 0, "token_index": TOKEN_INDEX},
        "status": "unsupported",
        "alignment_status": "unaligned",
        "bridge_status": "custom_op_emitted",
        "board_authenticated": False,
        "source_operation": dict(source_op),
        "custom_op": dict(descriptor),
        "numeric_trace": dict(evidence["numeric_trace"]),
        "checkpoint_identities": dict(evidence["checkpoint_identities"]),
        "first_unsupported_operation": {
            "target": CUSTOM_OP,
            "pipeline_stage": "custom_op_to_linalg_or_calyx",
            "code": "fixed_layer_norm_backend_lowering_not_implemented",
            "reason": "the compiler graph contains the authenticated fixed LayerNorm op, but no backend legalization lowers it to the existing Linalg/Calyx path",
        },
        "compiler_artifacts": {
            "mlir": {"kind": "custom_op_ir", "sha256": hashlib.sha256(mlir.encode("utf-8")).hexdigest()},
            "systemverilog": None,
            "rtlil": None,
        },
        "compiler_slice_equivalence": {
            "status": "not_run",
            "reason_code": "fixed_layer_norm_backend_lowering_not_implemented",
        },
        "provenance": {
            "reference_role": "content_authenticated_behavioral_oracle_only",
            "reference_source_or_rtl_copied": False,
            "compiler_source": "LLM2FPGA",
            "llm_assistance_disclosure_required": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exported-program", required=True, type=Path)
    parser.add_argument("--adapter-receipt", required=True, type=Path)
    parser.add_argument("--layernorm-profile", required=True, type=Path)
    parser.add_argument("--layernorm-vector", required=True, type=Path)
    parser.add_argument("--layernorm-primitive", required=True, type=Path)
    parser.add_argument("--fixed-qdq-profile", required=True, type=Path)
    parser.add_argument("--graph-index", type=int, default=149)
    parser.add_argument("--mlir-out", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    evidence = load_evidence(
        args.layernorm_profile,
        args.layernorm_vector,
        args.layernorm_primitive,
        args.fixed_qdq_profile,
    )
    source_op = inspect_exported_layernorm(args.exported_program, args.adapter_receipt, graph_index=args.graph_index)
    descriptor = bridge_source_op(source_op, evidence, token_index=TOKEN_INDEX)
    mlir = lower_custom_op_to_mlir(descriptor)
    report = make_report(source_op=source_op, descriptor=descriptor, mlir=mlir, evidence=evidence)
    args.mlir_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.mlir_out.write_text(mlir, encoding="utf-8")
    report["compiler_artifacts"]["mlir"]["path"] = str(args.mlir_out)
    report["sha256"] = canonical_sha256(report)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
