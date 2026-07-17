from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("domain", ROOT / "scripts/pipeline/characterize_rc_softmax_exp_domain.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["domain"] = MODULE
SPEC.loader.exec_module(MODULE)


class DomainTests(unittest.TestCase):
    def test_lexical_base_six(self):
        self.assertEqual(MODULE.context_from_index(0), [0] * 8)
        self.assertEqual(MODULE.context_from_index(1), [0, 0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(MODULE.context_from_index(6), [0, 0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(MODULE.context_from_index(6**8 - 1), [5] * 8)
        with self.assertRaisesRegex(ValueError, "outside"):
            MODULE.context_from_index(6**8)

    def test_merge_requires_complete_adjacent_coverage(self):
        def shard(start, stop, analyzer="a" * 64):
            return {"receipt": {"x": 1, "analyzer_sha256": analyzer},
                    "enumeration": {"start": start, "stop": stop},
                    "sites": {"softmax": {"input_value_count": 1,
                      "derived_pre_exp_value_count": 1,
                      "derived_pre_exp_positive_count": 0,
                      "derived_pre_exp_nan_count": 0,
                      "derived_pre_exp_infinity_count": 0,
                      "input_bits": ["0x00000000"],
                      "derived_pre_exp_bits": ["0x00000000"],
                      "boundary": {}}}}
        old = MODULE.TOTAL_CONTEXTS
        MODULE.TOTAL_CONTEXTS = 6
        try:
            result = MODULE.merge_shards([shard(3, 6), shard(0, 3)])
            self.assertTrue(result["coverage"]["complete"])
            with self.assertRaisesRegex(ValueError, "coverage"):
                MODULE.merge_shards([shard(0, 2), shard(3, 6)])
        finally:
            MODULE.TOTAL_CONTEXTS = old


if __name__ == "__main__":
    unittest.main()
