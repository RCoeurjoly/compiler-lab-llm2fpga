import json
import tempfile
from pathlib import Path
import unittest

from scripts.pipeline.verify_exact_torch_mlir import verify


class ExactTorchMlirGateTest(unittest.TestCase):
    def test_checked_in_receipt_is_complete(self):
        receipt = json.loads(
            (Path(__file__).parents[1] / "artifacts/reference/tinystories-1m-exact-torch-mlir-gate.json").read_text()
        )
        self.assertEqual(receipt["status"], "legalized")
        self.assertEqual(receipt["gemv_calls"], 49)
        self.assertEqual(receipt["raw_torch_operator_calls"], 0)

    def test_verifies_all_compiler_owned_gemv_boundaries(self):
        body = "\n".join(
            '"llm2fpga.serial_gemv"(%a, %b) {mac_order = "ascending_i64_wrap"}'
            for _ in range(49)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.torch.mlir"
            path.write_text(body, encoding="utf-8")
            receipt = verify(path)
        self.assertEqual(receipt["gemv_calls"], 49)
        self.assertEqual(receipt["raw_torch_operator_calls"], 0)


if __name__ == "__main__":
    unittest.main()
