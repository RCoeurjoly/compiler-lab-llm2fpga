import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/pipeline/extract_mlir_dataflow.py"
spec = importlib.util.spec_from_file_location("extract_mlir_dataflow", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ExtractDataflowTest(unittest.TestCase):
    def test_preserves_order_operands_and_edges(self):
        graph = module.extract(
            '  %a = "test.const"() : i64\n'
            '  %b = "test.add"(%a, %a) : (i64, i64) -> i64\n',
            "fixture",
        )
        self.assertEqual(graph["node_count"], 2)
        self.assertEqual(graph["edge_count"], 2)
        self.assertEqual(graph["nodes"][1]["operands"], ["%a", "%a"])
        self.assertEqual(graph["operation_counts"]["test.add"], 1)

    def test_graph_hash_changes_when_dataflow_changes(self):
        first = module.extract('%a = "x"() : i64\n%b = "y"(%a) : i64 -> i64\n', "x")
        second = module.extract('%a = "x"() : i64\n%b = "y"(%missing) : i64 -> i64\n', "x")
        self.assertNotEqual(first["graph_sha256"], second["graph_sha256"])

    def test_rejects_text_without_result_operations(self):
        with self.assertRaisesRegex(ValueError, "no SSA"):
            module.extract("module {}\n", "empty")


if __name__ == "__main__":
    unittest.main()
