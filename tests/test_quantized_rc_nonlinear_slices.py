import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "scripts" / "pipeline" / "extract_quantized_rc_nonlinear_slices.py"

TORCH_SOURCE = """module {
  func.func @main(%arg0: !torch.vtensor<[1,8,2],si8>) {
    %c3 = torch.constant.int 3
    %dq0 = torch.aten.dequantize.tensor %arg0 : !torch.vtensor<[1,8,2],!torch.qint8> -> !torch.vtensor<[1,8,2],f32>
    %max = torch.aten.max.dim %dq0, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.int, !torch.bool -> !torch.vtensor<[1,8,1],f32>, !torch.vtensor<[1,8,1],si64>
    %sub = torch.aten.sub.Tensor %dq0, %max, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.vtensor<[1,8,1],f32>, !torch.float -> !torch.vtensor<[1,8,2],f32>
    %exp = torch.aten.exp %sub : !torch.vtensor<[1,8,2],f32> -> !torch.vtensor<[1,8,2],f32>
    %sum = torch.aten.sum.dim_IntList %exp, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.list<int>, !torch.bool, !torch.none -> !torch.vtensor<[1,8,1],f32>
    %softmax = torch.aten.div.Tensor %exp, %sum : !torch.vtensor<[1,8,2],f32>, !torch.vtensor<[1,8,1],f32> -> !torch.vtensor<[1,8,2],f32>
    %pow = torch.aten.pow.Tensor_Scalar %dq0, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.int -> !torch.vtensor<[1,8,2],f32>
    %tanh = torch.aten.tanh %pow : !torch.vtensor<[1,8,2],f32> -> !torch.vtensor<[1,8,2],f32>
    %gelu_q = torch.aten.quantize_per_tensor %tanh, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.float, !torch.int, !torch.dtype -> !torch.vtensor<[1,8,2],!torch.qint8>
    %mean = torch.aten.sum.dim_IntList %dq0, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.list<int>, !torch.bool, !torch.none -> !torch.vtensor<[1,8,1],f32>
    %div = torch.aten.div.Scalar %mean, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.float -> !torch.vtensor<[1,8,1],f32>
    %add = torch.aten.add.Scalar %div, %c3, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.float, !torch.float -> !torch.vtensor<[1,8,1],f32>
    %rsqrt = torch.aten.rsqrt %add : !torch.vtensor<[1,8,1],f32> -> !torch.vtensor<[1,8,1],f32>
    %broadcast = torch.aten.broadcast_to %rsqrt, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.list<int> -> !torch.vtensor<[1,8,2],f32>
    %layernorm_q = torch.aten.quantize_per_tensor %broadcast, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.float, !torch.int, !torch.dtype -> !torch.vtensor<[1,8,2],!torch.qint8>
    return
  }
}
"""

FLAT_SCF_SOURCE = """module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %value = memref.load %input[%c0] : memref<1xf32>
    %exp = math.exp %value : f32
    %pow = math.fpowi %value, %c3_i64 : f32, i64
    %tanh = math.tanh %value : f32
    %rsqrt = math.rsqrt %value : f32
    memref.store %exp, %output[%c0] : memref<1xf32>
    return
  }
}
"""


class QuantizedRcNonlinearSlicesTest(unittest.TestCase):
    def run_extract(self, torch_source: str = TORCH_SOURCE) -> tuple[dict, dict, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        torch_path = root / "model.torch.mlir"
        flat_path = root / "flat.scf.mlir"
        out = root / "out"
        torch_path.write_text(torch_source, encoding="utf-8")
        flat_path.write_text(FLAT_SCF_SOURCE, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(EXTRACT),
                "--torch-mlir",
                str(torch_path),
                "--flat-scf",
                str(flat_path),
                "--model-key",
                "tinystories-w8a8-rc-study-mask9-vocab6-width2",
                "--out-dir",
                str(out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return (
            json.loads((out / "slices.json").read_text(encoding="utf-8")),
            json.loads(
                (out / "primitive-observations.json").read_text(encoding="utf-8")
            ),
            out,
        )

    def test_preserves_source_hash_family_ranges_and_external_values(self) -> None:
        slices, primitive, out = self.run_extract()

        self.assertEqual(
            slices["source"]["sha256"],
            hashlib.sha256(TORCH_SOURCE.encode()).hexdigest(),
        )
        self.assertEqual(
            {entry["family"] for entry in slices["composites"]},
            {"attention-softmax", "tanh-gelu", "layernorm"},
        )
        self.assertEqual(
            primitive["op_counts"],
            {"math.exp": 1, "math.fpowi": 1, "math.rsqrt": 1, "math.tanh": 1},
        )
        for entry in slices["composites"]:
            fragment = out / entry["fragment"]
            self.assertTrue(fragment.is_file())
            text = fragment.read_text(encoding="utf-8")
            self.assertIn("non-executable provenance fragment", text)
            self.assertIn("source_sha256:", text)
            self.assertTrue(entry["retained_external_values"])
            self.assertGreaterEqual(entry["source_range"][0], 1)
            self.assertFalse(entry["executable"])
            self.assertFalse(entry["semantic_replacement"])

    def test_rejects_source_without_all_required_families(self) -> None:
        with self.assertRaises(AssertionError):
            self.run_extract(TORCH_SOURCE.replace("torch.aten.tanh", "torch.aten.sin"))

    def test_primitive_mrcs_match_the_observed_scalar_signatures(self) -> None:
        expected = {
            "calyx-math-tanh/input.mlir": "math.tanh %value : f32",
            "calyx-math-fpowi-cube/input.mlir": "math.fpowi %value, %c3_i64 : f32, i64",
            "calyx-math-sqrt/input.mlir": "math.sqrt %value : f32",
        }
        for relative_path, signature in expected.items():
            path = ROOT / "reproducers" / relative_path
            self.assertTrue(path.is_file(), path)
            source = path.read_text(encoding="utf-8")
            self.assertIn(signature, source)


if __name__ == "__main__":
    unittest.main()
