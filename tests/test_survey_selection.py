from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from survey.scripts.select_deep_review import (
    DEEP_REVIEW_COLUMNS,
    score_family,
    select_families,
    validate_reviews,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "survey/scripts/select_deep_review.py"


def _family(index: int, **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "project_family_id": f"PF-{index:016X}",
        "primary_work_id": f"WORK-{index:016X}",
        "project_family_key": f"WORK-{index:016X}",
        "work_id": f"WORK-{index:016X}",
        "is_primary_work": True,
        "preferred_record_id": f"REC-{index:016X}",
        "record_ids_json": json.dumps([f"REC-{index:016X}"]),
        "title": f"Family {index:02d}",
        "level_final": "B",
        "route_family": "HLS",
        "family_grouping_basis": "single_work_family",
        "evidence_sources_json": json.dumps(
            [f"https://example.test/paper-{index:02d}#abstract"]
        ),
    }
    row.update(changes)
    return row


def _review(family: dict[str, object], **changes: object) -> dict[str, object]:
    row = {column: "" for column in DEEP_REVIEW_COLUMNS}
    location = (
        f"https://example.test/paper-{family['project_family_id']}#abstract"
    )
    row.update(
        {
            "project_family_id": family["project_family_id"],
            "title": family["title"],
            "level_final": family["level_final"],
            "route_family": family["route_family"],
            "preferred_record_id": family["preferred_record_id"],
            "mandatory_reason": "",
            "causal_lm_relevance_score": 2,
            "distinct_route_score": 2,
            "artifact_availability_score": 1,
            "open_toolchain_migration_score": 1,
            "quantitative_evidence_score": 1,
            "selection_score": 7,
            "evidence_locations": json.dumps(
                {
                    field: location
                    for field in (
                        "level_final",
                        "route_family",
                        "mandatory_reason",
                        "causal_lm_relevance_score",
                        "distinct_route_score",
                        "artifact_availability_score",
                        "open_toolchain_migration_score",
                        "quantitative_evidence_score",
                    )
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            "notes": "documented from the cited abstract",
        }
    )
    row.update(changes)
    if "selection_score" not in changes:
        row["selection_score"] = sum(
            int(row[field])
            for field in (
                "causal_lm_relevance_score",
                "distinct_route_score",
                "artifact_availability_score",
                "open_toolchain_migration_score",
                "quantitative_evidence_score",
            )
        )
    return row


def _controlled_fixture(
    families: list[dict[str, object]],
    reviews: list[dict[str, object]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    families = [dict(row) for row in families]
    reviews = [dict(row) for row in reviews]
    by_id = {str(row["project_family_id"]): row for row in reviews}
    for family in families:
        if family["level_final"] == "A":
            by_id[str(family["project_family_id"])][
                "mandatory_reason"
            ] = "supported_level_a"

    routes = [
        "MLIR_CIRCT",
        "PARAMETERIZED_RTL",
        "HLS",
        "DATAFLOW",
        "OVERLAY",
        "CPU_FPGA_FALLBACK",
    ]
    for offset, route in enumerate(routes):
        family = _family(10_000 + offset, level_final="C", route_family=route)
        families.append(family)
        reviews.append(
            _review(
                family,
                mandatory_reason=(
                    "distinct_executable_c_route|route_incompatibility_case"
                ),
            )
        )
    control = _family(
        99_999,
        project_family_id="CONTROL-COMPILER-LAB",
        preferred_record_id="CONTROL-COMPILER-LAB",
        title="compiler-lab artifact control",
        level_final="CONTROL",
        route_family="MLIR_CIRCT",
    )
    reviews.append(
        _review(
            control,
            mandatory_reason="compiler_lab_artifact_control|open_block_artifact",
        )
    )
    return pd.DataFrame(families), pd.DataFrame(reviews)


class DeepReviewSelectionTests(unittest.TestCase):
    def test_score_family_sums_the_five_bounded_protocol_dimensions(self) -> None:
        row = pd.Series(
            {
                "causal_lm_relevance_score": 3,
                "distinct_route_score": 2,
                "artifact_availability_score": 2,
                "open_toolchain_migration_score": 2,
                "quantitative_evidence_score": 1,
            }
        )
        self.assertEqual(score_family(row), 10)

        for field, invalid in (
            ("causal_lm_relevance_score", 4),
            ("distinct_route_score", -1),
            ("quantitative_evidence_score", 2),
        ):
            with self.subTest(field=field):
                broken = row.copy()
                broken[field] = invalid
                with self.assertRaisesRegex(ValueError, field):
                    score_family(broken)

    def test_includes_all_supported_level_a_distinct_c_routes_and_control(self) -> None:
        routes = ["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"]
        c_routes = [
            "MLIR_CIRCT",
            "DATAFLOW",
            "HLS",
            "OVERLAY",
            "PARAMETERIZED_RTL",
            "CPU_FPGA_FALLBACK",
        ]
        families = [
            _family(1, level_final="A", route_family="DATAFLOW"),
            *[
                _family(index + 2, level_final="C", route_family=route)
                for index, route in enumerate(c_routes)
            ],
            *[
                _family(i, route_family=routes[(i - 3) % len(routes)])
                for i in range(8, 29)
            ],
        ]
        reviews = [_review(row) for row in families]
        reviews[0]["mandatory_reason"] = "supported_level_a"
        for row in reviews[1:7]:
            row["mandatory_reason"] = (
                "distinct_executable_c_route|route_incompatibility_case"
            )
        control = _family(
            99,
            project_family_id="CONTROL-COMPILER-LAB",
            primary_work_id="CONTROL-COMPILER-LAB",
            work_id="CONTROL-COMPILER-LAB",
            preferred_record_id="CONTROL-COMPILER-LAB",
            record_ids_json='["CONTROL-COMPILER-LAB"]',
            title="compiler-lab artifact control",
            level_final="CONTROL",
            route_family="MLIR_CIRCT",
        )
        reviews.append(
            _review(
                control,
                mandatory_reason=(
                    "compiler_lab_artifact_control|open_block_artifact"
                ),
                causal_lm_relevance_score=3,
            )
        )

        selected = select_families(pd.DataFrame(families), pd.DataFrame(reviews))

        self.assertTrue(
            {
                families[0]["project_family_id"],
                *(row["project_family_id"] for row in families[1:7]),
                "CONTROL-COMPILER-LAB",
            }.issubset(set(selected["project_family_id"]))
        )

    def test_controlled_composition_rejects_a_missing_executable_c_route(self) -> None:
        routes = ["MLIR_CIRCT", "DATAFLOW", "HLS", "OVERLAY", "PARAMETERIZED_RTL"]
        families = [
            _family(1, level_final="A", route_family="DATAFLOW"),
            *[
                _family(index + 2, level_final="C", route_family=route)
                for index, route in enumerate(routes)
            ],
            *[
                _family(i, route_family=["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"][i % 4])
                for i in range(7, 30)
            ],
        ]
        reviews = [_review(row) for row in families]
        reviews[0]["mandatory_reason"] = "supported_level_a"
        for row in reviews[1:6]:
            row["mandatory_reason"] = (
                "distinct_executable_c_route|route_incompatibility_case"
            )
        control = _family(
            99,
            project_family_id="CONTROL-COMPILER-LAB",
            preferred_record_id="CONTROL-COMPILER-LAB",
            title="compiler-lab artifact control",
            level_final="CONTROL",
            route_family="MLIR_CIRCT",
        )
        reviews.append(
            _review(control, mandatory_reason="compiler_lab_artifact_control")
        )

        with self.assertRaisesRegex(ValueError, "each executable C route"):
            select_families(pd.DataFrame(families), pd.DataFrame(reviews))

    def test_uses_project_family_id_as_the_final_stable_tie_break(self) -> None:
        routes = ["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"]
        families = [
            _family(i, route_family=routes[(i - 1) % len(routes)])
            for i in range(1, 42)
        ]
        reviews = [_review(row) for row in families]

        family_frame, review_frame = _controlled_fixture(families, reviews)
        selected = select_families(family_frame, review_frame)

        self.assertEqual(len(selected), 40)
        self.assertNotIn(families[-1]["project_family_id"], set(selected.project_family_id))
        self.assertEqual(
            list(selected.project_family_id), sorted(selected.project_family_id)
        )

    def test_enforces_25_to_40_selection_bounds(self) -> None:
        too_few = [_family(i) for i in range(1, 18)]
        family_frame, review_frame = _controlled_fixture(
            too_few, [_review(row) for row in too_few]
        )
        with self.assertRaisesRegex(ValueError, "at least 25"):
            select_families(family_frame, review_frame)

        routes = ["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"]
        enough = [
            _family(i, route_family=routes[(i - 1) % len(routes)])
            for i in range(1, 46)
        ]
        family_frame, review_frame = _controlled_fixture(
            enough, [_review(row) for row in enough]
        )
        selected = select_families(family_frame, review_frame)
        self.assertGreaterEqual(len(selected), 25)
        self.assertLessEqual(len(selected), 40)

    def test_route_family_cap_is_30_percent_without_level_a_exception(self) -> None:
        routes = (
            ["HLS"] * 16
            + ["DATAFLOW"] * 8
            + ["OVERLAY"] * 8
            + ["PARAMETERIZED_RTL"] * 8
        )
        families = [
            _family(i + 1, route_family=route) for i, route in enumerate(routes)
        ]
        family_frame, review_frame = _controlled_fixture(
            families, [_review(row) for row in families]
        )
        selected = select_families(family_frame, review_frame)
        counts = selected.route_family.value_counts()
        self.assertLessEqual(counts.max(), int(len(selected) * 0.30))

    def test_all_level_a_families_permit_a_documented_route_cap_exception(self) -> None:
        non_a_routes = ["HLS"] * 9 + ["OVERLAY"] * 9 + ["PARAMETERIZED_RTL"] * 8
        families = [
            _family(
                i,
                level_final="A" if i <= 14 else "B",
                route_family="DATAFLOW" if i <= 14 else non_a_routes[i - 15],
            )
            for i in range(1, 41)
        ]
        reviews = [_review(row) for row in families]
        for row in reviews[:14]:
            row["mandatory_reason"] = "supported_level_a"

        family_frame, review_frame = _controlled_fixture(families, reviews)
        selected = select_families(family_frame, review_frame)

        self.assertEqual(
            set(row["project_family_id"] for row in families[:14]),
            set(selected.loc[selected.level_final.eq("A"), "project_family_id"]),
        )
        self.assertEqual(selected.attrs["route_cap_exception"], "DATAFLOW")

    def test_returns_the_mandatory_set_when_it_already_fills_the_target(self) -> None:
        routes = ["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"]
        families = [
            _family(i, route_family=routes[(i - 1) % len(routes)])
            for i in range(1, 19)
        ]
        reviews = [
            _review(row, mandatory_reason="open_block_artifact")
            for row in families
        ]

        family_frame, review_frame = _controlled_fixture(families, reviews)
        selected = select_families(family_frame, review_frame)

        self.assertEqual(len(selected), 25)
        self.assertEqual(
            set(selected.project_family_id),
            set(review_frame.project_family_id),
        )

    def test_validation_requires_exact_schema_and_evidence_for_nonempty_rq_claims(self) -> None:
        family = _family(1)
        row = _review(family, rq2_model_family="decoder-only causal LM")
        with self.assertRaisesRegex(ValueError, "rq2_model_family"):
            validate_reviews(pd.DataFrame([row]))

        evidence = json.loads(row["evidence_locations"])
        evidence["rq2_model_family"] = "https://example.test/paper-01#abstract"
        row["evidence_locations"] = json.dumps(evidence)
        validate_reviews(pd.DataFrame([row]))

        extra = pd.DataFrame([{**row, "invented_alias": "value"}])
        with self.assertRaisesRegex(ValueError, "exact deep-review schema"):
            validate_reviews(extra)

    def test_zero_score_is_a_decision_and_requires_evidence(self) -> None:
        family = _family(1)
        row = _review(
            family,
            artifact_availability_score=0,
            selection_score=6,
        )
        evidence = json.loads(row["evidence_locations"])
        evidence.pop("artifact_availability_score")
        row["evidence_locations"] = json.dumps(evidence)

        with self.assertRaisesRegex(ValueError, "artifact_availability_score"):
            validate_reviews(pd.DataFrame([row]))

    def test_rejects_selection_without_the_compiler_lab_control(self) -> None:
        routes = ["HLS", "DATAFLOW", "OVERLAY", "PARAMETERIZED_RTL"]
        families = [
            _family(i, route_family=routes[(i - 1) % len(routes)])
            for i in range(1, 30)
        ]

        with self.assertRaisesRegex(ValueError, "compiler-lab control"):
            select_families(
                pd.DataFrame(families),
                pd.DataFrame([_review(row) for row in families]),
            )

    def test_level_a_exception_does_not_admit_optional_same_route_rows(self) -> None:
        route_vocabulary = [
            "MLIR_CIRCT",
            "PARAMETERIZED_RTL",
            "HLS",
            "DATAFLOW",
            "OVERLAY",
            "CPU_FPGA_FALLBACK",
        ]
        mandatory_a = [
            _family(i, level_final="A", route_family="DATAFLOW")
            for i in range(1, 15)
        ]
        optional_dataflow = [
            _family(i, route_family="DATAFLOW") for i in range(15, 35)
        ]
        c_routes = [
            _family(100 + i, level_final="C", route_family=route)
            for i, route in enumerate(route_vocabulary)
        ]
        other_optional = [
            _family(200 + i, route_family=route_vocabulary[i % 5])
            for i in range(30)
        ]
        families = mandatory_a + optional_dataflow + c_routes + other_optional
        reviews = [_review(row) for row in families]
        for row in reviews[:14]:
            row["mandatory_reason"] = "supported_level_a"
        for row in reviews[34:40]:
            row["mandatory_reason"] = (
                "distinct_executable_c_route|route_incompatibility_case"
            )
        control = _family(
            999,
            project_family_id="CONTROL-COMPILER-LAB",
            preferred_record_id="CONTROL-COMPILER-LAB",
            title="compiler-lab artifact control",
            level_final="CONTROL",
            route_family="MLIR_CIRCT",
        )
        reviews.append(
            _review(
                control,
                mandatory_reason=(
                    "compiler_lab_artifact_control|open_block_artifact"
                ),
            )
        )

        selected = select_families(pd.DataFrame(families), pd.DataFrame(reviews))

        self.assertEqual(
            int(selected["route_family"].eq("DATAFLOW").sum()),
            15,
        )

    def test_committed_paper_claims_use_pdf_page_evidence_and_correct_known_rows(self) -> None:
        reviews = pd.read_csv(
            ROOT / "survey/data/deep_review_manual.csv",
            dtype=str,
            keep_default_na=False,
        )
        paper_rows = reviews.loc[reviews["project_family_id"].ne("CONTROL-COMPILER-LAB")]
        rq_columns = [column for column in DEEP_REVIEW_COLUMNS if column.startswith("rq")]
        for _, row in paper_rows.iterrows():
            evidence = json.loads(row["evidence_locations"])
            for field, location in evidence.items():
                with self.subTest(project_family_id=row["project_family_id"], field=field):
                    self.assertIn("https://arxiv.org/pdf/", location)
                    self.assertIn(";cache_sha256=", location)
                    self.assertIn(";locator=page", location)
                    self.assertNotIn("#abstract", location)
            for column in rq_columns:
                if not row[column]:
                    continue
                with self.subTest(project_family_id=row["project_family_id"], field=column):
                    self.assertIn(column, evidence)

        by_id = paper_rows.set_index("project_family_id")
        fastmamba = by_id.loc["PF-5345A35EEB976D35"]
        self.assertEqual(fastmamba["rq2_attention"], "")
        self.assertIn("8-bit", fastmamba["rq5_precision"])

        tataa = by_id.loc["PF-5487714A7E757A5C"]
        self.assertIn("INT8", tataa["rq5_precision"])
        self.assertIn("bfloat16", tataa["rq5_precision"])
        self.assertIn("2935.2 GOPS", tataa["rq5_throughput"])
        self.assertIn("189.5 GFLOPS", tataa["rq5_throughput"])

        meadow = by_id.loc["PF-7E3A5FA298AD6A6F"]
        self.assertEqual(meadow["rq5_precision"], "")
        self.assertTrue(meadow["rq5_latency"])
        self.assertTrue(meadow["rq5_power"])

    def test_fastmamba_pdf_primary_energy_evidence_discloses_catalog_conflict(self) -> None:
        reviews = pd.read_csv(
            ROOT / "survey/data/deep_review_manual.csv",
            dtype=str,
            keep_default_na=False,
        ).set_index("project_family_id")
        fastmamba = reviews.loc["PF-5345A35EEB976D35"]
        evidence = json.loads(fastmamba["evidence_locations"])

        self.assertEqual(
            fastmamba["rq5_power"],
            "1.65× higher decode energy efficiency than RTX 3090",
        )
        self.assertIn(
            "locator=page-1_section-Abstract_phrase-1.65",
            evidence["rq5_power"],
        )
        self.assertIn("catalog abstract says 6×", fastmamba["notes"])
        self.assertIn("PDF-primary", fastmamba["notes"])

    def test_committed_extraction_regenerates_byte_identically(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            out = Path(temporary_directory)
            subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "--families",
                    str(ROOT / "survey/build/project_families.csv"),
                    "--reviews",
                    str(ROOT / "survey/data/deep_review_manual.csv"),
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            for name in ("deep_review.csv", "deep_review.md"):
                self.assertEqual(
                    (out / name).read_bytes(),
                    (ROOT / "survey/build" / name).read_bytes(),
                    name,
                )


if __name__ == "__main__":
    unittest.main()
