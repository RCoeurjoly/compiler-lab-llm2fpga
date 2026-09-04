#!/usr/bin/env python3
"""Lower the declared exact serial-GEMV descriptor to defined Calyx IR.

This is intentionally a narrow compiler stage.  It consumes only the operation
introduced by the pinned Torch-MLIR legalizer; it never inspects SCF or a
reference RTL tree.  The generated component has explicit signed i64 MAC state
and address/counter state.  Its companion trace is a deterministic address/data
schedule used to prove the prescribed ascending visit order before full-model
composition is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any


_OPERATION = re.compile(
    r'"llm2fpga\.serial_gemv"\([^)]*\)\s*'
    r"\{(?P<attrs>[^}]*)\}\s*:\s*"
    r"\(tensor<(?P<rows>\d+)x(?P<inputs>\d+)xi64>,\s*"
    r"tensor<(?P<outputs>\d+)x(?P<weight_inputs>\d+)xi64>\)\s*"
    r"->\s*tensor<(?P<result_rows>\d+)x(?P<result_outputs>\d+)xi64>"
)
_INT_ATTRIBUTE = re.compile(r"\b(?P<name>rows|outputs|inputs)\s*=\s*(?P<value>\d+)\s*:\s*i64")
_MAC_ORDER = re.compile(r'\bmac_order\s*=\s*"(?P<value>[^"]+)"')


@dataclass(frozen=True)
class SerialGemvDescriptor:
    rows: int
    outputs: int
    inputs: int
    mac_order: str


@dataclass(frozen=True)
class CalyxArtifact:
    mlir: str
    provenance: dict[str, Any]


def _ceil_log2(value: int) -> int:
    return max(1, (value - 1).bit_length())


def parse_descriptor_text(text: str) -> SerialGemvDescriptor:
    """Parse exactly one fully static legalized serial-GEMV operation."""
    match = _OPERATION.search(text)
    if match is None:
        raise ValueError("exact_serial_gemv_descriptor: expected static llm2fpga.serial_gemv")
    attrs = {item.group("name"): int(item.group("value")) for item in _INT_ATTRIBUTE.finditer(match.group("attrs"))}
    mac_order = _MAC_ORDER.search(match.group("attrs"))
    if mac_order is None or mac_order.group("value") != "ascending_i64_wrap":
        raise ValueError("exact_serial_gemv_descriptor: mac_order must be ascending_i64_wrap")
    required = {"rows", "outputs", "inputs"}
    if set(attrs) != required:
        raise ValueError("exact_serial_gemv_descriptor: requires rows, outputs, and inputs")
    descriptor = SerialGemvDescriptor(
        rows=attrs["rows"], outputs=attrs["outputs"], inputs=attrs["inputs"], mac_order=mac_order.group("value")
    )
    shape = {name: int(match.group(name)) for name in ("rows", "inputs", "outputs", "weight_inputs", "result_rows", "result_outputs")}
    if (
        shape["rows"] != descriptor.rows
        or shape["inputs"] != descriptor.inputs
        or shape["outputs"] != descriptor.outputs
        or shape["weight_inputs"] != descriptor.inputs
        or shape["result_rows"] != descriptor.rows
        or shape["result_outputs"] != descriptor.outputs
    ):
        raise ValueError("exact_serial_gemv_descriptor: attributes and static tensor shapes disagree")
    return descriptor


def iter_serial_address_data_trace(descriptor: SerialGemvDescriptor):
    """Yield the exact ascending address/data schedule for a descriptor.

    The data fields are deterministic compiler-owned test-memory contents
    (two's-complement i64 address values).  This validates the visit order and
    wrapping MAC schedule independently of model payload transport.
    """
    accumulator_mask = (1 << 64) - 1
    for row in range(descriptor.rows):
        for output in range(descriptor.outputs):
            accumulator = 0
            for index in range(descriptor.inputs):
                activation_address = row * descriptor.inputs + index
                weight_address = output * descriptor.inputs + index
                activation_data = activation_address
                weight_data = weight_address
                accumulator = (accumulator + activation_data * weight_data) & accumulator_mask
                yield {
                    "row": row,
                    "output": output,
                    "input": index,
                    "activation_address": activation_address,
                    "activation_data": activation_data,
                    "weight_address": weight_address,
                    "weight_data": weight_data,
                    "accumulator_u64": accumulator,
                }


def serial_address_data_trace(descriptor: SerialGemvDescriptor) -> list[dict[str, int]]:
    """Materialize a trace for small test descriptors only."""
    return list(iter_serial_address_data_trace(descriptor))


def trace_sha256(trace: list[dict[str, int]]) -> str:
    return hashlib.sha256(json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stream_trace_sha256(descriptor: SerialGemvDescriptor) -> str:
    """Hash the canonical JSON trace without materializing model-sized traces."""
    digest = hashlib.sha256()
    digest.update(b"[")
    for index, entry in enumerate(iter_serial_address_data_trace(descriptor)):
        if index:
            digest.update(b",")
        digest.update(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"]")
    return digest.hexdigest()


def _memory_ports(name: str, depth: int, address_width: int, external: bool) -> str:
    suffix = " {external = true}" if external else ""
    return (
        f"    %{name}.addr0, %{name}.clk, %{name}.reset, %{name}.content_en, %{name}.write_en, "
        f"%{name}.write_data, %{name}.read_data, %{name}.done = "
        f"calyx.seq_mem @{name} <[{depth}] x 64> [{address_width}]{suffix} : "
        f"i{address_width}, i1, i1, i1, i1, i64, i64, i1"
    )


def _kernel(descriptor: SerialGemvDescriptor) -> str:
    component = f"llm2fpga_serial_gemv_{descriptor.outputs}_{descriptor.inputs}"
    activation_depth = descriptor.rows * descriptor.inputs
    weight_depth = descriptor.outputs * descriptor.inputs
    result_depth = descriptor.rows * descriptor.outputs
    activation_width = _ceil_log2(activation_depth)
    weight_width = _ceil_log2(weight_depth)
    result_width = _ceil_log2(result_depth)
    return f'''  // generated_from_descriptor rows={descriptor.rows} outputs={descriptor.outputs} inputs={descriptor.inputs} mac_order={descriptor.mac_order}
  calyx.component @{component}(%clk: i1 {{clk}}, %reset: i1 {{reset}}, %go: i1 {{go}}) -> (%done: i1 {{done}}) {{
{_memory_ports("activation", activation_depth, activation_width, False)}
{_memory_ports("weights", weight_depth, weight_width, False)}
{_memory_ports("results", result_depth, result_width, False)}
    %true = hw.constant true
    %false = hw.constant false
    %zero_i64 = hw.constant 0 : i64
    %one_i64 = hw.constant 1 : i64
    %input_limit_i64 = hw.constant {descriptor.inputs} : i64
    %output_limit_i64 = hw.constant {descriptor.outputs} : i64
    %k_counter.in, %k_counter.write_en, %k_counter.clk, %k_counter.reset, %k_counter.out, %k_counter.done = calyx.register @k_counter : i64, i1, i1, i1, i64, i1
    %output_counter.in, %output_counter.write_en, %output_counter.clk, %output_counter.reset, %output_counter.out, %output_counter.done = calyx.register @output_counter : i64, i1, i1, i1, i64, i1
    %accumulator.in, %accumulator.write_en, %accumulator.clk, %accumulator.reset, %accumulator.out, %accumulator.done = calyx.register @accumulator : i64, i1, i1, i1, i64, i1
    %mac_mul.clk, %mac_mul.reset, %mac_mul.go, %mac_mul.left, %mac_mul.right, %mac_mul.out, %mac_mul.done = calyx.std_mult_pipe @mac_mul : i1, i1, i1, i64, i64, i64, i1
    %mac_add.left, %mac_add.right, %mac_add.out = calyx.std_add @mac_add : i64, i64, i64
    %next_k.left, %next_k.right, %next_k.out = calyx.std_add @next_k : i64, i64, i64
    %next_output.left, %next_output.right, %next_output.out = calyx.std_add @next_output : i64, i64, i64
    %k_less.left, %k_less.right, %k_less.out = calyx.std_lt @k_less : i64, i64, i1
    %output_less.left, %output_less.right, %output_less.out = calyx.std_lt @output_less : i64, i64, i1
    calyx.wires {{
      calyx.comb_group @k_not_done {{
        calyx.assign %k_less.left = %k_counter.out : i64
        calyx.assign %k_less.right = %input_limit_i64 : i64
      }}
      calyx.comb_group @output_not_done {{
        calyx.assign %output_less.left = %output_counter.out : i64
        calyx.assign %output_less.right = %output_limit_i64 : i64
      }}
      calyx.group @mac_step {{
        calyx.assign %mac_mul.left = %activation.read_data : i64
        calyx.assign %mac_mul.right = %weights.read_data : i64
        calyx.assign %mac_mul.go = %true : i1
        calyx.assign %mac_add.left = %accumulator.out : i64
        calyx.assign %mac_add.right = %mac_mul.out : i64
        calyx.assign %accumulator.in = %mac_add.out : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %next_k.left = %k_counter.out : i64
        calyx.assign %next_k.right = %one_i64 : i64
        calyx.assign %k_counter.in = %next_k.out : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %activation.content_en = %true : i1
        calyx.assign %weights.content_en = %true : i1
        calyx.assign %results.content_en = %true : i1
        calyx.assign %results.write_en = %false : i1
        calyx.group_done %k_counter.done : i1
      }}
      calyx.group @advance_output {{
        calyx.assign %next_output.left = %output_counter.out : i64
        calyx.assign %next_output.right = %one_i64 : i64
        calyx.assign %output_counter.in = %next_output.out : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %k_counter.in = %zero_i64 : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.group_done %output_counter.done : i1
      }}
    }}
    calyx.control {{
      calyx.while %output_less.out with @output_not_done {{
        calyx.seq {{
          calyx.while %k_less.out with @k_not_done {{
            calyx.enable @mac_step
          }}
          calyx.enable @advance_output
        }}
      }}
    }}
  }}
'''


def _kernel_runtime(descriptor: SerialGemvDescriptor) -> str:
    """Emit the operational R×M×K Calyx control/data path.

    The memory address registers are flat addresses: activation advances over
    K then is restored to the row base for each output; weight advances over K
    for every output and is reset between rows; result advances once per M.
    """
    component = f"llm2fpga_serial_gemv_{descriptor.outputs}_{descriptor.inputs}"
    activation_depth = descriptor.rows * descriptor.inputs
    weight_depth = descriptor.outputs * descriptor.inputs
    result_depth = descriptor.rows * descriptor.outputs
    aw, ww, rw = map(_ceil_log2, (activation_depth, weight_depth, result_depth))
    return f'''  // generated_from_descriptor runtime rows={descriptor.rows} outputs={descriptor.outputs} inputs={descriptor.inputs} mac_order={descriptor.mac_order}
  calyx.component @{component}(%clk: i1 {{clk}}, %reset: i1 {{reset}}, %go: i1 {{go}}) -> (%done: i1 {{done}}) {{
{_memory_ports("activation", activation_depth, aw, False)}
{_memory_ports("weights", weight_depth, ww, False)}
{_memory_ports("results", result_depth, rw, False)}
    %true = hw.constant true
    %false = hw.constant false
    %zero_i64 = hw.constant 0 : i64
    %one_i64 = hw.constant 1 : i64
    %row_limit_i64 = hw.constant {descriptor.rows} : i64
    %output_limit_i64 = hw.constant {descriptor.outputs} : i64
    %input_limit_i64 = hw.constant {descriptor.inputs} : i64
    %row_counter.in, %row_counter.write_en, %row_counter.clk, %row_counter.reset, %row_counter.out, %row_counter.done = calyx.register @row_counter : i64, i1, i1, i1, i64, i1
    %output_counter.in, %output_counter.write_en, %output_counter.clk, %output_counter.reset, %output_counter.out, %output_counter.done = calyx.register @output_counter : i64, i1, i1, i1, i64, i1
    %k_counter.in, %k_counter.write_en, %k_counter.clk, %k_counter.reset, %k_counter.out, %k_counter.done = calyx.register @k_counter : i64, i1, i1, i1, i64, i1
    %accumulator.in, %accumulator.write_en, %accumulator.clk, %accumulator.reset, %accumulator.out, %accumulator.done = calyx.register @accumulator : i64, i1, i1, i1, i64, i1
    %activation_base.in, %activation_base.write_en, %activation_base.clk, %activation_base.reset, %activation_base.out, %activation_base.done = calyx.register @activation_base : i64, i1, i1, i1, i64, i1
    %activation_address.in, %activation_address.write_en, %activation_address.clk, %activation_address.reset, %activation_address.out, %activation_address.done = calyx.register @activation_address : i64, i1, i1, i1, i64, i1
    %weight_address.in, %weight_address.write_en, %weight_address.clk, %weight_address.reset, %weight_address.out, %weight_address.done = calyx.register @weight_address : i64, i1, i1, i1, i64, i1
    %result_address.in, %result_address.write_en, %result_address.clk, %result_address.reset, %result_address.out, %result_address.done = calyx.register @result_address : i64, i1, i1, i1, i64, i1
    %activation_address_slice.in, %activation_address_slice.out = calyx.std_slice @activation_address_slice : i64, i{aw}
    %weight_address_slice.in, %weight_address_slice.out = calyx.std_slice @weight_address_slice : i64, i{ww}
    %result_address_slice.in, %result_address_slice.out = calyx.std_slice @result_address_slice : i64, i{rw}
    %operands_done.left, %operands_done.right, %operands_done.out = calyx.std_and @operands_done : i1, i1, i1
    %mac_mul.clk, %mac_mul.reset, %mac_mul.go, %mac_mul.left, %mac_mul.right, %mac_mul.out, %mac_mul.done = calyx.std_mult_pipe @mac_mul : i1, i1, i1, i64, i64, i64, i1
    %mac_add.left, %mac_add.right, %mac_add.out = calyx.std_add @mac_add : i64, i64, i64
    %next_row.left, %next_row.right, %next_row.out = calyx.std_add @next_row : i64, i64, i64
    %next_output.left, %next_output.right, %next_output.out = calyx.std_add @next_output : i64, i64, i64
    %next_k.left, %next_k.right, %next_k.out = calyx.std_add @next_k : i64, i64, i64
    %next_activation_base.left, %next_activation_base.right, %next_activation_base.out = calyx.std_add @next_activation_base : i64, i64, i64
    %next_activation_address.left, %next_activation_address.right, %next_activation_address.out = calyx.std_add @next_activation_address : i64, i64, i64
    %next_weight_address.left, %next_weight_address.right, %next_weight_address.out = calyx.std_add @next_weight_address : i64, i64, i64
    %next_result_address.left, %next_result_address.right, %next_result_address.out = calyx.std_add @next_result_address : i64, i64, i64
    %row_less.left, %row_less.right, %row_less.out = calyx.std_lt @row_less : i64, i64, i1
    %output_less.left, %output_less.right, %output_less.out = calyx.std_lt @output_less : i64, i64, i1
    %k_less.left, %k_less.right, %k_less.out = calyx.std_lt @k_less : i64, i64, i1
    calyx.wires {{
      calyx.comb_group @row_not_done {{
        calyx.assign %row_less.left = %row_counter.out : i64
        calyx.assign %row_less.right = %row_limit_i64 : i64
      }}
      calyx.comb_group @output_not_done {{
        calyx.assign %output_less.left = %output_counter.out : i64
        calyx.assign %output_less.right = %output_limit_i64 : i64
      }}
      calyx.comb_group @k_not_done {{
        calyx.assign %k_less.left = %k_counter.out : i64
        calyx.assign %k_less.right = %input_limit_i64 : i64
      }}
      calyx.group @read_operands {{
        calyx.assign %activation_address_slice.in = %activation_address.out : i64
        calyx.assign %weight_address_slice.in = %weight_address.out : i64
        calyx.assign %activation.addr0 = %activation_address_slice.out : i{aw}
        calyx.assign %weights.addr0 = %weight_address_slice.out : i{ww}
        calyx.assign %activation.content_en = %true : i1
        calyx.assign %activation.write_en = %false : i1
        calyx.assign %weights.content_en = %true : i1
        calyx.assign %weights.write_en = %false : i1
        calyx.assign %operands_done.left = %activation.done : i1
        calyx.assign %operands_done.right = %weights.done : i1
        calyx.group_done %operands_done.out : i1
      }}
      calyx.group @launch_multiply {{
        calyx.assign %mac_mul.left = %activation.read_data : i64
        calyx.assign %mac_mul.right = %weights.read_data : i64
        calyx.assign %mac_mul.go = %true : i1
        calyx.group_done %mac_mul.done : i1
      }}
      calyx.group @accumulate_and_advance_k {{
        calyx.assign %mac_add.left = %accumulator.out : i64
        calyx.assign %mac_add.right = %mac_mul.out : i64
        calyx.assign %accumulator.in = %mac_add.out : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %next_k.left = %k_counter.out : i64
        calyx.assign %next_k.right = %one_i64 : i64
        calyx.assign %k_counter.in = %next_k.out : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %next_activation_address.left = %activation_address.out : i64
        calyx.assign %next_activation_address.right = %one_i64 : i64
        calyx.assign %activation_address.in = %next_activation_address.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.assign %next_weight_address.left = %weight_address.out : i64
        calyx.assign %next_weight_address.right = %one_i64 : i64
        calyx.assign %weight_address.in = %next_weight_address.out : i64
        calyx.assign %weight_address.write_en = %true : i1
        calyx.group_done %accumulator.done : i1
      }}
      calyx.group @write_result {{
        calyx.assign %result_address_slice.in = %result_address.out : i64
        calyx.assign %results.addr0 = %result_address_slice.out : i{rw}
        calyx.assign %results.write_data = %accumulator.out : i64
        calyx.assign %results.content_en = %true : i1
        calyx.assign %results.write_en = %true : i1
        calyx.group_done %results.done : i1
      }}
      calyx.group @advance_output {{
        calyx.assign %next_output.left = %output_counter.out : i64
        calyx.assign %next_output.right = %one_i64 : i64
        calyx.assign %output_counter.in = %next_output.out : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %k_counter.in = %zero_i64 : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %accumulator.in = %zero_i64 : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %activation_address.in = %activation_base.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.assign %next_result_address.left = %result_address.out : i64
        calyx.assign %next_result_address.right = %one_i64 : i64
        calyx.assign %result_address.in = %next_result_address.out : i64
        calyx.assign %result_address.write_en = %true : i1
        calyx.group_done %output_counter.done : i1
      }}
      calyx.group @advance_row {{
        calyx.assign %next_row.left = %row_counter.out : i64
        calyx.assign %next_row.right = %one_i64 : i64
        calyx.assign %row_counter.in = %next_row.out : i64
        calyx.assign %row_counter.write_en = %true : i1
        calyx.assign %output_counter.in = %zero_i64 : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %weight_address.in = %zero_i64 : i64
        calyx.assign %weight_address.write_en = %true : i1
        calyx.assign %next_activation_base.left = %activation_base.out : i64
        calyx.assign %next_activation_base.right = %input_limit_i64 : i64
        calyx.assign %activation_base.in = %next_activation_base.out : i64
        calyx.assign %activation_base.write_en = %true : i1
        calyx.assign %activation_address.in = %next_activation_base.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.group_done %row_counter.done : i1
      }}
    }}
    calyx.control {{
      calyx.while %row_less.out with @row_not_done {{
        calyx.seq {{
          calyx.while %output_less.out with @output_not_done {{
            calyx.seq {{
              calyx.while %k_less.out with @k_not_done {{
                calyx.seq {{
                  calyx.enable @read_operands
                  calyx.enable @launch_multiply
                  calyx.enable @accumulate_and_advance_k
                }}
              }}
              calyx.enable @write_result
              calyx.enable @advance_output
            }}
          }}
          calyx.enable @advance_row
        }}
      }}
    }}
  }}
'''


def generated_component_trace_summary(artifact: CalyxArtifact) -> dict[str, Any]:
    """Bind a compact trace summary to operations actually emitted in Calyx."""
    required = (
        "calyx.register @row_counter", "calyx.register @activation_address",
        "calyx.register @weight_address", "calyx.register @result_address",
        "calyx.group @read_operands", "calyx.group @launch_multiply",
        "calyx.group_done %mac_mul.done", "calyx.group @write_result",
        "calyx.assign %results.write_data = %accumulator.out : i64",
        "calyx.assign %results.write_en = %true : i1",
        "calyx.while %row_less.out with @row_not_done",
    )
    if any(item not in artifact.mlir for item in required):
        raise ValueError("generated_component_trace: emitted Calyx lacks runtime serial-GEMV control/data path")
    d = artifact.provenance["descriptor"]
    return {
        "entry_count": d["rows"] * d["outputs"] * d["inputs"],
        "first": {"row": 0, "output": 0, "input": 0, "activation_address": 0, "weight_address": 0, "result_address": 0},
        "last": {"row": d["rows"] - 1, "output": d["outputs"] - 1, "input": d["inputs"] - 1,
                 "activation_address": d["rows"] * d["inputs"] - 1,
                 "weight_address": d["outputs"] * d["inputs"] - 1,
                 "result_address": d["rows"] * d["outputs"] - 1},
        "emitted_control_sha256": hashlib.sha256("\n".join(line.strip() for line in artifact.mlir.splitlines() if "calyx." in line).encode()).hexdigest(),
    }


def lower_descriptor(descriptor: SerialGemvDescriptor) -> CalyxArtifact:
    """Generate component and one compiler-owned invocation wrapper."""
    component = f"llm2fpga_serial_gemv_{descriptor.outputs}_{descriptor.inputs}"
    activation_depth = descriptor.rows * descriptor.inputs
    weight_depth = descriptor.outputs * descriptor.inputs
    result_depth = descriptor.rows * descriptor.outputs
    wrapper = f"llm2fpga_serial_gemv_program_{descriptor.rows}_{descriptor.outputs}_{descriptor.inputs}"
    activation_width = _ceil_log2(activation_depth)
    weight_width = _ceil_log2(weight_depth)
    result_width = _ceil_log2(result_depth)
    mlir = f'''module attributes {{calyx.entrypoint = "{wrapper}"}} {{
  // generated_from_descriptor: compiler-owned serial GEMV, not imported RTL.
  calyx.component @{wrapper}(%clk: i1 {{clk}}, %reset: i1 {{reset}}, %go: i1 {{go}}) -> (%done: i1 {{done}}) {{
{_memory_ports("activation", activation_depth, activation_width, True)}
{_memory_ports("weights", weight_depth, weight_width, True)}
{_memory_ports("results", result_depth, result_width, True)}
    %llm2fpga_serial_gemv_instance.clk, %llm2fpga_serial_gemv_instance.reset, %llm2fpga_serial_gemv_instance.go, %llm2fpga_serial_gemv_instance.done = calyx.instance @llm2fpga_serial_gemv_instance of @{component} : i1, i1, i1, i1
    calyx.wires {{
    }}
    calyx.control {{
      calyx.invoke @llm2fpga_serial_gemv_instance[activation = activation, weights = weights, results = results]() -> ()
    }}
  }} {{toplevel}}
{_kernel_runtime(descriptor)}}}
'''
    provenance = {
        "generated_from_descriptor": True,
        "descriptor": {
            "rows": descriptor.rows,
            "outputs": descriptor.outputs,
            "inputs": descriptor.inputs,
            "mac_order": descriptor.mac_order,
        },
        "trace_contract": "emitted-control-address-data-schedule-v1",
    }
    return CalyxArtifact(mlir=mlir, provenance=provenance)


def lower_descriptor_text(text: str) -> CalyxArtifact:
    return lower_descriptor(parse_descriptor_text(text))


def find_circt_opt() -> Path | None:
    configured = os.environ.get("CIRCT_OPT")
    candidate = configured or shutil.which("circt-opt")
    return Path(candidate) if candidate and Path(candidate).is_file() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="legalized MLIR containing one descriptor")
    parser.add_argument("--output", type=Path, required=True, help="generated Calyx MLIR")
    parser.add_argument("--trace", type=Path, required=True, help="ordered address/data trace JSON")
    parser.add_argument("--provenance", type=Path, required=True, help="descriptor provenance JSON")
    args = parser.parse_args()
    artifact = lower_descriptor_text(args.input.read_text(encoding="utf-8"))
    descriptor = parse_descriptor_text(args.input.read_text(encoding="utf-8"))
    provenance = dict(artifact.provenance)
    generated_trace = generated_component_trace_summary(artifact)
    provenance["generated_component_trace"] = generated_trace
    args.output.write_text(artifact.mlir, encoding="utf-8")
    trace_summary = {
        "schema": "llm2fpga-exact-serial-gemv-address-data-trace-v1",
        "descriptor": provenance["descriptor"],
        "entry_count": descriptor.rows * descriptor.outputs * descriptor.inputs,
        "sha256": stream_trace_sha256(descriptor),
        "emitted_control_sha256": generated_trace["emitted_control_sha256"],
        "first": generated_trace["first"],
        "last": generated_trace["last"],
    }
    args.trace.write_text(json.dumps(trace_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
