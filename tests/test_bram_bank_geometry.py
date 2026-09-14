"""Tests for the compiler's legal Kintex-7 BRAM bank geometry."""

import unittest
from pathlib import Path

from scripts.pipeline.lower_fixed_point_model_bram_production import generate_production_kernel

from scripts.pipeline.lower_fixed_point_model_to_calyx import (
    bram_bank_plan,
    alias_runtime_memories,
    narrow_source_memory_words,
    narrow_runtime_memory_words,
)


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
        self.assertEqual(artifact.futil.count("@external q_input_codes_i8 ="), 1)
        self.assertNotIn("@external k_input_codes_i8 =", artifact.futil)
        self.assertNotIn("@external v_output_codes_i8 =", artifact.futil)

    def test_narrow_source_memory_adds_explicit_sign_extension(self):
        futil = """component main() -> () {
  cells {
    @external q_weight_scale_q8_24 = seq_mem_d1(64, 512, 9);
    @external q_output_q16_16 = seq_mem_d1(64, 512, 9);
  }
  wires { use.left = q_weight_scale_q8_24.read_data; }
}
"""
        result = narrow_source_memory_words(futil, ["q_weight_scale_q8_24"])
        self.assertIn("q_weight_scale_q8_24 = seq_mem_d1(32, 512, 9)", result)
        self.assertIn("q_weight_scale_q8_24_wide = std_signext(32, 64);", result)
        self.assertIn("q_weight_scale_q8_24_wide.in = q_weight_scale_q8_24.read_data;", result)
        self.assertIn("use.left = q_weight_scale_q8_24_wide.out;", result)

    def test_narrow_source_memory_supports_sixteen_bit_lut(self):
        futil = """component main() -> () {
  cells {
    @external gelu_lut_q12 = seq_mem_d1(64, 8192, 13);
  }
  wires { use.left = gelu_lut_q12.read_data; }
}
"""
        result = narrow_source_memory_words(futil, ["gelu_lut_q12"], target_width=16)
        self.assertIn("gelu_lut_q12 = seq_mem_d1(16, 8192, 13)", result)
        self.assertIn("gelu_lut_q12_wide = std_signext(16, 64);", result)

    def test_narrow_runtime_memory_adapts_reads_and_writes(self):
        futil = """component main() -> () {
  cells {
    @external attention_score_q8 = seq_mem_d1(64, 6400, 13);
  }
  wires { group g {
    attention_score_q8.addr0 = addr.out;
    attention_score_q8.content_en = 1'd1;
    attention_score_q8.write_data = score.out;
    attention_score_q8.write_en = 1'd1;
    use.left = attention_score_q8.read_data;
  } }
}
"""
        result = narrow_runtime_memory_words(futil, ["attention_score_q8"])
        self.assertIn("attention_score_q8 = seq_mem_d1(32, 6400, 13)", result)
        self.assertIn("attention_score_q8_wide = std_signext(32, 64);", result)
        self.assertIn("attention_score_q8_narrow = std_slice(64, 32);", result)
        self.assertIn("attention_score_q8_narrow.in = score.out;", result)
        self.assertIn("attention_score_q8.write_data = attention_score_q8_narrow.out;", result)
        self.assertIn("use.left = attention_score_q8_wide.out;", result)


if __name__ == "__main__":
    unittest.main()
