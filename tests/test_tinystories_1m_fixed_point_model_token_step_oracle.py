"""Tests for the exact two-token TinyStories-1M model-level oracle."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py"
ORACLE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json"
)
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
GENERATION = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
PACKAGE = Path(
    "/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m"
)
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)
PROMPT = [7454, 2402, 257, 640]
TOKENS = [11, 612]
LOGITS_SHA256 = [
    "419d13c8778ccad33aa604cae466d06a6d77492ae280367deb9bb68ba43773d6",
    "9ca8dbffe83a6ad4f96be73b279fb1f2c12f5fb407cd1840f53d141388494bf2",
]
FULL_LOGITS_SHA256 = [
    "3d52bb0fcad732af1e0e7fffb29d1017b49bce507adf7529913cd783afe132d8",
    "081e890bf9a17b61659f21b7db6d3303ce388f0c8c624473abfa6e4962b66569",
]


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rehash_for_current_capture(fixture: dict) -> None:
    fixture["identity"]["capture_source_sha256"] = hashlib.sha256(
        CAPTURE.read_bytes()
    ).hexdigest()
    fixture["artifact_sha256"] = canonical_sha256(
        {key: value for key, value in fixture.items() if key != "artifact_sha256"}
    )


def load_capture():
    if not CAPTURE.is_file():
        raise AssertionError("missing model-level token-step oracle capture")
    spec = importlib.util.spec_from_file_location("model_token_step_oracle", CAPTURE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStories1MModelTokenStepOracleUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture = load_capture()

    def test_capture_rejects_host_supplied_second_token_before_model_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "host_second_token_forbidden"):
            self.capture.capture_model_token_steps(
                None, PROMPT, step_count=2, host_second_token=11
            )

    def test_capture_rejects_host_supplied_intermediate_states_before_model_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "host_intermediate_states_forbidden"):
            self.capture.capture_model_token_steps(
                None, PROMPT, step_count=2, host_intermediate_states={"block.0": []}
            )

    def test_model_identity_reads_tied_embeddings_from_the_package_manifest(self) -> None:
        contract_model = {
            "name": "TinyStories-1M",
            "architecture": "gpt_neo",
            "n_layer": 8,
            "hidden_size": 64,
            "n_head": 16,
            "head_dim": 4,
            "vocab_size": 50257,
            "max_context": 32,
        }
        manifest_model = {
            "model_type": "gpt_neo",
            "n_layer": 8,
            "hidden_size": 64,
            "n_head": 16,
            "head_dim": 4,
            "vocab_size": 50257,
            "max_context": 32,
            "tie_word_embeddings": True,
        }

        self.capture.validate_model_contract(contract_model, manifest_model)
        changed = dict(manifest_model, tie_word_embeddings=False)
        with self.assertRaisesRegex(ValueError, "model_contract_mismatch"):
            self.capture.validate_model_contract(contract_model, changed)

    def test_fixture_validator_rejects_rehashed_second_token_injection(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        changed["token_contract"]["host_second_token"] = 11
        changed["artifact_sha256"] = canonical_sha256(
            {key: value for key, value in changed.items() if key != "artifact_sha256"}
        )

        with self.assertRaisesRegex(ValueError, "token_contract_schema_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_intermediate_state_injection(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        changed["steps"][1]["host_intermediate_state_sha256"] = "0" * 64
        changed["artifact_sha256"] = canonical_sha256(
            {key: value for key, value in changed.items() if key != "artifact_sha256"}
        )

        with self.assertRaisesRegex(ValueError, "step_schema_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_disconnected_block_boundary(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        blocks = changed["steps"][0]["transformer_blocks"]
        blocks[0]["output"]["sha256"] = "0" * 64
        blocks[0]["boundary_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in blocks[0].items()
                if key != "boundary_sha256"
            }
        )
        changed["steps"][0]["step_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in changed["steps"][0].items()
                if key != "step_sha256"
            }
        )
        changed["artifact_sha256"] = canonical_sha256(
            {key: value for key, value in changed.items() if key != "artifact_sha256"}
        )

        with self.assertRaisesRegex(ValueError, "model_boundary_disconnected"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_coherently_rehashed_connected_boundary(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        blocks = changed["steps"][0]["transformer_blocks"]
        corrupted = copy.deepcopy(blocks[3]["output"])
        corrupted["sha256"] = "0" * 64
        corrupted["little_endian_int64_sha256"] = "1" * 64
        blocks[3]["output"] = corrupted
        blocks[4]["input"] = copy.deepcopy(corrupted)
        for block_index in (3, 4):
            blocks[block_index]["boundary_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in blocks[block_index].items()
                    if key != "boundary_sha256"
                }
            )
        changed["steps"][0]["step_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in changed["steps"][0].items()
                if key != "step_sha256"
            }
        )
        rehash_for_current_capture(changed)

        with self.assertRaisesRegex(ValueError, "semantic_authority_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_greedy_metadata(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        selected = changed["steps"][0]["selected_token"]
        selected["tie_breaking"] = "largest_token_id_among_equal_maxima"
        selected["selection_sha256"] = canonical_sha256(
            {
                "value": selected["value"],
                "tie_count": selected["tie_count"],
                "tie_breaking": selected["tie_breaking"],
            }
        )
        changed["steps"][0]["step_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in changed["steps"][0].items()
                if key != "step_sha256"
            }
        )
        rehash_for_current_capture(changed)

        with self.assertRaisesRegex(ValueError, "semantic_authority_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_selection_hash(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        changed["steps"][0]["selected_token"]["selection_sha256"] = "0" * 64
        changed["steps"][0]["step_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in changed["steps"][0].items()
                if key != "step_sha256"
            }
        )
        rehash_for_current_capture(changed)

        with self.assertRaisesRegex(ValueError, "semantic_authority_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_capture_source_identity(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        changed["identity"]["capture_source_sha256"] = "0" * 64
        changed["artifact_sha256"] = canonical_sha256(
            {key: value for key, value in changed.items() if key != "artifact_sha256"}
        )

        with self.assertRaisesRegex(ValueError, "provenance_identity_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_rejects_rehashed_model_config_without_cache(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))
        changed = copy.deepcopy(fixture)
        changed["identity"]["model_config_sha256"] = "0" * 64
        rehash_for_current_capture(changed)
        original_model = self.capture.DEFAULT_MODEL
        self.capture.DEFAULT_MODEL = ROOT / "absent-authenticated-model-cache"
        self.addCleanup(setattr, self.capture, "DEFAULT_MODEL", original_model)

        with self.assertRaisesRegex(ValueError, "provenance_identity_mismatch"):
            self.capture.verify_oracle_fixture(changed)

    def test_fixture_validator_accepts_portable_identity_without_path_receipt(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))

        self.assertNotIn("exact_model_receipt_sha256", fixture["identity"])
        self.capture.verify_oracle_fixture(fixture)


@unittest.skipUnless(
    PACKAGE.is_dir() and MODEL.is_dir(), "authenticated package/model unavailable"
)
class TinyStories1MModelTokenStepOracleAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture = load_capture()
        cls.live = cls.capture.build_oracle(
            CONTRACT, PACKAGE, MODEL, GENERATION, step_count=2
        )

    def test_exact_two_token_trajectory_is_hardware_feedback_shaped(self) -> None:
        steps = self.live["steps"]

        self.assertEqual(self.live["token_contract"]["initial_context"], PROMPT)
        self.assertEqual(self.live["token_contract"]["host_inputs"], ["initial_context"])
        self.assertEqual(
            self.live["token_contract"]["forbidden_host_inputs"],
            ["second_token", "intermediate_states"],
        )
        self.assertEqual([step["context_tokens"] for step in steps], [PROMPT, PROMPT + [11]])
        self.assertEqual([step["selected_token"]["value"] for step in steps], TOKENS)
        self.assertEqual(
            steps[1]["input_token_source"], "steps.0.selected_token.hardware_feedback"
        )
        self.assertEqual(steps[1]["feedback_token"], 11)

    def test_every_exact_model_boundary_is_present_and_ordered(self) -> None:
        expected_blocks = list(range(8))
        for step in self.live["steps"]:
            self.assertEqual(
                list(step["embedding"]),
                ["token", "position", "sum", "boundary_sha256"],
            )
            self.assertEqual(
                [block["block_index"] for block in step["transformer_blocks"]],
                expected_blocks,
            )
            self.assertEqual(len(step["transformer_blocks"]), 8)
            self.assertEqual(step["final_layer_norm"]["input"]["shape"][-1], 64)
            self.assertEqual(step["final_layer_norm"]["output"]["shape"][-1], 64)
            self.assertEqual(step["lm_head"]["last_logits"]["shape"], [50257])
            self.assertEqual(
                step["lm_head"]["weight_source"], "token_embedding.weight"
            )
            for block in step["transformer_blocks"]:
                self.assertEqual(block["input"]["shape"][-1], 64)
                self.assertEqual(block["output"]["shape"][-1], 64)
            self.assertEqual(
                step["embedding"]["sum"], step["transformer_blocks"][0]["input"]
            )
            self.assertEqual(
                step["transformer_blocks"][-1]["output"],
                step["final_layer_norm"]["input"],
            )
            self.assertEqual(
                step["final_layer_norm"]["output"], step["lm_head"]["input"]
            )

    def test_logits_and_tokens_match_the_authenticated_generation_authority(self) -> None:
        steps = self.live["steps"]

        self.assertEqual(
            [step["lm_head"]["last_logits"]["sha256"] for step in steps],
            LOGITS_SHA256,
        )
        self.assertEqual(
            [step["lm_head"]["full_context_logits"]["sha256"] for step in steps],
            FULL_LOGITS_SHA256,
        )
        self.assertEqual([step["selected_token"]["value"] for step in steps], TOKENS)
        self.assertEqual([step["selected_token"]["tie_count"] for step in steps], [1, 1])

    def test_committed_fixture_replays_the_live_authenticated_capture(self) -> None:
        fixture = json.loads(ORACLE.read_text(encoding="utf-8"))

        self.capture.verify_oracle_fixture(fixture, live_oracle=self.live)
        self.assertEqual(fixture, self.live)

    def test_provenance_binds_the_current_capture_and_exact_adapter_sources(self) -> None:
        identity = self.live["identity"]

        self.assertEqual(
            identity["capture_source_sha256"],
            hashlib.sha256(CAPTURE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            identity["exact_adapter_sha256"],
            hashlib.sha256(
                (ROOT / "TinyStories/model_adapter_exact_package.py").read_bytes()
            ).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
