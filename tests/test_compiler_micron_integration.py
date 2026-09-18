"""Cold-start the real compiler/DDR3 integration, never a replacement core."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(all(os.environ.get(key) for key in
    ("UBERDDR3_SOURCE", "MICRON_PARAMETERS", "MICRON_MODEL", "MICRON_IMAGE", "XSIM_BIN")),
    "requires the authenticated compiler/image and external simulation inputs")
class CompilerMicronIntegrationTest(unittest.TestCase):
    def run_integration(self, *extra):
        with tempfile.TemporaryDirectory(prefix="compiler-micron-integration-") as work:
            return subprocess.run([
                "bash", str(ROOT / "scripts/analysis/run_compiler_micron_sim.sh"),
                "--phase", "infer", "--simulator", "xsim", "--work-dir", work,
                "--xsim-bin", os.environ["XSIM_BIN"],
                "--uberddr3-source", os.environ["UBERDDR3_SOURCE"],
                "--vendor-parameters", os.environ["MICRON_PARAMETERS"],
                "--model", os.environ["MICRON_MODEL"],
                "--image", os.environ["MICRON_IMAGE"],
                "--max-cycles", "100", *extra,
            ], capture_output=True, text=True, timeout=300)

    def test_real_compiler_cannot_start_before_calibration(self):
        result = self.run_integration()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PASS: authenticated compiler and complete image", result.stdout)
        self.assertIn("FAIL: integration watchdog phase=0 host_requests=0", result.stdout,
                      (result.stdout + result.stderr)[-12000:])
        self.assertNotIn("PASS: full image readback", result.stdout)
        self.assertNotIn("PASS: compiler Micron first token", result.stdout)

    def test_wrong_image_rejected_before_elaboration(self):
        with tempfile.NamedTemporaryFile() as image:
            image.write(b"not the authenticated model")
            image.flush()
            result = self.run_integration("--image", image.name)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("image authentication failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
