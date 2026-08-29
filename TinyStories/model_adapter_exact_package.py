from __future__ import annotations

"""Authenticated integer/fixed-point TinyStories-1M package adapter.

The public reference-package adapter remains an FP32 reconstruction.  This
module reuses only its package tensor mapping and executes the selected
``fixed_hardware_reference`` semantics explicitly with tensor-visible integer
codes, Q8.24 scales, signed Q16.16 values, signed-64 serial accumulation,
rounding, clamp, and LUT operations.
"""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

import torch

from TinyStories import model_adapter_reference_package as reference_adapter


Q_VALUE = 16
Q_SCALE = 24
MAX_CONTEXT = 32
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
AUDIT_NAME = "tinystories-1m-exact-input-audit.json"
FIXED_PROFILE_RELATIVE = Path("artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json")
FINITE_VALIDATOR_RELATIVE = Path("scripts/comparison/audit_tinystories_1m_exact_input.py")
FINITE_VALIDATOR_SHA256 = "93b51d87dbb0a61911abdb951573c37018c90358dfed2f27b67832a6c1eea92d"
FROZEN_FIXED_PROFILE_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"
FROZEN_PROFILE_SELF_SHA256 = "7d54acda88f1d1a6979fd0ca8a3b0445e20ef127a399e5124a994427565caad0"


class ExactModelError(ValueError):
    """The exact model cannot be constructed or entered without approximation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ExactModelError(code, message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExactModelError("invalid_json", f"{label}: {error}") from error
    _require(isinstance(value, dict), "invalid_json", f"{label} must be an object")
    return value


def round_shift_signed(values: torch.Tensor, shift: int) -> torch.Tensor:
    """Signed nearest rounding, with ties away from zero, then right shift."""

    _require(isinstance(shift, int) and shift >= 0, "invalid_shift", str(shift))
    values = values.to(torch.int64)
    if shift == 0:
        return values.clone()
    magnitude = torch.abs(values)
    rounded = torch.bitwise_right_shift(magnitude + (1 << (shift - 1)), shift)
    return torch.where(values < 0, -rounded, rounded)


def activation_qdq(values_q16: torch.Tensor, scales_q24: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Execute one symmetric per-channel INT8 Q/DQ boundary explicitly."""

    values_q16 = values_q16.to(torch.int64)
    scales_q24 = scales_q24.to(torch.int64)
    numerator = torch.bitwise_left_shift(values_q16, Q_SCALE - Q_VALUE)
    magnitude = torch.div(
        torch.abs(numerator) + torch.div(scales_q24, 2, rounding_mode="floor"),
        scales_q24,
        rounding_mode="floor",
    )
    signed = torch.where(numerator < 0, -magnitude, magnitude)
    codes = torch.clamp(signed, -128, 127).to(torch.int64)
    dequantized = round_shift_signed(codes * scales_q24, Q_SCALE - Q_VALUE)
    return codes, dequantized


def serial_gemv_accumulate(scaled_input_q24: torch.Tensor, weight_codes: torch.Tensor) -> torch.Tensor:
    """Ascending-index signed-64 serial MAC; torch int64 supplies two's-complement wrap."""

    scaled_input_q24 = scaled_input_q24.to(torch.int64)
    weight_codes = weight_codes.to(torch.int64)
    _require(scaled_input_q24.ndim == 2 and weight_codes.ndim == 2,
             "gemv_shape_mismatch", "serial GEMV expects two matrices")
    _require(scaled_input_q24.shape[1] == weight_codes.shape[1],
             "gemv_shape_mismatch", "input widths differ")
    accumulator = torch.zeros(
        (scaled_input_q24.shape[0], weight_codes.shape[0]),
        dtype=torch.int64,
        device=scaled_input_q24.device,
    )
    for input_index in range(weight_codes.shape[1]):
        term = scaled_input_q24[:, input_index:input_index + 1] * weight_codes[:, input_index]
        accumulator = accumulator + term
    return accumulator


