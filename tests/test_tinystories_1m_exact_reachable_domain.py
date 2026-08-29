"""Reachable-domain and independent-logits authorities for the exact model."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CERTIFIER = ROOT / "scripts/comparison/certify_tinystories_1m_exact_reachable_domain.py"
CAPTURE = ROOT / "scripts/comparison/capture_tinystories_1m_fixed_logits.py"
CERTIFICATE = ROOT / "artifacts/reference/tinystories-1m-exact-reachable-domain.json"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-logits-oracle.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
AUDIT = ROOT / "artifacts/reference/tinystories-1m-exact-input-audit.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
SOFTMAX = ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
REFERENCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PACKAGE.is_dir() and REFERENCE.is_dir(), "canonical inputs unavailable")
class ExactReachableDomainCertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.certifier = load_script(CERTIFIER, "exact_reachable_domain")
        cls.certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))

    def test_checked_in_certificate_rederives_exactly(self) -> None:
        actual = self.certifier.derive_certificate(
            CONTRACT, AUDIT, PROFILE, SOFTMAX, PACKAGE, REFERENCE, ROOT
        )

        self.assertEqual(actual, self.certificate)
        self.assertEqual(actual["status"], "proven_reachable_domain_equivalent")
        self.assertEqual(actual["certificate_sha256"], self.certifier.certificate_sha256(actual))

    def test_all_layernorm_sites_have_closed_width_and_output_proofs(self) -> None:
        layer_norm = self.certificate["layer_norm"]
        calls = layer_norm["calls"]

        self.assertEqual(len(calls), 17)
        self.assertEqual(calls[0]["name"], "transformer.h.0.ln_1")
        self.assertEqual(calls[-1]["name"], "transformer.ln_f")
        for call in calls:
            with self.subTest(call=call["name"]):
                self.assertEqual(len(call["input_bounds_q16_16"]["lower_by_channel"]), 64)
                self.assertEqual(len(call["input_bounds_q16_16"]["upper_by_channel"]), 64)
                self.assertTrue(all(call["proof"]["inequalities"].values()))
                self.assertLess(call["proof"]["square_sum_abs_bound"], 2**63)
                self.assertLess(call["proof"]["affine_output_abs_bound"], 2**31)
                self.assertEqual(call["edge_witnesses"]["status"], "runtime_rtl_matched")
        self.assertEqual(layer_norm["conclusion"], "runtime_and_synthesizable_rtl_identical_on_reachable_domain")

    def test_unprovable_layernorm_interval_reports_exact_failed_inequality(self) -> None:
        result = self.certifier.prove_layernorm_interval(
            "adversarial", [-2**31] * 32 + [2**31 - 1] * 32,
            [-2**31] * 32 + [2**31 - 1] * 32,
            [65536] * 64, [0] * 64,
        )

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["failing_inequality"], "runtime_square_sum_fits_signed_int64")

    def test_gelu_and_attention_are_source_bound_for_every_layer(self) -> None:
        nonlinear = self.certificate["nonlinear"]

        self.assertEqual(len(nonlinear["gelu"]["calls"]), 8)
        self.assertEqual(len(nonlinear["attention_softmax"]["calls"]), 8)
        self.assertEqual(nonlinear["gelu"]["calls"][-1]["name"], "transformer.h.7.mlp.gelu")
        self.assertEqual(
            nonlinear["attention_softmax"]["calls"][-1]["name"],
            "transformer.h.7.attn.attention",
        )
        self.assertTrue(all(call["proof"]["all"] for call in nonlinear["gelu"]["calls"]))
        self.assertTrue(all(call["proof"]["all"] for call in nonlinear["attention_softmax"]["calls"]))
        source_paths = set(self.certificate["identity"]["semantic_sources"])
        self.assertIn("fpga/rtl/gptneo_layernorm.sv", source_paths)
        self.assertIn("fpga/rtl/gptneo_gelu.sv", source_paths)
        self.assertIn("fpga/rtl/gptneo_attention.sv", source_paths)
        self.assertIn("fpga/rtl/gptneo_iterative_divider.sv", source_paths)


@unittest.skipUnless(PACKAGE.is_dir() and REFERENCE.is_dir(), "canonical inputs unavailable")
class IndependentFixedLogitsOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture = load_script(CAPTURE, "capture_fixed_logits")
        cls.oracle = json.loads(ORACLE.read_text(encoding="utf-8"))

    def test_oracle_is_reproduced_by_pinned_external_reference(self) -> None:
        actual = self.capture.capture_fixed_logits(CONTRACT, AUDIT, PACKAGE, REFERENCE)

        self.assertEqual(actual, self.oracle)
        self.assertEqual(actual["status"], "independent_pinned_fixed_reference")
        self.assertEqual(len(actual["logits"]["values"]), 50257)
        self.assertEqual(actual["next_token"], 11)
        self.assertEqual(actual["oracle_sha256"], self.capture.oracle_sha256(actual))

    def test_oracle_vector_hash_agrees_with_existing_independent_softmax_receipt(self) -> None:
        softmax = json.loads(SOFTMAX.read_text(encoding="utf-8"))
        values = self.oracle["logits"]["values"]

        self.assertEqual(
            self.oracle["logits"]["canonical_sha256"],
            hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest(),
        )
        self.assertEqual(
            self.oracle["logits"]["canonical_sha256"],
            softmax["last_token_logits_q16_16_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
