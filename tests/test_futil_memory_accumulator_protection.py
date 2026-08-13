import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/protect_futil_memory_accumulators.py"


FIXTURE = '''component main() -> () {
  cells {
    sum = std_add(32);
    old_reg = std_reg(32);
    term_reg = std_reg(32);
    unrelated = std_add(32);
  }
  wires {
    group accumulate {
      memory.write_data = sum.out;
      sum.left = old_reg.out;
      sum.right = term_reg.out;
      accumulate[done] = memory.done;
    }
  }
  control { accumulate; }
}
'''


class ProtectFutilMemoryAccumulatorsTest(unittest.TestCase):
    def test_protects_rmw_adder_and_operand_registers_only(self):
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "input.futil"
            output_path = Path(td) / "output.futil"
            receipt_path = Path(td) / "receipt.json"
            input_path.write_text(FIXTURE, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(input_path),
                    str(output_path),
                    str(receipt_path),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = output_path.read_text(encoding="utf-8")
            self.assertIn("@protected sum = std_add(32);", output)
            self.assertIn("@protected old_reg = std_reg(32);", output)
            self.assertIn("@protected term_reg = std_reg(32);", output)
            self.assertIn("    unrelated = std_add(32);", output)


if __name__ == "__main__":
    unittest.main()
