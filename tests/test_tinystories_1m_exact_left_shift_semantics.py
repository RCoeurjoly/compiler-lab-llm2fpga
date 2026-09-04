from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py"
FIXTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json"


def load_verifier():
    spec = importlib.util.spec_from_file_location("exact_left_shift_semantics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExactLeftShiftSemanticsTest(unittest.TestCase):
    def test_fixture_freezes_all_required_cases_and_contract_rejections(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case_ids = [case["id"] for case in fixture["valid_cases"] + fixture["invalid_cases"]]
        self.assertEqual(
            case_ids,
            [
                "shift_zero",
                "model_observed_shift_sixteen",
                "negative_operand",
                "positive_high_bit_wrap",
                "negative_high_bit_discard",
                "shift_sixty_two",
                "negative_count",
                "count_sixty_three",
                "dynamic_count",
                "si32_rejection",
            ],
        )
        rejected = {case["id"]: case for case in fixture["invalid_cases"]}
        self.assertEqual(rejected["count_sixty_three"]["classification"], "compiler_contract")
        self.assertEqual(rejected["count_sixty_three"]["status"], "rejected_shift_greater_than_sixty_two")
        for case in rejected.values():
            self.assertNotIn("expected", case)
            self.assertNotIn("pytorch_output", case)

    def test_verifier_reexecutes_pinned_pytorch_and_checks_independent_si64_arithmetic(self) -> None:
        verifier = load_verifier()
        result = verifier.verify(FIXTURE)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["valid_case_count"], 6)
        self.assertEqual(result["invalid_case_count"], 4)

    def test_verifier_rejects_fixture_self_hash_and_provenance_mutations(self) -> None:
        verifier = load_verifier()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "fixture_self_hash"):
            verifier.verify_object(fixture, ROOT)

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["provenance"]["adapter"]["file_sha256"] = "0" * 64
        fixture["sha256"] = verifier.canonical_sha256(
            {key: value for key, value in fixture.items() if key != "sha256"}
        )
        with self.assertRaisesRegex(ValueError, "adapter_file_hash"):
            verifier.verify_object(fixture, ROOT)

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["valid_cases"][0]["expected"]["values"][0] = 0
        fixture["valid_cases"][0]["expected_sha256"] = verifier.canonical_sha256(
            fixture["valid_cases"][0]["expected"]
        )
        fixture["sha256"] = verifier.canonical_sha256(
            {key: value for key, value in fixture.items() if key != "sha256"}
        )
        with self.assertRaisesRegex(ValueError, "shift_zero:independent_arithmetic"):
            verifier.verify_object(fixture, ROOT)

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["invalid_cases"][1]["status"] = "ok"
        fixture["sha256"] = verifier.canonical_sha256(
            {key: value for key, value in fixture.items() if key != "sha256"}
        )
        with self.assertRaisesRegex(ValueError, "count_sixty_three:status"):
            verifier.verify_object(fixture, ROOT)


if __name__ == "__main__":
    unittest.main()
