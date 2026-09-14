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

# The Yosys XC7 BRAM mapper has a bounded address depth.  Keep the exact
# token-embedding tensor order, but bank it by 256-token rows so every
# production memory is depth-16384.  This is the largest depth accepted by the
# installed XC7 BRAM library mapper for the generated synchronous memories.
# The final bank is padded with zeros; all valid TinyStories vocabulary
# addresses remain unchanged.
TOKEN_CODE_BANKS = 197
TOKEN_CODE_BANK_DEPTH = 16384
TOKEN_CODE_ROW_BITS = 8
# Packed production layout: eight signed INT8 codes share one 64-bit BRAM
# word.  A depth-16384 bank therefore stores 2048 vocabulary rows, reducing
# the physical bank count from 197 to 25 while preserving row-major order.
PACKED_TOKEN_CODE_LANES = 8
PACKED_TOKEN_CODE_ROWS_PER_BANK = TOKEN_CODE_BANK_DEPTH // (64 // PACKED_TOKEN_CODE_LANES)
PACKED_TOKEN_CODE_BANKS = (50257 + PACKED_TOKEN_CODE_ROWS_PER_BANK - 1) // PACKED_TOKEN_CODE_ROWS_PER_BANK
# Scale rows are 32-bit values. A 2,048-row bank maps to two 36-bit
# RAMB36E1-width slices, avoiding the padding cost of a 16,384-row bank.
TOKEN_SCALE_BANK_DEPTH = 2048
TOKEN_SCALE_BANKS = (50257 + TOKEN_SCALE_BANK_DEPTH - 1) // TOKEN_SCALE_BANK_DEPTH


def packed_token_code_location(token: int, hidden: int) -> tuple[int, int, int]:
    """Return (bank, word address, byte lane) for an exact model code."""
    if not 0 <= token < 50257:
        raise ValueError("token index outside authenticated vocabulary")
    if not 0 <= hidden < 64:
        raise ValueError("hidden index outside authenticated width")
    row = token % PACKED_TOKEN_CODE_ROWS_PER_BANK
    return token // PACKED_TOKEN_CODE_ROWS_PER_BANK, row * (64 // PACKED_TOKEN_CODE_LANES) + hidden // PACKED_TOKEN_CODE_LANES, hidden % PACKED_TOKEN_CODE_LANES


def pack_token_code_words(codes: list[int]) -> list[int]:
    """Pack row-major signed INT8 token codes into little-endian 64-bit words."""
    if len(codes) == 0 or len(codes) % 64:
        raise ValueError("token code tensor must contain complete 64-value rows")
    if any(type(code) is not int or not -128 <= code <= 127 for code in codes):
        raise ValueError("token code tensor contains a non-INT8 value")
    words = []
    for offset in range(0, len(codes), PACKED_TOKEN_CODE_LANES):
        word = 0
        for lane, code in enumerate(codes[offset : offset + PACKED_TOKEN_CODE_LANES]):
            word |= (code & 0xFF) << (8 * lane)
        words.append(word)
    return words


