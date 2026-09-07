#!/usr/bin/env python3
"""Compose the authenticated TinyStories model from existing compiler phases.

This emits one hardware controller and one shared transformer datapath.  Eight
row slots are allocated; rows beyond the real 4/5-token context are causally
irrelevant padding.  Only scheduling/address capacities are widened.  Existing
fixed-point arithmetic generators are not modified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "tinystories-1m-model-orchestrator-calyx-v1"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json"
Phase = tuple[list[str], list[str], str]


@dataclass(frozen=True)
class CalyxArtifact:
    futil: str
    provenance: dict[str, Any]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _dependencies():
    block = _load(ROOT / "scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py", "model_block_lowerer")
    return block, block._attention_lowerer(), block._mlp_lowerer()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _rename(phase: Phase, names: dict[str, str]) -> Phase:
    def apply(text):
        return re.sub(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b", lambda m: names[m[0]], text)
    return [apply(x) for x in phase[0]], [apply(x) for x in phase[1]], apply(phase[2])


def _resize(phase: Phase, changes: dict[str, tuple[int, ...]], limits: dict[str, int] | None = None) -> Phase:
    """Change only named counter/address cells and their literal input widths."""
    cells, wires, control = phase
    text = "\n".join(wires)
    result = []
    seen = set()
    for cell in cells:
        match = re.fullmatch(r"(\w+) = (\w+)\(([^)]*)\);", cell.strip())
        if match and match[1] in changes:
            name, primitive = match[1], match[2]
            args = changes[name]
            # All changed primitives have their input width in parameter 0.
            text = re.sub(rf"({name}\.(?:in|left|right)\s*=\s*)\d+'d(\d+)", rf"\g<1>{args[0]}'d\2", text)
            result.append(f"{name} = {primitive}({', '.join(map(str, args))});")
            seen.add(name)
        else:
            result.append(cell)
    if seen != set(changes):
        raise ValueError(f"schedule ABI changed: {sorted(set(changes) - seen)}")
    for name, value in (limits or {}).items():
        text, count = re.subn(rf"({name}\.right\s*=\s*\d+'d)\d+;", rf"\g<1>{value};", text)
        if count != 1:
            raise ValueError(f"schedule loop bound ABI changed: {name}")
    return result, [text], control


def _layer_norm(attention, prefix: str = "", final: bool = False) -> Phase:
    phase = attention._ln2_composed_phase() if prefix == "ln2_" else attention._ln1_composed_phase()
    changes = {
        "row_counter": (4,), "row_lt": (4,), "increment_row": (4,),
        "row_pad": (4, 9), "row_shift": (9,), "column_pad": (6, 9), "flat_address": (9,),
    }
    phase = _resize(phase, {prefix + k: v for k, v in changes.items()}, {prefix + "row_lt": 8})
    if final:
        # Namespace the unmodified ln1 arithmetic and reconnect its memory ABI.
        cells = re.findall(r"^(\w+) =", "\n".join(phase[0]), re.M)
        groups = re.findall(r"(?:comb )?group (\w+)", "\n".join(phase[1]))
        names = {x: "final_" + x for x in cells + groups}
        names.update({"block_input_q16_16": "block_output_q16_16", "ln1_gamma_q16_16": "final_gamma_q16_16", "ln1_beta_q16_16": "final_beta_q16_16", "ln1_output_q16_16": "final_output_q16_16"})
        phase = _rename(phase, names)
    return phase


def _causal(attention) -> Phase:
    changes = {
        "causal_row": (4,), "causal_key": (4,), "causal_row_lt": (4,),
        "causal_key_le": (4,), "causal_row_increment": (4,), "causal_key_increment": (4,),
        "causal_row_pad8": (4, 9), "causal_row_shift6": (9,),
        "causal_key_pad8": (4, 9), "causal_key_shift6": (9,),
        "causal_head_pad8": (5, 9), "causal_head_shift2": (9,),
        "causal_lane_pad8": (3, 9), "causal_query_head_lane": (9,),
        "causal_query_address": (9,), "causal_key_address": (9,),
        "causal_slot_head_key": (10,), "causal_slot_address": (10,),
        "causal_row_pad6": (4, 7), "causal_row_shift4": (7,),
        "causal_head_pad6": (5, 7), "causal_row_head_address": (7,),
    }
    cells, wires, control = _resize(attention._causal_attention_phase(), changes, {"causal_row_lt": 8})
    # Score slots are [row,head,key] with key stride8, whereas Q/K/V are
    # [row,head,lane] with lane stride4.  They must not share that address.
    cells += ["model_score_row = std_pad(4, 10);", "model_score_row_shift = std_lsh(10);", "model_score_head = std_pad(5, 10);", "model_score_head_shift = std_lsh(10);", "model_score_key = std_pad(4, 10);"]
    text = "\n".join(wires)
    for old, new in {
        "causal_slot_head_key.left = causal_head_shift2.out;": "causal_slot_head_key.left = model_score_head_shift.out;",
        "causal_slot_head_key.right = causal_key_pad8.out;": "causal_slot_head_key.right = model_score_key.out;",
        "causal_slot_address.left = causal_row_shift6.out;": "causal_slot_address.left = model_score_row_shift.out;",
    }.items():
        if text.count(old) != 1:
            raise ValueError("causal score address ABI changed")
        text = text.replace(old, new)
    text += """
    model_score_row.in = causal_row.out;
    model_score_row_shift.left = model_score_row.out;
    model_score_row_shift.right = 10'd7;
    model_score_head.in = causal_head.out;
    model_score_head_shift.left = model_score_head.out;
    model_score_head_shift.right = 10'd3;
    model_score_key.in = causal_key.out;
