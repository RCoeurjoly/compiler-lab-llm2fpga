#!/usr/bin/env python3
"""Generate a BRAM/LUTRAM integration wrapper for the integer RC SV."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def _load_helpers(path: Path):
    spec = importlib.util.spec_from_file_location("rc_sv_helpers_bram", path)
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


def _render_top(rtl, *, result_port: int, result_width: int,
                initialized_ports: set[int]) -> str:
    declarations: list[str] = []
    connections: list[str] = []
    services: list[str] = []
    initialization: list[str] = []
    for port in rtl:
        number = port.number
        addr_width = max(1, (port.depth - 1).bit_length())
        declarations.extend(
            [
                f"  logic [{port.width - 1}:0] mem{number} [0:{port.depth - 1}];",
                f"  wire [{addr_width - 1}:0] a{number}_addr;",
                f"  wire a{number}_en, a{number}_we;",
                f"  wire [{port.width - 1}:0] a{number}_wdata;",
                f"  logic [{port.width - 1}:0] a{number}_rdata;",
                f"  logic a{number}_done;",
            ]
        )
        connections.extend(
            [
                f".arg_mem_{number}_addr0(a{number}_addr)",
                f".arg_mem_{number}_content_en(a{number}_en)",
                f".arg_mem_{number}_write_en(a{number}_we)",
                f".arg_mem_{number}_write_data(a{number}_wdata)",
                f".arg_mem_{number}_read_data(a{number}_rdata)",
                f".arg_mem_{number}_done(a{number}_done)",
            ]
        )
        services.extend(
            [
                f"    if (a{number}_en) begin",
                f"      a{number}_done <= 1'b1;",
                f"      if (a{number}_we) mem{number}[a{number}_addr] <= a{number}_wdata;",
                f"      else a{number}_rdata <= mem{number}[a{number}_addr];",
                "    end else begin",
                f"      a{number}_done <= 1'b0;",
                "    end",
            ]
        )
        initialization.append(
            f"    for (int i{number} = 0; i{number} < {port.depth}; i{number}++) mem{number}[i{number}] = '0;"
        )
        if number in initialized_ports:
            initialization.append(f'    $readmemh("mem{number}.hex", mem{number});')
    result_decl = "" if result_width == 1 else f" [{result_width - 1}:0]"
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "module tinystories_integer_rc_bram_top(",
            "  input logic clk, input logic reset, input logic go,",
            "  output logic done,",
            f"  output logic{result_decl} result0, output logic{result_decl} result1",
            ");",
            *declarations,
            "  main_1 generated(.clk(clk), .reset(reset), .go(go), .done(done),",
            "    " + ",\n    ".join(connections) + ");",
            "  always_ff @(posedge clk) begin",
            "    if (reset) begin",
            *[f"      a{port.number}_done <= 1'b0; a{port.number}_rdata <= '0;" for port in rtl],
            "    end else begin",
            *services,
            "    end",
            "  end",
            "  assign result0 = mem%d[0];" % result_port,
            "  assign result1 = mem%d[1];" % result_port,
            "  initial begin",
            *initialization,
            "  end",
            "endmodule",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--flat-scf", type=Path, required=True)
    parser.add_argument("--exported", type=Path, required=True)
    parser.add_argument("--helpers", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("--out-dir must not already exist")
    helpers = _load_helpers(args.helpers)
    semantic = helpers.parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    rtl = helpers.parse_sv_memory_ports(args.sv.read_text(encoding="utf-8"))
    if len(semantic) != 52 or len(rtl) < len(semantic):
        raise ValueError("integer RC ABI must contain 52 semantic memories")
    values = _exported_values(args.exported)
    if len(values) != 51:
        raise ValueError("integer RC requires 50 buffers and one token input")
    args.out_dir.mkdir(parents=True)
    input_manifest = []
    for number, tensor in enumerate(values):
        payload, dtype, shape = helpers.tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape and not (shape == () and memory.shape == (1,)):
            raise ValueError(f"arg_mem_{number} shape {shape} != {memory.shape}")
        words = helpers.memory_words(payload, width=memory.width)
        path = args.out_dir / f"mem{number}.hex"
        path.write_text("\n".join(words) + "\n", encoding="ascii")
        input_manifest.append({"port": number, "dtype": dtype, "shape": list(shape),
                               "sha256": hashlib.sha256(payload).hexdigest()})
    globals_ = helpers.parse_flat_scf_global_bindings(
        args.flat_scf.read_text(encoding="utf-8"), first_port=len(semantic)
    )
    initialized_ports = set(range(len(values)))
    for binding in globals_:
        width = rtl[binding.port].width
        digits = width // 4
        (args.out_dir / f"mem{binding.port}.hex").write_text(
            "\n".join(f"{word:0{digits}x}" for word in binding.words) + "\n",
            encoding="ascii",
        )
        initialized_ports.add(binding.port)
    top = _render_top(
        rtl, result_port=51, result_width=rtl[51].width,
        initialized_ports=initialized_ports,
    )
    (args.out_dir / "top.sv").write_text(top, encoding="utf-8")
    manifest = {
        "schema": "tinystories-integer-rc-bram-top-v1",
        "status": "generated",
        "semantic_memory_count": len(semantic),
        "rtl_memory_count": len(rtl),
        "result_port": 51,
        "source_sv": str(args.sv),
        "source_sv_sha256": hashlib.sha256(args.sv.read_bytes()).hexdigest(),
        "inputs": input_manifest,
        "globals": [binding.symbol for binding in globals_],
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
