import unittest

from scripts.pipeline.legalize_external_memory_latency import (
    legalize_external_memory_latency,
)


SOURCE = '''import "primitives/core.futil";
import "primitives/memories/seq.futil";
component main(@go go: 1) -> (@done done: 1) {
  cells {
    @external weights = seq_mem_d1(64, 16, 4);
    local = seq_mem_d1(64, 16, 4);
  }
}
'''


class ExternalMemoryLatencyLegalizerTest(unittest.TestCase):
    def test_rewrites_only_selected_external_memory_and_adds_native_import(self):
        result, report = legalize_external_memory_latency(SOURCE, ["weights"])
        self.assertIn('import "primitives/memories/dyn.futil";', result)
        self.assertIn("@external weights = dyn_mem_d1(64, 16, 4);", result)
        self.assertIn("local = seq_mem_d1(64, 16, 4);", result)
        self.assertEqual(report["rewritten"], ["weights"])

    def test_is_idempotent_for_existing_dynamic_memory(self):
        dynamic = SOURCE.replace("seq_mem_d1(64, 16, 4);", "dyn_mem_d1(64, 16, 4);", 1)
        result, report = legalize_external_memory_latency(dynamic, ["weights"])
        self.assertEqual(result, dynamic)
        self.assertEqual(report["rewritten"], [])

    def test_missing_or_unannotated_memory_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            legalize_external_memory_latency(SOURCE, ["missing"])
        with self.assertRaisesRegex(ValueError, "missing"):
            legalize_external_memory_latency(SOURCE, ["local"])


if __name__ == "__main__":
    unittest.main()
