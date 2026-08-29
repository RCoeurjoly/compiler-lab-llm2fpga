"""Fail-closed tests for the Task 3r backend execution probe."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/execute_tinystories_1m_fixed_layernorm_backend.py"
BACKEND = ROOT / "artifacts/comparison/tinystories-1m-fixed-layernorm-backend.json"
CALYX = ROOT / "artifacts/comparison/tinystories-1m-fixed-layernorm-backend.calyx.mlir"
VECTOR = ROOT / "artifacts/reference/tinystories-1m-rtl-layernorm-vector.json"


def load_module():
    spec = importlib.util.spec_from_file_location("task3r_execution", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackendExecutionProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.inputs = cls.module.load_inputs(BACKEND, CALYX, VECTOR)
        cls.inputs["backend_path"] = str(BACKEND)
        cls.inputs["vector_path"] = str(VECTOR)

    def test_authenticated_artifacts_and_vector_are_required(self):
        with self.assertRaisesRegex(self.module.ExecutionProbeError, "missing_artifact"):
            self.module.load_inputs(BACKEND, CALYX.with_name("does-not-exist.mlir"), VECTOR)

    def test_no_calyx_runtime_is_a_concrete_boundary(self):
        report = self.module.build_report(self.inputs, calyx_bin="/does/not/exist", fud="/does/not/exist", verilator="/does/not/exist")
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["execution"]["status"], "not_executed")
        self.assertEqual(report["execution"]["first_unsupported_operation"]["code"], "calyx_runtime_unavailable")
        self.assertEqual(report["numeric_trace"]["status"], "algorithm_matched_backend_execution_not_run")
        self.assertEqual(report["numeric_trace"]["result"], self.inputs["vector"]["result"])

    def test_available_calyx_still_requires_memory_harness(self):
        report = self.module.build_report(self.inputs, calyx_bin="/bin/sh", fud="/does/not/exist", verilator="/does/not/exist")
        self.assertEqual(report["execution"]["first_unsupported_operation"]["code"], "external_memory_harness_not_implemented")
        self.assertEqual(report["execution"]["external_memory_inventory"]["external_memories"], 4)

    def test_report_self_hash_is_reproducible(self):
        report = self.module.build_report(self.inputs, calyx_bin="/does/not/exist")
        report["sha256"] = self.module.canonical_sha256(report)
        self.assertEqual(report["sha256"], self.module.canonical_sha256({k: v for k, v in report.items() if k != "sha256"}))


if __name__ == "__main__":
    unittest.main()
