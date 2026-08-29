"""Tests for the authenticated exact TinyStories-1M generation gate."""

from __future__ import annotations

import importlib.util
import copy
import hashlib
import json
import unittest
from pathlib import Path

from TinyStories.model_adapter_exact_package import load_exact_model


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)
VERIFIER = ROOT / "scripts/comparison/verify_tinystories_1m_exact_generation.py"
ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
TASK_1_COMMIT = "c8eb2011ee09c368accdf8efd67c50dfc5564679"
TASK_2_COMMIT = "a2eda783819bbfb35a833d1a45d3dd125a176973"
EXPECTED = [11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 6151, 284, 711, 2354, 287, 262]


def load_script(path: Path):
    spec = importlib.util.spec_from_file_location("exact_generation_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
class TinyStories1MExactGenerationAuthorityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_script(VERIFIER)
        cls.bundle = load_exact_model(CONTRACT, PACKAGE, MODEL)

    def test_mutated_in_memory_model_state_fails_before_generation(self) -> None:
        changed = self.verifier._fresh_bundle(self.bundle)
        first_buffer = next(changed.model.buffers())
        first_buffer.view(-1)[0] += 1

        with self.assertRaisesRegex(ValueError, "task_2_model_state_mismatch"):
            self.verifier.verify_generation(
                changed, [7454, 2402, 257, 640], EXPECTED, count=3
            )

    def test_first_checkpoint_mismatch_names_the_checkpoint(self) -> None:
        eager = {"checkpoint_sha256": {"block.input": "a", "block.output": "b"}}
        exported = {"checkpoint_sha256": {"block.input": "a", "block.output": "changed"}}

        self.assertEqual(
            self.verifier._first_mapping_mismatch(eager, exported),
            ["checkpoint_sha256", "block.output"],
        )


@unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
class TinyStories1MExactGenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_script(VERIFIER)
        cls.bundle = load_exact_model(CONTRACT, PACKAGE, MODEL)
        cls.result = cls.verifier.verify_generation(
            cls.bundle, [7454, 2402, 257, 640], EXPECTED, count=3
        )

    def test_three_runs_match_the_frozen_sequence(self) -> None:
        result = self.result

        self.assertEqual(result["status"], "matched")
        self.assertEqual([run["tokens"] for run in result["runs"]], [EXPECTED] * 3)

    def test_every_context_replays_eager_and_exported_observations(self) -> None:
        self.assertEqual(self.result["context_lengths"], list(range(4, 20)))
        self.assertEqual(self.result["export_cache"]["export_count"], 16)
        self.assertEqual(self.result["export_cache"]["replay_count"], 48)
        self.assertEqual(
            sorted(map(int, self.result["export_cache"]["programs"])), list(range(4, 20))
        )
        for run in self.result["runs"]:
            self.assertEqual(len(run["steps"]), 16)
            for length, step in zip(range(4, 20), run["steps"], strict=True):
                with self.subTest(run=run["run_index"], length=length):
                    self.assertEqual(step["context_length"], length)
                    self.assertEqual(step["comparison_status"], "matched")
                    self.assertEqual(step["eager"], step["exported"])
                    self.assertEqual(len(step["eager"]["checkpoint_sha256"]), 12)
                    self.assertEqual(len(step["eager"]["qdq_boundary_sha256"]), 97)
                    self.assertEqual(len(step["eager"]["gemv_accumulator_sha256"]), 49)
                    self.assertEqual(len(step["eager"]["nonlinear_boundary_sha256"]), 33)
                    self.assertRegex(step["eager"]["logits_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(step["eager"]["observation_sha256"], r"^[0-9a-f]{64}$")
                    self.assertRegex(step["step_sha256"], r"^[0-9a-f]{64}$")

    def test_fresh_runs_have_identical_authenticated_transcripts(self) -> None:
        runs = self.result["runs"]
        self.assertEqual([run["bundle_instance"] for run in runs], [1, 2, 3])
        self.assertEqual(len({run["transcript_sha256"] for run in runs}), 1)
        self.assertEqual(len({run["model_state_sha256"] for run in runs}), 1)
        self.assertEqual(
            self.result["determinism"]["run_transcript_sha256"],
            [run["transcript_sha256"] for run in runs],
        )
        self.assertRegex(self.result["determinism"]["three_run_sha256"], r"^[0-9a-f]{64}$")

    def test_tie_breaking_selects_the_smallest_token_id(self) -> None:
        selected, tie_count = self.verifier.select_greedy_token([7, 9, 9, 4])
        self.assertEqual((selected, tie_count), (1, 2))

    def test_inputs_fail_closed_before_generation(self) -> None:
        cases = (
            ("prompt_identity_mismatch", [7454, 2402, 257], EXPECTED, 3),
            ("expected_tokens_identity_mismatch", [7454, 2402, 257, 640], EXPECTED[:-1] + [0], 3),
            ("generation_count_mismatch", [7454, 2402, 257, 640], EXPECTED, 2),
        )
        for code, prompt, expected, count in cases:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                self.verifier.verify_generation(self.bundle, prompt, expected, count=count)

    def test_artifact_binds_task_identities_sources_and_complete_result(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        expected = self.verifier.build_artifact(ROOT, self.result)

        self.assertEqual(artifact, expected)
        self.assertEqual(artifact["identity"]["task_1"]["commit"], TASK_1_COMMIT)
        self.assertEqual(artifact["identity"]["task_2"]["commit"], TASK_2_COMMIT)
        self.assertEqual(
            artifact["identity"]["sources"]["scripts/comparison/verify_tinystories_1m_exact_generation.py"],
            hashlib.sha256(VERIFIER.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            artifact["identity"]["sources"]["tests/test_tinystories_1m_exact_generation.py"],
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        self.assertEqual(artifact["generation"], self.result)
        self.verifier.validate_artifact(artifact, ROOT, self.result)

    def test_self_rehashed_artifact_drift_fails_closed(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        mutations = (
            lambda value: value["identity"]["task_1"].__setitem__("commit", "0" * 40),
            lambda value: value["identity"]["task_2"].__setitem__("commit", "0" * 40),
            lambda value: value["identity"]["sources"].__setitem__(
                "tests/test_tinystories_1m_exact_generation.py", "0" * 64
            ),
            lambda value: value["generation"]["runs"][0]["steps"][9]["eager"].__setitem__(
                "logits_sha256", "0" * 64
            ),
            lambda value: value["generation"]["runs"][2].__setitem__(
                "transcript_sha256", "0" * 64
            ),
        )
        for mutate in mutations:
            changed = copy.deepcopy(artifact)
            mutate(changed)
            changed["artifact_sha256"] = self.verifier.artifact_sha256(changed)
            with self.assertRaisesRegex(ValueError, "artifact_evidence_mismatch"):
                self.verifier.validate_artifact(changed, ROOT, self.result)


if __name__ == "__main__":
    unittest.main()
