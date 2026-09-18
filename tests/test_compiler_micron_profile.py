"""Exercise the real Micron model, including rejection of an incompatible part."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/analysis/run_compiler_micron_sim.sh"


@unittest.skipUnless(
    os.environ.get("UBERDDR3_SOURCE") and os.environ.get("MICRON_PARAMETERS"),
    "requires explicit UberDDR3 and licensed Micron parameter inputs",
)
class MicronProfileTest(unittest.TestCase):
    def run_profile(self, *extra):
        source = os.environ["UBERDDR3_SOURCE"]
        parameters = os.environ["MICRON_PARAMETERS"]
        with tempfile.TemporaryDirectory(prefix="micron-profile-") as directory:
            result = subprocess.run(
                ["bash", str(RUNNER), "--phase", "profile", "--work-dir", directory,
                 "--uberddr3-source", source, "--vendor-parameters", parameters,
                 *extra], capture_output=True, text=True, timeout=120,
            )
            receipt = Path(directory) / "sources.sha256"
            return result, receipt.read_text() if receipt.exists() else ""

    def test_board_part_elaborates_with_strict_checks(self):
        result, receipt = self.run_profile()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: micron profile rows=15 cols=10 banks=3 dq=16", result.stdout)
        self.assertIn("4096Mb_ddr3_parameters.vh", receipt)
        self.assertIn("ddr3.sv", receipt)

    def test_wrong_density_fails_at_runtime(self):
        result, _ = self.run_profile("--negative-control", "wrong-geometry")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: Micron geometry", result.stdout)
        self.assertNotIn("PASS: micron profile", result.stdout)

    def test_missing_vendor_input_is_not_silently_substituted(self):
        result, _ = self.run_profile("--vendor-parameters", "/nonexistent/4096Mb_ddr3_parameters.vh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing vendor parameters", result.stderr)


if __name__ == "__main__":
    unittest.main()
