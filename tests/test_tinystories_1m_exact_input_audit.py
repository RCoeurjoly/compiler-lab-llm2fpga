from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


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
