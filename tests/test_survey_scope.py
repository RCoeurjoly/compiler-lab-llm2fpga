from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = ROOT / "survey/config/scope.yaml"
COMMON_PATH = ROOT / "survey/scripts/common.py"

LEVELS = {"A", "B", "C", "D", "X"}
EXCLUSION_CODES = {
    "X_NOT_FPGA",
    "X_LLM_FOR_EDA",
    "X_TRAINING_ONLY",
    "X_NON_LM_MODEL",
    "X_VIT_NO_TRANSFER",
    "X_ASIC_GPU_ONLY",
    "X_PERFORMANCE_MODEL_ONLY",
    "X_SECONDARY",
    "X_NO_EVIDENCE",
    "X_DUPLICATE",
    "X_RETRACTED",
}
DECISION_WEIGHTS = {
    "demonstrator_score_0_5": 25,
    "foss_score_0_5": 20,
    "end_to_end_score_0_5": 15,
    "reuse_score_0_5": 15,
    "verification_score_0_5": 10,
    "hardware_score_0_5": 10,
    "performance_score_0_5": 5,
}


def _require_file(test: unittest.TestCase, path: Path) -> None:
    test.assertTrue(path.is_file(), f"required survey contract is missing: {path}")


def _load_common(test: unittest.TestCase) -> ModuleType:
    _require_file(test, COMMON_PATH)
    spec = importlib.util.spec_from_file_location("survey_common", COMMON_PATH)
    test.assertIsNotNone(spec)
    test.assertIsNotNone(spec.loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True
    ).strip()


