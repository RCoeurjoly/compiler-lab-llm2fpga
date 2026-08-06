from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from survey.scripts.build_report import (
    REPORT_CITATIONS,
    REPORT_INPUTS,
    _canonical_json_sha256,
    _render_pdf,
    _validate_generated_deliverables,
    _validate_textual_outputs,
    build_report,
    validate_deliverables,
)
from survey.scripts.make_figures import (
    ROUTE_TAXONOMY,
    render_corpus_flow,
    validate_mermaid,
    write_figures,
)


ROOT = Path(__file__).resolve().parents[1]
TEXTUAL_REPORT_ARTIFACTS = (
    "corpus_flow.mmd",
    "route_family_comparison.csv",
    "route_family_comparison.md",
    "timeline.mmd",
    "final_report.md",
    "final_report.tex",
    "final_report_pdflatex.txt",
    "final_report_build.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _refresh_report_metadata(out: Path, filenames: tuple[str, ...]) -> None:
    """Rehash deliberately modified temporary report evidence."""

    metadata_path = out / "final_report_build.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for filename in filenames:
        digest = _sha256(out / filename)
        if filename in metadata["generated_sha256"]:
            metadata["generated_sha256"][filename] = digest
        if filename in metadata["retained_sha256"]:
            metadata["retained_sha256"][filename] = digest
        if filename == "final_report_pdflatex.txt":
            metadata["transcript_sha256"] = digest
        if filename == "final_report.pdf":
            metadata["pdf_sha256"] = digest
    metadata_without_hash = {
        key: value for key, value in metadata.items() if key != "metadata_sha256"
    }
    metadata["metadata_sha256"] = _canonical_json_sha256(metadata_without_hash)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class SurveyFigureTests(unittest.TestCase):
    def test_corpus_flow_uses_final_not_automatic_screening_counts(self) -> None:
        flow = {
            "input_records": 461,
            "candidate_unique_works": 456,
            "duplicate_manifestations": 5,
            "final_levels": {"A": 30, "B": 57, "C": 75, "D": 68, "X": 231},
            "included_records": 230,
            "excluded_records": 231,
        }

        rendered = render_corpus_flow(flow)

        validate_mermaid(rendered)
        self.assertIn("461 source records", rendered)
        self.assertIn("456 unique works", rendered)
        self.assertIn("5 duplicate manifestations", rendered)
        self.assertIn("A: 30", rendered)
        self.assertIn("B: 57", rendered)
        self.assertIn("C: 75", rendered)
        self.assertIn("D: 68", rendered)
        self.assertIn("X: 231", rendered)
        self.assertNotIn("A: 46", rendered)

    def test_figures_preserve_route_taxonomy_and_canonical_timeline(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory)
            outputs = write_figures(ROOT, out)
            comparison = pd.read_csv(outputs["route_family_comparison_csv"])
            comparison_markdown = outputs["route_family_comparison_md"].read_text(
                encoding="utf-8"
            )
            timeline = outputs["timeline_mmd"].read_text(encoding="utf-8")

        self.assertEqual(comparison["route_family"].tolist(), list(ROUTE_TAXONOMY))
        self.assertEqual(
            comparison["reviewed_families"].tolist(), [2, 2, 5, 15, 6, 6]
        )
        self.assertEqual(int(comparison["reviewed_families"].sum()), 36)
        self.assertIn("survey/build/project_families.csv", comparison_markdown)
        self.assertIn("survey/build/deep_review.csv", comparison_markdown)
        validate_mermaid(timeline)
        self.assertIn("Automated triage", timeline)
        self.assertIn("Manual screening", timeline)
        self.assertIn("Deduplication and lineage", timeline)
        self.assertIn("Deep review and extraction", timeline)
        self.assertIn("Route compatibility", timeline)
        self.assertIn("Decision matrix and report", timeline)
        self.assertNotIn("2026-", timeline)

    def test_mermaid_validation_rejects_a_malformed_graph(self) -> None:
        with self.assertRaisesRegex(ValueError, "Mermaid"):
            validate_mermaid("flowchart TD\nA[unclosed --> B")

    def test_figure_script_is_directly_executable_from_repository_root(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "figure-output"
            result = subprocess.run(
                [
                    sys.executable,
                    "survey/scripts/make_figures.py",
                    "--root",
                    ".",
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("<OUTPUT_DIR>/corpus_flow.mmd", result.stdout)
        self.assertNotIn(str(output.parent), result.stdout)


class SurveyReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._output_directory = TemporaryDirectory()
        cls.out = Path(cls._output_directory.name) / "report-output"
        cls.primary_artifact_hashes = {
            filename: _sha256(ROOT / "survey/build" / filename)
            for filename in (*TEXTUAL_REPORT_ARTIFACTS, "final_report.pdf")
        }
        cls.pdf = build_report(ROOT, cls.out)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._output_directory.cleanup()

    def test_report_rendering_is_self_contained_and_records_pdf_provenance(self) -> None:
        markdown = (self.out / "final_report.md").read_text(encoding="utf-8")
        latex = (self.out / "final_report.tex").read_text(encoding="utf-8")
        transcript = (self.out / "final_report_pdflatex.txt").read_text(
            encoding="utf-8"
        )
        metadata = json.loads(
            (self.out / "final_report_build.json").read_text(encoding="utf-8")
        )

        self.assertEqual(self.pdf, self.out / "final_report.pdf")
        self.assertGreater(self.pdf.stat().st_size, 0)
        self.assertEqual(metadata["pdf_sha256"], _sha256(self.pdf))
        self.assertEqual(
            metadata["transcript_sha256"],
            _sha256(self.out / "final_report_pdflatex.txt"),
        )
        self.assertEqual(
            metadata["retained_sha256"]["final_report.pdf"], _sha256(self.pdf)
        )
        self.assertEqual(
            metadata["retained_sha256"]["final_report_pdflatex.txt"],
            metadata["transcript_sha256"],
        )
        self.assertEqual(metadata["pdflatex"]["command"], "pdflatex")
        self.assertTrue(metadata["pdflatex"]["version"])
        self.assertEqual(
            metadata["pdflatex"]["environment"], "declared-flake-texlive"
        )
        self.assertEqual(metadata["pdflatex_runs"], 2)
        self.assertIn("survey/build/final_flow_counts.json", metadata["input_sha256"])
        self.assertIn("survey/build/screening_audit.md", metadata["input_sha256"])
        for required_text in (
            "459 to 461",
            "461 source records",
            "456 unique works",
            "5 duplicate manifestations",
            "A=30, B=57, C=75, D=68, X=231",
            "230 included records",
            "226 project families",
            "36 reviewed project-family/control rows",
            "3 projects x 20 canonical transformations = 60 assessed cells",
            "NO_PRIMARY_ROUTE_PASSED",
            "Primary route: none",
            "R1 is the ineligible next evidence-gathering route",
            "R2 is an ineligible different-family hypothesis",
            "board remains unspecified",
            "flake.nix",
            "flake.lock",
            "declared pdflatex",
            "survey/protocol.md",
            "survey/build/deep_review.csv",
            "survey/build/artifact_inventory.csv",
            "survey/build/repository_audit.csv",
            "survey/compatibility/R1-mlir-circt/manifest.json",
            "survey/build/mlir_circt_stage_matrix.csv",
            "survey/build/decision_matrix_scored.csv",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, markdown)
        self.assertNotIn("/home/", markdown)
        self.assertNotIn("file://", markdown)
        self.assertNotIn("/home/", latex)
        self.assertIn(r"\texttt{nix develop", latex)
        self.assertIn(r"\pdftrailerid{<4C4C4D32465047415F53555256455931>}", latex)
        self.assertIn("flake.nix", latex)
        self.assertIn("flake.lock", latex)
        self.assertIn("declared pdflatex", latex)
        self.assertIn("$ pdflatex", transcript)
        self.assertNotIn("/home/", transcript)
        self.assertNotIn("/home/", json.dumps(metadata, sort_keys=True))

        for filename in TEXTUAL_REPORT_ARTIFACTS:
            content = (self.out / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertNotIn("file://", content)
                self.assertNotRegex(content, r"(?<![A-Za-z0-9.])/(?:home|tmp|nix/store)/")
                self.assertNotRegex(
                    content,
                    r"(?im)^(?:authorization|proxy-authorization|cookie|x-api-key)\s*:",
                )
                self.assertNotRegex(content, r"https?://[^/\s]+@")

    def test_report_inputs_close_every_substantive_source_citation(self) -> None:
        self.assertTrue(set(REPORT_CITATIONS).issubset(REPORT_INPUTS))

    def test_environment_manifest_hashes_bind_the_current_flake_inputs(self) -> None:
        manifest = json.loads(
            (ROOT / "survey/build/environment_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["flake_nix_sha256"], _sha256(ROOT / "flake.nix"))
        self.assertEqual(manifest["flake_lock_sha256"], _sha256(ROOT / "flake.lock"))

    def test_report_rendering_does_not_rewrite_tracked_build_artifacts(self) -> None:
        self.assertNotEqual(self.out, ROOT / "survey/build")
        for filename, expected_hash in self.primary_artifact_hashes.items():
            with self.subTest(filename=filename):
                self.assertEqual(_sha256(ROOT / "survey/build" / filename), expected_hash)

    def test_report_rendering_is_byte_deterministic_across_isolated_outputs(self) -> None:
        replay_out = self.out.parent / "report-output-replay"
        replay_pdf = build_report(ROOT, replay_out)

        for filename in (*TEXTUAL_REPORT_ARTIFACTS, "final_report.pdf"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    _sha256(self.out / filename),
                    _sha256(replay_out / filename),
                )
        self.assertEqual(_sha256(self.pdf), _sha256(replay_pdf))
        transcript = (self.out / "final_report_pdflatex.txt").read_text(encoding="utf-8")
        self.assertTrue(all(line == line.rstrip() for line in transcript.splitlines()))

    def test_report_renderer_refuses_pdflatex_outside_declared_flake(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory)
            tex_path = out / "final_report.tex"
            tex_path.write_text(
                (self.out / "final_report.tex").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with patch.dict(
                "survey.scripts.build_report.os.environ",
                {"SURVEY_DECLARED_TEXLIVE": "/nix/store/declared-texlive"},
                clear=False,
            ):
                with patch(
                    "survey.scripts.build_report.shutil.which",
                    return_value="/nix/store/other-texlive/bin/pdflatex",
                ):
                    with self.assertRaisesRegex(
                        ValueError, "declared Nix development environment"
                    ):
                        _render_pdf(ROOT, out, tex_path)

    def test_fresh_copied_root_replay_is_deterministic_and_portable(self) -> None:
        with TemporaryDirectory() as directory:
            replay_root = Path(directory) / "replay"
            shutil.copytree(
                ROOT,
                replay_root,
                ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "survey/scripts/build_report.py",
                    "--root",
                    ".",
                    "--out",
                    "survey/build",
                ],
                cwd=replay_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            replay_out = replay_root / "survey/build"
            self.assertEqual(
                validate_deliverables(replay_root),
                [f"D{number}" for number in range(1, 17)],
            )
            for filename in (*TEXTUAL_REPORT_ARTIFACTS, "final_report.pdf"):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        _sha256(self.out / filename), _sha256(replay_out / filename)
                    )
            transcript = (replay_out / "final_report_pdflatex.txt").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(str(replay_root), transcript)
            self.assertNotIn("/tmp/", transcript)

    def test_generated_validation_rejects_corpus_flow_drift(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report-output"
            build_report(ROOT, out)
            corpus_flow = out / "corpus_flow.mmd"
            corpus_flow.write_text(
                corpus_flow.read_text(encoding="utf-8")
                + 'included --> drift["unjustified extra edge"]\n',
                encoding="utf-8",
            )
            _refresh_report_metadata(out, ("corpus_flow.mmd",))

            with self.assertRaisesRegex(ValueError, "D13.*canonical"):
                _validate_generated_deliverables(ROOT, out)

    def test_generated_validation_rejects_timeline_dates(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report-output"
            build_report(ROOT, out)
            timeline = out / "timeline.mmd"
            timeline.write_text(
                timeline.read_text(encoding="utf-8")
                + 'decision --> dated["2025-01-01"]\n',
                encoding="utf-8",
            )
            _refresh_report_metadata(out, ("timeline.mmd",))

            with self.assertRaisesRegex(ValueError, "D15.*canonical"):
                _validate_generated_deliverables(ROOT, out)

    def test_generated_validation_rejects_route_comparison_markdown_drift(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report-output"
            build_report(ROOT, out)
            comparison = out / "route_family_comparison.md"
            comparison.write_text(
                comparison.read_text(encoding="utf-8")
                + "| UNJUSTIFIED_SEVENTH_ROUTE | 99 | 99 |\n",
                encoding="utf-8",
            )
            _refresh_report_metadata(out, ("route_family_comparison.md",))

            with self.assertRaisesRegex(ValueError, "D14.*canonical"):
                _validate_generated_deliverables(ROOT, out)

    def test_textual_output_validation_rejects_secret_assignments_and_pem(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report-output"
            build_report(ROOT, out)
            markdown_path = out / "final_report.md"
            original = markdown_path.read_text(encoding="utf-8")
            for payload in (
                "\napi_token=not-for-publication\n",
                "\n-----BEGIN PRIVATE KEY-----\nnot-for-publication\n",
            ):
                with self.subTest(payload=payload):
                    markdown_path.write_text(original + payload, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "credential|private-key"):
                        _validate_textual_outputs(out)

    def test_validation_rejects_a_forged_single_pass_transcript(self) -> None:
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report-output"
            build_report(ROOT, out)
            transcript_path = out / "final_report_pdflatex.txt"
            transcript_path.write_text(
                transcript_path.read_text(encoding="utf-8").replace(
                    "# pdflatex pass 2", "# forged pass", 1
                ),
                encoding="utf-8",
            )
            metadata_path = out / "final_report_build.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("transcript_sha256", metadata)
            _refresh_report_metadata(out, ("final_report_pdflatex.txt",))

            with self.assertRaisesRegex(ValueError, "two successful pdflatex passes"):
                _validate_generated_deliverables(ROOT, out)

    def test_validate_deliverables_confirms_every_required_delivery(self) -> None:
        self.assertEqual(
            validate_deliverables(ROOT), [f"D{number}" for number in range(1, 17)]
        )

    def test_build_report_refuses_a_missing_evidence_package_before_rendering(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "survey/build"
            with self.assertRaisesRegex(ValueError, "D1"):
                build_report(root, out)
            self.assertFalse((out / "final_report.md").exists())

    def test_report_script_is_directly_executable_from_repository_root(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report-output"
            result = subprocess.run(
                [
                    sys.executable,
                    "survey/scripts/build_report.py",
                    "--root",
                    ".",
                    "--out",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("<OUTPUT_DIR>/final_report.pdf", result.stdout)
        self.assertNotIn(str(output.parent), result.stdout)
