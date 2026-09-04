import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/materialize_zero_seed_copies.py"


FIXTURE = """module {
  func.func @main() {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c8 = arith.constant 8 : index
    %zero = arith.constant 0.000000e+00 : f32
    %seed = memref.alloc() : memref<8xf32, strided<[1]>>
    %seed_view = memref.reinterpret_cast %seed to offset: [0], sizes: [1, 8, 1], strides: [8, 1, 1] : memref<8xf32, strided<[1]>> to memref<1x8x1xf32>
    scf.for %i = %c0 to %c8 step %c1 {
      memref.store %zero, %seed[%i] : memref<8xf32, strided<[1]>>
    }
    %mean = memref.alloc() : memref<8xf32, strided<[1]>>
    %mean_view = memref.reinterpret_cast %mean to offset: [0], sizes: [1, 8, 1], strides: [8, 1, 1] : memref<8xf32, strided<[1]>> to memref<1x8x1xf32>
    memref.copy %seed_view, %mean_view : memref<1x8x1xf32> to memref<1x8x1xf32>
    %variance = memref.alloc() : memref<8xf32, strided<[1]>>
    %variance_view = memref.reinterpret_cast %variance to offset: [0], sizes: [1, 8, 1], strides: [8, 1, 1] : memref<8xf32, strided<[1]>> to memref<1x8x1xf32>
    memref.copy %seed_view, %variance_view : memref<1x8x1xf32> to memref<1x8x1xf32>
    memref.copy %mean_view, %variance_view : memref<1x8x1xf32> to memref<1x8x1xf32>
    return
  }
}
"""


class MaterializeZeroSeedCopiesTest(unittest.TestCase):
    def test_replaces_zero_seed_copies_with_destination_fills(self):
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "input.mlir"
            output_path = Path(td) / "output.mlir"
            receipt_path = Path(td) / "receipt.json"
            input_path.write_text(FIXTURE, encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(input_path), str(output_path), str(receipt_path)],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = output_path.read_text(encoding="utf-8")
            self.assertNotIn("memref.copy %seed_view, %mean_view", output)
            self.assertNotIn("memref.copy %seed_view, %variance_view", output)
            self.assertIn("memref.store %zero, %mean[", output)
            self.assertIn("memref.store %zero, %variance[", output)
            self.assertIn("memref.copy %mean_view, %variance_view", output)

    def test_nix_stage_creates_output_directory_before_receipt(self):
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        stage = pipeline[pipeline.index("tmp_zero_seed_fixed=") :]
        self.assertLess(
            stage.index('mkdir -p "$out"'),
            stage.index("materialize_zero_seed_copies.py"),
        )


if __name__ == "__main__":
    unittest.main()
