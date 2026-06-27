import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "diagnostics" / "flat_scf_blocker_report.py"


class FlatScfBlockerReportTest(unittest.TestCase):
    def test_reports_blocker_locations_with_context(self) -> None:
        mlir = """\
module {
  func.func @main(%arg0: memref<16xi1>) {
    scf.for %i = %c0 to %c16 step %c1 {
      %view = memref.reinterpret_cast %arg0 to offset: [0], sizes: [1, 1, 4, 4], strides: [16, 16, 4, 1] : memref<16xi1> to memref<1x1x4x4xi1, strided<[?, ?, ?, ?], offset: ?>>
      %flat = memref.collapse_shape %view [[0, 1, 2, 3]] : memref<1x1x4x4xi1, strided<[?, ?, ?, ?], offset: ?>> into memref<16xi1>
      %bit = memref.load %flat[%i] : memref<16xi1>
    }
    return
  }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "flat.scf.mlir"
            output_path = Path(tmp) / "blockers.json"
            input_path.write_text(mlir, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["stage"], "flat-scf")
        self.assertEqual(
            report["blockers"],
            [
                {"op": "memref.collapse_shape", "count": 1},
                {"op": "memref.reinterpret_cast", "count": 1},
            ],
        )
        self.assertEqual(len(report["locations"]), 2)
        reinterpret = report["locations"][0]
        self.assertEqual(reinterpret["op"], "memref.reinterpret_cast")
        self.assertEqual(reinterpret["line"], 4)
        self.assertEqual(reinterpret["function"], "main")
        self.assertEqual(reinterpret["parents"], ["scf.for"])
        self.assertEqual(reinterpret["result"], "%view")
        self.assertEqual(reinterpret["operands"], ["%arg0"])
        self.assertEqual(reinterpret["users"][0]["op"], "memref.collapse_shape")
        self.assertIn("memref<16xi1> to memref<1x1x4x4xi1", reinterpret["text"])
        collapse = report["locations"][1]
        self.assertEqual(collapse["result"], "%flat")
        self.assertEqual(collapse["operand_definitions"][0]["line"], 4)
        self.assertEqual(collapse["users"][0]["op"], "memref.load")

    def test_reports_float_math_locations_with_provenance(self) -> None:
        mlir = """\
module {
  func.func @main(%arg0: memref<1xi32>, %arg1: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %i = memref.load %arg0[%c0] : memref<1xi32>
    %f = arith.sitofp %i : i32 to f32
    %scale = memref.load %arg1[%c0] : memref<1xf32>
    %scaled = arith.mulf %f, %scale : f32
    %rounded = math.floor %scaled : f32
    %q = arith.fptosi %rounded : f32 to i32
    return
  }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "flat.scf.mlir"
            output_path = Path(tmp) / "blockers.json"
            input_path.write_text(mlir, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            report["float_math_ops"],
            [
                {"op": "arith.fptosi", "count": 1},
                {"op": "arith.mulf", "count": 1},
                {"op": "arith.sitofp", "count": 1},
                {"op": "math.floor", "count": 1},
            ],
        )
        floor = next(
            location
            for location in report["float_math_locations"]
            if location["op"] == "math.floor"
        )
        self.assertEqual(floor["line"], 8)
        self.assertEqual(floor["function"], "main")
        self.assertEqual(floor["result"], "%rounded")
        self.assertEqual(floor["operands"], ["%scaled"])
        self.assertEqual(floor["operand_definitions"][0]["op"], "arith.mulf")
        self.assertEqual(floor["users"][0]["op"], "arith.fptosi")

    def test_uses_nearest_prior_definition_for_reused_ssa_names(self) -> None:
        mlir = """\
module {
  func.func @main() {
    %x = arith.constant 1.0 : f32
    %rounded = math.floor %x : f32
    %use = arith.addf %rounded, %x : f32
    %x = arith.constant 2.0 : f32
    %rounded = math.floor %x : f32
    %later = arith.addf %rounded, %x : f32
    return
  }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "flat.scf.mlir"
            output_path = Path(tmp) / "blockers.json"
            input_path.write_text(mlir, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        floor = report["float_math_locations"][0]
        self.assertEqual(floor["operand_definitions"][0]["line"], 3)
        self.assertEqual([user["line"] for user in floor["users"]], [5])


if __name__ == "__main__":
    unittest.main()
