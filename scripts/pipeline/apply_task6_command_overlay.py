#!/usr/bin/env python3
"""Authenticated one-stage normal-command overlay; pinned upstream stays intact."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PINS = Path(__file__).with_name("task6_command_overlay_pins.json")
STAGE = ROOT / "rtl/diagnostics/task6_normal_command_stage.sv"
SHELL_PATH = "llm2fpga/fpga/rtl/task6_ypcb_uberddr3_bist_rowstream_loader_top.sv"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("overlay anchor is not unique")
    return text.replace(before, after)


def _transform(data):
    text = data.decode()
    text = replace_once(text,
        "TINYSTORIES_LOADER_ONLY ? tinystories_staged_command_payload : jtag_command_payload;",
        "TINYSTORIES_LOADER_ONLY ? tinystories_staged_command_payload : normal_command_payload;")
    anchor = "  wire [31:0] jtag_command_magic = loader_command_payload[0 +: 32];"
    insertion = """  // Task 3B authenticated overlay: source selection remains upstream.
  wire [207:0] normal_command_payload;
  wire normal_command_event, normal_command_source_pcie;
  wire normal_command_accept, normal_command_restart;
  wire [19:1] normal_command_decode;
  task6_normal_command_stage #(.WB_SEL_BITS(WB_SEL_BITS)) normal_command_stage (
    .clk(controller_clk), .rst_n(rst_n), .enabled(!TINYSTORIES_LOADER_ONLY),
    .payload(jtag_command_payload), .event_i(jtag_command_event),
    .accept_phase(jtag_command_accept_phase_q), .idle(read_probe_done_q),
    .ready(ddr_ready_q),
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
    .busy(top1_reader_busy), .source_pcie(pcie_command_event_i),
`else
    .busy(1'b0), .source_pcie(1'b0),
`endif
    .payload_q(normal_command_payload), .event_q(normal_command_event),
    .source_pcie_q(normal_command_source_pcie),
    .accept_q(normal_command_accept), .restart_q(normal_command_restart),
    .decode_q(normal_command_decode)
  );

"""
    text = replace_once(text, anchor, insertion + anchor)
    text = replace_once(text, """        (!TINYSTORIES_LOADER_ONLY && jtag_command_event &&
         !jtag_command_accept_phase_q && read_probe_done_q &&
         jtag_command_magic_ok && ddr_ready_q
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
         && !top1_reader_busy
`endif
        )""", "        normal_command_accept")
    text = replace_once(text, """        !TINYSTORIES_LOADER_ONLY && jtag_command_event &&
        !jtag_command_accept_phase_q && read_probe_done_q""", "        normal_command_restart")
    # Only the normal-mode command ladder is decoded before the boundary;
    # later state-machine opcode tests and packet-only mode are untouched.
    start = text.index("        end else if (jtag_command_opcode == LOADER_OP_READ_BANDWIDTH_COUNTER")
    end = text.index("      end else if (\n        normal_command_restart", start)
    ladder = text[start:end]
    opcodes = dict((name, int(value, 16)) for name, value in re.findall(
        r"localparam logic \[7:0\] (LOADER_OP_\w+) = 8'h([0-9a-f]+);", text))
    count = 0
    def decode(match):
        nonlocal count
        count += 1
        return "else if (normal_command_decode[" + str(opcodes[match[1]]) + "]) begin"
    ladder = re.sub(r"else if \(jtag_command_opcode == (LOADER_OP_\w+)[^\n]*\) begin", decode, ladder)
    if count != 19:
        raise ValueError("normal command ladder changed")
    return (text[:start] + ladder + text[end:]).encode()


def verify_output(data):
    if digest(data) != json.loads(PINS.read_text())["output_sha256"]:
        raise ValueError("overlay output SHA-256 mismatch")


def transform(data):
    pins = json.loads(PINS.read_text())
    if digest(data) != pins["input_sha256"]:
        raise ValueError("overlay input SHA-256 mismatch")
    if digest(STAGE.read_bytes()) != pins["stage_sha256"]:
        raise ValueError("overlay stage SHA-256 mismatch")
    output = _transform(data)
    verify_output(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, required=True)
    args = parser.parse_args()
    shell = args.closure / SHELL_PATH
    shell.write_bytes(transform(shell.read_bytes()))
    (args.closure / "command-overlay.json").write_bytes(PINS.read_bytes())


if __name__ == "__main__":
    main()
