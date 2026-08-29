"""Tests for the authenticated exact fixed-point TinyStories-1M adapter."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

import torch

from TinyStories.model_adapter_exact_package import (
    ExactModelError,
    _validate_reachable_certificate,
    activation_qdq,
    export_exact_program,
    exported_program_identity,
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
CERTIFICATE = ROOT / "artifacts/reference/tinystories-1m-exact-reachable-domain.json"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-logits-oracle.json"
GENERATOR = ROOT / "scripts/comparison/build_tinystories_1m_exact_package_model_artifact.py"
CERTIFIER = ROOT / "scripts/comparison/certify_tinystories_1m_exact_reachable_domain.py"
CAPTURE = ROOT / "scripts/comparison/capture_tinystories_1m_fixed_logits.py"
REACHABLE_TEST = ROOT / "tests/test_tinystories_1m_exact_reachable_domain.py"
REFERENCE_ADAPTER = ROOT / "TinyStories/model_adapter_reference_package.py"
FINITE_VALIDATOR = ROOT / "scripts/comparison/audit_tinystories_1m_exact_input.py"
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


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        cls.generator = load_script(GENERATOR, "exact_model_artifact_generator")
        cls.bundle = load_exact_model(CONTRACT, PACKAGE, MODEL)
        cls.prompt = torch.tensor([[7454, 2402, 257, 640]], dtype=torch.int64)
        cls.trace = cls.bundle.trace(cls.prompt)
        cls.exported = export_exact_program(cls.bundle)

    def test_exact_model_matches_frozen_block_zero_checkpoints(self) -> None:
        trace = self.trace

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
        boundaries = trace["qdq_boundaries"]
        self.assertEqual(len(boundaries), 97)
        self.assertEqual(len({item["name"] for item in boundaries}), 97)
        self.assertEqual(boundaries[0]["name"], "transformer.h.0.attn.attention.q_proj.input")
        self.assertEqual(boundaries[-1]["name"], "lm_head.input")
        self.assertIn("transformer.h.7.mlp.c_proj.output", {item["name"] for item in boundaries})
        for boundary in boundaries:
            self.assertRegex(boundary["codes_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(boundary["scales_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(boundary["dequantized_sha256"], r"^[0-9a-f]{64}$")
        nonlinear = trace["nonlinear_boundaries"]
        self.assertEqual(len(nonlinear), 33)
        self.assertIn("transformer.h.7.attn.attention.context", nonlinear)
        self.assertIn("transformer.h.7.mlp.gelu.output", nonlinear)
        self.assertIn("transformer.ln_f.output", nonlinear)

    def test_export_replay_matches_eager_checkpoints_and_logits(self) -> None:
        eager_logits = self.bundle.model(self.prompt)
        replayed_logits = self.exported.module()(self.prompt)

        self.assertTrue(torch.equal(replayed_logits, eager_logits))
        self.assertEqual(tuple(eager_logits.shape), (1, 4, 50257))
        self.assertEqual(eager_logits.dtype, torch.int64)
        self.assertEqual(int(torch.argmax(eager_logits[0, -1])), 11)
        self.assertEqual(self.bundle.export_verification["checkpoint_sha256"], FROZEN_CHECKPOINT_SHA256)
        self.assertEqual(len(self.bundle.export_verification["qdq_boundary_sha256"]), 97)
        self.assertEqual(len(self.bundle.export_verification["nonlinear_boundary_sha256"]), 33)
        self.assertEqual(self.bundle.export_verification["final_logits_status"], "matched")
        self.assertEqual(
            self.bundle.export_verification["independent_oracle_status"],
            "full_logits_bit_exact",
        )

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
            with self.assertRaisesRegex(ExactModelError, "contract_identity_mismatch"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_exact_model_rejects_rehashed_model_identity_mutation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        contract["model"]["source_revision"] = "0" * 40
        audit["model"] = copy.deepcopy(contract["model"])
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "contract_identity_mismatch"):
                load_exact_model(conflicting, PACKAGE, MODEL)

    def test_complete_contract_identity_rejects_consistently_rehashed_ignored_fields(self) -> None:
        mutations = (
            ("tokenizer", lambda contract, audit: (
                contract["tokenizer"].__setitem__("type", "substituted"),
                audit["tokenizer"].__setitem__("type", "substituted"),
            )),
            ("source_closure", lambda contract, audit: (
                contract["deployed_profile"]["sources"]["tinystories/hardware_reference.py"].__setitem__("sha256", "0" * 64),
                audit["source"]["pinned_semantic_source_closure"]["tinystories/hardware_reference.py"].__setitem__("sha256", "0" * 64),
            )),
            ("historical_authority", lambda contract, audit: (
                contract["semantic_authorities"]["implementation_profile"].__setitem__("sha256", "0" * 64),
                audit["semantic_receipts"]["implementation_profile"].__setitem__("sha256", "0" * 64),
            )),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
                audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
                mutate(contract, audit)
                conflicting = write_contract_and_audit(Path(temporary), contract, audit)
                with self.assertRaisesRegex(ExactModelError, "contract_identity_mismatch"):
                    load_exact_model(conflicting, PACKAGE, MODEL)

    def test_exact_model_rejects_package_hash_mutation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit = json.loads((CONTRACT.parent / "tinystories-1m-exact-input-audit.json").read_text(encoding="utf-8"))
        contract["package"]["files"]["weights.bin"]["sha256"] = "0" * 64
        contract["package"]["sha256"] = "0" * 64
        audit["package"]["files"]["weights.bin"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            conflicting = write_contract_and_audit(Path(temporary), contract, audit)
            with self.assertRaisesRegex(ExactModelError, "contract_identity_mismatch"):
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

        minimum = round_shift_signed(torch.tensor([-(1 << 63)], dtype=torch.int64), 1)
        self.assertTrue(torch.equal(minimum, torch.tensor([-(1 << 62)], dtype=torch.int64)))
        with self.assertRaisesRegex(ExactModelError, "q16_range_violation"):
            activation_qdq(torch.tensor([1 << 31]), torch.tensor([512]))

    def test_independent_full_logits_oracle_and_repeat_are_bit_exact(self) -> None:
        oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
        expected = torch.tensor(oracle["logits"]["values"], dtype=torch.int64)
        first = self.bundle.model(self.prompt)[0, -1]
        second = self.bundle.model(self.prompt)[0, -1]

        self.assertTrue(torch.equal(first, expected))
        self.assertTrue(torch.equal(second, expected))
        self.assertEqual(self.bundle.receipt["independent_logits_oracle"]["canonical_sha256"],
                         oracle["logits"]["canonical_sha256"])
        self.assertEqual(self.trace, self.bundle.trace(self.prompt))

    def test_adapter_rejects_self_rehashed_incomplete_semantic_and_gemv_certificates(self) -> None:
        mutations = (
            ("source_authentication", lambda value: value["source_authentication"].__setitem__(
                "status", "copied_not_materialized"
            )),
            ("gelu", lambda value: value["nonlinear"]["gelu"]["semantic_equivalence"].__setitem__(
                "status", "identity_frontier"
            )),
            ("exp", lambda value: value["nonlinear"]["attention_softmax"]["exp_equivalence"]
             ["comparison"].__setitem__("mismatch_witness", {"delta": -4096})),
            ("divider", lambda value: value["nonlinear"]["attention_softmax"]
             ["operator_equivalence"]["divider"].__setitem__("status", "identity_frontier")),
            ("gemv", lambda value: value["gemv"]["calls"][48]["proof"]["inequalities"]
             .__setitem__("pre_output_q16_fits_signed_int32", False)),
            ("gemv_summary_count", lambda value: value["gemv"]["calls"][48]
             ["per_output_summaries"]["accumulator_min"].__setitem__("element_count", 1)),
            ("gemv_summary_extremum", lambda value: value["gemv"]["calls"][0]
             ["per_output_summaries"]["pre_output_q16_max"]["signed_maximum"]
             .__setitem__("output_index", 64)),
            ("gemv_summary_witness", lambda value: value["gemv"]["calls"][0]
             ["per_output_summaries"]["accumulator_max"]["worst_case_witness"]
             .__setitem__("module", "substituted.module")),
            ("gemv_failure_witness", lambda value: value["gemv"]["calls"][0].__setitem__(
                "first_failure_witness", {
                    "module": "transformer.h.0.attn.attention.q_proj",
                    "output": 0,
                    "term": "substituted_failure",
                }
            )),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                certificate = copy.deepcopy(self.bundle.certificate)
                mutate(certificate)
                certificate["certificate_sha256"] = canonical_sha256({
                    key: value for key, value in certificate.items()
                    if key != "certificate_sha256"
                })
                with self.assertRaisesRegex(ExactModelError, "identity_frontier"):
                    _validate_reachable_certificate(
                        certificate, self.bundle.contract, self.bundle.audit
                    )

    def _expected_artifact_sections(self) -> dict:
        certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))
        oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        audit_path = CONTRACT.with_name("tinystories-1m-exact-input-audit.json")
        source_paths = (
            ROOT / "TinyStories/model_adapter_exact_package.py",
            REFERENCE_ADAPTER,
            FINITE_VALIDATOR,
            Path(__file__),
            REACHABLE_TEST,
            GENERATOR,
            CERTIFIER,
            CAPTURE,
        )
        identity = {
            "contract": {"sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest()},
            "audit": {
                "file_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                "payload_sha256": self.bundle.audit["sha256"],
            },
            "fixed_profile": {
                "sha256": hashlib.sha256(
                    (ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json").read_bytes()
                ).hexdigest(),
            },
            "package": {"files": contract["package"]["files"]},
            "source_files": {
                str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in source_paths
            },
            "model_receipt_sha256": self.bundle.receipt["receipt_sha256"],
            "reachable_certificate": {
                "file_sha256": hashlib.sha256(CERTIFICATE.read_bytes()).hexdigest(),
                "certificate_sha256": certificate["certificate_sha256"],
            },
            "fixed_logits_oracle": {
                "file_sha256": hashlib.sha256(ORACLE.read_bytes()).hexdigest(),
                "oracle_sha256": oracle["oracle_sha256"],
            },
        }
        trace = {
            "prompt_tokens": self.bundle.contract["reference"]["prompt_tokens"],
            "sha256": self.trace["trace_sha256"],
            "checkpoint_sha256": {
                name: checkpoint["sha256"]
                for name, checkpoint in self.trace["checkpoints"].items()
            },
            "qdq_boundary_sha256": {
                item["name"]: {
                    "codes": item["codes_sha256"],
                    "scales": item["scales_sha256"],
                    "dequantized": item["dequantized_sha256"],
                }
                for item in self.trace["qdq_boundaries"]
            },
            "gemv_accumulator_sha256": {
                name: item["sha256"] for name, item in self.trace["gemv_accumulators"].items()
            },
            "nonlinear_boundary_sha256": {
                name: item["sha256"] for name, item in self.trace["nonlinear_boundaries"].items()
            },
        }
        export = {
            "shape": [1, 4, 50257],
            "dtype": "torch.int64",
            "checkpoint_replay": "matched",
            "qdq_boundary_replay": "matched",
            "gemv_accumulator_replay": "matched",
            "nonlinear_boundary_replay": "matched",
            "final_logits_replay": "matched",
            "independent_oracle": "full_logits_bit_exact",
            "final_logits_sha256": self.bundle.export_verification["final_logits_sha256"],
            "final_logits_canonical_sha256": self.bundle.export_verification[
                "final_logits_canonical_sha256"
            ],
        }
        return {
            "identity": identity,
            "execution": self.bundle.receipt["execution"],
            "trace": trace,
            "export": export,
            "exported_program": exported_program_identity(self.exported),
        }

    def test_exact_package_model_artifact_validates_every_recorded_identity_and_execution_field(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        expected = self._expected_artifact_sections()

        self.assertEqual(artifact["schema"], "tinystories-1m-exact-package-model-v1")
        self.assertEqual(
            artifact["status"], "exact_eager_export_and_independent_oracle_matched"
        )
        self.assertEqual({key: artifact[key] for key in expected}, expected)
        self.generator.validate_artifact(artifact, expected)
        self.assertEqual(
            artifact["artifact_sha256"],
            canonical_sha256({key: value for key, value in artifact.items() if key != "artifact_sha256"}),
        )

    def test_consistently_self_rehashed_artifact_mutations_are_rejected(self) -> None:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        expected = self._expected_artifact_sections()
        mutations = (
            ("contract", lambda value: value["identity"]["contract"].__setitem__("sha256", "0" * 64)),
            ("package", lambda value: value["identity"]["package"]["files"]["weights.bin"].__setitem__("sha256", "0" * 64)),
            ("certifier", lambda value: value["identity"]["source_files"].__setitem__(
                "scripts/comparison/certify_tinystories_1m_exact_reachable_domain.py", "0" * 64
            )),
            ("certificate", lambda value: value["identity"]["reachable_certificate"].__setitem__("certificate_sha256", "0" * 64)),
            ("oracle", lambda value: value["identity"]["fixed_logits_oracle"].__setitem__("oracle_sha256", "0" * 64)),
            ("program", lambda value: value["exported_program"].__setitem__("program_sha256", "0" * 64)),
            ("logits", lambda value: value["export"].__setitem__("final_logits_sha256", "0" * 64)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = copy.deepcopy(artifact)
                mutate(changed)
                changed["artifact_sha256"] = canonical_sha256({
                    key: value for key, value in changed.items() if key != "artifact_sha256"
                })
                with self.assertRaisesRegex(ValueError, "artifact_evidence_mismatch"):
                    self.generator.validate_artifact(changed, expected)


if __name__ == "__main__":
    unittest.main()