"""
    return cells, [text], control


def _block_phases(block, attention, mlp) -> list[Phase]:
    phases = [_layer_norm(attention), attention._initialize_zero_bias_phase()]
    def projection(prefix, source, inputs, outputs, bias, qdq=True):
        if qdq:
            phases.append(mlp._activation_qdq_phase(f"{prefix}_input_qdq", source, f"{prefix}_input_scale_q8_24", f"{prefix}_input_codes_i8", f"{prefix}_input_q16_16", 8 * inputs, inputs))
        phases.append(mlp._gemv_phase(f"{prefix}_gemv", f"{prefix}_input_codes_i8", f"{prefix}_input_scale_q8_24", f"{prefix}_weight_codes_i8", f"{prefix}_accumulator_i64", 8, inputs, outputs))
        phases.append(mlp._requantize_phase(f"{prefix}_requant", f"{prefix}_accumulator_i64", f"{prefix}_weight_scale_q8_24", bias, f"{prefix}_output_scale_q8_24", f"{prefix}_post_weight_rescale_bias_q16_16", f"{prefix}_output_codes_i8", f"{prefix}_output_q16_16", 8 * outputs, outputs))
    for prefix in ("q", "k", "v"):
        projection(prefix, "ln1_output_q16_16", 64, 64, "zero_bias_q16_16")
    phases.append(_resize(attention._initialize_causal_slots_phase(), {"causal_zero_counter": (11,), "causal_zero_lt": (11,), "causal_zero_increment": (11,), "causal_zero_address": (11, 10)}, {"causal_zero_lt": 1024}))
    phases.append(_causal(attention))
    projection("out", "attention_context_q16_16", 64, 64, "out_bias_q16_16")
    phases.append(_resize(attention._residual_add_phase(), {"attention_residual_counter": (10,), "attention_residual_lt": (10,), "attention_residual_increment": (10,), "attention_residual_address": (10, 9)}, {"attention_residual_lt": 512}))
    phases.append(_layer_norm(attention, "ln2_"))
    projection("c_fc", "ln2_output_q16_16", 64, 256, "c_fc_bias_q16_16")
    phases.append(_resize(mlp._gelu_phase(), {"gelu_entry_counter": (12,), "gelu_entry_lt": (12,), "gelu_increment_entry": (12,), "gelu_entry_address": (12, 11)}, {"gelu_entry_lt": 2048}))
    projection("c_proj", "gelu_output_q16_16", 256, 64, "c_proj_bias_q16_16")
    phases.append(_resize(block._final_residual_phase(), {"block_output_counter": (10,), "block_output_lt": (10,), "block_output_increment": (10,), "block_output_address": (10, 9)}, {"block_output_lt": 512}))
    return phases


def _memory(name: str, width: int, count: int) -> str:
    return f"@external {name} = seq_mem_d1({width}, {count}, {(count - 1).bit_length()});"


def _source_binding(name: str) -> tuple[str, str]:
    if name.startswith("ln"):
        ln, kind, _ = name.split("_", 2)
        return "parameter", f"blocks.{{layer}}.{ln}.{'weight' if kind == 'gamma' else 'bias'}"
    for prefix, projection, module in (("q", "attn.q", "attn.attention.q_proj"), ("k", "attn.k", "attn.attention.k_proj"), ("v", "attn.v", "attn.attention.v_proj"), ("out", "attn.out", "attn.attention.out_proj"), ("c_fc", "mlp.fc", "mlp.c_fc"), ("c_proj", "mlp.proj", "mlp.c_proj")):
        if name.startswith(prefix + "_"):
            suffix = name[len(prefix) + 1:]
            if suffix == "weight_codes_i8": return "code", f"blocks.{{layer}}.{projection}.weight"
            if suffix == "weight_scale_q8_24": return "scale", f"blocks.{{layer}}.{projection}.weight"
            if suffix == "bias_q16_16": return "parameter", f"blocks.{{layer}}.{projection}.bias"
            if suffix in ("input_scale_q8_24", "output_scale_q8_24"):
                return "scale", f"activation::transformer.h.{{layer}}.{module}.{suffix.split('_')[0]}"
    raise ValueError(f"unknown parameter source: {name}")


class Builder:
    def __init__(self):
        self.cells: list[str] = []
        self.wires: list[str] = []

    def cell(self, name, primitive, *args):
        self.cells.append(f"{name} = {primitive}({', '.join(map(str, args))});")
        return name

    def group(self, name, assignments, done):
        self.wires.append(f"group {name} {{\n" + "\n".join(assignments) + f"\n{name}[done] = {done};\n}}")
        return name + ";"

    def counter(self, name, width, count):
        self.cell(name, "std_reg", width)
        self.cell(name + "_lt", "std_lt", width)
        self.cell(name + "_add", "std_add", width)
        self.wires.append(f"comb group {name}_condition {{ {name}_lt.left = {name}.out; {name}_lt.right = {count}; }}")
        self.group(name + "_init", [f"{name}.in = {width}'d0;", f"{name}.write_en = 1'd1;"], name + ".done")
        self.group(name + "_increment", [f"{name}_add.left = {name}.out;", f"{name}_add.right = {width}'d1;", f"{name}.in = {name}_add.out;", f"{name}.write_en = 1'd1;"], name + ".done")

    def loop(self, name, body):
        return f"{name}_init; while {name}_lt.out with {name}_condition {{ seq {{ {body} {name}_increment; }} }}"

    def read(self, name, memories):
        assignments = []
        for mem, address in memories:
            assignments += [f"{mem}.addr0 = {address};", f"{mem}.content_en = 1'd1;"]
        done = " & ".join(f"{mem}.done" for mem, _ in memories)
        return self.group(name, assignments, f"({done}) ? 1'd1")

    def write(self, name, memories):
        assignments = []
        for mem, address, value in memories:
            assignments += [f"{mem}.addr0 = {address};", f"{mem}.content_en = 1'd1;", f"{mem}.write_en = 1'd1;", f"{mem}.write_data = {value};"]
        done = " & ".join(f"{mem}.done" for mem, _, _ in memories)
        return self.group(name, assignments, f"({done}) ? 1'd1")

    def round(self, name, value, shift):
        for suffix, op in (("negative", "std_slt"), ("negate", "std_ssub"), ("absolute", "std_mux"), ("bias", "std_add"), ("shift", "std_rsh"), ("signed", "std_ssub"), ("select", "std_mux"), ("result", "std_reg")):
            self.cell(name + "_" + suffix, op, 64)
        return self.group(name, [f"{name}_negative.left = {value};", f"{name}_negative.right = 64'd0;", f"{name}_negate.left = 64'd0;", f"{name}_negate.right = {value};", f"{name}_absolute.cond = {name}_negative.out;", f"{name}_absolute.tru = {name}_negate.out;", f"{name}_absolute.fal = {value};", f"{name}_bias.left = {name}_absolute.out;", f"{name}_bias.right = 64'd{1 << (shift - 1)};", f"{name}_shift.left = {name}_bias.out;", f"{name}_shift.right = 64'd{shift};", f"{name}_signed.left = 64'd0;", f"{name}_signed.right = {name}_shift.out;", f"{name}_select.cond = {name}_negative.out;", f"{name}_select.tru = {name}_signed.out;", f"{name}_select.fal = {name}_shift.out;", f"{name}_result.in = {name}_select.out;", f"{name}_result.write_en = 1'd1;"], name + "_result.done")


def _orchestration(builder: Builder, block_control: str, final_control: str, lm_control: str, *, audit_checkpoints: bool = True) -> str:
    b = builder
    for name, width, limit in (("model_step", 2, "2'd2"), ("model_layer", 4, "4'd8"), ("model_row", 4, "4'd8"), ("model_column", 7, "7'd64"), ("model_copy", 10, "10'd512"), ("model_logit_row", 4, "model_context_length.out"), ("model_logit", 16, "16'd50257")):
        b.counter(name, width, limit)
    b.cell("model_context_length", "std_reg", 4)
    b.cell("model_context_next", "std_add", 4)
    b.cell("model_context_address", "std_slice", 4, 3)
    b.cell("model_layer_bank", "std_slice", 4, 3)
    b.cell("model_step_address", "std_slice", 2, 1)
    b.cell("model_row_address", "std_slice", 4, 3)
    b.cell("model_prompt_address", "std_slice", 4, 2)
    b.cell("model_is_prompt", "std_lt", 4)
    b.cell("model_position_address", "std_pad", 4, 5)
    b.cell("model_column_address", "std_slice", 7, 6)
    b.cell("model_hidden_address", "std_cat", 3, 6, 9)
    b.cell("model_token_address", "std_cat", 16, 6, 22)
    b.cell("model_position_weight_address", "std_cat", 5, 6, 11)
    b.cell("model_copy_address", "std_slice", 10, 9)
    if audit_checkpoints:
        b.cell("model_embedding_checkpoint_address", "std_cat", 1, 9, 10)
        b.cell("model_block_step_layer", "std_cat", 1, 3, 4)
        b.cell("model_block_checkpoint_address", "std_cat", 4, 9, 13)
        b.cell("model_ln_checkpoint_address", "std_cat", 1, 9, 10)
    b.cell("model_valid_not", "std_not", 1)
    b.cell("model_wait_register", "std_reg", 1)
    if audit_checkpoints:
        b.wires += ["""
