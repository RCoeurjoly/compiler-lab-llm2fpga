"""Normal-mode dispatch must delay, never mix or newly accept a busy event."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "third_party/task6-e368449/fpga/rtl/task6_ypcb_uberddr3_bist_rowstream_loader_top.sv"


def overlay_module():
    path = ROOT / "scripts/pipeline/apply_task6_command_overlay.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("command_overlay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommandDispatchTest(unittest.TestCase):
    def test_stage_exhaustive_decode_metadata_and_strict_lint(self):
        stage = ROOT / "rtl/diagnostics/task6_normal_command_stage.sv"
        lint = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module",
                               "task6_normal_command_stage", str(stage)],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        with tempfile.TemporaryDirectory(prefix="task3b-decode-") as directory:
            output = Path(directory) / "test.vvp"
            tb = ROOT / "tests/rtl/task6_normal_command_stage_tb.sv"
            built = subprocess.run(["iverilog", "-g2012", "-s", "task6_normal_command_stage_tb",
                                    "-o", str(output), str(stage), str(tb)],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run(["vvp", str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: exhaustive command decode/metadata", run.stdout)
            print(next(line for line in run.stdout.splitlines() if line.startswith("PASS:")))

    def test_authenticated_overlay_rejects_changed_input_and_output(self):
        module = overlay_module()
        self.assertIsNotNone(module, "authenticated normal-command overlay missing")
        original = SHELL.read_bytes()
        transformed = module.transform(original)
        self.assertNotEqual(original, transformed)
        self.assertEqual(transformed, module.transform(original))
        with self.assertRaisesRegex(ValueError, "input SHA-256"):
            module.transform(original + b"\n")
        with self.assertRaisesRegex(ValueError, "output SHA-256"):
            module.verify_output(transformed + b"\n")
        with tempfile.TemporaryDirectory() as directory:
            changed_stage = Path(directory) / "stage.sv"
            changed_stage.write_bytes(module.STAGE.read_bytes() + b"\n")
            module.STAGE = changed_stage
            with self.assertRaisesRegex(ValueError, "stage SHA-256"):
                module.transform(original)

    def test_normal_commands_cycle_reference_and_capture_safety(self):
        # Before the overlay exists this runs the REAL original shell as DUT:
        # RED must be the missing latency, not a missing file/compile error.
        module = overlay_module()
        candidate = module.transform(SHELL.read_bytes()) if module else SHELL.read_bytes()
        with tempfile.TemporaryDirectory(prefix="task3b-command-") as directory:
            work = Path(directory)
            dut = work / "candidate.sv"
            dut.write_bytes(candidate)
            reference = work / "reference.sv"
            reference.write_text(SHELL.read_text().split("module task6_uberddr3_loader_jtag_command_shift")[0].replace(
                "module task6_ypcb_uberddr3_bist_rowstream_loader_top #(",
                "module reference_loader #("))
            fixture = ROOT / "tests/rtl/compiler_ddr3_trace_replay_board_tb.sv"
            models = work / "models.sv"
            models.write_text(fixture.read_text()[fixture.read_text().index("module ddr3_top"):])
            sources = sorted(SHELL.parent.glob("*.sv")) + sorted(SHELL.parent.glob("*.v"))
            sources.remove(SHELL)
            build = subprocess.run([
                "verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "task6_command_dispatch_tb",
                "-DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS", "-DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS",
                "-DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS", "--Mdir", str(work / "obj"),
                *map(str, sources), str(ROOT / "rtl/diagnostics/task6_normal_command_stage.sv"),
                str(dut), str(reference), str(models),
                str(ROOT / "tests/rtl/task6_command_dispatch_tb.sv")],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(work / "obj/Vtask6_command_dispatch_tb")],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: normal command dispatch equivalence and capture safety", run.stdout)
            print(next(line for line in run.stdout.splitlines() if line.startswith("PASS:")))


if __name__ == "__main__":
    unittest.main()
