#!/usr/bin/env python3
"""Prove exact eager/exported greedy generation for the frozen TinyStories-1M input."""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from TinyStories.model_adapter_exact_package import (
    CHECKPOINT_SHAPES,
    GEMV_NAMES,
    NONLINEAR_BOUNDARY_NAMES,
    QDQ_BOUNDARY_NAMES,
    ExactModelBundle,
    _TraceOutputs,
    _named_tensor_state_sha256,
    canonical_sha256,
    exported_program_identity,
    load_exact_model,
)


SCHEMA = "tinystories-1m-exact-generation-v1"
PROMPT_IDS = [7454, 2402, 257, 640]
FROZEN_TOKENS = [
    11, 612, 373, 257, 1310, 2576, 3706, 20037,
    13, 1375, 6151, 284, 711, 2354, 287, 262,
]
TASK_1_COMMIT = "c8eb2011ee09c368accdf8efd67c50dfc5564679"
TASK_2_COMMIT = "a2eda783819bbfb35a833d1a45d3dd125a176973"
TASK_1_CONTRACT_SHA256 = "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c"
TASK_1_AUDIT_FILE_SHA256 = "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd"
TASK_2_ARTIFACT_FILE_SHA256 = "3bc578d7f13263f438d8e7d3f4d3b80386afa89accb859da74d1a4404606eae7"
TASK_2_ARTIFACT_SHA256 = "8f74d35cc90d534fb385608c9cdf1f6f5bb0a5aad83eb6c34133e4b7b6f1e938"
TASK_2_MODEL_RECEIPT_SHA256 = "f061dbf4f91bf5389acb0f27ce4b9e672f6f3831478907e01900e60e8869235b"
TASK_2_ARTIFACT_RELATIVE = Path("artifacts/reference/tinystories-1m-exact-package-model.json")
CONTRACT_RELATIVE = Path("artifacts/reference/tinystories-1m-exact-input-contract.json")
AUDIT_RELATIVE = Path("artifacts/reference/tinystories-1m-exact-input-audit.json")
VERIFIER_RELATIVE = Path("scripts/comparison/verify_tinystories_1m_exact_generation.py")
TEST_RELATIVE = Path("tests/test_tinystories_1m_exact_generation.py")


