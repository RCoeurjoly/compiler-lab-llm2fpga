from __future__ import annotations

import hashlib
import json
import shutil
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
                    "pdf_url": "https://arxiv.org/pdf/1234.00001v1",
                    "cache_sha256": "1" * 64,
                    "cache_json": json.dumps({"filename": "1234.00001v1.pdf"}),
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
                    "pdf_url": "https://arxiv.org/pdf/1234.00002v1",
                    "cache_sha256": "2" * 64,
                    "cache_json": json.dumps({"filename": "1234.00002v1.pdf"}),
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
                    "evidence_location": (
                        "survey/build/phase1_mapping.csv#record_id=REC-1:"
                        "title+abstract"
                    ),
                    "decision_notes": "Block-level FPGA transformer evidence.",
                    "project_family_id": "PF-4C2FEC15D9875CAC",
                    "project_family_key": "WORK-1",
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
                    "evidence_location": (
                        "survey/build/phase1_mapping.csv#record_id=REC-2:"
                        "title+abstract"
                    ),
                    "decision_notes": "Secondary survey.",
                    "project_family_id": "",
                    "project_family_key": "",
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
            project_family_key="",
            family_is_primary_work=False,
            family_grouping_basis="",
        )

    def test_rejects_noncanonical_project_family_id(self) -> None:
        self.assert_invalid(
            "derived from project_family_key", project_family_id="PF-ARBITRARY"
        )

    def test_rejects_malformed_or_wrong_single_work_family_key(self) -> None:
        self.assert_invalid(
            "project_family_key must be canonical",
            project_family_key="named-system:Invalid Slug",
        )
        self.assert_invalid(
            "single-work project_family_key",
            project_family_key="WORK-2",
        )

    def test_rejects_unknown_route_family(self) -> None:
        self.assert_invalid("controlled route family", route_family_final="OTHER")

    def test_requires_route_family_for_levels_a_through_c(self) -> None:
        self.assert_invalid("A-C records require", route_family_final="")

    def test_title_abstract_evidence_binds_the_current_record_and_path(self) -> None:
        decisions = self.decisions.copy()
        decisions.loc[0, "evidence_location"] = (
            "survey/build/phase1_mapping.csv#record_id=REC-2:title+abstract"
        )
        with self.assertRaisesRegex(ValueError, "own frozen mapping record"):
            validate_decisions(self.mapping, decisions)

        decisions.loc[0, "evidence_location"] = "/tmp/REC-1:title+abstract"
        with self.assertRaisesRegex(ValueError, "local path"):
            validate_decisions(self.mapping, decisions)

    def test_full_text_basis_requires_portable_source_and_cache_identity(self) -> None:
        decisions = self.decisions.copy()
        decisions.loc[0, "review_basis"] = "title_abstract+local_full_text"
        decisions.loc[0, "evidence_location"] = (
            "survey/build/phase1_mapping.csv#record_id=REC-1:title+abstract"
        )
        with self.assertRaisesRegex(ValueError, "portable full-text evidence"):
            validate_decisions(self.mapping, decisions)

        valid_evidence = (
            "survey/build/phase1_mapping.csv#record_id=REC-1:title+abstract;"
            "source_url=https://arxiv.org/pdf/1234.00001v1;"
            "cache_filename=1234.00001v1.pdf;"
            f"cache_sha256={'1' * 64};locator=page 1"
        )
        decisions.loc[0, "evidence_location"] = valid_evidence
        validate_decisions(self.mapping, decisions)

        local_references = (
            "local_cache=/tmp/private-copy.pdf",
            "source_copy=/home/reviewer/private-copy.pdf",
            r"cache_filename=C:\reviewer\private-copy.pdf",
            "source_url=file:///tmp/private-copy.pdf",
        )
        for local_reference in local_references:
            with self.subTest(local_reference=local_reference):
                decisions.loc[0, "evidence_location"] = (
                    f"{valid_evidence};{local_reference}"
                )
                with self.assertRaisesRegex(ValueError, "local path"):
                    validate_decisions(self.mapping, decisions)

    def test_rejects_invalid_or_primary_flag_on_unlinked_record(self) -> None:
        decisions = self.decisions.copy()
        decisions["family_is_primary_work"] = decisions[
            "family_is_primary_work"
        ].astype(object)
        decisions.loc[1, "family_is_primary_work"] = "not-a-boolean"
        with self.assertRaisesRegex(
            ValueError, "family_is_primary_work must be Boolean"
        ):
            validate_decisions(self.mapping, decisions)

        decisions.loc[1, "family_is_primary_work"] = True
        with self.assertRaisesRegex(ValueError, "without a project family"):
            validate_decisions(self.mapping, decisions)

    def duplicate_fixture(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        mapping = pd.concat(
            [
                self.mapping.iloc[[0]],
                self.mapping.iloc[[0]].assign(
                    record_index=2,
                    record_id="REC-1-OLD",
                    preferred_record_id="REC-1",
                    is_preferred_manifestation=False,
                    dedup_rule="exact_arxiv",
                ),
            ],
            ignore_index=True,
        )
        mapping.loc[0, "preferred_record_id"] = "REC-1"
        mapping.loc[0, "is_preferred_manifestation"] = True
        mapping.loc[0, "dedup_rule"] = "preferred_manifestation"
        decisions = pd.concat(
            [
                self.decisions.iloc[[0]],
                self.decisions.iloc[[1]].assign(
                    record_id="REC-1-OLD",
                    work_id="WORK-1",
                    exclusion_code="X_DUPLICATE",
                    project_family_id="PF-4C2FEC15D9875CAC",
                    project_family_key="WORK-1",
                    family_is_primary_work=True,
                    family_grouping_basis="single_work_family",
                ),
            ],
            ignore_index=True,
        )
        return mapping, decisions

    def test_rejects_invalid_preferred_and_duplicate_lineage(self) -> None:
        mapping, decisions = self.duplicate_fixture()

        included_duplicate = decisions.copy()
        included_duplicate.loc[
            1,
            [
                "final_level",
                "include_final",
                "exclusion_code",
                "route_family_final",
            ],
        ] = ["B", True, "", "DATAFLOW"]
        with self.assertRaisesRegex(ValueError, "non-preferred manifestations"):
            validate_decisions(mapping, included_duplicate)

        preferred_duplicate = self.decisions.copy()
        preferred_duplicate.loc[1, "exclusion_code"] = "X_DUPLICATE"
        with self.assertRaisesRegex(ValueError, "only on non-preferred"):
            validate_decisions(self.mapping, preferred_duplicate)

        split_family = decisions.copy()
        split_family.loc[1, "project_family_key"] = "named-system:other"
        split_family.loc[1, "project_family_id"] = "PF-28B67C9C652831BA"
        with self.assertRaisesRegex(ValueError, "project family key"):
            validate_decisions(mapping, split_family)

        no_preferred = mapping.copy()
        no_preferred["is_preferred_manifestation"] = False
        with self.assertRaisesRegex(ValueError, "exactly one preferred"):
            validate_decisions(no_preferred, decisions)

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

    def _write_frozen_phase1_inputs(
        self, output: Path
    ) -> tuple[Path, dict[str, object], bytes]:
        mapping_path = output / "phase1_mapping.csv"
        self.mapping.to_csv(mapping_path, index=False, lineterminator="\n")
        mapping_bytes = mapping_path.read_bytes()
        source_counts: dict[str, object] = {
            "auto_levels": {"A": 0, "B": 1, "C": 0, "D": 0, "X": 1},
            "candidate_unique_works": 2,
            "duplicate_manifestations": 0,
            "duplicate_work_groups": 0,
            "input_records": 2,
            "manual_review_queue": 2,
        }
        flow_bytes = (
            json.dumps(source_counts, indent=2, sort_keys=True) + "\n"
        ).encode()
        (output / "flow_counts.json").write_bytes(flow_bytes)
        phase1_run = {
            "output_sha256": {
                "flow_counts.json": hashlib.sha256(flow_bytes).hexdigest(),
                "phase1_mapping.csv": hashlib.sha256(mapping_bytes).hexdigest(),
            }
        }
        (output / "phase1_run.json").write_text(
            json.dumps(phase1_run, indent=2, sort_keys=True) + "\n"
        )
        return mapping_path, source_counts, flow_bytes

    def test_writes_exclusion_family_and_traceable_audit_outputs(self) -> None:
        screened = validate_decisions(self.mapping, self.decisions)
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            mapping_path, source_counts, flow_bytes = self._write_frozen_phase1_inputs(
                output
            )
            write_screening_outputs(screened, output, mapping_path=mapping_path)

            exclusions = pd.read_csv(
                output / "phase1_exclusions.csv", keep_default_na=False
            )
            families = pd.read_csv(
                output / "project_families.csv", keep_default_na=False
            )
            audit = (output / "screening_audit.md").read_text()
            final_counts = json.loads((output / "final_flow_counts.json").read_text())
            repeat_sample = pd.read_csv(
                output / "repeat_review_sample.csv", keep_default_na=False
            )

        self.assertEqual(["REC-2"], exclusions["record_id"].tolist())
        self.assertEqual(["X_SECONDARY"], exclusions["exclusion_code"].tolist())
        self.assertEqual(
            ["PF-4C2FEC15D9875CAC"], families["project_family_id"].tolist()
        )
        self.assertIn("| B | 1 |", audit)
        self.assertIn("| X | 1 |", audit)
        self.assertIn("Duplicate/version decisions", audit)
        self.assertIn("When the preferred manifestation is included", audit)
        self.assertIn("Reviewer sample / re-review design", audit)
        self.assertIn("| B | 1 | 1 |", audit)
        self.assertIn("| X | 1 | 1 |", audit)
        self.assertIn("Unresolved but non-blocking uncertainty", audit)
        self.assertIn("SHA-256(`project-family:` + `work_id`)", audit)
        self.assertIn(
            "survey/build/phase1_mapping.csv#record_id=REC-1:title+abstract",
            audit,
        )
        self.assertIn(
            "survey/build/phase1_mapping.csv#record_id=REC-2:title+abstract",
            audit,
        )
        self.assertEqual(source_counts["auto_levels"], final_counts["auto_levels"])
        self.assertEqual(
            {"A": 0, "B": 1, "C": 0, "D": 0, "X": 1},
            final_counts["final_levels"],
        )
        self.assertEqual(1, final_counts["included_records"])
        self.assertEqual(1, final_counts["excluded_records"])
        self.assertEqual(1, final_counts["project_family_count"])
        self.assertEqual(
            hashlib.sha256(flow_bytes).hexdigest(),
            final_counts["source_phase1_flow_counts_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                self.mapping.to_csv(index=False, lineterminator="\n").encode()
            ).hexdigest(),
            final_counts["source_phase1_mapping_sha256"],
        )
        self.assertEqual({"REC-1", "REC-2"}, set(repeat_sample["record_id"]))
        self.assertEqual(
            {"lowest stable hashes; ceil(20%)"},
            set(repeat_sample["selection_rule"]),
        )

    def test_rejects_mapping_bytes_that_do_not_match_phase1_receipt(self) -> None:
        screened = validate_decisions(self.mapping, self.decisions)
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            mapping_path, _, _ = self._write_frozen_phase1_inputs(output)
            mapping_path.write_bytes(mapping_path.read_bytes() + b"\n")

            with self.assertRaisesRegex(ValueError, "phase1_mapping.csv no longer"):
                write_screening_outputs(screened, output, mapping_path=mapping_path)

    def test_mapping_receipt_mismatch_preserves_all_final_artifacts(self) -> None:
        """Receipt validation must precede every final-artifact write."""

        screened = validate_decisions(self.mapping, self.decisions)
        final_artifacts = (
            "phase1_exclusions.csv",
            "project_families.csv",
            "repeat_review_sample.csv",
            "final_flow_counts.json",
            "screening_audit.md",
        )
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            mapping_path, _, _ = self._write_frozen_phase1_inputs(output)
            sentinels = {
                artifact: f"unchanged sentinel for {artifact}\n".encode()
                for artifact in final_artifacts
            }
            for artifact, sentinel in sentinels.items():
                (output / artifact).write_bytes(sentinel)
            mapping_path.write_bytes(mapping_path.read_bytes() + b"\n")

            with self.assertRaisesRegex(ValueError, "phase1_mapping.csv no longer"):
                write_screening_outputs(screened, output, mapping_path=mapping_path)

            for artifact, sentinel in sentinels.items():
                self.assertEqual(sentinel, (output / artifact).read_bytes())


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
                    "project_family_id": "PF-EE98D34497449122",
                    "project_family_key": "named-system:system",
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
                    "project_family_id": "PF-EE98D34497449122",
                    "project_family_key": "named-system:system",
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
            ["PF-EE98D34497449122", "PF-EE98D34497449122"],
            families["project_family_id"].tolist(),
        )
        self.assertEqual(
            ["named-system:system", "named-system:system"],
            families["project_family_key"].tolist(),
        )
        self.assertEqual(
            [
                '["phase1_mapping.csv#REC-1:title+abstract"]',
                '["phase1_mapping.csv#REC-2:title+abstract"]',
            ],
            families["evidence_sources_json"].tolist(),
        )

    def test_rejects_one_work_split_across_project_families(self) -> None:
        screened = self.family_rows()
        screened["work_id"] = "WORK-1"
        screened["preferred_record_id"] = "REC-1"
        screened.loc[1, "project_family_key"] = "named-system:other"
        screened.loc[1, "project_family_id"] = "PF-28B67C9C652831BA"
        screened["family_is_primary_work"] = True

        with self.assertRaisesRegex(ValueError, "exactly one project family"):
            make_project_families(screened)

    def test_rejects_primary_work_without_included_preferred_manifestation(self) -> None:
        screened = self.family_rows()
        screened.loc[0, "record_id"] = "REC-1-OLD"

        with self.assertRaisesRegex(ValueError, "included preferred manifestation"):
            make_project_families(screened)

    def test_rejects_arbitrary_project_family_id_before_family_output(self) -> None:
        screened = self.family_rows()
        screened.loc[0, "project_family_id"] = "PF-ARBITRARY"

        with self.assertRaisesRegex(ValueError, "derived from project_family_key"):
            make_project_families(screened)

    def test_rejects_named_system_key_for_a_single_work(self) -> None:
        screened = self.family_rows().iloc[[0]].copy()

        with self.assertRaisesRegex(
            ValueError, "named-system project_family_key must link multiple works"
        ):
            make_project_families(screened)


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
        final_counts = json.loads(
            (repository / "survey/build/final_flow_counts.json").read_text()
        )

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
        linked = screened.loc[screened["project_family_key"].ne("")]
        self.assertTrue(
            linked.apply(
                lambda row: row["project_family_id"]
                == "PF-"
                + hashlib.sha256(
                    f"project-family:{row['project_family_key']}".encode()
                ).hexdigest()[:16].upper(),
                axis=1,
            ).all()
        )

        nonpreferred = screened.loc[~screened["is_preferred_manifestation"]]
        self.assertEqual(5, len(nonpreferred))
        self.assertEqual({"X"}, set(nonpreferred["final_level"]))
        self.assertEqual({"X_DUPLICATE"}, set(nonpreferred["exclusion_code"]))

        full_text = screened.loc[
            screened["review_basis"].eq("title_abstract+local_full_text"),
            "evidence_location",
        ]
        self.assertEqual(51, len(full_text))
        self.assertTrue(full_text.str.contains(";source_url=https://").all())
        self.assertTrue(full_text.str.contains(";cache_filename=").all())
        self.assertTrue(full_text.str.contains(";cache_sha256=").all())
        self.assertTrue(full_text.str.contains(";locator=").all())
        self.assertFalse(full_text.str.contains("/home/").any())
        self.assertFalse(
            full_text.str.contains("LLM-inference-on-FPGA-papers/papers/").any()
        )

        expected_extensions = [
            (
                "REC-0A35BCF12DE7E299",
                "REC-48B14D3F981A4130",
                "WORK-D98F092B3E212C22",
            ),
            (
                "REC-0ED11F871A636313",
                "REC-397AA2E8B322E5B6",
                "WORK-76ACBFCD99E4F225",
            ),
            (
                "REC-22B8F133078A7448",
                "REC-0E5CD4ABE22322D8",
                "WORK-674CDDB57508D5CE",
            ),
            (
                "REC-4C2E95DDB8B7F21F",
                "REC-66B094C6BAA51FA7",
                "WORK-2D44FCCE8D9826E3",
            ),
        ]
        for foundation_id, extension_id, primary_work_id in expected_extensions:
            linked = screened.loc[
                screened["record_id"].isin([foundation_id, extension_id])
            ]
            self.assertEqual(1, linked["project_family_id"].nunique())
            self.assertEqual(
                {False, True}, set(linked["family_is_primary_work"])
            )
            self.assertTrue(
                linked["family_grouping_basis"]
                .str.startswith("named_system_")
                .all()
            )
            relation = families.loc[
                families["project_family_id"].eq(
                    linked["project_family_id"].iloc[0]
                )
            ]
            self.assertEqual(2, len(relation))
            self.assertEqual({primary_work_id}, set(relation["primary_work_id"]))

        self.assertEqual(230, len(families))
        self.assertEqual(226, families["project_family_id"].nunique())
        self.assertEqual(
            4,
            sum(
                len(group) > 1
                for _, group in families.groupby("project_family_id", sort=True)
            ),
        )

        unrelated_pairs = [
            ("REC-1D91E09883329FFA", "REC-A53433EACA5A3E39"),
            ("REC-F95950AEA19221D0", "REC-6099EE66504F6EF2"),
            ("REC-8079DF7689E5D2AD", "REC-361ADBB8874502B6"),
        ]
        for left_id, right_id in unrelated_pairs:
            unrelated = screened.loc[
                screened["record_id"].isin([left_id, right_id]),
                "project_family_id",
            ]
            self.assertEqual(2, unrelated.nunique())
        self.assertEqual(461, final_counts["input_records"])
        self.assertEqual(456, final_counts["candidate_unique_works"])
        self.assertEqual(
            {"A": 30, "B": 57, "C": 75, "D": 68, "X": 231},
            final_counts["final_levels"],
        )
        self.assertEqual(226, final_counts["project_family_count"])
        qat = screened.loc[
            screened["record_id"].eq("REC-BCED24E48DF96CCD")
        ].iloc[0]
        self.assertEqual("X", qat["final_level"])
        self.assertEqual("X_TRAINING_ONLY", qat["exclusion_code"])
        self.assertEqual("title_abstract+local_full_text", qat["review_basis"])
        self.assertIn("section=6.3.Extension_to_Mixed-precision_Quantisation", qat["evidence_location"])
        audit = (repository / "survey/build/screening_audit.md").read_text()
        for expected in (
            "| A | 30 | 30 |",
            "| B | 57 | 12 |",
            "| C | 75 | 75 |",
            "| D | 68 | 14 |",
            "| X | 231 | 47 |",
            "## Explicit conservative non-merges",
            "REC-1D91E09883329FFA; REC-A53433EACA5A3E39",
            "the cited conference predecessor is a different 2021 work",
            "REC-F95950AEA19221D0; REC-6099EE66504F6EF2",
            "shared use of hls4ml is insufficient without an explicit cross-citation",
            "REC-8079DF7689E5D2AD; REC-361ADBB8874502B6",
            "no direct release, version, or extension evidence",
        ):
            self.assertIn(expected, audit)

        with TemporaryDirectory() as temporary:
            regenerated = Path(temporary)
            for source_name in (
                "flow_counts.json",
                "phase1_run.json",
                "phase1_mapping.csv",
            ):
                shutil.copyfile(
                    repository / "survey/build" / source_name,
                    regenerated / source_name,
                )
            write_screening_outputs(
                screened,
                regenerated,
                mapping_path=regenerated / "phase1_mapping.csv",
            )
            for artifact_name in (
                "phase1_exclusions.csv",
                "project_families.csv",
                "screening_audit.md",
                "final_flow_counts.json",
                "repeat_review_sample.csv",
            ):
                self.assertEqual(
                    (repository / "survey/build" / artifact_name).read_bytes(),
                    (regenerated / artifact_name).read_bytes(),
                    artifact_name,
                )


if __name__ == "__main__":
    unittest.main()
