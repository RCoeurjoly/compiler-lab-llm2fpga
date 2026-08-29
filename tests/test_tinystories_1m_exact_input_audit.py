from __future__ import annotations

import importlib.util
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
    def test_audit_reports_the_exact_unresolved_semantics_frontier(self):
        result = load_auditor().audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)

        self.assertEqual(result["activation_quantization"]["boundary_count"], 97)
        self.assertEqual(result["contract"]["activation_granularity"], "per_channel")
        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(
            [conflict["code"] for conflict in result["conflicts"]],
            [
                "implementation_profile_unresolved",
                "board_checkpoint_trace_unavailable",
                "nonfinite_policy_unresolved",
            ],
        )


if __name__ == "__main__":
    unittest.main()
