import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "run_rc_calyx_hardfloat_bindings.py"

SAMPLE_FLAT_SCF = """
module {
  func.func @main(%i32: i32, %i1: i1, %a: f32, %b: f32) {
    %0 = arith.addf %a, %b : f32
    %1 = arith.subf %a, %b : f32
    %2 = arith.mulf %a, %b : f32
    %3 = arith.divf %a, %b : f32
    %4 = arith.cmpf ugt, %a, %b : f32
    %5 = arith.sitofp %i32 : i32 to f32
    %6 = arith.fptosi %a : f32 to i8
    %7 = arith.uitofp %i1 : i1 to f32
    %8 = math.exp %a : f32
    %9 = math.sin %a : f32
    return
  }
}
"""


def load_module():
    spec = importlib.util.spec_from_file_location("rc_calyx_hardfloat_bindings", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RcCalyxHardfloatBindingsTest(unittest.TestCase):
    def test_observes_declared_forms_without_rejecting_unknown_float_ops(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flat.scf.mlir"
            path.write_text(SAMPLE_FLAT_SCF, encoding="utf-8")
            report = module.observe_rc_forms(path)

        self.assertEqual(report["policy"], module.NON_GATING_POLICY)
        self.assertEqual(report["forms"]["arith.addf.f32"]["count"], 1)
        self.assertEqual(report["forms"]["arith.fptosi.f32-to-i8"]["count"], 1)
        self.assertEqual(report["forms"]["arith.uitofp.i1-to-f32"]["count"], 1)
        self.assertIn("math.exp", report["unclassified_float_operations"])
        self.assertIn("math.sin", report["unclassified_float_operations"])
        self.assertEqual(module.MRC_SPECS["addf-f32"]["form_id"], "arith.addf.f32")
        self.assertEqual(
            module.MRC_SPECS["fptosi-f32-i8"]["expected_wrapper"], "std_fpToInt"
        )
        module.require_observed_forms(report)

    def test_rejects_zero_exit_when_diagnostic_and_partial_output_exist(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            fake_tool = directory / "fake-tool"
            output = directory / "partial.mlir"
            log = directory / "fake-tool.log"
            fake_tool.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib\n"
                "import sys\n"
                "output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                "output.write_text('partial', encoding='utf-8')\n"
                "print('error: unsupported', file=sys.stderr)\n",
                encoding="utf-8",
            )
            os.chmod(fake_tool, 0o755)

            result = module.run_command(
                "fake-tool", [str(fake_tool), "-o", str(output)], log, output
            )

        self.assertEqual(result["status"], "rejected")
        self.assertTrue(result["diagnostic_error"])
        self.assertTrue(result["output_exists"])

    def test_classifies_binding_evidence_without_inferring_from_float_ops(self) -> None:
        module = load_module()

        self.assertEqual(
            module.binding_status({"status": "rejected"}, False, set()),
            "not-attempted",
        )
        self.assertEqual(
            module.binding_status({"status": "accepted"}, False, set()),
            "native-export-rejected",
        )
        self.assertEqual(
            module.binding_status(
                {"status": "accepted"}, True, {"std_addFN", "addRecFN", "fNToRecFN"}
            ),
            "accepted-with-hardfloat-binding",
        )


if __name__ == "__main__":
    unittest.main()
