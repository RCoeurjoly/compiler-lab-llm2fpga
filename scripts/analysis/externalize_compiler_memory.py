"""Lower one generated read-only memory instance to an external port.

This deliberately handles one instance at a time.  It is the small, auditable
vertical slice used before introducing a shared arbiter for all immutable
tensor memories.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import re
from pathlib import Path


_INSTANCE = re.compile(
    r"(?P<kind>seq_mem_d1(?:_bram|_lutram)?)\s*#\s*\((?P<params>.*?)\)\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<body>.*?)\);",
    re.DOTALL,
)
_BANK_CONTENT_ASSIGNMENT = re.compile(
    r"(?m)^(?P<prefix>[ \t]*assign\s+token_weight_codes_i8_b(?P<index>\d+)_content_en\s*=\s*)"
    r"(?P<rhs>[^;]+);"
)
_BANK_SELECTION_MARKER = "// LLM2FPGA selected-bank external-memory reads v1"
_COMPLETION_JOIN_MARKER = "// LLM2FPGA latency-tolerant external-memory joins v1"


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


def select_banked_memory_reads(source: str) -> str:
    """Gate the banked INT8 weight memories by their existing address selectors.

    The generated design keeps the read-data muxes, but its generic BRAM
    lowering enables every bank and waits for every bank on each read. That is
    correct with parallel BRAMs but needlessly serializes all banks through a
    single external-memory port. This pass preserves the selected data value
    while requesting and waiting for only the bank selected by each existing
    mux address.
    """

    if _BANK_SELECTION_MARKER in source:
        return source
    assignments = list(_BANK_CONTENT_ASSIGNMENT.finditer(source))
    if not assignments:
        return source
    indices = sorted(int(match.group("index")) for match in assignments)
    if len(indices) != len(set(indices)) or indices != list(range(len(indices))):
        raise ValueError("token_weight_codes_i8 banks must be unique and contiguous from b0")
    if indices[-1] >= 256:
        raise ValueError("token_weight_codes_i8 bank index exceeds the generated 8-bit selector")

    expected_enable_terms = {
        "lm_gemv_read_operands_go_out",
        "model_read_token_codes_go_out",
    }
    for match in assignments:
        terms = {term.strip() for term in re.split(r"\s*\|\s*", match.group("rhs"))}
        if terms != expected_enable_terms:
            raise ValueError(
                f"unsupported read enables for token-weight bank b{match.group('index')}"
            )

    for selector in ("lm_gemv_weight_bank_out", "model_token_bank_out"):
        if not re.search(rf"\b{selector}\b", source):
            raise ValueError(f"generated bank selector {selector} is missing")

    def selected_done(selector: str) -> str:
        return " | ".join(
            f"(({selector} == 8'd{index}) & token_weight_codes_i8_b{index}_done)"
            for index in indices
        )

    rewritten = source

    def rewrite_enable(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        return (
            f"{match.group('prefix')}"
            f"((lm_gemv_read_operands_go_out && "
            f"(lm_gemv_weight_bank_out == 8'd{index})) || "
            f"(model_read_token_codes_go_out && "
            f"(model_token_bank_out == 8'd{index})));"
        )

    rewritten = _BANK_CONTENT_ASSIGNMENT.sub(rewrite_enable, rewritten)

    def rewrite_done(signal: str, selector: str) -> None:
        nonlocal rewritten
        pattern = re.compile(
            rf"(?m)^(?P<prefix>[ \t]*assign\s+{signal}\s*=\s*)(?P<rhs>[^;]+);"
        )
        match = pattern.search(rewritten)
        if match is None or pattern.search(rewritten, match.end()) is not None:
            raise ValueError(f"expected exactly one generated {signal} assignment")
        terms = [term.strip() for term in re.split(r"\s*&\s*", match.group("rhs"))]
        found = []
        other_terms = []
        for term in terms:
            bank_match = re.fullmatch(r"token_weight_codes_i8_b(\d+)_done", term)
            if bank_match:
                found.append(int(bank_match.group(1)))
            else:
                other_terms.append(term)
        if sorted(found) != indices:
            raise ValueError(f"{signal} must wait for each token-weight bank exactly once")
        rhs_terms = other_terms + [f"({selected_done(selector)})"]
        replacement = f"{match.group('prefix')}{' & '.join(rhs_terms)};"
        rewritten = rewritten[: match.start()] + replacement + rewritten[match.end() :]

    rewrite_done("lm_gemv_read_operands_done_in", "lm_gemv_weight_bank_out")
    rewrite_done("model_read_token_codes_done_in", "model_token_bank_out")
    return f"{_BANK_SELECTION_MARKER}\n{rewritten}"


def _split_top_level_and(expression: str) -> list[str]:
    """Split an expression at top-level bitwise AND operators."""

    terms: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses in generated completion expression")
        elif (
            char == "&"
            and depth == 0
            and (index == 0 or expression[index - 1] != "&")
            and (index + 1 == len(expression) or expression[index + 1] != "&")
        ):
            terms.append(expression[start:index].strip())
            start = index + 1
    if depth != 0:
        raise ValueError("unbalanced parentheses in generated completion expression")
    terms.append(expression[start:].strip())
    if any(not term for term in terms):
        raise ValueError("empty operand in generated completion expression")
    return terms


def latch_external_memory_completion_joins(
    source: str, memory_names: list[str] | tuple[str, ...]
) -> str:
    """Latch independently timed completion operands for external-memory joins."""

    if _COMPLETION_JOIN_MARKER in source:
        return source
    external_done = {f"{name}_done" for name in memory_names}
    if not external_done:
        return source
    assignment = re.compile(
        r"(?m)^(?P<prefix>[ \t]*assign\s+(?P<signal>[A-Za-z_][A-Za-z0-9_]*_done_in)\s*=\s*)"
        r"(?P<rhs>[^;]+);"
    )
    rewritten = source
    for match in reversed(list(assignment.finditer(source))):
        terms = _split_top_level_and(match.group("rhs"))
        if len(terms) < 2:
            continue
        identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", match.group("rhs")))
        if not identifiers.intersection(external_done):
            continue

        signal = match.group("signal")
        phase = signal.removesuffix("_done_in")
        go_signal = f"{phase}_go_out"
        if not re.search(rf"\b{re.escape(go_signal)}\b", source):
            raise ValueError(f"generated completion join {signal} has no {go_signal} phase")
        seen = f"llm2fpga_{phase}_completion_seen"
        if re.search(rf"\b{re.escape(seen)}\b", source):
            raise ValueError(f"generated completion join state already exists: {seen}")
        captures = "\n".join(
            f"      if ({term}) {seen}[{index}] <= 1'b1;"
            for index, term in enumerate(terms)
        )
        replacement = (
            f"logic [{len(terms) - 1}:0] {seen};\n"
            "always_ff @(posedge clk) begin\n"
            f"  if (reset) {seen} <= '0;\n"
            f"  else if (!{go_signal}) {seen} <= '0;\n"
            "  else begin\n"
            f"{captures}\n"
            "  end\n"
            "end\n"
            f"assign {signal} = &{seen};"
        )
        rewritten = rewritten[: match.start()] + replacement + rewritten[match.end() :]
    if rewritten == source:
        return source
    return f"{_COMPLETION_JOIN_MARKER}\n{rewritten}"


def _parameter(params: str, name: str) -> int:
    match = re.search(rf"\.\s*{name}\s*\(\s*(\d+)\s*\)", params)
    if not match:
        raise ValueError(f"memory instance is missing {name}")
    return int(match.group(1))


def legalize_static_external_reads(
    source: str, memory_names: list[str] | tuple[str, ...]
) -> str:
    """Wait at the end of audited TinyStories static memory-read windows.

    Dynamic groups consume ``done``; static Calyx schedules instead assume
    BRAM latency. Keep their read window open until the external response is
    captured, before executing any downstream writes. These exact schedules
    were audited for side effects in the stalled phase. Reject unfamiliar
    static schedules rather than silently claiming variable-latency support.
    This is not a general static-to-dynamic Calyx conversion.
    """
    schedules = {
        "attention_exp_lut_q1_20": (
            "fsm_out < 4'd2 & early_reset_static_par_thread8_go_out",
            "fsm_out == 4'd1",
        ),
        "gelu_lut_q12": (
            "(fsm_out < 4'd2 | fsm_out >= 4'd3 & fsm_out < 4'd5) & early_reset_static_seq50_go_out",
            "fsm_out == 4'd1 || fsm_out == 4'd4",
        ),
        "prompt_tokens": (
            "cond_wire_out & fsm_out >= 4'd1 & fsm_out < 4'd3 & early_reset_static_seq0_go_out",
            "fsm_out == 4'd2",
        ),
    }
    states = []
    waits = []
    for name in memory_names:
        assignments = re.findall(
            rf"\bassign\s+{re.escape(name)}_content_en\s*=\s*([^;]+);", source
        )
        if not assignments:
            continue
        if len(assignments) != 1:
            raise ValueError(f"ambiguous content enable for {name}")
        expression = assignments[0]
        if "fsm_out" not in expression and "early_reset_static" not in expression:
            continue
        expected = schedules.get(name)
        if expected is None or re.sub(r"\s+", "", expression) != re.sub(r"\s+", "", expected[0]):
            raise ValueError(f"unsupported static external-read schedule for {name}")
        seen = f"llm2fpga_{name}_static_response_seen"
        if re.search(rf"\b{seen}\b", source):
            raise ValueError(f"static external-read schedule already legalized for {name}")
        states.append(
            f"logic {seen};\n"
            "always_ff @(posedge clk) begin\n"
            f"  if (reset || !{name}_content_en) {seen} <= 1'b0;\n"
            f"  else if ({name}_done) {seen} <= 1'b1;\n"
            "end\n"
        )
        waits.append(
            f"({name}_content_en && ({expected[1]}) && !({name}_done || {seen}))"
        )
    if not waits:
        return source
    scheduler = list(re.finditer(r"\bassign\s+fsm_write_en\s*=\s*([^;]+);", source))
    if len(scheduler) != 1:
        raise ValueError("static external reads require exactly one audited fsm_write_en")
    match = scheduler[0]
    replacement = (
        "// LLM2FPGA latency-tolerant static external-memory reads v1\n"
        + "".join(states)
        + f"assign fsm_write_en = ({match[1]}) && !(" + " || ".join(waits) + ");"
    )
    return source[:match.start()] + replacement + source[match.end():]


def externalize_memory(source: str, memory_name: str) -> ExternalizationResult:
    """Replace one generated d1 memory and expose a simple external ABI."""

    source = legalize_static_external_reads(source, [memory_name])
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
    """Externalize several memories through indexed shared-port vectors.

    Before exposing the banked INT8 weight memories, lower their existing
    output-mux selectors into one-hot external read enables and selected-bank
    completion. This prevents a single external port from serializing reads
    from every inactive BRAM bank.
    """

    names = tuple(memory_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("memory names must be a non-empty unique list")
    source = select_banked_memory_reads(source)
    source = latch_external_memory_completion_joins(source, names)
    source = legalize_static_external_reads(source, names)
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
    parameter INIT_FILE = "",
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
  logic response_ready;
  logic [IDX_SIZE-1:0] request_index;
  logic [IDX_SIZE-1:0] response_index;
  // A DDR3 response supplies one 64-bit lane.  Narrow elements may start at
  // any byte offset within that lane, so retain the request offset until the
  // one-cycle response arrives.
  logic [2:0] response_byte_offset;
  // Emit one response pulse and suppress duplicate reads until the client
  // advances its address or ends the current operation. The generated join
  // lowering captures pulses from independent external-memory responses.
  assign ext_req_valid = content_en && !write_en && !pending &&
    (!response_ready || (response_index != addr0));
  assign ext_req_addr = EXT_BASE_ADDR + (addr0 * (WIDTH / 8));
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      response_ready <= 1'b0;
      request_index <= '0;
      response_index <= '0;
      response_byte_offset <= '0;
      done <= 1'b0;
      read_data <= '0;
    end else begin
      done <= pending && ext_rsp_valid;
      if (!content_en || write_en)
        response_ready <= 1'b0;
      if (pending && ext_rsp_valid) begin
        read_data <= ext_rsp_data >> (response_byte_offset * 8);
        response_index <= request_index;
        pending <= 1'b0;
        response_ready <= content_en && !write_en;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
        request_index <= addr0;
        response_byte_offset <= ext_req_addr[2:0];
        response_ready <= 1'b0;
      end
    end
  end
endmodule
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--select-banked-reads-only",
        action="store_true",
        help="apply the bank-select lowering to already externalized RTL",
    )
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    if args.select_banked_reads_only:
        result_source = select_banked_memory_reads(source)
        bank_count = len(_BANK_CONTENT_ASSIGNMENT.findall(source))
        report = {
            "bank_count": bank_count,
            "input_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "output_sha256": hashlib.sha256(result_source.encode("utf-8")).hexdigest(),
            "pass": "selected-bank-external-memory-reads-v1",
        }
    else:
        if args.manifest is None:
            parser.error("--manifest is required unless --select-banked-reads-only is used")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        tensors = manifest.get("tensors", [])
        names = [item["name"] for item in tensors]
        bases = {item["name"]: int(item["ddr3_offset"]) for item in tensors}
        source = remove_static_initializers(source, names)
        result = externalize_memories(source, names, bases)
        result_source = result.source
        report = {
            "memory_count": len(names),
            "memory_names": names,
            "output_sha256": hashlib.sha256(result_source.encode("utf-8")).hexdigest(),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result_source, encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
