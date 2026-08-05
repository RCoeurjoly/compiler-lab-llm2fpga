import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = REPO_ROOT / "rtl" / "rc-working" / "rc_ddr3_adapter.sv"
TESTBENCH = REPO_ROOT / "sim" / "rc-working" / "rc_ddr3_transport_tb.sv"


def _iverilog() -> Path:
    configured = os.environ.get("IVERILOG")
    if configured:
        return Path(configured)
    discovered = shutil.which("iverilog")
    if discovered:
        return Path(discovered)
    candidates = sorted(Path("/nix/store").glob("*-iverilog-*/bin/iverilog"))
    if candidates:
        return candidates[-1]
    raise unittest.SkipTest("iverilog is required for the DDR3 transport microcase")


class RcDdr3TransportTest(unittest.TestCase):
    def test_adapter_transport_contract_against_host_ddr3_model(self):
        """A broken address/lane, stall, reset, ordering, or write path fails SV simulation."""
        iverilog = _iverilog()
        self.assertTrue(ADAPTER.is_file(), "transport adapter source is missing")
        self.assertTrue(TESTBENCH.is_file(), "transport testbench source is missing")
        vvp = iverilog.with_name("vvp")
        if not vvp.is_file():
            discovered = shutil.which("vvp")
            if not discovered:
                self.skipTest("vvp is required for the DDR3 transport microcase")
            vvp = Path(discovered)

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "rc_ddr3_transport.vvp"
            compile_result = subprocess.run(
                [str(iverilog), "-g2012", "-s", "rc_ddr3_transport_tb", "-o",
                 str(executable), str(ADAPTER), str(TESTBENCH)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(vvp), str(executable)], cwd=REPO_ROOT, text=True, capture_output=True
            )

        self.assertEqual(run_result.returncode, 0, run_result.stdout + run_result.stderr)
        self.assertIn("RC_DDR3_TRANSPORT_PASS", run_result.stdout)


if __name__ == "__main__":
    unittest.main()
