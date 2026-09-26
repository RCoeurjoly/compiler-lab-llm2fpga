import unittest

from scripts.pipeline.prune_sv_reachable import prune


class PruneSvReachableTest(unittest.TestCase):
    def test_retains_transitive_instantiations_and_drops_dead_modules(self) -> None:
        source = """
module dead(input logic a); endmodule
module leaf(input logic a); endmodule
module child(input logic a); leaf u_leaf(.a(a)); endmodule
module top(input logic a); child u_child(.a(a)); endmodule
"""
        result, report = prune(source, top="top")
        self.assertEqual(report["input_module_count"], 4)
        self.assertEqual(report["retained_module_count"], 3)
        self.assertNotIn("module dead", result)
        self.assertIn("module child", result)
        self.assertIn("module leaf", result)

    def test_parameterized_instance_is_a_dependency(self) -> None:
        source = """
module leaf #(parameter WIDTH = 1)(input logic a); endmodule
module top(input logic a); leaf #(.WIDTH(8)) u_leaf(.a(a)); endmodule
"""
        _result, report = prune(source, top="top")
        self.assertEqual(report["retained_module_count"], 2)


if __name__ == "__main__":
    unittest.main()
