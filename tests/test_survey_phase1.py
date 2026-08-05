from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import csv
from pathlib import Path

import pyarrow.parquet as pq
import yaml


ROOT = Path(__file__).resolve().parents[1]
PHASE1_PATH = ROOT / "survey/scripts/phase1_map.py"
CATALOGUE_PATH = ROOT / "LLM-inference-on-FPGA-papers/data/catalog.json"
SCOPE_PATH = ROOT / "survey/config/scope.yaml"


def _load_phase1():
    spec = importlib.util.spec_from_file_location("survey_phase1", PHASE1_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {PHASE1_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "title": "A Transformer Accelerator on FPGA",
        "abstract": "FPGA transformer inference " * 20,
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "categories": ["cs.AR"],
        "published_at": "2025-01-02T00:00:00Z",
        "updated_at": "2025-02-03T00:00:00Z",
        "abs_url": "https://arxiv.org/abs/2501.00001v1",
        "pdf_url": "https://arxiv.org/pdf/2501.00001v1",
        "arxiv_id": "2501.00001",
        "version": 1,
        "query_ids": ["query-a"],
        "cache": {"sha256": "a" * 64, "filename": "paper.pdf"},
    }
    record.update(overrides)
    return record


class CatalogueNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.phase1 = _load_phase1()

    def test_extracts_mapping_catalogue_and_preserves_key(self) -> None:
        records = self.phase1.extract_records(
            {"papers": {"2401.00001v2": {"title": "A"}}}
        )
        self.assertEqual(records, [("2401.00001v2", {"title": "A"})])

    def test_extracts_list_catalogue_with_stable_identity_key(self) -> None:
        records = self.phase1.extract_records(
            {"papers": [{"arxiv_id": "2401.00001", "version": 2, "title": "A"}]}
        )
        self.assertEqual(
            records,
            [
                (
                    "2401.00001v2",
                    {"arxiv_id": "2401.00001", "version": 2, "title": "A"},
                )
            ],
        )

    def test_list_catalogue_disambiguates_work_id_across_arxiv_versions(self) -> None:
        source = {
            "papers": [
                {
                    "record_id": "shared-work-id",
                    "arxiv_id": "2401.00001",
                    "version": 1,
                    "title": "A",
                },
                {
                    "record_id": "shared-work-id",
                    "arxiv_id": "2401.00001",
                    "version": 2,
                    "title": "A revised",
                },
            ]
        }
        extracted = self.phase1.extract_records(source)
        self.assertEqual([key for key, _ in extracted], ["2401.00001v1", "2401.00001v2"])
        normalized = [
            self.phase1.canonicalize_record(key, record) for key, record in extracted
        ]
        self.assertEqual(
            [row["source_record_id"] for row in normalized],
            ["shared-work-id", "shared-work-id"],
        )
        self.assertEqual(len({row["record_id"] for row in normalized}), 2)

    def test_normalizes_doi_urls_and_trailing_citation_punctuation(self) -> None:
        self.assertEqual(
            self.phase1.normalize_doi(" HTTPS://DX.DOI.ORG/10.1109/ABC.123. "),
            "10.1109/abc.123",
        )

    def test_normalizes_arxiv_versions_to_base_identifier(self) -> None:
        self.assertEqual(
            self.phase1.normalize_arxiv("https://arxiv.org/pdf/2401.12345v12.pdf"),
            "2401.12345",
        )

    def test_normalizes_unicode_punctuation_and_linebreak_hyphenation(self) -> None:
        self.assertEqual(
            self.phase1.normalize_title("ＦＰＧＡ-based Trans-\nformer: An ‘Example’!"),
            "fpga based transformer an example",
        )

    def test_canonical_record_retains_versioned_lineage_and_raw_json(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.00001v3",
            _record(
                version=3,
                doi="https://doi.org/10.1/ABC",
                custom_source_field={"z": 1, "a": [2]},
            ),
        )
        self.assertEqual(row["catalog_key"], "2501.00001v3")
        self.assertEqual(row["arxiv_version_id"], "2501.00001v3")
        self.assertEqual(row["arxiv_id"], "2501.00001")
        self.assertEqual(row["doi"], "10.1/abc")
        self.assertEqual(json.loads(row["authors_json"]), ["Ada Lovelace", "Grace Hopper"])
        self.assertEqual(json.loads(row["cache_json"])["sha256"], "a" * 64)
        self.assertEqual(json.loads(row["raw_record_json"])["custom_source_field"], {"a": [2], "z": 1})
        self.assertRegex(row["record_id"], r"^REC-[0-9A-F]{16}$")

    def test_structured_authors_remain_json_names_not_python_dict_strings(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.00002v1",
            _record(authors=[{"name": "Ada Lovelace"}, {"full_name": "Grace Hopper"}]),
        )
        self.assertEqual(json.loads(row["authors_json"]), ["Ada Lovelace", "Grace Hopper"])
        self.assertNotIn("{'", row["authors_json"])

    def test_generic_mapping_values_use_canonical_json_never_python_repr(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.00004v1",
            _record(
                title={"text": "Structured FPGA title", "language": "en"},
                keywords={"topic": "FPGA", "kind": ["compiler", "HLS"]},
                primary_category={"id": "cs.AR", "label": "Architecture"},
            ),
        )
        self.assertEqual(
            json.loads(row["title"]),
            {"language": "en", "text": "Structured FPGA title"},
        )
        self.assertEqual(
            json.loads(row["keywords"]),
            {"kind": ["compiler", "HLS"], "topic": "FPGA"},
        )
        self.assertEqual(
            json.loads(row["primary_category"]),
            {"id": "cs.AR", "label": "Architecture"},
        )
        for field in ("title", "keywords", "primary_category"):
            self.assertNotIn("{'", row[field])

    def test_repository_url_in_source_text_is_preserved_for_artifact_scoring(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.00003v1",
            _record(abstract="Source is available at https://github.com/example/project.")
        )
        self.assertEqual(row["repo_url"], "https://github.com/example/project")

    def test_pinned_catalogue_contains_all_461_source_records(self) -> None:
        catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
        records = self.phase1.extract_records(catalogue)
        self.assertEqual(len(records), 461)
        self.assertEqual(len({key for key, _ in records}), 461)


class DeduplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.phase1 = _load_phase1()

    def _canonical(self, key: str, **values: object) -> dict[str, object]:
        return self.phase1.canonicalize_record(key, _record(**values))

    def test_ordered_exact_rules_merge_and_retain_every_record(self) -> None:
        records = [
            self._canonical(
                "2501.00001v1",
                doi="10.1000/SAME",
                arxiv_id="2501.00001",
                title="First title",
            ),
            self._canonical(
                "2502.00002v1",
                doi="https://doi.org/10.1000/same",
                arxiv_id="2502.00002",
                title="Journal title",
            ),
            self._canonical(
                "2501.00001v2",
                doi=None,
                arxiv_id="2501.00001",
                version=2,
                title="Revised title",
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 1)
        self.assertEqual(len(lineage), 3)
        self.assertEqual({row["work_id"] for row in lineage}, {works[0]["work_id"]})
        self.assertEqual(
            {row["dedup_rule"] for row in lineage},
            {"preferred_manifestation", "exact_doi", "exact_arxiv"},
        )
        for row in lineage:
            self.assertTrue(row["dedup_confidence"])
            self.assertIsInstance(json.loads(row["dedup_evidence_json"]), list)
            self.assertTrue(row["preferred_manifestation_rationale"])

    def test_authoritative_identifier_precedes_exact_title(self) -> None:
        records = [
            self._canonical(
                "2501.10001v1",
                arxiv_id="2501.10001",
                title="Different title one",
                openalex_id="W123",
            ),
            self._canonical(
                "2501.10002v1",
                arxiv_id="2501.10002",
                title="Different title two",
                openalex_id="https://openalex.org/W123",
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 1)
        self.assertIn("exact_authoritative_id", {row["dedup_rule"] for row in lineage})

    def test_exact_normalized_titles_merge(self) -> None:
        records = [
            self._canonical("2501.20001v1", arxiv_id="2501.20001", title="A Title: Here"),
            self._canonical("2501.20002v1", arxiv_id="2501.20002", title="A title — here!"),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 1)
        self.assertIn("exact_title", {row["dedup_rule"] for row in lineage})

    def test_fuzzy_95_merge_records_similarity_author_and_year_evidence(self) -> None:
        records = [
            self._canonical(
                "2501.30001v1",
                arxiv_id="2501.30001",
                title="Composable Accelerator Generation for Transformer Inference",
                authors=["Ada Lovelace", "Grace Hopper"],
                published_at="2024-01-01T00:00:00Z",
            ),
            self._canonical(
                "2501.30002v1",
                arxiv_id="2501.30002",
                title="Composable Accelerator Generation for Transformers Inference",
                authors=["Ada Lovelace", "Alan Turing"],
                published_at="2025-01-01T00:00:00Z",
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 1)
        fuzzy = next(row for row in lineage if row["dedup_rule"] == "fuzzy_title_95")
        self.assertGreaterEqual(fuzzy["candidate_similarity"], 95.0)
        evidence = json.loads(fuzzy["dedup_evidence_json"])
        self.assertTrue(any(item["same_first_author"] for item in evidence))
        self.assertTrue(any(item["year_difference"] == 1 for item in evidence))

    def test_fuzzy_92_merge_requires_two_authors_and_distinctive_subtitle(self) -> None:
        records = [
            self._canonical(
                "2501.31001v1",
                arxiv_id="2501.31001",
                title="Forge: A Reusable Architecture for Decoder Inference",
                authors=["Ada Lovelace", "Grace Hopper"],
            ),
            self._canonical(
                "2501.31002v1",
                arxiv_id="2501.31002",
                title="Forges: A Reusable Architecture for Decoder Inference",
                authors=["Grace Hopper", "Ada Lovelace"],
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 1)
        fuzzy = next(row for row in lineage if row["dedup_rule"] == "fuzzy_title_92")
        evidence = json.loads(fuzzy["dedup_evidence_json"])
        self.assertTrue(any(len(item["matching_authors"]) == 2 for item in evidence))
        self.assertTrue(any(item["distinctive_subtitle_match"] for item in evidence))

    def test_shared_repository_url_alone_never_merges_records(self) -> None:
        records = [
            self._canonical(
                "2501.40001v1",
                arxiv_id="2501.40001",
                title="One Unrelated Hardware Design",
                repo_url="https://github.com/example/shared",
            ),
            self._canonical(
                "2501.40002v1",
                arxiv_id="2501.40002",
                title="Another Completely Separate Compiler",
                repo_url="https://github.com/example/shared",
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 2)
        self.assertEqual({row["dedup_rule"] for row in lineage}, {"unique"})

    def test_contradictory_pinned_doi_collision_fails_closed(self) -> None:
        catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))["papers"]
        keys = ["2508.15468v2", "2601.17215v1"]
        records = [self.phase1.canonicalize_record(key, catalogue[key]) for key in keys]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 2)
        self.assertEqual(len({row["work_id"] for row in lineage}), 2)
        for row in lineage:
            evidence = json.loads(row["dedup_evidence_json"])
            self.assertTrue(any(item["rule"] == "contradictory_identity" for item in evidence))

    def test_exact_arxiv_fails_closed_on_independent_identity_conflict(self) -> None:
        records = [
            self._canonical(
                "2501.61001v1",
                arxiv_id="2501.61001",
                doi="10.1000/first",
                title="Alpha FPGA Accelerator",
                authors=["Ada Lovelace"],
            ),
            self._canonical(
                "2501.61001v2",
                arxiv_id="2501.61001",
                version=2,
                doi="10.1000/second",
                title="Unrelated Database Compiler",
                authors=["Grace Hopper"],
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 2)
        for row in lineage:
            conflict = next(
                item
                for item in json.loads(row["dedup_evidence_json"])
                if item["rule"] == "contradictory_identity"
            )
            self.assertEqual(conflict["attempted_rule"], "exact_arxiv")
            self.assertEqual(
                set(conflict["conflicting_fields"]),
                {"doi", "first_author", "title"},
            )

    def test_transitive_union_checks_all_cross_component_identities(self) -> None:
        records = [
            self._canonical(
                "2501.62001v1",
                arxiv_id="2501.62001",
                doi="10.1000/bridge",
                title="Alpha Accelerator",
                authors=["Ada Lovelace"],
            ),
            self._canonical(
                "2501.62002v1",
                arxiv_id="2501.62002",
                doi="10.1000/bridge",
                title="",
                abstract="",
                authors=[],
            ),
            self._canonical(
                "2501.62002v2",
                arxiv_id="2501.62002",
                version=2,
                doi="10.1000/other",
                title="Unrelated Database Compiler",
                authors=["Grace Hopper"],
            ),
        ]
        works, lineage = self.phase1.deduplicate(records)
        self.assertEqual(len(works), 2)
        self.assertEqual(lineage[0]["work_id"], lineage[1]["work_id"])
        self.assertNotEqual(lineage[1]["work_id"], lineage[2]["work_id"])
        bridge_evidence = json.loads(lineage[1]["dedup_evidence_json"])
        conflict = next(item for item in bridge_evidence if item["rule"] == "contradictory_identity")
        self.assertEqual(conflict["attempted_rule"], "exact_arxiv")
        self.assertTrue(conflict["component_level"])
        self.assertEqual(len(conflict["conflicting_record_pairs"]), 1)


class TriageAndOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.phase1 = _load_phase1()
        cls.scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))

    def test_classification_preserves_individual_matches_and_exact_priority_score(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.50001v1",
            _record(
                title="End-to-end LLM token generation on FPGA with MLIR MatMul",
                abstract="A public implementation lowers a transformer using CIRCT. " * 8,
                repo_url="https://github.com/example/code",
                doi="10.1000/example",
            ),
        )
        classified = self.phase1.classify_record(row, self.scope)
        self.assertEqual(classified["auto_level"], "A")
        self.assertEqual(classified["auto_route_family"], "MLIR_CIRCT")
        self.assertEqual(classified["screen_priority_score"], 21)
        self.assertIn(r"\bfpga(s)?\b", json.loads(classified["matched_fpga_terms_json"]))
        self.assertIn(r"\bmlir\b", json.loads(classified["matched_compiler_terms_json"]))
        self.assertIn("token generation", json.loads(classified["matched_end_to_end_terms_json"]))
        self.assertIn(r"\bmatmul\b", json.loads(classified["matched_component_terms_json"]))
        score_evidence = json.loads(classified["score_evidence_json"])
        self.assertEqual(sum(item["contribution"] for item in score_evidence), 21)
        fpga = next(item for item in score_evidence if item["category"] == "fpga_term")
        self.assertEqual(
            fpga,
            {
                "category": "fpga_term",
                "matched_terms": [r"\bfpga(s)?\b"],
                "weight": 4,
                "contribution": 4,
            },
        )
        compiler = next(
            item for item in score_evidence if item["category"] == "compiler_or_generator_term"
        )
        self.assertEqual(compiler["weight"], 3)
        self.assertEqual(compiler["contribution"], 3)
        self.assertEqual(
            compiler["matched_terms"],
            [r"\bmlir\b", r"\bcirct\b"],
        )

    def test_eda_agent_receives_named_llm_for_eda_penalty(self) -> None:
        row = self.phase1.canonicalize_record(
            "2501.50002v1",
            _record(title="EDA Agent on FPGA", abstract="An EDA agent for routing hardware." * 10),
        )
        classified = self.phase1.classify_record(row, self.scope)
        self.assertEqual(classified["screen_priority_score"], 0)
        evidence = json.loads(classified["score_evidence_json"])
        penalty = next(item for item in evidence if item["category"] == "llm_for_eda_pattern")
        self.assertEqual(
            penalty,
            {
                "category": "llm_for_eda_pattern",
                "matched_terms": ["eda agent"],
                "weight": -5,
                "contribution": -5,
            },
        )
        self.assertEqual(sum(item["contribution"] for item in evidence), 0)

    def test_uncertain_queue_follows_protocol_lane_order_then_score(self) -> None:
        rows = [
            {"auto_level": "X", "screen_priority_score": 10, "record_index": 0, "manual_review_reasons_json": "[]"},
            {"auto_level": "B", "screen_priority_score": 8, "record_index": 1, "manual_review_reasons_json": "[]"},
            {"auto_level": "C", "screen_priority_score": 3, "record_index": 2, "manual_review_reasons_json": "[]"},
            {"auto_level": "A", "screen_priority_score": 2, "record_index": 3, "manual_review_reasons_json": "[]"},
            {"auto_level": "D", "screen_priority_score": 9, "record_index": 4, "manual_review_reasons_json": "[]"},
        ]
        ordered = self.phase1.prioritize_uncertain(rows)
        self.assertEqual([row["auto_level"] for row in ordered], ["A", "C", "B", "D", "X"])

    def test_pipeline_rejects_count_mismatch_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "out"
            with self.assertRaisesRegex(ValueError, "expected 460 records; found 461"):
                self.phase1.run_phase1(CATALOGUE_PATH, SCOPE_PATH, out, 460)
            self.assertFalse(out.exists())

    def test_pipeline_writes_explicit_parquet_schema_and_refuses_changed_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            catalogue_copy = directory_path / "catalog.json"
            catalogue_copy.write_bytes(CATALOGUE_PATH.read_bytes())
            out = directory_path / "out"
            self.phase1.run_phase1(catalogue_copy, SCOPE_PATH, out, 461)

            schema = pq.read_schema(out / "phase1_mapping.parquet")
            self.assertEqual(schema.field("record_id").type, self.phase1.PARQUET_SCHEMA.field("record_id").type)
            self.assertEqual(schema, self.phase1.PARQUET_SCHEMA)
            self.assertEqual(pq.read_table(out / "phase1_mapping.parquet").num_rows, 461)
            with (out / "records_normalized.csv").open(encoding="utf-8", newline="") as source:
                first_normalized = next(csv.DictReader(source))
            self.assertNotIn("_catalog_query_id", json.loads(first_normalized["raw_record_json"]))
            self.assertEqual(first_normalized["catalog_query_id"], "llm-inference-fpga-v1")

            changed = json.loads(catalogue_copy.read_text(encoding="utf-8"))
            first_key = next(iter(changed["papers"]))
            changed["papers"][first_key]["title"] += " changed"
            catalogue_copy.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                self.phase1.run_phase1(catalogue_copy, SCOPE_PATH, out, 461)

    def test_nix_shell_exposes_survey_phase1_command(self) -> None:
        result = subprocess.run(
            ["nix", "develop", "-c", "survey-phase1", "--help"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("--expected-records", result.stdout)

    def test_nix_entrypoint_records_checkout_independent_command_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "phase1"
            result = subprocess.run(
                [
                    "nix",
                    "develop",
                    "-c",
                    "survey-phase1",
                    "--catalog",
                    "LLM-inference-on-FPGA-papers/data/catalog.json",
                    "--config",
                    "survey/config/scope.yaml",
                    "--out",
                    str(out),
                    "--expected-records",
                    "461",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            command = json.loads((out / "phase1_run.json").read_text())["command"]
        self.assertEqual(
            command,
            [
                "survey-phase1",
                "--catalog",
                "LLM-inference-on-FPGA-papers/data/catalog.json",
                "--config",
                "survey/config/scope.yaml",
                "--out",
                "<OUT_DIR>",
                "--expected-records",
                "461",
            ],
        )

    def test_clean_runs_are_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            self.phase1.run_phase1(CATALOGUE_PATH, SCOPE_PATH, first, 461)
            self.phase1.run_phase1(CATALOGUE_PATH, SCOPE_PATH, second, 461)
            names = sorted(path.name for path in first.iterdir())
            self.assertEqual(names, sorted(path.name for path in second.iterdir()))
            self.assertEqual(
                {name: hashlib.sha256((first / name).read_bytes()).hexdigest() for name in names},
                {name: hashlib.sha256((second / name).read_bytes()).hexdigest() for name in names},
            )


if __name__ == "__main__":
    unittest.main()
