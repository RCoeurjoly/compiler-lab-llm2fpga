#!/usr/bin/env python3
"""Authenticated same-edge static M2 word banking; pinned source stays intact."""
import argparse
import hashlib
import json
from pathlib import Path

PINS = Path(__file__).with_name("task6_m2_banking_overlay_pins.json")
INGRESS_PATH = "llm2fpga/fpga/rtl/task6_pcie_axil_rowstream_loader_ingress.v"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _transform(data):
    text = data.decode()
    for bank, base, indent in (("input", 0x150, 36), ("residual", 0x160, 32)):
        signal = f"m2_full_block_{bank}_vector_o"
        whitespace = " " * indent
        before = (
            f"{whitespace}{signal}[(write_word_index - 10'h{base:03x}) * 32 +: 32] <=\n"
            f"{whitespace}    apply_wstrb(\n"
            f"{whitespace}        {signal}[(write_word_index - 10'h{base:03x}) * 32 +: 32],\n"
            f"{whitespace}        wdata_q,\n"
            f"{whitespace}        wstrb_q\n"
            f"{whitespace}    );")
        lines = [whitespace + "case (write_word_index)"]
        for word in range(16):
            target = f"{signal}[{32 * word} +: 32]"
            lines.append(f"{whitespace}    10'h{base + word:03x}: {target} <= apply_wstrb({target}, wdata_q, wstrb_q);")
        lines.append(whitespace + "endcase")
        if text.count(before) != 1:
            raise ValueError("M2 overlay anchor is not unique")
        text = text.replace(before, "\n".join(lines))
    return text.encode()


def verify_output(data):
    if digest(data) != json.loads(PINS.read_text())["output_sha256"]:
        raise ValueError("M2 overlay output SHA-256 mismatch")


def transform(data):
    if digest(data) != json.loads(PINS.read_text())["input_sha256"]:
        raise ValueError("M2 overlay input SHA-256 mismatch")
    output = _transform(data)
    verify_output(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, required=True)
    args = parser.parse_args()
    ingress = args.closure / INGRESS_PATH
    ingress.write_bytes(transform(ingress.read_bytes()))
    (args.closure / "m2-banking-overlay.json").write_bytes(PINS.read_bytes())


if __name__ == "__main__":
    main()
