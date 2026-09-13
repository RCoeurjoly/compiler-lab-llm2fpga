import re
import unittest
from scripts.pipeline.lower_fixed_point_model_bram_production import generate_production_kernel


class SixteenProductionTest(unittest.TestCase):
    def test_production_audit_mode_retains_semantic_checkpoints(self):
        production = generate_production_kernel(generation_steps=16)
        audit = generate_production_kernel(generation_steps=16, audit_checkpoints=True)
        self.assertNotIn('model_embedding = seq_mem_d1', production.futil)
        self.assertIn('model_embedding = seq_mem_d1', audit.futil)
        self.assertTrue(audit.provenance['claims']['simulation_checkpoints'])

    def test_full_generation_has_twenty_rows_sixteen_outputs_and_unchanged_sources(self):
        legacy = generate_production_kernel(generation_steps=2)
        artifact = generate_production_kernel(generation_steps=16)
        self.assertEqual(artifact.provenance['source_memories'], legacy.provenance['source_memories'])
        self.assertEqual(artifact.provenance['oracle_sha256'],
                         '7c306e8b6e38e94f54a13b8434c6dff720d0cccfb7a9e9c749198f3dde93f74d')
        self.assertEqual(artifact.provenance['schedule']['real_context_lengths'], list(range(4,20)))
        self.assertIn('token_index: 4', artifact.futil)
        for declaration in ('model_step = std_reg(5);', 'model_context_length = std_reg(5);',
                            'model_step_address = std_slice(5, 4);',
                            'model_row_address = std_slice(5, 5);',
                            'model_copy_address = std_slice(11, 11);'):
            self.assertIn(declaration, artifact.futil)
        self.assertIn("model_step_lt.right = 5'd16;", artifact.futil)
        self.assertIn("model_row_lt.right = model_context_length.out;", artifact.futil)
        self.assertIn("model_copy_lt.right = 11'd1280;", artifact.futil)
        self.assertIn("model_score_row_shift.right = 13'd8;", artifact.futil)
        self.assertIn("model_score_head_low_shift.right = 13'd2;", artifact.futil)
        self.assertIn("causal_slot_head_key.left = model_score_head_stride.out;", artifact.futil)
        memories = {m[1]:(int(m[2]),int(m[3]),int(m[4])) for m in re.finditer(
            r'@external (\w+) = seq_mem_d1\((\d+), (\d+), (\d+)\);', artifact.futil)}
        for name,count in (('context_tokens',20),('selected_tokens',16),
                           ('block_input_q16_16',1280),('block_output_q16_16',1280),
                           ('attention_score_q8',6400),('attention_exp_q1_20',6400),
                           ('c_fc_output_q16_16',5120),('gelu_output_q16_16',5120),
                           ('final_output_q16_16',1280),('lm_input_codes_i8',1280)):
            self.assertEqual(memories[name][1:], (count,(count-1).bit_length()), name)
        for index in range(16):
            self.assertIn(f'model_token{index} = std_reg(16);', artifact.futil)
            self.assertIn(f"model_step_eq{index}.right = 4'd{index};", artifact.futil)
            self.assertIn(f"model_output_eq{index}.right = 4'd{index};", artifact.futil)
        self.assertIn('context_tokens.write_data = model_best_token.out;', artifact.futil)
        self.assertIn('selected_tokens.write_data = model_best_token.out;', artifact.futil)
        self.assertFalse(artifact.provenance['claims']['sv_execution_verified'])
        self.assertFalse(artifact.provenance['claims']['board_executed'])
