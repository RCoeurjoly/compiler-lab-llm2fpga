import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/run_rc_serving_w4a8_sv.py"
spec = importlib.util.spec_from_file_location("run_rc_serving_w4a8_sv", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class RcServingW4A8SvSimTest(unittest.TestCase):
    def test_flat_scf_abi_preserves_semantic_argument_order(self) -> None:
        mlir = """
        module {
          func.func @main(%arg0: memref<1xi64>, %arg1: memref<2x2xi8>,
                          %arg2: memref<1x1x6xf32>, %arg3: memref<1x1x9x2xf32>) {
            return
          }
        }
        """
        abi = module.parse_flat_scf_abi(mlir)
        self.assertEqual(
            [(item.number, item.shape, item.width) for item in abi],
            [(0, (1,), 64), (1, (2, 2), 8), (2, (1, 1, 6), 32),
             (3, (1, 1, 9, 2), 32)],
        )

    def test_decode_phase_classifies_five_outputs_after_32_inputs(self) -> None:
        roles = module.phase_roles("decode-8", semantic_port_count=37)
        self.assertEqual(roles.inputs, tuple(range(32)))
        self.assertEqual(roles.outputs, tuple(range(32, 37)))
        self.assertEqual(roles.logits, 32)
        self.assertEqual(roles.cache_outputs, (33, 34, 35, 36))

    def test_prefill_phase_classifies_five_outputs_after_28_inputs(self) -> None:
        roles = module.phase_roles("prefill-8", semantic_port_count=33)
        self.assertEqual(roles.inputs, tuple(range(28)))
        self.assertEqual(roles.outputs, tuple(range(28, 33)))


if __name__ == "__main__":
    unittest.main()
