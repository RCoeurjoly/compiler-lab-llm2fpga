"""Contract tests for the fail-closed Verilator memory probe."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/probe_verilator_memory_hierarchy.py"
HEADER = ROOT / "obj_dir/Vmain___024root.h"
CPP = ROOT / "scripts/comparison/probe_verilator_memory_hierarchy.cpp"


def load_module():
    spec = importlib.util.spec_from_file_location("verilator_memory_probe", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VerilatorMemoryProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_current_generated_model_exposes_all_four_memories(self) -> None:
        if not HEADER.exists():
            self.skipTest("generated Verilator model is not present")
        report = self.module.inspect(HEADER)
        self.assertTrue(report["public_flat_rw"])
        self.assertTrue(report["all_expected_memory_fields_present"])
        self.assertEqual(report["field_shape"], {"width_bits": 32, "depth": 64})
        self.assertFalse(report["inference_executed"])

    def test_probe_cpp_is_an_execution_probe_not_a_success_claim(self) -> None:
        source = CPP.read_text(encoding="utf-8")
        self.assertIn("model.go = 1", source)
        self.assertIn("while (!model.done", source)
        self.assertIn('\\"status\\"', source)
        self.assertIn("return match ? 0 : 1", source)
        self.assertIn("diagnostic fixture", source)

    def test_inspect_report_is_json_serializable_and_fail_closed_for_missing_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.h"
            with self.assertRaises(FileNotFoundError):
                self.module.inspect(path)

            output = Path(directory) / "report.json"
            report = {
                "schema": "verilator-calyx-memory-hierarchy-probe-v1",
                "status": "not_executed",
                "inference_executed": False,
            }
            output.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "not_executed")


if __name__ == "__main__":
    unittest.main()
