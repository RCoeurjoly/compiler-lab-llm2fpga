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
            f"wire [{width-1}:0] a{number}_wdata; logic [{width-1}:0] a{number}_rdata; logic a{number}_done;",
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
            + "  timeout_counter = 0; while (!done && timeout_counter < 100000) begin @(posedge clk); timeout_counter = timeout_counter + 1; end if (!done) begin $display(\"TIMEOUT " + case["case_id"] + "\"); $finish; end repeat (2) @(posedge clk);\n"
            + f'  $display("RESULT {case["case_id"]} %0d %0d %0d %0d %0d %0d", '
            + ", ".join(f"$signed(mem26[{i}])" for i in range(6))
            + ");\n"
            + "end"
        )
    text = "`timescale 1ns/1ps\nmodule tb;\ninteger timeout_counter;\n" + "\n".join(declarations) + "\n"
    text += "logic clk=0, reset=0, go=0; wire done; always #5 clk=~clk;\n"
    text += "always_ff @(posedge clk) begin\n"
    for n in ports:
        text += f"  if (reset) begin a{n}_done <= 1'b0; a{n}_rdata <= '0; end\n"
        text += f"  else if (a{n}_en) begin a{n}_done <= 1'b1;"
        text += f" if (!a{n}_we) a{n}_rdata <= mem{n}[a{n}_addr];"
        text += f" else mem{n}[a{n}_addr] <= a{n}_wdata; end\n"
        text += f"  else a{n}_done <= 1'b0;\n"
    text += "end\n"
    connections[-1] = connections[-1].rstrip(",")
    text += "main_1 dut(.clk(clk), .reset(reset), .go(go), .done(done),\n" + "\n".join(connections) + ");\n"
    text += "initial begin\n" + "  " + "\n  ".join(initialization) + "\n  " + "\n  ".join(case_blocks) + "\n  $finish;\nend\nendmodule\n"
    path = root / "tb.sv"
    path.write_text(text, encoding="utf-8")
    return path


def _normalize_large_or_assignments(source: str) -> str:
    """Turn huge one-bit OR trees into equivalent procedural priority logic.

    CIRCT's Calyx Verilog backend emits the FSM enable as one enormous
    ``assign x = a | b | ...`` expression.  Splitting that expression is a
    simulation-only lexical normalization; each term still drives the same
    one-bit signal with the same OR semantics.
    """
    pattern = re.compile(r"assign\s+(\w+)\s*=\s*(\S[^;]*);", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        name, expression = match.group(1), match.group(2)
        if len(match.group(0)) < 20000:
            return match.group(0)
        if "?" in expression:
            # FSM state outputs are wide priority-ternary chains.  Convert
            # them to reverse-order procedural assignments, which preserves
            # the original priority while avoiding one enormous AST node.
            pairs: list[tuple[str, str]] = []
            rest = expression.strip()
            while " ? " in rest:
                condition, true_value, false_rest = re.split(
                    r"\s*\?\s*|\s*:\s*", rest, maxsplit=2
                )
                pairs.append((condition, true_value))
                rest = false_rest
            if not pairs:
                return match.group(0)
            body = ["always_comb begin", f"  {name} = {rest.strip()};"]
            body.extend(
                f"  if ({condition.strip()}) {name} = {true_value.strip()};"
                for condition, true_value in reversed(pairs)
            )
            body.append("end")
            return "\n".join(body)
        if " | " not in expression:
            return match.group(0)
        # The rewrite is valid only for scalar enables.  Wide data buses use
        # the same textual OR operator but cannot be assigned 1'b1.
        if re.search(r"\b(?:logic|wire)\s+" + re.escape(name) + r"\s*;", source) is None:
            return match.group(0)
        terms = expression.split(" | ")
        if not all(term.strip() for term in terms):
            return match.group(0)
        body = ["always_comb begin", f"  {name} = 1'b0;"]
        body.extend(f"  if ({term.strip()}) {name} = 1'b1;" for term in terms)
        body.append("end")
        return "\n".join(body)

    return pattern.sub(replace, source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--iverilog", default="iverilog")
    parser.add_argument("--vvp", default="vvp")
    parser.add_argument("--simulator", choices=("verilator", "iverilog"), default="verilator")
    parser.add_argument("--verilator-jobs", type=int, default=4)
    parser.add_argument("--verilator-output-split", type=int, default=1000)
    parser.add_argument("--verilator-output-split-cfuncs", type=int, default=500)
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
        lexical_sv = _normalize_large_or_assignments(lexical_sv)
        normalized_sv.write_text(
            lexical_sv.replace(";", ";\n").replace(" | ", " |\n"),
            encoding="utf-8",
        )
        tb = _fixture(sv, args.image.read_bytes(), json.loads(args.manifest.read_text()), json.loads(args.reference.read_text()), root)
        binary = root / "obj_dir" / "Vtb"
        if args.simulator == "verilator":
            subprocess.run([
                args.verilator, "--binary", "--timing", "--Wno-fatal", "-O0",
                "--output-split", str(args.verilator_output_split),
                "--output-split-cfuncs", str(args.verilator_output_split_cfuncs),
                "-CFLAGS", "-O0",
                "-j", str(args.verilator_jobs), "--top-module", "tb",
                str(normalized_sv), str(tb), "-Mdir", str(root / "obj_dir")
            ], check=True)
            output = subprocess.check_output([str(binary)], text=True)
        else:
            binary = root / "tb.vvp"
            subprocess.run([args.iverilog, "-g2012", "-s", "tb", "-o", str(binary), str(normalized_sv), str(tb)], check=True)
            output = subprocess.check_output([args.vvp, str(binary)], text=True)
        expected_rows = json.loads(args.reference.read_text())["results"]
        expected = {row["case_id"]: row["output_codes_i8"] for row in expected_rows}
        expected_token_ids = {row["case_id"]: row["token_id"] for row in expected_rows}
        observed = {}
        for line in output.splitlines():
            match = re.match(r"RESULT (\S+) ([-0-9 ]+)$", line)
            if match:
                observed[match.group(1)] = [int(x) for x in match.group(2).split()]
        observed_token_ids = {
            case_id: max(range(len(codes)), key=lambda index: codes[index])
            for case_id, codes in observed.items()
        }
        if observed != expected or observed_token_ids != expected_token_ids:
            raise SystemExit(json.dumps({
                "status": "fail",
                "expected": expected,
                "observed": observed,
                "expected_token_ids": expected_token_ids,
                "observed_token_ids": observed_token_ids,
            }, sort_keys=True))
        print(json.dumps({
            "status": "pass",
            "cases": len(expected),
            "logits": 6,
            "token_ids": observed_token_ids,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
