import importlib.util
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/optimize_calyx_fsm_decode.py"
spec = importlib.util.spec_from_file_location("optimize_calyx_fsm_decode", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class OptimizeCalyxFsmDecodeTest(unittest.TestCase):
    def test_large_flat_next_state_chain_is_bounded(self) -> None:
        terms = [
            f"(fsm0_out == 11'd{state} & guard_{state}) ? 11'd{state + 1} : "
            for state in range(2000)
        ]
        source = (
            "logic [10:0] fsm0_out;\n"
            "assign fsm0_in = " + "".join(terms) + "11'd0;\n"
            "assign fsm0_write_en = "
            + " | ".join(
                f"(fsm0_out == 11'd{state} & guard_{state})"
                for state in range(2000)
            )
            + ";\n"
        )
        started = time.monotonic()
        transformed, _shared = module.transform(
            source, hierarchical_state_decodes=True
        )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertIn("case (fsm0_out)", transformed)
        self.assertIn("11'd1999", transformed)


if __name__ == "__main__":
    unittest.main()
