#!/usr/bin/env python3
"""Generate a transaction-level external-memory probe around generated ``main_1``.

The compiler-generated accelerator remains the only compute implementation.  A
single immutable ``arg_mem_N`` is removed from the local memory service and is
exposed as a request/response channel.  This is deliberately a one-port probe:
it validates the generated ``main_1`` ABI and variable-latency handoff before
the same adapter is expanded to the complete tensor image and UberDDR3.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def _load_helpers(path: Path):
    spec = importlib.util.spec_from_file_location("rc_sv_helpers_external", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _exported_values(exported_path: Path):
    import torch

    archive = exported_path / "exported.pt2" if exported_path.is_dir() else exported_path
    exported = torch.export.load(archive)
    positional, keyword = exported.example_inputs
    if keyword:
        raise ValueError("integer RC requires positional example inputs")
    user_inputs = iter(positional)
    values = []
    for spec in exported.graph_signature.input_specs:
        if spec.kind.name == "BUFFER":
            value = exported.state_dict.get(spec.target)
            if value is None:
                raise ValueError(f"missing buffer {spec.target}")
            values.append(value)
        elif spec.kind.name == "USER_INPUT":
            values.append(next(user_inputs))
    return values


def _render_top(rtl, *, external_port: int, result_port: int, result_width: int,
                initialized_ports: set[int], external_width: int) -> str:
    declarations: list[str] = []
    connections: list[str] = []
    local_services: list[str] = []
    initialization: list[str] = []
    for port in rtl:
        number = port.number
        addr_width = max(1, (port.depth - 1).bit_length())
        declarations.extend([
            f"  logic [{port.width - 1}:0] mem{number} [0:{port.depth - 1}];",
            f"  wire [{addr_width - 1}:0] a{number}_addr;",
            f"  wire a{number}_en, a{number}_we;",
            f"  wire [{port.width - 1}:0] a{number}_wdata;",
            f"  logic [{port.width - 1}:0] a{number}_rdata;",
            f"  logic a{number}_done;",
        ])
        connections.extend([
            f".arg_mem_{number}_addr0(a{number}_addr)",
            f".arg_mem_{number}_content_en(a{number}_en)",
            f".arg_mem_{number}_write_en(a{number}_we)",
            f".arg_mem_{number}_write_data(a{number}_wdata)",
            f".arg_mem_{number}_read_data(a{number}_rdata)",
            f".arg_mem_{number}_done(a{number}_done)",
        ])
        if number == external_port:
            if port.width != external_width:
                raise ValueError("external width disagrees with generated memory port")
            declarations.extend([
                "  logic ext_active, ext_wait_response;",
                "  logic [31:0] ext_addr_q;",
            ])
        else:
            local_services.extend([
                f"      if (a{number}_en) begin",
                f"        a{number}_done <= 1'b1;",
                f"        if (a{number}_we) mem{number}[a{number}_addr] <= a{number}_wdata;",
                f"        else a{number}_rdata <= mem{number}[a{number}_addr];",
                "      end",
            ])
            initialization.append(
                f"    for (int i{number} = 0; i{number} < {port.depth}; i{number}++) mem{number}[i{number}] = '0;"
            )
            if number in initialized_ports:
                initialization.append(f'    $readmemh("mem{number}.hex", mem{number});')

    result_decl = "" if result_width == 1 else f" [{result_width - 1}:0]"
    ext_addr_shift = max(0, (external_width // 8).bit_length() - 1)
    ext_addr_width = max(1, (rtl[external_port].depth - 1).bit_length())
    ext_addr_expr = f"{{{{{32 - ext_addr_width}{{1'b0}}}}, a{external_port}_addr}}"
    ext_slice = "" if external_width == 64 else f"[ {external_width - 1}:0 ]"
    ext_data = f"ext_rsp_data{ext_slice}" if ext_slice else "ext_rsp_data"
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tinystories_integer_rc_external_probe_top(",
        "  input logic clk, input logic reset, input logic go,",
        "  output logic done,",
        "  output logic ext_req_valid, input logic ext_req_ready,",
        "  output logic [31:0] ext_req_addr,",
        "  input logic ext_rsp_valid, input logic [63:0] ext_rsp_data,",
        f"  output logic{result_decl} result0, output logic{result_decl} result1",
        ");",
        *declarations,
        "  main_1 generated(.clk(clk), .reset(reset), .go(go), .done(done),",
        "    " + ",\n    ".join(connections) + ");",
        f"  assign ext_req_valid = ext_active;",
        "  assign ext_req_addr = ext_addr_q;",
        "  always_ff @(posedge clk) begin",
        "    if (reset) begin",
        *[f"      a{port.number}_done <= 1'b0; a{port.number}_rdata <= '0;" for port in rtl],
        "      ext_active <= 1'b0; ext_wait_response <= 1'b0; ext_addr_q <= 32'd0;",
        "    end else begin",
        *[f"      a{port.number}_done <= 1'b0;" for port in rtl],
        f"      if (!ext_active && !ext_wait_response && a{external_port}_en && !a{external_port}_we) begin",
        "        ext_active <= 1'b1;",
        f"        ext_addr_q <= {ext_addr_expr} << {ext_addr_shift};",
        "      end",
        "      if (ext_active && ext_req_ready) begin ext_active <= 1'b0; ext_wait_response <= 1'b1; end",
        "      if (ext_wait_response && ext_rsp_valid) begin",
        f"        a{external_port}_rdata <= {ext_data}; a{external_port}_done <= 1'b1;",
        "        ext_wait_response <= 1'b0;",
        "      end",
        *local_services,
        "    end",
        "  end",
        f"  assign result0 = mem{result_port}[0];",
        f"  assign result1 = mem{result_port}[1];",
        "  initial begin",
        *initialization,
        "  end",
        "endmodule",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--flat-scf", type=Path, required=True)
    parser.add_argument("--exported", type=Path, required=True)
    parser.add_argument("--helpers", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--external-port", type=int, default=0)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("--out-dir must not already exist")
    helpers = _load_helpers(args.helpers)
    semantic = helpers.parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    rtl = helpers.parse_sv_memory_ports(args.sv.read_text(encoding="utf-8"))
    if len(semantic) != 52 or len(rtl) < len(semantic):
        raise ValueError("integer RC ABI must contain 52 semantic memories")
    if not 0 <= args.external_port < 50:
        raise ValueError("the first probe may externalize only immutable tensor ports 0..49")
    values = _exported_values(args.exported)
    if len(values) != 51:
        raise ValueError("integer RC requires 50 buffers plus one token input")
    args.out_dir.mkdir(parents=True)
    input_manifest = []
    for number, tensor in enumerate(values):
        payload, dtype, shape = helpers.tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape and not (shape == () and memory.shape == (1,)):
            raise ValueError(f"arg_mem_{number} shape {shape} != {memory.shape}")
        words = helpers.memory_words(payload, width=memory.width)
        path = args.out_dir / (f"external_mem{number}.hex" if number == args.external_port else f"mem{number}.hex")
        path.write_text("\n".join(words) + "\n", encoding="ascii")
        input_manifest.append({"port": number, "dtype": dtype, "shape": list(shape),
                               "sha256": hashlib.sha256(payload).hexdigest(),
                               "external": number == args.external_port})
    globals_ = helpers.parse_flat_scf_global_bindings(
        args.flat_scf.read_text(encoding="utf-8"), first_port=len(semantic)
    )
    initialized_ports = set(range(1, len(values)))
    for binding in globals_:
        width = rtl[binding.port].width
        digits = width // 4
        (args.out_dir / f"mem{binding.port}.hex").write_text(
            "\n".join(f"{word:0{digits}x}" for word in binding.words) + "\n",
            encoding="ascii",
        )
        initialized_ports.add(binding.port)
    top = _render_top(rtl, external_port=args.external_port, result_port=51,
                      result_width=rtl[51].width, initialized_ports=initialized_ports,
                      external_width=rtl[args.external_port].width)
    top_path = args.out_dir / "top.sv"
    top_path.write_text(top, encoding="utf-8")
    (args.out_dir / "manifest.json").write_text(json.dumps({
        "schema": "tinystories-integer-rc-external-probe-v1",
        "external_port": args.external_port,
        "external_width": rtl[args.external_port].width,
        "semantic_memory_count": len(semantic),
        "rtl_memory_count": len(rtl),
        "token_input_port": 50,
        "result_port": 51,
        "source_sv_sha256": hashlib.sha256(args.sv.read_bytes()).hexdigest(),
        "top_sha256": hashlib.sha256(top_path.read_bytes()).hexdigest(),
        "inputs": input_manifest,
        "globals": [binding.symbol for binding in globals_],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
