"""Tests for the compiler's legal Kintex-7 BRAM bank geometry."""

import unittest
from pathlib import Path

from scripts.pipeline.lower_fixed_point_model_bram_production import generate_production_kernel

from scripts.pipeline.lower_fixed_point_model_to_calyx import bram_bank_plan


class BramBankGeometryTests(unittest.TestCase):
    def test_wide_non_power_depth_is_banked_into_legal_ram_shapes(self):
        plan = bram_bank_plan(64, 1280)
        self.assertEqual(plan["banks"], 3)
        self.assertEqual(plan["physical_width"], 72)
        self.assertEqual(plan["physical_depth"], 512)
        self.assertEqual(plan["logical_words_per_bank"], 512)

    def test_eight_bit_deep_memory_uses_nine_bit_bram_lane(self):
        plan = bram_bank_plan(8, 5120)
        self.assertEqual(plan["banks"], 2)
        self.assertEqual(plan["physical_width"], 9)
        self.assertEqual(plan["physical_depth"], 4096)
        self.assertEqual(plan["logical_words_per_bank"], 4096)

    def test_invalid_width_is_rejected(self):
        with self.assertRaises(ValueError):
            bram_bank_plan(73, 512)

    def test_authenticated_production_provenance_publishes_runtime_plan(self):
        oracle = Path("artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json")
        artifact = generate_production_kernel(oracle, generation_steps=16)
        plans = artifact.provenance["runtime_bram_bank_plan"]
        self.assertIn("c_fc_output_codes_i8", plans)
        self.assertEqual(plans["c_fc_output_codes_i8"]["banks"], 2)
        for plan in plans.values():
            self.assertLessEqual(plan["physical_width"], 72)
            self.assertIn(plan["physical_width"], (1, 2, 4, 9, 18, 36, 72))
            self.assertIn(plan["physical_depth"], (512, 1024, 2048, 4096, 8192, 16384, 32768))


if __name__ == "__main__":
    unittest.main()
