from __future__ import annotations

import csv
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from survey.scripts.mlir_stage_matrix import (
    CANONICAL_STAGE_CATALOG_PATH,
    FIRST_FAILED_GATE_SEMANTICS,
    HARD_GATES,
    PROJECTS,
    SCORE_WEIGHTS,
    STAGE_STATUSES,
    _evidence_source_paths,
    build_decision_matrix,
    build_stage_matrix,
    choose_routes,
    hard_gates_pass,
    score_route,
    stage_status,
    validate_decision_matrix,
    validate_stage_matrix,
    write_decision_template,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_STAGES = [
    "PyTorch model capture",
    "Dynamic-to-static shape specialization",
    "Tensor-to-buffer conversion",
    "Quantized/fixed-point type legalization",
    "MatMul tiling and data reuse",
    "Attention/QKV fusion",
    "Causal masking",
    "Softmax approximation",
    "LayerNorm/RMSNorm lowering",
    "GELU/SiLU approximation",
    "RoPE lowering",
    "KV-cache state and addressing",
    "Buffer banking and memory-port assignment",
    "Resource sharing and scheduling",
    "Backpressure and deadlock handling",
    "Weight-loading interface",
    "AXI/stream/memory interface generation",
    "Synthesizable memory inference",
    "Clock/reset generation",
    "FPGA-family technology mapping",
]


def _scored_route(
    route_id: str,
    route_family: str,
    *,
    score: int,
    failed_gate: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "route_id": route_id,
        "route_family": route_family,
    }
    for gate in HARD_GATES:
        row[gate] = gate != failed_gate
        row[f"{gate}_evidence"] = f"tests/evidence/{route_id}/{gate}"
    for criterion in SCORE_WEIGHTS:
        row[criterion] = score
        row[f"{criterion}_evidence"] = f"tests/evidence/{route_id}/{criterion}"
    return row


class MlirStageMatrixTests(unittest.TestCase):
    def test_portable_catalog_drives_each_project_twenty_stage_order(self) -> None:
        matrix = build_stage_matrix()
        self.assertEqual(set(matrix["project"]), set(PROJECTS))
        self.assertEqual(len(matrix), len(PROJECTS) * len(EXPECTED_STAGES))
        for project in PROJECTS:
            with self.subTest(project=project):
                project_rows = matrix.loc[matrix["project"].eq(project)]
                self.assertEqual(project_rows["ordinal"].tolist(), list(range(1, 21)))
                self.assertEqual(project_rows["stage"].tolist(), EXPECTED_STAGES)
                self.assertEqual(
                    project_rows.loc[project_rows["ordinal"].eq(16), "stage"].item(),
                    "Weight-loading interface",
                )

    def test_catalog_is_tracked_portable_and_records_source_provenance(self) -> None:
        catalog_path = ROOT / CANONICAL_STAGE_CATALOG_PATH
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(catalog["source_provenance"]["source_filename"], "survey_protocol_llm2fpga.md")
        self.assertEqual(
            catalog["source_provenance"]["source_sha256"],
            "5112ba94144043a5d3cefa01b29d89dd3eb8643633a9a6fb26c9e20ca372fb2e",
        )
        self.assertEqual(catalog["source_provenance"]["source_line_range"], "1170-1203")
        self.assertEqual([stage["name"] for stage in catalog["stages"]], EXPECTED_STAGES)
        self.assertNotIn("/home/", catalog_path.read_text(encoding="utf-8"))

    def test_stage_statuses_use_only_the_contract_vocabulary(self) -> None:
        matrix = build_stage_matrix()
        observed = {
            row["status"]
            for row in matrix.to_dict(orient="records")
        }
        self.assertTrue(observed.issubset(STAGE_STATUSES))
        self.assertEqual(
            [stage_status("compiler-lab", stage) for stage in EXPECTED_STAGES],
            matrix.loc[matrix["project"].eq("compiler-lab"), "status"].tolist(),
        )
        with self.assertRaises(KeyError):
            stage_status("compiler-lab", "not a protocol stage")

    def test_external_audits_cover_allo_and_olympus_without_claiming_unreproduced_stages(self) -> None:
        matrix = build_stage_matrix()
        for project in ("Allo", "Olympus"):
            with self.subTest(project=project):
                rows = matrix.loc[matrix["project"].eq(project)]
                self.assertEqual(len(rows), 20)
                self.assertTrue(rows["status"].eq("missing").all())
                self.assertTrue(rows["evidence_location"].str.strip().ne("").all())

    def test_validation_requires_exactly_the_audited_project_set_and_full_catalogs(self) -> None:
        matrix = build_stage_matrix()
        additional_project = matrix.loc[matrix["project"].eq("compiler-lab")].copy()
        additional_project.loc[:, "project"] = "Additional audited project"
        with self.assertRaisesRegex(ValueError, "project set"):
            validate_stage_matrix(pd.concat([matrix, additional_project], ignore_index=True))

        incomplete = pd.concat([matrix, additional_project.iloc[:-1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "project set"):
            validate_stage_matrix(incomplete)

    def test_disputed_compiler_lab_stages_remain_missing_without_exercised_exact_evidence(self) -> None:
        self.assertEqual(
            stage_status("compiler-lab", "Dynamic-to-static shape specialization"),
            "missing",
        )
        self.assertEqual(
            stage_status("compiler-lab", "Tensor-to-buffer conversion"),
            "missing",
        )
        self.assertEqual(
            stage_status("compiler-lab", "Softmax approximation"),
            "missing",
        )
        self.assertEqual(
            stage_status("compiler-lab", "GELU/SiLU approximation"),
            "missing",
        )

    def test_every_non_missing_status_has_concrete_evidence(self) -> None:
        matrix = build_stage_matrix()
        for row in matrix.to_dict(orient="records"):
            if row["status"] != "missing":
                with self.subTest(stage=row["stage"]):
                    self.assertTrue(str(row["evidence_location"]).strip())

        invalid = matrix.copy()
        index = invalid.index[0]
        invalid.loc[index, "status"] = "manual_implementation"
        invalid.loc[index, "evidence_location"] = ""
        with self.assertRaisesRegex(ValueError, "evidence_location"):
            validate_stage_matrix(invalid)

        invalid = matrix.copy()
        invalid.loc[index, "status"] = "declared_dialect_only"
        with self.assertRaisesRegex(ValueError, "unsupported stage status"):
            validate_stage_matrix(invalid)

        invalid = matrix.copy()
        invalid.loc[index, "status"] = "manual_implementation"
        invalid.loc[index, "evidence_location"] = "missing/source/example.py#lines=1-1"
        with self.assertRaisesRegex(ValueError, "does not resolve to a local source"):
            validate_stage_matrix(invalid)

        for invalid_locator in (
            "survey/protocol.md#definitely-not-a-real-locator",
            "survey/protocol.md#lines=999999-999999",
            "survey/config/scope.yaml#key=fixtures.definitely-not-a-real-key",
            "survey/build/deep_review.csv#lines=1-1",
            "survey/compatibility/R1-mlir-circt/manifest.json#lines=1-1",
            "survey/config/scope.yaml#lines=1-1",
            "flake.lock#lines=1-1",
        ):
            with self.subTest(invalid_locator=invalid_locator):
                invalid = matrix.copy()
                invalid.loc[index, "status"] = "manual_implementation"
                invalid.loc[index, "evidence_location"] = invalid_locator
                with self.assertRaisesRegex(ValueError, "invalid evidence locator"):
                    validate_stage_matrix(invalid)

        valid = matrix.copy()
        valid.loc[index, "status"] = "manual_implementation"
        valid.loc[index, "evidence_location"] = (
            "survey/compatibility/R1-mlir-circt/manifest.json#command-1"
        )
        validate_stage_matrix(valid)

    def test_evidence_paths_are_relative_and_stay_within_the_repository(self) -> None:
        matrix = build_stage_matrix()
        index = matrix.index[0]
        traversal_to_passwd = os.path.relpath("/etc/passwd", ROOT)
        for invalid_location in (
            f"{ROOT / 'survey/protocol.md'}#lines=1-1",
            f"{traversal_to_passwd}#lines=1-1",
        ):
            with self.subTest(invalid_location=invalid_location):
                invalid = matrix.copy()
                invalid.loc[index, "status"] = "manual_implementation"
                invalid.loc[index, "evidence_location"] = invalid_location
                with self.assertRaisesRegex(ValueError, "relative.*repository"):
                    validate_stage_matrix(invalid)

        with TemporaryDirectory() as repository, TemporaryDirectory() as outside:
            repository_root = Path(repository)
            outside_source = Path(outside) / "outside.md"
            outside_source.write_text("outside evidence\n", encoding="utf-8")
            (repository_root / "linked-evidence.md").symlink_to(outside_source)
            with self.assertRaisesRegex(ValueError, "relative.*repository"):
                _evidence_source_paths(
                    "linked-evidence.md#lines=1-1", repository_root
                )

    def test_native_status_requires_pinned_source_test_or_example(self) -> None:
        matrix = build_stage_matrix()
        native_rows = matrix.index[matrix["status"].eq("native")]
        self.assertGreater(len(native_rows), 0)
        invalid = matrix.copy()
        invalid.loc[native_rows[0], "evidence_kind"] = "declared_dialect_only"
        with self.assertRaisesRegex(ValueError, "source test or example"):
            validate_stage_matrix(invalid)

    def test_native_status_rejects_documentation_only_source_claims(self) -> None:
        matrix = build_stage_matrix()
        native_index = matrix.index[matrix["status"].eq("native")][0]
        validate_stage_matrix(matrix)
        for evidence_kind in ("source_example", "source_test"):
            with self.subTest(evidence_kind=evidence_kind):
                invalid = matrix.copy()
                invalid.loc[native_index, "evidence_kind"] = evidence_kind
                invalid.loc[native_index, "evidence_location"] = (
                    "survey/compatibility/R1-mlir-circt/README.md#lines=1-16"
                )
                with self.assertRaisesRegex(
                    ValueError, "concrete pinned source test or example"
                ):
                    validate_stage_matrix(invalid)

    def test_stage_markdown_discloses_source_faithful_protocol_correction(self) -> None:
        with TemporaryDirectory() as directory:
            write_outputs(ROOT, Path(directory))
            markdown = (Path(directory) / "mlir_circt_stage_matrix.md").read_text(
                encoding="utf-8"
            )
        self.assertIn("survey/data/mlir_circt_stage_catalog.json", markdown)
        self.assertIn("repository-relative", markdown)
        self.assertIn("5112ba94144043a5d3cefa01b29d89dd3eb8643633a9a6fb26c9e20ca372fb2e", markdown)
        self.assertIn("60", markdown)
        self.assertIn(
            "fixes the audited project set to compiler-lab, Allo, Olympus", markdown
        )
        self.assertNotIn("Additional audited projects", markdown)
        self.assertIn("Weight-loading interface", markdown)
        self.assertIn("Allo", markdown)
        self.assertIn("Olympus", markdown)
        self.assertIn("survey/protocol.md", markdown)
        self.assertIn("not modified", markdown)
        self.assertNotIn("/home/", markdown)
        self.assertNotIn("Downloads", markdown)


class DecisionMatrixTests(unittest.TestCase):
    def test_score_route_uses_the_exact_weighted_zero_to_one_hundred_formula(self) -> None:
        self.assertEqual(
            SCORE_WEIGHTS,
            {
                "demonstrator_score_0_5": 25,
                "foss_score_0_5": 20,
                "end_to_end_score_0_5": 15,
                "reuse_score_0_5": 15,
                "verification_score_0_5": 10,
                "hardware_score_0_5": 10,
                "performance_score_0_5": 5,
            },
        )
        row = _scored_route("T1", "HLS", score=0)
        row.update(
            {
                "demonstrator_score_0_5": 5,
                "foss_score_0_5": 4,
                "end_to_end_score_0_5": 3,
                "reuse_score_0_5": 2,
                "verification_score_0_5": 1,
                "hardware_score_0_5": 0,
                "performance_score_0_5": 5,
            }
        )
        self.assertEqual(score_route(row), 63.0)

    def test_positive_score_requires_a_direct_evidence_path(self) -> None:
        row = _scored_route("T1", "HLS", score=0)
        row["demonstrator_score_0_5"] = 1
        row["demonstrator_score_0_5_evidence"] = ""
        with self.assertRaisesRegex(ValueError, "demonstrator_score_0_5_evidence"):
            score_route(row)

    def test_all_eight_hard_gates_are_required(self) -> None:
        self.assertEqual(
            HARD_GATES,
            (
                "source_access",
                "license",
                "reproducible_minimal_build",
                "model_path",
                "no_required_closed_ip",
                "complete_rtl",
                "test_budget",
                "deterministic_reference",
            ),
        )
        for gate in HARD_GATES:
            with self.subTest(gate=gate):
                self.assertFalse(
                    hard_gates_pass(
                        _scored_route("T1", "HLS", score=5, failed_gate=gate)
                    )
                )

    def test_hard_gate_failure_overrides_the_highest_weighted_score(self) -> None:
        routes = pd.DataFrame(
            [
                _scored_route(
                    "blocked-high-score",
                    "MLIR_CIRCT",
                    score=5,
                    failed_gate="complete_rtl",
                ),
                _scored_route("eligible-primary", "HLS", score=3),
                _scored_route("eligible-fallback", "DATAFLOW", score=2),
            ]
        )
        self.assertEqual(
            choose_routes(routes),
            ("eligible-primary", "eligible-fallback"),
        )

    def test_primary_and_fallback_must_have_distinct_route_families(self) -> None:
        routes = pd.DataFrame(
            [
                _scored_route("primary", "HLS", score=5),
                _scored_route("same-family", "HLS", score=4),
                _scored_route("other-family", "PARAMETERIZED_RTL", score=3),
            ]
        )
        self.assertEqual(choose_routes(routes), ("primary", "other-family"))

    def test_choose_routes_raises_when_no_candidate_passes_all_gates(self) -> None:
        routes = pd.DataFrame(
            [
                _scored_route(
                    "blocked", "HLS", score=5, failed_gate="source_access"
                )
            ]
        )
        with self.assertRaisesRegex(ValueError, "NO_PRIMARY_ROUTE_PASSED"):
            choose_routes(routes)

    def test_generated_matrix_uses_final_receipts_and_exactly_eight_routes(self) -> None:
        matrix = build_decision_matrix(ROOT)
        self.assertEqual(matrix["route_id"].tolist(), [f"R{index}" for index in range(1, 9)])
        self.assertEqual(matrix.loc[0, "actual_stage"], "RTL_GENERATION")
        self.assertEqual(matrix.loc[0, "failure_code"], "F_SOURCE_MISSING")
        self.assertEqual(matrix.loc[0, "reproducible_minimal_build"], "false")
        self.assertEqual(matrix.loc[0, "complete_rtl"], "false")
        self.assertEqual(matrix.loc[0, "first_failed_gate"], "reproducible_minimal_build")
        self.assertEqual(matrix.loc[0, "first_failed_gate_semantics"], FIRST_FAILED_GATE_SEMANTICS)
        self.assertEqual(matrix.loc[0, "hardware_score_0_5"], 0)
        self.assertLessEqual(matrix.loc[0, "foss_score_0_5"], 2)
        self.assertLessEqual(
            matrix.loc[matrix["route_id"].eq("R2"), "demonstrator_score_0_5"].item(),
            2,
        )
        self.assertEqual(
            matrix.loc[matrix["route_id"].eq("R4"), "demonstrator_score_0_5"].item(),
            0,
        )
        for route_id in ("R7", "R8"):
            row = matrix.loc[matrix["route_id"].eq(route_id)].iloc[0]
            self.assertEqual(row["actual_stage"], "SOURCE_CLOSURE")
            self.assertEqual(row["failure_code"], "F_SOURCE_MISSING")
            self.assertEqual(row["model_path"], "not_assessed")
        self.assertTrue(set(HARD_GATES).issubset(matrix.columns))
        self.assertTrue(set(SCORE_WEIGHTS).issubset(matrix.columns))
        for _, row in matrix.iterrows():
            for gate in HARD_GATES:
                evidence = str(row[f"{gate}_evidence"])
                self.assertTrue(evidence.strip())
                self.assertTrue((ROOT / evidence.split("#", 1)[0].split(":", 1)[0]).exists())
            for criterion in SCORE_WEIGHTS:
                if float(row[criterion]) > 0:
                    evidence = str(row[f"{criterion}_evidence"])
                    self.assertTrue(evidence.strip())
                    self.assertTrue((ROOT / evidence.split("#", 1)[0]).exists())

    def test_decision_validation_requires_each_frozen_route_exactly_once(self) -> None:
        matrix = build_decision_matrix(ROOT)
        missing_route = matrix.loc[~matrix["route_id"].eq("R8")].copy()
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_decision_matrix(missing_route, ROOT)

        duplicate_route = matrix.copy()
        duplicate_route.loc[duplicate_route["route_id"].eq("R8"), "route_id"] = "R7"
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_decision_matrix(duplicate_route, ROOT)

    def test_decision_validation_binds_route_rows_to_persisted_receipts(self) -> None:
        matrix = build_decision_matrix(ROOT)
        r2 = matrix["route_id"].eq("R2")
        for changes, error in (
            ({"route_family": "HLS"}, "receipt route_family"),
            (
                {
                    "receipt_manifest": "survey/compatibility/R1-mlir-circt/manifest.json"
                },
                "receipt_manifest",
            ),
            (
                {"receipt_readme": "survey/compatibility/R1-mlir-circt/README.md"},
                "receipt_readme",
            ),
            (
                {"actual_stage": "SIMULATION", "failure_code": "F_NONE"},
                "receipt actual_stage",
            ),
            ({"failure_code": "F_NONE"}, "receipt failure_code"),
            ({"selection_status": "ELIGIBLE"}, "receipt decision"),
        ):
            with self.subTest(changes=changes):
                invalid = matrix.copy()
                for column, value in changes.items():
                    invalid.loc[r2, column] = value
                with self.assertRaisesRegex(ValueError, error):
                    validate_decision_matrix(invalid, ROOT)

    def test_decision_validation_rejects_score_anchor_overclaims(self) -> None:
        matrix = build_decision_matrix(ROOT)
        for route_id, criterion, overclaim in (
            ("R1", "foss_score_0_5", 5),
            ("R2", "demonstrator_score_0_5", 5),
            ("R4", "demonstrator_score_0_5", 4),
        ):
            with self.subTest(route_id=route_id, criterion=criterion):
                invalid = matrix.copy()
                invalid.loc[invalid["route_id"].eq(route_id), criterion] = overclaim
                invalid.loc[
                    invalid["route_id"].eq(route_id), f"{criterion}_evidence"
                ] = "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43"
                with self.assertRaisesRegex(ValueError, "score anchor"):
                    validate_decision_matrix(invalid, ROOT)

    def test_decision_validation_enforces_protocol_order_first_failure_and_gate_evidence(self) -> None:
        matrix = build_decision_matrix(ROOT)
        invalid = matrix.copy()
        invalid.loc[invalid["route_id"].eq("R1"), "first_failed_gate"] = "complete_rtl"
        with self.assertRaisesRegex(ValueError, "first_failed_gate"):
            validate_decision_matrix(invalid, ROOT)

        invalid = matrix.copy()
        invalid.loc[invalid["route_id"].eq("R1"), "source_access_evidence"] = "missing/evidence"
        with self.assertRaisesRegex(ValueError, "gate evidence"):
            validate_decision_matrix(invalid, ROOT)

        invalid = matrix.copy()
        invalid.loc[invalid["route_id"].eq("R1"), "source_access_evidence"] = (
            "survey/protocol.md#definitely-not-a-real-locator"
        )
        with self.assertRaisesRegex(ValueError, "gate evidence"):
            validate_decision_matrix(invalid, ROOT)

        invalid = matrix.copy()
        invalid.loc[invalid["route_id"].eq("R1"), "source_access_evidence"] = (
            "survey/compatibility/R1-mlir-circt/manifest.json#command-1"
        )
        with self.assertRaisesRegex(ValueError, "gate evidence"):
            validate_decision_matrix(invalid, ROOT)

    def test_no_primary_report_keeps_primary_empty_and_labels_hypothesis_ineligible(self) -> None:
        with TemporaryDirectory() as directory:
            write_outputs(ROOT, Path(directory))
            report = (Path(directory) / "route_selection.md").read_text(
                encoding="utf-8"
            )
        self.assertIn("NO_PRIMARY_ROUTE_PASSED", report)
        self.assertIn("Primary route: ``", report)
        self.assertIn("Next evidence-gathering route: `R1`", report)
        self.assertIn("Fallback hypothesis: `R2`", report)
        self.assertIn("PARAMETERIZED_RTL", report)
        self.assertIn("ineligible", report.lower())

    def test_template_and_generated_csv_expose_all_required_columns(self) -> None:
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            template = directory_path / "decision_matrix.csv"
            write_decision_template(template)
            with template.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                fields = set(reader.fieldnames or [])
                rows = list(reader)
            self.assertTrue(set(HARD_GATES).issubset(fields))
            self.assertTrue(set(SCORE_WEIGHTS).issubset(fields))
            self.assertEqual(
                [row["route_id"] for row in rows],
                [f"R{index}" for index in range(1, 9)],
            )


if __name__ == "__main__":
    unittest.main()
