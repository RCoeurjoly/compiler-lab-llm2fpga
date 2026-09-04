#!/usr/bin/env python3
"""Generate the narrow public shell for one integrated W4A8 Calyx design."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Sequence


@dataclasses.dataclass(frozen=True)
class MemoryPort:
    number: int
    width: int
    depth: int


@dataclasses.dataclass(frozen=True)
class ReadbackBinding:
    address: int
    memory: int
    index: int
    width: int


PHASES = ("prefill-8", "decode-8", "decode-9")


def build_readback_bindings(
    manifest: dict[str, object], output_ports: Sequence[int]
) -> tuple[ReadbackBinding, ...]:
    if len(output_ports) != 18:
        raise ValueError("integrated ABI requires exactly 18 output memories")
    words = manifest.get("words")
    if not isinstance(words, list):
        raise ValueError("readback manifest words must be a list")
    addresses = [word.get("address") for word in words if isinstance(word, dict)]
    expected_count = manifest.get("address_count")
    if addresses != list(range(len(words))) or expected_count != len(words):
        raise ValueError("readback addresses must be dense and match address_count")

    phase_index = {name: index for index, name in enumerate(PHASES)}
    bindings: list[ReadbackBinding] = []
    for word in words:
        if not isinstance(word, dict):
            raise ValueError("readback word must be an object")
        try:
            phase = phase_index[str(word["phase"])]
            kind = str(word["kind"])
            flat_index = int(word["flat_index"])
            width = int(word["width"])
            address = int(word["address"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("malformed readback word") from error
        if kind == "token":
            ordinal = phase
        elif kind == "logits":
            ordinal = 3 + phase * 5
        elif kind == "cache":
            leaf = word.get("leaf")
            if not isinstance(leaf, int) or not 0 <= leaf < 4:
                raise ValueError("cache readback word requires leaf 0..3")
            ordinal = 4 + phase * 5 + leaf
        else:
            raise ValueError(f"unsupported readback kind: {kind}")
        bindings.append(ReadbackBinding(address, output_ports[ordinal], flat_index, width))
    return tuple(bindings)


def _width_decl(width: int) -> str:
    return "" if width == 1 else f" [{width - 1}:0]"


def render_public_shell(
    manifest: dict[str, object],
    ports: Sequence[MemoryPort],
    *,
    prompt_port: int,
    output_ports: Sequence[int],
    initialized_ports: Sequence[int] = (),
) -> str:
    by_number = {port.number: port for port in ports}
    if sorted(by_number) != list(range(len(ports))):
        raise ValueError("memory ports must be a dense zero-based sequence")
    prompt = by_number.get(prompt_port)
    if prompt is None or prompt.width != 64 or prompt.depth < 8:
        raise ValueError("prompt memory must provide at least eight 64-bit words")
    bindings = build_readback_bindings(manifest, output_ports)
    for binding in bindings:
        port = by_number.get(binding.memory)
        if port is None or port.width != binding.width or binding.index >= port.depth:
            raise ValueError(f"readback address {binding.address} does not fit its memory")

    declarations: list[str] = []
    connections: list[str] = []
    services: list[str] = []
    initialization: list[str] = []
    output_set = set(output_ports)
    initialized_set = set(initialized_ports)
    for port in ports:
        number = port.number
        addr_width = max(1, (port.depth - 1).bit_length())
        declarations.extend((
            f"logic [{port.width - 1}:0] mem{number} [0:{port.depth - 1}];",
            f"wire [{addr_width - 1}:0] a{number}_addr;",
            f"wire a{number}_en, a{number}_we;",
            f"wire [{port.width - 1}:0] a{number}_wdata;",
            f"logic [{port.width - 1}:0] a{number}_rdata;",
            f"logic a{number}_done;",
        ))
        connections.extend((
            f".arg_mem_{number}_addr0(a{number}_addr)",
            f".arg_mem_{number}_content_en(a{number}_en)",
            f".arg_mem_{number}_write_en(a{number}_we)",
            f".arg_mem_{number}_write_data(a{number}_wdata)",
            f".arg_mem_{number}_read_data(a{number}_rdata)",
            f".arg_mem_{number}_done(a{number}_done)",
        ))
        host_write = ""
        if number == prompt_port:
            host_write = (
                " if (!busy && prompt_write && prompt_index < 8) "
                f"mem{number}[prompt_index] <= prompt_data;"
            )
        services.extend((
            f"always_ff @(posedge clk) begin : service_mem_{number}",
            f"  if (reset) begin a{number}_done <= 1'b0; a{number}_rdata <= '0; end",
            f"  else if (busy && a{number}_en) begin",
            f"    a{number}_done <= 1'b1;",
            f"    if (a{number}_we) mem{number}[a{number}_addr] <= a{number}_wdata;",
            f"    else a{number}_rdata <= mem{number}[a{number}_addr];",
            f"  end else begin a{number}_done <= 1'b0;{host_write} end",
            "end",
        ))
        if number in initialized_set:
            initialization.append(f'  $readmemh("mem{number}.hex", mem{number});')
        else:
            initialization.append(
                f"  for (int i{number} = 0; i{number} < {port.depth}; i{number}++) mem{number}[i{number}] = '0;"
            )

    cases = []
    for binding in bindings:
        pad = 64 - binding.width
        value = f"mem{binding.memory}[{binding.index}]"
        if pad:
            value = "{" + f"{pad}'d0, {value}" + "}"
        cases.append(f"      {binding.address}: readback_response_data <= {value};")
    address_count = int(manifest["address_count"])
    address_width = max(1, math.ceil(math.log2(max(2, address_count))))

    return "\n".join((
        "`timescale 1ns/1ps",
        "module rc_serving_w4a8_integrated_reference(",
        "  input logic clk, input logic reset,",
        "  input logic [2:0] prompt_index, input logic [63:0] prompt_data,",
        "  input logic prompt_write, input logic go,",
        "  output logic busy, output logic done, output logic protocol_error,",
        f"  input logic [{address_width - 1}:0] readback_address, input logic readback_request,",
        "  output logic readback_response_valid, output logic [63:0] readback_response_data",
        ");",
        "logic [7:0] prompt_written; logic generated_go; wire generated_done;",
        *declarations,
        "main_1 generated(.clk(clk), .reset(reset), .go(generated_go), .done(generated_done),",
        "  " + ",\n  ".join(connections) + ");",
        *services,
        "always_ff @(posedge clk) begin",
        "  if (reset) begin",
        "    prompt_written <= 8'h00; generated_go <= 1'b0; busy <= 1'b0;",
        "    done <= 1'b0; protocol_error <= 1'b0;",
        "    readback_response_valid <= 1'b0; readback_response_data <= '0;",
        "  end else begin",
        "    done <= 1'b0; readback_response_valid <= 1'b0;",
        "    if (prompt_write) begin",
        "      if (busy || prompt_index >= 8 || prompt_written[prompt_index]) protocol_error <= 1'b1;",
        "      else prompt_written[prompt_index] <= 1'b1;",
        "    end",
        "    if (go) begin",
        "      if (busy || prompt_written != 8'hff) protocol_error <= 1'b1;",
        "      else begin busy <= 1'b1; generated_go <= 1'b1; end",
        "    end",
        "    if (busy && generated_done) begin",
        "      busy <= 1'b0; generated_go <= 1'b0; done <= 1'b1; prompt_written <= 8'h00;",
        "    end",
        "    if (readback_request) begin",
        f"      if (busy || readback_address >= {address_count}) protocol_error <= 1'b1;",
        "      else begin",
        "        readback_response_valid <= 1'b1;",
        "        case (readback_address)",
        *cases,
        "          default: readback_response_data <= '0;",
        "        endcase",
        "      end",
        "    end",
        "  end",
        "end",
        "initial begin",
        *initialization,
        "end",
        "endmodule",
        "",
    ))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--flat-scf", required=True, type=Path)
    parser.add_argument("--generated-sv", required=True, type=Path)
    parser.add_argument("--exported", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.pipeline.run_rc_serving_w4a8_sv import (
        memory_words,
        parse_flat_scf_abi,
        parse_flat_scf_global_bindings,
        parse_sv_memory_ports,
        runtime_values,
        tensor_payload,
        validate_abi,
    )
    import torch
    from torch.ao.quantization.quantize_pt2e import convert_pt2e  # noqa: F401

    if args.out_dir.exists():
        parser.error("--out-dir must not already exist")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    semantic = parse_flat_scf_abi(args.flat_scf.read_text(encoding="utf-8"))
    ports_raw = parse_sv_memory_ports(args.generated_sv.read_text(encoding="utf-8"))
    validate_abi(semantic, ports_raw)
    if len(semantic) < 19:
        raise ValueError("integrated semantic ABI is too small")
    output_ports = tuple(range(len(semantic) - 18, len(semantic)))
    prompt_port = len(semantic) - 19
    ports = tuple(MemoryPort(port.number, port.width, port.depth) for port in ports_raw)
    args.out_dir.mkdir(parents=True)
    exported = torch.export.load(args.exported)
    values = runtime_values(exported)
    if len(values) != prompt_port + 1:
        raise ValueError("exported runtime values do not match integrated input ABI")
    initialized_memories: list[int] = []
    for number, tensor in enumerate(values):
        if number == prompt_port:
            continue
        payload, _dtype, shape = tensor_payload(tensor)
        memory = semantic[number]
        if shape != memory.shape and not (shape == () and memory.shape == (1,)):
            raise ValueError(f"arg_mem_{number} tensor shape disagrees with flat-SCF")
        (args.out_dir / f"mem{number}.hex").write_text(
            "\n".join(memory_words(payload, width=memory.width)) + "\n",
            encoding="ascii",
        )
        initialized_memories.append(number)
    globals_ = parse_flat_scf_global_bindings(
        args.flat_scf.read_text(encoding="utf-8"), first_port=len(semantic)
    )
    for binding in globals_:
        port = ports[binding.port]
        if port.width != binding.width or port.depth < len(binding.words):
            raise ValueError(f"global @{binding.symbol} does not fit its RTL memory")
        digits = binding.width // 4
        (args.out_dir / f"mem{binding.port}.hex").write_text(
            "\n".join(f"{word:0{digits}x}" for word in binding.words) + "\n",
            encoding="ascii",
        )
        initialized_memories.append(binding.port)
    shell = render_public_shell(
        manifest,
        ports,
        prompt_port=prompt_port,
        output_ports=output_ports,
        initialized_ports=initialized_memories,
    )
    shell_path = args.out_dir / "reference-top.sv"
    shell_path.write_text(shell, encoding="utf-8")
    receipt = {
        "schema": "rc-serving-w4a8-integrated-shell-v1",
        "status": "ok",
        "generated_top": "main_1",
        "public_top": "rc_serving_w4a8_integrated_reference",
        "semantic_memory_count": len(semantic),
        "rtl_memory_count": len(ports),
        "prompt_memory": prompt_port,
        "output_memories": list(output_ports),
        "readback_word_count": len(build_readback_bindings(manifest, output_ports)),
        "initialized_memory_count": len(initialized_memories),
        "hashes": {
            "manifest_sha256": _sha256(args.manifest),
            "flat_scf_sha256": _sha256(args.flat_scf),
            "generated_sv_sha256": _sha256(args.generated_sv),
            "exported_sha256": _sha256(args.exported),
            "shell_sha256": _sha256(shell_path),
        },
    }
    (args.out_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
