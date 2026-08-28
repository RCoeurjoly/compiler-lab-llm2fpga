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
    reference = {
        "contract": fixture_contract(),
        "checkpoint_tensors": {"block.out": [1, 2]},
        "output_tokens": [11, 612],
        "resources": {"lut": 100, "ff": 20, "bram": 2, "dsp": 3, "memory_bits": 512},
        "timing": {"max_frequency_mhz": 100.0, "critical_paths": [{"delay_ns": 10.0}], "cycles_per_token": 4, "interface_overhead_cycles": 1},
        "provenance": {"source": "reference-fixture"},
    }
    compiler = {
        "contract": fixture_contract(),
        "checkpoint_tensors": {"block.out": [1, 2]},
        "output_tokens": [11, 612],
        "resources": {"lut": 120, "ff": 25, "bram": 2, "dsp": 3, "memory_bits": 1024},
        "timing": {"max_frequency_mhz": 80.0, "critical_paths": [{"delay_ns": 12.5}], "cycles_per_token": 5, "interface_overhead_cycles": 2},
        "provenance": {
            "source": "compiler-fixture",
            "annotations": [
                {"kind": "buffer", "module": "block.buffer", "source_operation": "aten.add", "resource": "lut", "amount": 20}
            ],
        },
    }
    return reference, compiler


class TinyStories1MSliceComparisonTest(unittest.TestCase):
    def test_comparison_rejects_mismatched_quantization(self) -> None:
        reference, compiler = fixtures()
        result = comparison.compare(reference, compiler, fixture_slice_manifest(), quantization="different")
        self.assertEqual(result["status"], "contract_mismatch")
        self.assertIn("quantization", result["reasons"][0])

    def test_comparison_reports_resource_and_timing_fields_when_aligned(self) -> None:
        reference, compiler = fixtures()
        result = comparison.compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "aligned")
        self.assertEqual(result["resources"]["lut_delta"], 20)
        self.assertEqual(result["timing"]["critical_paths"]["compiler"][0]["delay_ns"], 12.5)
        self.assertEqual(result["timing"]["cycles_per_token_delta"], 1)
        self.assertEqual(result["waste_map"][0]["source_operation"], "aten.add")

    def test_requires_exact_checkpoints_and_final_outputs_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        del compiler["checkpoint_tensors"]
        result = comparison.compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])

    def test_reports_functional_mismatch_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        compiler["checkpoint_tensors"] = {"block.out": [1, 9]}
        result = comparison.compare(reference, compiler, fixture_slice_manifest())
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

    def test_manifest_contract_hash_mismatch_is_not_compared(self) -> None:
        manifest = fixture_slice_manifest()
        manifest["contract"]["sha256"] = "0" * 64
        self.assertEqual(comparison.manifest_contract_status(CONTRACT_PATH, manifest), "contract_mismatch")

    def test_checked_in_comparison_is_honestly_incomplete_without_full_artifacts(self) -> None:
        output = ROOT / "artifacts/comparison/tinystories-1m-slice-comparison.json"
        self.assertEqual(comparison.main(["--contract", str(CONTRACT_PATH), "--slice-manifest", str(SLICE_MANIFEST_PATH), "--out", str(output)]), 0)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])


if __name__ == "__main__":
    unittest.main()
