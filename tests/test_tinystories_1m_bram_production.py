"""Structural and semantic gates for the BRAM-only production generator."""
from __future__ import annotations

import importlib.util
import json
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
        self.assertIn("lm_accumulator_i64 = seq_mem_d1(64, 50257, 16)", futil)
        self.assertIn("model_last_row", futil)

    def test_production_contract_streams_argmax_and_keeps_source_only_inputs(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        self.assertEqual(artifact.provenance["production_memory_contract"]["full_logits_storage"], False)
        self.assertEqual(artifact.provenance["production_memory_contract"]["audit_checkpoint_memories"], [])
        self.assertEqual(artifact.provenance["claims"]["board_fit_verified"], False)
        self.assertIn("token_weight_codes_i8", artifact.provenance["source_memories"])
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
