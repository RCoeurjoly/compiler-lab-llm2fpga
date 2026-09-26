import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.annotate_flat_scf_phase_abi import main


class AnnotateFlatScfPhaseAbiTest(unittest.TestCase):
    def test_injects_authenticated_module_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.mlir").write_text("module {\n}\n")
            (root / "abi.json").write_text(
                json.dumps(
                    {
                        "schema": "rc-serving-w4a8-compiler-phase-abi-v1",
                        "phases": [
                            {"name": "prefill-8"},
                            {"name": "decode-8"},
                            {"name": "decode-9"},
                        ],
                    }
                )
            )
            import sys

            old = sys.argv
            try:
                sys.argv = [
                    "annotate",
                    str(root / "input.mlir"),
                    str(root / "abi.json"),
                    str(root / "output.mlir"),
                    str(root / "receipt.json"),
                ]
                self.assertEqual(main(), 0)
            finally:
                sys.argv = old
            output = (root / "output.mlir").read_text()
            self.assertIn('llm2fpga.phase_abi_schema = "rc-serving-w4a8-compiler-phase-abi-v1"', output)
            self.assertIn("prefill-8,decode-8,decode-9", output)
            self.assertEqual(json.loads((root / "receipt.json").read_text())["status"], "ok")


if __name__ == "__main__":
    unittest.main()