def _trunc_divide(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    quotient = torch.div(torch.abs(numerator), torch.abs(denominator), rounding_mode="floor")
    return torch.where((numerator < 0) != (denominator < 0), -quotient, quotient)


def _integer_sqrt(values: torch.Tensor) -> torch.Tensor:
    """Vectorized restoring square root for non-negative signed-64 values."""

    remainder = values.to(torch.int64)
    result = torch.zeros_like(remainder)
    bit = 1 << 62
    for _ in range(32):
        candidate = result + bit
        take = remainder >= candidate
        remainder = torch.where(take, remainder - candidate, remainder)
        result = torch.where(take, torch.bitwise_right_shift(result, 1) + bit,
                             torch.bitwise_right_shift(result, 1))
        bit >>= 2
    return result


def _fixed_layer_norm(values: torch.Tensor, gamma: torch.Tensor, beta: torch.Tensor) -> torch.Tensor:
    original_shape = values.shape
    rows = values.reshape(-1, original_shape[-1]).to(torch.int64)
    width = rows.shape[1]
    row_sum = torch.sum(rows, dim=1, keepdim=True, dtype=torch.int64)
    mean_magnitude = torch.div(torch.abs(row_sum), width, rounding_mode="floor")
    mean = torch.where(row_sum < 0, -mean_magnitude, mean_magnitude)
    deltas = rows - mean
    variance = torch.div(torch.sum(deltas * deltas, dim=1, keepdim=True, dtype=torch.int64),
                         width, rounding_mode="floor") + 42950
    deviation = _integer_sqrt(variance)
    normalized = _trunc_divide(torch.bitwise_left_shift(deltas, Q_VALUE), deviation)
    affine = torch.bitwise_right_shift(normalized * gamma, Q_VALUE) + beta
    return affine.reshape(original_shape)


def _gelu_table() -> torch.Tensor:
    values = []
    for index in range(8192):
        value = -8.0 + index / 512.0
        gelu = 0.5 * value * (
            1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (value + 0.044715 * value ** 3))
        )
        values.append(max(-32768, min(32767, round(gelu * 4096.0))))
    return torch.tensor(values, dtype=torch.int64)


def _exp_table() -> torch.Tensor:
    return torch.tensor(
        [round(math.exp((index - 4096) / 256.0) * (1 << 20)) for index in range(4096)],
        dtype=torch.int64,
    )