model_layer_bank.in = model_layer.out;
model_step_address.in = model_step.out;
model_context_address.in = model_context_length.out;
model_row_address.in = model_row.out;
model_prompt_address.in = model_row.out;
model_position_address.in = model_row.out;
model_column_address.in = model_column.out;
model_hidden_address.left = model_row_address.out;
model_hidden_address.right = model_column_address.out;
model_token_address.left = context_tokens.read_data;
model_token_address.right = model_column_address.out;
model_position_weight_address.left = model_position_address.out;
model_position_weight_address.right = model_column_address.out;
model_copy_address.in = model_copy.out;
model_embedding_checkpoint_address.left = model_step_address.out;
model_embedding_checkpoint_address.right = model_hidden_address.out;
model_block_step_layer.left = model_step_address.out;
model_block_step_layer.right = model_layer_bank.out;
model_block_checkpoint_address.left = model_block_step_layer.out;
model_block_checkpoint_address.right = model_copy_address.out;
model_ln_checkpoint_address.left = model_step_address.out;
model_ln_checkpoint_address.right = model_copy_address.out;
comb group model_wait_condition { model_valid_not.in = valid; }
comb group model_prompt_condition { model_is_prompt.left = model_row.out; model_is_prompt.right = 4'd4; }
"""]
    else:
        b.wires += ["""
model_layer_bank.in = model_layer.out;
model_step_address.in = model_step.out;
model_context_address.in = model_context_length.out;
model_row_address.in = model_row.out;
model_prompt_address.in = model_row.out;
model_position_address.in = model_row.out;
model_column_address.in = model_column.out;
model_hidden_address.left = model_row_address.out;
model_hidden_address.right = model_column_address.out;
model_token_address.left = context_tokens.read_data;
model_token_address.right = model_column_address.out;
model_position_weight_address.left = model_position_address.out;
model_position_weight_address.right = model_column_address.out;
model_copy_address.in = model_copy.out;
comb group model_wait_condition { model_valid_not.in = valid; }
comb group model_prompt_condition { model_is_prompt.left = model_row.out; model_is_prompt.right = 4'd4; }
"""]
    wait = b.group("model_wait", ["model_wait_register.in = 1'd1;", "model_wait_register.write_en = 1'd1;"], "model_wait_register.done")
    init_length = b.group("model_init_length", ["model_context_length.in = 4'd4;", "model_context_length.write_en = 1'd1;"], "model_context_length.done")
    read_prompt = b.read("model_read_prompt", [("prompt_tokens", "model_prompt_address.out")])
    copy_prompt = b.write("model_copy_prompt", [("context_tokens", "model_row_address.out", "prompt_tokens.read_data")])
    pad_prompt = b.write("model_pad_prompt", [("context_tokens", "model_row_address.out", "16'd0")])
    prompt = b.loop("model_row", f"if model_is_prompt.out with model_prompt_condition {{ seq {{ {read_prompt} {copy_prompt} }} }} else {{ {pad_prompt} }}")
    read_token = b.read("model_read_token", [("context_tokens", "model_row_address.out"), ("position_weight_scale_q8_24", "model_position_address.out")])
    read_token_scale = b.read("model_read_token_scale", [("token_weight_scale_q8_24", "context_tokens.read_data")])
    read_codes = b.read("model_read_embedding_codes", [("token_weight_codes_i8", "model_token_address.out"), ("position_weight_codes_i8", "model_position_weight_address.out")])
    for p in ("model_token", "model_position"):
        b.cell(p + "_signed", "std_signext", 8, 64)
        b.cell(p + "_product", "std_smult_pipe", 64)
    multiply = b.group("model_embedding_multiply", ["model_token_signed.in = token_weight_codes_i8.read_data;", "model_token_product.left = model_token_signed.out;", "model_token_product.right = token_weight_scale_q8_24.read_data;", "model_token_product.go = 1'd1;", "model_position_signed.in = position_weight_codes_i8.read_data;", "model_position_product.left = model_position_signed.out;", "model_position_product.right = position_weight_scale_q8_24.read_data;", "model_position_product.go = 1'd1;"], "(model_token_product.done & model_position_product.done) ? 1'd1")
    round_token = b.round("model_round_token", "model_token_product.out", 8)
    round_position = b.round("model_round_position", "model_position_product.out", 8)
    b.cell("model_embedding_sum", "std_sadd", 64)
    b.wires.append("model_embedding_sum.left = model_round_token_result.out; model_embedding_sum.right = model_round_position_result.out;")
    embedding_writes = [("block_input_q16_16", "model_hidden_address.out", "model_embedding_sum.out")]
    if audit_checkpoints:
        embedding_writes += [("model_embedding", "model_embedding_checkpoint_address.out", "model_embedding_sum.out"), ("model_token_embedding", "model_embedding_checkpoint_address.out", "model_round_token_result.out"), ("model_position_embedding", "model_embedding_checkpoint_address.out", "model_round_position_result.out")]
    write_embedding = b.write("model_write_embedding", embedding_writes)
    embedding = b.loop("model_row", read_token + read_token_scale + b.loop("model_column", read_codes + multiply + round_token + round_position + write_embedding))
    read_block = b.read("model_read_block", [("block_output_q16_16", "model_copy_address.out")])
    block_writes = [("block_input_q16_16", "model_copy_address.out", "block_output_q16_16.read_data")]
    if audit_checkpoints:
        block_writes += [("model_block_outputs", "model_block_checkpoint_address.out", "block_output_q16_16.read_data")]
    copy_block = b.write("model_copy_block", block_writes)
    blocks = b.loop("model_layer", block_control + b.loop("model_copy", read_block + copy_block))
    read_ln = b.read("model_read_final_ln", [("final_output_q16_16", "model_copy_address.out")]) if audit_checkpoints else ""
    copy_ln = ""
    if audit_checkpoints:
        copy_ln = b.write("model_copy_final_ln", [("model_final_ln", "model_ln_checkpoint_address.out", "final_output_q16_16.read_data")])
    # Vocabulary rows are padded to stride 65536 only for addressing; all
    # 50257 exact vocabulary entries, and only real context rows, are visited.
    b.cell("model_logit_row_address", "std_slice", 4, 3)
    b.cell("model_accumulator_address", "std_cat", 3, 16, 19)
    if audit_checkpoints:
        b.cell("model_logits_address", "std_cat", 1, 19, 20)
    b.cell("model_logit_product", "std_smult_pipe", 64)
    b.cell("model_best_value", "std_reg", 64)
    b.cell("model_best_token", "std_reg", 16)
    b.cell("model_logit_is_better", "std_sgt", 64)
    if audit_checkpoints:
        b.wires += ["""
model_logit_row_address.in = model_logit_row.out;
model_accumulator_address.left = model_logit_row_address.out;
model_accumulator_address.right = model_logit.out;
model_logits_address.left = model_step_address.out;
model_logits_address.right = model_accumulator_address.out;
comb group model_greedy_condition { model_logit_is_better.left = model_round_logit_result.out; model_logit_is_better.right = model_best_value.out; }
"""]
    else:
        b.wires += ["""
model_logit_row_address.in = model_logit_row.out;
model_accumulator_address.left = model_logit_row_address.out;
model_accumulator_address.right = model_logit.out;
comb group model_greedy_condition { model_logit_is_better.left = model_round_logit_result.out; model_logit_is_better.right = model_best_value.out; }
"""]
    init_greedy = b.group("model_init_greedy", ["model_best_value.in = 64'd9223372036854775808;", "model_best_value.write_en = 1'd1;", "model_best_token.in = 16'd0;", "model_best_token.write_en = 1'd1;"], "(model_best_value.done & model_best_token.done) ? 1'd1")
    read_logit = b.read("model_read_logit", [("lm_accumulator_i64", "model_accumulator_address.out"), ("token_weight_scale_q8_24", "model_logit.out")])
    mul_logit = b.group("model_multiply_logit", ["model_logit_product.left = lm_accumulator_i64.read_data;", "model_logit_product.right = token_weight_scale_q8_24.read_data;", "model_logit_product.go = 1'd1;"], "model_logit_product.done")
    round_logit = b.round("model_round_logit", "model_logit_product.out", 32)
    write_logit = ""
    if audit_checkpoints:
        write_logit = b.write("model_write_logit", [("model_logits", "model_logits_address.out", "model_round_logit_result.out")])
    greedy = b.group("model_update_greedy", ["model_best_value.in = model_round_logit_result.out;", "model_best_value.write_en = 1'd1;", "model_best_token.in = model_logit.out;", "model_best_token.write_en = 1'd1;"], "(model_best_value.done & model_best_token.done) ? 1'd1")
    logits = b.loop("model_logit_row", init_greedy + b.loop("model_logit", read_logit + mul_logit + round_logit + write_logit + f"if model_logit_is_better.out with model_greedy_condition {{ {greedy} }}"))
    feedback = b.write("model_commit_feedback", [("selected_tokens", "model_step_address.out", "model_best_token.out"), ("context_tokens", "model_context_address.out", "model_best_token.out")])
    next_context = b.group("model_next_context", ["model_context_next.left = model_context_length.out;", "model_context_next.right = 4'd1;", "model_context_length.in = model_context_next.out;", "model_context_length.write_en = 1'd1;"], "model_context_length.done")
    final_copy = b.loop("model_copy", read_ln + copy_ln) if audit_checkpoints else ""
    steps = b.loop("model_step", embedding + blocks + final_control + final_copy + lm_control + logits + feedback + next_context)
    return f"seq {{ while model_valid_not.out with model_wait_condition {{ {wait} }} {init_length} {prompt} {steps} }}"


def generate_model_kernel(oracle_path: Path = ORACLE, *, host_second_token=None, host_intermediate_states=None, production: bool = False) -> CalyxArtifact:
    if host_second_token is not None:
        raise ValueError("host_second_token_forbidden")
    if host_intermediate_states is not None:
        raise ValueError("host_intermediate_states_forbidden")
    capture = _load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "model_oracle_for_calyx")
    oracle = json.loads(Path(oracle_path).read_text())
    capture.verify_oracle_fixture(oracle)
    block, attention, mlp = _dependencies()
    base = block._block_kernel_futil()
    base_cells, _, _ = mlp._component_sections(base)
    source_names = set(block._memory_contracts(attention, mlp)[0]) - {"block_input_q16_16"}
    shared_luts = {"attention_exp_lut_q1_20", "gelu_lut_q12"}
    sources = {}
    memory_cells = []
    banks = {}
    for match in re.finditer(r"(?:@external )?(\w+) = seq_mem_d1\((\d+), (\d+), (\d+)\);", base_cells):
        name, width, count, address = match[1], int(match[2]), int(match[3]), int(match[4])
        if name in source_names:
            if name in shared_luts:
                source = {"kind": "lut", "buffer": "_exp_lut" if name.startswith("attention") else "_gelu_lut"}
            else:
                kind, binding = _source_binding(name)
                source = {"kind": kind, "buffer": binding, "banks": 8, "bank_elements": count}
                banks[name] = address
                count *= 8
            sources[name] = {**source, "width": width, "elements": count}
        elif name != "zero_bias_q16_16":
            count *= 4 if name in {"attention_score_q8", "attention_delta_q8", "attention_exp_q1_20"} else 2
        memory_cells.append(_memory(name, width, count))
    new_sources = {
        "prompt_tokens": {"kind": "prompt", "width": 16, "elements": 4},
        "token_weight_codes_i8": {"kind": "code", "buffer": "token_embedding.weight", "width": 8, "elements": 50257 * 64},
        "token_weight_scale_q8_24": {"kind": "scale", "buffer": "token_embedding.weight", "width": 64, "elements": 50257},
        "position_weight_codes_i8": {"kind": "code", "buffer": "position_embedding.weight", "width": 8, "elements": 32 * 64},
        "position_weight_scale_q8_24": {"kind": "scale", "buffer": "position_embedding.weight", "width": 64, "elements": 32},
        "final_gamma_q16_16": {"kind": "parameter", "buffer": "final_ln.weight", "width": 64, "elements": 64},
        "final_beta_q16_16": {"kind": "parameter", "buffer": "final_ln.bias", "width": 64, "elements": 64},
        "lm_input_scale_q8_24": {"kind": "scale", "buffer": "activation::lm_head.input", "width": 64, "elements": 64},
    }
    sources.update(new_sources)
    memory_cells += [_memory(name, record["width"], record["elements"]) for name, record in new_sources.items()]
    if production:
        hardware = {"context_tokens": (16, 8), "selected_tokens": (16, 2), "final_output_q16_16": (64, 512), "lm_input_codes_i8": (8, 512), "lm_input_q16_16": (64, 512), "lm_accumulator_i64": (64, 524288)}
    else:
        hardware = {"context_tokens": (16, 8), "selected_tokens": (16, 2), "model_embedding": (64, 1024), "model_token_embedding": (64, 1024), "model_position_embedding": (64, 1024), "model_block_outputs": (64, 8192), "model_final_ln": (64, 1024), "final_output_q16_16": (64, 512), "lm_input_codes_i8": (8, 512), "lm_input_q16_16": (64, 512), "lm_accumulator_i64": (64, 524288), "model_logits": (64, 1048576)}
    memory_cells += [_memory(name, *descriptor) for name, descriptor in hardware.items()]
    phases = _block_phases(block, attention, mlp)
    b = Builder()
    b.cells += memory_cells
    block_wires = "\n".join(wire for _, wires, _ in phases for wire in wires)
    b.cells += [cell for cells, _, _ in phases for cell in cells]
    for name, address in banks.items():
        bank = name + "_bank_address"
        b.cell(bank, "std_cat", 3, address, address + 3)
        # Keep both concatenation inputs in the memory-access group. Mixing
        # a continuous bank input with a group-local index makes Calyx's
        # dead-assign-removal drop the upstream group-local index drivers.
        block_wires, count = re.subn(rf"\b{name}\.addr0 = ([^;]+);", rf"{bank}.left = model_layer_bank.out; {bank}.right = \1; {name}.addr0 = {bank}.out;", block_wires)
        if count == 0:
            raise ValueError(f"unused model parameter bank: {name}")
    b.wires.append(block_wires)
    final_phase = _layer_norm(attention, final=True)
    qdq_phase = mlp._activation_qdq_phase("lm_input_qdq", "final_output_q16_16", "lm_input_scale_q8_24", "lm_input_codes_i8", "lm_input_q16_16", 512, 64)
    gemv_phase = mlp._gemv_phase("lm_gemv", "lm_input_codes_i8", "lm_input_scale_q8_24", "token_weight_codes_i8", "lm_accumulator_i64", 8, 64, 50257)
    # Restrict expensive vocabulary projections to real context rows.
    gemv_phase = (gemv_phase[0], [w.replace("lm_gemv_row_lt.right = 4'd8;", "lm_gemv_row_lt.right = model_context_length.out;") for w in gemv_phase[1]], gemv_phase[2])
    for cells, wires, _ in (final_phase, qdq_phase, gemv_phase):
        b.cells += cells
        b.wires += wires
    control = _orchestration(b, "\n".join(p[2] for p in phases), final_phase[2], qdq_phase[2] + gemv_phase[2], audit_checkpoints=not production)
    futil = '''// Compiler-owned exact model orchestration; no imported hand-written RTL.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";
component main(@go start: 1, valid: 1) -> (@done done: 1) {
  cells {
''' + mlp._indent_lines(b.cells, 4) + "\n  }\n  wires {\n" + mlp._indent_lines(b.wires, 4) + "\n  }\n  control {\n" + control + "\n  }\n}\n"
    provenance = {
        "schema": SCHEMA, "oracle_sha256": oracle["artifact_sha256"],
        "futil_sha256": _sha(futil.encode()), "base_block_futil_sha256": _sha(base.encode()),
        "compiler_sources": {str(Path(module.__file__).relative_to(ROOT)): _sha(Path(module.__file__).read_bytes()) for module in (block, attention, mlp)},
        "orchestrator_sha256": _sha(Path(__file__).read_bytes()),
        "schedule": {"layers": list(range(8)), "shared_block_datapaths": 1, "row_capacity": 8, "real_context_lengths": [4, 5], "padded_future_rows": "causally_disconnected_from_real_rows", "lm_head_rows": "real_context_only", "vocabulary": 50257, "vocabulary_storage_stride": 65536},
        "source_memories": sources,
        "hardware_owned_memories": sorted(set(re.findall(r"@external (\w+) =", futil)) - set(sources)),
        "feedback": "greedy_last_real_row -> context_tokens[context_length] -> token_embedding",
        "claims": {"compiler_owned_control": True, "existing_arithmetic_generators_modified": False, "sv_execution_verified": False, "board_executed": False, "board_fit_verified": False},
        "production_memory_contract": {"audit_checkpoint_memories": [] if production else ["model_embedding", "model_token_embedding", "model_position_embedding", "model_block_outputs", "model_final_ln", "model_logits"], "full_logits_storage": not production, "streamed_argmax": True},
    }
    provenance["artifact_sha256"] = _canonical(provenance)
    return CalyxArtifact(futil, provenance)


def compile_model_kernel(artifact: CalyxArtifact, directory: Path, *, timeout: int = 1800) -> dict[str, Any]:
    if not 0 < timeout <= 7200:
        raise ValueError("compilation timeout must be in (0, 7200]")
    if _sha(artifact.futil.encode()) != artifact.provenance["futil_sha256"]:
        raise ValueError("generated Futil identity mismatch")
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + timeout
    futil = directory / "model.futil"
    verilog = directory / "model.sv"
    futil.write_text(artifact.futil)
    def run_stage(command, stage):
        remaining = deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=remaining)
        except subprocess.TimeoutExpired as error:
            failure = {"status": "deadline_exceeded", "stage": stage, "timeout_seconds": timeout, "elapsed_seconds": time.monotonic() - started, "futil_sha256": artifact.provenance["futil_sha256"], "execution_verified": False}
            (directory / "compile.json").write_text(json.dumps(failure, indent=2) + "\n")
            raise ValueError(f"deadline_exceeded: {stage}") from error
        (directory / f"{stage}.log").write_text(run.stderr)
        if run.returncode:
            failure = {"status": "compilation_failed", "stage": stage, "returncode": run.returncode, "diagnostic": run.stderr[-6000:], "futil_sha256": artifact.provenance["futil_sha256"], "execution_verified": False}
            (directory / "compile.json").write_text(json.dumps(failure, indent=2) + "\n")
            raise ValueError(f"model Calyx lowering failed ({run.returncode}): {run.stderr[-6000:]}")
        return run
    tool = run_stage(["nix", "build", "--no-link", "--print-out-paths", ".#calyx"], "calyx_tool_resolution")
    paths = tool.stdout.strip().splitlines()
    if len(paths) != 1:
        raise ValueError("Calyx tool resolution did not yield one store path")
    install = Path(paths[0])
    command = [str(install / "bin/calyx"), str(futil), "-l", str(install / "share/calyx"), "-d", "cell-share", "-b", "verilog"]
    run = run_stage(command, "calyx_lowering")
    verilog.write_text(run.stdout)
    top = re.search(r"module main\s*\((.*?)\);", run.stdout, re.S)
    if not top:
        raise ValueError("generated SV lacks main")
    ports = [name for name in ("clk", "reset", "start", "valid", "done") if re.search(rf"\b{name}\b", top[1])]
    receipt = {"status": "generated_sv", "futil_sha256": artifact.provenance["futil_sha256"], "verilog_sha256": _sha(run.stdout.encode()), "verilog_bytes": len(run.stdout.encode()), "top_ports": ports, "elapsed_seconds": time.monotonic() - started, "timeout_seconds": timeout, "command": command, "execution_verified": False}
    (directory / "compile.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def materialize_model_sources(artifact: CalyxArtifact, bundle) -> dict[str, Any]:
    """Only immutable authenticated model inputs; never oracle intermediates."""
    import torch
    sources = {}
    for name, record in artifact.provenance["source_memories"].items():
        if record["kind"] == "prompt":
            value = torch.tensor([7454, 2402, 257, 640], dtype=torch.int64)
        elif record["kind"] == "lut":
            value = getattr(bundle.model, record["buffer"])
        elif record.get("banks"):
            value = torch.cat([bundle.model._buffer(record["kind"], record["buffer"].format(layer=layer)).reshape(-1) for layer in range(8)])
        else:
            value = bundle.model._buffer(record["kind"], record["buffer"]).reshape(-1)
        value = value.detach().cpu().to(torch.int64).flatten().contiguous()
        if value.numel() != record["elements"]:
            raise ValueError(f"source memory shape mismatch: {name}")
        sources[name] = value
    return sources