def pack_sparse_int8_rows(codes: list[int], inputs: int) -> tuple[list[int], list[int], list[int]]:
    """Encode row-major INT8 codes as (bitmaps, offsets, values).

    Each row has one bitmap bit per input index and a compact list of its
    nonzero signed INT8 values in ascending input order.  Offsets has one
    entry per row plus a terminal entry, so decoding is random-access by row
    without relying on variable-width parsing.  Zero rows are represented by
    an all-zero bitmap and equal consecutive offsets.
    """
    if type(inputs) is not int or inputs <= 0:
        raise ValueError("inputs must be a positive integer")
    if len(codes) == 0 or len(codes) % inputs:
        raise ValueError("sparse tensor must contain complete rows")
    if any(type(code) is not int or not -128 <= code <= 127 for code in codes):
        raise ValueError("sparse tensor contains a non-INT8 value")
    rows = len(codes) // inputs
    bitmap_words = (inputs + 31) // 32
    bitmaps: list[int] = []
    offsets = [0]
    values: list[int] = []
    for row in range(rows):
        bitmap = [0] * bitmap_words
        for index, code in enumerate(codes[row * inputs : (row + 1) * inputs]):
            if code:
                bitmap[index // 32] |= 1 << (index % 32)
                values.append(code)
        bitmaps.extend(bitmap)
        offsets.append(len(values))
    return bitmaps, offsets, values


def unpack_sparse_int8_rows(bitmaps: list[int], offsets: list[int], values: list[int], inputs: int) -> list[int]:
    """Decode :func:`pack_sparse_int8_rows`, validating its structural ABI."""
    if type(inputs) is not int or inputs <= 0:
        raise ValueError("inputs must be a positive integer")
    bitmap_words = (inputs + 31) // 32
    if len(offsets) < 1 or (len(offsets) - 1) * bitmap_words != len(bitmaps):
        raise ValueError("sparse bitmap/offset dimensions disagree")
    if offsets[0] != 0 or any(type(x) is not int or x < 0 for x in offsets):
        raise ValueError("sparse offsets must be nonnegative and start at zero")
    if any(offsets[i] > offsets[i + 1] for i in range(len(offsets) - 1)) or offsets[-1] != len(values):
        raise ValueError("sparse offsets are not monotonic or do not end at values")
    if any(type(x) is not int or not -128 <= x <= 127 for x in values):
        raise ValueError("sparse values contain a non-INT8 value")
    result: list[int] = []
    for row in range(len(offsets) - 1):
        row_bitmap = bitmaps[row * bitmap_words : (row + 1) * bitmap_words]
        cursor = offsets[row]
        end = offsets[row + 1]
        for index in range(inputs):
            present = (row_bitmap[index // 32] >> (index % 32)) & 1
            if present:
                if cursor >= end:
                    raise ValueError("sparse bitmap has too many nonzero entries")
                result.append(values[cursor])
                cursor += 1
            else:
                result.append(0)
        if cursor != end:
            raise ValueError("sparse bitmap has too few nonzero entries")
    return result


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


def _layer_norm(attention, prefix: str = "", final: bool = False, rows: int = 8) -> Phase:
    phase = attention._ln2_composed_phase() if prefix == "ln2_" else attention._ln1_composed_phase()
    changes = {
        "row_counter": (rows.bit_length(),), "row_lt": (rows.bit_length(),), "increment_row": (rows.bit_length(),),
        "row_pad": (rows.bit_length(), (rows * 64 - 1).bit_length()), "row_shift": ((rows * 64 - 1).bit_length(),), "column_pad": (6, (rows * 64 - 1).bit_length()), "flat_address": ((rows * 64 - 1).bit_length(),),
    }
    phase = _resize(phase, {prefix + k: v for k, v in changes.items()}, {prefix + "row_lt": rows})
    if final:
        # Namespace the unmodified ln1 arithmetic and reconnect its memory ABI.
        cells = re.findall(r"^(\w+) =", "\n".join(phase[0]), re.M)
        groups = re.findall(r"(?:comb )?group (\w+)", "\n".join(phase[1]))
        names = {x: "final_" + x for x in cells + groups}
        names.update({"block_input_q16_16": "block_output_q16_16", "ln1_gamma_q16_16": "final_gamma_q16_16", "ln1_beta_q16_16": "final_beta_q16_16", "ln1_output_q16_16": "final_output_q16_16"})
        phase = _rename(phase, names)
    return phase


def _causal(attention, *, split_denominator: bool = False, rows: int = 8) -> Phase:
    if type(rows) is not int or rows not in (8, 20):
        raise ValueError("causal row capacity must be 8 or 20")
    rw = rows.bit_length()
    vw = (rows * 64 - 1).bit_length()
    sw = (rows * rows * 16 - 1).bit_length()
    hw = (rows * 16 - 1).bit_length()
    changes = {
        "causal_row": (rw,), "causal_key": (rw,), "causal_row_lt": (rw,),
        "causal_key_le": (rw,), "causal_row_increment": (rw,), "causal_key_increment": (rw,),
        "causal_row_pad8": (rw, vw), "causal_row_shift6": (vw,),
        "causal_key_pad8": (rw, vw), "causal_key_shift6": (vw,),
        "causal_head_pad8": (5, vw), "causal_head_shift2": (vw,),
        "causal_lane_pad8": (3, vw), "causal_query_head_lane": (vw,),
        "causal_query_address": (vw,), "causal_key_address": (vw,),
        "causal_slot_head_key": (sw,), "causal_slot_address": (sw,),
        "causal_row_pad6": (rw, hw), "causal_row_shift4": (hw,),
        "causal_head_pad6": (5, hw), "causal_row_head_address": (hw,),
    }
    cells, wires, control = _resize(attention._causal_attention_phase(), changes, {"causal_row_lt": rows})
    # Score slots are [row,head,key] with key stride8, whereas Q/K/V are
    # [row,head,lane] with lane stride4.  They must not share that address.
    cells += [f"model_score_row = std_pad({rw}, {sw});", f"model_score_row_shift = std_lsh({sw});", f"model_score_head = std_pad(5, {sw});", f"model_score_head_shift = std_lsh({sw});", f"model_score_key = std_pad({rw}, {sw});"]
    text = "\n".join(wires)
    for old, new in {
        "causal_slot_head_key.left = causal_head_shift2.out;": "causal_slot_head_key.left = model_score_head_shift.out;",
        "causal_slot_head_key.right = causal_key_pad8.out;": "causal_slot_head_key.right = model_score_key.out;",
        "causal_slot_address.left = causal_row_shift6.out;": "causal_slot_address.left = model_score_row_shift.out;",
    }.items():
        if text.count(old) != 1:
            raise ValueError("causal score address ABI changed")
        text = text.replace(old, new)
    text += f"""
    model_score_row.in = causal_row.out;
    model_score_row_shift.left = model_score_row.out;
    model_score_row_shift.right = {sw}'d{7 if rows == 8 else 8};
    model_score_head.in = causal_head.out;
    model_score_head_shift.left = model_score_head.out;
    model_score_head_shift.right = {sw}'d{3 if rows == 8 else 4};
    model_score_key.in = causal_key.out;
"""
    if rows == 20:
        # Dense [row,head,key]: row*320 + head*20 + key.  The head stride
        # is formed as head*16 + head*4; constant shifts avoid multipliers.
        for axis, low_shift in (("row", 6), ("head", 2)):
            cells += [f"model_score_{axis}_low_shift = std_lsh({sw});",
                      f"model_score_{axis}_stride = std_add({sw});"]
            text += f"""
    model_score_{axis}_low_shift.left = model_score_{axis}.out;
    model_score_{axis}_low_shift.right = {sw}'d{low_shift};
    model_score_{axis}_stride.left = model_score_{axis}_shift.out;
    model_score_{axis}_stride.right = model_score_{axis}_low_shift.out;
"""
        text = text.replace("causal_slot_address.left = model_score_row_shift.out;",
                            "causal_slot_address.left = model_score_row_stride.out;")
        text = text.replace("causal_slot_head_key.left = model_score_head_shift.out;",
                            "causal_slot_head_key.left = model_score_head_stride.out;")
    if split_denominator:
        # A two-cycle memory write must not stretch the non-idempotent
        # denominator register update across both cycles.
        name = "causal_write_exp_accumulate_denominator"
        match = re.search(r"group " + name + r" \{(.*?)\n\s*\}", text, re.S)
        if match is None:
            raise ValueError("causal denominator group ABI changed")
        body = match[1]
        update = re.search(r"causal_denominator_add.left =.*?causal_denominator.write_en = 1'd1;", body, re.S)
        done = "(causal_denominator.done & attention_exp_q1_20.done) ? 1'd1"
        if update is None or body.count(done) != 1 or control.count(name + ";") != 1:
            raise ValueError("causal denominator update ABI changed")
        probability = body[:update.start()]
        write = body.replace(update[0], "", 1).replace(done, "attention_exp_q1_20.done", 1)
        accumulate = "group model_accumulate_denominator {" + probability + update[0] + "\n model_accumulate_denominator[done] = causal_denominator.done;\n}"
        text = text.replace(match[0], "group " + name + " {" + write + "\n}\n" + accumulate, 1)
        control = control.replace(name + ";", name + "; model_accumulate_denominator;", 1)
    return cells, [text], control


def _block_phases(block, attention, mlp, *, narrow_products: bool = False, rows: int = 8) -> list[Phase]:
    phases = [_layer_norm(attention, rows=rows), attention._initialize_zero_bias_phase()]
    def loop_geometry(phase, counter, comparison, increment, address, count):
        width = count.bit_length()
        return _resize(phase, {counter: (width,), comparison: (width,),
                              increment: (width,), address: (width, (count-1).bit_length())},
                       {comparison: count})
    def projection(prefix, source, inputs, outputs, bias, qdq=True):
        if qdq:
            phases.append(mlp._activation_qdq_phase(f"{prefix}_input_qdq", source, f"{prefix}_input_scale_q8_24", f"{prefix}_input_codes_i8", f"{prefix}_input_q16_16", rows * inputs, inputs, narrow_products=narrow_products))
        phases.append(mlp._gemv_phase(f"{prefix}_gemv", f"{prefix}_input_codes_i8", f"{prefix}_input_scale_q8_24", f"{prefix}_weight_codes_i8", f"{prefix}_accumulator_i64", rows, inputs, outputs, narrow_products=narrow_products))
        phases.append(mlp._requantize_phase(f"{prefix}_requant", f"{prefix}_accumulator_i64", f"{prefix}_weight_scale_q8_24", bias, f"{prefix}_output_scale_q8_24", f"{prefix}_post_weight_rescale_bias_q16_16", f"{prefix}_output_codes_i8", f"{prefix}_output_q16_16", rows * outputs, outputs))
    for prefix in ("q", "k", "v"):
        projection(prefix, "ln1_output_q16_16", 64, 64, "zero_bias_q16_16")
    phases.append(loop_geometry(attention._initialize_causal_slots_phase(), "causal_zero_counter", "causal_zero_lt", "causal_zero_increment", "causal_zero_address", rows * rows * 16))
    phases.append(_causal(attention, split_denominator=narrow_products, rows=rows))
    projection("out", "attention_context_q16_16", 64, 64, "out_bias_q16_16")
    phases.append(loop_geometry(attention._residual_add_phase(), "attention_residual_counter", "attention_residual_lt", "attention_residual_increment", "attention_residual_address", rows * 64))
    phases.append(_layer_norm(attention, "ln2_", rows=rows))
    projection("c_fc", "ln2_output_q16_16", 64, 256, "c_fc_bias_q16_16")
    phases.append(loop_geometry(mlp._gelu_phase(), "gelu_entry_counter", "gelu_entry_lt", "gelu_increment_entry", "gelu_entry_address", rows * 256))
    projection("c_proj", "gelu_output_q16_16", 256, 64, "c_proj_bias_q16_16")
    phases.append(loop_geometry(block._final_residual_phase(), "block_output_counter", "block_output_lt", "block_output_increment", "block_output_address", rows * 64))
    return phases


def _memory(name: str, width: int, count: int) -> str:
    return f"@external {name} = seq_mem_d1({width}, {count}, {(count - 1).bit_length()});"


def bram_bank_plan(width: int, count: int) -> dict[str, int]:
    """Return a legal XC7 BRAM36 geometry for a logical one-read memory.

    The Calyx ``seq_mem_d1`` declaration is a logical memory and its width
    and depth are not themselves legal RAMB36E1 configurations.  Keep this
    calculation in the compiler (rather than in a generated-SV annotation)
    so a later physical-memory pass can use one authenticated description for
    storage, address banking, and source-image serialization.
    """
    if type(width) is not int or type(count) is not int or width <= 0 or count <= 0:
        raise ValueError("memory width and count must be positive integers")
    # RAMB36E1 simple-dual-port legal width/depth pairs.  Widths are rounded
    # up to the next lane shape; unused high bits are padding, not data.
    shapes = ((1, 32768), (2, 16384), (4, 8192), (9, 4096),
              (18, 2048), (36, 1024), (72, 512))
    for physical_width, physical_depth in shapes:
        if width <= physical_width:
            banks = (count + physical_depth - 1) // physical_depth
            return {
                "logical_width": width,
                "logical_words": count,
                "banks": banks,
                "physical_width": physical_width,
                "physical_depth": physical_depth,
                "logical_words_per_bank": physical_depth,
                "capacity_bits": banks * physical_width * physical_depth,
            }
    raise ValueError(f"memory width {width} exceeds RAMB36E1 72-bit lane")


def alias_runtime_memories(futil: str, aliases: dict[str, str]) -> str:
    """Coalesce explicitly non-overlapping runtime memories in generated Futil.

    ``aliases`` maps an old cell name to another cell name.  The mapping is
    resolved transitively, the surviving declaration is enlarged to the
    largest logical depth in its alias class, and all cell references are
    rewritten.  Width mismatches are rejected rather than silently truncating
    data.  This pass is intentionally explicit: it does not infer liveness.
    """
    if not aliases:
        return futil
    declaration = re.compile(r"@external (\w+) = seq_mem_d1\((\d+), (\d+), (\d+)\);")
    records = {m[1]: (int(m[2]), int(m[3])) for m in declaration.finditer(futil)}
    def root(name: str) -> str:
        seen = set()
        while name in aliases:
            if name in seen:
                raise ValueError("cyclic runtime memory alias")
            seen.add(name)
            name = aliases[name]
        return name
    classes: dict[str, list[str]] = {}
    for old in aliases:
        if old not in records:
            raise ValueError(f"cannot alias undeclared runtime memory: {old}")
        target = root(old)
        if target not in records:
            raise ValueError(f"cannot alias to undeclared runtime memory: {target}")
        classes.setdefault(target, []).append(old)
    replacements: dict[str, str] = {}
    for target, members in classes.items():
        names = [target, *members]
        widths = {records[name][0] for name in names}
        if len(widths) != 1:
            raise ValueError(f"runtime memory alias width mismatch: {names}")
        width = widths.pop()
        count = max(records[name][1] for name in names)
        records[target] = (width, count)
        replacements.update({name: target for name in members})
    # Remove aliased declarations before replacing identifiers, then emit the
    # surviving declaration with a width-correct address field.
    def declaration_rewrite(match: re.Match[str]) -> str:
        name, width, count = match[1], int(match[2]), int(match[3])
        if name in replacements:
            return ""
        if name in records:
            width, count = records[name]
            index_width = max(1, (count - 1).bit_length())
            return f"@external {name} = seq_mem_d1({width}, {count}, {index_width});"
        return match[0]
    result = declaration.sub(declaration_rewrite, futil)
    for old, target in sorted(replacements.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"\b{re.escape(old)}\b", target, result)
    return result


def narrow_source_memory_words(futil: str, names: list[str]) -> str:
    """Store proven 32-bit source values in 32-bit memories with wide reads."""
    if not names:
        return futil
    declaration = re.compile(r"@external (\w+) = seq_mem_d1\((\d+), (\d+), (\d+)\);")
    selected = set(names)
    adapters: list[str] = []
    wires: list[str] = []
    def rewrite(match: re.Match[str]) -> str:
        name, width, count, index = match[1], int(match[2]), match[3], match[4]
        if name not in selected:
            return match[0]
        if width != 64:
            raise ValueError(f"source narrowing requires 64-bit declaration: {name}")
        adapter = name + "_wide"
        adapters.append(f"{adapter} = std_signext(32, 64);")
        wires.append(f"{adapter}.in = {name}.read_data;")
        return f"@external {name} = seq_mem_d1(32, {count}, {index});"
    result = declaration.sub(rewrite, futil)
    missing = selected - {m[1] for m in declaration.finditer(futil)}
    if missing:
        raise ValueError(f"cannot narrow undeclared source memory: {sorted(missing)}")
    for name in selected:
        adapter = name + "_wide"
        result = re.sub(rf"\b{re.escape(name)}\.read_data\b", adapter + ".out", result)
    result = result.replace("  cells {", "  cells {\n    " + "\n    ".join(adapters), 1)
    result = result.replace("  wires {", "  wires {\n    " + "\n    ".join(wires), 1)
    return result


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


def _banked_read(builder: Builder, group_name: str, prefix: str, memory_prefix: str,
                 banks: int, bank_address: str, local_address: str, width: int,
                 packed_lanes: int | None = None, lane_address: str | None = None,
                 lane_width: int = 16):
    """Read a depth-bounded banked table and mux its selected word.

    All physical banks are read in parallel.  The seven-bit bank selector is
    reduced through a balanced mux tree; unused leaves are constant zero.  The
    caller receives a Calyx group statement and the mux output expression.
    """
    leaf_count = 1 << (banks - 1).bit_length()
    bank_bits = leaf_count.bit_length() - 1
    for level in range(bank_bits):
        # Select the actual level bit.  A plain std_slice would always select
        # bit zero and would alias every bank except the first pair.
        builder.cell(f"{prefix}_bank_bit_{level}", "std_bit_slice", bank_bits, level, level, 1)
        builder.wires.append(f"{prefix}_bank_bit_{level}.in = {bank_address};")
    leaves = []
    assignments = []
    done_terms = []
    for bank in range(banks):
        name = f"{memory_prefix}_b{bank}"
        assignments += [f"{name}.addr0 = {local_address};", f"{name}.content_en = 1'd1;"]
        done_terms.append(f"{name}.done")
        leaves.append(f"{name}.read_data")
    leaves += [f"{width}'d0"] * (leaf_count - banks)
    for level in range(bank_bits):
        next_leaves = []
        for index in range(0, len(leaves), 2):
            mux = f"{prefix}_bank_mux_{level}_{index // 2}"
            builder.cell(mux, "std_mux", width)
            builder.wires.append(
                f"{mux}.cond = {prefix}_bank_bit_{level}.out; "
                f"{mux}.tru = {leaves[index + 1]}; {mux}.fal = {leaves[index]};"
            )
            next_leaves.append(f"{mux}.out")
        leaves = next_leaves
    value = leaves[0]
    if packed_lanes is not None:
        if packed_lanes != 8 or width != 64 or lane_address is None:
            raise ValueError("packed banked reads require 64-bit words, eight lanes, and a lane address")
        lane = f"{prefix}_lane"
        lane_pad = f"{prefix}_lane_pad"
        lane_shift = f"{prefix}_lane_shift"
        code_shift = f"{prefix}_code_shift"
        code_slice = f"{prefix}_code_slice"
        builder.cell(lane, "std_slice", lane_width, 3)
        builder.cell(lane_pad, "std_pad", 3, 64)
        builder.cell(lane_shift, "std_lsh", 64)
        builder.cell(code_shift, "std_rsh", 64)
        builder.cell(code_slice, "std_slice", 64, 8)
        builder.wires.append(
            f"{lane}.in = {lane_address}; "
            f"{lane_pad}.in = {lane}.out; "
            f"{lane_shift}.left = {lane_pad}.out; "
            f"{lane_shift}.right = 64'd3; "
            f"{code_shift}.left = {value}; "
            f"{code_shift}.right = {lane_shift}.out; "
            f"{code_slice}.in = {code_shift}.out;"
        )
        value = f"{code_slice}.out"
    group = builder.group(group_name, assignments, f"({' & '.join(done_terms)}) ? 1'd1")
    return group, value


def _orchestration(builder: Builder, block_control: str, final_control: str, lm_control: str, *, audit_checkpoints: bool = True, stream_lm_head: bool = False, stream_gemv_control: str | None = None, board_io: bool = False, generation_steps: int = 2) -> str:
    b = builder
    geometry = _load(ROOT / "scripts/pipeline/tinystories_generation_geometry.py", "orchestration_geometry").generation_geometry(generation_steps)
    rows, rw, sw = geometry.row_capacity, geometry.row_counter_width, geometry.step_counter_width
    aw, iw = geometry.row_address_width, geometry.token_index_width
    count = rows * 64
    cw, vw = count.bit_length(), (count - 1).bit_length()
    counter_specs = [("model_step", sw, f"{sw}'d{generation_steps}"), ("model_layer", 4, "4'd8"), ("model_row", rw, f"{rw}'d{rows}"), ("model_column", 7, "7'd64"), ("model_copy", cw, f"{cw}'d{count}"), ("model_logit", 16, "16'd50257")]
    if stream_lm_head:
        counter_specs.pop()  # GEMV's output counter owns the vocabulary index.
    if not stream_lm_head:
        counter_specs.insert(-1, ("model_logit_row", 4, "model_context_length.out"))
    for name, width, limit in counter_specs:
        b.counter(name, width, limit)
    b.cell("model_context_length", "std_reg", rw)
    b.cell("model_context_next", "std_add", rw)
    if stream_lm_head:
        b.cell("model_last_row", "std_sub", rw)
    b.cell("model_context_address", "std_slice", rw, aw)
    b.cell("model_layer_bank", "std_slice", 4, 3)
    b.cell("model_step_address", "std_slice", sw, iw)
    if board_io and generation_steps <= 2:
        b.cell("model_step_is_first", "std_not", 1)
        b.cell("model_token0_next", "std_mux", 16)
        b.cell("model_token1_next", "std_mux", 16)
        b.cell("model_token0", "std_reg", 16)
        b.cell("model_token1", "std_reg", 16)
        b.cell("model_token_select", "std_mux", 16)
    if board_io and generation_steps == 16:
        for index in range(16):
            b.cell(f"model_step_eq{index}", "std_eq", iw)
            b.cell(f"model_output_eq{index}", "std_eq", iw)
            b.cell(f"model_token{index}_next", "std_mux", 16)
            b.cell(f"model_token{index}", "std_reg", 16)
            b.cell(f"model_output_mux{index}", "std_mux", 16)
            previous = "16'd0" if index == 0 else f"model_output_mux{index-1}.out"
            b.wires.append(f"model_step_eq{index}.left = model_step_address.out; model_step_eq{index}.right = {iw}'d{index}; model_token{index}_next.cond = model_step_eq{index}.out; model_token{index}_next.tru = model_best_token.out; model_token{index}_next.fal = model_token{index}.out; model_output_eq{index}.left = token_index; model_output_eq{index}.right = {iw}'d{index}; model_output_mux{index}.cond = model_output_eq{index}.out; model_output_mux{index}.tru = model_token{index}.out; model_output_mux{index}.fal = {previous};")
        b.wires.append("token_id = model_output_mux15.out;")
    b.cell("model_row_address", "std_slice", rw, aw)
    b.cell("model_prompt_address", "std_slice", rw, 2)
    if board_io:
        for index in range(4):
            b.cell(f"model_prompt_eq{index}", "std_eq", 2)
        b.cell("model_prompt_pair01", "std_or", 1)
        b.cell("model_prompt_value01", "std_mux", 16)
        b.cell("model_prompt_value23", "std_mux", 16)
        b.cell("model_prompt_value", "std_mux", 16)
    b.cell("model_is_prompt", "std_lt", rw)
    b.cell("model_position_address", "std_pad", rw, 5)
    b.cell("model_column_address", "std_slice", 7, 6)
    if board_io:
        b.cell("model_token_column_shift", "std_rsh", 6)
        b.cell("model_token_column_word", "std_slice", 6, 3)
    b.cell("model_hidden_address", "std_cat", aw, 6, vw)
    b.cell("model_token_address", "std_cat", 16, 6, 22)
    b.cell("model_position_weight_address", "std_cat", 5, 6, 11)
    b.cell("model_copy_address", "std_slice", cw, vw)
    token_code_read = None
    token_scale_read = None
    token_code_value = "token_weight_codes_i8.read_data"
    token_scale_value = "token_weight_scale_q8_24.read_data"
    if board_io:
        b.cell("model_token_row_low", "std_slice", 16, 11)
        b.cell("model_token_bank_full", "std_rsh", 16)
        b.cell("model_token_scale_bank_full", "std_rsh", 16)
        b.cell("model_token_bank", "std_slice", 16, 5)
        b.cell("model_token_scale_bank", "std_slice", 16, 5)
        b.cell("model_token_code_local", "std_cat", 11, 3, 14)
        b.cell("model_token_scale_local", "std_slice", 16, 11)
        b.wires += [
            "model_token_row_low.in = context_tokens.read_data;",
            "model_token_bank_full.left = context_tokens.read_data;",
            "model_token_bank_full.right = 16'd11;",
            "model_token_scale_bank_full.left = context_tokens.read_data;",
            "model_token_scale_bank_full.right = 16'd11;",
            "model_token_bank.in = model_token_bank_full.out;",
            "model_token_scale_bank.in = model_token_scale_bank_full.out;",
            "model_token_column_shift.left = model_column_address.out;",
            "model_token_column_shift.right = 6'd3;",
            "model_token_column_word.in = model_token_column_shift.out;",
            "model_token_code_local.left = model_token_row_low.out;",
            "model_token_code_local.right = model_token_column_word.out;",
            "model_token_scale_local.in = context_tokens.read_data;",
        ]
        token_scale_read, token_scale_value = _banked_read(
            b, "model_read_token_scale", "model_token_scale", "token_weight_scale_q8_24",
            TOKEN_SCALE_BANKS, "model_token_scale_bank.out", "model_token_scale_local.out", 32)
        token_code_read, token_code_value = _banked_read(
            b, "model_read_token_codes", "model_token_code", "token_weight_codes_packed",
            PACKED_TOKEN_CODE_BANKS, "model_token_bank.out", "model_token_code_local.out", 64,
            packed_lanes=PACKED_TOKEN_CODE_LANES, lane_address="model_column_address.out", lane_width=6)
    if audit_checkpoints:
        b.cell("model_embedding_checkpoint_address", "std_cat", iw, vw, iw + vw)
        b.cell("model_block_step_layer", "std_cat", iw, 3, iw + 3)
        b.cell("model_block_checkpoint_address", "std_cat", iw + 3, vw, iw + 3 + vw)
        b.cell("model_ln_checkpoint_address", "std_cat", iw, vw, iw + vw)
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
    if board_io:
        b.wires.append(" ".join(
            [f"model_prompt_eq{index}.left = model_prompt_address.out; model_prompt_eq{index}.right = 2'd{index};"
             for index in range(4)]
            + [
                "model_prompt_pair01.left = model_prompt_eq0.out; model_prompt_pair01.right = model_prompt_eq1.out;",
                "model_prompt_value01.cond = model_prompt_eq0.out; model_prompt_value01.tru = prompt_0; model_prompt_value01.fal = prompt_1;",
                "model_prompt_value23.cond = model_prompt_eq2.out; model_prompt_value23.tru = prompt_2; model_prompt_value23.fal = prompt_3;",
                "model_prompt_value.cond = model_prompt_pair01.out; model_prompt_value.tru = model_prompt_value01.out; model_prompt_value.fal = model_prompt_value23.out;",
            ]
        ))
    wait = b.group("model_wait", ["model_wait_register.in = 1'd1;", "model_wait_register.write_en = 1'd1;"], "model_wait_register.done")
    init_length = b.group("model_init_length", [f"model_context_length.in = {rw}'d4;", "model_context_length.write_en = 1'd1;"], "model_context_length.done")
    read_prompt = b.read("model_read_prompt", [("prompt_tokens", "model_prompt_address.out")])
    copy_prompt = b.write("model_copy_prompt", [("context_tokens", "model_row_address.out", "model_prompt_value.out" if board_io else "prompt_tokens.read_data")])
    pad_prompt = b.write("model_pad_prompt", [("context_tokens", "model_row_address.out", "16'd0")])
    prompt = b.loop("model_row", f"if model_is_prompt.out with model_prompt_condition {{ seq {{ {read_prompt} {copy_prompt} }} }} else {{ {pad_prompt} }}")
    read_token = b.read("model_read_token", [("context_tokens", "model_row_address.out"), ("position_weight_scale_q8_24", "model_position_address.out")])
    if board_io:
        read_codes_position = b.read("model_read_position_code", [("position_weight_codes_i8", "model_position_weight_address.out")])
        read_token_scale = token_scale_read
        read_codes = token_code_read + read_codes_position
    else:
        read_token_scale = b.read("model_read_token_scale", [("token_weight_scale_q8_24", "context_tokens.read_data")])
        read_codes = b.read("model_read_embedding_codes", [("token_weight_codes_i8", "model_token_address.out"), ("position_weight_codes_i8", "model_position_weight_address.out")])
        token_scale_value = "token_weight_scale_q8_24.read_data"
        token_code_value = "token_weight_codes_i8.read_data"
    token_scale_assign = ""
    if board_io:
        b.cell("model_token_scale_signed", "std_signext", 32, 64)
        token_scale_assign = f"model_token_scale_signed.in = {token_scale_value};"
        token_scale_value = "model_token_scale_signed.out"
    for p in ("model_token", "model_position"):
        b.cell(p + "_signed", "std_signext", 8, 64)
        b.cell(p + "_product", "std_smult_pipe", 64)
    multiply_assignments = [f"model_token_signed.in = {token_code_value};", "model_token_product.left = model_token_signed.out;", f"model_token_product.right = {token_scale_value};", "model_token_product.go = 1'd1;", "model_position_signed.in = position_weight_codes_i8.read_data;", "model_position_product.left = model_position_signed.out;", "model_position_product.right = position_weight_scale_q8_24.read_data;", "model_position_product.go = 1'd1;"]
    if token_scale_assign:
        multiply_assignments.insert(0, token_scale_assign)
    multiply = b.group("model_embedding_multiply", multiply_assignments, "(model_token_product.done & model_position_product.done) ? 1'd1")
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
    if not stream_lm_head:
        b.cell("model_logit_row_address", "std_slice", 4, 3)
    if not stream_lm_head:
        b.cell("model_accumulator_address", "std_cat", 3, 16, 19)
    if audit_checkpoints and not stream_lm_head:
        b.cell("model_logits_address", "std_cat", 1, 19, 20)
    b.cell("model_logit_product", "std_smult_pipe", 64)
    b.cell("model_best_value", "std_reg", 64)
    b.cell("model_best_token", "std_reg", 16)
    b.cell("model_logit_is_better", "std_sgt", 64)
    if audit_checkpoints and not stream_lm_head:
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
model_last_row.left = model_context_length.out;
model_last_row.right = 4'd1;
comb group model_greedy_condition { model_logit_is_better.left = model_round_logit_result.out; model_logit_is_better.right = model_best_value.out; }
"""]
    if board_io and generation_steps <= 2:
        b.wires.append("model_step_is_first.in = model_step_address.out; model_token0_next.cond = model_step_is_first.out; model_token0_next.tru = model_best_token.out; model_token0_next.fal = model_token0.out; model_token1_next.cond = model_step_address.out; model_token1_next.tru = model_best_token.out; model_token1_next.fal = model_token1.out; model_token_select.cond = token_index; model_token_select.tru = model_token1.out; model_token_select.fal = model_token0.out; token_id = model_token_select.out;")
    logit_index = "lm_gemv_output_counter.out" if stream_lm_head else "model_logit.out"
    init_greedy = b.group("model_init_greedy", ["model_best_value.in = 64'd9223372036854775808;", "model_best_value.write_en = 1'd1;", "model_best_token.in = 16'd0;", "model_best_token.write_en = 1'd1;"], "(model_best_value.done & model_best_token.done) ? 1'd1")
    logit_scale_read = None
    logit_scale_value = "token_weight_scale_q8_24.read_data"
    if board_io:
        b.cell("model_logit_scale_bank_full", "std_rsh", 16)
        b.cell("model_logit_scale_bank", "std_slice", 16, 5)
        b.cell("model_logit_scale_local", "std_slice", 16, 11)
        b.wires += [
            f"model_logit_scale_bank_full.left = {logit_index};",
            "model_logit_scale_bank_full.right = 16'd11;",
            "model_logit_scale_bank.in = model_logit_scale_bank_full.out;",
            f"model_logit_scale_local.in = {logit_index};",
        ]
        logit_scale_read, logit_scale_value = _banked_read(
            b, "model_read_logit_scale", "model_logit_scale", "token_weight_scale_q8_24",
            TOKEN_SCALE_BANKS, "model_logit_scale_bank.out", "model_logit_scale_local.out", 32)
    if stream_lm_head:
        read_logit = (logit_scale_read if board_io else b.read("model_read_logit", [("token_weight_scale_q8_24", logit_index)]))
        logit_value = "lm_gemv_accumulator.out"
    else:
        if board_io:
            read_logit = b.read("model_read_logit", [("lm_accumulator_i64", "model_accumulator_address.out")]) + logit_scale_read
        else:
            read_logit = b.read("model_read_logit", [("lm_accumulator_i64", "model_accumulator_address.out"), ("token_weight_scale_q8_24", "model_logit.out")])
        logit_value = "lm_accumulator_i64.read_data"
    logit_scale_assign = ""
    if board_io:
        logit_scale_assign = f"model_token_scale_signed.in = {logit_scale_value};"
        logit_scale_value = "model_token_scale_signed.out"
    logit_assignments = [f"model_logit_product.left = {logit_value};", f"model_logit_product.right = {logit_scale_value};", "model_logit_product.go = 1'd1;"]
    if logit_scale_assign:
        logit_assignments.insert(0, logit_scale_assign)
    mul_logit = b.group("model_multiply_logit", logit_assignments, "model_logit_product.done")
    round_logit = b.round("model_round_logit", "model_logit_product.out", 32)
    write_logit = ""
    if audit_checkpoints and not stream_lm_head:
        write_logit = b.write("model_write_logit", [("model_logits", "model_logits_address.out", "model_round_logit_result.out")])
    greedy = b.group("model_update_greedy", ["model_best_value.in = model_round_logit_result.out;", "model_best_value.write_en = 1'd1;", f"model_best_token.in = {logit_index};", "model_best_token.write_en = 1'd1;"], "(model_best_value.done & model_best_token.done) ? 1'd1")
    consume_logit = read_logit + mul_logit + round_logit + write_logit + f"if model_logit_is_better.out with model_greedy_condition {{ {greedy} }}"
    if stream_lm_head:
        # Consume each scalar accumulator before GEMV advances to the next
        # vocabulary entry and resets it. No logits memory is materialized.
        if stream_gemv_control is None:
            raise ValueError("streamed LM head requires a GEMV control section")
        advance = "lm_gemv_increment_output_counter;"
        if stream_gemv_control.count(advance) != 1:
            raise ValueError("streamed LM head requires one output advance boundary")
        streamed = stream_gemv_control.replace(advance, consume_logit + advance)
        logits = lm_control + init_greedy + streamed
        lm_control = ""
    else:
        logit_scan = b.loop("model_logit", consume_logit)
        logits = b.loop("model_logit_row", init_greedy + logit_scan)
    if board_io and generation_steps <= 2:
        feedback = b.group("model_commit_feedback", [
            "selected_tokens.addr0 = model_step_address.out;", "selected_tokens.content_en = 1'd1;", "selected_tokens.write_en = 1'd1;", "selected_tokens.write_data = model_best_token.out;",
            "context_tokens.addr0 = model_context_address.out;", "context_tokens.content_en = 1'd1;", "context_tokens.write_en = 1'd1;", "context_tokens.write_data = model_best_token.out;",
            "model_token0.in = model_token0_next.out;", "model_token0.write_en = 1'd1;", "model_token1.in = model_token1_next.out;", "model_token1.write_en = 1'd1;",
        ], "(selected_tokens.done & context_tokens.done) ? 1'd1")
    elif board_io:
        feedback = b.group("model_commit_feedback", [
            "selected_tokens.addr0 = model_step_address.out;", "selected_tokens.content_en = 1'd1;", "selected_tokens.write_en = 1'd1;", "selected_tokens.write_data = model_best_token.out;",
            "context_tokens.addr0 = model_context_address.out;", "context_tokens.content_en = 1'd1;", "context_tokens.write_en = 1'd1;", "context_tokens.write_data = model_best_token.out;",
            *[f"model_token{index}.in = model_token{index}_next.out;" + " model_token%d.write_en = 1'd1;" % index for index in range(16)],
        ], "(selected_tokens.done & context_tokens.done) ? 1'd1")
    else:
        feedback = b.write("model_commit_feedback", [("selected_tokens", "model_step_address.out", "model_best_token.out"), ("context_tokens", "model_context_address.out", "model_best_token.out")])
    next_context = b.group("model_next_context", ["model_context_next.left = model_context_length.out;", f"model_context_next.right = {rw}'d1;", "model_context_length.in = model_context_next.out;", "model_context_length.write_en = 1'd1;"], "model_context_length.done")
    final_copy = b.loop("model_copy", read_ln + copy_ln) if audit_checkpoints else ""
    steps = b.loop("model_step", embedding + blocks + final_control + final_copy + lm_control + logits + feedback + next_context)
    if generation_steps == 16:
        b.wires = [wire.replace("model_is_prompt.right = 4'd4;", "model_is_prompt.right = 5'd4;").replace("model_last_row.right = 4'd1;", "model_last_row.right = 5'd1;") for wire in b.wires]
    return f"seq {{ while model_valid_not.out with model_wait_condition {{ {wait} }} {init_length} {prompt} {steps} }}"


def generate_model_kernel(oracle_path: Path = ORACLE, *, host_second_token=None, host_intermediate_states=None, production: bool = False, generation_steps: int = 2, audit_checkpoints: bool | None = None) -> CalyxArtifact:
    if type(generation_steps) is not int or generation_steps not in (1, 2, 16):
        raise ValueError("generation_steps must be 1, 2, or 16 (authenticated oracle prefix)")
    if host_second_token is not None:
        raise ValueError("host_second_token_forbidden")
    if audit_checkpoints is None:
        audit_checkpoints = not production
    if host_intermediate_states is not None:
        raise ValueError("host_intermediate_states_forbidden")
    geometry = _load(ROOT / "scripts/pipeline/tinystories_generation_geometry.py", "model_generation_geometry").generation_geometry(generation_steps)
    if generation_steps == 16:
        capture = _load(ROOT / "TinyStories/capture_fixed_point_continuation_oracle.py", "continuation_oracle_for_calyx")
        continuation = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-point-continuation-oracle.json").read_text())
        capture.verify_continuation_oracle(continuation)
        oracle = json.loads(Path(oracle_path).read_text())
        if oracle.get("artifact_sha256") != continuation["identity"]["legacy_artifact_sha256"]:
            raise ValueError("sixteen-step oracle must retain the authenticated two-step model identity")
    else:
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
            count *= (geometry.row_capacity // 4) ** 2 if name in {"attention_score_q8", "attention_delta_q8", "attention_exp_q1_20"} else geometry.row_capacity // 4
        memory_cells.append(_memory(name, width, count))
    new_sources = {
        "prompt_tokens": {"kind": "prompt", "width": 16, "elements": 4},
        "position_weight_codes_i8": {"kind": "code", "buffer": "position_embedding.weight", "width": 8, "elements": 32 * 64},
        "position_weight_scale_q8_24": {"kind": "scale", "buffer": "position_embedding.weight", "width": 64, "elements": 32},
        "final_gamma_q16_16": {"kind": "parameter", "buffer": "final_ln.weight", "width": 64, "elements": 64},
        "final_beta_q16_16": {"kind": "parameter", "buffer": "final_ln.bias", "width": 64, "elements": 64},
        "lm_input_scale_q8_24": {"kind": "scale", "buffer": "activation::lm_head.input", "width": 64, "elements": 64},
    }
    if production:
        for bank in range(PACKED_TOKEN_CODE_BANKS):
            new_sources[f"token_weight_codes_packed_b{bank}"] = {
                "kind": "code", "buffer": "token_embedding.weight", "width": 64,
                "elements": TOKEN_CODE_BANK_DEPTH,
                "banked": {"source_elements": 50257 * 64, "bank": bank, "banks": PACKED_TOKEN_CODE_BANKS, "depth": TOKEN_CODE_BANK_DEPTH, "layout": "token_rows_2048_then_hidden_packed_i8", "lanes": PACKED_TOKEN_CODE_LANES},
            }
        for bank in range(TOKEN_SCALE_BANKS):
            new_sources[f"token_weight_scale_q8_24_b{bank}"] = {
                "kind": "scale", "buffer": "token_embedding.weight", "width": 32,
                "elements": TOKEN_SCALE_BANK_DEPTH,
                "banked": {"source_elements": 50257, "bank": bank, "banks": TOKEN_SCALE_BANKS, "depth": TOKEN_SCALE_BANK_DEPTH, "layout": "contiguous_token_rows"},
            }
    else:
        old_sources = {
            "token_weight_codes_i8": {"kind": "code", "buffer": "token_embedding.weight", "width": 8, "elements": 50257 * 64},
            "token_weight_scale_q8_24": {"kind": "scale", "buffer": "token_embedding.weight", "width": 64, "elements": 50257},
        }
        new_sources = {"prompt_tokens": new_sources.pop("prompt_tokens"), **old_sources, **new_sources}
    sources.update(new_sources)
    memory_cells += [_memory(name, record["width"], record["elements"]) for name, record in new_sources.items()]
    if production and audit_checkpoints:
        # Explicit diagnostic builds retain the same production arithmetic and
        # schedule while exposing bounded semantic checkpoints.  They are not
        # the BRAM production image and are used only for localization.
        hardware = {
            "context_tokens": (16, geometry.row_capacity),
            "selected_tokens": (16, geometry.output_slots),
            "model_embedding": (64, generation_steps * geometry.row_capacity * 64),
            "model_token_embedding": (64, generation_steps * geometry.row_capacity * 64),
            "model_position_embedding": (64, generation_steps * geometry.row_capacity * 64),
            "model_block_outputs": (64, generation_steps * geometry.row_capacity * 64 * 8),
            "model_final_ln": (64, generation_steps * geometry.row_capacity * 64),
            "final_output_q16_16": (64, geometry.row_capacity * 64),
            "lm_input_codes_i8": (8, geometry.row_capacity * 64),
            "lm_input_q16_16": (64, geometry.row_capacity * 64),
            # The production LM head streams one vocabulary row at a time;
            # retain only that accumulator in an audit build as well.
            "lm_accumulator_i64": (64, 50257),
        }
    elif production:
        # The streamed LM head reuses one vocabulary-row accumulator for each
        # real context row; it never materializes rows*vocabulary results.
        hardware = {"context_tokens": (16, geometry.row_capacity), "selected_tokens": (16, geometry.output_slots), "final_output_q16_16": (64, geometry.row_capacity * 64), "lm_input_codes_i8": (8, geometry.row_capacity * 64), "lm_input_q16_16": (64, geometry.row_capacity * 64)}
    else:
        hardware = {"context_tokens": (16, 8), "selected_tokens": (16, 2), "model_embedding": (64, 1024), "model_token_embedding": (64, 1024), "model_position_embedding": (64, 1024), "model_block_outputs": (64, 8192), "model_final_ln": (64, 1024), "final_output_q16_16": (64, 512), "lm_input_codes_i8": (8, 512), "lm_input_q16_16": (64, 512), "lm_accumulator_i64": (64, 524288), "model_logits": (64, 1048576)}
    memory_cells += [_memory(name, *descriptor) for name, descriptor in hardware.items()]
    phases = _block_phases(block, attention, mlp, narrow_products=production, rows=geometry.row_capacity)
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
    final_phase = _layer_norm(attention, final=True, rows=geometry.row_capacity)
    qdq_phase = mlp._activation_qdq_phase("lm_input_qdq", "final_output_q16_16", "lm_input_scale_q8_24", "lm_input_codes_i8", "lm_input_q16_16", geometry.row_capacity * 64, 64, narrow_products=production)
    gemv_phase = mlp._gemv_phase(
        "lm_gemv", "lm_input_codes_i8", "lm_input_scale_q8_24",
        "token_weight_codes_packed", "lm_accumulator_i64",
        1 if production else 8, 64, 50257,
        input_row_expr="model_last_row.out" if production else None,
        input_row_width=geometry.context_length_width if production else None,
        input_address_width_override=geometry.row_address_width + 6 if production else None,
        write_trace=not production,
        banked_weights=("token_weight_codes_packed", PACKED_TOKEN_CODE_BANKS, 14) if production else None,
        narrow_products=production,
        packed_weight=production,
    )
    # Restrict expensive vocabulary projections to real context rows.
    gemv_phase = (gemv_phase[0], [w.replace("lm_gemv_row_lt.right = 4'd8;", "lm_gemv_row_lt.right = model_context_length.out;") for w in gemv_phase[1]], gemv_phase[2])
    for cells, wires, _ in (final_phase, qdq_phase, gemv_phase):
        b.cells += cells
        b.wires += wires
    control = _orchestration(
        b,
        "\n".join(p[2] for p in phases),
        final_phase[2],
        qdq_phase[2] if production else qdq_phase[2] + gemv_phase[2],
        audit_checkpoints=audit_checkpoints,
        stream_lm_head=production,
        stream_gemv_control=gemv_phase[2] if production else None,
        board_io=production,
        generation_steps=generation_steps,
    )
    futil = '''// Compiler-owned exact model orchestration; no imported hand-written RTL.
import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";
''' + (f"component main(@go start: 1, valid: 1, token_index: {geometry.token_index_width}, prompt_0: 16, prompt_1: 16, prompt_2: 16, prompt_3: 16) -> (@done done: 1, token_id: 16) {{" if production else "component main(@go start: 1, valid: 1) -> (@done done: 1) {") + '''
  cells {
''' + mlp._indent_lines(b.cells, 4) + "\n  }\n  wires {\n" + mlp._indent_lines(b.wires, 4) + "\n  }\n  control {\n" + control + "\n  }\n}\n"
    if production:
        # Authenticated scale/parameter tensors have been range-checked to
        # signed 32 bits. Store them narrowly and sign-extend at the consumer;
        # this halves the physical width without changing arithmetic values.
        narrow_names = [
            name for name, record in sources.items()
            if record.get("width") == 64 and record.get("kind") in {"scale", "parameter"}
        ]
        futil = narrow_source_memory_words(futil, narrow_names)
        for name in narrow_names:
            sources[name]["width"] = 32
        # These accumulators execute serially on the shared GEMV datapath and
        # are never live at the same time. Keep the alias set explicit rather
        # than attempting heuristic liveness inference.
        futil = alias_runtime_memories(
            futil,
            {
                "k_accumulator_i64": "q_accumulator_i64",
                "v_accumulator_i64": "q_accumulator_i64",
                "out_accumulator_i64": "q_accumulator_i64",
                "c_proj_accumulator_i64": "q_accumulator_i64",
                # Every listed INT8 code buffer is a 1,280-word transient:
                # its producer/consumer completes before the next projection
                # starts, and no later phase retains the codes.
                "k_input_codes_i8": "q_input_codes_i8",
                "v_input_codes_i8": "q_input_codes_i8",
                "out_input_codes_i8": "q_input_codes_i8",
                "q_output_codes_i8": "q_input_codes_i8",
                "k_output_codes_i8": "q_input_codes_i8",
                "v_output_codes_i8": "q_input_codes_i8",
                "out_output_codes_i8": "q_input_codes_i8",
                "lm_input_codes_i8": "q_input_codes_i8",
                "c_proj_output_codes_i8": "c_fc_input_codes_i8",
                "c_proj_input_codes_i8": "c_fc_output_codes_i8",
                # GELU has consumed c_fc_output_q16_16 before the c_proj
                # input Q/DQ phase writes c_proj_input_q16_16.  Both are
                # 64-bit, rows*256-word transient buffers, so they can share
                # storage without changing the phase ordering or ABI.
                "c_proj_input_q16_16": "c_fc_output_q16_16",
                "attention_denominator_q1_20": "attention_maximum_q8",
            },
        )
    if generation_steps == 16:
        # The physical storage is provisioned for the largest context, but a
        # step must execute only its real rows.  Running padded future rows
        # changes shared intermediate memories and was observed to change the
        # first selected token (1544 versus the authenticated 11).  Keep the
        # capacity static while binding every row loop to the live context.
        futil = re.sub(
            r"(\b(?:\w+_row_lt|row_lt)\.right = )5'd20;",
            r"\1model_context_length.out;",
            futil,
        )
    # Publish the physical bank geometry alongside the logical Calyx contract.
    # This is deliberately metadata-only for now: the upcoming banked-memory
    # lowering consumes it, while simulation continues to use the logical
    # ``seq_mem_d1`` ABI unchanged.
    runtime_bram_plan = {}
    for match in re.finditer(r"@external (\w+) = seq_mem_d1\((\d+), (\d+), (\d+)\);", futil):
        name, width, count = match[1], int(match[2]), int(match[3])
        if count >= 512:
            runtime_bram_plan[name] = bram_bank_plan(width, count)
    provenance = {
        "schema": SCHEMA, "oracle_sha256": oracle["artifact_sha256"],
        "futil_sha256": _sha(futil.encode()), "base_block_futil_sha256": _sha(base.encode()),
        "compiler_sources": {str(Path(module.__file__).relative_to(ROOT)): _sha(Path(module.__file__).read_bytes()) for module in (block, attention, mlp)},
        "orchestrator_sha256": _sha(Path(__file__).read_bytes()),
        "schedule": {"layers": list(range(8)), "shared_block_datapaths": 1, "row_capacity": geometry.row_capacity, "real_context_lengths": list(geometry.real_context_lengths), "padded_future_rows": "causally_disconnected_from_real_rows", "lm_head_rows": "real_context_only", "vocabulary": 50257, "vocabulary_storage_stride": 65536},
        "source_memories": sources,
        "hardware_owned_memories": sorted(set(re.findall(r"@external (\w+) =", futil)) - set(sources)),
        "feedback": "greedy_last_real_row -> context_tokens[context_length] -> token_embedding",
        "claims": {"compiler_owned_control": True, "existing_arithmetic_generators_modified": production, "simulation_checkpoints": bool(audit_checkpoints), "sv_execution_verified": False, "board_executed": False, "board_fit_verified": False},
        "production_memory_contract": {"audit_checkpoint_memories": [] if production else ["model_embedding", "model_token_embedding", "model_position_embedding", "model_block_outputs", "model_final_ln", "model_logits"], "full_logits_storage": not production, "streamed_argmax": True},
        "runtime_bram_bank_plan": runtime_bram_plan,
    }
    provenance["schedule"]["generation_steps"] = generation_steps
    provenance["schedule"]["real_context_lengths"] = list(geometry.real_context_lengths)
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
        if record.get("banked"):
            layout = record["banked"]["layout"]
            bank = int(record["banked"]["bank"])
            depth = int(record["banked"]["depth"])
            if layout == "token_rows_2048_then_hidden_packed_i8":
                rows_per_bank = depth // PACKED_TOKEN_CODE_LANES
                start = bank * rows_per_bank * 64
                packed_words = pack_token_code_words(value[start:start + rows_per_bank * 64].tolist())
                # Source memories are serialized as signed int64 words, while
                # packing is defined over the complete 64-bit bit pattern.
                # Convert high-bit words to their two's-complement int64
                # representation before constructing the torch tensor.
                value = torch.tensor(
                    [word - (1 << 64) if word >= (1 << 63) else word for word in packed_words],
                    dtype=torch.int64,
                )
            elif layout in {"token_rows_256_then_hidden", "token_rows_512_then_hidden"}:
                row_stride = 64
                rows_per_bank = depth // row_stride
                start = bank * rows_per_bank * row_stride
                value = value[start:start + depth]
            elif layout == "contiguous_token_rows":
                start = bank * depth
                value = value[start:start + depth]
            else:
                raise ValueError(f"unknown banked source layout: {layout}")
            if value.numel() < depth:
                import torch
                value = torch.cat([value, torch.zeros(depth - value.numel(), dtype=value.dtype)])
        value = value.detach().cpu().to(torch.int64).flatten().contiguous()
        if value.numel() != record["elements"]:
            raise ValueError(f"source memory shape mismatch: {name}")
        sources[name] = value
    return sources
