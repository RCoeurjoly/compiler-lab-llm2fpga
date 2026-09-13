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
    def test_one_step_preserves_model_and_changes_only_generation_bound(self):
        module = load_module()
        import inspect
        self.assertIn("generation_steps", inspect.signature(module.generate_production_kernel).parameters)
        default = module.generate_production_kernel(ORACLE)
        single = module.generate_production_kernel(ORACLE, generation_steps=1)
        self.assertEqual(default.provenance["schedule"]["generation_steps"], 2)
        self.assertEqual(single.provenance["schedule"]["generation_steps"], 1)
        self.assertEqual(single.provenance["schedule"]["real_context_lengths"], [4])
        self.assertEqual(single.provenance["source_memories"], default.provenance["source_memories"])
        self.assertEqual(single.provenance["oracle_sha256"], default.provenance["oracle_sha256"])
        old_bound = "model_step_lt.right = 2'd2;"
        self.assertEqual(default.futil.count(old_bound), 1)
        self.assertEqual(single.futil, default.futil.replace(old_bound, "model_step_lt.right = 2'd1;"))

    def test_generation_steps_rejects_outside_authenticated_prefix(self):
        module = load_module()
        import inspect
        self.assertIn("generation_steps", inspect.signature(module.generate_production_kernel).parameters)
        for steps in (0, 3, -1, True, 1.0, "1"):
            with self.subTest(steps=steps), self.assertRaisesRegex(ValueError, "generation_steps"):
                module.generate_production_kernel(ORACLE, generation_steps=steps)

    def test_production_runner_harness_supports_authenticated_sixteen_steps(self):
        path = ROOT / "scripts/pipeline/run_bram_production_sv.py"
        spec = importlib.util.spec_from_file_location("bram_sv_runner_sixteen", path)
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        artifact = runner.production.generate_production_kernel(ORACLE, generation_steps=16)
        harness = runner.harness(artifact)
        self.assertIn("constexpr unsigned steps = 16;", harness)
        self.assertIn("711, 2354, 287, 262", harness)
        self.assertIn("for (unsigned step = 0; step < steps; ++step)", harness)

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
            "fa168f813ef4abb40470ef933c12a2271dd4fde58e73ee2d0b61d4c39d1f586f",
        )

    def test_selective_bram_annotation_preserves_small_memories(self):
        path = ROOT / "scripts/pipeline/run_bram_production_sv.py"
        spec = importlib.util.spec_from_file_location("bram_sv_runner", path)
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        source = """module seq_mem_d1 #(parameter SIZE=16, parameter WIDTH=8, parameter IDX_SIZE=4) (input clk);
  logic [WIDTH-1:0] mem[SIZE-1:0];
  logic [WIDTH-1:0] read_out;
  always_ff @(posedge clk) read_out <= mem[addr0];
endmodule
seq_mem_d1 #(.SIZE(2048), .WIDTH(8)) large ( .clk(clk) );
seq_mem_d1 #(.SIZE(512), .WIDTH(64)) wide ( .clk(clk) );
seq_mem_d1 #(.SIZE(64), .WIDTH(8)) small ( .clk(clk) );
"""
        result = runner.annotate_bram_memories(source)
        self.assertEqual(result.count('ram_style = "block"'), 1)
        self.assertIn("seq_mem_d1_bram # (.SIZE(2048), .WIDTH(8)) large", result)
        self.assertIn("seq_mem_d1_bram # (.SIZE(512), .WIDTH(64)) wide", result)
        self.assertIn("seq_mem_d1 #(.SIZE(64), .WIDTH(8)) small", result)

    def test_known_scratch_buffers_use_lutram_variant(self):
        path = ROOT / "scripts/pipeline/run_bram_production_sv.py"
        spec = importlib.util.spec_from_file_location("bram_sv_runner_lutram", path)
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        source = """module seq_mem_d1 #(parameter SIZE=16, parameter WIDTH=8, parameter IDX_SIZE=4) (input clk);
  logic [WIDTH-1:0] mem[SIZE-1:0];
endmodule
seq_mem_d1 #(.SIZE(512), .WIDTH(64)) attention_context_q16_16 ( .clk(clk) );
"""
        result = runner.annotate_bram_memories(source)
        self.assertIn("seq_mem_d1_lutram # (.SIZE(512), .WIDTH(64)) attention_context_q16_16", result)

    def test_signed_multiply_repair_is_strict_and_preserves_result_context(self):
        path = ROOT / "scripts/pipeline/repair_calyx_signed_multiply_width.py"
        spec = importlib.util.spec_from_file_location("signed_multiply_repair", path)
        assert spec and spec.loader
        repair = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repair)
        source = Path("/tmp/calyx-multiply-helper.sv")
        destination = Path("/tmp/calyx-multiply-helper.repaired.sv")
        receipt = Path("/tmp/calyx-multiply-helper.receipt.json")
        source.write_text(
            "module std_fp_mult_pipe #(\n"
            + repair.OLD_DECL + "\n" + repair.OLD + "\n"
            + repair.OLD_UNSIGNED + "\nendmodule\n",
            encoding="utf-8",
        )
        repair.repair(source, destination, receipt)
        repaired = destination.read_text(encoding="utf-8")
        self.assertIn("module llm2fpga_bounded_mul64", repaired)
        self.assertIn("module llm2fpga_bounded_mul32", repaired)
        self.assertIn("logic [WIDTH-1:0] left_mag;", repaired)
        self.assertIn("out_tmp <= bounded_product;", repaired)
        self.assertIn("else\n          out_tmp <= ltmp * rtmp;", repaired)
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["replacements"], 2)

    def test_bram_variant_exposes_a_registered_read_address(self):
        path = ROOT / "scripts/pipeline/run_bram_production_sv.py"
        spec = importlib.util.spec_from_file_location("bram_sv_runner_addr", path)
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        source = """module seq_mem_d1 #(parameter SIZE=16, parameter WIDTH=8, parameter IDX_SIZE=4) (input clk);
  logic [WIDTH-1:0] mem[SIZE-1:0];
  logic [WIDTH-1:0] read_out;
  always_ff @(posedge clk) begin
    if (reset) begin
      read_out <= '0;
    end else begin
      read_out <= mem[addr0];
    end
  end
  logic done;
  always_ff @(posedge clk) begin
    if (reset) begin
      done <= '0;
    end else if (content_en) begin
      done <= '1;
    end else begin
      done <= '0;
    end
  end
endmodule
seq_mem_d1 #(.SIZE(2048), .WIDTH(8)) large ( .clk(clk) );
"""
        result = runner.annotate_bram_memories(source)
        self.assertIn("logic [IDX_SIZE-1:0] read_addr;", result)
        self.assertIn("logic read_pending;", result)
        self.assertIn("read_addr <= addr0;", result)
        self.assertIn("read_out <= mem[read_addr];", result)
        self.assertIn("done <= read_pending;", result)

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
        self.assertIn("token_weight_codes_packed_b0 = seq_mem_d1(64, 16384, 14)", futil)
        self.assertIn("token_weight_codes_packed_b24 = seq_mem_d1(64, 16384, 14)", futil)
        self.assertIn("model_token_scale_signed = std_signext(32, 64)", futil)
        self.assertIn("model_last_row", futil)
        self.assertIn("model_token_code_bank_bit_1 = std_bit_slice(5, 1, 1, 1)", futil)
        self.assertIn("lm_gemv_weight_bank_bit_1 = std_bit_slice(5, 1, 1, 1)", futil)

    def test_production_contract_streams_argmax_and_keeps_source_only_inputs(self):
        module = load_module()
        artifact = module.generate_production_kernel(ORACLE)
        self.assertEqual(artifact.provenance["production_memory_contract"]["full_logits_storage"], False)
        self.assertEqual(artifact.provenance["production_memory_contract"]["audit_checkpoint_memories"], [])
        self.assertEqual(artifact.provenance["claims"]["board_fit_verified"], False)
        sources = artifact.provenance["source_memories"]
        self.assertIn("token_weight_codes_packed_b0", sources)
        self.assertEqual(sources["token_weight_codes_packed_b0"]["banked"]["layout"], "token_rows_2048_then_hidden_packed_i8")
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
        self.assertIn("tinystories_1m_jtag_csr #(.TOKEN_INDEX_WIDTH(TOKEN_INDEX_WIDTH)) csr", top)
        self.assertIn("main core", top)
        self.assertIn("wire async_reset = tap_reset | !clock_locked", top)
        self.assertIn("wire sys_reset = reset_sync[1]", top)
        clock = (ROOT / "rtl/tinystories_1m_ypcb_clock.sv").read_text()
        self.assertIn(".CLKFBOUT_MULT_F(18.0), .CLKOUT0_DIVIDE_F(30.0)", clock)
        self.assertIn(".CLKIN1_PERIOD(20.0), .DIVCLK_DIVIDE(1)", clock)
        self.assertIn(".clk(accelerator_clk)", top)
        self.assertIn(".sys_clk(accelerator_clk)", top)
        self.assertIn(".sys_rst(sys_reset)", top)

    def test_jtag_abi_preserves_lifecycle_and_readback_ordering(self):
        csr = (ROOT / "rtl/tinystories_1m_jtag_csr.sv").read_text()
        self.assertIn("input  wire        model_init_done", csr)
        self.assertIn("reg        start_pending", csr)
        self.assertIn("reg        token_read_pending", csr)
        self.assertIn("reg        done_latched", csr)
        self.assertIn("response_word <= {4'h0, 12'd0, 16'd0, 16'd0, core_token_id};", csr)
        self.assertIn("response_word <= {4'h2, model_init_done, done_latched, run_active,", csr)
        self.assertIn("start_pending <= 1'b1;", csr)

    def test_flattened_memory_mapper_discovers_and_resumes_checkpoints(self):
        path = ROOT / "scripts/pipeline/map_flattened_memory_checkpoints.py"
        spec = importlib.util.spec_from_file_location("flattened_mapper", path)
        assert spec and spec.loader
        mapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mapper)
        sample = Path("/tmp/llm2fpga-memory-map-test.il")
        sample.write_text(
            "module \\main\n"
            "  memory width 64 size 512 \\attention_context_q16_16.mem\n"
            "  memory width 8 size 32768 \\token_weight_codes_i8_b0.mem\n"
        )
        try:
            self.assertEqual(
                mapper.memory_names(sample),
                ["attention_context_q16_16.mem", "token_weight_codes_i8_b0.mem"],
            )
            self.assertIn("lutrams_xc5v.txt", mapper.checkpoint_script(sample, sample, "attention_context_q16_16.mem"))
            script = mapper.checkpoint_script(sample, sample, "token_weight_codes_i8_b0.mem")
            self.assertIn("+/xilinx/brams_xc4v.txt", script)
            self.assertIn("-D HAS_SIZE_36 -D HAS_CASCADE -D HAS_MIXWIDTH_SDP", script)
            self.assertNotIn("/tmp/yosys-data", script)
        finally:
            sample.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
