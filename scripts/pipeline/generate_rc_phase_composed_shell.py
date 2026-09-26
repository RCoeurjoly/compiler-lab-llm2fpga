"""Generate an autonomous token/cache shell around three compiler RC phases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PHASES = ("prefill-8", "decode-8", "decode-9")
SCHEMA = "llm2fpga.rc-phase-handoff-v1"


def _validate(manifest: dict) -> None:
    if manifest.get("schema") != SCHEMA or manifest.get("phase_order") != list(PHASES):
        raise ValueError("unsupported or reordered RC phase handoff")
    phases = manifest.get("phases")
    handoffs = manifest.get("handoffs")
    if not isinstance(phases, list) or len(phases) != 3 or not isinstance(handoffs, list) or len(handoffs) != 2:
        raise ValueError("RC shell requires three phases and two handoffs")
    if manifest.get("readback_words") != 237:
        raise ValueError("RC readback ABI must contain 237 words")
    tops = []
    cursor = 0
    for index, phase in enumerate(phases):
        if phase.get("name") != PHASES[index]:
            raise ValueError("RC phase names are not canonical")
        top = phase.get("top")
        if not isinstance(top, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", top):
            raise ValueError("invalid compiler phase top")
        tops.append(top)
        memories = phase.get("rtl_memories")
        if not isinstance(memories, list) or [m.get("port") for m in memories] != list(range(len(memories))):
            raise ValueError(f"{phase['name']}: RTL memory ports are not dense")
        if len(memories) < 37 or any(m["width"] < 1 or m["depth"] < 1 for m in memories):
            raise ValueError(f"{phase['name']}: missing or invalid RTL memory ports")
        if any(m.get("address_width", max(1, (m["depth"] - 1).bit_length())) < 1 for m in memories):
            raise ValueError(f"{phase['name']}: invalid RTL memory address width")
        token_port = phase["token_input_port"]
        if token_port != (31 if index == 0 else 27) or memories[token_port]["width"] != 64:
            raise ValueError(f"{phase['name']}: token input port is invalid")
        if memories[token_port]["depth"] < (8 if index == 0 else 1):
            raise ValueError(f"{phase['name']}: token input memory is too shallow")
        logits = phase["logits"]
        if logits["port"] != 32 or logits["words"] != 6 or memories[32]["width"] != 32:
            raise ValueError(f"{phase['name']}: logits port is invalid")
        if logits["offset"] != (42 if index == 0 else 0) or memories[32]["depth"] < logits["offset"] + 6:
            raise ValueError(f"{phase['name']}: logits memory is too shallow")
        if phase["token_address"] != cursor:
            raise ValueError("token readback addresses are not contiguous")
        cursor += 7
        leaves = phase["cache_outputs"]
        if len(leaves) != 4:
            raise ValueError("RC phase requires four cache output leaves")
        for leaf, item in enumerate(leaves):
            if item["leaf"] != leaf or item["port"] != 33 + leaf or item["width"] != 32:
                raise ValueError("cache output leaf order or width is invalid")
            if item["readback_address"] != cursor or item["words"] != 2 * (8 + index):
                raise ValueError("cache readback address or word count is invalid")
            if memories[item["port"]]["width"] != 32 or memories[item["port"]]["depth"] < item["words"]:
                raise ValueError("cache output memory is too shallow")
            cursor += item["words"]
    if len(set(tops)) != 3 or cursor != 237:
        raise ValueError("phase tops collide or readback coverage is incomplete")
    for index, handoff in enumerate(handoffs):
        src, dst = phases[index], phases[index + 1]
        if (handoff["source"], handoff["destination"]) != (src["name"], dst["name"]):
            raise ValueError("phase handoff order is invalid")
        if handoff["token_source_port"] != 32 or handoff["token_destination_port"] != dst["token_input_port"]:
            raise ValueError("token feedback port is invalid")
        if len(handoff["cache"]) != 4:
            raise ValueError("phase handoff cache arity is invalid")
        for leaf, link in enumerate(handoff["cache"]):
            src_port, dst_port = 33 + leaf, 28 + leaf
            if (link["source_port"], link["destination_port"], link["width"], link["words"]) != (
                src_port, dst_port, 32, 2 * (8 + index)
            ):
                raise ValueError("phase cache handoff port, width or depth is invalid")
            memory = dst["rtl_memories"][dst_port]
            if memory["width"] != 32 or memory["depth"] < link["words"]:
                raise ValueError("destination cache memory is too shallow")


def _memory_name(phase: int, port: int) -> str:
    return f"mem_p{phase}_{port}"


def render_shell(manifest: dict) -> str:
    """Emit synthesizable memory service, token feedback and cache sequencing."""
    _validate(manifest)
    phases = manifest["phases"]
    lines = [
        "`timescale 1ns/1ps",
        "module rc_phase_composed(",
        "  input logic clk, reset, prompt_write, start,",
        "  input logic [2:0] prompt_index,",
        "  input logic [63:0] prompt_data,",
        "  input logic [7:0] readback_addr,",
        "  output logic [63:0] readback_data,",
        "  output logic busy, done, error,",
        "  output logic [63:0] token0, token1, token2",
        ");",
        "localparam logic [3:0] IDLE=0, RUN0=1, ARGMAX0=2, COPY0=3,",
        "  RUN1=4, ARGMAX1=5, COPY1=6, RUN2=7, ARGMAX2=8, FINISHED=9;",
        "logic [3:0] state;",
        "logic [7:0] prompt_mask;",
        "logic [6:0] copy_cursor;",
        "wire [2:0] core_done;",
        "assign busy = state != IDLE && state != FINISHED;",
        "assign done = state == FINISHED;",
        "function automatic [31:0] finite_f32_key(input [31:0] bits);",
        "  if (bits[30:0] == 0) finite_f32_key = 32'h80000000;",
        "  else if (bits[31]) finite_f32_key = ~bits;",
        "  else finite_f32_key = bits ^ 32'h80000000;",
        "endfunction",
    ]
    for p, phase in enumerate(phases):
        lines.append(f"wire core_go{p} = state == RUN{p};")
        for memory in phase["rtl_memories"]:
            port, width, depth = (memory[k] for k in ("port", "width", "depth"))
            aw = memory.get("address_width", max(1, (depth - 1).bit_length()))
            stem = f"a{p}_{port}"
            mem = _memory_name(p, port)
            lines += [f"logic [{width - 1}:0] {mem} [0:{depth - 1}];",
                      f"wire [{aw - 1}:0] {stem}_addr;",
                      f"wire {stem}_en, {stem}_we;",
                      f"wire [{width - 1}:0] {stem}_wdata;",
                      f"logic [{width - 1}:0] {stem}_rdata;",
                      f"logic {stem}_done;"]
            special = []
            if p == 0 and port == phase["token_input_port"]:
                special.append(f"if (state == IDLE && prompt_write) {mem}[prompt_index] <= prompt_data;")
            if p in (1, 2) and port == phase["token_input_port"]:
                special.append(f"if (state == ARGMAX{p - 1}) {mem}[0] <= {{61'd0, argmax{p - 1}}};")
            if p in (1, 2) and 28 <= port <= 31:
                leaf = port - 28
                offset = sum(link["words"] for link in manifest["handoffs"][p - 1]["cache"][:leaf])
                count = manifest["handoffs"][p - 1]["cache"][leaf]["words"]
                source = _memory_name(p - 1, 33 + leaf)
                special.append(
                    f"if (state == COPY{p - 1} && copy_cursor >= {offset} && copy_cursor < {offset + count}) "
                    f"{mem}[copy_cursor - {offset}] <= {source}[copy_cursor - {offset}];"
                )
            lines += ["always_ff @(posedge clk) begin",
                      f"  if (reset) begin {stem}_done <= 0; {stem}_rdata <= '0; end",
                      f"  else begin {stem}_done <= {stem}_en;",
                      f"    if ({stem}_en) begin",
                      f"      if ({stem}_we) {mem}[{stem}_addr] <= {stem}_wdata;",
                      f"      else {stem}_rdata <= {mem}[{stem}_addr];",
                      "    end",
                      *(f"    {item}" for item in special),
                      "  end",
                      "end"]
        connections = [".clk(clk)", ".reset(reset)", f".go(core_go{p})", f".done(core_done[{p}])"]
        for memory in phase["rtl_memories"]:
            port = memory["port"]
            stem = f"a{p}_{port}"
            connections += [f".arg_mem_{port}_addr0({stem}_addr)",
                            f".arg_mem_{port}_content_en({stem}_en)",
                            f".arg_mem_{port}_write_en({stem}_we)",
                            f".arg_mem_{port}_write_data({stem}_wdata)",
                            f".arg_mem_{port}_read_data({stem}_rdata)",
                            f".arg_mem_{port}_done({stem}_done)"]
        lines += [f"{phase['top']} phase{p}(" + ",\n  ".join(connections) + ");"]
        logits = phase["logits"]
        mem = _memory_name(p, logits["port"])
        lines += [f"logic [2:0] argmax{p};",
                  f"logic argmax{p}_nan;",
                  f"logic [31:0] argmax{p}_best_key;",
                  "always_comb begin",
                  f"  argmax{p} = 0;",
                  f"  argmax{p}_best_key = finite_f32_key({mem}[{logits['offset']}]);",
                  f"  argmax{p}_nan = 0;",
                  "  for (int i=0; i<6; i++) begin",
                  f"    if ({mem}[{logits['offset']}+i][30:23] == 8'hff && {mem}[{logits['offset']}+i][22:0] != 0) argmax{p}_nan = 1;",
                  f"    if (i > 0 && finite_f32_key({mem}[{logits['offset']}+i]) > argmax{p}_best_key) begin",
                  f"      argmax{p}_best_key = finite_f32_key({mem}[{logits['offset']}+i]);",
                  f"      argmax{p} = i[2:0];",
                  "    end",
                  "  end",
                  "end"]
    lines += [
        "always_ff @(posedge clk) begin",
        "  if (reset) begin",
        "    state <= IDLE; prompt_mask <= 0; copy_cursor <= 0; error <= 0;",
        "    token0 <= 0; token1 <= 0; token2 <= 0;",
        "  end else begin",
        "    if (start && state != IDLE) error <= 1;",
        "    case (state)",
        "      IDLE: begin",
        "        if (prompt_write) prompt_mask[prompt_index] <= 1;",
        "        if (start) begin",
        "          if (prompt_mask == 8'hff && !prompt_write) state <= RUN0;",
        "          else error <= 1;",
        "        end",
        "      end",
        "      RUN0: if (core_done[0]) state <= ARGMAX0;",
        "      ARGMAX0: begin token0 <= {61'd0, argmax0}; if (argmax0_nan) error <= 1; copy_cursor <= 0; state <= COPY0; end",
        f"      COPY0: if (copy_cursor == {sum(x['words'] for x in manifest['handoffs'][0]['cache']) - 1}) state <= RUN1; else copy_cursor <= copy_cursor + 1;",
        "      RUN1: if (core_done[1]) state <= ARGMAX1;",
        "      ARGMAX1: begin token1 <= {61'd0, argmax1}; if (argmax1_nan) error <= 1; copy_cursor <= 0; state <= COPY1; end",
        f"      COPY1: if (copy_cursor == {sum(x['words'] for x in manifest['handoffs'][1]['cache']) - 1}) state <= RUN2; else copy_cursor <= copy_cursor + 1;",
        "      RUN2: if (core_done[2]) state <= ARGMAX2;",
        "      ARGMAX2: begin token2 <= {61'd0, argmax2}; if (argmax2_nan) error <= 1; state <= FINISHED; end",
        "      default: state <= FINISHED;",
        "    endcase",
        "  end",
        "end",
        "always_comb begin",
        "  readback_data = 0;",
        "  case (readback_addr)",
    ]
    for p, phase in enumerate(phases):
        lines.append(f"    8'd{phase['token_address']}: readback_data = token{p};")
        for index in range(6):
            address = phase["token_address"] + 1 + index
            lines.append(f"    8'd{address}: readback_data = {{32'd0, {_memory_name(p, 32)}[{phase['logits']['offset'] + index}]}};")
        for item in phase["cache_outputs"]:
            for index in range(item["words"]):
                address = item["readback_address"] + index
                lines.append(f"    8'd{address}: readback_data = {{32'd0, {_memory_name(p, item['port'])}[{index}]}};")
    lines += ["    default: readback_data = 0;", "  endcase", "end", "initial begin"]
    for p, phase in enumerate(phases):
        for memory in phase["rtl_memories"]:
            port, depth = memory["port"], memory["depth"]
            mem = _memory_name(p, port)
            lines.append(f"  for (int i=0; i<{depth}; i++) {mem}[i] = '0;")
            if str(port) in phase["initial_memories"]:
                lines.append(f'  $readmemh("phase{p}_mem{port}.hex", {mem});')
    lines += ["end", "endmodule", ""]
    return "\n".join(lines)


def write_package(manifest: dict, source_paths: dict[str, Path], output: Path) -> dict:
    """Materialize source-linked shell, memory images and a hash receipt."""
    shell = render_shell(manifest)
    source_payloads = {}
    for phase in manifest["phases"]:
        path = source_paths[phase["name"]]
        payload = path.read_bytes()
        expected = phase.get("namespaced_sv_sha256")
        if expected is not None and hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"{phase['name']}: source hash does not match handoff manifest")
        source_payloads[phase["name"]] = payload
    output.mkdir(parents=True, exist_ok=True)
    shell_path = output / "rc_phase_composed.sv"
    shell_path.write_text(shell)
    file_hashes = {shell_path.name: hashlib.sha256(shell.encode()).hexdigest()}
    for index, phase in enumerate(manifest["phases"]):
        path = source_paths[phase["name"]]
        payload = source_payloads[phase["name"]]
        file_hashes[str(path)] = hashlib.sha256(payload).hexdigest()
        for port, image in phase["initial_memories"].items():
            name = f"phase{index}_mem{port}.hex"
            (output / name).write_text("\n".join(image["words"]) + "\n")
            file_hashes[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    receipt = {"schema": "llm2fpga.rc-phase-composed-package-v1",
               "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
               "files": file_hashes, "sources": [str(source_paths[p["name"]]) for p in manifest["phases"]]}
    (output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--prefill-sv", required=True, type=Path)
    parser.add_argument("--decode8-sv", required=True, type=Path)
    parser.add_argument("--decode9-sv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    write_package(manifest, dict(zip(PHASES, (args.prefill_sv, args.decode8_sv, args.decode9_sv))), args.output)


if __name__ == "__main__":
    main()
