import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PATTERN_DIR = REPO_ROOT / "patterns" / "layernorm"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LayerNormPatternTest(unittest.TestCase):
    def test_w4a8_core_layernorm_has_integer_boundary(self) -> None:
        if importlib.util.find_spec("torch") is None:
            self.skipTest("PyTorch is required for layernorm pattern behavior")

        adapter = load_module(
            "layernorm_w4a8_core_adapter",
            PATTERN_DIR / "adapter_w4a8_core.py",
        )

        model = adapter.build_model()
        example_inputs = adapter.example_inputs()
        actual = model(*example_inputs)

        self.assertEqual(model.training, False)
        self.assertEqual(len(example_inputs), 1)
        self.assertEqual(tuple(example_inputs[0].shape), (1, 1, 4))
        self.assertEqual(str(example_inputs[0].dtype), "torch.int8")
        self.assertEqual(tuple(actual.shape), (1, 1, 4))
        self.assertEqual(str(actual.dtype), "torch.int8")

    def test_adapter_uses_explicit_integer_layernorm_math(self) -> None:
        adapter = (PATTERN_DIR / "adapter_w4a8_core.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("torch.int8", adapter)
        self.assertIn("torch.int32", adapter)
        self.assertIn("gamma_i32", adapter)
        self.assertIn("torch.bitwise_right_shift", adapter)
        self.assertIn("inv_std_base_i32", adapter)
        self.assertIn("inv_std_min_i32", adapter)
        self.assertIn("def export_program", adapter)
        self.assertNotIn("gamma_i16", adapter)
        self.assertNotIn("gamma_i16.to(torch.int32)", adapter)
        self.assertNotIn("torch.nn.LayerNorm", adapter)
        self.assertNotIn("torch.rsqrt", adapter)
        self.assertNotIn("prepare_pt2e", adapter)
        self.assertNotIn("convert_pt2e", adapter)

    def test_adapter_avoids_lane_extraction_slices(self) -> None:
        adapter = (PATTERN_DIR / "adapter_w4a8_core.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("torch.gather", adapter)
        self.assertIn("torch.sum", adapter)
        self.assertIn("inv_std_base_i32", adapter)
        self.assertNotIn("[:, :, 0:1]", adapter)
        self.assertNotIn("[:, :, 1:2]", adapter)
        self.assertNotIn("[:, :, 2:3]", adapter)
        self.assertNotIn("[:, :, 3:4]", adapter)

    def test_pattern_is_registered_in_existing_pipeline(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn('"pattern-layernorm-w4a8-core"', models)
        self.assertIn("../patterns/layernorm/adapter_w4a8_core.py", models)
        self.assertIn(
            'alias = "pattern-layernorm-w4a8-core-via-tosa-no-handshake"',
            flake,
        )
        self.assertIn('model = "pattern-layernorm-w4a8-core"', flake)
        self.assertIn('"tosa"', flake)
        self.assertIn('"flat-scf"', flake)


if __name__ == "__main__":
    unittest.main()
