"""Tests for the authenticated exact fixed-point TinyStories-1M adapter."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import torch

from TinyStories.model_adapter_exact_package import (
    ExactModelError,
    activation_qdq,
    export_exact_program,
    load_exact_model,
    round_shift_signed,
    serial_gemv_accumulate,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)
ARTIFACT = ROOT / "artifacts/reference/tinystories-1m-exact-package-model.json"
FROZEN_TRACE_SHA256 = "ac0118fe0068aea3790c3fc7414f75cd56abd5690f0d7f4bc13b143d05249d1d"
FROZEN_CHECKPOINT_SHA256 = {
    "block.input": "c310f302cfb5fd58e2f0b00e6d6a9d36fc23121e7e04eb6b09c7aa630c00e12e",
    "block.ln_1.output": "233de767e3744ac70d9d074f9d0174e5e973fda4a11c20efd392061b4c0e7eee",
    "block.attention.q": "caa771925998871b7431570e7f7c6c6ac4b163c6ab3bd67ca3d5c7703a288f3f",
    "block.attention.k": "434b82f2e692836381355fbc9400d8e597a9ea9768734c13109e32870efb92a5",
    "block.attention.v": "ac5c3f5ff49e52260f6cee72c39d59ff990d1242e76faf3e052632ec53a3a922",
    "block.attention.output": "b8a362876c047fcec8c14286c9c64df0930e8519e0fa8c60970094be6a7f9eeb",
    "block.residual.attention": "41a33e2b0933e0fb8846766e78b8edd2c661431340e295b32497b3eed34eecf5",
    "block.ln_2.output": "220e940d35a173b443992377dd47195606ee1e9aed448d13e24bcc64019341c1",
    "block.mlp.fc_in": "f40eb2c071374cb265c3795e09697efab06477caac34da12614e6ce7170e052b",
    "block.mlp.activation": "31fecd6626fb19dd762374022aa485e5b45e4dc140ffae34eaae48206ae32a3d",
    "block.mlp.fc_out": "b1e511d393cc2a84de8781ae642838a167da568156c98336428d89125600a200",
    "block.output": "116356f5887b36c3d1c7bfb57ce247a2013000699cfaee6c4fee056175cca7ea",
}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def write_contract_and_audit(directory: Path, contract: dict, audit: dict) -> Path:
    contract_path = directory / "tinystories-1m-exact-input-contract.json"
    audit_path = directory / "tinystories-1m-exact-input-audit.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    audit["contract"]["path"] = str(contract_path)
    audit["contract"]["sha256"] = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    audit["sha256"] = canonical_sha256({key: value for key, value in audit.items() if key != "sha256"})
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    return contract_path


@unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
class TinyStories1MExactPackageModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_exact_model(CONTRACT, PACKAGE, MODEL)

    def test_exact_model_matches_frozen_block_zero_checkpoints(self) -> None:
        trace = self.bundle.trace(torch.tensor([[7454, 2402, 257, 640]], dtype=torch.int64))

        self.assertEqual(trace["trace_sha256"], FROZEN_TRACE_SHA256)
        self.assertEqual(
            {name: value["sha256"] for name, value in trace["checkpoints"].items()},
            FROZEN_CHECKPOINT_SHA256,
        )
        self.assertEqual(trace["next_token"], 11)
        self.assertEqual(trace["arithmetic"]["value_format"], "signed Q16.16")
        self.assertEqual(trace["arithmetic"]["accumulator"], "signed_int64_serial_wrap")
        self.assertEqual(trace["arithmetic"]["q_proj.input"]["scale_format"], "unsigned Q8.24")
        self.assertEqual(len(trace["arithmetic"]["q_proj.input"]["codes"]), 64)
        self.assertEqual(len(trace["arithmetic"]["q_proj.accumulator"]["values"]), 64)
        self.assertEqual(trace["arithmetic"]["q_proj.accumulator"]["order"], "ascending_input_index")
        self.assertEqual(trace["arithmetic"]["q_proj.accumulator"]["overflow"], "twos_complement_wrap")
        self.assertEqual(len(trace["arithmetic"]["q_proj.output"]["codes"]), 64)
        self.assertEqual(
            trace["arithmetic"]["q_proj.output"]["dequantized"],
            sum(trace["checkpoints"]["block.attention.q"]["values"], []),
        )

    def test_export_replay_matches_eager_checkpoints_and_logits(self) -> None:
        prompt = torch.tensor([[7454, 2402, 257, 640]], dtype=torch.int64)
        eager_logits = self.bundle.model(prompt)

        exported = export_exact_program(self.bundle)
        replayed_logits = exported.module()(prompt)

        self.assertTrue(torch.equal(replayed_logits, eager_logits))
        self.assertEqual(tuple(eager_logits.shape), (1, 4, 50257))
        self.assertEqual(eager_logits.dtype, torch.int64)
        self.assertEqual(int(torch.argmax(eager_logits[0, -1])), 11)
        self.assertEqual(self.bundle.export_verification["checkpoint_sha256"], FROZEN_CHECKPOINT_SHA256)
        self.assertEqual(self.bundle.export_verification["final_logits_status"], "matched")

    def test_exact_model_rejects_non_authenticated_audit(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        audit["status"] = "identity_frontier"
        audit["conflicts"] = [{"code": "test_conflict", "reason": "adversarial fixture"}]
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "identity_frontier"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_exact_model_rejects_rehashed_arithmetic_mutation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        contract["fixed_point"]["gemv_accumulator"] = "signed 32-bit accumulator"
        audit["fixed_point"] = copy.deepcopy(contract["fixed_point"])
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "arithmetic_identity_mismatch"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_exact_model_rejects_rehashed_model_identity_mutation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        contract["model"]["source_revision"] = "0" * 40
        audit["model"] = copy.deepcopy(contract["model"])
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "model_identity_mismatch"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_exact_model_rejects_package_hash_mutation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        contract["package"]["files"]["weights.bin"]["sha256"] = "0" * 64
        contract["package"]["sha256"] = "0" * 64
        audit["package"]["files"]["weights.bin"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "package_identity_mismatch"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_real_model_boundary_reuses_finite_integer_policy(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ExactModelError, "nonfinite_adapter_input"):
                    self.bundle.model(torch.tensor([[7454.0, value]]))

    def test_rounding_saturation_and_serial_wrap_are_explicit(self) -> None:
        shifted = round_shift_signed(torch.tensor([-5, -4, -3, 3, 4, 5]), 1)
        self.assertTrue(torch.equal(shifted, torch.tensor([-3, -2, -2, 2, 2, 3])))

        codes, dequantized = activation_qdq(
            torch.tensor([1, 10_000], dtype=torch.int64),
            torch.tensor([512, 512], dtype=torch.int64),
        )
        self.assertTrue(torch.equal(codes, torch.tensor([1, 127])))
        self.assertTrue(torch.equal(dequantized, torch.tensor([2, 254])))

        accumulated = serial_gemv_accumulate(
            torch.tensor([[1 << 62, 1 << 62, 1 << 62]], dtype=torch.int64),
            torch.tensor([[3, 3, 3]], dtype=torch.int64),
        )
        self.assertTrue(torch.equal(accumulated, torch.tensor([[1 << 62]], dtype=torch.int64)))

    def test_exact_package_model_artifact_is_content_bound(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

        self.assertEqual(artifact["schema"], "tinystories-1m-exact-package-model-v1")
        self.assertEqual(artifact["status"], "exact_eager_and_export_replay_matched")
        self.assertEqual(artifact["trace"]["sha256"], FROZEN_TRACE_SHA256)
        self.assertEqual(artifact["trace"]["checkpoint_sha256"], FROZEN_CHECKPOINT_SHA256)
        self.assertEqual(artifact["execution"]["domain"], "integers_only_after_materialization")
        self.assertEqual(
            artifact["artifact_sha256"],
            canonical_sha256({key: value for key, value in artifact.items() if key != "artifact_sha256"}),
        )


if __name__ == "__main__":
    unittest.main()
