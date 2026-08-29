#!/usr/bin/env python3
"""Authenticate the kev-gpt fixed softmax LUT and one token-step trace."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np


SCHEMA = "tinystories-1m-fixed-softmax-checkpoints-v1"
PROFILE_NAME = "fixed_hardware_reference"
EXPECTED_GIT_REVISION = "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f"
CANONICAL_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
CANONICAL_PROFILE_ARTIFACT_SHA256 = "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6"
CANONICAL_PROFILE_SHA256 = "7d54acda88f1d1a6979fd0ca8a3b0445e20ef127a399e5124a994427565caad0"
PROMPT_TOKENS = [7454, 2402, 257, 640]
NEXT_TOKEN = 11
TOKEN_INDEX = len(PROMPT_TOKENS) - 1
BLOCK_INDEX = 0
SPECIAL_ONE_Q1_20 = 1 << 20
EXPECTED_SOURCES = {
    "LICENSE": "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0",
    "tinystories/int_reference.py": "b6353d10d4227d676f78a7130af9a73fca2f0d68422f3215aec9307e0fb893d8",
    "tinystories/rtl_memories.py": "1b8bd74d09139ca6acd9bd26b8ad0dbc8326960d7a9997d003c5d99ad26e6fd6",
    "tinystories/hardware_reference.py": "3780015d7f4be69cae3952fb630af971a37490a17cf8519fd6ac81a7bb080371",
    "fpga/rtl/gptneo_attention.sv": "b42c1ed824198e49b685d827a49036bfb41ce6218e6a391a69208fbf48ef1ba9",
    "fpga/rtl/gptneo_iterative_divider.sv": "8665cc99e7bf98e0415775a36c78aa4ff242d30c976dce0719e6d465686a1540",
}


class FixedSoftmaxArtifactError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def row_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in row.items() if key != "sha256"})


def artifact_sha256(artifact: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in artifact.items() if key != "sha256"})


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FixedSoftmaxArtifactError(code, message)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FixedSoftmaxArtifactError("invalid_json", f"{label}: {error}") from error
    _require(isinstance(value, dict), "invalid_json", f"{label} must be a JSON object")
    return value


def _authenticate_reference_sources(reference_root: Path) -> dict[str, Any]:
    sources = []
    for relative, expected in EXPECTED_SOURCES.items():
        path = reference_root / relative
        _require(path.is_file(), "source_missing", relative)
        actual = sha256_file(path)
        _require(
            actual == expected,
            "source_hash_mismatch",
            f"{relative}: {actual} != {expected}",
        )
        sources.append({"path": relative, "sha256": actual})
    try:
        revision = subprocess.run(
            ["git", "-C", str(reference_root), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        selected = subprocess.run(
            ["git", "-C", str(reference_root), "status", "--porcelain", "--", *EXPECTED_SOURCES],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise FixedSoftmaxArtifactError(
            "git_identity_unavailable", error.stderr.strip()
        ) from error
    _require(
        revision == EXPECTED_GIT_REVISION,
        "git_revision_mismatch",
        f"{revision} != {EXPECTED_GIT_REVISION}",
    )
    _require(not selected, "source_worktree_dirty", selected)
    return {
        "kind": "content_authenticated_local_agpl_reference",
        "git_revision": revision,
        "selected_sources_clean_at_generation": True,
        "license": {"spdx": "AGPL-3.0-only", "sha256": EXPECTED_SOURCES["LICENSE"]},
        "sources": sources,
        "host_role": "transport_and_tokenizer_only",
        "host_inference_statement": "FPGA inference is not emulated by the host client",
    }


def _load_reference_modules(reference_root: Path) -> tuple[Any, Any, Any]:
    root = str(reference_root.resolve())
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    sys.modules.pop("tinystories", None)
    sys.modules.pop("tinystories.int_reference", None)
    sys.modules.pop("tinystories.rtl_memories", None)
    sys.modules.pop("tinystories.hardware_reference", None)
    int_reference = importlib.import_module("tinystories.int_reference")
    rtl_memories = importlib.import_module("tinystories.rtl_memories")
    hardware_reference = importlib.import_module("tinystories.hardware_reference")
    _require(
        Path(int_reference.__file__).resolve()
        == (reference_root / "tinystories/int_reference.py").resolve(),
        "module_origin_mismatch",
        str(int_reference.__file__),
    )
    _require(
        Path(rtl_memories.__file__).resolve()
        == (reference_root / "tinystories/rtl_memories.py").resolve(),
        "module_origin_mismatch",
        str(rtl_memories.__file__),
    )
    _require(
        Path(hardware_reference.__file__).resolve()
        == (reference_root / "tinystories/hardware_reference.py").resolve(),
        "module_origin_mismatch",
        str(hardware_reference.__file__),
    )
    return int_reference, rtl_memories, hardware_reference


def load_exp_lut(path: Path) -> list[int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise FixedSoftmaxArtifactError("exp_lut_missing", str(path)) from error
    _require(
        len(lines) == 4096,
        "exp_lut_format_mismatch",
        f"expected 4096 lines, found {len(lines)}",
    )
    values: list[int] = []
    for index, line in enumerate(lines):
        _require(
            len(line) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in line),
            "exp_lut_format_mismatch",
            f"line {index} is not a 6-digit hex word",
        )
        values.append(int(line, 16))
    return values


def materialize_authenticated_exp_lut(reference_root: Path, output_dir: Path) -> dict[str, Any]:
    reference_root = Path(reference_root)
    output_dir = Path(output_dir)
    _authenticate_reference_sources(reference_root)
    _, rtl_memories, _ = _load_reference_modules(reference_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = Path(rtl_memories.write_exp_lut(output_dir))
    _require(path.name == "gptneo_exp.mem", "exp_lut_name_mismatch", path.name)
    values = load_exp_lut(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    sample_indices = [0, 1, 256, 2048, 4094, 4095]
    return {
        "path": str(path),
        "file_name": path.name,
        "sha256": sha256_file(path),
        "line_count": len(lines),
        "line_width_hex": 6,
        "special_zero_delta_q1_20": SPECIAL_ONE_Q1_20,
        "sample_entries": [
            {"index": index, "hex": lines[index], "value_q1_20": values[index]}
            for index in sample_indices
        ],
    }


def _validate_profile(profile_path: Path) -> dict[str, Any]:
    _require(
        sha256_file(profile_path) == CANONICAL_PROFILE_ARTIFACT_SHA256,
        "profile_artifact_identity_mismatch",
        str(profile_path),
    )
    profile = _load_json(profile_path, "fixed-hardware profile")
    _require(
        profile.get("profile") == PROFILE_NAME,
        "profile_name_mismatch",
        str(profile.get("profile")),
    )
    _require(
        profile.get("profile_sha256") == CANONICAL_PROFILE_SHA256,
        "profile_identity_mismatch",
        str(profile.get("profile_sha256")),
    )
    _require(
        profile.get("profile_sha256")
        == canonical_sha256({key: value for key, value in profile.items() if key != "profile_sha256"}),
        "profile_hash_mismatch",
        "self hash",
    )
    trace = profile.get("software_trace")
    _require(isinstance(trace, dict), "profile_trace_missing", "software_trace")
    _require(
        trace.get("block_index") == BLOCK_INDEX and trace.get("token_index") == TOKEN_INDEX,
        "profile_trace_context_mismatch",
        "block/token",
    )
    _require(
        trace.get("prompt_tokens") == PROMPT_TOKENS and trace.get("next_token") == NEXT_TOKEN,
        "profile_trace_token_mismatch",
        "prompt/next token",
    )
    return profile


def _capture_fixed_attention(
    hardware_reference: Any, package: Path, prompt_tokens: list[int]
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, int]:
    model = hardware_reference.FixedGPTNeo(package)
    gemv_outputs: dict[str, np.ndarray] = {}
    attention_contexts: list[np.ndarray] = []
    original_gemv = model._gemv
    original_attention = model._attention

    def trace_gemv(
        values: np.ndarray,
        weight: str,
        bias: str | None,
        module: str,
        output_quantized: bool = True,
    ) -> np.ndarray:
        output = original_gemv(values, weight, bias, module, output_quantized)
        gemv_outputs[module] = np.array(output, copy=True)
        return output

    def trace_attention(query: np.ndarray, key: np.ndarray, value: np.ndarray) -> np.ndarray:
        output = original_attention(query, key, value)
        attention_contexts.append(np.array(output, copy=True))
        return output

    model._gemv = trace_gemv
    model._attention = trace_attention
    try:
        logits = model.forward(prompt_tokens)
    finally:
        model._gemv = original_gemv
        model._attention = original_attention

    block = "transformer.h.0"
    required = (
        f"{block}.attn.attention.q_proj",
        f"{block}.attn.attention.k_proj",
        f"{block}.attn.attention.v_proj",
        f"{block}.attn.attention.out_proj",
    )
    for module in required:
        _require(module in gemv_outputs, "softmax_trace_incomplete", module)
    _require(attention_contexts, "softmax_trace_incomplete", "attention")
    return (
        gemv_outputs,
        attention_contexts[0],
        np.array(logits[-1], copy=True),
        int(np.argmax(logits[-1])),
    )


def _trunc_divide(numerator: int, denominator: int) -> int:
    _require(denominator > 0, "softmax_denominator_invalid", str(denominator))
    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


def _trace_softmax_row(
    head: int,
    query: np.ndarray,
    key_rows: np.ndarray,
    value_rows: np.ndarray,
    exp_lut: list[int],
) -> dict[str, Any]:
    scores: list[int] = []
    for row in key_rows.tolist():
        total = sum(int(lhs) * int(rhs) for lhs, rhs in zip(query.tolist(), row, strict=True))
        scores.append(total >> 24)
    max_score = max(scores)
    deltas = [max(-4096, min(0, score - max_score)) for score in scores]
    exp_indices = [None if delta == 0 else 4096 + delta for delta in deltas]
    exp_values = [
        SPECIAL_ONE_Q1_20 if index is None else exp_lut[index] for index in exp_indices
    ]
    denominator = sum(exp_values)
    numerators = []
    rounded = []
    context = []
    for column in range(value_rows.shape[1]):
        numerator = sum(
            exp * int(value_rows[row_index, column])
            for row_index, exp in enumerate(exp_values)
        )
        numerators.append(numerator)
        rounded_value = numerator - (denominator // 2) if numerator < 0 else numerator + (denominator // 2)
        rounded.append(rounded_value)
        context.append(_trunc_divide(rounded_value, denominator))
    row = {
        "head": head,
        "query_q16_16": [int(value) for value in query.tolist()],
        "key_rows_q16_16": [[int(value) for value in row] for row in key_rows.tolist()],
        "value_rows_q16_16": [[int(value) for value in row] for row in value_rows.tolist()],
        "score_codes_q8_8": scores,
        "max_score_code_q8_8": max_score,
        "delta_codes_q8_8": deltas,
        "exp_lut_indices": exp_indices,
        "exp_q1_20": exp_values,
        "denominator_q1_20": denominator,
        "numerators_q16_36": numerators,
        "rounded_numerators_q16_36": rounded,
        "probabilities_q1_20": [_trunc_divide(exp << 20, denominator) for exp in exp_values],
        "context_q16_16": context,
    }
    row["sha256"] = row_sha256(row)
    return row


def _payload(shape: list[int], values: list[int]) -> dict[str, Any]:
    payload = {"shape": shape, "dtype": "signed_q16.16", "values": values}
    return {**payload, "sha256": canonical_sha256(payload)}


def build_artifact(
    contract_path: Path,
    profile_path: Path,
    reference_root: Path,
    package_path: Path,
) -> dict[str, Any]:
    contract_path = Path(contract_path)
    profile_path = Path(profile_path)
    reference_root = Path(reference_root)
    package_path = Path(package_path)
    _require(
        sha256_file(contract_path) == CANONICAL_CONTRACT_SHA256,
        "contract_artifact_identity_mismatch",
        str(contract_path),
    )
    contract = _load_json(contract_path, "contract")
    profile = _validate_profile(profile_path)
    authority = _authenticate_reference_sources(reference_root)
    for name, expected in contract.get("package", {}).get("files", {}).items():
        path = package_path / name
        _require(path.is_file(), "package_file_missing", name)
        _require(
            sha256_file(path) == expected,
            "package_identity_mismatch",
            name,
        )
    int_reference, _, hardware_reference = _load_reference_modules(reference_root)
    with tempfile.TemporaryDirectory() as temporary:
        exp_meta = materialize_authenticated_exp_lut(reference_root, Path(temporary))
        exp_lut = load_exp_lut(Path(exp_meta["path"]))
    gemv_outputs, attention_context, logits, next_token = _capture_fixed_attention(
        hardware_reference, package_path, PROMPT_TOKENS
    )
    _require(next_token == NEXT_TOKEN, "runtime_token_mismatch", str(next_token))
    block = "transformer.h.0"
    q_all = gemv_outputs[f"{block}.attn.attention.q_proj"]
    k_all = gemv_outputs[f"{block}.attn.attention.k_proj"]
    v_all = gemv_outputs[f"{block}.attn.attention.v_proj"]
    out_all = gemv_outputs[f"{block}.attn.attention.out_proj"]
    sequence_length = TOKEN_INDEX + 1
    rows = []
    context_values: list[int] = []
    for head in range(16):
        start = head * 4
        stop = start + 4
        row = _trace_softmax_row(
            head=head,
            query=np.asarray(q_all[TOKEN_INDEX, start:stop], dtype=np.int64),
            key_rows=np.asarray(k_all[:sequence_length, start:stop], dtype=np.int64),
            value_rows=np.asarray(v_all[:sequence_length, start:stop], dtype=np.int64),
            exp_lut=exp_lut,
        )
        rows.append(row)
        context_values.extend(row["context_q16_16"])
    runtime_context = [int(value) for value in attention_context[TOKEN_INDEX].tolist()]
    runtime_output = [int(value) for value in out_all[TOKEN_INDEX].tolist()]
    _require(
        context_values == runtime_context,
        "softmax_context_mismatch",
        "derived context differs from authenticated runtime",
    )
    profile_trace = profile["software_trace"]["checkpoints"]
    profile_binding = {
        "profile_artifact_sha256": sha256_file(profile_path),
        "profile_sha256": profile["profile_sha256"],
        "checkpoint_matches": {
            "block.attention.q": q_all[TOKEN_INDEX].reshape(16, 4).tolist()
            == profile_trace["block.attention.q"]["values"],
            "block.attention.k": k_all[TOKEN_INDEX].reshape(16, 4).tolist()
            == profile_trace["block.attention.k"]["values"],
            "block.attention.v": v_all[TOKEN_INDEX].reshape(16, 4).tolist()
            == profile_trace["block.attention.v"]["values"],
            "block.attention.output": runtime_output
            == profile_trace["block.attention.output"]["values"],
        },
        "profile_missing_pre_out_proj_context": (
            "The fixed-hardware profile does not expose the pre-out-proj attention context; "
            "this artifact adds it by authenticated rerun of the fixed runtime."
        ),
    }
    _require(
        all(profile_binding["checkpoint_matches"].values()),
        "profile_binding_mismatch",
        json.dumps(profile_binding["checkpoint_matches"], sort_keys=True),
    )
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "runtime_authenticated_not_board_checkpoint_authenticated",
        "board_authenticated": False,
        "identity": {
            "contract_sha256": sha256_file(contract_path),
            "package_manifest_sha256": sha256_file(package_path / "manifest.json"),
            "package_weights_sha256": sha256_file(package_path / "weights.bin"),
            "package_scales_sha256": sha256_file(package_path / "scales.bin"),
            "package_calibration_ids_sha256": sha256_file(package_path / "calibration_ids.bin"),
            "reference_root": str(reference_root),
        },
        "authority": authority,
        "profile_binding": profile_binding,
        "exp_lut": {
            "file_name": "gptneo_exp.mem",
            "sha256": exp_meta["sha256"],
            "line_count": 4096,
            "line_width_hex": 6,
            "entry_encoding": "unsigned Q1.20 hex words for exp((index-4096)/256), indices 0..4095",
            "special_zero_delta_q1_20": SPECIAL_ONE_Q1_20,
            "generator": {
                "path": "tinystories/rtl_memories.py",
                "symbol": "write_exp_lut",
                "sha256": EXPECTED_SOURCES["tinystories/rtl_memories.py"],
                "transitive_dependencies": [
                    {
                        "path": "tinystories/int_reference.py",
                        "sha256": EXPECTED_SOURCES["tinystories/int_reference.py"],
                    }
                ],
            },
            "consumers": [
                {
                    "path": "tinystories/hardware_reference.py",
                    "symbol": "EXP_TABLE",
                    "sha256": EXPECTED_SOURCES["tinystories/hardware_reference.py"],
                },
                {
                    "path": "fpga/rtl/gptneo_attention.sv",
                    "symbol": "exp_lut",
                    "sha256": EXPECTED_SOURCES["fpga/rtl/gptneo_attention.sv"],
                },
            ],
            "sample_entries": exp_meta["sample_entries"],
        },
        "slice": {
            "kind": "one_transformer_block_token_step",
            "block_index": BLOCK_INDEX,
            "token_index": TOKEN_INDEX,
            "prompt_tokens": PROMPT_TOKENS,
            "next_token": next_token,
            "num_heads": 16,
            "head_dim": 4,
            "sequence_length": sequence_length,
        },
        "softmax_rows": rows,
        "attention_context_q16_16": _payload([64], runtime_context),
        "attention_output_q16_16": _payload([64], runtime_output),
        "last_token_logits_q16_16_sha256": canonical_sha256([int(value) for value in logits.tolist()]),
        "unresolved_board_authority": {
            "code": "board_checkpoint_receipt_missing",
            "required": (
                "A content-bound TinyStories-1M board receipt reproducing this exact "
                "gptneo_exp.mem hash and the block-0/token-3 softmax checkpoints."
            ),
        },
    }
    artifact["sha256"] = artifact_sha256(artifact)
    return artifact


def validate_artifact(
    artifact_path: Path,
    contract_path: Path,
    profile_path: Path,
    reference_root: Path,
    package_path: Path,
) -> dict[str, Any]:
    actual = _load_json(Path(artifact_path), "fixed softmax artifact")
    expected = build_artifact(contract_path, profile_path, reference_root, package_path)
    _require(actual == expected, "artifact_content_mismatch", str(artifact_path))
    _require(actual.get("sha256") == artifact_sha256(actual), "artifact_hash_mismatch", "self hash")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--emit-exp-mem", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        validate_artifact(
            args.output, args.contract, args.profile, args.reference_root, args.package
        )
        return
    artifact = build_artifact(
        args.contract, args.profile, args.reference_root, args.package
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if args.emit_exp_mem is not None:
        materialize_authenticated_exp_lut(args.reference_root, args.emit_exp_mem.parent)
        generated = args.emit_exp_mem.parent / "gptneo_exp.mem"
        if generated != args.emit_exp_mem:
            args.emit_exp_mem.write_bytes(generated.read_bytes())


if __name__ == "__main__":
    main()
