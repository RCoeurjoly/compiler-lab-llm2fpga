"""Structural and semantic gates for the BRAM-only production generator."""
from __future__ import annotations

import importlib.util
import json
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/lower_fixed_point_model_bram_production.py"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json"


def load_module():
    if not SCRIPT.is_file():
        raise AssertionError("missing BRAM production generator")
    spec = importlib.util.spec_from_file_location("bram_production", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BramProductionTest(unittest.TestCase):
    @staticmethod
    def _signed(value: int, width: int) -> int:
        value &= (1 << width) - 1
        return value - (1 << width) if value & (1 << (width - 1)) else value

    def test_production_narrow_products_preserve_signed_64_contract(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        self.assertEqual(artifact.futil.count("std_smult_pipe(40)"), 14)
        self.assertEqual(artifact.futil.count("std_smult_pipe(48)"), 7)
        rng = random.Random(0x1A2B3C)
        cases = [(-128, -105952), (-128, 105952), (127, -105952), (127, 105952)]
        cases += [(rng.randint(-128, 127), rng.randint(-105952, 105952)) for _ in range(256)]
        for code, scale in cases:
            reference = self._signed(code * scale, 64)
            narrowed = self._signed(self._signed(code, 40) * self._signed(scale, 40), 40)
            self.assertEqual(self._signed(narrowed, 64), reference)
            activation = narrowed
            reference_mac = self._signed(activation * code, 64)
            narrowed_mac = self._signed(self._signed(activation, 48) * self._signed(code, 48), 48)
            self.assertEqual(self._signed(narrowed_mac, 64), reference_mac)

    def test_audit_generator_futil_remains_byte_identical(self):
        module = load_module()
        self.assertEqual(
            module.base.generate_model_kernel(ORACLE).provenance["futil_sha256"],
            "ed7abe873d1a95a0896473acad7467004cc168606b7aac30b1bbdf6c3672509a",
        )

    def test_production_futil_removes_audit_memories_and_logits_buffer(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        futil = artifact.futil
        for name in (
            "model_embedding", "model_token_embedding", "model_position_embedding",
            "model_block_outputs", "model_final_ln", "model_logits",
        ):
            self.assertNotIn(f"{name} = seq_mem_d1", futil)
        self.assertNotIn("model_write_logit", futil)
        self.assertIn("model_best_token", futil)
        self.assertIn("selected_tokens", futil)
        self.assertNotIn("lm_accumulator_i64 = seq_mem_d1(64, 50257, 16)", futil)
        self.assertIn("lm_gemv_accumulator = std_reg(64)", futil)
        self.assertNotIn("token_weight_scale_q8_24 = seq_mem_d1(32, 50257, 16)", futil)
        self.assertIn("token_weight_scale_q8_24_b0 = seq_mem_d1(32, 16384, 14)", futil)
        self.assertIn("token_weight_scale_q8_24_b3 = seq_mem_d1(32, 16384, 14)", futil)
        self.assertIn("token_weight_codes_i8_b0 = seq_mem_d1(8, 16384, 14)", futil)
        self.assertIn("token_weight_codes_i8_b196 = seq_mem_d1(8, 16384, 14)", futil)
        self.assertIn("model_token_scale_signed = std_signext(32, 64)", futil)
        self.assertIn("model_last_row", futil)
        self.assertIn("model_token_code_bank_bit_1 = std_bit_slice(8, 1, 1, 1)", futil)
        self.assertIn("lm_gemv_weight_bank_bit_1 = std_bit_slice(8, 1, 1, 1)", futil)

    def test_production_contract_streams_argmax_and_keeps_source_only_inputs(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        self.assertEqual(artifact.provenance["production_memory_contract"]["full_logits_storage"], False)
        self.assertEqual(artifact.provenance["production_memory_contract"]["audit_checkpoint_memories"], [])
        self.assertEqual(artifact.provenance["claims"]["board_fit_verified"], False)
        sources = artifact.provenance["source_memories"]
        self.assertIn("token_weight_codes_i8_b0", sources)
        self.assertEqual(sources["token_weight_codes_i8_b0"]["banked"]["layout"], "token_rows_256_then_hidden")
        self.assertIn("token_weight_scale_q8_24_b1", sources)
        self.assertNotIn("token_weight_codes_i8", sources)
        self.assertNotIn("selected_tokens", artifact.provenance["source_memories"])

    def test_production_generator_rejects_host_feedback(self):
        module = load_module()
        with self.assertRaisesRegex(ValueError, "host_second_token_forbidden"):
            module.generate_production_kernel(ORACLE, host_second_token=612)

    def test_production_exposes_board_token_readback_port(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        self.assertIn("token_index: 1", artifact.futil)
        self.assertIn("token_id: 16", artifact.futil)
        self.assertIn("model_token_select.cond = token_index", artifact.futil)
        for port in ("prompt_0: 16", "prompt_1: 16", "prompt_2: 16", "prompt_3: 16"):
            self.assertIn(port, artifact.futil)
        self.assertIn("model_prompt_value.out", artifact.futil)
        with self.assertRaisesRegex(ValueError, "host_intermediate_states_forbidden"):
            module.generate_production_kernel(ORACLE, host_intermediate_states={"block.0": []})

    def test_ypcb_top_wires_jtag_prompt_into_generated_kernel(self):
        top = (ROOT / "rtl/tinystories_1m_ypcb_bram_production_top.sv").read_text()
        for signal in ("prompt_0", "prompt_1", "prompt_2", "prompt_3"):
            self.assertIn(f".{signal}({signal})", top)
        self.assertIn("tinystories_1m_jtag_csr csr", top)
        self.assertIn("main core", top)


if __name__ == "__main__":
    unittest.main()
