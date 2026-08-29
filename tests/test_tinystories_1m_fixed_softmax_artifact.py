from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/authenticate_tinystories_1m_fixed_softmax.py"
ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
REFERENCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")
PACKAGE = REFERENCE / "model_packages" / "tinystories-1m"


def load_module():
    spec = importlib.util.spec_from_file_location("tinystories_1m_fixed_softmax", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedSoftmaxArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_artifact_is_content_bound_runtime_only(self) -> None:
        artifact = self.artifact
        self.assertEqual(artifact["schema"], "tinystories-1m-fixed-softmax-checkpoints-v1")
        self.assertEqual(artifact["status"], "runtime_authenticated_not_board_checkpoint_authenticated")
        self.assertFalse(artifact["board_authenticated"])
        self.assertEqual(
            artifact["identity"]["contract_sha256"],
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            artifact["profile_binding"]["profile_artifact_sha256"],
            hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            artifact["sha256"],
            self.module.artifact_sha256(artifact),
        )
        source_paths = [source["path"] for source in artifact["authority"]["sources"]]
        self.assertIn("tinystories/int_reference.py", source_paths)
        self.assertEqual(
            artifact["exp_lut"]["generator"]["transitive_dependencies"],
            [
                {
                    "path": "tinystories/int_reference.py",
                    "sha256": hashlib.sha256((REFERENCE / "tinystories/int_reference.py").read_bytes()).hexdigest(),
                }
            ],
        )

    def test_exp_lut_loader_materializes_the_exact_authenticated_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out_dir = Path(temporary)
            metadata = self.module.materialize_authenticated_exp_lut(REFERENCE, out_dir)
            mem_path = out_dir / "gptneo_exp.mem"
            self.assertTrue(mem_path.is_file())
            self.assertEqual(metadata["sha256"], self.artifact["exp_lut"]["sha256"])
            self.assertEqual(
                hashlib.sha256(mem_path.read_bytes()).hexdigest(),
                self.artifact["exp_lut"]["sha256"],
            )
            lut = self.module.load_exp_lut(mem_path)
            self.assertEqual(len(lut), 4096)
            self.assertEqual(lut[0], self.artifact["exp_lut"]["sample_entries"][0]["value_q1_20"])
            self.assertEqual(lut[-1], self.artifact["exp_lut"]["sample_entries"][-1]["value_q1_20"])

    def test_block0_final_prompt_step_covers_all_heads_and_binds_profile(self) -> None:
        artifact = self.artifact
        self.assertEqual(
            artifact["slice"],
            {
                "kind": "one_transformer_block_token_step",
                "block_index": 0,
                "token_index": 3,
                "prompt_tokens": [7454, 2402, 257, 640],
                "next_token": 11,
                "num_heads": 16,
                "head_dim": 4,
                "sequence_length": 4,
            },
        )
        self.assertEqual(
            artifact["profile_binding"]["checkpoint_matches"],
            {
                "block.attention.q": True,
                "block.attention.k": True,
                "block.attention.v": True,
                "block.attention.output": True,
            },
        )
        rows = artifact["softmax_rows"]
        self.assertEqual(len(rows), 16)
        for expected_head, row in enumerate(rows):
            self.assertEqual(row["head"], expected_head)
            self.assertEqual(len(row["query_q16_16"]), 4)
            self.assertEqual(len(row["key_rows_q16_16"]), 4)
            self.assertEqual(len(row["value_rows_q16_16"]), 4)
            self.assertEqual(len(row["score_codes_q8_8"]), 4)
            self.assertEqual(len(row["delta_codes_q8_8"]), 4)
            self.assertEqual(len(row["exp_q1_20"]), 4)
            self.assertEqual(len(row["probabilities_q1_20"]), 4)
            self.assertEqual(len(row["context_q16_16"]), 4)
            self.assertTrue(all(value <= 0 for value in row["delta_codes_q8_8"]))
            self.assertGreater(row["denominator_q1_20"], 0)
            self.assertLessEqual(sum(row["probabilities_q1_20"]), 1 << 20)
            self.assertEqual(row["sha256"], self.module.row_sha256(row))

    def test_rebuild_is_byte_identical(self) -> None:
        rebuilt = self.module.build_artifact(CONTRACT, PROFILE, REFERENCE, PACKAGE)
        self.assertEqual(rebuilt, self.artifact)

    def test_logits_digest_hashes_only_the_logits_vector(self) -> None:
        root = str(REFERENCE.resolve())
        if root not in sys.path:
            sys.path.insert(0, root)
        sys.modules.pop("tinystories.int_reference", None)
        sys.modules.pop("tinystories.hardware_reference", None)
        import tinystories.hardware_reference as fixed_module

        model = fixed_module.FixedGPTNeo(PACKAGE)
        logits = model.forward([7454, 2402, 257, 640])[-1]
        expected = self.module.canonical_sha256([int(value) for value in logits.tolist()])
        self.assertEqual(self.artifact["last_token_logits_q16_16_sha256"], expected)

    def test_loader_rejects_malformed_exp_mem(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bad = Path(temporary) / "gptneo_exp.mem"
            bad.write_text("000001\nnot_hex\n", encoding="utf-8")
            with self.assertRaisesRegex(self.module.FixedSoftmaxArtifactError, "exp_lut_format_mismatch"):
                self.module.load_exp_lut(bad)

    def test_tampered_int_reference_fails_before_runtime_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / "reference"
            (fake / "tinystories").mkdir(parents=True)
            (fake / "fpga/rtl").mkdir(parents=True)
            shutil.copy2(REFERENCE / "LICENSE", fake / "LICENSE")
            shutil.copy2(REFERENCE / "tinystories/rtl_memories.py", fake / "tinystories/rtl_memories.py")
            shutil.copy2(REFERENCE / "tinystories/hardware_reference.py", fake / "tinystories/hardware_reference.py")
            shutil.copy2(REFERENCE / "tinystories/int_reference.py", fake / "tinystories/int_reference.py")
            shutil.copy2(REFERENCE / "fpga/rtl/gptneo_attention.sv", fake / "fpga/rtl/gptneo_attention.sv")
            shutil.copy2(REFERENCE / "fpga/rtl/gptneo_iterative_divider.sv", fake / "fpga/rtl/gptneo_iterative_divider.sv")
            target = fake / "tinystories/int_reference.py"
            target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(self.module.FixedSoftmaxArtifactError, "source_hash_mismatch"):
                self.module.build_artifact(CONTRACT, PROFILE, fake, PACKAGE)


if __name__ == "__main__":
    unittest.main()
