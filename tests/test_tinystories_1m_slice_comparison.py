"""Tests for the fail-closed TinyStories-1M slice comparison harness."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/comparison/compare_tinystories_1m_slice.py"
CONTRACT_PATH = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
SLICE_MANIFEST_PATH = ROOT / "artifacts/comparison/tinystories-1m-slice-manifest.json"


def load_module():
    spec = importlib.util.spec_from_file_location("compare_tinystories_1m_slice", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


comparison = load_module()


def fixture_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def fixture_slice_manifest() -> dict[str, object]:
    return {
        "schema": "tinystories-1m-compiler-slice-manifest-v1",
        "status": "ready",
        "model": "TinyStories-1M",
        "contract": {
            "path": "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            "sha256": comparison.sha256_file(CONTRACT_PATH),
        },
        "slice": {
            "kind": "one_transformer_block_token_step",
            "dependency_closure": ["block"],
        },
    }


def fixtures() -> tuple[dict[str, object], dict[str, object]]:
    report_sha256 = comparison.sha256_file(CONTRACT_PATH)
    report_path = str(CONTRACT_PATH)
    reference = {
        "contract": fixture_contract(),
        "contract_sha256": comparison.sha256_file(CONTRACT_PATH),
        "checkpoint_tensors": {"block.out": [1, 2]},
        "output_tokens": fixture_contract()["reference"]["tokens"],
        "resources": {"lut": 100, "ff": 20, "bram": 2, "dsp": 3, "memory_bits": 512, "path": report_path, "sha256": report_sha256, "measurement_id": "reference-yosys"},
        "timing": {"max_frequency_mhz": 100.0, "critical_paths": [{"delay_ns": 10.0}], "cycles_per_token": 4, "interface_overhead_cycles": 1, "path": report_path, "sha256": report_sha256, "measurement_id": "reference-timing"},
        "provenance": {"source": "reference-fixture"},
    }
    compiler = {
        "contract": fixture_contract(),
        "contract_sha256": comparison.sha256_file(CONTRACT_PATH),
        "checkpoint_tensors": {"block.out": [1, 2]},
        "output_tokens": fixture_contract()["reference"]["tokens"],
        "resources": {"lut": 120, "ff": 25, "bram": 2, "dsp": 3, "memory_bits": 1024, "path": report_path, "sha256": report_sha256, "measurement_id": "compiler-yosys"},
        "timing": {"max_frequency_mhz": 80.0, "critical_paths": [{"delay_ns": 12.5}], "cycles_per_token": 5, "interface_overhead_cycles": 2, "path": report_path, "sha256": report_sha256, "measurement_id": "compiler-timing"},
        "provenance": {
            "source": "compiler-fixture",
            "annotations": [
                {"kind": "buffer", "module": "block.buffer", "source_operation": "aten.add", "compiler_stage": "lowering", "resource": "lut", "measurement_id": "compiler-yosys", "measured_delta": 20}
            ],
        },
    }
    return reference, compiler


def run_compare(reference: dict[str, object], compiler: dict[str, object], manifest: dict[str, object], **kwargs: object) -> dict[str, object]:
    return comparison.compare(reference, compiler, manifest, frozen_contract=fixture_contract(), frozen_contract_path=CONTRACT_PATH, frozen_contract_sha256=comparison.sha256_file(CONTRACT_PATH), **kwargs)


class TinyStories1MSliceComparisonTest(unittest.TestCase):
    def test_comparison_rejects_mismatched_quantization(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest(), quantization="different")
        self.assertEqual(result["status"], "contract_mismatch")
        self.assertIn("quantization", result["reasons"][0])

    def test_comparison_reports_resource_and_timing_fields_when_aligned(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "aligned")
        self.assertEqual(result["resources"]["lut_delta"], 20)
        self.assertEqual(result["timing"]["critical_paths"]["compiler"][0]["delay_ns"], 12.5)
        self.assertEqual(result["timing"]["cycles_per_token_delta"], 1)
        self.assertEqual(result["waste_map"][0]["source_operation"], "aten.add")

    def test_requires_exact_checkpoints_and_final_outputs_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        del compiler["checkpoint_tensors"]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])

    def test_empty_checkpoints_or_tokens_are_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        compiler["checkpoint_tensors"] = {}
        compiler["output_tokens"] = []
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])

    def test_empty_resource_or_timing_evidence_is_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        compiler["resources"] = {}
        compiler["timing"] = {"max_frequency_mhz": 80.0, "critical_paths": [], "cycles_per_token": 5, "interface_overhead_cycles": 2}
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])

    def test_missing_report_provenance_is_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        del compiler["resources"]["sha256"]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")

    def test_compare_has_no_frozen_contract_bypass(self) -> None:
        reference, compiler = fixtures()
        with self.assertRaises(TypeError):
            comparison.compare(reference, compiler, fixture_slice_manifest())

    def test_equal_side_outputs_that_differ_from_frozen_reference_are_mismatch(self) -> None:
        reference, compiler = fixtures()
        reference["output_tokens"] = [99]
        compiler["output_tokens"] = [99]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "functional_mismatch")

    def test_public_api_rejects_slice_manifest_contract_sha_mismatch(self) -> None:
        reference, compiler = fixtures()
        manifest = fixture_slice_manifest()
        manifest["contract"]["sha256"] = "0" * 64
        result = run_compare(reference, compiler, manifest)
        self.assertEqual(result["status"], "contract_mismatch")

    def test_report_provenance_requires_existing_content_matching_hash(self) -> None:
        reference, compiler = fixtures()
        compiler["timing"]["path"] = "/does/not/exist"
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        reference, compiler = fixtures()
        compiler["resources"]["sha256"] = "0" * 64
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")

    def test_full_contract_identity_rejects_abi_and_reference_changes(self) -> None:
        reference, compiler = fixtures()
        compiler["contract"]["command_abi"]["version"] = 99
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")
        reference, compiler = fixtures()
        compiler["contract"]["reference"]["tokens"][0] = 12
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")

    def test_frozen_contract_hash_binds_each_evidence_side(self) -> None:
        reference, compiler = fixtures()
        compiler["contract_sha256"] = "f" * 64
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")

    def test_reports_functional_mismatch_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        compiler["checkpoint_tensors"] = {"block.out": [1, 9]}
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "functional_mismatch")
        self.assertIsNone(result["resources"])
        self.assertEqual(result["functional"]["first_mismatch"]["checkpoint"], "block.out")

    def test_report_parsers_preserve_raw_provenance_and_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            yosys = root / "yosys.json"
            yosys.write_text(json.dumps({"cells": {"lut": 12, "ff": 8, "bram": 1, "dsp": 2, "memory_bits": 256}}), encoding="utf-8")
            timing = root / "nextpnr.rpt"
            timing.write_text("Max frequency: 83.33 MHz\\ncritical path delay 12.0 ns\\ncycles_per_token: 9\\ninterface_overhead_cycles: 2\\n", encoding="utf-8")
            resources = comparison.parse_yosys_statistics(yosys)
            parsed_timing = comparison.parse_nextpnr_timing(timing)
            self.assertEqual(resources["lut"], 12)
            self.assertEqual(resources["sha256"], comparison.sha256_file(yosys))
            self.assertEqual(parsed_timing["max_frequency_mhz"], 83.33)
            self.assertEqual(parsed_timing["critical_paths"][0]["delay_ns"], 12.0)
            self.assertEqual(parsed_timing["cycles_per_token"], 9)

    def test_yosys_structural_utilization_json_preserves_real_statistics(self) -> None:
        path = ROOT / "artifacts/full-tinystories-pt2e-w8a8-scout/yosys-slang-structural-utilization.json"
        parsed = comparison.parse_yosys_statistics(path)
        self.assertEqual(parsed["memory_bits"], 236744916)
        self.assertEqual(parsed["structural_cells"]["$mux"], 708653)
        self.assertIsNone(parsed["lut"])

    def test_yosys_standard_stat_json_uses_top_module_cell_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stat.json"
            path.write_text(json.dumps({"modules": {"top": {"num_cells_by_type": {"LUT6": 11, "FDRE": 12, "RAMB36E1": 2, "DSP48E1": 3}}}}), encoding="utf-8")
            parsed = comparison.parse_yosys_statistics(path)
            self.assertEqual(parsed["lut"], 11)
            self.assertEqual(parsed["ff"], 12)
            self.assertEqual(parsed["bram"], 2)
            self.assertEqual(parsed["dsp"], 3)

    def test_manifest_contract_hash_mismatch_is_not_compared(self) -> None:
        manifest = fixture_slice_manifest()
        manifest["contract"]["sha256"] = "0" * 64
        self.assertEqual(comparison.manifest_contract_status(CONTRACT_PATH, manifest), "contract_mismatch")

    def test_waste_entries_require_stage_and_exact_measured_delta(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["waste_map"][0]["measured_delta"], 20)
        self.assertEqual(result["waste_map"][0]["measurement_id"], "compiler-yosys")
        del compiler["provenance"]["annotations"][0]["compiler_stage"]
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["waste_map"], [])

    def test_checked_in_comparison_is_honestly_incomplete_without_full_artifacts(self) -> None:
        committed = ROOT / "artifacts/comparison/tinystories-1m-slice-comparison.json"
        original = committed.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.json"
            self.assertEqual(comparison.main(["--contract", str(CONTRACT_PATH), "--slice-manifest", str(SLICE_MANIFEST_PATH), "--out", str(output)]), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "incomplete")
            self.assertIsNone(result["resources"])
            self.assertIsNone(result["timing"])
        self.assertEqual(committed.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