class ExactGenerationError(ValueError):
    """Generation evidence is incomplete, mismatched, or unauthenticated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ExactGenerationError(code, message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExactGenerationError("invalid_json", f"{path}: {error}") from error
    _require(isinstance(value, dict), "invalid_json", f"{path} must contain an object")
    return value


def _task_2_artifact_sha256(value: Mapping[str, Any]) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != "artifact_sha256"})


def _authenticate_authority(bundle: ExactModelBundle, repo_root: Path) -> dict[str, Any]:
    """Authenticate the exact Task 1/2 boundary before any candidate execution."""

    repo_root = Path(repo_root)
    contract_path = repo_root / CONTRACT_RELATIVE
    audit_path = repo_root / AUDIT_RELATIVE
    task_2_path = repo_root / TASK_2_ARTIFACT_RELATIVE
    _require(_sha256(contract_path) == TASK_1_CONTRACT_SHA256,
             "task_1_identity_mismatch", "contract file drifted")
    _require(_sha256(audit_path) == TASK_1_AUDIT_FILE_SHA256,
             "task_1_identity_mismatch", "audit file drifted")
    _require(_sha256(task_2_path) == TASK_2_ARTIFACT_FILE_SHA256,
             "task_2_identity_mismatch", "exact-model artifact file drifted")

    task_2 = _load_json(task_2_path)
    _require(task_2.get("artifact_sha256") == TASK_2_ARTIFACT_SHA256
             and _task_2_artifact_sha256(task_2) == TASK_2_ARTIFACT_SHA256,
             "task_2_identity_mismatch", "exact-model artifact self hash drifted")
    source_files = task_2.get("identity", {}).get("source_files", {})
    _require(isinstance(source_files, dict) and source_files,
             "task_2_identity_mismatch", "exact-model source closure is missing")
    for relative, expected in source_files.items():
        path = repo_root / relative
        _require(path.is_file() and _sha256(path) == expected,
                 "task_2_identity_mismatch", f"source drift: {relative}")

    receipt = bundle.receipt
    receipt_payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    _require(receipt.get("status") == "authenticated_fixed_point_model"
             and receipt.get("receipt_sha256") == canonical_sha256(receipt_payload)
             and receipt.get("receipt_sha256") == TASK_2_MODEL_RECEIPT_SHA256
             and task_2.get("identity", {}).get("model_receipt_sha256") == TASK_2_MODEL_RECEIPT_SHA256,
             "task_2_receipt_mismatch", "exact model receipt is not the accepted Task 2 receipt")
    independent = receipt.get("independent_logits_oracle", {})
    _require(independent.get("status") == "full_logits_bit_exact"
             and independent.get("canonical_sha256") == bundle.oracle.get("logits", {}).get("canonical_sha256"),
             "task_2_oracle_mismatch", "independent fixed-logits oracle is not authenticated")
    authenticated_model_state = task_2.get("exported_program", {}).get("state_dict_sha256")
    actual_model_state = _named_tensor_state_sha256(bundle.model.state_dict())
    _require(actual_model_state == authenticated_model_state,
             "task_2_model_state_mismatch", "live exact-model state differs from Task 2 export")
    _require(bundle.contract.get("reference", {}).get("prompt_tokens") == PROMPT_IDS
             and bundle.contract.get("reference", {}).get("tokens") == FROZEN_TOKENS,
             "task_1_identity_mismatch", "bundle reference fixture drifted")

    return {
        "task_1": {
            "commit": TASK_1_COMMIT,
            "contract_file_sha256": TASK_1_CONTRACT_SHA256,
            "audit_file_sha256": TASK_1_AUDIT_FILE_SHA256,
            "audit_payload_sha256": bundle.audit["sha256"],
        },
        "task_2": {
            "commit": TASK_2_COMMIT,
            "artifact_file_sha256": TASK_2_ARTIFACT_FILE_SHA256,
            "artifact_sha256": TASK_2_ARTIFACT_SHA256,
            "model_receipt_sha256": TASK_2_MODEL_RECEIPT_SHA256,
            "fixed_logits_oracle_sha256": bundle.oracle["oracle_sha256"],
            "fixed_logits_vector_sha256": independent["canonical_sha256"],
            "model_state_sha256": actual_model_state,
        },
    }


def _tensor_sha256(tensor: torch.Tensor, semantic_dtype: str) -> str:
    value = tensor.detach().cpu().to(torch.int64).contiguous()
    payload = {
        "shape": list(value.shape),
        "dtype": semantic_dtype,
        "values": value.tolist(),
    }
    return canonical_sha256(payload)


def _little_endian_int64_sha256(tensor: torch.Tensor) -> str:
    value = tensor.detach().cpu().to(torch.int64).contiguous()
    return hashlib.sha256(value.numpy().astype("<i8", copy=False).tobytes()).hexdigest()


def _execution_observations(outputs: Sequence[torch.Tensor]) -> dict[str, Any]:
    checkpoint_end = 1 + len(CHECKPOINT_SHAPES)
    qdq_end = checkpoint_end + len(QDQ_BOUNDARY_NAMES) * 3
    accumulator_end = qdq_end + len(GEMV_NAMES)
    nonlinear_end = accumulator_end + len(NONLINEAR_BOUNDARY_NAMES)
    _require(len(outputs) == nonlinear_end, "trace_schema_mismatch", str(len(outputs)))

    logits = outputs[0]
    last_logits = logits[0, -1]
    checkpoint_hashes = {
        name: _tensor_sha256(tensor, "signed_q16.16")
        for name, tensor in zip(CHECKPOINT_SHAPES, outputs[1:checkpoint_end], strict=True)
    }
    qdq_hashes: dict[str, dict[str, str]] = {}
    qdq = outputs[checkpoint_end:qdq_end]
    for index, name in enumerate(QDQ_BOUNDARY_NAMES):
        tensors = qdq[index * 3:index * 3 + 3]
        qdq_hashes[name] = {
            semantic: _tensor_sha256(tensor, dtype)
            for semantic, tensor, dtype in zip(
                ("codes", "scales", "dequantized"),
                tensors,
                ("signed_int8_codes", "unsigned_q8.24", "signed_q16.16"),
                strict=True,
            )
        }
    accumulator_hashes = {
        name: _tensor_sha256(tensor, "signed_int64_serial_accumulator")
        for name, tensor in zip(GEMV_NAMES, outputs[qdq_end:accumulator_end], strict=True)
    }
    nonlinear_hashes = {
        name: _tensor_sha256(tensor, "signed_q16.16")
        for name, tensor in zip(
            NONLINEAR_BOUNDARY_NAMES, outputs[accumulator_end:nonlinear_end], strict=True
        )
    }
    observation_groups = {
        "checkpoint_sha256": checkpoint_hashes,
        "qdq_boundary_sha256": qdq_hashes,
        "gemv_accumulator_sha256": accumulator_hashes,
        "nonlinear_boundary_sha256": nonlinear_hashes,
    }
    return {
        "logits_shape": list(last_logits.shape),
        "logits_dtype": "signed_fixed_point_int64",
        "logits_sha256": _tensor_sha256(last_logits, "signed_fixed_point_logits"),
        "logits_little_endian_int64_sha256": _little_endian_int64_sha256(last_logits),
        "full_context_logits_sha256": _tensor_sha256(logits, "signed_fixed_point_logits"),
        **observation_groups,
        "observation_sha256": canonical_sha256(observation_groups),
    }


def select_greedy_token(logits: Sequence[int] | torch.Tensor) -> tuple[int, int]:
    """Select top-1, explicitly resolving equal maxima to the smallest token ID."""

    values = torch.as_tensor(logits, dtype=torch.int64).flatten()
    _require(values.numel() > 0, "empty_logits", "at least one logit is required")
    maximum = torch.max(values)
    tied_ids = torch.nonzero(values == maximum, as_tuple=False).flatten()
    return int(torch.min(tied_ids)), int(tied_ids.numel())


class _StaticExportCache:
    """One honest static trace export per input length, replayable for any token values."""

    def __init__(self, bundle: ExactModelBundle) -> None:
        self._bundle = bundle
        self._active_length: int | None = None
        self._active_program: torch.export.ExportedProgram | None = None
        self._identities: dict[int, dict[str, Any]] = {}
        self.replay_count = 0

    def export_length(self, length: int) -> None:
        _require(length not in self._identities, "duplicate_static_export", str(length))
        _require(self._active_program is None, "static_export_not_released", str(self._active_length))
        example = torch.zeros((1, length), dtype=torch.int64)
        self._active_program = torch.export.export(
            _TraceOutputs(self._bundle.model).eval(), (example,), strict=False
        )
        self._active_length = length
        self._identities[length] = exported_program_identity(self._active_program)

    def replay(self, context: torch.Tensor) -> tuple[torch.Tensor, ...]:
        length = int(context.shape[1])
        _require(self._active_program is not None and self._active_length == length,
                 "static_export_length_mismatch", str(length))
        with torch.no_grad():
            outputs = self._active_program.module()(context)
        self.replay_count += 1
        return tuple(outputs)

    def release(self) -> None:
        self._active_program = None
        self._active_length = None
        gc.collect()

    def program_identity(self, length: int) -> dict[str, Any]:
        return self._identities[length]

    def summary(self) -> dict[str, Any]:
        return {
            "strategy": "one_static_trace_export_per_context_length",
            "context_lengths": sorted(self._identities),
            "export_count": len(self._identities),
            "replay_count": self.replay_count,
            "programs": {str(length): identity for length, identity in sorted(self._identities.items())},
            "cache_sha256": canonical_sha256({
                str(length): identity for length, identity in sorted(self._identities.items())
            }),
        }


def _fresh_bundle(bundle: ExactModelBundle) -> ExactModelBundle:
    """Materialize a new bundle and model instance from authenticated in-memory state."""

    return ExactModelBundle(
        contract=copy.deepcopy(bundle.contract),
        audit=copy.deepcopy(bundle.audit),
        profile=copy.deepcopy(bundle.profile),
        certificate=copy.deepcopy(bundle.certificate),
        oracle=copy.deepcopy(bundle.oracle),
        oracle_logits=bundle.oracle_logits.detach().clone(),
        manifest=copy.deepcopy(bundle.manifest),
        model=copy.deepcopy(bundle.model),
        receipt=copy.deepcopy(bundle.receipt),
    )


def _first_mapping_mismatch(
    expected: Mapping[str, Any], actual: Mapping[str, Any], prefix: list[str] | None = None
) -> list[str] | None:
    prefix = [] if prefix is None else prefix
    for key in expected:
        path = prefix + [key]
        if key not in actual:
            return path
        expected_value = expected[key]
        actual_value = actual[key]
        if isinstance(expected_value, Mapping) and isinstance(actual_value, Mapping):
            nested = _first_mapping_mismatch(expected_value, actual_value, path)
            if nested is not None:
                return nested
        elif expected_value != actual_value:
            return path
    for key in actual:
        if key not in expected:
            return prefix + [key]
    return None


def _mapping_path_value(value: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def verify_generation(
    bundle: ExactModelBundle,
    prompt_ids: Sequence[int],
    expected_tokens: Sequence[int],
    count: int = 3,
) -> dict[str, object]:
    """Run three fresh exact models and compare all 16 eager/exported steps."""

    _require(isinstance(bundle, ExactModelBundle), "bundle_type_mismatch", "ExactModelBundle required")
    _require(list(prompt_ids) == PROMPT_IDS, "prompt_identity_mismatch", str(list(prompt_ids)))
    _require(list(expected_tokens) == FROZEN_TOKENS,
             "expected_tokens_identity_mismatch", str(list(expected_tokens)))
    _require(count == 3, "generation_count_mismatch", "exactly three fresh runs are required")
    authority = _authenticate_authority(bundle, REPO_ROOT)
    cache = _StaticExportCache(bundle)
    fresh_bundles = [_fresh_bundle(bundle) for _ in range(count)]
    for run_index, fresh in enumerate(fresh_bundles):
        _require(fresh is not bundle and fresh.model is not bundle.model,
                 "fresh_bundle_failure", str(run_index + 1))
        _require(fresh.receipt == bundle.receipt,
                 "task_2_receipt_mismatch", f"fresh bundle {run_index + 1}")
    contexts = [list(prompt_ids) for _ in range(count)]
    generated_runs: list[list[int]] = [[] for _ in range(count)]
    step_runs: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    first_mismatch: dict[str, Any] | None = None

    for step_index, expected_token in enumerate(expected_tokens):
        length = len(prompt_ids) + step_index
        cache.export_length(length)
        for run_index, fresh in enumerate(fresh_bundles):
            context = contexts[run_index]
            input_ids = torch.tensor([context], dtype=torch.int64)
            with torch.no_grad():
                eager_outputs = fresh.model._execute(input_ids)
            eager_flat = (
                (eager_outputs[0],) + eager_outputs[1] + eager_outputs[2]
                + eager_outputs[3] + eager_outputs[4]
            )
            exported_flat = cache.replay(input_ids)
            eager = _execution_observations(eager_flat)
            exported = _execution_observations(exported_flat)
            mismatch_path = _first_mapping_mismatch(eager, exported)
            eager_token, tie_count = select_greedy_token(eager_outputs[0][0, -1])
            exported_token, exported_tie_count = select_greedy_token(exported_flat[0][0, -1])
            mismatch: dict[str, Any] | None = None
            if mismatch_path is not None:
                mismatch = {
                    "code": "eager_export_mismatch",
                    "field_path": mismatch_path,
                    "eager": _mapping_path_value(eager, mismatch_path),
                    "exported": _mapping_path_value(exported, mismatch_path),
                }
            elif eager_token != exported_token or tie_count != exported_tie_count:
                mismatch = {
                    "code": "eager_export_token_mismatch",
                    "eager_token": eager_token,
                    "exported_token": exported_token,
                    "eager_tie_count": tie_count,
                    "exported_tie_count": exported_tie_count,
                }
            elif eager_token != expected_token:
                mismatch = {
                    "code": "frozen_token_mismatch",
                    "expected_token": expected_token,
                    "actual_token": eager_token,
                }
            step: dict[str, Any] = {
                "step_index": step_index,
                "context_length": len(context),
                "context_sha256": canonical_sha256(context),
                "expected_token": expected_token,
                "selected_token": eager_token,
                "tie_count": tie_count,
                "tie_breaking": "smallest_token_id_among_equal_maxima",
                "eager": eager,
                "exported": exported,
                "exported_program_sha256": cache.program_identity(len(context))["program_sha256"],
                "comparison_status": "matched" if mismatch is None else "mismatch",
                "mismatch": mismatch,
            }
            step["step_sha256"] = canonical_sha256(step)
            step_runs[run_index].append(step)
            if mismatch is not None:
                first_mismatch = {
                    "run_index": run_index,
                    "step_index": step_index,
                    "context_length": len(context),
                    **mismatch,
                }
                break
            generated_runs[run_index].append(eager_token)
            context.append(eager_token)
        cache.release()
        if first_mismatch is not None:
            break

    runs: list[dict[str, Any]] = []
    for run_index, fresh in enumerate(fresh_bundles):
        transcript_payload = {
            "prompt_ids": list(prompt_ids),
            "tokens": generated_runs[run_index],
            "step_sha256": [step["step_sha256"] for step in step_runs[run_index]],
            "model_receipt_sha256": fresh.receipt["receipt_sha256"],
        }
        transcript_sha256 = canonical_sha256(transcript_payload)
        run = {
            "run_index": run_index,
            "bundle_instance": run_index + 1,
            "bundle_materialization": "fresh_deep_copy_of_authenticated_exact_bundle",
            "model_receipt_sha256": fresh.receipt["receipt_sha256"],
            "model_state_sha256": _named_tensor_state_sha256(fresh.model.state_dict()),
            "tokens": generated_runs[run_index],
            "steps": step_runs[run_index],
            "transcript_sha256": transcript_sha256,
        }
        run["run_sha256"] = canonical_sha256(run)
        runs.append(run)

    transcript_hashes = [run["transcript_sha256"] for run in runs]
    matched = first_mismatch is None and len(runs) == count and all(
        run["tokens"] == list(expected_tokens) for run in runs
    ) and len(set(transcript_hashes)) == 1
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "matched" if matched else "mismatch",
        "authority": authority,
        "prompt_ids": list(prompt_ids),
        "expected_tokens": list(expected_tokens),
        "context_lengths": list(range(len(prompt_ids), len(prompt_ids) + len(expected_tokens))),
        "execution_modes": ["eager", "torch_export_static_per_length"],
        "runs": runs,
        "export_cache": cache.summary(),
        "determinism": {
            "required_runs": count,
            "completed_runs": len(runs),
            "run_transcript_sha256": transcript_hashes,
            "all_transcripts_identical": (
                len(transcript_hashes) == count and len(set(transcript_hashes)) == 1
            ),
            "three_run_sha256": canonical_sha256(transcript_hashes),
        },
        "first_mismatch": first_mismatch,
        "compiler_model_registration": {
            "performed": False,
            "gate": "open_for_later_lowering" if matched else "closed",
        },
    }
    result["result_sha256"] = canonical_sha256(result)
    return result


def artifact_sha256(value: Mapping[str, Any]) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != "artifact_sha256"})


def build_artifact(repo_root: Path, result: Mapping[str, Any]) -> dict[str, Any]:
    repo_root = Path(repo_root)
    _require(result.get("status") == "matched" and result.get("first_mismatch") is None,
             "generation_not_matched", "refusing to register mismatched generation evidence")
    identity = copy.deepcopy(result["authority"])
    identity["sources"] = {
        str(relative): _sha256(repo_root / relative)
        for relative in (VERIFIER_RELATIVE, TEST_RELATIVE)
    }
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "exact_generation_matched",
        "identity": identity,
        "generation": copy.deepcopy(dict(result)),
        "claims": {
            "all_sixteen_steps_compared": True,
            "eager_export_observations_bit_exact": True,
            "three_fresh_bundle_runs_deterministic": True,
            "external_oracle_used_as_candidate": False,
            "compiler_model_registered": False,
        },
    }
    artifact["artifact_sha256"] = artifact_sha256(artifact)
    return artifact


def validate_artifact(value: Mapping[str, Any], repo_root: Path,
                      expected_result: Mapping[str, Any]) -> None:
    expected = build_artifact(repo_root, expected_result)
    if value.get("artifact_sha256") != artifact_sha256(value):
        raise ExactGenerationError("artifact_self_hash_mismatch", "generation artifact")
    if value != expected:
        raise ExactGenerationError("artifact_evidence_mismatch", "current identities or execution differ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = load_exact_model(args.contract, args.package, args.model_path)
    result = verify_generation(bundle, PROMPT_IDS, FROZEN_TOKENS, count=3)
    artifact = build_artifact(REPO_ROOT, result)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(artifact["artifact_sha256"])


if __name__ == "__main__":
    main()
