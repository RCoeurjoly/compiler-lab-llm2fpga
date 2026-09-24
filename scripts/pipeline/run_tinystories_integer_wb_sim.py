#!/usr/bin/env python3
"""Run exact-image transaction simulation for the generated RC Wishbone top."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


def _load_helpers(path: Path):
    spec = importlib.util.spec_from_file_location("rc_sv_helpers_wb_sim", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _render_tb(ports, external_ports: list[int], expected: int) -> str:
    ext_index = {port: index for index, port in enumerate(external_ports)}
    declarations = [
        "  logic clk = 0; always #1 clk = ~clk;",
        "  logic reset = 1, go = 0;",
        "  logic [127:0] token_data;",
        "  logic done; logic wb_cyc, wb_stb; logic [31:0] wb_addr; logic [15:0] wb_sel;",
        "  logic wb_accept = 0, wb_ack = 0, wb_err = 0; logic [127:0] wb_rdata = 0;",
        "  logic [7:0] result0, result1;",
        "  logic [63:0] token_words [0:1];",
        "  integer owner = -1; integer saved_addr = 0; integer pending = 0;",
    ]
    for port in ports:
        if port.number in external_ports:
            declarations.append(f"  logic [{port.width - 1}:0] mem{port.number} [0:{port.depth - 1}];")
    connections = [
        ".clk(clk), .reset(reset), .go(go), .token_data(token_data), .done(done),",
        ".wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_addr(wb_addr), .wb_sel(wb_sel),",
        ".wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata),",
        ".result0(result0), .result1(result1)",
    ]
    initial_loads = ["    $readmemh(\"token.hex\", token_words);", "    token_data = 128'd0;"]
    for port in ports:
        if port.number in external_ports:
            initial_loads.append(f'    $readmemh("mem{port.number}.hex", mem{port.number});')
    response_cases = []
    for port in ports:
        if port.number not in ext_index:
            continue
        index = ext_index[port.number]
        bytes_per_element = max(1, (port.width + 7) // 8)
        response_cases.append(
            f"          {index}: begin wb_rdata <= 128'd0; "
            f"wb_rdata[((saved_addr & 15) * 8) +: {port.width}] <= "
            f"mem{port.number}[saved_addr / {bytes_per_element}]; end"
        )
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tb;",
        *declarations,
        "  tinystories_integer_rc_wb_top dut(",
        "    " + "\n    ".join(connections) + ");",
        "  assign token_data = {token_words[1], token_words[0]};",
        "  assign wb_accept = wb_cyc && wb_stb;",
        "  always_ff @(posedge clk) begin",
        "    if (reset) begin wb_ack <= 1'b0; wb_rdata <= '0; pending <= 0; owner <= -1; end",
        "    else begin",
        "      wb_ack <= 1'b0;",
        "      if (pending != 0) begin",
        "        wb_ack <= 1'b1; pending <= 0;",
        "        case (owner)",
        *response_cases,
        "          default: wb_rdata <= '0;",
        "        endcase",
        "      end else if (wb_cyc && wb_stb) begin",
        "        pending <= 1; saved_addr <= dut.external_memory.arbiter.saved_addr;",
        "        owner <= dut.external_memory.arbiter.owner;",
        "      end",
        "    end",
        "  end",
        "  initial begin",
        *initial_loads,
        "    repeat (5) @(posedge clk); reset <= 0; repeat (2) @(posedge clk); go <= 1;",
        "    wait(done); #1;",
        f"    if ({{result1, result0}} !== 16'h{expected:04x}) $fatal(1, \"WB_RC_FAIL result=%h\", {{result1, result0}});",
        "    $display(\"WB_RC_PASS result=%h\", {result1, result0}); $finish;",
        "  end",
        "  initial begin repeat (200000) @(posedge clk); $fatal(1, \"WB_RC_TIMEOUT\"); end",
        "endmodule",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrapper-dir", type=Path, required=True)
    parser.add_argument("--generated-sv", type=Path, required=True)
    parser.add_argument("--helpers", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--build-timeout", type=int, default=300)
    parser.add_argument("--build-jobs", type=int, default=4)
    args = parser.parse_args()
    manifest = json.loads((args.wrapper_dir / "manifest.json").read_text())
    helpers = _load_helpers(args.helpers)
    ports = helpers.parse_sv_memory_ports(args.generated_sv.read_text())
    tb_text = _render_tb(ports, manifest["external_ports"], expected=0x4CFE)
    with tempfile.TemporaryDirectory(prefix="rc-wb-sim-") as directory:
        path = Path(directory)
        (path / "tb.sv").write_text(tb_text)
        for source in (args.wrapper_dir / "top.sv", args.generated_sv,
                       Path("rtl/memory/llm_compiler_memory_wb_adapter.sv"),
                       Path("rtl/memory/llm_external_memory_arbiter.sv")):
            target = path / source.name
            target.symlink_to(source.resolve())
        for image in args.wrapper_dir.glob("*.hex"):
            (path / image.name).symlink_to(image.resolve())
        subprocess.run([
            args.verilator, "--binary", "--timing", "-Wno-fatal", "--build-jobs", str(args.build_jobs),
            "--top-module", "tb",
            str(path / "tb.sv"), str(path / "top.sv"), str(path / args.generated_sv.name),
            str(path / "llm_compiler_memory_wb_adapter.sv"),
            str(path / "llm_external_memory_arbiter.sv"),
        ], cwd=path, check=True, timeout=args.build_timeout)
        run = subprocess.run([str(path / "obj_dir/Vtb")], cwd=path, capture_output=True,
                             text=True, timeout=120)
        print(run.stdout, end="")
        print(run.stderr, end="")
        if run.returncode:
            raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
