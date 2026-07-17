#!/usr/bin/env python3
"""Compare a bounded rational tanh candidate at the frozen RC boundary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from run_rc_softmax_candidates import _output_tensor, load_module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exported-program-dir", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--contexts", type=Path)
    source.add_argument("--context-count", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.contexts is not None:
        contexts = json.loads(args.contexts.read_text(encoding="utf-8"))
    else:
        contexts = []
        for index in range(args.context_count):
            digits = [0] * 8
            remaining = index
            for position in range(7, -1, -1):
                digits[position] = remaining % 6
                remaining //= 6
            contexts.append(digits)
    module = load_module(args.exported_program_dir)

    class Candidate(torch.fx.Interpreter):
        def run_node(self, node):
            if "aten.tanh" in str(getattr(node, "target", "")):
                value = self.env[node.args[0]]
                square = value * value
                return value * (27.0 + square) / (27.0 + 9.0 * square)
            return super().run_node(node)

    cases = []
    with torch.inference_mode():
        for index, context in enumerate(contexts):
            inputs = torch.tensor([context], dtype=torch.long)
            reference = _output_tensor(module(inputs)).detach().cpu()
            candidate = _output_tensor(Candidate(module).run(inputs)).detach().cpu()
            cases.append({
                "context_index": index,
                "tensor_equal": bool(torch.equal(reference, candidate)),
                "differing_elements": int(torch.ne(reference, candidate).sum()),
                "reference_last_row": reference[0, -1, :].tolist(),
                "candidate_last_row": candidate[0, -1, :].tolist(),
            })
    args.out.write_text(json.dumps({
        "candidate": "tanh-rational-27",
        "status": "pass" if all(case["tensor_equal"] for case in cases) else "fail",
        "cases": cases,
        "semantic_status": "analysis-only; not yet a lowering or equivalence claim",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
