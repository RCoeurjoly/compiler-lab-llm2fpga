import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PATTERN_DIR = REPO_ROOT / "patterns" / "embedding"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class EmbeddingPatternTest(unittest.TestCase):
    def test_w4a8_core_embedding_is_int8_lookup(self) -> None:
        if importlib.util.find_spec("torch") is None:
            self.skipTest("PyTorch is required for embedding pattern behavior")

        adapter = load_module(
            "embedding_w4a8_core_adapter",
            PATTERN_DIR / "adapter_w4a8_core.py",
        )

        model = adapter.build_model()
        example_inputs = adapter.example_inputs()
        actual = model(*example_inputs)
        expected = model.weight_i8[example_inputs[0]]

        self.assertEqual(model.training, False)
        self.assertEqual(len(example_inputs), 1)
        self.assertEqual(tuple(example_inputs[0].shape), (1, 2))
        self.assertEqual(str(example_inputs[0].dtype), "torch.int64")
        self.assertEqual(tuple(actual.shape), (1, 2, 4))
        self.assertEqual(str(actual.dtype), "torch.int8")
        self.assertTrue(actual.equal(expected))

    def test_adapter_avoids_float_quantization_scaffolding(self) -> None:
        adapter = (PATTERN_DIR / "adapter_w4a8_core.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("torch.int8", adapter)
        self.assertIn("def export_program", adapter)
        self.assertNotIn("prepare_pt2e", adapter)
        self.assertNotIn("convert_pt2e", adapter)
        self.assertNotIn("quantize_per_tensor", adapter)


if __name__ == "__main__":
    unittest.main()
