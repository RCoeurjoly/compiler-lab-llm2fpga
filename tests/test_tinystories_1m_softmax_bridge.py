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
  func.func @main(%score: f32, %row_max: f32, %old_sum: f32, %time_index: i32, %position: i32, %delta_mem: memref<32xf32>, %exp_mem: memref<32xf32>, %i: index) {
  %delta = arith.subf %score, %row_max : f32
  memref.store %delta, %delta_mem[%i] : memref<32xf32>
  %delta_loaded = memref.load %delta_mem[%i] : memref<32xf32>
  %exp = math.exp %delta_loaded : f32
  memref.store %exp, %exp_mem[%i] : memref<32xf32>
  %exp_loaded = memref.load %exp_mem[%i] : memref<32xf32>
  %sum = arith.addf %old_sum, %exp_loaded : f32
  %prob = arith.divf %exp_loaded, %sum : f32
  %causal = arith.cmpi sle, %time_index, %position : i32
  }
}
"""


def repeated_graph(site_count: int = 8) -> str:
    """Build a package-shaped graph with one independently linked head/site."""
    body = []
    for head in range(site_count):
        body.extend(
            [
                f"  %delta{head} = arith.subf %score{head}, %row_max{head} : f32",
                f"  memref.store %delta{head}, %delta_mem{head}[%i{head}] : memref<32xf32>",
                f"  %delta_loaded{head} = memref.load %delta_mem{head}[%i{head}] : memref<32xf32>",
                f"  %exp{head} = math.exp %delta_loaded{head} : f32",
                f"  memref.store %exp{head}, %exp_mem{head}[%i{head}] : memref<32xf32>",
                f"  %exp_loaded{head} = memref.load %exp_mem{head}[%i{head}] : memref<32xf32>",
                f"  %sum{head} = arith.addf %old_sum{head}, %exp_loaded{head} : f32",
                f"  %prob{head} = arith.divf %exp_loaded{head}, %sum{head} : f32",
                f"  %causal{head} = arith.cmpi sle, %time_index{head}, %position{head} : i32",
            ]
        )
    return "module {\n  func.func @main() {\n" + "\n".join(body) + "\n  }\n}\n"


class SoftmaxBridgeTest(unittest.TestCase):
    def test_exact_stabilized_attention_pattern_emits_authenticated_custom_op(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        descriptor = module.bridge_graph(GRAPH, evidence, source_name="fixture.mlir", expected_exp_sites=1)
        self.assertEqual(descriptor["op"], "llm2fpga.attention_softmax_fixed")
        self.assertEqual(descriptor["attributes"]["score_fraction_bits"], 8)
        self.assertEqual(descriptor["attributes"]["exp_fraction_bits"], 20)
        self.assertEqual(descriptor["evidence"]["contract_sha256"], module.CONTRACT_SHA256)
        rendered = module.render_custom_op(descriptor)
        self.assertIn('"llm2fpga.attention_softmax_fixed"', rendered)
        self.assertIn("causal_mask = \"prefix_time_index_le_position\"", rendered)
        self.assertIn(module.CONTRACT_SHA256, rendered)

    def test_eight_attention_sites_each_have_an_independent_chain(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        descriptor = module.bridge_graph(repeated_graph(), evidence, source_name="eight-heads.mlir")
        self.assertEqual(descriptor["source"]["exp_site_count"], 8)
        self.assertEqual(len(descriptor["source"]["sites"]), 8)
        self.assertEqual(
            [site["exp_site_line"] for site in descriptor["source"]["sites"]],
            sorted(site["exp_site_line"] for site in descriptor["source"]["sites"]),
        )

    def test_missing_head_site_fails_closed(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "expected 8 stabilized exp sites"):
            module.bridge_graph(repeated_graph(7), evidence, source_name="seven-heads.mlir")

    def test_cross_head_stitching_fails_closed(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        graph = repeated_graph()
        # Remove head 1's delta chain.  Its exp must not borrow head 0's
        # producer or head 2's reduction across neighbouring sites.
        graph = graph.replace("  %delta1 = arith.subf %score1, %row_max1 : f32\n", "")
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "dataflow_not_proven"):
            module.bridge_graph(graph, evidence, source_name="mixed-heads.mlir")

    def test_single_site_requires_explicit_expectation(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "expected 8 stabilized exp sites"):
            module.bridge_graph(GRAPH, evidence, source_name="implicit-single.mlir")

    def test_missing_stabilization_fails_closed(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "pattern_not_proven"):
            module.bridge_graph("%x = math.exp %x : f32", evidence, source_name="bad.mlir")

    def test_comments_and_unlinked_operations_fail_closed(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        comments = "// %d = arith.subf %score, %row_max\n// %e = math.exp %d\n"
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "pattern_not_proven"):
            module.bridge_graph(comments, evidence, source_name="comments.mlir")
        unlinked = GRAPH.replace("%delta_loaded = memref.load %delta_mem[%i] : memref<32xf32>", "%delta_loaded = memref.load %other_mem[%i] : memref<32xf32>")
        with self.assertRaisesRegex(module.SoftmaxBridgeError, r"(?:pattern|dataflow)_not_proven"):
            module.bridge_graph(unlinked, evidence, source_name="unlinked.mlir")

    def test_plain_or_mutated_evidence_is_not_accepted(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "evidence_capability_required"):
            module.bridge_graph(GRAPH, dict(evidence), source_name="forged.mlir")
        evidence._payload["contract_sha256"] = "forged"
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "evidence_capability_invalidated"):
            module.bridge_graph(GRAPH, evidence, source_name="mutated.mlir")

    def test_inverse_causal_direction_is_rejected(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        inverse = GRAPH.replace("%time_index, %position", "%position, %time_index")
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "pattern_not_proven"):
            module.bridge_graph(inverse, evidence, source_name="inverse.mlir")

    def test_capability_constructor_is_not_public(self):
        with self.assertRaises(TypeError):
            module._EvidenceCapability({})

    def test_forged_token_and_payload_are_rejected(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        forged = module._EvidenceCapability(module._EVIDENCE_TOKEN, dict(evidence))
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "evidence_capability_unissued"):
            module.bridge_graph(GRAPH, forged, source_name="forged-token.mlir")

    def test_use_before_definition_is_rejected(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        before = GRAPH.replace(
            "  %exp = math.exp %delta_loaded : f32\n",
            "  %exp = math.exp %delta_loaded : f32\n  %delta_loaded = memref.load %delta_mem[%i] : memref<32xf32>\n",
        ).replace("  %delta_loaded = memref.load %delta_mem[%i] : memref<32xf32>\n  %exp = math.exp", "  %exp = math.exp", 1)
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "dataflow_not_proven"):
            module.bridge_graph(before, evidence, source_name="use-before-def.mlir", expected_exp_sites=1)

    def test_invalid_wrapper_and_cross_region_chain_are_rejected(self):
        evidence = module.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        with self.assertRaisesRegex(module.SoftmaxBridgeError, "pattern_not_proven"):
            module.bridge_graph(GRAPH.replace("func.func @main", "not_a_func @main"), evidence, source_name="invalid.mlir")
        first, second = GRAPH.split("  %exp = math.exp", 1)
        second_body = second.rsplit("\n  }\n}\n", 1)[0]
        cross = first + "  }\n  func.func @other(%delta_loaded: f32) {\n  %exp = math.exp" + second_body + "\n  }\n}\n"
        with self.assertRaisesRegex(module.SoftmaxBridgeError, r"(?:pattern|dataflow)_not_proven"):
            module.bridge_graph(cross, evidence, source_name="cross-region.mlir")

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