class SurveyScopeTests(unittest.TestCase):
    def test_scope_records_snapshot_amendment(self) -> None:
        _require_file(self, SCOPE_PATH)
        scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(scope["snapshot"]["expected_records"], 461)
        self.assertEqual(scope["snapshot"]["protocol_stated_records"], 459)
        self.assertEqual(
            scope["snapshot"]["papers_commit"],
            "95fd9b9a509f275dd3cfdb3360b33dbcca7429f0",
        )
        self.assertEqual(set(scope["levels"]), LEVELS)

    def test_scope_preserves_controlled_exclusions_and_weights(self) -> None:
        _require_file(self, SCOPE_PATH)
        scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(scope["controlled_exclusions"]), EXCLUSION_CODES)
        self.assertEqual(scope["decision_matrix"]["weights"], DECISION_WEIGHTS)
        self.assertEqual(sum(scope["decision_matrix"]["weights"].values()), 100)

    def test_load_scope_accepts_the_frozen_contract(self) -> None:
        common = _load_common(self)
        scope = common.load_scope(SCOPE_PATH)
        self.assertEqual(scope["snapshot"]["expected_records"], 461)

    def test_load_scope_rejects_missing_level(self) -> None:
        common = _load_common(self)
        scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
        del scope["levels"]["D"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.yaml"
            path.write_text(yaml.safe_dump(scope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "levels"):
                common.load_scope(path)

    def test_load_scope_rejects_missing_controlled_exclusion(self) -> None:
        common = _load_common(self)
        scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
        del scope["controlled_exclusions"]["X_DUPLICATE"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.yaml"
            path.write_text(yaml.safe_dump(scope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "controlled exclusions"):
                common.load_scope(path)

    def test_load_scope_rejects_weights_not_summing_to_100(self) -> None:
        common = _load_common(self)
        scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
        scope["decision_matrix"]["weights"]["performance_score_0_5"] = 4
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.yaml"
            path.write_text(yaml.safe_dump(scope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sum to 100"):
                common.load_scope(path)

    def test_manual_decision_and_route_vocabularies_are_frozen(self) -> None:
        manual_path = ROOT / "survey/data/manual_overrides.csv"
        routes_path = ROOT / "survey/data/route_vocabulary.csv"
        _require_file(self, manual_path)
        _require_file(self, routes_path)
        manual_header = manual_path.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            manual_header.split(","),
            [
                "record_id",
                "work_id",
                "project_family_id",
                "level_final",
                "include_final",
                "exclusion_code",
                "route_family",
                "reviewer",
                "evidence_location",
                "decision_basis",
            ],
        )
        route_rows = routes_path.read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual(
            {row.split(",", 1)[0] for row in route_rows},
            {
                "MLIR_CIRCT",
                "PARAMETERIZED_RTL",
                "HLS",
                "DATAFLOW",
                "OVERLAY",
                "CPU_FPGA_FALLBACK",
            },
        )


class SurveyProvenanceTests(unittest.TestCase):
    def test_remote_sanitization_removes_all_http_credential_channels(self) -> None:
        common = _load_common(self)
        remote = (
            "https://user:password@example.com/org/repository.git"
            "?access_token=secret#credential-fragment"
        )
        self.assertEqual(
            common._sanitize_remote(remote),
            "https://example.com/org/repository.git",
        )

    def test_write_provenance_rejects_modified_papers_catalogue(self) -> None:
        common = _load_common(self)
        catalogue = ROOT / "LLM-inference-on-FPGA-papers/data/catalog.json"
        original = catalogue.read_bytes()
        try:
            catalogue.write_bytes(original + b"\n")
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "provenance.json"
                with self.assertRaisesRegex(ValueError, "dirty frozen inputs"):
                    common.write_provenance(ROOT, output)
        finally:
            catalogue.write_bytes(original)

    def test_environment_manifest_pins_nix_definition_and_packages(self) -> None:
        common = _load_common(self)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "environment_manifest.json"
            manifest = common.write_environment_manifest(ROOT, output)
            raw = output.read_bytes()

        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(
            set(manifest["python_packages"]),
            {
                "pandas",
                "pyarrow",
                "pyyaml",
                "rapidfuzz",
                "unidecode",
                "requests",
                "requests-cache",
                "tabulate",
            },
        )
        self.assertIn("flake_nix_sha256", manifest)
        self.assertEqual(
            manifest["flake_nix_sha256"],
            hashlib.sha256((ROOT / "flake.nix").read_bytes()).hexdigest(),
        )
        self.assertEqual(
            manifest["flake_lock_sha256"],
            hashlib.sha256((ROOT / "flake.lock").read_bytes()).hexdigest(),
        )

    def test_write_provenance_pins_repositories_inputs_and_tools(self) -> None:
        common = _load_common(self)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "provenance.json"
            provenance = common.write_provenance(ROOT, output)
            raw = output.read_bytes()

        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(provenance["expected_records"], 461)
        self.assertEqual(provenance["protocol_record_count"], 459)
        self.assertEqual(
            provenance["papers_commit"],
            "95fd9b9a509f275dd3cfdb3360b33dbcca7429f0",
        )
        self.assertEqual(
            provenance["compiler_lab_commit"], _git(ROOT, "rev-parse", "HEAD")
        )
        papers = ROOT / "LLM-inference-on-FPGA-papers"
        self.assertEqual(provenance["papers_commit"], _git(papers, "rev-parse", "HEAD"))
        self.assertIn("compiler_lab_remote", provenance)
        self.assertIn("papers_remote", provenance)
        self.assertIn("llm2fpga_commit", provenance)
        self.assertIn("llm2fpga_remote", provenance)
        self.assertIn("python", provenance["tool_versions"])
        self.assertIn("git", provenance["tool_versions"])
        datetime.fromisoformat(provenance["generated_at_utc"])

        catalogue_key = "LLM-inference-on-FPGA-papers/data/catalog.json"
        catalogue = ROOT / catalogue_key
        expected_hash = hashlib.sha256(catalogue.read_bytes()).hexdigest()
        self.assertEqual(provenance["input_sha256"][catalogue_key], expected_hash)
        self.assertEqual(provenance["catalog_sha256"], expected_hash)
        self.assertIn(
            "LLM-inference-on-FPGA-papers/data/survey.csv",
            provenance["input_sha256"],
        )

    def test_repeated_provenance_differs_only_by_timestamp(self) -> None:
        common = _load_common(self)
        with tempfile.TemporaryDirectory() as directory:
            first = common.write_provenance(ROOT, Path(directory) / "first.json")
            second = common.write_provenance(ROOT, Path(directory) / "second.json")
        first.pop("generated_at_utc")
        second.pop("generated_at_utc")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
