import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PATTERN_DIR = REPO_ROOT / "patterns" / "linear"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LinearPatternTest(unittest.TestCase):
    def test_pattern_files_exist(self) -> None:
        for filename in ["model.py", "inputs.py", "reference.py", "metadata.json"]:
            self.assertTrue((PATTERN_DIR / filename).is_file(), filename)

    def test_pattern_is_deterministic_fp32_linear(self) -> None:
        if importlib.util.find_spec("torch") is None:
            self.skipTest("PyTorch is required for linear pattern behavior")

        model_module = load_module("linear_pattern_model", PATTERN_DIR / "model.py")
        inputs_module = load_module("linear_pattern_inputs", PATTERN_DIR / "inputs.py")
        reference_module = load_module(
            "linear_pattern_reference", PATTERN_DIR / "reference.py"
        )

        model = model_module.build_model()
        example_inputs = inputs_module.example_inputs()
        expected = reference_module.expected_output()
        actual = model(*example_inputs)

        self.assertEqual(model.training, False)
        self.assertEqual(len(example_inputs), 1)
        self.assertEqual(tuple(example_inputs[0].shape), (1, 8))
        self.assertEqual(str(example_inputs[0].dtype), "torch.float32")
        self.assertEqual(tuple(actual.shape), (1, 4))
        self.assertEqual(str(actual.dtype), "torch.float32")
        self.assertTrue(actual.equal(expected))

    def test_metadata_declares_pipeline_applied_w4a8_target(self) -> None:
        metadata = json.loads((PATTERN_DIR / "metadata.json").read_text())

        self.assertEqual(metadata["name"], "linear")
        self.assertEqual(metadata["source_dtype"], "fp32")
        self.assertEqual(metadata["target"], "w4a8")
        self.assertEqual(metadata["expected_op_family"], "linear")
        self.assertEqual(metadata["quantization"]["activation_bits"], 8)
        self.assertEqual(metadata["quantization"]["weight_bits"], 4)

    def test_pattern_is_registered_in_existing_pipeline(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")

        self.assertIn('"pattern-linear-fp32"', models)
        self.assertIn('"pattern-linear-w4a8"', models)
        self.assertIn('type = "pattern";', models)
        self.assertIn("../patterns/linear/adapter.py", models)
        self.assertIn("../patterns/linear/adapter_w4a8.py", models)
        self.assertIn("TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4", models)
        self.assertIn("TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8", models)


if __name__ == "__main__":
    unittest.main()
