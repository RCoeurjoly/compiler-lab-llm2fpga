"""Lower one generated read-only memory instance to an external port.

This deliberately handles one instance at a time.  It is the small, auditable
vertical slice used before introducing a shared arbiter for all immutable
tensor memories.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


_INSTANCE = re.compile(
    r"(?P<kind>seq_mem_d1(?:_bram|_lutram)?)\s*#\s*\((?P<params>.*?)\)\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<body>.*?)\);",
    re.DOTALL,
)


@dataclass(frozen=True)
class ExternalizationResult:
    source: str
    memory_name: str
    memory_width: int


def _parameter(params: str, name: str) -> int:
    match = re.search(rf"\.\s*{name}\s*\(\s*(\d+)\s*\)", params)
    if not match:
        raise ValueError(f"memory instance is missing {name}")
    return int(match.group(1))


def externalize_memory(source: str, memory_name: str) -> ExternalizationResult:
    """Replace one generated d1 memory and expose a simple external ABI."""

    selected: re.Match[str] | None = None
    for match in _INSTANCE.finditer(source):
        if match.group("name") == memory_name:
            selected = match
            break
    if selected is None:
        raise ValueError(f"memory instance {memory_name!r} not found")
    width = _parameter(selected.group("params"), "WIDTH")
    if width > 64:
        raise ValueError("external memory slice supports widths up to 64 bits")

    main_match = re.search(r"module\s+main\s*\((?P<ports>.*?)\);", source, re.DOTALL)
    if main_match is None:
        raise ValueError("module main declaration not found")
    ports = main_match.group("ports")
    ports += (
        ",\n  output logic ext_mem_req_valid"
        ",\n  input logic ext_mem_req_ready"
        ",\n  output logic [31:0] ext_mem_req_addr"
        ",\n  input logic ext_mem_rsp_valid"
        ",\n  input logic [63:0] ext_mem_rsp_data"
    )
    rewritten = source[: main_match.start("ports")] + ports + source[main_match.end("ports") :]

    # The main declaration edit shifts offsets, so locate the selected instance again.
    selected = next(m for m in _INSTANCE.finditer(rewritten) if m.group("name") == memory_name)
    body = selected.group("body")
    body += (
        ",\n  .ext_req_valid(ext_mem_req_valid)"
        ",\n  .ext_req_ready(ext_mem_req_ready)"
        ",\n  .ext_req_addr(ext_mem_req_addr)"
        ",\n  .ext_rsp_valid(ext_mem_rsp_valid)"
        ",\n  .ext_rsp_data(ext_mem_rsp_data)"
    )
    replacement = "seq_mem_d1_external # (" + selected.group("params") + ") " + memory_name + " (" + body + ");"
    rewritten = rewritten[: selected.start()] + replacement + rewritten[selected.end() :]
    if "module seq_mem_d1_external" not in rewritten:
        rewritten = _EXTERNAL_MODULE + "\n" + rewritten
    return ExternalizationResult(rewritten, memory_name, width)


_EXTERNAL_MODULE = r'''module seq_mem_d1_external #(
    parameter WIDTH = 32,
    parameter SIZE = 16,
    parameter IDX_SIZE = 4
) (
   input wire logic clk,
   input wire logic reset,
   input wire logic [IDX_SIZE-1:0] addr0,
   input wire logic content_en,
   output logic done,
   output logic [WIDTH-1:0] read_data,
   input wire logic [WIDTH-1:0] write_data,
   input wire logic write_en,
   output wire ext_req_valid,
   input wire ext_req_ready,
   output wire [31:0] ext_req_addr,
   input wire ext_rsp_valid,
   input wire [63:0] ext_rsp_data
);
  logic pending;
  assign ext_req_valid = content_en && !write_en && !pending;
  assign ext_req_addr = {{(32-IDX_SIZE){1'b0}}, addr0};
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      done <= 1'b0;
      read_data <= '0;
    end else begin
      done <= 1'b0;
      if (pending && ext_rsp_valid) begin
        read_data <= ext_rsp_data[WIDTH-1:0];
        done <= 1'b1;
        pending <= 1'b0;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
      end
    end
  end
endmodule
'''
