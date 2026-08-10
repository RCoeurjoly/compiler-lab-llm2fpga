import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.fix_sv_synthesis_frontend import normalize


class SynthesisFrontendFixTests(unittest.TestCase):
    def test_moves_request_declaration_before_hardfloat_instance(self):
        source = """
module std_divSqrtFN(input go, output done);
  divSqrtRecFNToRaw_small u(.inValid(llm2fpga_request));
  wire llm2fpga_request = go;
endmodule
"""
        output, receipt = normalize(source)
        self.assertIn("wire llm2fpga_request;", output)
        self.assertIn("assign llm2fpga_request = go;", output)
        self.assertLess(output.index("wire llm2fpga_request;"), output.index(".inValid"))
        self.assertEqual(receipt["request_declaration_repairs"], 1)

    def test_removes_only_duplicate_sqrtopout_wire(self):
        source = """
module divSqrtRecFN_small(output sqrtOpOut);
  wire sqrtOpOut;
endmodule
module other(output sqrtOpOut);
  wire sqrtOpOut;
endmodule
"""
        output, receipt = normalize(source)
        self.assertEqual(output.count("wire sqrtOpOut;"), 1)
        self.assertEqual(receipt["duplicate_sqrtopout_repairs"], 1)

    def test_is_idempotent(self):
        source = "module x; endmodule\n"
        output, first = normalize(source)
        again, second = normalize(output)
        self.assertEqual(again, output)
        self.assertEqual(first["repair_count"], 0)
        self.assertEqual(second["repair_count"], 0)

    def test_removes_generated_onehot_fatal_assertion_blocks(self):
        source = """
module main;
  always_comb begin
    if (~$onehot0({a, b})) begin
      $fatal(2, "multiple");
    end
  end
  assign y = a;
endmodule
"""
        output, receipt = normalize(source)
        self.assertNotIn("$onehot0", output)
        self.assertNotIn("$fatal", output)
        self.assertIn("assign y = a;", output)
        self.assertEqual(receipt["assertion_block_repairs"], 1)


if __name__ == "__main__":
    unittest.main()
