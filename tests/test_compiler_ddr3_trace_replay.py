"""Behavioral tests of temporary diagnostic RTL, not compiler output."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl/diagnostics"
TB = ROOT / "tests/rtl/compiler_ddr3_trace_replay_tb.sv"


class CompilerDdr3TraceReplayTest(unittest.TestCase):
    def simulate(self, mutation=None, owner_mux=False):
        self.assertIsNotNone(shutil.which("iverilog"))
        sources = [RTL / "compiler_ddr3_trace_replay.sv",
                   RTL / "compiler_ddr3_trace_replay_csr.sv"]
        for source in sources:
            self.assertTrue(source.is_file(), f"missing diagnostic RTL: {source}")
        with tempfile.TemporaryDirectory(prefix="compiler-replay-test-") as tmp:
            directory = Path(tmp)
            if mutation:
                old, new = mutation
                source = sources[0].read_text()
                self.assertEqual(source.count(old), 1)
                changed = directory / sources[0].name
                changed.write_text(source.replace(old, new))
                sources[0] = changed
            options = []
            if owner_mux:
                mux = Path("/nix/store/5f2fppa4a3636py498f4pv5500dsizfm-task6_wishbone_owner_mux.sv")
                self.assertTrue(mux.is_file(), "pinned production owner mux is required")
                sources.append(mux)
                options.append("-DTEST_OWNER_MUX")
            build = subprocess.run(["iverilog", "-g2012", *options, "-s", "compiler_ddr3_trace_replay_tb",
                                    "-o", str(directory / "test.vvp"), *map(str, sources), str(TB)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            return subprocess.run(["vvp", str(directory / "test.vvp")],
                                  capture_output=True, text=True, timeout=30)

    def test_replay_and_csr_contract(self):
        result = self.simulate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: diagnostic replay and CSR contract", result.stdout)

    def test_request_address_mutation_is_detected(self):
        result = self.simulate(("active_address <= fifo_address[read_pointer];",
                                "active_address <= fifo_address[read_pointer] ^ 32'd1;"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("request order/stability", result.stdout)

    def test_replay_through_pinned_production_owner_mux(self):
        result = self.simulate(owner_mux=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: diagnostic replay and CSR contract", result.stdout)

    def test_first_failure_mutation_is_detected(self):
        result = self.simulate(("first_actual <= wb_rdata;", "first_actual <= 128'd0;"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("first failure actual", result.stdout)


if __name__ == "__main__":
    unittest.main()
