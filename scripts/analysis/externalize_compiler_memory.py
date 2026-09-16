"""Lower one generated read-only memory instance to an external port.

This deliberately handles one instance at a time.  It is the small, auditable
vertical slice used before introducing a shared arbiter for all immutable
tensor memories.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import re
from pathlib import Path


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
    memory_names: tuple[str, ...] = ()
    memory_widths: tuple[int, ...] = ()


def remove_static_initializers(source: str, memory_names: list[str] | tuple[str, ...]) -> str:
    """Remove readmemh calls for memories moved behind the external port."""

    selected = set(memory_names)
    pattern = re.compile(
        r'^[ \t]*\$readmemh\([ \t]*"[^"]+"[ \t]*,[ \t]*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.mem[ \t]*\);[ \t]*\n?',
        re.MULTILINE,
    )
    return pattern.sub(lambda m: "" if m.group("name") in selected else m.group(0), source)


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


def externalize_memories(
    source: str, memory_names: list[str], base_addresses: dict[str, int] | None = None
) -> ExternalizationResult:
    """Externalize several memories through indexed shared-port vectors."""

    names = tuple(memory_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("memory names must be a non-empty unique list")
    matches = {m.group("name"): m for m in _INSTANCE.finditer(source)}
    missing = [name for name in names if name not in matches]
    if missing:
        raise ValueError(f"memory instance {missing[0]!r} not found")
    widths = tuple(_parameter(matches[name].group("params"), "WIDTH") for name in names)
    if any(width > 64 for width in widths):
        raise ValueError("external memory slice supports widths up to 64 bits")
    bases = {name: 0 for name in names}
    if base_addresses is not None:
        for name, address in base_addresses.items():
            if name not in names:
                raise ValueError(f"base address provided for unselected memory {name!r}")
            if address < 0:
                raise ValueError("base address must not be negative")
            bases[name] = address
    main_match = re.search(r"module\s+main\s*\((?P<ports>.*?)\);", source, re.DOTALL)
    if main_match is None:
        raise ValueError("module main declaration not found")
    count = len(names)
    ports = main_match.group("ports") + (
        f",\n  output logic [{count - 1}:0] ext_mem_req_valid"
        f",\n  input logic [{count - 1}:0] ext_mem_req_ready"
        f",\n  output logic [{count * 32 - 1}:0] ext_mem_req_addr"
        f",\n  input logic [{count - 1}:0] ext_mem_rsp_valid"
        f",\n  input logic [{count * 64 - 1}:0] ext_mem_rsp_data"
    )
    rewritten = source[: main_match.start("ports")] + ports + source[main_match.end("ports") :]
    # Replace from the end so source offsets remain valid.
    selected = {
        m.group("name"): m for m in _INSTANCE.finditer(rewritten) if m.group("name") in names
    }
    for index in sorted(range(count), key=lambda i: selected[names[i]].start(), reverse=True):
        name = names[index]
        match = selected[name]
        body = match.group("body") + (
            f",\n  .ext_req_valid(ext_mem_req_valid[{index}])"
            f",\n  .ext_req_ready(ext_mem_req_ready[{index}])"
            f",\n  .ext_req_addr(ext_mem_req_addr[{index * 32 + 31}:{index * 32}])"
            f",\n  .ext_rsp_valid(ext_mem_rsp_valid[{index}])"
            f",\n  .ext_rsp_data(ext_mem_rsp_data[{index * 64 + 63}:{index * 64}])"
        )
        params = match.group("params") + f",\n    .EXT_BASE_ADDR({bases[name]})"
        replacement = "seq_mem_d1_external # (" + params + ") " + name + " (" + body + ");"
        rewritten = rewritten[: match.start()] + replacement + rewritten[match.end() :]
    if "module seq_mem_d1_external" not in rewritten:
        rewritten = _EXTERNAL_MODULE + "\n" + rewritten
    return ExternalizationResult(rewritten, names[0], widths[0], names, widths)


_EXTERNAL_MODULE = r'''module seq_mem_d1_external #(
    parameter WIDTH = 32,
    parameter SIZE = 16,
    parameter IDX_SIZE = 4,
    parameter EXT_BASE_ADDR = 0
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
  // content_en is a level in the generated memory ABI. Hold a completed
  // response until the requester drops it, otherwise one read is re-issued
  // every cycle while the consumer waits for other operands.
  logic served;
  assign ext_req_valid = content_en && !write_en && !pending && !served;
  assign ext_req_addr = EXT_BASE_ADDR + (addr0 * (WIDTH / 8));
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      served <= 1'b0;
      done <= 1'b0;
      read_data <= '0;
    end else begin
      done <= served;
      if (!content_en || write_en) begin
        pending <= 1'b0;
        served <= 1'b0;
      end else if (pending && ext_rsp_valid) begin
        read_data <= ext_rsp_data[WIDTH-1:0];
        done <= 1'b1;
        pending <= 1'b0;
        served <= 1'b1;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
      end
    end
  end
endmodule
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tensors = manifest.get("tensors", [])
    names = [item["name"] for item in tensors]
    bases = {item["name"]: int(item["ddr3_offset"]) for item in tensors}
    source = args.input.read_text(encoding="utf-8")
    source = remove_static_initializers(source, names)
    result = externalize_memories(source, names, bases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.source, encoding="utf-8")
    print(json.dumps({"memory_count": len(names), "memory_names": names}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
