from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from survey.scripts.finalize_screening import (
    make_project_families,
    validate_decisions,
    write_screening_outputs,
)


class ScreeningDecisionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping = pd.DataFrame(
            [
                {
                    "record_index": 0,
                    "record_id": "REC-1",
                    "work_id": "WORK-1",
                    "title": "An FPGA transformer",
                    "auto_level": "B",
                    "auto_route_family": "DATAFLOW",
                    "screen_priority_score": 12,
                    "preferred_record_id": "REC-1",
                    "is_preferred_manifestation": True,
                    "dedup_rule": "unique",
                    "preferred_manifestation_rationale": "only manifestation",
                },
                {
                    "record_index": 1,
                    "record_id": "REC-2",
                    "work_id": "WORK-2",
                    "title": "An unrelated survey",
                    "auto_level": "X",
                    "auto_route_family": "",
                    "screen_priority_score": 1,
                    "preferred_record_id": "REC-2",
                    "is_preferred_manifestation": True,
                    "dedup_rule": "unique",
                    "preferred_manifestation_rationale": "only manifestation",
                },
            ]
        )
        self.decisions = pd.DataFrame(
            [
                {
                    "record_id": "REC-1",
                    "work_id": "WORK-1",
                    "final_level": "B",
                    "include_final": True,
                    "exclusion_code": "",
                    "reviewer": "codex-title-abstract-screen",
                    "review_basis": "title_abstract",
                    "evidence_location": "phase1_mapping.csv#REC-1:title+abstract",
                    "decision_notes": "Block-level FPGA transformer evidence.",
                    "project_family_id": "PF-1",
                    "family_is_primary_work": True,
                    "family_grouping_basis": "single_work_family",
                    "route_family_final": "DATAFLOW",
                },
                {
                    "record_id": "REC-2",
                    "work_id": "WORK-2",
                    "final_level": "X",
                    "include_final": False,
                    "exclusion_code": "X_SECONDARY",
                    "reviewer": "codex-title-abstract-screen",
                    "review_basis": "title_abstract",
                    "evidence_location": "phase1_mapping.csv#REC-2:title+abstract",
                    "decision_notes": "Secondary survey.",
                    "project_family_id": "",
                    "family_is_primary_work": False,
                    "family_grouping_basis": "",
                    "route_family_final": "",
                },
            ]
        )

    def assert_invalid(self, message: str, **changes: object) -> None:
        decisions = self.decisions.copy()
        for key, value in changes.items():
            decisions.loc[0, key] = value
        with self.assertRaisesRegex(ValueError, message):
            validate_decisions(self.mapping, decisions)

    def test_rejects_blank_final_level(self) -> None:
        self.assert_invalid("final_level", final_level="")

    def test_rejects_included_x_record(self) -> None:
        self.assert_invalid(
            "X records must be excluded",
            final_level="X",
            include_final=True,
            exclusion_code="X_NOT_FPGA",
            project_family_id="",
            family_is_primary_work=False,
            family_grouping_basis="",
        )

    def test_rejects_excluded_non_x_record(self) -> None:
        self.assert_invalid("A-D records must be included", include_final=False)

    def test_rejects_uncontrolled_exclusion_code(self) -> None:
        decisions = self.decisions.copy()
        decisions.loc[1, "exclusion_code"] = "X_OTHER"
        with self.assertRaisesRegex(ValueError, "controlled exclusion"):
            validate_decisions(self.mapping, decisions)

    def test_rejects_exclusion_code_on_included_record(self) -> None:
        self.assert_invalid(
            "A-D records cannot have an exclusion", exclusion_code="X_NOT_FPGA"
        )

    def test_rejects_missing_or_duplicate_source_decisions(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one decision"):
            validate_decisions(self.mapping, self.decisions.iloc[[0]])

        duplicate = pd.concat([self.decisions, self.decisions.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "exactly one decision"):
            validate_decisions(self.mapping, duplicate)

    def test_rejects_blank_reviewer_or_evidence(self) -> None:
        self.assert_invalid("reviewer", reviewer="")
        self.assert_invalid("evidence_location", evidence_location="")
        self.assert_invalid("review_basis", review_basis="")

    def test_rejects_included_record_without_project_family(self) -> None:
        self.assert_invalid(
            "project family",
            project_family_id="",
            family_is_primary_work=False,
            family_grouping_basis="",
        )

    def test_rejects_project_family_id_that_reuses_work_id(self) -> None:
        self.assert_invalid("distinct from work_id", project_family_id="WORK-1")

    def test_rejects_unknown_route_family(self) -> None:
        self.assert_invalid("controlled route family", route_family_final="OTHER")

    def test_preserves_automatic_fields_as_source_metadata(self) -> None:
        screened = validate_decisions(self.mapping, self.decisions)

        self.assertEqual(["B", "X"], screened["auto_level"].tolist())
        self.assertEqual([12, 1], screened["screen_priority_score"].tolist())
        self.assertEqual(["B", "X"], screened["final_level"].tolist())

    def test_controlled_decisions_override_blank_provisional_source_columns(self) -> None:
        mapping = self.mapping.assign(
            include_final="", exclusion_code="", reviewer=""
        )

        screened = validate_decisions(mapping, self.decisions)

        self.assertEqual([True, False], screened["include_final"].tolist())
        self.assertEqual(["", "X_SECONDARY"], screened["exclusion_code"].tolist())
        self.assertEqual(
            ["codex-title-abstract-screen"] * 2, screened["reviewer"].tolist()
        )
        self.assertEqual(["", ""], screened["include_final_source"].tolist())

    def test_writes_exclusion_family_and_traceable_audit_outputs(self) -> None:
        screened = validate_decisions(self.mapping, self.decisions)
        with TemporaryDirectory() as temporary:
            write_screening_outputs(screened, Path(temporary))

            exclusions = pd.read_csv(
                Path(temporary) / "phase1_exclusions.csv", keep_default_na=False
            )
            families = pd.read_csv(
                Path(temporary) / "project_families.csv", keep_default_na=False
            )
            audit = (Path(temporary) / "screening_audit.md").read_text()

        self.assertEqual(["REC-2"], exclusions["record_id"].tolist())
        self.assertEqual(["X_SECONDARY"], exclusions["exclusion_code"].tolist())
        self.assertEqual(["PF-1"], families["project_family_id"].tolist())
        self.assertIn("| B | 1 |", audit)
        self.assertIn("| X | 1 |", audit)
        self.assertIn("Duplicate/version decisions", audit)
        self.assertIn("Reviewer sample / re-review design", audit)
        self.assertIn("Unresolved but non-blocking uncertainty", audit)
        self.assertIn("SHA-256(`project-family:` + `work_id`)", audit)
        self.assertIn(
            "phase1_mapping.csv#REC-1:title+abstract",
            audit,
        )
        self.assertIn(
            "phase1_mapping.csv#REC-2:title+abstract",
            audit,
        )


class ProjectFamilyTests(unittest.TestCase):
    def family_rows(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "record_id": "REC-1",
                    "work_id": "WORK-1",
                    "preferred_record_id": "REC-1",
                    "title": "System foundation",
                    "final_level": "C",
                    "include_final": True,
                    "project_family_id": "PF-SYSTEM",
                    "family_is_primary_work": True,
                    "family_grouping_basis": "named_system_extension",
                    "evidence_location": "phase1_mapping.csv#REC-1:title+abstract",
                    "route_family_final": "HLS",
                },
                {
                    "record_id": "REC-2",
                    "work_id": "WORK-2",
                    "preferred_record_id": "REC-2",
                    "title": "System extension",
                    "final_level": "A",
                    "include_final": True,
                    "project_family_id": "PF-SYSTEM",
                    "family_is_primary_work": False,
                    "family_grouping_basis": "named_system_extension",
                    "evidence_location": "phase1_mapping.csv#REC-2:title+abstract",
                    "route_family_final": "HLS",
                },
            ]
        )

    def test_rejects_family_without_exactly_one_primary_work(self) -> None:
        screened = self.family_rows()
        screened["family_is_primary_work"] = False
        with self.assertRaisesRegex(ValueError, "exactly one primary work"):
            make_project_families(screened)

        screened["family_is_primary_work"] = True
        with self.assertRaisesRegex(ValueError, "exactly one primary work"):
            make_project_families(screened)

    def test_retains_each_linked_work_and_evidence_source(self) -> None:
        families = make_project_families(self.family_rows())

        self.assertEqual(["WORK-1", "WORK-2"], families["work_id"].tolist())
        self.assertEqual(["WORK-1", "WORK-1"], families["primary_work_id"].tolist())
        self.assertEqual(
            [
                '["phase1_mapping.csv#REC-1:title+abstract"]',
                '["phase1_mapping.csv#REC-2:title+abstract"]',
            ],
            families["evidence_sources_json"].tolist(),
        )


class FrozenScreeningArtifactTests(unittest.TestCase):
    def test_frozen_corpus_has_one_valid_traceable_decision_per_record(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        mapping = pd.read_csv(
            repository / "survey/build/phase1_mapping.csv", keep_default_na=False
        )
        decisions = pd.read_csv(
            repository / "survey/data/screening_decisions.csv",
            keep_default_na=False,
        )

        screened = validate_decisions(mapping, decisions)
        families = make_project_families(screened)

        self.assertEqual(461, len(screened))
        self.assertEqual(461, screened["record_id"].nunique())
        self.assertEqual(
            {"codex-title-abstract-screen"}, set(screened["reviewer"])
        )
        self.assertEqual(
            set(screened.loc[screened["include_final"], "work_id"]),
            set(families["work_id"]),
        )
        self.assertTrue(
            set(families["project_family_id"]).isdisjoint(set(mapping["work_id"]))
        )

        nonpreferred = screened.loc[~screened["is_preferred_manifestation"]]
        self.assertEqual(5, len(nonpreferred))
        self.assertEqual({"X"}, set(nonpreferred["final_level"]))
        self.assertEqual({"X_DUPLICATE"}, set(nonpreferred["exclusion_code"]))


if __name__ == "__main__":
    unittest.main()
