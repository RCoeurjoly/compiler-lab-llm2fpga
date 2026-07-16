import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "audit_rc_sv_interface.py"
REPRODUCER = ROOT / "reproducers" / "rc-working-io" / "input.mlir"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_rc_sv_interface", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RcWorkingIoAbiTest(unittest.TestCase):
    def test_captured_rc_abi_has_token_and_raw_output_memrefs(self) -> None:
        module = load_module()

        report = module.audit_flat_scf_abi(REPRODUCER.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "flat-scf-abi-confirmed")
        self.assertEqual(report["entry"], "main")
        self.assertEqual(report["argument_count"], 27)
        self.assertEqual(report["function_result"], "none")
        self.assertEqual(report["token_input"]["argument_index"], 25)
        self.assertEqual(report["token_input"]["type"], "memref<1x8xi64>")
        self.assertEqual(report["output_buffer"]["argument_index"], 26)
        self.assertEqual(report["output_buffer"]["type"], "memref<1x8x6xi8>")
        self.assertEqual(report["output_buffer"]["final_position"], 7)
        self.assertFalse(report["materialization_required"])

    def test_scalar_return_is_not_mistaken_for_the_rc_buffer_abi(self) -> None:
        module = load_module()
        scalar_return = """
module {
  func.func @main(%tokens: memref<1x8xi64>) -> i32 {
    %zero = arith.constant 0 : i32
    return %zero : i32
  }
}
"""

        report = module.audit_flat_scf_abi(scalar_return)

        self.assertEqual(report["status"], "blocked-abi")
        self.assertIn("function result", report["reason"])

    def test_done_only_sv_top_is_rejected(self) -> None:
        module = load_module()
        done_only_sv = """
module main(
  input logic clk,
  input logic reset,
  input logic go,
  output logic done
);
endmodule
"""

        report = module.audit_sv_text(done_only_sv, top_module="main")

        self.assertEqual(report["status"], "blocked-done-only")
        self.assertIn("token", report["missing"])
        self.assertIn("raw-output", report["missing"])

    def test_cli_records_not_built_sv_without_claiming_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "interface.json"
            rc = __import__("subprocess").run(
                [
                    "python3",
                    str(SCRIPT),
                    "--flat-scf",
                    str(REPRODUCER),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rc.returncode, 0, rc.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "flat-scf-abi-confirmed")
        self.assertEqual(report["sv_interface"]["status"], "not-built")

    def test_cli_records_a_calyx_frontier_before_sv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "interface.json"
            manifest = root / "calyx-manifest.json"
            log = root / "lower-scf-to-calyx.log"
            manifest.write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "reason": "lower-scf-to-calyx did not produce a Calyx artifact",
                    }
                ),
                encoding="utf-8",
            )
            log.write_text(
                "/build/pre-calyx.mlir:2026:16: error: Unhandled operation during "
                "BuildOpGroups()\n%0 = math.exp %arg0 : f32\n",
                encoding="utf-8",
            )
            rc = __import__("subprocess").run(
                [
                    "python3",
                    str(SCRIPT),
                    "--flat-scf",
                    str(REPRODUCER),
                    "--calyx-manifest",
                    str(manifest),
                    "--calyx-log",
                    str(log),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rc.returncode, 0, rc.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["calyx"]["status"], "failed")
        self.assertIn("Unhandled operation", report["calyx"]["first_diagnostic"])
        self.assertIn("math.exp", report["calyx"]["first_diagnostic"])
        self.assertEqual(report["sv_interface"]["status"], "blocked-before-sv")


if __name__ == "__main__":
    unittest.main()
