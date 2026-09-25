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

    def test_current_calyx_names_and_guard_aliases(self) -> None:
        source = """
module main(
  input logic clk,
  output logic done
);
logic [3:0] fsm_out;
wire _guard0 = fsm_out == 4'd0;
wire _guard1 = fsm_out == 4'd1;
wire _guard2 = _guard0 & ready;
wire fsm_in;
wire fsm_write_en;
assign fsm_in = _guard2 ? 4'd1 : _guard1 ? 4'd0 : 4'd0;
assign fsm_write_en = _guard0 | _guard1;
endmodule
module helper(input logic clk, output logic out);
assign out = 1'b0;
endmodule
"""
        transformed, _shared = module.transform(
            source, hierarchical_state_decodes=True
        )
        self.assertIn("case (fsm_out)", transformed)
        self.assertIn("fsm_in = 4'd1", transformed)
        self.assertNotIn("assign fsm_in =", transformed)

    def test_opaque_guard_chain_uses_priority_case(self) -> None:
        source = """
module main(input logic clk, output logic done);
logic [3:0] fsm_out;
wire _guard0 = ready;
wire _guard1 = finished;
wire fsm_in;
wire fsm_write_en;
assign fsm_in = _guard0 ? 4'd1 : _guard1 ? 4'd2 : 4'd0;
assign fsm_write_en = _guard0 | _guard1;
endmodule
"""
        transformed, _shared = module.transform(source)
        self.assertIn("case (1'b1)", transformed)
        self.assertIn("(_guard0): fsm_in = 4'd1", transformed)


if __name__ == "__main__":
    unittest.main()
