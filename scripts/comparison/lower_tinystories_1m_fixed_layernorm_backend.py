#!/usr/bin/env python3
"""Legalize the authenticated TinyStories-1M fixed LayerNorm to flat SCF.

The established CIRCT SCF-to-Calyx converter rejects memories wider than 64
bits.  The receipt-defined 72-bit variance reduction is therefore represented
as an explicit unsigned ``[high8:low64]`` limb pair.  The 33x33 square is
mathematically bounded below 2**64 for signed-int32 inputs and their int32
mean, so the emitted absolute-delta i64 multiply preserves the declared
66-bit square without introducing an illegal wide backend value.

This stage proves deterministic legalization and Calyx conversion only.  Its
algorithm trace checks the same primitive operation schedule in Python, but is
not a Calyx simulation; the report remains fail-closed until backend execution
is independently verified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_SCRIPT = ROOT / "scripts/comparison/bridge_tinystories_1m_rtl_layernorm.py"
BRIDGE_SCRIPT_SHA256 = "99bac4f1a414336d54dcd7d328fbb63eac837d87e75fb393862e3fde997505d7"
BRIDGE_FILE_SHA256 = "2544191ec838a36e0865ae729725bef4c46bbde93efddbc6bdb6cd3a93fed073"
BRIDGE_RECEIPT_SHA256 = "5f8d17c3d3ad209e52b1460a677f49d21c42a4f3a674a51b5e4896a93511311d"
BRIDGE_MLIR_SHA256 = "92c532626a81c974f85414c052a51b84ca55c0b230af3c03f177c8adb5c8f5c8"
VECTOR_FILE_SHA256 = "750007e58f6303cbb0fe3b67c7a424d3d28ebd4c8bf4fc0428c3181c356c4c5e"
VECTOR_SHA256 = "1b84d6194874f1f9e6074a99f06527aa01e633ecc6daf92340136a86806d6304"
WIDTH = 64
MASK64 = (1 << 64) - 1


class BackendLoweringError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise BackendLoweringError(code, message)


def canonical_sha256(value: Any) -> str:
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise BackendLoweringError("noncanonical_value", str(error)) from error
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(Path(path).read_bytes())
    except OSError as error:
        raise BackendLoweringError("artifact_missing", f"{path}: {error}") from error


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BackendLoweringError("invalid_json", f"{path}: {error}") from error
    require(isinstance(value, dict), "invalid_json", f"{path}: expected object")
    return value


def _load_bridge_module() -> Any:
    require(sha256_file(BRIDGE_SCRIPT) == BRIDGE_SCRIPT_SHA256, "bridge_script_identity_mismatch", str(BRIDGE_SCRIPT))
    spec = importlib.util.spec_from_file_location("task3p_bridge", BRIDGE_SCRIPT)
    require(spec is not None and spec.loader is not None, "bridge_script_load_failed", str(BRIDGE_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_authenticated_inputs(bridge_path: Path, bridge_mlir_path: Path, vector_path: Path) -> dict[str, Any]:
    """Load only the pinned Task3p evidence and reject self-rehashed substitutes."""

    require(sha256_file(bridge_path) == BRIDGE_FILE_SHA256, "bridge_artifact_identity_mismatch", str(bridge_path))
    require(sha256_file(bridge_mlir_path) == BRIDGE_MLIR_SHA256, "bridge_mlir_identity_mismatch", str(bridge_mlir_path))
    require(sha256_file(vector_path) == VECTOR_FILE_SHA256, "vector_artifact_identity_mismatch", str(vector_path))
    bridge = load_json(bridge_path)
    vector = load_json(vector_path)
    require(
        bridge.get("schema") == "tinystories-1m-layernorm-compiler-bridge-v1"
        and bridge.get("sha256") == BRIDGE_RECEIPT_SHA256
        and bridge.get("sha256") == canonical_sha256({key: value for key, value in bridge.items() if key != "sha256"}),
        "bridge_receipt_mismatch",
        "Task3p schema/self hash",
    )
    require(
        vector.get("schema") == "tinystories-1m-rtl-layernorm-vector-v1"
        and vector.get("sha256") == VECTOR_SHA256
        and vector.get("sha256") == canonical_sha256({key: value for key, value in vector.items() if key != "sha256"}),
        "vector_receipt_mismatch",
        "Task3o vector schema/self hash",
    )
    descriptor = bridge.get("custom_op")
    require(isinstance(descriptor, dict), "bridge_descriptor_missing", "custom_op")
    bridge_module = _load_bridge_module()
    # Task3p writes JSON with ``sort_keys=True`` while its in-memory validator
    # also asserts semantic checkpoint order.  Restore that authenticated order
    # after checking the deserialized mapping has exactly the expected values.
    require(
        descriptor.get("checkpoint_identities") == bridge_module.CHECKPOINT_IDENTITIES,
        "checkpoint_identity_mismatch",
        "Task3p descriptor checkpoints",
    )
    ordered_descriptor = copy.deepcopy(descriptor)
    ordered_descriptor["checkpoint_identities"] = dict(bridge_module.CHECKPOINT_IDENTITIES)
    try:
        bridge_module.validate_descriptor(ordered_descriptor)
    except Exception as error:
        raise BackendLoweringError("bridge_descriptor_mismatch", str(error)) from error
    expected_mlir = bridge_module.lower_custom_op_to_mlir(ordered_descriptor)
    actual_mlir = Path(bridge_mlir_path).read_text(encoding="utf-8")
    require(actual_mlir == expected_mlir, "bridge_mlir_content_mismatch", str(bridge_mlir_path))
    require(
        bridge.get("compiler_artifacts", {}).get("mlir", {}).get("sha256") == BRIDGE_MLIR_SHA256,
        "bridge_mlir_binding_mismatch",
        "Task3p report",
    )
    checkpoints = bridge.get("checkpoint_identities")
    require(
        isinstance(checkpoints, dict)
        and checkpoints == descriptor.get("checkpoint_identities")
        and len(checkpoints) == 12,
        "checkpoint_identity_mismatch",
        "exact Task3p checkpoint set",
    )
    require(bridge.get("numeric_trace", {}).get("result") == vector.get("result"), "numeric_vector_binding_mismatch", "Task3p/Task3o result")
    return {
        "bridge": bridge,
        "descriptor": ordered_descriptor,
        "vector": vector,
        "checkpoint_identities": dict(bridge_module.CHECKPOINT_IDENTITIES),
        "bridge_file_sha256": BRIDGE_FILE_SHA256,
        "bridge_mlir_sha256": BRIDGE_MLIR_SHA256,
        "vector_file_sha256": VECTOR_FILE_SHA256,
    }


def validate_bundle(bundle: Mapping[str, Any]) -> None:
    require(
        isinstance(bundle, Mapping)
        and set(bundle)
        == {
            "bridge",
            "descriptor",
            "vector",
            "checkpoint_identities",
            "bridge_file_sha256",
            "bridge_mlir_sha256",
            "vector_file_sha256",
        },
        "backend_bundle_schema_mismatch",
        "authenticated bundle keys",
    )
    bridge = bundle.get("bridge")
    descriptor = bundle.get("descriptor")
    vector = bundle.get("vector")
    require(
        bundle.get("bridge_file_sha256") == BRIDGE_FILE_SHA256
        and bundle.get("bridge_mlir_sha256") == BRIDGE_MLIR_SHA256
        and bundle.get("vector_file_sha256") == VECTOR_FILE_SHA256,
        "bridge_artifact_identity_mismatch",
        "bundle file identities",
    )
    require(
        isinstance(bridge, dict)
        and bridge.get("sha256") == BRIDGE_RECEIPT_SHA256
        and bridge.get("sha256")
        == canonical_sha256({key: value for key, value in bridge.items() if key != "sha256"}),
        "bridge_receipt_mismatch",
        "bundle bridge receipt",
    )
    require(
        isinstance(vector, dict)
        and vector.get("sha256") == VECTOR_SHA256
        and vector.get("sha256")
        == canonical_sha256({key: value for key, value in vector.items() if key != "sha256"}),
        "vector_receipt_mismatch",
        "bundle vector receipt",
    )
    bridge_module = _load_bridge_module()
    try:
        bridge_module.validate_descriptor(descriptor)
    except Exception as error:
        raise BackendLoweringError("bridge_descriptor_mismatch", str(error)) from error
    require(
        descriptor == {**bridge["custom_op"], "checkpoint_identities": dict(bridge_module.CHECKPOINT_IDENTITIES)}
        and bundle.get("checkpoint_identities") == bridge_module.CHECKPOINT_IDENTITIES
        and bridge.get("numeric_trace", {}).get("result") == vector.get("result"),
        "backend_bundle_binding_mismatch",
        "descriptor/checkpoints/numeric vector",
    )


def _wrap_u(value: int, width: int) -> int:
    return value & ((1 << width) - 1)


def _wrap_s(value: int, width: int) -> int:
    unsigned = _wrap_u(value, width)
    return unsigned - (1 << width) if unsigned & (1 << (width - 1)) else unsigned


def _trunc_div(numerator: int, denominator: int) -> int:
    require(denominator > 0, "zero_deviation", str(denominator))
    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


def execute_lowered_algorithm(vector: Mapping[str, Any]) -> dict[str, Any]:
    """Execute the limb schedule rendered by :func:`render_flat_scf`."""

    values = vector.get("input_q16_16")
    gamma = vector.get("gamma_q16_16")
    beta = vector.get("beta_q16_16")
    require(all(isinstance(items, list) and len(items) == WIDTH for items in (values, gamma, beta)), "vector_shape_mismatch", "input/gamma/beta")
    require(all(isinstance(item, int) and not isinstance(item, bool) for items in (values, gamma, beta) for item in items), "vector_value_mismatch", "signed integers")
    mean_accumulator = _wrap_s(sum(values), 64)
    mean = _trunc_div(mean_accumulator, WIDTH)
    low = 0
    high = 0
    deltas: list[int] = []
    for value in values:
        delta = value - mean
        require(-(1 << 32) < delta < (1 << 32), "delta_bound_violation", str(delta))
        deltas.append(delta)
        square = _wrap_u(abs(delta) * abs(delta), 64)
        next_low = _wrap_u(low + square, 64)
        carry = 1 if next_low < low else 0
        low = next_low
        high = _wrap_u(high + carry, 8)
    square_sum = (high << 64) | low
    variance = _wrap_u((square_sum >> 6) + 42950, 64)
    remainder = variance
    root = 0
    bit = 1 << 62
    for _ in range(32):
        candidate = _wrap_u(root + bit, 64)
        if remainder >= candidate:
            remainder = _wrap_u(remainder - candidate, 64)
            root = _wrap_u((root >> 1) + bit, 64)
        else:
            root >>= 1
        bit >>= 2
    require(root != 0, "zero_deviation", "epsilon and variance produced zero")
    normalized = [_wrap_s(_trunc_div(delta << 16, root), 32) for delta in deltas]
    output = [
        _wrap_s(((value * scale) >> 16) + offset, 32)
        for value, scale, offset in zip(normalized, gamma, beta)
    ]
    return {
        "mean_q16_16": mean,
        "square_sum_72": square_sum,
        "variance_u64": variance,
        "deviation_floor_sqrt": root,
        "normalized_q16_16": normalized,
        "output_q16_16": output,
    }


def _manifest_attributes(bundle: Mapping[str, Any]) -> str:
    values = [
        ("task3p_bridge_file_sha256", bundle["bridge_file_sha256"]),
        ("task3p_bridge_receipt_sha256", bundle["bridge"]["sha256"]),
        ("task3p_custom_op_sha256", bundle["descriptor"]["sha256"]),
        ("task3p_custom_mlir_sha256", bundle["bridge_mlir_sha256"]),
        ("task3o_vector_file_sha256", bundle["vector_file_sha256"]),
        ("task3o_vector_sha256", bundle["vector"]["sha256"]),
        ("wide_reduction_layout", "unsigned_high8_low64"),
        ("square_realization", "abs_signed_delta_i64_product"),
    ]
    for index, (name, digest) in enumerate(bundle["checkpoint_identities"].items()):
        values.append((f"checkpoint_{index:02d}_name", name))
        values.append((f"checkpoint_{index:02d}_sha256", digest))
    return ", ".join(f'{name} = "{value}"' for name, value in values)


def render_flat_scf(bundle: Mapping[str, Any]) -> str:
    """Render unrolled, deterministic, Calyx-legal integer MLIR."""

    # Revalidate the exact immutable inputs at this public boundary.
    validate_bundle(bundle)
    lines = [
        f"module attributes {{llm2fpga.backend_manifest = {{{_manifest_attributes(bundle)}}}}} {{",
        "  func.func @main(%input: memref<64xi32>, %gamma: memref<64xi32>, %beta: memref<64xi32>, %output: memref<64xi32>) {",
        "    %c0 = arith.constant 0 : index",
        "    %zero_i64 = arith.constant 0 : i64",
        "    %zero_i8 = arith.constant 0 : i8",
        "    %den64 = arith.constant 64 : i64",
        "    %epsilon = arith.constant 42950 : i64",
        "    %shift1 = arith.constant 1 : i64",
        "    %shift2 = arith.constant 2 : i64",
        "    %shift6 = arith.constant 6 : i64",
        "    %shift16 = arith.constant 16 : i64",
        "    %shift58 = arith.constant 58 : i64",
        "    %sqrt_bit_init = arith.constant 4611686018427387904 : i64",
    ]
    previous = "%zero_i64"
    for index in range(WIDTH):
        lines.extend([
            f"    %idx_{index:02d} = arith.constant {index} : index",
            f"    %mean_x_{index:02d} = memref.load %input[%idx_{index:02d}] : memref<64xi32>",
            f"    %mean_x64_{index:02d} = arith.extsi %mean_x_{index:02d} : i32 to i64",
            f"    %mean_sum_{index:02d} = arith.addi {previous}, %mean_x64_{index:02d} : i64",
        ])
        previous = f"%mean_sum_{index:02d}"
    lines.append(f"    %mean = arith.divsi {previous}, %den64 : i64")
    low = "%zero_i64"
    high = "%zero_i8"
    for index in range(WIDTH):
        lines.extend([
            f"    %var_x64_{index:02d} = arith.extsi %mean_x_{index:02d} : i32 to i64",
            f"    %delta_{index:02d} = arith.subi %var_x64_{index:02d}, %mean : i64",
            f"    %delta_negative_{index:02d} = arith.cmpi slt, %delta_{index:02d}, %zero_i64 : i64",
            f"    %delta_negated_{index:02d} = arith.subi %zero_i64, %delta_{index:02d} : i64",
            f"    %delta_abs_{index:02d} = arith.select %delta_negative_{index:02d}, %delta_negated_{index:02d}, %delta_{index:02d} : i64",
            f"    %square_{index:02d} = arith.muli %delta_abs_{index:02d}, %delta_abs_{index:02d} : i64",
            f"    %sumsq_low_{index:02d} = arith.addi {low}, %square_{index:02d} : i64",
            f"    %sumsq_carry_{index:02d} = arith.cmpi ult, %sumsq_low_{index:02d}, {low} : i64",
            f"    %sumsq_carry8_{index:02d} = arith.extui %sumsq_carry_{index:02d} : i1 to i8",
            f"    %sumsq_high_{index:02d} = arith.addi {high}, %sumsq_carry8_{index:02d} : i8",
        ])
        low = f"%sumsq_low_{index:02d}"
        high = f"%sumsq_high_{index:02d}"
    lines.extend([
        f"    %sumsq_high64 = arith.extui {high} : i8 to i64",
        f"    %variance_low = arith.shrui {low}, %shift6 : i64",
        "    %variance_high = arith.shli %sumsq_high64, %shift58 : i64",
        "    %variance_without_epsilon = arith.ori %variance_low, %variance_high : i64",
        "    %variance = arith.addi %variance_without_epsilon, %epsilon : i64",
    ])
    remainder = "%variance"
    root = "%zero_i64"
    bit = "%sqrt_bit_init"
    for index in range(32):
        lines.extend([
            f"    %sqrt_candidate_{index:02d} = arith.addi {root}, {bit} : i64",
            f"    %sqrt_ge_{index:02d} = arith.cmpi uge, {remainder}, %sqrt_candidate_{index:02d} : i64",
            f"    %sqrt_sub_{index:02d} = arith.subi {remainder}, %sqrt_candidate_{index:02d} : i64",
            f"    %sqrt_remainder_{index:02d} = arith.select %sqrt_ge_{index:02d}, %sqrt_sub_{index:02d}, {remainder} : i64",
            f"    %sqrt_root_half_{index:02d} = arith.shrui {root}, %shift1 : i64",
            f"    %sqrt_root_plus_bit_{index:02d} = arith.addi %sqrt_root_half_{index:02d}, {bit} : i64",
            f"    %sqrt_root_{index:02d} = arith.select %sqrt_ge_{index:02d}, %sqrt_root_plus_bit_{index:02d}, %sqrt_root_half_{index:02d} : i64",
            f"    %sqrt_bit_{index:02d} = arith.shrui {bit}, %shift2 : i64",
        ])
        remainder = f"%sqrt_remainder_{index:02d}"
        root = f"%sqrt_root_{index:02d}"
        bit = f"%sqrt_bit_{index:02d}"
    for index in range(WIDTH):
        lines.extend([
            f"    %norm_numerator_{index:02d} = arith.shli %delta_{index:02d}, %shift16 : i64",
            f"    %norm64_{index:02d} = arith.divsi %norm_numerator_{index:02d}, {root} : i64",
            f"    %norm_{index:02d} = arith.trunci %norm64_{index:02d} : i64 to i32",
            f"    %gamma_{index:02d} = memref.load %gamma[%idx_{index:02d}] : memref<64xi32>",
            f"    %gamma64_{index:02d} = arith.extsi %gamma_{index:02d} : i32 to i64",
            f"    %norm_ext_{index:02d} = arith.extsi %norm_{index:02d} : i32 to i64",
            f"    %affine_product_{index:02d} = arith.muli %norm_ext_{index:02d}, %gamma64_{index:02d} : i64",
            f"    %affine_scaled_{index:02d} = arith.shrsi %affine_product_{index:02d}, %shift16 : i64",
            f"    %beta_{index:02d} = memref.load %beta[%idx_{index:02d}] : memref<64xi32>",
            f"    %beta64_{index:02d} = arith.extsi %beta_{index:02d} : i32 to i64",
            f"    %affine_biased_{index:02d} = arith.addi %affine_scaled_{index:02d}, %beta64_{index:02d} : i64",
            f"    %wrapped_{index:02d} = arith.trunci %affine_biased_{index:02d} : i64 to i32",
            f"    memref.store %wrapped_{index:02d}, %output[%idx_{index:02d}] : memref<64xi32>",
        ])
    lines.extend(["    return", "  }", "}"])
    return "\n".join(lines) + "\n"


def validate_calyx_structure(bundle: Mapping[str, Any], calyx_mlir: str) -> None:
    """Reject partial, stale-looking, or unrelated Calyx text."""

    validate_bundle(bundle)
    require(isinstance(calyx_mlir, str) and calyx_mlir.strip(), "calyx_artifact_invalid", "empty conversion output")
    require(
        'calyx.entrypoint = "main"' in calyx_mlir
        and "llm2fpga.backend_manifest" in calyx_mlir
        and "calyx.component @main(" in calyx_mlir
        and "calyx.component @main_1(" in calyx_mlir,
        "calyx_artifact_invalid",
        "entrypoint/component structure",
    )
    require(
        calyx_mlir.count("{external = true}") == 4
        and calyx_mlir.count("<[64] x 32>") >= 8,
        "calyx_artifact_invalid",
        "expected four external 64xi32 memories and their internal bindings",
    )
    require(
        "llm2fpga.fixed_layer_norm_q16_16" not in calyx_mlir
        and "func.func" not in calyx_mlir
        and "memref." not in calyx_mlir,
        "calyx_artifact_invalid",
        "unlowered operation residue",
    )
    for identity in (
        bundle["bridge_file_sha256"],
        bundle["bridge"]["sha256"],
        bundle["descriptor"]["sha256"],
        bundle["bridge_mlir_sha256"],
        bundle["vector_file_sha256"],
        bundle["vector"]["sha256"],
        *bundle["checkpoint_identities"].values(),
    ):
        require(identity in calyx_mlir, "calyx_artifact_invalid", f"missing provenance identity {identity}")


def _failed_conversion(command: Sequence[str], diagnostic: str) -> dict[str, Any]:
    return {
        "calyx_mlir": None,
        "command": list(command),
        "diagnostic": diagnostic,
        "validation": None,
    }


def run_calyx_conversion(
    circt_opt: Path, flat_scf_path: Path, calyx_out: Path, bundle: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert and independently reparse Calyx, never trusting prior output."""

    validate_bundle(bundle)
    require(Path(flat_scf_path).is_file(), "flat_scf_missing", str(flat_scf_path))
    require(
        sha256_file(flat_scf_path) == sha256_bytes(render_flat_scf(bundle).encode()),
        "flat_scf_identity_mismatch",
        str(flat_scf_path),
    )
    calyx_out = Path(calyx_out)
    calyx_out.unlink(missing_ok=True)
    command = [
        str(circt_opt),
        str(flat_scf_path),
        "--lower-scf-to-calyx=top-level-function=main",
        "-o",
        str(calyx_out),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    conversion_diagnostic = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        calyx_out.unlink(missing_ok=True)
        return _failed_conversion(command, f"calyx_conversion_failed(exit={completed.returncode}): {conversion_diagnostic}")
    if not calyx_out.is_file():
        return _failed_conversion(command, "conversion_output_missing: circt-opt exited zero without creating --calyx-out")
    try:
        calyx_mlir = calyx_out.read_text(encoding="utf-8")
        validate_calyx_structure(bundle, calyx_mlir)
    except (OSError, UnicodeError, BackendLoweringError) as error:
        calyx_out.unlink(missing_ok=True)
        return _failed_conversion(command, f"calyx_artifact_invalid: {error}")

    with tempfile.NamedTemporaryFile(
        prefix=".task3q-calyx-reparse-",
        suffix=".mlir",
        dir=calyx_out.parent,
        delete=False,
    ) as temporary:
        reparsed_path = Path(temporary.name)
    # Presence must prove the parser invocation, not NamedTemporaryFile.
    reparsed_path.unlink()
    reparse_command = [str(circt_opt), str(calyx_out), "--verify-each", "-o", str(reparsed_path)]
    try:
        reparsed = subprocess.run(reparse_command, check=False, capture_output=True, text=True)
        reparse_diagnostic = (reparsed.stdout + reparsed.stderr).strip()
        if reparsed.returncode != 0:
            calyx_out.unlink(missing_ok=True)
            return _failed_conversion(
                command,
                f"calyx_reparse_failed(exit={reparsed.returncode}): {reparse_diagnostic}",
            )
        if not reparsed_path.is_file():
            calyx_out.unlink(missing_ok=True)
            return _failed_conversion(
                command,
                "calyx_reparse_output_missing: verifier exited zero without creating output",
            )
        reparsed_mlir = reparsed_path.read_text(encoding="utf-8")
        validate_calyx_structure(bundle, reparsed_mlir)
        validation = {
            "schema": "tinystories-1m-calyx-validation-v1",
            "status": "converted_and_reparsed",
            "flat_scf_sha256": sha256_file(flat_scf_path),
            "calyx_sha256": sha256_bytes(calyx_mlir.encode()),
            "reparsed_calyx_sha256": sha256_bytes(reparsed_mlir.encode()),
            "conversion_command": command,
            "reparse_command": [
                str(circt_opt),
                str(calyx_out),
                "--verify-each",
                "-o",
                "<temporary-reparse-output>",
            ],
        }
        validation["sha256"] = canonical_sha256(validation)
        diagnostic = "\n".join(item for item in (conversion_diagnostic, reparse_diagnostic) if item)
        return {
            "calyx_mlir": calyx_mlir,
            "command": command,
            "diagnostic": diagnostic,
            "validation": validation,
        }
    except (OSError, UnicodeError, BackendLoweringError) as error:
        calyx_out.unlink(missing_ok=True)
        return _failed_conversion(command, f"calyx_reparse_invalid: {error}")
    finally:
        reparsed_path.unlink(missing_ok=True)


def make_report(
    bundle: Mapping[str, Any],
    flat_scf: str,
    *,
    calyx_mlir: str | None,
    calyx_command: Sequence[str] | None,
    calyx_diagnostic: str,
    calyx_validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    require(flat_scf == render_flat_scf(bundle), "rendered_backend_ir_mismatch", "flat SCF")
    algorithm_result = execute_lowered_algorithm(bundle["vector"])
    expected = bundle["vector"].get("result")
    require(algorithm_result == expected, "lowered_algorithm_trace_mismatch", "Task3o vector")
    calyx_artifact = None
    backend_status = "flat_scf_emitted"
    if calyx_mlir is not None:
        validate_calyx_structure(bundle, calyx_mlir)
        require(isinstance(calyx_validation, Mapping), "calyx_validation_missing", "converted output must be independently reparsed")
        required_validation_keys = {
            "schema",
            "status",
            "flat_scf_sha256",
            "calyx_sha256",
            "reparsed_calyx_sha256",
            "conversion_command",
            "reparse_command",
            "sha256",
        }
        require(set(calyx_validation) == required_validation_keys, "calyx_validation_mismatch", "receipt keys")
        require(
            calyx_validation.get("schema") == "tinystories-1m-calyx-validation-v1"
            and calyx_validation.get("status") == "converted_and_reparsed"
            and calyx_validation.get("flat_scf_sha256") == sha256_bytes(flat_scf.encode())
            and calyx_validation.get("calyx_sha256") == sha256_bytes(calyx_mlir.encode())
            and calyx_validation.get("conversion_command") == list(calyx_command or ())
            and calyx_validation.get("sha256")
            == canonical_sha256({key: value for key, value in calyx_validation.items() if key != "sha256"}),
            "calyx_validation_mismatch",
            "conversion/reparse receipt",
        )
        calyx_artifact = {"kind": "calyx_mlir", "sha256": sha256_bytes(calyx_mlir.encode())}
        backend_status = "calyx_emitted_not_executed"
    else:
        require(calyx_validation is None, "calyx_validation_mismatch", "validation without Calyx artifact")
    return {
        "schema": "tinystories-1m-fixed-layernorm-backend-v1",
        "model": "TinyStories-1M",
        "slice": {"kind": "one_transformer_block_token_step", "block_index": 0, "token_index": 3},
        "status": "unsupported",
        "alignment_status": "unaligned",
        "board_authenticated": False,
        "backend_ir": {
            "status": backend_status,
            "representation": "unrolled_flat_scf_with_unsigned_high8_low64_variance_sum",
            "custom_op_eliminated": True,
            "max_integer_width": 64,
            "calyx_command": list(calyx_command) if calyx_command is not None else None,
            "calyx_diagnostic": calyx_diagnostic,
            "calyx_validation": dict(calyx_validation) if calyx_validation is not None else None,
        },
        "numeric_trace": {
            "status": "algorithm_matched_backend_execution_not_run",
            "expected_sha256": canonical_sha256(expected),
            "lowered_algorithm_sha256": canonical_sha256(algorithm_result),
            "result": algorithm_result,
            "scope": "compiler-side execution of emitted operation schedule; not MLIR/Calyx simulation",
        },
        "checkpoint_identities": dict(bundle["checkpoint_identities"]),
        "first_unsupported_operation": {
            "target": "calyx_backend_execution",
            "pipeline_stage": "calyx_numeric_equivalence",
            "code": "calyx_backend_execution_not_verified",
            "reason": "flat SCF and Calyx conversion are available, but no executed Calyx trace has yet been compared with the authenticated vector",
        },
        "compiler_artifacts": {
            "flat_scf": {"kind": "flat_scf_mlir", "sha256": sha256_bytes(flat_scf.encode())},
            "calyx": calyx_artifact,
            "systemverilog": None,
            "rtlil": None,
        },
        "provenance": {
            "task3p_bridge_file_sha256": bundle["bridge_file_sha256"],
            "task3p_bridge_receipt_sha256": bundle["bridge"]["sha256"],
            "task3p_custom_op_sha256": bundle["descriptor"]["sha256"],
            "task3p_custom_mlir_sha256": bundle["bridge_mlir_sha256"],
            "task3o_vector_file_sha256": bundle["vector_file_sha256"],
            "task3o_vector_sha256": bundle["vector"]["sha256"],
            "reference_role": "content_authenticated_behavioral_oracle_only",
            "reference_source_or_rtl_copied": False,
            "compiler_source": "LLM2FPGA",
            "llm_assistance_disclosure_required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", required=True, type=Path)
    parser.add_argument("--bridge-mlir", required=True, type=Path)
    parser.add_argument("--vector", required=True, type=Path)
    parser.add_argument("--circt-opt", type=Path)
    parser.add_argument("--flat-scf-out", required=True, type=Path)
    parser.add_argument("--calyx-out", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    bundle = load_authenticated_inputs(args.bridge, args.bridge_mlir, args.vector)
    flat_scf = render_flat_scf(bundle)
    calyx_mlir = None
    command = None
    diagnostic = "backend conversion not requested"
    validation = None
    args.flat_scf_out.parent.mkdir(parents=True, exist_ok=True)
    args.calyx_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.flat_scf_out.write_text(flat_scf, encoding="utf-8")
    if args.circt_opt is not None:
        conversion = run_calyx_conversion(args.circt_opt, args.flat_scf_out, args.calyx_out, bundle)
        calyx_mlir = conversion["calyx_mlir"]
        command = conversion["command"]
        diagnostic = conversion["diagnostic"]
        validation = conversion["validation"]
    else:
        args.calyx_out.unlink(missing_ok=True)
    report = make_report(
        bundle,
        flat_scf,
        calyx_mlir=calyx_mlir,
        calyx_command=command,
        calyx_diagnostic=diagnostic,
        calyx_validation=validation,
    )
    report["compiler_artifacts"]["flat_scf"]["path"] = str(args.flat_scf_out)
    if calyx_mlir is not None:
        report["compiler_artifacts"]["calyx"]["path"] = str(args.calyx_out)
    report["sha256"] = canonical_sha256(report)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
