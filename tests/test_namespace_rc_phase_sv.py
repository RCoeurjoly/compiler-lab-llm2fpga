import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.namespace_rc_phase_sv import namespace_modules


SOURCE = '''// helper and main_1 must stay in this comment
module helper #(parameter W = 8) (input [W-1:0] a, output [W-1:0] y);
  assign y = a;
endmodule
module main_1 (input [7:0] a, output [7:0] y);
  wire helper;
  helper #(.W(8)) instance (.a(a), .y(y));
endmodule
'''


class NamespaceModulesTests(unittest.TestCase):
    def test_renames_definitions_and_parameterized_instance_only(self):
        output, receipt = namespace_modules(SOURCE, "prefill8")
        self.assertIn("module prefill8__helper #(", output)
        self.assertIn("module prefill8__main_1 (", output)
        self.assertIn("prefill8__helper #(.W(8)) instance", output)
        self.assertIn("wire helper;", output)
        self.assertIn("// helper and main_1 must stay in this comment", output)
        self.assertEqual(receipt["modules"], {"helper": "prefill8__helper", "main_1": "prefill8__main_1"})
        self.assertEqual(receipt["input_sha256"], hashlib.sha256(SOURCE.encode()).hexdigest())
        self.assertEqual(receipt["output_sha256"], hashlib.sha256(output.encode()).hexdigest())

    def test_same_helper_name_in_two_phases_does_not_collide(self):
        other = SOURCE.replace("assign y = a;", "assign y = ~a;")
        first, _ = namespace_modules(SOURCE, "prefill8")
        second, _ = namespace_modules(other, "decode8")
        self.assertIn("module prefill8__helper", first)
        self.assertIn("module decode8__helper", second)
        self.assertNotIn("module prefill8__helper", second)

    def test_two_phases_elaborate_together(self):
        if shutil.which("yosys") is None:
            self.skipTest("yosys unavailable outside Nix")
        first, _ = namespace_modules(SOURCE, "prefill8")
        second, _ = namespace_modules(SOURCE.replace("assign y = a;", "assign y = ~a;"), "decode8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "phases.sv"
            path.write_text(first + "\n" + second)
            run = subprocess.run(
                ["yosys", "-Q", "-T", "-p", f"read_verilog -sv {path}; hierarchy -check -top prefill8__main_1"],
                text=True, capture_output=True, timeout=30, check=False,
            )
        self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-2000:])

    def test_rejects_duplicate_definition(self):
        with self.assertRaisesRegex(ValueError, "duplicate module"):
            namespace_modules(SOURCE + "\nmodule helper; endmodule\n", "prefill8")

    def test_rejects_missing_main_and_unsupported_identifier(self):
        with self.assertRaisesRegex(ValueError, "main_1"):
            namespace_modules("module helper; endmodule\n", "prefill8")
        with self.assertRaisesRegex(ValueError, "prefix"):
            namespace_modules(SOURCE, "bad-prefix")


if __name__ == "__main__":
    unittest.main()
