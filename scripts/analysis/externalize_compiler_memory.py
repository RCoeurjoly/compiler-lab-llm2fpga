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
    r"(?P<kind>(?:seq_mem_d1|dyn_mem_d1)(?:_bram|_lutram)?)\s*#\s*\((?P<params>.*?)\)\s*"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<body>.*?)\);",
    re.DOTALL,
)
_EXTERNAL_INSTANCE = re.compile(
    r"(?<!module )(?P<kind>seq_mem_d1_external)\s*#\s*\((?P<params>.*?)\)\s*"
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
    """Remove generated read/write-memory calls for externalized memories.

    Calyx emits both literal paths (``$readmemh("...", mem.mem)``) and
    concatenated ``DATA`` paths (``$readmemh({DATA, "..."}, mem.mem)``).
    Once the instance is replaced by ``seq_mem_d1_external`` it has no local
    ``mem`` array, so either form must be removed.  Keep this bounded to the
    selected instance names and to one generated call per line.
    """

    selected = set(memory_names)
    pattern = re.compile(
        r'^[ \t]*\$(?:read|write)memh\([^;]*,[ \t]*'
        r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.mem[ \t]*\);[ \t]*\n?',
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
        # Token lookup has one selected-bank completion expression, but its
        # selector-to-done-to-go feedback is also a measured critical path.
        # Register that predicate without discarding bank qualification.
        if len(terms) < 2 and match.group("signal") != "model_read_token_codes_done_in":
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


def _resolve_guard_aliases(source: str, expression: str) -> str:
    """Resolve generated single-wire guard aliases for static-read matching.

    The Calyx Verilog emitter commonly factors a static memory enable through
    several ``_guardN`` wires.  Static-read legalization must inspect the
    semantic predicate, not the emitter's arbitrary alias number.  Resolve
    only whole-expression single identifiers, with a bounded depth and no
    general expression rewriting.
    """

    assignments = {
        name: rhs.strip()
        for name, rhs in re.findall(
            r"(?m)^\s*wire\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+);", source
        )
    }
    def resolve_token(name: str, stack: tuple[str, ...]) -> str:
        if name not in assignments:
            return name
        if name in stack:
            raise ValueError(f"cyclic generated guard alias {name}")
        return re.sub(
            r"\b[A-Za-z_][A-Za-z0-9_]*\b",
            lambda match: resolve_token(match.group(0), stack + (name,)),
            assignments[name],
        )

    return re.sub(
        r"\b[A-Za-z_][A-Za-z0-9_]*\b",
        lambda match: resolve_token(match.group(0), ()),
        expression.strip(),
    )


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
    # The production generator's two-token schedule is semantically the same
    # static lookup window but Calyx may renumber its FSM states after the
    # 53-bit requantization specialization. Keep this exact observed variant
    # bounded; unfamiliar schedules remain rejected below.
    observed_regenerated_schedules = {
        "attention_exp_lut_q1_20": (
            "fsm_out == 4'd0 & early_reset_static_par_thread11_go_out",
            "fsm_out == 4'd1",
        ),
        "gelu_lut_q12": (
            "(fsm_out == 4'd0 | fsm_out == 4'd2) & early_reset_static_seq46_go_out",
            "fsm_out == 4'd1 || fsm_out == 4'd3",
        ),
        "prompt_tokens": (
            "cond_wire_out & fsm_out == 4'd1 & early_reset_static_seq0_go_out",
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
            expression = _resolve_guard_aliases(source, expression)
            if "fsm_out" not in expression and "early_reset_static" not in expression:
                continue
        expected = schedules.get(name)
        observed = observed_regenerated_schedules.get(name)
        normalized = re.sub(r"\s+", "", expression)
        if expected is not None and normalized == re.sub(r"\s+", "", expected[0]):
            selected_schedule = expected
        elif observed is not None and normalized == re.sub(r"\s+", "", observed[0]):
            selected_schedule = observed
        else:
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
        content_guard = f"{name}_content_en && "
        waits.append(f"(({content_guard}({selected_schedule[1]})) && !({name}_done || {seen}))")
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
    rewritten = source[:match.start()] + replacement + source[match.end():]
    # The generated static controller receives an ``undef`` placeholder for
    # its completion input.  That is harmless for fixed one-cycle BRAM reads,
    # but it prevents a variable-latency external response from closing the
    # sequence.  Connect only the audited static sequence corresponding to the
    # selected external memory; unfamiliar schedules remain rejected above.
    done_inputs = {
        "prompt_tokens": "early_reset_static_seq0_done_in",
    }
    for name in memory_names:
        done_signal = done_inputs.get(name)
        if done_signal is None:
            continue
        pattern = re.compile(
            rf"(?m)^([ \t]*assign\s+{re.escape(done_signal)}\s*=\s*)[^;]+;"
        )
        rewritten, count = pattern.subn(
            rf"\1{name}_done;", rewritten, count=1
        )
        # Small schedule fixtures may model the scheduler directly and omit
        # the generated Calyx completion input.  The external-memory wait
        # predicate above is still sufficient for those fixtures; production
        # generated sources retain the explicit completion assignment and are
        # rewired here.
        if count != 1:
            if name == "prompt_tokens":
                continue
            raise ValueError(f"expected generated completion input for {name}")
    return rewritten


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


def canonicalize_static_counter(source: str) -> str:
    """Share identical static-schedule increments, preserving reset priority.

    Only the compiler's known four-bit counter/standard-adder form is accepted.
    No mutually-exclusive-enable assumption is needed: increments before the
    zero branch win; increments after it remain masked by its original guard.
    The register's write-enable (including external-memory waits) is untouched.
    """
    marker = "// LLM2FPGA shared static-counter increment v1"
    if marker in source:
        return source
    main = re.search(r"\bmodule\s+main\b.*?\bendmodule\b", source, re.DOTALL)
    if main is None:
        return source
    body = main.group(0)
    matches = list(re.finditer(r"\bassign\s+fsm_in\s*=([^;]+);", body))
    if not matches:
        return source
    if len(matches) != 1 or not re.search(r"\b(?:logic|wire)\s*\[3:0\]\s+fsm_out\b", body):
        raise ValueError("unsupported static counter declaration")
    match = matches[0]
    chunks = match.group(1).split(":")
    if chunks[-1].strip() != "4'd0":
        raise ValueError("unsupported static counter default")

    def assignment(name: str) -> str:
        found = re.findall(rf"\bassign\s+{re.escape(name)}\s*=([^;]+);", body)
        if len(found) != 1:
            raise ValueError(f"expected exactly one {name} assignment")
        return re.sub(r"\s+", "", found[0])

    before, after = [], []
    zero_guard = None
    for chunk in chunks[:-1]:
        parts = chunk.split("?")
        if len(parts) != 2:
            raise ValueError("unsupported static counter selection")
        guard, value = (part.strip() for part in parts)
        if value == "4'd0":
            if zero_guard is not None:
                raise ValueError("multiple static counter zero branches")
            zero_guard = guard
            continue
        condition = re.fullmatch(r"fsm_out\s*!=\s*4'd\d+\s*&\s*(\w+)", guard)
        adder = re.fullmatch(r"(adder\d*)_out", value)
        if condition is None or adder is None:
            raise ValueError("unsupported static counter increment branch")
        name, enable = adder.group(1), condition.group(1)
        instances = re.findall(
            rf"\bstd_add\s*#\s*\(\s*\.WIDTH\s*\(4\)\s*\)\s+{name}\s*\((.*?)\);",
            body, re.DOTALL,
        )
        expected_ports = {"left": name + "_left", "right": name + "_right", "out": value}
        if len(instances) != 1:
            raise ValueError(f"unsupported static counter adder {name}")
        ports = re.findall(r"\.(\w+)\s*\(\s*(\w+)\s*\)", instances[0])
        if len(ports) != 3 or dict(ports) != expected_ports:
            raise ValueError(f"unsupported static counter wiring {name}")
        if (assignment(name + "_left") != f"{enable}?fsm_out:4'd0"
                or assignment(name + "_right") != f"{enable}?4'd1:4'd0"):
            raise ValueError(f"unsupported static counter operands {name}")
        (before if zero_guard is None else after).append(guard)
    if zero_guard is None or not (before or after):
        raise ValueError("expected static counter increment and zero branches")

    def any_guard(guards: list[str]) -> str:
        return " | ".join(f"({guard})" for guard in guards) or "1'b0"

    increment = f"({any_guard(before)}) | (!({zero_guard}) & ({any_guard(after)}))"
    replacement = f"{marker}\nassign fsm_in = ({increment}) ? (fsm_out + 4'd1) : 4'd0;"
    body = body[:match.start()] + replacement + body[match.end():]
    return source[:main.start()] + body + source[main.end():]


def externalize_memories(
    source: str,
    memory_names: list[str],
    base_addresses: dict[str, int] | None = None,
    *,
    canonicalize_counter: bool = True,
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
    if canonicalize_counter:
        source = canonicalize_static_counter(source)
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
  logic request_queued;
  logic [31:0] queued_address;
  // Keep the captured local index visible to structural timing audits.  It is
  // not on the external request payload, but removing it would make the
  // capture-enable proof impossible to inspect after Yosys optimization.
  (* keep *) logic [IDX_SIZE-1:0] request_index;
  // A DDR3 response supplies one 64-bit lane.  Narrow elements may start at
  // any byte offset within that lane, so retain the request offset until the
  // one-cycle response arrives.
  logic [2:0] response_byte_offset;
  // Emit one response pulse for every enabled read, including repeated
  // same-address reads. Native generated seq_mem instances are level-sensitive
  // while content_en is asserted; suppressing repeats changes their contract.
  // Cut the measured context-token/scheduler/address-to-arbiter timing path.
  // Once captured, a read is irrevocable until accepted (or reset). Keep its
  // identity and byte offset with it, not with the client's changing inputs.
  assign ext_req_valid = request_queued;
  assign ext_req_addr = queued_address;
  // Payload is unobservable until request_queued is asserted. Capture on the
  // enqueue edge, independently of reset, to avoid a wide reset fanout. All
  // transaction-valid state retains reset; a stalled valid address is held.
  always_ff @(posedge clk) begin
    if (!pending && !request_queued)
      queued_address <= EXT_BASE_ADDR + (addr0 * (WIDTH / 8));
  end
  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      request_queued <= 1'b0;
      request_index <= '0;
      response_byte_offset <= '0;
      done <= 1'b0;
      read_data <= '0;
    end else begin
      done <= pending && ext_rsp_valid;
      // Sample the payload whenever the local slot is empty. On the enqueue
      // edge both payload and valid capture the same client inputs; queued/
      // pending then freeze the payload until the transaction has completed.
      // Keep the address mux out of the wide payload-register enable cone
      // measured in the integrated design.
      if (!pending && !request_queued) begin
        request_index <= addr0;
      end
      if (pending && ext_rsp_valid) begin
        read_data <= ext_rsp_data >> (response_byte_offset * 8);
        pending <= 1'b0;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
        request_queued <= 1'b0;
        response_byte_offset <= ext_req_addr[2:0];
      end else if (content_en && !write_en && !pending && !request_queued &&
                   1'b1) begin
        request_queued <= 1'b1;
      end
    end
  end
endmodule
'''


_BANKED_EXTERNAL_MODULE = r'''module seq_mem_d1_shared_banks #(
    parameter integer BANKS = 197,
    parameter integer WIDTH = 8,
    parameter integer SIZE = 16384,
    parameter integer IDX_SIZE = 14,
    parameter [BANKS * 32 - 1:0] BANK_BASES = '0
) (
    input wire clk,
    input wire reset,
    input wire [BANKS * IDX_SIZE - 1:0] addr0,
    input wire [BANKS - 1:0] content_en,
    output logic [BANKS - 1:0] done,
    output logic [BANKS * WIDTH - 1:0] read_data,
    input wire [BANKS * WIDTH - 1:0] write_data,
    input wire [BANKS - 1:0] write_en,
    output wire ext_req_valid,
    input wire ext_req_ready,
    output wire [31:0] ext_req_addr,
    input wire ext_rsp_valid,
    input wire [63:0] ext_rsp_data
);
  logic pending;
  logic request_queued;
  logic [7:0] queued_bank;
  logic [31:0] queued_address;
  logic [2:0] response_byte_offset;
  logic [31:0] selected_address;
  integer bank_index;

  assign ext_req_valid = request_queued;
  assign ext_req_addr = queued_address;

  always_comb begin
    bank_index = 0;
    selected_address = '0;
    for (integer i = 0; i < BANKS; i = i + 1)
      if (content_en[i] && !write_en[i]) begin
        bank_index = i;
        selected_address = BANK_BASES[i * 32 +: 32]
            + (addr0[i * IDX_SIZE +: IDX_SIZE] * (WIDTH / 8));
      end
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      pending <= 1'b0;
      request_queued <= 1'b0;
      queued_bank <= '0;
      queued_address <= '0;
      response_byte_offset <= '0;
      done <= '0;
      read_data <= '0;
    end else begin
      done <= '0;
      if (pending && ext_rsp_valid) begin
        for (integer i = 0; i < BANKS; i = i + 1)
          if (queued_bank == i) begin
            read_data[i * WIDTH +: WIDTH] <=
                ext_rsp_data >> (response_byte_offset * 8);
            done[i] <= 1'b1;
          end
        pending <= 1'b0;
      end else if (ext_req_valid && ext_req_ready) begin
        pending <= 1'b1;
        request_queued <= 1'b0;
        response_byte_offset <= ext_req_addr[2:0];
      end else if (!pending && !request_queued && (|content_en)) begin
        queued_bank <= bank_index;
        queued_address <= selected_address;
        request_queued <= 1'b1;
      end
    end
  end
endmodule
'''


_BANK_NAME = re.compile(r"^token_weight_codes_i8_b(?P<index>\d+)$")


def consolidate_token_weight_banks(
    source: str,
    bank_names: list[str] | tuple[str, ...],
    base_addresses: dict[str, int],
) -> ExternalizationResult:
    """Replace the generated token-bank controllers with one shared controller.

    The external-memory vector ABI is retained.  Each bank keeps its generated
    address/content/read-data/done signals, while only the selected bank is
    presented to one request/response slot.  This is deliberately limited to
    the authenticated token-weight bank naming and width contract.
    """

    names = tuple(bank_names)
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError("shared bank controller requires at least two unique banks")
    parsed = []
    for name in names:
        match = _BANK_NAME.fullmatch(name)
        if match is None:
            raise ValueError(f"unsupported token bank name {name!r}")
        parsed.append((int(match.group("index")), name))
    parsed.sort()
    if [index for index, _ in parsed] != list(range(len(parsed))):
        raise ValueError("token-weight banks must be contiguous from b0")
    names = tuple(name for _, name in parsed)
    if any(name not in base_addresses for name in names):
        raise ValueError("missing token-bank base address")

    # Permit the pass to be used directly on the pre-externalized compiler
    # source in focused tests; production invokes it after all 240 slots are
    # externalized.
    if not all(re.search(rf"\bseq_mem_d1_external\s*#.*?\b{re.escape(name)}\s*\(", source, re.DOTALL)
               for name in names):
        result = externalize_memories(source, list(names), base_addresses)
        source = result.source

    matches = {m.group("name"): m for m in _EXTERNAL_INSTANCE.finditer(source) if m.group("name") in names}
    if set(matches) != set(names):
        raise ValueError("all token banks must be externalized before consolidation")
    widths = {_parameter(matches[name].group("params"), "WIDTH") for name in names}
    idx_sizes = {_parameter(matches[name].group("params"), "IDX_SIZE") for name in names}
    sizes = {_parameter(matches[name].group("params"), "SIZE") for name in names}
    if widths != {8} or len(idx_sizes) != 1 or len(sizes) != 1:
        raise ValueError("token banks must share WIDTH=8, IDX_SIZE and SIZE")
    idx_size = next(iter(idx_sizes))
    size = next(iter(sizes))

    slots: dict[str, int] = {}
    for name, match in matches.items():
        body = match.group("body")
        slot = re.search(r"\.ext_req_valid\(ext_mem_req_valid\[(\d+)\]\)", body)
        if slot is None:
            raise ValueError(f"missing external slot for {name}")
        slots[name] = int(slot.group(1))
    if len(set(slots.values())) != len(names):
        raise ValueError("token banks must occupy distinct external slots")
    shared_slot = slots[names[0]]

    first = matches[names[0]]
    bank_vectors = {
        "addr0": ", ".join(f"{name}_addr0" for name in reversed(names)),
        "content_en": ", ".join(f"{name}_content_en" for name in reversed(names)),
        "done": ", ".join(f"{name}_done" for name in reversed(names)),
        "read_data": ", ".join(f"{name}_read_data" for name in reversed(names)),
        "write_data": ", ".join(f"{name}_write_data" for name in reversed(names)),
        "write_en": ", ".join(f"{name}_write_en" for name in reversed(names)),
    }
    bases = ", ".join(f"32'h{base_addresses[name]:08x}" for name in reversed(names))
    replacement = (
        f"seq_mem_d1_shared_banks #(\n"
        f"  .BANKS({len(names)}), .WIDTH(8), .SIZE({size}), .IDX_SIZE({idx_size}),\n"
        f"  .BANK_BASES({{{bases}}})\n"
        f") token_weight_codes_i8_banked (\n"
        f"  .clk(clk), .reset(reset),\n"
        f"  .addr0({{{bank_vectors['addr0']}}}),\n"
        f"  .content_en({{{bank_vectors['content_en']}}}),\n"
        f"  .done({{{bank_vectors['done']}}}),\n"
        f"  .read_data({{{bank_vectors['read_data']}}}),\n"
        f"  .write_data({{{bank_vectors['write_data']}}}),\n"
        f"  .write_en({{{bank_vectors['write_en']}}}),\n"
        f"  .ext_req_valid(ext_mem_req_valid[{shared_slot}]),\n"
        f"  .ext_req_ready(ext_mem_req_ready[{shared_slot}]),\n"
        f"  .ext_req_addr(ext_mem_req_addr[{shared_slot * 32 + 31}:{shared_slot * 32}]),\n"
        f"  .ext_rsp_valid(ext_mem_rsp_valid[{shared_slot}]),\n"
        f"  .ext_rsp_data(ext_mem_rsp_data[{shared_slot * 64 + 63}:{shared_slot * 64}])\n"
        f");"
    )
    disabled_slots = "\n".join(
        f"assign ext_mem_req_valid[{slots[name]}] = 1'b0;\n"
        f"assign ext_mem_req_addr[{slots[name] * 32 + 31}:{slots[name] * 32}] = 32'd0;"
        for name in names[1:]
    )
    rewritten = source
    for name in names:
        rewritten = rewritten.replace(matches[name].group(0), "", 1)
    # Re-find the first instance location after removals and insert the shared
    # controller before the next module declaration.
    module_pos = rewritten.find("endmodule", rewritten.find("module main"))
    if module_pos < 0:
        raise ValueError("main module end not found")
    rewritten = rewritten[:module_pos] + replacement + "\n" + disabled_slots + "\n" + rewritten[module_pos:]
    if "module seq_mem_d1_shared_banks" not in rewritten:
        rewritten = _BANKED_EXTERNAL_MODULE + "\n" + rewritten
    return ExternalizationResult(rewritten, names[0], 8, names, tuple(8 for _ in names))


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
    parser.add_argument(
        "--skip-static-counter-canonicalization",
        action="store_true",
        help="preserve a non-static Calyx lowering without requiring the static-counter form",
    )
    parser.add_argument(
        "--consolidate-token-weight-banks",
        action="store_true",
        help="replace the authenticated 197 token-weight controllers with one shared controller",
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
        result = externalize_memories(
            source,
            names,
            bases,
            canonicalize_counter=not args.skip_static_counter_canonicalization,
        )
        if args.consolidate_token_weight_banks:
            bank_names = sorted(
                (name for name in names if _BANK_NAME.fullmatch(name)),
                key=lambda name: int(_BANK_NAME.fullmatch(name).group("index")),
            )
            if len(bank_names) != 197:
                parser.error("--consolidate-token-weight-banks requires exactly 197 token banks")
            result = consolidate_token_weight_banks(result.source, bank_names, bases)
        result_source = result.source
        report = {
            "memory_count": len(names),
            "memory_names": names,
            "output_sha256": hashlib.sha256(result_source.encode("utf-8")).hexdigest(),
            "token_weight_bank_controller": (
                "shared" if args.consolidate_token_weight_banks else "per-bank"
            ),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result_source, encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
