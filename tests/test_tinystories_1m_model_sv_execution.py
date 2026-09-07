"""Exact generated hardware execution and fail-closed evidence checks."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/pipeline/run_fixed_point_model_sv.py"


def load_runner():
    if not RUNNER.is_file():
        raise AssertionError("missing full-model generated-SV execution runner")
    spec = importlib.util.spec_from_file_location("model_sv_execution_tests", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelExecutionTest(unittest.TestCase):
    def test_simulator_visibility_and_preloads_are_narrowly_scoped(self):
        runner = load_runner()
        artifact = runner.lowerer.generate_model_kernel()
        futil_before = artifact.futil
        harness = runner.generate_harness(artifact)
        visibility = runner.generate_visibility_config(artifact)
        preloads = re.findall(r'preload\(root->main__DOT__(\w+)__DOT__mem,', harness)
        self.assertEqual(sorted(preloads), sorted(artifact.provenance["source_memories"]))
        self.assertNotIn("context_tokens", preloads)
        self.assertNotIn("selected_tokens", preloads)
        expected_wires = {
            "model_context_length_out", "model_layer_out",
            *[f"{memory}_{port}" for memory in (
                "model_block_outputs", "model_embedding", "model_final_ln", "model_logits", "selected_tokens"
            ) for port in ("addr0", "content_en", "write_en")],
        }
        actual_wires = set(re.findall(r'public_flat_rd -module "main" -var "(\w+)"', visibility))
        self.assertEqual(actual_wires, expected_wires)
        self.assertEqual(visibility.count("public_flat_rw"), 1)
        self.assertIn('public_flat_rw -module "seq_mem_d1" -var "mem" @(posedge clk)', visibility)
        self.assertNotIn('public_flat_rw -module "main"', visibility)
        self.assertEqual(artifact.futil, futil_before)

    def test_compiled_banked_gemvs_keep_output_and_reduction_address_dependencies(self):
        # A constant-address weight/scale read changes every GEMV column into
        # the same dot product. Inspect the actual compiled SV drivers, not
        # merely the pre-lowering text where the dead wires still existed.
        runner = load_runner()
        artifact = runner.lowerer.generate_model_kernel()
        with tempfile.TemporaryDirectory(prefix="banked-gemv-cone-") as tmp:
            runner.lowerer.compile_model_kernel(artifact, Path(tmp), timeout=1800)
            sv = (Path(tmp) / "model.sv").read_text()
        assignments = dict(re.findall(r"assign\s+(\w+)\s*=\s*([^;]+);", sv))
        for prefix in ("q", "k", "v", "out", "c_fc", "c_proj"):
            for destination, source in (
                ("weight_output_pad_in", "output_counter_out"),
                ("weight_k_pad_in", "k_counter_out"),
                ("scale_address_in", "k_counter_out"),
            ):
                with self.subTest(projection=prefix, destination=destination):
                    name = f"{prefix}_gemv_{destination}"
                    self.assertTrue(name in assignments, "Calyx dropped a live banked-memory address driver: " + name)
                    self.assertRegex(assignments[name], rf"\b{prefix}_gemv_{source}\b")

    def test_diagnostic_compares_signed_words_and_reports_first_bad_channel(self):
        runner = load_runner()
        self.assertTrue(hasattr(runner, "compare_diagnostic_words"), "missing exact-word diagnostic comparator")
        with tempfile.TemporaryDirectory() as tmp:
            import struct
            path = Path(tmp) / "words.bin"
            path.write_bytes(struct.pack("<qqq", -7, 12, -2))
            result = runner.compare_diagnostic_words(path, [-7, 11, -2], [1, 3])
        self.assertFalse(result["matches"])
        self.assertEqual(result["mismatches"], 1)
        self.assertEqual(result["first_mismatch"], {"index": 1, "coordinate": [0, 1], "expected": 11, "observed": 12})

    def test_source_preload_rejects_computed_memory_even_if_manifest_is_rehashed(self):
        runner = load_runner()
        artifact = runner.lowerer.generate_model_kernel()
        changed = copy.deepcopy(artifact.provenance)
        changed["source_memories"]["selected_tokens"] = {"kind": "prompt", "width": 16, "elements": 2}
        changed["artifact_sha256"] = runner.canonical({k: v for k, v in changed.items() if k != "artifact_sha256"})
        with self.assertRaisesRegex(ValueError, "artifact_authority_mismatch"):
            runner.generate_harness(runner.lowerer.CalyxArtifact(artifact.futil, changed))

    def test_first_divergence_identifies_step_and_semantic_boundary(self):
        runner = load_runner()
        oracle = json.loads(runner.lowerer.ORACLE.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "embedding.bin"
            path.write_bytes(bytes(4 * 64 * 8))
            event = {"event": "boundary", "run": 0, "step": 0, "boundary": "embedding.sum", "file": path.name, "cycles": 123}
            with self.assertRaisesRegex(ValueError, "step=0 boundary=embedding.sum"):
                runner.check_boundary(event, Path(tmp), oracle)

    def test_receipt_verifier_rejects_a_rehashed_execution_without_feedback(self):
        runner = load_runner()
        path = ROOT / "artifacts/reference/tinystories-1m-model-sv-execution-receipt.json"
        self.assertTrue(path.is_file(), "missing full-model SV execution evidence")
        receipt = json.loads(path.read_text())
        runner.validate_execution_receipt(receipt, verify_artifacts=False)
        receipt["execution"]["host_intermediate_preload"] = True
        receipt["receipt_sha256"] = runner.canonical({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "host_preload_contract"):
            runner.validate_execution_receipt(receipt, verify_artifacts=False)

    @unittest.skipUnless(os.environ.get("LLM2FPGA_FULL_MODEL_SV") == "1", "bounded full-model acceptance is opt-in")
    def test_exact_model_two_tokens_reset_and_all_boundaries_in_generated_sv(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory(prefix="model-sv-test-") as tmp:
            receipt = runner.run_model_sv(Path(tmp), timeout=7200)
        self.assertEqual(receipt["execution"]["selected_tokens"], [11, 612])
        self.assertEqual(receipt["execution"]["complete_decode_runs"], 2)
        self.assertTrue(receipt["reset"]["restart_reproduced_all_boundaries"])
        self.assertEqual(len(receipt["boundaries"]), 2 * (3 + 8 + 1 + 1 + 1))


if __name__ == "__main__":
    unittest.main()
