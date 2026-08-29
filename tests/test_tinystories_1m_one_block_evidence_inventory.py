from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/inventory_tinystories_1m_one_block_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tinystories_1m_one_block_evidence_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStories1MOneBlockEvidenceInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_inventory_reports_provenance_bound_trace_and_first_missing_gate(self) -> None:
        inventory = self.module.build_inventory(ROOT)

        self.assertEqual(inventory["schema"], "tinystories-1m-one-block-evidence-inventory-v1")
        self.assertEqual(inventory["status"], "blocked")
        self.assertEqual(
            inventory["first_missing_gate"],
            "slice manifest schema, model, kind, or accepted status is invalid",
        )
        package = inventory["compiler_package_identity"]
        self.assertEqual(package["contract_sha256"], "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf")
        self.assertEqual(package["manifest_sha256"], "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35")
        self.assertEqual(package["package_receipt_sha256"], "aa546aa3956fd5de207af647ed4cf280d26c8477e9f308f9f0b39c1a2b90cca2")

        trace = inventory["trace_checkpoints"]
        self.assertEqual(trace["status"], "authenticated_profile_trace_validated")
        self.assertEqual(trace["checkpoint_count"], 12)
        self.assertEqual(trace["checkpoint_hashes"]["block.attention.q"], "caa771925998871b7431570e7f7c6c6ac4b163c6ab3bd67ca3d5c7703a288f3f")
        self.assertEqual(trace["checkpoint_hashes"]["block.output"], "116356f5887b36c3d1c7bfb57ce247a2013000699cfaee6c4fee056175cca7ea")

    def test_inventory_does_not_promote_unbound_resource_or_timing_fixtures(self) -> None:
        inventory = self.module.build_inventory(ROOT)

        for key in ("resources", "timing", "memory", "latency", "throughput"):
            self.assertEqual(inventory["accepted_one_block_metrics"][key]["status"], "unavailable")

        rejected = inventory["rejected_or_non_one_block_artifacts"]
        self.assertEqual(rejected["compiler_yosys_fixture"]["status"], "fixture_only_not_provenance_bound")
        self.assertEqual(rejected["compiler_nextpnr_fixture"]["status"], "fixture_only_not_provenance_bound")
        self.assertEqual(rejected["full_w8a8_yosys_slang_structural"]["status"], "not_one_block_evidence")
        self.assertEqual(rejected["baseline_float_memory_utilization"]["status"], "not_compiler_one_block_evidence")


if __name__ == "__main__":
    unittest.main()
