"""Integration behavior at the real loader AXI and production owner mux."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReplayTopTest(unittest.TestCase):
    def test_pcie_bar_boundary_does_not_add_a_timing_disruptive_bscan(self):
        """BAR evidence is carried by the overlaid existing USER1 status chain."""
        text = (ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay_top.sv").read_text()
        self.assertNotIn("compiler_pcie_bar_status_shift", text)

    def test_pcie_transport_reset_does_not_depend_on_ddr_pll_lock(self):
        """A failed DDR PLL must not turn an enumerated BAR into all-ones reads."""
        text = (ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay_top.sv").read_text()
        self.assertIn(".pcie_reset(!pcie_user_cfg_rst_n)", text)
        self.assertIn("always @(posedge pcie_user_clk or negedge rowstream_rst_n)", text)
        self.assertIn(".pcie_abort(pcie_user_reset && replay_pcie_init[1])", text)

    def test_transport_shell_is_a_staged_synthesis_boundary(self):
        text = (ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay_top.sv").read_text()
        self.assertRegex(text, r"\(\*\s*keep_hierarchy\s*=\s*\"yes\"\s*\*\)\s*task6_ypcb_uberddr3_bist_rowstream_loader_top")

    def test_full_pinned_loader_shell_bar_fixture(self):
        tb = ROOT / "tests/rtl/compiler_ddr3_trace_replay_board_tb.sv"
        self.assertTrue(tb.exists(), "full board loader-shell fixture is missing")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "obj"
            sources = sorted((ROOT / "third_party/task6-e368449").rglob("*.sv"))
            sources += sorted((ROOT / "third_party/task6-e368449").rglob("*.v"))
            sources += sorted((ROOT / "rtl/diagnostics").glob("*.sv"))
            from scripts.pipeline.apply_task6_command_overlay import transform
            shell = ROOT / "third_party/task6-e368449/fpga/rtl/task6_ypcb_uberddr3_bist_rowstream_loader_top.sv"
            staged_shell = Path(directory) / shell.name
            staged_shell.write_bytes(transform(shell.read_bytes()))
            sources[sources.index(shell)] = staged_shell
            from scripts.pipeline.apply_task6_m2_banking_overlay import transform as bank_transform
            ingress = shell.with_name("task6_pcie_axil_rowstream_loader_ingress.v")
            banked_ingress = Path(directory) / ingress.name
            banked_ingress.write_bytes(bank_transform(ingress.read_bytes()))
            sources[sources.index(ingress)] = banked_ingress
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
            from scripts.pipeline.apply_task6_m2_banking_overlay import transform as bank_transform
            banked_ingress = Path(directory) / sources[4].name
            banked_ingress.write_bytes(bank_transform(sources[4].read_bytes()))
            sources[4] = banked_ingress
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

    def test_runtime_transport_reset_mutation_is_detected(self):
        run = self.simulate_fabric(("if(transport_reset) begin", "if(pcie_reset) begin"))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("runtime reset retained", run.stdout)

    def test_row_transport_flush_mutation_is_detected(self):
        run = self.simulate_fabric((".transport_reset(flush_sync)", ".transport_reset(1'b0)"))
        self.assertNotEqual(run.returncode, 0)
        self.assertRegex(run.stdout, "test timeout|read 00000904 expected 00000001 got 52504c59")

    def test_starvation_ownership_mutation_is_detected(self):
        run = self.simulate_fabric(("assign wb_cyc=replay_active || core_cyc || pending;",
                                    "assign wb_cyc=core_cyc || pending;"))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("starvation released", run.stdout)


if __name__ == "__main__":
    unittest.main()