def _load_finite_validator() -> Callable[[Any], None]:
    path = _repo_root() / FINITE_VALIDATOR_RELATIVE
    _require(path.is_file() and _sha256(path) == FINITE_VALIDATOR_SHA256,
             "validator_identity_mismatch", str(path))
    spec = importlib.util.spec_from_file_location("tinystories_exact_finite_validator", path)
    _require(spec is not None and spec.loader is not None, "validator_identity_mismatch", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    validator = getattr(module, "validate_finite_adapter_input", None)
    _require(callable(validator), "validator_identity_mismatch", "finite validator missing")
    return validator


def _validate_arithmetic_identity(contract: Mapping[str, Any], audit: Mapping[str, Any],
                                  profile: Mapping[str, Any]) -> None:
    required_fixed = {
        "value_format": "signed Q16.16",
        "scale_format": "unsigned Q8.24",
        "gemv_accumulator": "signed 64-bit serial accumulator",
    }
    required_quantization = {
        "weights": "symmetric per-output INT8",
        "activations": "symmetric per-channel INT8",
        "activation_boundary_count": 97,
        "activation_vector_widths": [64, 256],
        "scale_format": "little-endian float32",
    }
    _require(contract.get("fixed_point") == required_fixed and audit.get("fixed_point") == required_fixed,
             "arithmetic_identity_mismatch", "fixed-point contract differs")
    _require(contract.get("quantization") == required_quantization
             and audit.get("quantization") == required_quantization,
             "arithmetic_identity_mismatch", "quantization contract differs")
    semantics = profile.get("semantics")
    _require(isinstance(semantics, dict)
             and semantics.get("execution_domain") == "integers_only_after_materialization",
             "arithmetic_identity_mismatch", "fixed profile execution domain differs")
    accumulation = semantics.get("accumulation", {}).get("synthesizable_rtl", {})
    _require(accumulation == {
        "operation": "serial_multiply_accumulate",
        "input_order": "ascending_input_index",
        "logical_width_bits": 64,
        "overflow": "twos_complement_wrap",
    }, "arithmetic_identity_mismatch", "serial accumulator semantics differ")
    activation = semantics.get("activation_conversion")
    _require(isinstance(activation, dict)
             and activation.get("rounding") == "nearest_ties_away_from_zero"
             and activation.get("clamp") == [-128, 127]
             and activation.get("zero_point") == 0,
             "arithmetic_identity_mismatch", "activation Q/DQ semantics differ")


def _authenticate_inputs(contract_path: Path, package_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = _load_json(contract_path, "exact-input contract")
    audit_path = contract_path.with_name(AUDIT_NAME)
    audit = _load_json(audit_path, "exact-input audit")
    _require(audit.get("schema") == "tinystories-1m-exact-input-audit-v1",
             "identity_frontier", "audit schema differs")
    _require(audit.get("sha256") == canonical_sha256({k: v for k, v in audit.items() if k != "sha256"}),
             "identity_frontier", "audit self-hash differs")
    _require(audit.get("status") == "authenticated" and audit.get("conflicts") == [],
             "identity_frontier", "canonical audit is not authenticated")
    _require(audit.get("next_gate") == "exact_quantized_pytorch_model",
             "identity_frontier", "audit does not authorize the exact model gate")
    _require(contract.get("schema") == "tinystories-1m-exact-input-contract-v2"
             and contract.get("status") == "authenticated",
             "identity_frontier", "v2 contract is not authenticated")
    audit_contract = audit.get("contract")
    _require(isinstance(audit_contract, dict) and audit_contract.get("sha256") == _sha256(contract_path),
             "identity_frontier", "audit is not bound to the supplied contract")
    required_model = {
        "name": "TinyStories-1M",
        "source_model_id": "roneneldan/TinyStories-1M",
        "source_revision": "ac533fb8b4f69c71894bf96badfe11e6294d9fcf",
        "architecture": "gpt_neo",
        "n_layer": 8,
        "hidden_size": 64,
        "n_head": 16,
        "head_dim": 4,
        "vocab_size": 50257,
        "max_context": 32,
    }
    _require(contract.get("model") == required_model and audit.get("model") == required_model,
             "model_identity_mismatch", "frozen model identity differs")
    required_reference = {
        "prompt_text": "Once upon a time",
        "prompt_tokens": [7454, 2402, 257, 640],
        "tokens": [11, 612, 373, 257, 1310, 2576, 3706, 20037,
                   13, 1375, 6151, 284, 711, 2354, 287, 262],
        "generation": "greedy top-1",
    }
    _require(contract.get("reference") == required_reference,
             "model_identity_mismatch", "frozen generation fixture differs")
    audit_fixture = audit.get("reference_fixture", {})
    _require(audit_fixture.get("prompt_ids") == required_reference["prompt_tokens"]
             and audit_fixture.get("expected_tokens") == required_reference["tokens"]
             and audit_fixture.get("fixed_reference_tokens") == required_reference["tokens"],
             "model_identity_mismatch", "authenticated reference fixture differs")
    deployed = contract.get("deployed_profile", {})
    _require(deployed.get("name") == "fixed_hardware_reference"
             and deployed.get("revision") == "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f"
             and deployed.get("nonfinite_policy") == "reject_nonfinite_adapter_input"
             and audit.get("nonfinite_policy") == "reject_nonfinite_adapter_input",
             "model_identity_mismatch", "deployed executable identity differs")
    selection = contract.get("selection_authority", {})
    selection_path = _repo_root() / str(selection.get("path", ""))
    _require(selection_path.is_file() and selection.get("sha256") == _sha256(selection_path),
             "model_identity_mismatch", "accepted selection authority differs")

    fixed_authority = contract.get("semantic_authorities", {}).get("fixed_profile", {})
    audit_fixed = audit.get("semantic_receipts", {}).get("fixed_profile", {})
    profile_path = _repo_root() / FIXED_PROFILE_RELATIVE
    _require(fixed_authority.get("path") == str(FIXED_PROFILE_RELATIVE)
             and fixed_authority.get("sha256") == FROZEN_FIXED_PROFILE_SHA256
             and audit_fixed.get("sha256") == FROZEN_FIXED_PROFILE_SHA256
             and _sha256(profile_path) == FROZEN_FIXED_PROFILE_SHA256,
             "arithmetic_identity_mismatch", "fixed-profile identity differs")
    profile = _load_json(profile_path, "fixed hardware profile")
    _require(profile.get("profile_sha256") == FROZEN_PROFILE_SELF_SHA256
             and profile.get("profile_sha256") == canonical_sha256(
                 {key: value for key, value in profile.items() if key != "profile_sha256"}
             ), "arithmetic_identity_mismatch", "fixed-profile self-hash differs")
    _validate_arithmetic_identity(contract, audit, profile)

    package_contract = contract.get("package")
    audit_package = audit.get("package")
    _require(isinstance(package_contract, dict) and isinstance(audit_package, dict),
             "package_identity_mismatch", "package identity missing")
    _require(Path(package_contract.get("origin", "")).resolve() == package_path.resolve()
             and Path(audit_package.get("path", "")).resolve() == package_path.resolve(),
             "package_identity_mismatch", "package path differs")
    expected_files = package_contract.get("files")
    _require(isinstance(expected_files, dict) and audit_package.get("files") == expected_files,
             "package_identity_mismatch", "audit and contract package files differ")
    for name, identity in expected_files.items():
        path = package_path / name
        _require(isinstance(identity, dict) and path.is_file()
                 and path.stat().st_size == identity.get("size")
                 and _sha256(path) == identity.get("sha256"),
                 "package_identity_mismatch", name)
    _require(package_contract.get("manifest_sha256") == expected_files["manifest.json"]["sha256"]
             and package_contract.get("sha256") == expected_files["weights.bin"]["sha256"],
             "package_identity_mismatch", "package aliases differ")
    return contract, audit, profile


def _tensor_images(manifest: Mapping[str, Any], weight_image: bytes, scale_image: bytes,
                   state_dict: Mapping[str, torch.Tensor]) -> tuple[
                       dict[str, torch.Tensor], dict[str, torch.Tensor], dict[str, torch.Tensor]
                   ]:
    codes: dict[str, torch.Tensor] = {}
    scales: dict[str, torch.Tensor] = {}
    parameters: dict[str, torch.Tensor] = {}
    tensors = manifest["tensors"]
    for name, descriptor in tensors.items():
        target = reference_adapter.package_name_to_gpt_neo_key(name)
        shape = tuple(descriptor["logical_shape"])
        if descriptor["format"] == "symmetric_int8_per_output":
            offset = int(descriptor["offset"])
            raw = weight_image[offset:offset + int(descriptor["nbytes"])]
            codes[name] = torch.frombuffer(bytearray(raw), dtype=torch.int8).clone().reshape(shape).to(torch.int64)
            scale_offset = int(descriptor["scale_offset"])
            scale_raw = scale_image[scale_offset:scale_offset + int(descriptor["scale_nbytes"])]
            float_scales = torch.frombuffer(bytearray(scale_raw), dtype=torch.float32).clone().to(torch.float64)
            materialized = torch.round(float_scales * (1 << Q_SCALE)).to(torch.int64)
            _require(bool(((materialized > 0) & (materialized < (1 << 24))).all()),
                     "arithmetic_identity_mismatch", f"{name}: Q8.24 scale range")
            scales[name] = materialized
        else:
            parameters[name] = torch.round(state_dict[target].to(torch.float64) * (1 << Q_VALUE)).to(torch.int64)
    for name, values in manifest["activation_scales"].items():
        materialized = torch.round(torch.tensor(values, dtype=torch.float64) * (1 << Q_SCALE)).to(torch.int64)
        _require(bool(((materialized > 0) & (materialized < (1 << 24))).all()),
                 "arithmetic_identity_mismatch", f"{name}: activation scale range")
        scales[f"activation::{name}"] = materialized
    return codes, scales, parameters


class _ExactFixedPointModel(torch.nn.Module):
    def __init__(self, codes: Mapping[str, torch.Tensor], scales: Mapping[str, torch.Tensor],
                 parameters: Mapping[str, torch.Tensor], finite_validator: Callable[[Any], None]) -> None:
        super().__init__()
        self._buffer_names: dict[str, str] = {}
        for prefix, values in (("code", codes), ("scale", scales), ("parameter", parameters)):
            for index, (name, tensor) in enumerate(sorted(values.items())):
                attribute = f"_{prefix}_{index}"
                self.register_buffer(attribute, tensor.to(torch.int64))
                self._buffer_names[f"{prefix}::{name}"] = attribute
        self.register_buffer("_gelu_lut", _gelu_table())
        self.register_buffer("_exp_lut", _exp_table())
        self._finite_validator = finite_validator

    def _buffer(self, prefix: str, name: str) -> torch.Tensor:
        return getattr(self, self._buffer_names[f"{prefix}::{name}"])

    def _activation_scale(self, name: str) -> torch.Tensor:
        return self._buffer("scale", f"activation::{name}")

    def _validate_input(self, input_ids: torch.Tensor) -> None:
        if not isinstance(input_ids, torch.Tensor):
            raise ExactModelError("nonfinite_adapter_input", "input_ids must be a tensor")
        try:
            self._finite_validator(input_ids.detach().cpu().tolist())
        except ValueError as error:
            raise ExactModelError("nonfinite_adapter_input", str(error)) from error
        _require(input_ids.dtype == torch.int64, "nonfinite_adapter_input", "token IDs must be torch.int64")
        _require(input_ids.ndim == 2 and input_ids.shape[0] == 1,
                 "input_shape_mismatch", "expected one [1, context] token batch")
        _require(1 <= input_ids.shape[1] <= MAX_CONTEXT,
                 "context_capacity_exceeded", "context length must be between 1 and 32")
        _require(bool(((input_ids >= 0) & (input_ids < 50257)).all()),
                 "token_id_out_of_range", "token IDs must be in [0, 50257)")

    def _embedding(self, name: str, rows: torch.Tensor) -> torch.Tensor:
        codes = self._buffer("code", name)[rows]
        scales = self._buffer("scale", name)[rows]
        return round_shift_signed(codes * scales.unsqueeze(-1), Q_SCALE - Q_VALUE)

    def _gemv(self, values: torch.Tensor, weight: str, bias: str | None,
              module: str, output_quantized: bool = True) -> torch.Tensor:
        original_shape = values.shape[:-1]
        flattened = values.reshape(-1, values.shape[-1])
        input_scale = self._activation_scale(f"{module}.input")
        input_codes, _ = activation_qdq(flattened, input_scale)
        scaled_input = input_codes * input_scale
        accumulator = serial_gemv_accumulate(scaled_input, self._buffer("code", weight))
        real_q16 = round_shift_signed(
            accumulator * self._buffer("scale", weight), 2 * Q_SCALE - Q_VALUE
        )
        if bias is not None:
            real_q16 = real_q16 + self._buffer("parameter", bias)
        if output_quantized:
            _, real_q16 = activation_qdq(real_q16, self._activation_scale(f"{module}.output"))
        return real_q16.reshape(original_shape + (real_q16.shape[-1],))

    def _fixed_gelu(self, values_q16: torch.Tensor) -> torch.Tensor:
        q12 = torch.clamp(round_shift_signed(values_q16, 4), -32768, 32767)
        biased = q12 + 32768
        index = torch.bitwise_right_shift(biased, 3)
        fraction = torch.bitwise_and(biased, 7)
        upper = torch.minimum(index + 1, torch.full_like(index, 8191))
        result_q12 = self._gelu_lut[index] + torch.bitwise_right_shift(
            (self._gelu_lut[upper] - self._gelu_lut[index]) * fraction, 3
        )
        return torch.bitwise_left_shift(result_q12, 4)

    def _attention(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor) -> torch.Tensor:
        length = query.shape[1]
        heads: list[torch.Tensor] = []
        for head in range(16):
            columns = slice(head * 4, head * 4 + 4)
            q_head = query[:, :, columns]
            k_head = key[:, :, columns]
            v_head = value[:, :, columns]
            positions: list[torch.Tensor] = []
            for position in range(length):
                products = q_head[:, position:position + 1, :] * k_head[:, :position + 1, :]
                scores = torch.bitwise_right_shift(torch.sum(products, dim=-1, dtype=torch.int64), 24)
                maxima = torch.amax(scores, dim=-1, keepdim=True)
                delta = torch.clamp(scores - maxima, -4096, 0)
                table_index = torch.minimum(4096 + delta, torch.full_like(delta, 4095))
                probabilities = torch.where(delta == 0, torch.full_like(delta, 1 << 20),
                                            self._exp_lut[table_index])
                denominator = torch.sum(probabilities, dim=-1, keepdim=True, dtype=torch.int64)
                numerator = torch.sum(probabilities.unsqueeze(-1) * v_head[:, :position + 1, :],
                                      dim=1, dtype=torch.int64)
                correction = torch.where(numerator < 0, -torch.div(denominator, 2, rounding_mode="floor"),
                                         torch.div(denominator, 2, rounding_mode="floor"))
                positions.append(_trunc_divide(numerator + correction, denominator))
            heads.append(torch.stack(positions, dim=1))
        return torch.cat(heads, dim=-1)

    def _execute(self, input_ids: torch.Tensor) -> tuple[torch.Tensor, tuple[torch.Tensor, ...], torch.Tensor]:
        length = input_ids.shape[1]
        positions = torch.arange(length, dtype=torch.int64, device=input_ids.device).unsqueeze(0)
        x = self._embedding("token_embedding.weight", input_ids)
        x = x + self._embedding("position_embedding.weight", positions)
        block_zero: tuple[torch.Tensor, ...] | None = None
        q_input_codes = torch.empty(0, dtype=torch.int64, device=input_ids.device)
        for layer in range(8):
            block = f"blocks.{layer}"
            source = f"transformer.h.{layer}"
            block_input = x
            normalized = _fixed_layer_norm(
                x, self._buffer("parameter", f"{block}.ln1.weight"),
                self._buffer("parameter", f"{block}.ln1.bias"),
            )
            query = self._gemv(normalized, f"{block}.attn.q.weight", None,
                               f"{source}.attn.attention.q_proj")
            key = self._gemv(normalized, f"{block}.attn.k.weight", None,
                             f"{source}.attn.attention.k_proj")
            value = self._gemv(normalized, f"{block}.attn.v.weight", None,
                               f"{source}.attn.attention.v_proj")
            context = self._attention(query, key, value)
            attention = self._gemv(context, f"{block}.attn.out.weight", f"{block}.attn.out.bias",
                                   f"{source}.attn.attention.out_proj")
            residual_attention = x + attention
            normalized_2 = _fixed_layer_norm(
                residual_attention, self._buffer("parameter", f"{block}.ln2.weight"),
                self._buffer("parameter", f"{block}.ln2.bias"),
            )
            hidden = self._gemv(normalized_2, f"{block}.mlp.fc.weight", f"{block}.mlp.fc.bias",
                                f"{source}.mlp.c_fc")
            activated = self._fixed_gelu(hidden)
            projected = self._gemv(activated, f"{block}.mlp.proj.weight", f"{block}.mlp.proj.bias",
                                   f"{source}.mlp.c_proj")
            x = residual_attention + projected
            if layer == 0:
                last = length - 1
                q_input_codes, _ = activation_qdq(
                    normalized[:, last, :], self._activation_scale(f"{source}.attn.attention.q_proj.input")
                )
                block_zero = (
                    block_input[0, last], normalized[0, last], query[0, last].reshape(16, 4),
                    key[0, last].reshape(16, 4), value[0, last].reshape(16, 4),
                    attention[0, last], residual_attention[0, last], normalized_2[0, last],
                    hidden[0, last], activated[0, last], projected[0, last], x[0, last],
                )
        normalized = _fixed_layer_norm(
            x, self._buffer("parameter", "final_ln.weight"), self._buffer("parameter", "final_ln.bias")
        )
        input_scale = self._activation_scale("lm_head.input")
        input_codes, _ = activation_qdq(normalized.reshape(-1, 64), input_scale)
        accumulator = serial_gemv_accumulate(
            input_codes * input_scale, self._buffer("code", "token_embedding.weight")
        )
        logits = round_shift_signed(
            accumulator * self._buffer("scale", "token_embedding.weight"), 2 * Q_SCALE - Q_VALUE
        ).reshape(1, length, 50257)
        assert block_zero is not None
        return logits, block_zero, q_input_codes

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        if not torch.compiler.is_compiling():
            self._validate_input(input_ids)
        return self._execute(input_ids)[0]


class _TraceOutputs(torch.nn.Module):
    def __init__(self, model: _ExactFixedPointModel) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor) -> tuple[torch.Tensor, ...]:
        logits, checkpoints, _ = self.model._execute(input_ids)
        return (logits,) + checkpoints


class ExactModelBundle:
    def __init__(self, *, contract: dict[str, Any], audit: dict[str, Any], profile: dict[str, Any],
                 manifest: dict[str, Any], model: _ExactFixedPointModel, receipt: dict[str, Any]) -> None:
        self.contract = contract
        self.audit = audit
        self.profile = profile
        self.manifest = manifest
        self.model = model
        self.receipt = receipt
        self.export_verification: dict[str, Any] = {}

    def trace(self, input_ids: torch.Tensor) -> dict[str, Any]:
        self.model._validate_input(input_ids)
        with torch.no_grad():
            logits, tensors, q_input_codes = self.model._execute(input_ids)
        checkpoints: dict[str, dict[str, Any]] = {}
        for (name, shape), tensor in zip(CHECKPOINT_SHAPES.items(), tensors, strict=True):
            _require(tuple(tensor.shape) == shape, "trace_schema_mismatch", name)
            payload = {"shape": list(shape), "dtype": "signed_q16.16", "values": tensor.cpu().tolist()}
            checkpoints[name] = {**payload, "sha256": canonical_sha256(payload)}
        oracle: dict[str, Any] = {
            "status": "runtime_authenticated_not_board_checkpoint_authenticated",
            "profile": "fixed_hardware_reference",
            "block_index": 0,
            "token_index": input_ids.shape[1] - 1,
            "prompt_tokens": input_ids[0].cpu().tolist(),
            "next_token": int(torch.argmax(logits[0, -1])),
            "checkpoint_order": list(CHECKPOINT_SHAPES),
            "checkpoints": checkpoints,
        }
        oracle["sha256"] = canonical_sha256(oracle)
        q_module = "transformer.h.0.attn.attention.q_proj"
        q_input_scale = self.model._activation_scale(f"{q_module}.input")
        q_input_codes, _ = activation_qdq(tensors[1].reshape(1, 64), q_input_scale)
        q_accumulator = serial_gemv_accumulate(
            q_input_codes * q_input_scale, self.model._buffer("code", "blocks.0.attn.q.weight")
        )
        q_weight_scale = self.model._buffer("scale", "blocks.0.attn.q.weight")
        q_before_output = round_shift_signed(q_accumulator * q_weight_scale, 2 * Q_SCALE - Q_VALUE)
        q_output_scale = self.model._activation_scale(f"{q_module}.output")
        q_output_codes, q_output = activation_qdq(q_before_output, q_output_scale)
        _require(torch.equal(q_output.reshape(16, 4), tensors[2]),
                 "trace_arithmetic_mismatch", "observable q projection differs")
        return {
            **oracle,
            "trace_sha256": oracle["sha256"],
            "arithmetic": {
                "value_format": "signed Q16.16",
                "accumulator": "signed_int64_serial_wrap",
                "rounding": "nearest_ties_away_from_zero",
                "saturation": [-128, 127],
                "q_proj.input": {
                    "codes": q_input_codes[0].cpu().tolist(),
                    "scales": q_input_scale.cpu().tolist(),
                    "scale_format": "unsigned Q8.24",
                },
                "q_proj.accumulator": {
                    "values": q_accumulator[0].cpu().tolist(),
                    "order": "ascending_input_index",
                    "width_bits": 64,
                    "overflow": "twos_complement_wrap",
                },
                "q_proj.weight_scale": {
                    "values": q_weight_scale.cpu().tolist(),
                    "round_shift": 32,
                },
                "q_proj.output": {
                    "codes": q_output_codes[0].cpu().tolist(),
                    "scales": q_output_scale.cpu().tolist(),
                    "dequantized": q_output[0].cpu().tolist(),
                    "scale_format": "unsigned Q8.24",
                },
            },
        }


def load_exact_model(contract_path: Path, package_path: Path, model_path: Path) -> ExactModelBundle:
    """Authenticate all identities, materialize integers, and construct the exact model."""

    contract_path = Path(contract_path)
    package_path = Path(package_path)
    model_path = Path(model_path)
    contract, audit, profile = _authenticate_inputs(contract_path, package_path)
    manifest = _load_json(package_path / "manifest.json", "package manifest")
    reference_adapter._validate_config(model_path, manifest)
    target_shapes = {
        reference_adapter.package_name_to_gpt_neo_key(name): tuple(descriptor["logical_shape"])
        for name, descriptor in manifest["tensors"].items()
    }
    target_shapes["lm_head.weight"] = target_shapes["transformer.wte.weight"]
    weight_image = (package_path / "weights.bin").read_bytes()
    scale_image = (package_path / "scales.bin").read_bytes()
    state_dict, mapping = reference_adapter.reconstruct_state_dict(
        manifest, weight_image, scale_image, target_shapes
    )
    codes, scales, parameters = _tensor_images(manifest, weight_image, scale_image, state_dict)
    model = _ExactFixedPointModel(codes, scales, parameters, _load_finite_validator()).eval()
    receipt: dict[str, Any] = {
        "schema": "tinystories-1m-exact-package-model-v1",
        "status": "authenticated_fixed_point_model",
        "identity": {
            "contract_sha256": _sha256(contract_path),
            "audit_sha256": audit["sha256"],
            "fixed_profile_sha256": FROZEN_FIXED_PROFILE_SHA256,
            "package_manifest_sha256": contract["package"]["manifest_sha256"],
            "package_weights_sha256": contract["package"]["sha256"],
        },
        "execution": {
            "domain": "integers_only_after_materialization",
            "activation_codes": "signed_int8_saturated",
            "value_format": "signed_q16.16_int64_tensor",
            "scale_format": "unsigned_q8.24_int64_tensor",
            "gemv_accumulation": "ascending_input_index_signed_int64_twos_complement_wrap",
            "activation_rounding": "nearest_ties_away_from_zero",
        },
        "tensor_mapping": mapping,
        "activation_boundary_count": len(manifest["activation_scales"]),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return ExactModelBundle(
        contract=contract, audit=audit, profile=profile, manifest=manifest, model=model, receipt=receipt
    )


def export_exact_program(bundle: ExactModelBundle) -> torch.export.ExportedProgram:
    """Verify exported checkpoints, then return the logits-only exact program."""

    prompt = torch.tensor([bundle.contract["reference"]["prompt_tokens"]], dtype=torch.int64)
    with torch.no_grad():
        eager_logits, eager_checkpoints, _ = bundle.model._execute(prompt)
    trace_export = torch.export.export(_TraceOutputs(bundle.model).eval(), (prompt,), strict=False)
    with torch.no_grad():
        replay = trace_export.module()(prompt)
    replay_logits, replay_checkpoints = replay[0], replay[1:]
    checkpoint_hashes: dict[str, str] = {}
    for (name, shape), eager, exported in zip(
        CHECKPOINT_SHAPES.items(), eager_checkpoints, replay_checkpoints, strict=True
    ):
        _require(torch.equal(eager, exported), "export_checkpoint_mismatch", name)
        payload = {"shape": list(shape), "dtype": "signed_q16.16", "values": eager.cpu().tolist()}
        checkpoint_hashes[name] = canonical_sha256(payload)
    _require(torch.equal(eager_logits, replay_logits), "export_logits_mismatch", "trace export logits")
    logits_export = torch.export.export(bundle.model.eval(), (prompt,), strict=False)
    with torch.no_grad():
        logits_replay = logits_export.module()(prompt)
    _require(torch.equal(eager_logits, logits_replay), "export_logits_mismatch", "logits-only export")
    bundle.export_verification = {
        "status": "matched",
        "checkpoint_sha256": checkpoint_hashes,
        "final_logits_status": "matched",
        "final_logits_sha256": hashlib.sha256(eager_logits.cpu().numpy().astype("<i8").tobytes()).hexdigest(),
    }
    return logits_export
