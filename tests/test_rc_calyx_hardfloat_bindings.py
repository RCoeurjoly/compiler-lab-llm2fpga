import importlib.util
import json
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

    def test_mrc_assignments_require_the_exact_unique_declared_set(self) -> None:
        module = load_module()
        expected = [f"{mrc_id}=/tmp/{mrc_id}.mlir" for mrc_id in module.MRC_SPECS]

        parsed = module.parse_mrc_assignments(expected)

        self.assertEqual(set(parsed), set(module.MRC_SPECS))
        with self.assertRaisesRegex(ValueError, "duplicate MRC ID: addf-f32"):
            module.parse_mrc_assignments(expected + ["addf-f32=/tmp/other.mlir"])
        with self.assertRaisesRegex(ValueError, "missing MRC IDs"):
            module.parse_mrc_assignments(expected[:-1])

    def test_yosys_slang_uses_calyx_ansi_port_compatibility_mode(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            fake_yosys = directory / "fake-yosys"
            fake_yosys.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(fake_yosys, 0o755)
            source = directory / "main.sv"
            source.write_text("module main; endmodule\n", encoding="utf-8")

            result = module.run_yosys_slang(
                str(fake_yosys), "unused-slang-plugin", source, directory / "yosys.log"
            )

        self.assertEqual(result["status"], "accepted")
        self.assertIn("--allow-merging-ansi-ports", result["command"][-1])

    def test_native_export_runs_the_existing_script_under_explicit_bash(self) -> None:
        module = load_module()

        command = module.native_export_command(
            Path("/nix/store/bash/bin/bash"),
            Path("/nix/store/calyx-to-sv.sh"),
            Path("/nix/store/circt-translate"),
            Path("/nix/store/calyx"),
            Path("/nix/store/calyx-lib"),
            Path("/nix/store/calyx-dir"),
            Path("/nix/store/native-sv"),
        )

        self.assertEqual(
            command[:2],
            ["/nix/store/bash/bin/bash", "/nix/store/calyx-to-sv.sh"],
        )

    def test_cli_writes_rejected_rows_when_circt_emits_partial_diagnostic_output(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            flat_scf = directory / "flat.scf.mlir"
            flat_scf.write_text(SAMPLE_FLAT_SCF, encoding="utf-8")
            fake_circt = directory / "fake-circt-opt"
            fake_circt.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib\n"
                "import sys\n"
                "output = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                "output.write_text('partial', encoding='utf-8')\n"
                "print('error: unsupported', file=sys.stderr)\n",
                encoding="utf-8",
            )
            os.chmod(fake_circt, 0o755)
            calyx_lib = directory / "calyx-lib"
            (calyx_lib / "primitives").mkdir(parents=True)
            plugin = directory / "slang.so"
            plugin.write_text("placeholder", encoding="utf-8")
            out_dir = directory / "out"
            mrc_args = []
            for mrc_id in module.MRC_SPECS:
                path = directory / f"{mrc_id}.mlir"
                path.write_text("module {}\n", encoding="utf-8")
                mrc_args.extend(["--mrc", f"{mrc_id}={path}"])

            result = module.main(
                [
                    "--flat-scf",
                    str(flat_scf),
                    "--circt-opt",
                    str(fake_circt),
                    "--circt-translate",
                    "/bin/true",
                    "--calyx-bin",
                    "/bin/true",
                    "--calyx-lib",
                    str(calyx_lib),
                    "--calyx-to-sv-script",
                    "/bin/true",
                    "--bash",
                    "/bin/true",
                    "--yosys",
                    "/bin/true",
                    "--yosys-slang-plugin",
                    str(plugin),
                    *mrc_args,
                    "--out-dir",
                    str(out_dir),
                ]
            )
            report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(len(report["mrcs"]), len(module.MRC_SPECS))
        self.assertTrue(all(row["circt"]["status"] == "rejected" for row in report["mrcs"]))
        self.assertTrue(all(row["binding_status"] == "not-attempted" for row in report["mrcs"]))


if __name__ == "__main__":
    unittest.main()
