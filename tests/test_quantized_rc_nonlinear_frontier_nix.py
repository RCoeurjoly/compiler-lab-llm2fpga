import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QuantizedRcNonlinearFrontierNixTest(unittest.TestCase):
    def test_frontier_package_uses_frozen_rc_and_named_routes(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        matrix = (
            ROOT / "scripts" / "pipeline" / "run_quantized_rc_nonlinear_matrix.py"
        ).read_text(encoding="utf-8")
        self.assertIn("quantizedRcNonlinearSlices", flake)
        self.assertIn("quantizedRcNonlinearFrontier", flake)
        self.assertIn('"tinystories-w8a8-rc-nonlinear-lowering-frontier"', flake)
        self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", flake)
        self.assertIn("extract_quantized_rc_nonlinear_slices.py", flake)
        self.assertIn("run_quantized_rc_nonlinear_matrix.py", flake)
        self.assertIn("render_quantized_rc_nonlinear_frontier.py", flake)
        self.assertIn("--torch-backend-to-tosa-backend-pipeline", matrix)
        self.assertIn("--tosa-to-linalg-pipeline", matrix)
        self.assertNotIn("lower-scout-math-for-calyx", matrix)


if __name__ == "__main__":
    unittest.main()
