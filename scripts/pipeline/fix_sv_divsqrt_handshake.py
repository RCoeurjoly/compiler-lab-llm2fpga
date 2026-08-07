#!/usr/bin/env python3
"""Repair the generated Calyx ``std_divSqrtFN`` request/completion protocol."""

import hashlib
import json
import re
import sys
from pathlib import Path


MODULE = re.compile(
    r"(?ms)\bmodule\s+std_divSqrtFN\b.*?\bendmodule\b"
)
LEGACY_TAIL = re.compile(
    r"(?ms)\s*logic\s+done_buf\s*\[31:0\]\s*;.*?(?=\s*endmodule\b)"
)

FIXED_TAIL = r"""

    // One HardFloat transaction is allowed for each Calyx go assertion.
    // Completion follows HardFloat outValid, not a guessed fixed latency.
    localparam logic [1:0] LLM2FPGA_IDLE = 2'd0;
    localparam logic [1:0] LLM2FPGA_BUSY = 2'd1;
    localparam logic [1:0] LLM2FPGA_COMPLETE = 2'd2;
    logic [1:0] llm2fpga_state;
    wire llm2fpga_request =
        llm2fpga_state == LLM2FPGA_IDLE && go && inReady;

    assign done = llm2fpga_state == LLM2FPGA_COMPLETE;

    always_ff @(posedge clk) begin
        if (reset) begin
            llm2fpga_state <= LLM2FPGA_IDLE;
            out <= 0;
        end else begin
            case (llm2fpga_state)
                LLM2FPGA_IDLE: begin
                    if (llm2fpga_request)
                        llm2fpga_state <= LLM2FPGA_BUSY;
                end
                LLM2FPGA_BUSY: begin
                    if (outValid) begin
                        out <= res_std;
                        llm2fpga_state <= LLM2FPGA_COMPLETE;
                    end
                end
                LLM2FPGA_COMPLETE: begin
                    if (!go)
                        llm2fpga_state <= LLM2FPGA_IDLE;
                end
                default: llm2fpga_state <= LLM2FPGA_IDLE;
            endcase
        end
    end

"""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repair(source: str) -> tuple[str, int]:
    modules = list(MODULE.finditer(source))
    if len(modules) != 1:
        raise ValueError(
            f"expected exactly one std_divSqrtFN module, found {len(modules)}"
        )
    match = modules[0]
    module = match.group(0)
    already_fixed = (
        "LLM2FPGA_COMPLETE" in module
        and ".inValid(llm2fpga_request)" in module
        and "done_buf" not in module
    )
    if already_fixed:
        return source, 0

    module, request_count = re.subn(
        r"\.inValid\(\s*go\s*\)",
        ".inValid(llm2fpga_request)",
        module,
    )
    if request_count != 1:
        raise ValueError(
            f"expected one legacy .inValid(go) connection, found {request_count}"
        )
    module, tail_count = LEGACY_TAIL.subn(FIXED_TAIL, module)
    if tail_count != 1:
        raise ValueError(
            f"expected one legacy fixed-delay/output tail, found {tail_count}"
        )
    return source[: match.start()] + module + source[match.end() :], 1


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"usage: {sys.argv[0]} <input.sv> <output.sv> <receipt.json>",
            file=sys.stderr,
        )
        return 2
    try:
        source = Path(sys.argv[1]).read_text(encoding="utf-8")
        output, repair_count = repair(source)
        receipt = {
            "schema": "llm2fpga.sv-divsqrt-handshake-repair.v1",
            "input_sv_sha256": sha256(source),
            "output_sv_sha256": sha256(output),
            "repair_count": repair_count,
        }
        Path(sys.argv[2]).write_text(output, encoding="utf-8")
        Path(sys.argv[3]).write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"repaired {repair_count} std_divSqrtFN wrapper(s)")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
