"""Regression gate for the current TinyStories-1M optimization candidate.

The current Task 4 state is still slice-scoped: the authenticated LayerNorm
slice has one evidence-backed compiler/backend candidate, but full-block
equivalence and FPGA timing/hardware acceptance remain open.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "artifacts/comparison/tinystories-1m-slice-comparison.json"
RESULT = ROOT / "artifacts/comparison/tinystories-1m-optimization-result.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class TinyStories1MOptimizationRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_task3_comparison_is_still_not_aligned(self) -> None:
        self.assertIn(self.comparison["status"], {"contract_mismatch", "incomplete"})
        self.assertEqual(self.comparison["functional"]["checkpoint_status"], "unavailable")

    def test_optimization_result_records_the_layernorm_candidate(self) -> None:
        self.assertEqual(self.result["schema"], "tinystories-1m-optimization-result-v1")
        self.assertEqual(self.result["status"], "candidate_validated_slice_only")
        self.assertEqual(self.result["candidate_status"], "evidence_backed_slice_candidate")
        self.assertEqual(self.result["selected_candidate"], "disable Calyx cell-share")
        self.assertEqual(
            self.result["structural_property"],
            "remove native Calyx Futil-to-Verilog assignment rebinding that introduces the authenticated LayerNorm synthesis loop",
        )
        self.assertEqual(
            self.result["source_change"]["path"],
            "scripts/pipeline/calyx_to_sv_no_handshake.sh",
        )
        self.assertEqual(
            self.result["source_change"]["change"],
            "switch Calyx Verilog emission from `-d papercut` to `-d cell-share` for the compiler path under evaluation",
        )
        self.assertFalse(self.result["source_change"]["applied_to_production"])

    def test_candidate_result_is_explicitly_slice_scoped(self) -> None:
        before = self.result["before"]
        after = self.result["after"]
        self.assertEqual(before["yosys_techmap"], "128 combinational-loop problems")
        self.assertEqual(after["yosys_techmap"], "completed; check reports 96 undriven external-memory write-data bits and no combinational-loop problems")
        self.assertTrue(after["functional_equivalence"]["exact_layernorm_vector_match"])
        self.assertFalse(self.result["acceptance"]["full_block_equivalence"])
        self.assertFalse(self.result["acceptance"]["resource_improvement"])
        self.assertFalse(self.result["acceptance"]["timing_preserved"])
        self.assertFalse(self.result["acceptance"]["hardware_accepted"])
        self.assertFalse(self.result["acceptance"]["accepted"])
        self.assertIn("slice-scoped", self.result["decision"])

    def test_result_self_hash_is_canonical(self) -> None:
        self.assertEqual(
            self.result["sha256"],
            canonical_sha256({key: value for key, value in self.result.items() if key != "sha256"}),
        )

    def test_comparison_input_hash_is_pinned(self) -> None:
        self.assertEqual(
            self.result["inputs"]["comparison"]["sha256"],
            file_sha256(COMPARISON),
        )

    def test_candidate_is_exposed_as_opt_in_pipeline_mode(self) -> None:
        script = (ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").read_text(encoding="utf-8")
        self.assertIn("CALYX_DISABLE_CELL_SHARE", script)
        self.assertIn("calyx_disabled_pass_args+=(-d cell-share)", script)
        self.assertIn('"cell_share_disabled"', script)


if __name__ == "__main__":
    unittest.main()
