import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "normalize_calyx_for_export.py"
FUTIL_SCRIPT = ROOT / "scripts" / "pipeline" / "normalize_futil_float_constants.py"


class CalyxExportNormalizationTest(unittest.TestCase):
    def test_removes_only_unreferenced_private_memref_globals(self) -> None:
        source = """module {
  memref.global "private" constant @dead : memref<1xf32> = dense<3.0>
  memref.global "private" constant @live : memref<1xf32> = dense<4.0>
  %0 = memref.get_global @live : memref<1xf32>
  calyx.component @main(%clk: i1 {clk}) -> () {
  }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "output.mlir"
            input_path.write_text(source, encoding="utf-8")
            subprocess.run(
                ["python3", str(SCRIPT), str(input_path), str(output_path)],
                check=True,
            )
            normalized = output_path.read_text(encoding="utf-8")

        self.assertNotIn("@dead", normalized)
        self.assertIn("@live", normalized)
        self.assertIn("memref.get_global @live", normalized)

    def test_native_export_runs_normalization_before_export(self) -> None:
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        script = (
            ROOT / "scripts" / "pipeline" / "calyx_to_sv_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("normalize_calyx_for_export.py", pipeline)
        self.assertIn("CALYX_NORMALIZE_FOR_EXPORT", pipeline)
        self.assertIn("CALYX_NORMALIZE_FUTIL_CONSTANTS", pipeline)
        self.assertIn('"$normalize_for_export" "$input"', script)
        self.assertIn('"$normalize_futil_constants" "$tmp_exported_futil"', script)
        self.assertIn("ulimit -s unlimited", script)

    def test_float_constants_become_exact_ieee_bit_constants(self) -> None:
        source = """cells {
  zero = std_float_const(0, 32, 0.000000);
  half = std_float_const(0, 32, 0.500000);
  neg = std_float_const(0, 32, -1.000000);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.futil"
            output_path = Path(tmp) / "output.futil"
            input_path.write_text(source, encoding="utf-8")
            subprocess.run(
                ["python3", str(FUTIL_SCRIPT), str(input_path), str(output_path)],
                check=True,
            )
            normalized = output_path.read_text(encoding="utf-8")

        self.assertIn("zero = std_const(32, 0);", normalized)
        self.assertIn("half = std_const(32, 1056964608);", normalized)
        self.assertIn("neg = std_const(32, 3212836864);", normalized)
        self.assertNotIn("std_float_const", normalized)


if __name__ == "__main__":
    unittest.main()
