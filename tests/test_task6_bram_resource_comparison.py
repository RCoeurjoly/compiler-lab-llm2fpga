"""Native-cell counts must follow only instantiated design hierarchy."""
import unittest

from scripts.pipeline.rebuild_task6_bram_resource_comparison import hierarchical_counts


class HierarchicalResourceCountsTest(unittest.TestCase):
    def test_counts_instantiated_cells_and_skips_uninstantiated_modules(self) -> None:
        design = {"modules": {
            "top": {"cells": {
                "first": {"type": "child"},
                "second": {"type": "child"},
                "top_lut": {"type": "LUT6"},
            }},
            "child": {"cells": {"ff": {"type": "FDRE"}, "lut": {"type": "LUT6"}}},
            "unused": {"cells": {"noise": {"type": "RAMB36E1"}}},
            "LUT6": {"attributes": {"blackbox": "00000000000000000000000000000001"},
                     "cells": {"internal": {"type": "FDRE"}}},
        }}
        self.assertEqual(hierarchical_counts(design, "top"), {"FDRE": 2, "LUT6": 3})

    def test_rejects_recursive_hierarchy(self) -> None:
        design = {"modules": {"top": {"cells": {"loop": {"type": "top"}}}}}
        with self.assertRaisesRegex(ValueError, "recursive design hierarchy"):
            hierarchical_counts(design, "top")


if __name__ == "__main__":
    unittest.main()
