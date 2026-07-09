#!/usr/bin/env python3
"""Build the baseline SV-equivalence report for the integer TinyStories route."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CONTROL_OUTPUTS = {"done"}


def parse_main_ports(main_sv: Path) -> dict[str, list[str]]:
    text = main_sv.read_text(encoding="utf-8")
    match = re.search(r"\bmodule\s+main\s*\((.*?)\);\s", text, flags=re.S)
    if match is None:
        raise RuntimeError(f"unable to find module main header in {main_sv}")

    header = re.sub(r"//.*", "", match.group(1))
    tokens = [token.strip() for token in header.replace("\n", " ").split(",") if token.strip()]
    inputs: list[str] = []
    outputs: list[str] = []
    direction: str | None = None

    for token in tokens:
        token = re.sub(r"\s+", " ", token)
        direction_match = re.match(r"^(input|output)\b(.*)$", token)
        rest = token
        if direction_match is not None:
            direction = direction_match.group(1)
            rest = direction_match.group(2).strip()
        if direction is None:
            raise RuntimeError(f"unable to infer direction for port token {token!r}")

        name_match = re.search(r"([A-Za-z_][A-Za-z0-9_$]*)\s*$", rest)
        if name_match is None:
            raise RuntimeError(f"unable to parse port name from token {token!r}")
        name = name_match.group(1)

        if direction == "input":
            inputs.append(name)
        else:
            outputs.append(name)

    return {"inputs": inputs, "outputs": outputs}


def build_report(sv_dir: Path, expected_json: Path) -> dict[str, object]:
    expected = json.loads(expected_json.read_text(encoding="utf-8"))
    ports = parse_main_ports(sv_dir / "main.sv")
    observable_outputs = [
        name for name in ports["outputs"] if name not in CONTROL_OUTPUTS
    ]

    if observable_outputs:
        status = "needs-sv-simulation"
        reason = (
            "SV exposes functional output ports, but this baseline harness does "
            "not yet run a simulator."
        )
    else:
        status = "blocked-unobservable-sv-output"
        reason = (
            "SV top module exposes no functional output ports; only control "
            "signals are observable, so PyTorch-vs-SV functional equivalence "
            "cannot be checked yet."
        )

    return {
        "schemaVersion": 1,
        "report_kind": "sv-equivalence-baseline",
        "model": "tinystories-representative-core-w4a8-integer",
        "frontend": "linalg",
        "backend": "calyx-native-sv",
        "status": status,
        "reason": reason,
        "reference": {
            "input_token_ids": expected["input_token_ids"],
            "pytorch_output_i8": expected["pytorch_output_i8"],
            "pytorch_output_shape": expected["pytorch_output_shape"],
        },
        "sv": {
            "top_module": "main",
            "main_sv": str(sv_dir / "main.sv"),
            "ports": ports,
            "observable_functional_outputs": observable_outputs,
        },
        "comparison": {
            "attempted": False,
            "reason": reason,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv-dir", type=Path, required=True)
    parser.add_argument("--expected-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.sv_dir, args.expected_json)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
