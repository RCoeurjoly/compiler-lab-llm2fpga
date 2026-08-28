"""Strict loader for the frozen TinyStories-1M reference contract."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "artifacts" / "reference" / "tinystories-1m-kev-gpt-contract.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load_contract() -> dict:
    if not CONTRACT_PATH.is_file():
        raise AssertionError(f"missing reference contract: {CONTRACT_PATH}")
    contract = json.loads(CONTRACT_PATH.read_text())
    required = {"schema_version", "status", "model", "package", "tokenizer", "quantization", "memory_image", "command_abi", "reference", "baseline"}
    missing = required - contract.keys()
    if missing:
        raise AssertionError(f"contract missing fields: {sorted(missing)}")
    model = contract["model"]
    expected = {"name": "TinyStories-1M", "n_layer": 8, "hidden_size": 64, "n_head": 16, "head_dim": 4, "vocab_size": 50257}
    for key, value in expected.items():
        if model.get(key) != value:
            raise AssertionError(f"model.{key} must be {value!r}")
    for section in ("package", "tokenizer", "memory_image"):
        digest = contract[section].get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise AssertionError(f"{section}.sha256 is not a lowercase SHA-256 digest")
    quant = contract["quantization"]
    for key in ("weights", "activations"):
        if key not in quant or not isinstance(quant[key], str):
            raise AssertionError(f"quantization.{key} is required")
    abi = contract["command_abi"]
    for key in ("request_magic", "reply_magic", "version", "max_context", "crc32", "token_id_bits"):
        if key not in abi:
            raise AssertionError(f"command_abi.{key} is required")
    reference = contract["reference"]
    if reference.get("prompt_text") != "Once upon a time":
        raise AssertionError("reference prompt fixture changed")
    if reference.get("prompt_tokens") != [7454, 2402, 257, 640]:
        raise AssertionError("reference prompt token IDs changed")
    tokens = reference.get("tokens")
    if not isinstance(tokens, list) or len(tokens) != 16 or any(not isinstance(t, int) for t in tokens):
        raise AssertionError("reference.tokens must contain exactly 16 integer IDs")
    if contract["status"] not in {"frozen", "incomplete"}:
        raise AssertionError("unknown contract status")
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


if __name__ == "__main__":
    unittest.main()
