"""Compare compiler payload-reset optimization with the frozen resetful cell.

The reference is the compiler-generated cell from static-counter-reviewed.sv,
not kev-gpt RTL. Invalid request addresses may differ; valid transactions,
completion, and returned data must not. An incorrect capture enable or reset
flush must produce a counterexample.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em

MITER = r'''
module miter(input clk, reset, content_en, write_en, ext_req_ready,
             ext_rsp_valid, input [3:0] addr0, input [63:0] ext_rsp_data);
  wire av, bv, ad, bd;
  wire [31:0] aa, ba;
  wire [7:0] ar, br;
  wire [13:0] ast, bst;
  seq_mem_d1_external #(.WIDTH(8), .SIZE(16), .IDX_SIZE(4),
      .EXT_BASE_ADDR(19)) a(.clk(clk), .reset(reset), .addr0(addr0),
      .content_en(content_en), .write_en(write_en), .write_data(8'b0),
      .done(ad), .read_data(ar), .ext_req_valid(av), .ext_req_addr(aa),
      .ext_req_ready(ext_req_ready), .ext_rsp_valid(ext_rsp_valid),
      .ext_rsp_data(ext_rsp_data), .proof_state(ast));
  resetful_reference #(.WIDTH(8), .SIZE(16), .IDX_SIZE(4),
      .EXT_BASE_ADDR(19)) b(.clk(clk), .reset(reset), .addr0(addr0),
      .content_en(content_en), .write_en(write_en), .write_data(8'b0),
      .done(bd), .read_data(br), .ext_req_valid(bv), .ext_req_addr(ba),
      .ext_req_ready(ext_req_ready), .ext_rsp_valid(ext_rsp_valid),
      .ext_rsp_data(ext_rsp_data), .proof_state(bst));
  reg initialized = 0;
  always @(posedge clk) initialized <= 1;
  always @* begin
    if (!initialized) assume(reset);
    if (initialized) begin
      assert(av == bv);
      assert(ad == bd);
      assert(ar == br);
      assert(ast == bst);
      if (av) assert(aa == ba);
    end
  end
endmodule
'''


class PayloadResetEquivalenceTest(unittest.TestCase):
    def test_valid_transactions_match_resetful_reference(self):
        reference = Path(__file__).parent / "rtl/external_memory_resetful_reference.sv"
        with tempfile.TemporaryDirectory(prefix="payload-reset-equivalence-") as tmp:
            path = Path(tmp)
            def observe_state(source):
                # Test-only observer: strengthen induction with unchanged
                # control/index state, without constraining environment inputs.
                return source.replace(
                    "input wire [63:0] ext_rsp_data",
                    "output wire [13:0] proof_state, input wire [63:0] ext_rsp_data",
                ).replace(
                    "endmodule",
                    "assign proof_state = {pending, request_queued, response_ready, "
                    "request_index, response_index, response_byte_offset};\nendmodule",
                )
            (path / "miter.sv").write_text(
                observe_state(em._EXTERNAL_MODULE) + observe_state(reference.read_text()) + MITER)
            result = subprocess.run(
                ["yosys", "-Q", "-T", "-p",
                 "read_verilog -formal -sv miter.sv; prep -top miter -flatten; chformal -lower; "
                 "sat -seq 12 -tempinduct -maxsteps 24 -set-assumes "
                 "-prove-asserts -verify"],
                cwd=path, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Induction step proven: SUCCESS", result.stdout)


if __name__ == "__main__":
    unittest.main()
