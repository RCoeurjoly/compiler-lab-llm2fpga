from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
FIXTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-shift-semantics.json"
DECISION = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"

SPEC = importlib.util.spec_from_file_location("exact_frontier_semantics", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactFrontierSemanticContractTest(unittest.TestCase):
    def test_contract_interprets_signed_si64_shift_vectors(self) -> None:
        result = MODULE.verify_contract(FIXTURE, DECISION)
        self.assertEqual(result["valid_cases"], ["shift_one", "shift_zero", "shift_sixty_two"])
        self.assertEqual(result["rejected_cases"], ["negative_shift", "shift_greater_than_sixty_two"])
        self.assertEqual(result["shift_one_output"], [-3, -1, 0, 0, 2])

    def test_lowered_result_requires_exact_dtype_shape_values_and_status(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        expected = fixture["valid_cases"][0]["expected"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "lowered-results.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "tinystories-1m-exact-shift-lowered-results-v1",
                        "cases": [
                            {
                                "id": "shift_one",
                                "status": "ok",
                                "output": {
                                    **expected,
                                    "values": [-2, -1, 0, 0, 2],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "lowered_result_mismatch:shift_one"):
                MODULE.verify_lowered_result(path, fixture)

    def test_lowered_result_requires_named_invalid_shift_rejections(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        valid_records = [
            {"id": case["id"], "status": "ok", "output": case["expected"]}
            for case in fixture["valid_cases"]
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "lowered-results.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "tinystories-1m-exact-shift-lowered-results-v1",
                        "cases": valid_records + [
                            {"id": "negative_shift", "status": "ok"},
                            {
                                "id": "shift_greater_than_sixty_two",
                                "status": "rejected_shift_greater_than_sixty_two",
                                "diagnostic": "shift_contract:greater_than_sixty_two",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "lowered_status_mismatch:negative_shift"):
                MODULE.verify_lowered_result(path, fixture)

    def test_registered_stage_requires_current_task_identity_hashes(self) -> None:
        decision = json.loads(DECISION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "torch.mlir"
            stage.write_text("module {}\n", encoding="utf-8")
            result = MODULE.verify_registered_stage(stage, decision)
            self.assertEqual(result["status"], "accepted")
            decision["identity_hashes"]["task_3_generation_result_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "task3_generation_result_hash"):
                MODULE.verify_registered_stage(stage, decision)


if __name__ == "__main__":
    unittest.main()
