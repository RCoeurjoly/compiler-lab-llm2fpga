"""Tests for the compiler's legal Kintex-7 BRAM bank geometry."""

import unittest
from pathlib import Path

from scripts.pipeline.lower_fixed_point_model_bram_production import generate_production_kernel

from scripts.pipeline.lower_fixed_point_model_to_calyx import bram_bank_plan, alias_runtime_memories


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

    def test_runtime_alias_keeps_largest_declaration_and_rewrites_uses(self):
        futil = """component main() -> () {
  cells {
    @external q_accumulator_i64 = seq_mem_d1(64, 1280, 11);
    @external k_accumulator_i64 = seq_mem_d1(64, 1280, 11);
    @external c_fc_accumulator_i64 = seq_mem_d1(64, 5120, 13);
  }
  wires { k_accumulator_i64.addr0 = q_accumulator_i64.addr0; }
}
"""
        result = alias_runtime_memories(
            futil,
            {"k_accumulator_i64": "q_accumulator_i64", "q_accumulator_i64": "c_fc_accumulator_i64"},
        )
        self.assertEqual(result.count("@external"), 1)
        self.assertIn("@external c_fc_accumulator_i64 = seq_mem_d1(64, 5120, 13);", result)
        self.assertNotIn("k_accumulator_i64", result)
        self.assertNotIn("q_accumulator_i64", result)

    def test_production_futil_reuses_serial_projection_accumulators(self):
        oracle = Path("artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json")
        artifact = generate_production_kernel(oracle, generation_steps=1)
        self.assertEqual(artifact.futil.count("@external q_accumulator_i64 ="), 1)
        self.assertNotIn("@external k_accumulator_i64 =", artifact.futil)
        self.assertNotIn("@external v_accumulator_i64 =", artifact.futil)
        self.assertNotIn("@external out_accumulator_i64 =", artifact.futil)
        self.assertNotIn("@external c_proj_accumulator_i64 =", artifact.futil)


if __name__ == "__main__":
    unittest.main()
