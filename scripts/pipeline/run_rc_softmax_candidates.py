#!/usr/bin/env python3
"""Evaluate Softmax candidates on internal rows observed from the frozen RC."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TinyStories.rc_working_contract import (  # noqa: E402
    RC_WORKING_SOURCE_MODEL_KEY,
)


def _candidate_module() -> Any:
    path = ROOT / "scripts/pipeline/evaluate_softmax_candidates.py"
    spec = importlib.util.spec_from_file_location("softmax_candidates", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load candidate evaluator")
    module = importlib.util.module_from_spec(spec)
    sys.modules["softmax_candidates"] = module
    spec.loader.exec_module(module)
    return module


def load_module(exported_program_dir: Path) -> Any:
    import torch
    import torch.ao.quantization.quantize_pt2e  # noqa: F401
    try:
        import transformers.modeling_outputs  # noqa: F401
    except ImportError:
        pass
    return torch.export.load(exported_program_dir / "exported.pt2").module()


def observe_rows(module: Any, contexts: list[list[int]]) -> dict[str, list[list[float]]]:
    import torch

    observed: dict[str, list[list[float]]] = {}

    class Observer(torch.fx.Interpreter):
        def run_node(self, node: Any) -> Any:
            if "aten.softmax.int" in str(getattr(node, "target", "")):
                value = self.env[node.args[0]]
                dim = int(node.args[1]) if len(node.args) > 1 else -1
                moved = value.detach().float().movedim(dim, -1).reshape(-1, value.shape[dim])
                observed.setdefault(node.name, []).extend(
                    [[float(item) for item in row] for row in moved.cpu().tolist()]
                )
            return super().run_node(node)

    observer = Observer(module)
    with torch.inference_mode():
        for context in contexts:
            observer.run(torch.tensor([context], dtype=torch.long))
    return observed


def _tensor_exp(value: Any, name: str) -> Any:
    import torch
    maximum = torch.amax(value, dim=-1, keepdim=True)
    stabilized = value - maximum
    if name == "streaming-exact":
        exponent = torch.exp(stabilized)
    elif name == "lut-256":
        lo = -8.0
        entries = 256
        clipped = torch.clamp(stabilized, lo, 0.0)
        position = (clipped - lo) * (entries - 1) / -lo
        left = torch.floor(position).to(torch.int64)
        fraction = position - left.to(position.dtype)
        step = -lo / (entries - 1)
        exponent = (1.0 - fraction) * torch.exp(lo + left.to(position.dtype) * step)
        exponent = exponent + fraction * torch.exp(lo + (left + 1).to(position.dtype) * step)
    elif name in {"polynomial-5", "cordic-12"}:
        n = torch.floor(stabilized / math.log(2.0) + 0.5)
        remainder = stabilized - n * math.log(2.0)
        order = 5 if name == "polynomial-5" else 12
        value_poly = torch.ones_like(remainder)
        for degree in range(order, 0, -1):
            value_poly = 1.0 + remainder * value_poly / degree
        exponent = torch.ldexp(value_poly, n.to(torch.int32))
    else:
        raise ValueError(f"unknown candidate {name}")
    return exponent / torch.sum(exponent, dim=-1, keepdim=True)


def _output_tensor(output: Any) -> Any:
    logits = getattr(output, "logits", None)
    if logits is not None:
        return logits
    return output


def compare_full_model(module: Any, contexts: list[list[int]], candidate_name: str) -> dict[str, object]:
    import torch

    class CandidateInterpreter(torch.fx.Interpreter):
        def run_node(self, node: Any) -> Any:
            if "aten.softmax.int" in str(getattr(node, "target", "")):
                value = self.env[node.args[0]]
                return _tensor_exp(value, candidate_name)
            return super().run_node(node)

    differences: list[dict[str, object]] = []
    with torch.inference_mode():
        for index, context in enumerate(contexts):
            input_tensor = torch.tensor([context], dtype=torch.long)
            reference = _output_tensor(module(input_tensor)).detach().cpu()
            candidate = _output_tensor(CandidateInterpreter(module).run(input_tensor)).detach().cpu()
            equal = bool(torch.equal(reference, candidate))
            ref_row = reference[0, -1, :].reshape(-1).tolist()
            cand_row = candidate[0, -1, :].reshape(-1).tolist()
            differences.append({
                "context_index": index,
                "tensor_equal": equal,
                "reference_last_row": [int(value) for value in ref_row],
                "candidate_last_row": [int(value) for value in cand_row],
                "differing_elements": int(torch.ne(reference, candidate).sum().item()),
            })
    return {"status": "pass" if differences and all(row["tensor_equal"] for row in differences) else "fail", "cases": differences}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exported-program-dir", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True, help="JSON array of token contexts")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    candidate = _candidate_module()
    contexts = json.loads(args.contexts.read_text(encoding="utf-8"))
    if not isinstance(contexts, list) or not all(isinstance(row, list) for row in contexts):
        raise ValueError("contexts must be a JSON array of arrays")
    rows = observe_rows(load_module(args.exported_program_dir), contexts)
    sites = {name: candidate.evaluate(site_rows) for name, site_rows in rows.items()}
    full_model = {item.name: compare_full_model(load_module(args.exported_program_dir), contexts, item.name) for item in candidate.candidates()}
    result = {
        "schema_version": 1,
        "kind": "frozen-rc-softmax-candidate-evaluation",
        "source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
        "context_count": len(contexts),
        "contexts": contexts,
        "sites": sites,
        "full_model": full_model,
        "semantic_status": "analysis-only; no graph rewrite or SV equivalence claim",
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
