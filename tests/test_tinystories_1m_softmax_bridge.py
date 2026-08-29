"""Tests for the fail-closed TinyStories-1M softmax compiler bridge."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/bridge_tinystories_1m_softmax.py"
spec = importlib.util.spec_from_file_location("softmax_bridge", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


GRAPH = """module {
  // authenticated attention score - row_max stabilization
  %delta = arith.subf %score, %row_max : f32
  %exp = math.exp %delta : f32
  memref.store %exp, %exp_mem[%i] : memref<32xf32>
  %sum = arith.addf %old_sum, %exp : f32
  %prob = arith.divf %exp, %sum : f32
  // causal prefix: time_index <= position
}
"""


class SoftmaxBridgeTest(unittest.TestCase):
    def test_exact_stabilized_attention_pattern_emits_authenticated_custom_op(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        descriptor = module.bridge_graph(GRAPH, evidence, source_name="fixture.mlir")
        self.assertEqual(descriptor["op"], "llm2fpga.attention_softmax_fixed")
        self.assertEqual(descriptor["attributes"]["score_fraction_bits"], 8)
        self.assertEqual(descriptor["attributes"]["exp_fraction_bits"], 20)
        self.assertEqual(descriptor["evidence"]["contract_sha256"], module.CONTRACT_SHA256)
        rendered = module.render_custom_op(descriptor)
        self.assertIn('"llm2fpga.attention_softmax_fixed"', rendered)
        self.assertIn("causal_mask = \"prefix_time_index_le_position\"", rendered)
        self.assertIn(module.CONTRACT_SHA256, rendered)

    def test_missing_stabilization_fails_closed(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "pattern_not_proven"):
            module.bridge_graph("%x = math.exp %x : f32", evidence, source_name="bad.mlir")

    def test_forged_contract_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract.json"
            value = json.loads((ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json").read_text())
            value["model"]["source_revision"] = "forged"
            contract.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(module.SoftmaxBridgeError, "contract_identity_mismatch"):
                module.load_evidence(contract, ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json")


if __name__ == "__main__":
    unittest.main()
