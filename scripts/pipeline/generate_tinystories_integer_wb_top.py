#!/usr/bin/env python3
"""Generate a Wishbone shell around the compiler-generated integer RC.

This generator externalizes every immutable tensor/global memory in ``main_1``
through the transport-only compiler-memory adapter.  Token input and result
memories stay local to preserve the generated accelerator's autoregressive
control interface.  No compute RTL is copied or rewritten here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def _load_helpers(path: Path):
    spec = importlib.util.spec_from_file_location("rc_sv_helpers_wb", path)
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


def _render_top(rtl, *, external_ports: tuple[int, ...], token_port: int,
                result_port: int, token_width: int, token_depth: int,
                result_width: int, register_requests: bool,
                register_local_memories: bool) -> str:
    external_index = {port: index for index, port in enumerate(external_ports)}
    declarations: list[str] = []
    connections: list[str] = []
    local_services: list[str] = []
    external_wires: list[str] = []
    local_initialization: list[str] = []
    for port in rtl:
        number = port.number
        addr_width = max(1, (port.depth - 1).bit_length())
        declarations.extend([
            f"  wire [{addr_width - 1}:0] a{number}_addr;",
            f"  wire a{number}_en, a{number}_we;",
            f"  wire [{port.width - 1}:0] a{number}_wdata;",
            f"  logic [{port.width - 1}:0] a{number}_rdata;",
            f"  logic a{number}_done;",
        ])
        if number not in external_index:
            declarations.append(f"  logic [{port.width - 1}:0] mem{number} [0:{port.depth - 1}];")
        connections.extend([
            f".arg_mem_{number}_addr0(a{number}_addr)",
            f".arg_mem_{number}_content_en(a{number}_en)",
            f".arg_mem_{number}_write_en(a{number}_we)",
            f".arg_mem_{number}_write_data(a{number}_wdata)",
            f".arg_mem_{number}_read_data(a{number}_rdata)",
            f".arg_mem_{number}_done(a{number}_done)",
        ])
        if number in external_index:
            index = external_index[number]
            element_bytes = max(1, (port.width + 7) // 8)
            external_wires.extend([
                f"  assign ext_req_valid[{index}] = a{number}_en && !a{number}_we;",
                f"  logic [2:0] ext_offset{number}_q;",
                f"  assign ext_req_addr[{index * 32} +: 32] = ({{{{{32 - addr_width}{{1'b0}}}}, a{number}_addr}} * {element_bytes});",
                f"  wire [63:0] ext_data{number} = ext_rsp_data[{index * 64} +: 64];",
                f"  wire [63:0] ext_shifted{number} = ext_data{number} >> (ext_offset{number}_q * 8);",
                f"  always_ff @(posedge clk) begin",
                f"    if (reset) begin a{number}_done <= 1'b0; a{number}_rdata <= '0; ext_offset{number}_q <= 3'd0; end",
                f"    else begin",
                f"      a{number}_done <= 1'b0;",
                f"      if (ext_req_valid[{index}] && ext_req_ready[{index}]) ext_offset{number}_q <= ((a{number}_addr * {element_bytes}) & 7);",
                f"      if (ext_rsp_valid[{index}]) begin",
                f"        a{number}_rdata <= ext_shifted{number}[{port.width - 1}:0];",
                f"        a{number}_done <= 1'b1;",
                f"      end",
                f"    end",
                f"  end",
            ])
        elif number == token_port:
            # The token input is a local read-only memory.  Keep both the
            # storage and its generated-memory handshake in one sequential
            # process: Yosys cannot lower a continuous assignment into an
            # unpacked memory, although simulators commonly accept it.
            local_services.extend([
                f"  always_ff @(posedge clk) begin : service_token_{number}",
                f"    if (reset) begin",
                f"      mem{number}[0] <= '0; mem{number}[1] <= '0;",
                f"      a{number}_done <= 1'b0; a{number}_rdata <= '0;",
                f"    end else begin",
                f"      mem{number}[0] <= token_data[0 +: {token_width}];",
                f"      mem{number}[1] <= token_data[{token_width} +: {token_width}];",
                f"      a{number}_done <= 1'b0;",
                f"      if (a{number}_en && !a{number}_we) begin",
                f"        a{number}_rdata <= mem{number}[a{number}_addr];",
                f"        a{number}_done <= 1'b1;",
                f"      end",
                f"    end",
                f"  end",
            ])
        else:
            if register_local_memories:
                local_services.extend([
                    f"  logic mem{number}_pending_q;",
                    f"  logic [{addr_width - 1}:0] mem{number}_addr_q;",
                    f"  logic mem{number}_we_q;",
                    f"  logic [{port.width - 1}:0] mem{number}_wdata_q;",
                    f"  always_ff @(posedge clk) begin : service_mem_{number}",
                    f"    if (reset) begin",
                    f"      mem{number}_pending_q <= 1'b0; a{number}_done <= 1'b0; a{number}_rdata <= '0;",
                    f"    end else begin",
                    f"      a{number}_done <= mem{number}_pending_q;",
                    f"      if (mem{number}_pending_q) begin",
                    f"        if (mem{number}_we_q) mem{number}[mem{number}_addr_q] <= mem{number}_wdata_q;",
                    f"        else a{number}_rdata <= mem{number}[mem{number}_addr_q];",
                    f"        mem{number}_pending_q <= 1'b0;",
                    f"      end else if (a{number}_en) begin",
                    f"        mem{number}_pending_q <= 1'b1; mem{number}_addr_q <= a{number}_addr;",
                    f"        mem{number}_we_q <= a{number}_we; mem{number}_wdata_q <= a{number}_wdata;",
                    f"      end",
                    f"    end",
                    f"  end",
                ])
            else:
                local_services.extend([
                    f"  always_ff @(posedge clk) begin : service_mem_{number}",
                    f"    if (reset) begin a{number}_done <= 1'b0; a{number}_rdata <= '0; end",
                    f"    else begin",
                    f"      a{number}_done <= 1'b0;",
                    f"      if (a{number}_en) begin",
                    f"        a{number}_done <= 1'b1;",
                    f"        if (a{number}_we) mem{number}[a{number}_addr] <= a{number}_wdata;",
                    f"        else a{number}_rdata <= mem{number}[a{number}_addr];",
                    f"      end",
                    f"    end",
                    f"  end",
                ])
            local_initialization.append(
                f"    for (int i{number} = 0; i{number} < {port.depth}; i{number}++) mem{number}[i{number}] = '0;"
            )

    token_decl_width = token_width * token_depth
    token_decl = "" if token_decl_width == 1 else f" [{token_decl_width - 1}:0]"
    result_decl = "" if result_width == 1 else f" [{result_width - 1}:0]"
    ext_count = len(external_ports)
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tinystories_integer_rc_wb_top(",
        "  input logic clk, input logic reset, input logic go,",
        f"  input logic{token_decl} token_data, output logic done,",
        "  output logic wb_cyc, output logic wb_stb,",
        "  output logic [31:0] wb_addr, output logic [15:0] wb_sel,",
        "  input logic wb_accept, input logic wb_ack, input logic wb_err,",
        "  input logic [127:0] wb_rdata,",
        f"  output logic{result_decl} result0, output logic{result_decl} result1",
        ");",
        f"  logic [{ext_count - 1}:0] ext_req_valid, ext_req_ready, ext_rsp_valid;",
        f"  logic [{ext_count * 32 - 1}:0] ext_req_addr;",
        f"  logic [{ext_count * 64 - 1}:0] ext_rsp_data;",
        *declarations,
        "  main_1 generated(.clk(clk), .reset(reset), .go(go), .done(done),",
        "    " + ",\n    ".join(connections) + ");",
        "  llm_compiler_memory_wb_adapter #(.PORTS(" + str(ext_count) + "), .REGISTER_REQUESTS(" + ("1" if register_requests else "0") + ")) external_memory (",
        "    .clk(clk), .rst(reset), .req_valid(ext_req_valid), .req_ready(ext_req_ready),",
        "    .req_addr(ext_req_addr), .rsp_valid(ext_rsp_valid), .rsp_data(ext_rsp_data),",
        "    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_addr(wb_addr), .wb_sel(wb_sel),",
        "    .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata));",
        *external_wires,
        *local_services,
        f"  assign result0 = mem{result_port}[0];",
        f"  assign result1 = mem{result_port}[1];",
        "  initial begin",
        *local_initialization,
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
    parser.add_argument("--register-requests", action="store_true",
                        help="register compiler memory requests before arbitration")
    parser.add_argument("--register-local-memories", action="store_true",
                        help="register non-token local memory service requests")
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("--out-dir must not already exist")
    helpers = _load_helpers(args.helpers)
    semantic = helpers.parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    rtl = helpers.parse_sv_memory_ports(args.sv.read_text(encoding="utf-8"))
    if len(semantic) != 52 or len(rtl) < 57:
        raise ValueError("integer RC ABI must contain 52 semantic and five global memories")
    values = _exported_values(args.exported)
    if len(values) != 51:
        raise ValueError("integer RC requires 50 buffers plus one token input")
    token_port, result_port = 50, 51
    external_ports = tuple(range(50)) + tuple(range(52, 57))
    args.out_dir.mkdir(parents=True)
    input_manifest = []
    for number, tensor in enumerate(values):
        payload, dtype, shape = helpers.tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape and not (shape == () and memory.shape == (1,)):
            raise ValueError(f"arg_mem_{number} shape {shape} != {memory.shape}")
        if number in external_ports:
            words = "\n".join(helpers.memory_words(payload, width=memory.width)) + "\n"
            (args.out_dir / f"mem{number}.hex").write_text(words, encoding="ascii")
        elif number == token_port:
            (args.out_dir / "token.hex").write_text(
                "\n".join(helpers.memory_words(payload, width=memory.width)) + "\n", encoding="ascii"
            )
        input_manifest.append({"port": number, "dtype": dtype, "shape": list(shape), "external": number in external_ports,
                               "sha256": hashlib.sha256(payload).hexdigest()})
    globals_ = helpers.parse_flat_scf_global_bindings(
        args.flat_scf.read_text(encoding="utf-8"), first_port=len(semantic)
    )
    for binding in globals_:
        if binding.port not in external_ports:
            raise ValueError(f"global binding unexpectedly local: {binding.port}")
        width = rtl[binding.port].width
        digits = width // 4
        (args.out_dir / f"mem{binding.port}.hex").write_text(
            "\n".join(f"{word:0{digits}x}" for word in binding.words) + "\n", encoding="utf-8"
        )
    top = _render_top(rtl, external_ports=external_ports, token_port=token_port,
                      result_port=result_port, token_width=rtl[token_port].width,
                      token_depth=rtl[token_port].depth,
                      result_width=rtl[result_port].width,
                      register_requests=args.register_requests,
                      register_local_memories=args.register_local_memories)
    top_path = args.out_dir / "top.sv"
    top_path.write_text(top, encoding="utf-8")
    (args.out_dir / "manifest.json").write_text(json.dumps({
        "schema": "tinystories-integer-rc-wishbone-top-v1",
        "external_ports": list(external_ports), "token_input_port": token_port,
        "result_port": result_port, "semantic_memory_count": len(semantic),
        "rtl_memory_count": len(rtl), "source_sv_sha256": hashlib.sha256(args.sv.read_bytes()).hexdigest(),
        "top_sha256": hashlib.sha256(top_path.read_bytes()).hexdigest(), "inputs": input_manifest,
        "globals": [binding.symbol for binding in globals_],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
