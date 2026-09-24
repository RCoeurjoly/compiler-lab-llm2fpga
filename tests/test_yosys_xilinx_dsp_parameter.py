"""Regression for Yosys' optional DSP48E1 pattern-detect parameter."""

import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "yosys_xilinx_dsp_missing_pattern.sv"


class YosysXilinxDspParameterTest(unittest.TestCase):
    def test_missing_pattern_parameter_does_not_abort_mapper(self):
        yosys = os.environ.get("YOSYS_BIN") or shutil.which("yosys")
        if not yosys:
            self.skipTest("YOSYS_BIN or yosys is required")
        result = subprocess.run(
            [yosys, "-q", "-p", (
                f"read_verilog -sv {FIXTURE}; hierarchy -top top; proc; "
                "xilinx_dsp -family xc7"
            )],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("USE_PATTERN_DETECT", result.stderr)


if __name__ == "__main__":
    unittest.main()
