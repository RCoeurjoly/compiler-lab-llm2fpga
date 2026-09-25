import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/simplify_fsm_guarded_or.py"
spec = importlib.util.spec_from_file_location("simplify_fsm_guarded_or", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SimplifyFsmGuardedOrTest(unittest.TestCase):
    def test_complementary_pairs_reduce_to_signal(self) -> None:
        source = (
            "assign fsm_write_en = fsm_out != 3'd3 & alpha_go_out | "
            "fsm_out == 3'd3 & alpha_go_out | "
            "fsm_out == 3'd3 & beta_go_out | fsm_out != 3'd3 & beta_go_out;\n"
        )
        output, count = module.simplify(source)
        self.assertEqual(count, 2)
        self.assertIn("assign fsm_write_en = alpha_go_out | beta_go_out;", output)

    def test_different_signals_are_not_collapsed(self) -> None:
        source = (
            "assign fsm_write_en = fsm_out != 3'd3 & alpha_go_out | "
            "fsm_out == 3'd3 & beta_go_out;\n"
        )
        output, count = module.simplify(source)
        self.assertEqual(count, 0)
        self.assertEqual(output, source)

    def test_many_terms_are_balanced(self) -> None:
        source = "assign fsm_write_en = " + " | ".join(
            f"signal_{index}_go_out" for index in range(8)
        ) + ";\n"
        output, count = module.simplify(source)
        self.assertEqual(count, 0)
        self.assertLess(max(map(len, output.splitlines())), 200)
        self.assertIn("(signal_0_go_out |\n  signal_1_go_out)", output)

    def test_boolean_terms_are_balanced_without_algebraic_rewrite(self) -> None:
        source = (
            "assign fsm_write_en = first_out | fsm_out == 3'd3 & second_out | "
            "fsm_out != 3'd3 & third_out;\n"
        )
        output, count = module.simplify(source)
        self.assertEqual(count, 0)
        self.assertIn("((first_out |\n  fsm_out == 3'd3 & second_out)", output)

    def test_long_assignment_is_balanced(self) -> None:
        source = "assign signal = " + " | ".join(
            f"term_{index}" for index in range(400)
        ) + ";\n"
        output, count = module.balance_large_assignments(source, minimum_bytes=100)
        self.assertEqual(count, 1)
        self.assertLess(max(map(len, output.splitlines())), 200)


if __name__ == "__main__":
    unittest.main()
