from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/audit_tinystories_1m_exact_input.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
PACKAGE = Path(
    "/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m"
)
KEV_ROOT = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")


def load_auditor():
    spec = importlib.util.spec_from_file_location("tinystories_exact_input_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PACKAGE.is_dir() and KEV_ROOT.is_dir(), "canonical kev-gpt input unavailable")
class TinyStories1MExactInputAuditTest(unittest.TestCase):
    @staticmethod
    def deployed_revision() -> str:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        return contract["deployed_profile"]["revision"]

    def test_missing_pinned_commit_is_an_identity_frontier(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        contract["deployed_profile"]["revision"] = "0" * 40
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            result = load_auditor().audit_exact_input(path, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "pinned_commit_unavailable")

    def test_audit_uses_pinned_blob_closure_when_the_live_reference_is_dirty(self):
        result = load_auditor().audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        source = result["source"]
        self.assertFalse(source["reference_source_worktree_clean"])
        self.assertIn("fpga/rtl/gptneo_sequencer.sv", source["relevant_dirty_paths"])
        self.assertRegex(source["relevant_worktree_diff_sha256"], r"^[0-9a-f]{64}$")
        closure = source["pinned_semantic_source_closure"]
        self.assertEqual(
            set(closure),
            set(load_auditor().REFERENCE_SOURCES),
        )
        self.assertTrue(all("git_blob_sha1" in identity for identity in closure.values()))

    def test_fixed_reference_rejects_nonfinite_prompt_at_its_call_boundary(self):
        auditor = load_auditor()

        with self.assertRaisesRegex(auditor.IdentityFrontierError, "non-finite") as raised:
            auditor._run_fixed_reference(
                KEV_ROOT, self.deployed_revision(), PACKAGE, [7454, math.nan]
            )

        self.assertEqual(raised.exception.code, "nonfinite_adapter_input")

    def test_fixed_reference_uses_authenticated_revision_without_reresolving_head(self):
        auditor = load_auditor()

        with mock.patch.object(
            auditor,
            "_git",
            side_effect=AssertionError("reference execution must not resolve live HEAD"),
        ):
            tokens = auditor._run_fixed_reference(
                KEV_ROOT,
                self.deployed_revision(),
                PACKAGE,
                auditor.FROZEN_PROMPT_IDS,
            )

        self.assertEqual(tokens, auditor.FROZEN_EXPECTED_TOKENS)

    def test_blob_identity_mismatch_has_a_precise_frontier_code(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        contract["deployed_profile"]["sources"]["fpga/rtl/gptneo_sequencer.sv"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(contract), encoding="utf-8")
            result = load_auditor().audit_exact_input(path, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "pinned_source_identity_mismatch")

    def test_fixed_profile_mismatch_has_a_precise_frontier_code(self):
        auditor = load_auditor()
        original_load_json = auditor._load_json

        def mismatched_fixed_profile(path):
            value = original_load_json(path)
            if path == auditor.FIXED_PROFILE:
                value["profile"] = "unexpected_profile"
            return value

        with mock.patch.object(auditor, "_load_json", side_effect=mismatched_fixed_profile):
            result = auditor.audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "fixed_profile_mismatch")

    def test_nonfinite_package_failure_has_a_precise_frontier_code(self):
        auditor = load_auditor()

        with mock.patch.object(
            auditor,
            "_validate_finite_package_values",
            side_effect=ValueError("package scales.bin contains a non-finite value"),
        ):
            result = auditor.audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "nonfinite_package_value")

    def test_reference_execution_failure_has_a_precise_frontier_code(self):
        auditor = load_auditor()

        with mock.patch.object(
            auditor,
            "_run_fixed_reference",
            side_effect=subprocess.CalledProcessError(1, ["fixed-reference"]),
        ):
            result = auditor.audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "reference_execution_failure")

    def test_reference_token_mismatch_has_a_precise_frontier_code(self):
        auditor = load_auditor()

        with mock.patch.object(auditor, "_run_fixed_reference", return_value=[0]):
            result = auditor.audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["conflicts"][0]["code"], "reference_token_mismatch")

    def test_adapter_input_policy_rejects_nonfinite_values(self):
        auditor = load_auditor()

        auditor.validate_finite_adapter_input([7454, 2402, 257, 640])
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "non-finite"):
                    auditor.validate_finite_adapter_input([7454, value])

    def test_audit_authenticates_the_deployed_fixed_profile(self):
        result = load_auditor().audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["activation_quantization"]["boundary_count"], 97)
        self.assertEqual(result["contract"]["activation_granularity"], "per_channel")
        self.assertEqual(result["status"], "authenticated")
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["implementation_profile"]["name"], "fixed_hardware_reference")
        self.assertEqual(
            result["semantic_receipts"]["fixed_profile"]["contract_sha256"],
            "f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6",
        )
        self.assertEqual(result["nonfinite_policy"], "reject_nonfinite_adapter_input")
        self.assertEqual(result["model"]["source_revision"], "ac533fb8b4f69c71894bf96badfe11e6294d9fcf")
        self.assertEqual(result["tokenizer"]["sha256"], "f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5")
        self.assertEqual(result["quantization"]["weights"], "symmetric per-output INT8")
        self.assertEqual(result["fixed_point"], {
            "value_format": "signed Q16.16",
            "scale_format": "unsigned Q8.24",
            "gemv_accumulator": "signed 64-bit serial accumulator",
        })
        self.assertEqual(
            result["observability_limitations"][0]["code"],
            "board_checkpoint_trace_unavailable",
        )
        self.assertEqual(result["reference_fixture"]["expected_tokens"], [
            11, 612, 373, 257, 1310, 2576, 3706, 20037,
            13, 1375, 6151, 284, 711, 2354, 287, 262,
        ])


if __name__ == "__main__":
    unittest.main()
