#!/usr/bin/env python3
"""Run the V=6 RC Calyx-SV memory-service fixture against its PT2E oracle.

The Calyx backend exposes the caller-owned flat-SCF buffers as ``arg_mem_N``
ports on ``main_1``.  This fixture supplies those memories, initializes the
frozen integer state from the checked image, drives the token buffer, and
compares the six final int8 codes and argmax token for every frozen corpus
case.  It deliberately fails if the expected functional ports are absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def _ports(source: str) -> dict[int, tuple[int, int]]:
    result: dict[int, tuple[int, int]] = {}
    pattern = re.compile(
        r"(?:input|output) logic(?: \[(\d+):(\d+)\])? arg_mem_(\d+)_(addr0|read_data)"
    )
    widths: dict[int, dict[str, int]] = {}
    for hi, lo, number, kind in pattern.findall(source):
        width = int(hi) - int(lo) + 1 if hi else 1
        widths.setdefault(int(number), {})[kind] = width
    for number, values in widths.items():
        if "addr0" in values and "read_data" in values:
            result[number] = (values["read_data"], 1 << values["addr0"])
    return result


def _hex_words(payload: bytes, width: int, depth: int) -> list[str]:
    byte_width = (width + 7) // 8
    return [
        int.from_bytes(
            payload[i * byte_width : (i + 1) * byte_width].ljust(byte_width, b"\0"),
            "little",
        ).to_bytes(byte_width, "big").hex()
        for i in range(depth)
    ]


def _fixture(sv: str, image: bytes, manifest: dict, reference: dict, root: Path) -> Path:
    ports = _ports(sv)
    if 25 not in ports or 26 not in ports:
        raise RuntimeError("SV does not expose token arg_mem_25 and output arg_mem_26")
    for number in range(27):
        if number not in ports:
            raise RuntimeError(f"SV is missing required arg_mem_{number}")
    segment_by_name = {s["name"]: s for s in manifest["segments"]}
    for number in range(21):
        name = f"state/_frozen_param{number}"
        segment = segment_by_name[name]
        raw = image[segment["offset"] : segment["offset"] + segment["byte_length"]]
        width, depth = ports[number]
        (root / f"mem{number}.hex").write_text(
            "\n".join(_hex_words(raw, width, depth)) + "\n", encoding="ascii"
        )

    declarations: list[str] = []
    connections: list[str] = []
    initialization: list[str] = []
    for number, (width, depth) in sorted(ports.items()):
        addr_width = max(1, (depth - 1).bit_length())
        declarations += [
            f"logic [{width-1}:0] mem{number} [0:{depth-1}];",
            f"wire [{addr_width-1}:0] a{number}_addr; wire a{number}_en, a{number}_we;",
            f"wire [{width-1}:0] a{number}_wdata; wire [{width-1}:0] a{number}_rdata; wire a{number}_done;",
        ]
        connections += [
            f".arg_mem_{number}_addr0(a{number}_addr), .arg_mem_{number}_content_en(a{number}_en),",
            f".arg_mem_{number}_write_en(a{number}_we), .arg_mem_{number}_write_data(a{number}_wdata),",
            f".arg_mem_{number}_read_data(a{number}_rdata), .arg_mem_{number}_done(a{number}_done),",
        ]
        initialization.append(f"for (int i=0; i<{depth}; i++) mem{number}[i] = '0;")
    for number in range(21):
        initialization.append(f'$readmemh("{root / f"mem{number}.hex"}", mem{number});')

    cases = reference["results"]
    case_blocks = []
    for index, case in enumerate(cases):
        tokens = case["token_ids"]
        expected = case["output_codes_i8"]
        case_blocks.append(
            "begin\n"
            f"  for (int i=0; i<8; i++) mem25[i] = 0;\n"
            + "  " + " ".join(f"mem25[{i}] = 64'sd{v};" for i, v in enumerate(tokens)) + "\n"
            + "  reset = 1; repeat (3) @(posedge clk); reset = 0; go = 1; @(posedge clk); go = 0;\n"
            + "  wait(done); repeat (2) @(posedge clk);\n"
            + f'  $display("RESULT {case["case_id"]} %0d %0d %0d %0d %0d %0d", '
            + ", ".join(f"$signed(mem26[{i}])" for i in range(6))
            + ");\n"
            + "end"
        )
    text = "`timescale 1ns/1ps\nmodule tb;\n" + "\n".join(declarations) + "\n"
    text += "logic clk=0, reset=0, go=0; wire done; always #5 clk=~clk;\n"
    text += "always_comb begin\n" + "\n".join(
        f"  a{n}_rdata = mem{n}[a{n}_addr]; a{n}_done = a{n}_en;" for n in ports
    ) + "\nend\nalways_ff @(posedge clk) begin\n" + "\n".join(
        f"  if (a{n}_we && a{n}_en) mem{n}[a{n}_addr] <= a{n}_wdata;" for n in ports
    ) + "\nend\n"
    text += "main_1 dut(.clk(clk), .reset(reset), .go(go), .done(done),\n" + "\n".join(connections) + ");\n"
    text += "initial begin\n" + "  " + "\n  ".join(initialization) + "\n  " + "\n  ".join(case_blocks) + "\n  $finish;\nend\nendmodule\n"
    path = root / "tb.sv"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rc-sv-equiv-") as directory:
        root = Path(directory)
        sv = args.sv.read_text(encoding="utf-8")
        # CIRCT's native Calyx printer can emit a very large single line of
        # Verilog.  This is lexically equivalent and keeps Verilator below its
        # per-line token limit; it does not alter the generated RTL.
        normalized_sv = root / "main.sv"
        # Comments are not part of the RTL and can contain semicolons; remove
        # them before introducing statement boundaries.
        lexical_sv = re.sub(r"/\*.*?\*/", "", sv, flags=re.DOTALL)
        lexical_sv = re.sub(r"//[^\n]*", "", lexical_sv)
        normalized_sv.write_text(
            lexical_sv.replace(";", ";\n").replace(" | ", " |\n"),
            encoding="utf-8",
        )
        tb = _fixture(sv, args.image.read_bytes(), json.loads(args.manifest.read_text()), json.loads(args.reference.read_text()), root)
        binary = root / "obj_dir" / "Vtb"
        subprocess.run([args.verilator, "--binary", "--timing", "--Wno-fatal", "--top-module", "tb", str(normalized_sv), str(tb), "-Mdir", str(root / "obj_dir")], check=True)
        output = subprocess.check_output([str(binary)], text=True)
        expected = {row["case_id"]: row["output_codes_i8"] for row in json.loads(args.reference.read_text())["results"]}
        observed = {}
        for line in output.splitlines():
            match = re.match(r"RESULT (\S+) ([-0-9 ]+)$", line)
            if match:
                observed[match.group(1)] = [int(x) for x in match.group(2).split()]
        if observed != expected:
            raise SystemExit(json.dumps({"status": "fail", "expected": expected, "observed": observed}, sort_keys=True))
        print(json.dumps({"status": "pass", "cases": len(expected), "logits": 6, "token_id": "argmax(output_codes_i8)"}, sort_keys=True))


if __name__ == "__main__":
    main()
