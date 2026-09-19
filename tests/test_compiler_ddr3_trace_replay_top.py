"""Integration behavior at the real loader AXI and production owner mux."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReplayTopTest(unittest.TestCase):
    def test_full_pinned_loader_shell_bar_fixture(self):
        tb = ROOT / "tests/rtl/compiler_ddr3_trace_replay_board_tb.sv"
        self.assertTrue(tb.exists(), "full board loader-shell fixture is missing")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "obj"
            sources = sorted((ROOT / "third_party/task6-e368449").rglob("*.sv"))
            sources += sorted((ROOT / "third_party/task6-e368449").rglob("*.v"))
            sources += sorted((ROOT / "rtl/diagnostics").glob("*.sv"))
            # The pinned loader uses 3-bit enum literals in a 4-bit enum.
            # Verilator accepts this legacy source; Icarus rejects it. Do not
            # rewrite the authenticated loader just for simulator convenience.
            built = subprocess.run(["verilator", "--binary", "--timing", "-Wno-fatal",
                                    "-DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS",
                                    "-DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS", "-DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS",
                                    "--top-module", "compiler_ddr3_trace_replay_board_tb", "--Mdir", str(output),
                                    *map(str, sources), str(tb)], capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(output / "Vcompiler_ddr3_trace_replay_board_tb")],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: full pinned loader shell BAR fixture", run.stdout)

    def test_screen_requires_completed_replay_top_and_driven_watched_nets(self):
        checker = ROOT / "scripts/analysis/check_compiler_shell_status.py"
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "yosys.log"
            complete = "Checking module compiler_ddr3_trace_replay_top...\nFound and reported 0 problems.\nEnd of script.\n"
            for contents, success in [(complete, True), (complete.replace("End of script.", ""), False),
                                      (complete + "Warning: Wire replay_ack is used but has no driver.\n", False)]:
                log.write_text(contents)
                result = subprocess.run(["python3", str(checker), str(log), "--top", "compiler_ddr3_trace_replay_top"],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def simulate_fabric(self, mutation=None):
        top = ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay_top.sv"
        self.assertTrue(top.is_file(), "integrated replay board top is missing")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test.vvp"
            sources = [top, ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay.sv",
                       ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay_csr.sv",
                       ROOT / "third_party/task6-e368449/fpga/rtl/task6_wishbone_owner_mux.sv",
                       ROOT / "third_party/task6-e368449/fpga/rtl/task6_pcie_axil_rowstream_loader_ingress.v",
                       ROOT / "tests/rtl/compiler_ddr3_trace_replay_top_tb.sv"]
            if mutation:
                old, new = mutation
                text = top.read_text()
                self.assertEqual(text.count(old), 1)
                changed = Path(directory) / top.name
                changed.write_text(text.replace(old, new))
                sources[0] = changed
            built = subprocess.run(["iverilog", "-g2012", "-s", "compiler_ddr3_trace_replay_top_tb",
                                    "-o", str(output), *map(str, sources)], capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            return subprocess.run(["vvp", str(output)], capture_output=True, text=True, timeout=30)

    def test_loader_readback_replay_handoff_and_abort_drain(self):
        run = self.simulate_fabric()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("PASS: integrated loader/replay/CDC/drain", run.stdout)

    def test_abort_drain_mutation_is_detected(self):
        run = self.simulate_fabric(("assign wb_cyc=replay_active || core_cyc || pending;",
                                    "assign wb_cyc=replay_active || core_cyc;"))
        self.assertNotEqual(run.returncode, 0)
        self.assertRegex(run.stdout, "outstanding|owner changed")

    def test_starvation_ownership_mutation_is_detected(self):
        run = self.simulate_fabric(("assign wb_cyc=replay_active || core_cyc || pending;",
                                    "assign wb_cyc=core_cyc || pending;"))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("starvation released", run.stdout)


if __name__ == "__main__":
    unittest.main()
