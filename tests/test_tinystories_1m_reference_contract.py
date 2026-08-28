"""Strict loader for the frozen TinyStories-1M reference contract."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "artifacts" / "reference" / "tinystories-1m-kev-gpt-contract.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load_contract() -> dict:
    if not CONTRACT_PATH.is_file():
        raise AssertionError(f"missing reference contract: {CONTRACT_PATH}")
    contract = json.loads(CONTRACT_PATH.read_text())
    required = {"schema_version", "status", "model", "package", "tokenizer", "quantization", "memory_image", "command_abi", "reference", "baseline", "incomplete_reasons"}
    missing = required - contract.keys()
    if missing:
        raise AssertionError(f"contract missing fields: {sorted(missing)}")
    if contract["schema_version"] != 1 or not isinstance(contract["status"], str):
        raise AssertionError("invalid contract header")
    model = contract["model"]
    if not isinstance(model, dict):
        raise AssertionError("model must be an object")
    model_required = {"name", "architecture", "source_model_id", "source_revision", "n_layer", "hidden_size", "n_head", "head_dim", "vocab_size", "max_context", "tie_word_embeddings", "activation_function"}
    if model_required - model.keys():
        raise AssertionError(f"model missing fields: {sorted(model_required - model.keys())}")
    expected = {"name": "TinyStories-1M", "n_layer": 8, "hidden_size": 64, "n_head": 16, "head_dim": 4, "vocab_size": 50257, "max_context": 32}
    for key, value in expected.items():
        if model.get(key) != value:
            raise AssertionError(f"model.{key} must be {value!r}")
    if not all(isinstance(model[key], int) and not isinstance(model[key], bool) for key in ("n_layer", "hidden_size", "n_head", "head_dim", "vocab_size", "max_context")):
        raise AssertionError("model dimensions must be integers")
    if not isinstance(model["tie_word_embeddings"], bool) or not all(isinstance(model[key], str) for key in ("name", "architecture", "source_model_id", "source_revision", "activation_function")):
        raise AssertionError("model metadata types are malformed")
    for section in ("package", "tokenizer", "memory_image"):
        if not isinstance(contract[section], dict):
            raise AssertionError(f"{section} must be an object")
        digest = contract[section].get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise AssertionError(f"{section}.sha256 is not a lowercase SHA-256 digest")
    package = contract["package"]
    for key in ("origin", "manifest_sha256", "files"):
        if key not in package:
            raise AssertionError(f"package.{key} is required")
    if not SHA256.fullmatch(package["manifest_sha256"]):
        raise AssertionError("package.manifest_sha256 is malformed")
    if not isinstance(package["files"], dict) or not package["files"]:
        raise AssertionError("package.files must be a non-empty object")
    if not isinstance(package["origin"], str) or not package["origin"]:
        raise AssertionError("package.origin must be a non-empty string")
    for filename, digest in package["files"].items():
        if not isinstance(filename, str) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise AssertionError(f"package.files.{filename} is malformed")
    tokenizer = contract["tokenizer"]
    for key in ("type", "vocab_sha256", "merges_sha256", "add_bos_token", "add_prefix_space"):
        if key not in tokenizer:
            raise AssertionError(f"tokenizer.{key} is required")
    for key in ("vocab_sha256", "merges_sha256"):
        if not SHA256.fullmatch(tokenizer[key]):
            raise AssertionError(f"tokenizer.{key} is malformed")
    if not isinstance(tokenizer["add_bos_token"], bool) or not isinstance(tokenizer["add_prefix_space"], bool):
        raise AssertionError("tokenizer boolean settings are malformed")
    quant = contract["quantization"]
    for key in ("weights", "activations", "accumulator", "scale_format", "scale_image_sha256"):
        if key not in quant or not isinstance(quant[key], str):
            raise AssertionError(f"quantization.{key} is required")
    if not SHA256.fullmatch(quant["scale_image_sha256"]):
        raise AssertionError("quantization.scale_image_sha256 is malformed")
    if not isinstance(contract["memory_image"].get("bytes"), int) or contract["memory_image"]["bytes"] <= 0:
        raise AssertionError("memory_image.bytes must be positive")
    abi = contract["command_abi"]
    for key in ("request_magic", "reply_magic", "version", "command", "max_context", "token_id_bits", "generation_count_bits", "cycle_count_bits", "crc32"):
        if key not in abi:
            raise AssertionError(f"command_abi.{key} is required")
    if not all(isinstance(abi[key], int) and not isinstance(abi[key], bool) and abi[key] > 0 for key in ("version", "max_context", "token_id_bits", "generation_count_bits", "cycle_count_bits")):
        raise AssertionError("command_abi numeric fields are malformed")
    if not all(isinstance(abi[key], str) and re.fullmatch(r"0x[0-9a-f]{4}", abi[key]) for key in ("request_magic", "reply_magic")):
        raise AssertionError("command_abi magic values are malformed")
    reference = contract["reference"]
    reference_required = {"prompt_text", "prompt_tokens", "tokens", "generation", "reference_impl", "reference_trace_sha256"}
    if not isinstance(reference, dict) or reference_required - reference.keys():
        raise AssertionError("reference fields are incomplete")
    if reference.get("prompt_text") != "Once upon a time":
        raise AssertionError("reference prompt fixture changed")
    if reference.get("prompt_tokens") != [7454, 2402, 257, 640]:
        raise AssertionError("reference prompt token IDs changed")
    if not isinstance(reference["prompt_text"], str) or not isinstance(reference["generation"], str) or not isinstance(reference["reference_impl"], str):
        raise AssertionError("reference metadata types are malformed")
    trace_hash = reference["reference_trace_sha256"]
    if trace_hash is not None and (not isinstance(trace_hash, str) or not SHA256.fullmatch(trace_hash)):
        raise AssertionError("reference_trace_sha256 must be null or a SHA-256 digest")
    tokens = reference.get("tokens")
    if not isinstance(tokens, list) or len(tokens) != 16 or any(not isinstance(t, int) for t in tokens):
        raise AssertionError("reference.tokens must contain exactly 16 integer IDs")
    if contract["status"] not in {"frozen", "incomplete"}:
        raise AssertionError("unknown contract status")
    if not isinstance(contract["incomplete_reasons"], list) or any(not isinstance(reason, str) or not reason for reason in contract["incomplete_reasons"]):
        raise AssertionError("incomplete_reasons must be a list of strings")
    baseline = contract["baseline"]
    if not isinstance(baseline, dict) or baseline.get("status") not in {"available", "unavailable"}:
        raise AssertionError("baseline.status must be available or unavailable")
    for key in ("cycles_per_token", "clock_mhz", "throughput_tokens_per_second", "resources", "source"):
        if key not in baseline:
            raise AssertionError(f"baseline.{key} is required")
    for key in ("cycles_per_token", "clock_mhz", "throughput_tokens_per_second"):
        if baseline[key] is not None and (not isinstance(baseline[key], (int, float)) or isinstance(baseline[key], bool) or baseline[key] < 0):
            raise AssertionError(f"baseline.{key} must be a non-negative number or null")
    if baseline["resources"] is not None and not isinstance(baseline["resources"], dict):
        raise AssertionError("baseline.resources must be an object or null")
    if baseline["source"] is not None and not isinstance(baseline["source"], str):
        raise AssertionError("baseline.source must be a string or null")
    if contract["status"] == "incomplete" and not contract.get("incomplete_reasons"):
        raise AssertionError("incomplete contracts must explain their blockers")
    return contract


class TinyStoriesReferenceContractTest(unittest.TestCase):
    def test_contract_contains_frozen_1m_identity(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["model"]["name"], "TinyStories-1M")
        self.assertEqual(contract["model"]["n_layer"], 8)
        self.assertEqual(contract["model"]["hidden_size"], 64)
        self.assertEqual(len(contract["reference"]["tokens"]), 16)

    def test_contract_is_explicitly_incomplete_without_unmeasured_baseline(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["status"], "incomplete")
        self.assertTrue(any("baseline" in reason for reason in contract["incomplete_reasons"]))

    def test_loader_rejects_nested_hash_and_abi_corruption(self) -> None:
        global CONTRACT_PATH
        original = CONTRACT_PATH.read_text()
        value = json.loads(original)
        for path, replacement in [
            (("package", "files", "weights.bin"), "not-a-hash"),
            (("tokenizer", "vocab_sha256"), "f" * 63),
            (("quantization", "scale_image_sha256"), "f" * 65),
            (("command_abi", "request_magic"), "4b47"),
        ]:
            candidate = deepcopy(value)
            cursor = candidate
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = replacement
            with tempfile.TemporaryDirectory() as temp:
                temp_path = Path(temp) / "contract.json"
                temp_path.write_text(json.dumps(candidate))
                saved = CONTRACT_PATH
                CONTRACT_PATH = temp_path
                try:
                    with self.assertRaises(AssertionError):
                        load_contract()
                finally:
                    CONTRACT_PATH = saved


if __name__ == "__main__":
    unittest.main()
