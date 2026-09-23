"""Bounded 512-line transaction-level loader fixture.

This deliberately uses the existing pinned PCIe/loader testbench and only
scales its command count.  It is not a Micron pin-level simulation and does
not claim to model PCIe ingress or physical DDR3 timing.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERILATOR = Path("/nix/store/7mil9l34vfbvmh0cm6wvbdapwv77bz9v-verilator-5.022/bin/verilator")


class CompilerDdr3512FixtureTest(unittest.TestCase):
    def test_512_line_loader_round_trip(self):
        if not VERILATOR.is_file():
            self.skipTest("pinned Verilator 5.022 is unavailable")
        source = (ROOT / "tests/rtl/compiler_ddr3_trace_replay_board_tb.sv").read_text()
        self.assertEqual(source.count("for(i=0;i<8;i=i+1)"), 2)
        source = source.replace("for(i=0;i<8;i=i+1)", "for(i=0;i<512;i=i+1)")
        # The parent fixture intentionally has only 32 words.  Enlarge only
        # this temporary behavioral memory; production RTL is untouched.
        source = source.replace("memory[0:31]", "memory[0:511]")
        source = source.replace("i_wb_addr>=32", "i_wb_addr>=512")
        with tempfile.TemporaryDirectory(prefix="compiler-ddr3-512-") as directory:
            directory = Path(directory)
            tb = directory / "compiler_ddr3_trace_replay_board_512_tb.sv"
            tb.write_text(source)
            output = directory / "obj"
            sources = sorted((ROOT / "third_party/task6-e368449").rglob("*.sv"))
            sources += sorted((ROOT / "third_party/task6-e368449").rglob("*.v"))
            sources += sorted((ROOT / "rtl/diagnostics").glob("*.sv"))
            from scripts.pipeline.apply_task6_command_overlay import transform
            shell = ROOT / "third_party/task6-e368449/fpga/rtl/task6_ypcb_uberddr3_bist_rowstream_loader_top.sv"
            staged_shell = directory / shell.name
            staged_shell.write_bytes(transform(shell.read_bytes()))
            sources[sources.index(shell)] = staged_shell
            from scripts.pipeline.apply_task6_m2_banking_overlay import transform as bank_transform
            ingress = shell.with_name("task6_pcie_axil_rowstream_loader_ingress.v")
            banked_ingress = directory / ingress.name
            banked_ingress.write_bytes(bank_transform(ingress.read_bytes()))
            sources[sources.index(ingress)] = banked_ingress
            built = subprocess.run(
                [str(VERILATOR), "--binary", "--timing", "-Wno-fatal",
                 "-DTASK6_PCIE_ROWSTREAM_INGRESS_PORTS",
                 "-DTASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS",
                 "-DTASK6_COMPILER_DDR3_ACCELERATOR_PORTS",
                 "--top-module", "compiler_ddr3_trace_replay_board_tb",
                 "--Mdir", str(output), *map(str, sources), str(tb)],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(output / "Vcompiler_ddr3_trace_replay_board_tb")],
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: full pinned loader shell BAR fixture", run.stdout)


if __name__ == "__main__":
    unittest.main()
