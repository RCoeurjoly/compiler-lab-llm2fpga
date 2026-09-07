"""Compiler-owned full-model composition, separate from SV execution acceptance."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_model_to_calyx.py"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json"


def load_lowerer():
    if not LOWERER.exists():
        raise AssertionError("missing compiler-owned model orchestrator")
    spec = importlib.util.spec_from_file_location("model_orchestrator_test", LOWERER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ModelOrchestratorTest(unittest.TestCase):
    def test_rejects_host_feedback_and_hidden_state_before_generation(self):
        lowerer = load_lowerer()
        for forbidden in ({"host_second_token": 11}, {"host_intermediate_states": [0]}):
            with self.assertRaisesRegex(ValueError, "host_.*forbidden"):
                lowerer.generate_model_kernel(ORACLE, **forbidden)

    def test_generated_full_model_compiles_with_real_memory_feedback(self):
        # Catches invalid component composition, width/bank/address mismatches,
        # and missing top-level ports in the actual Calyx-emitted SV.
        lowerer = load_lowerer()
        artifact = lowerer.generate_model_kernel(ORACLE)
        with tempfile.TemporaryDirectory(prefix="model-orchestrator-compile-") as tmp:
            receipt = lowerer.compile_model_kernel(artifact, Path(tmp), timeout=120)
            self.assertEqual(receipt["status"], "generated_sv")
            self.assertEqual(receipt["futil_sha256"], artifact.provenance["futil_sha256"])
            self.assertEqual(set(receipt["top_ports"]), {"clk", "reset", "start", "valid", "done"})
            self.assertGreater(receipt["verilog_bytes"], 1000)
        self.assertFalse(artifact.provenance["claims"]["sv_execution_verified"])
        self.assertEqual(artifact.provenance["schedule"]["layers"], list(range(8)))
        self.assertEqual(artifact.provenance["schedule"]["real_context_lengths"], [4, 5])

    def test_source_manifest_excludes_all_hardware_intermediates(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_model_kernel(ORACLE)
        sources = artifact.provenance["source_memories"]
        for name in ("context_tokens", "selected_tokens", "block_input_q16_16", "model_logits"):
            self.assertNotIn(name, sources)
        self.assertEqual(sources["prompt_tokens"]["elements"], 4)
        self.assertEqual(sources["token_weight_codes_i8"]["elements"], 50257 * 64)
        self.assertEqual(sources["q_weight_codes_i8"]["elements"], 8 * 64 * 64)

    def test_materialized_bank_zero_matches_existing_independent_slice_authorities(self):
        # Wrong bank ordering, projection mapping or transpose breaks these
        # independently checked-in source tensor hashes.
        lowerer = load_lowerer()
        capture = lowerer._load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "orchestrator_source_capture")
        bundle = capture.exact_adapter.load_successor_exact_model(
            capture.DEFAULT_CONTRACT, capture.DEFAULT_PACKAGE,
            capture.DEFAULT_MODEL, capture.DEFAULT_GENERATION,
        )
        artifact = lowerer.generate_model_kernel(ORACLE)
        sources = lowerer.materialize_model_sources(artifact, bundle)
        records = {}
        for name in ("attention", "mlp"):
            fixture = ROOT / f"artifacts/reference/tinystories-1m-fixed-point-{name}-crossing-slice.json"
            records.update(json.loads(fixture.read_text())["tensors"])
        for name, value in sources.items():
            if name in records:
                count = artifact.provenance["source_memories"][name].get("bank_elements", value.numel())
                digest = hashlib.sha256(value[:count].numpy().astype("<i8").tobytes()).hexdigest()
                self.assertEqual(digest, records[name]["little_endian_int64_sha256"], name)
        self.assertEqual(sources["prompt_tokens"].tolist(), [7454, 2402, 257, 640])
        oracle = json.loads(ORACLE.read_text())
        for memory, record in (("token_weight_codes_i8", "weight_codes"), ("token_weight_scale_q8_24", "weight_scales")):
            digest = hashlib.sha256(sources[memory].numpy().astype("<i8").tobytes()).hexdigest()
            self.assertEqual(digest, oracle["steps"][0]["lm_head"][record]["little_endian_int64_sha256"])

    def test_deadline_failure_preserves_an_explicit_stage_diagnostic(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_model_kernel(ORACLE)
        with tempfile.TemporaryDirectory(prefix="model-deadline-") as tmp:
            with self.assertRaisesRegex(ValueError, "deadline_exceeded"):
                lowerer.compile_model_kernel(artifact, Path(tmp), timeout=0.000001)
            failure = json.loads((Path(tmp) / "compile.json").read_text())
            self.assertEqual(failure["status"], "deadline_exceeded")
            self.assertEqual(failure["stage"], "calyx_tool_resolution")
            self.assertFalse(failure["execution_verified"])

    def test_compile_evidence_is_current_self_hashed_and_makes_no_inference_claim(self):
        lowerer = load_lowerer()
        path = ROOT / "artifacts/reference/tinystories-1m-model-orchestrator-compile-evidence.json"
        self.assertTrue(path.is_file(), "missing compile-only provenance evidence")
        evidence = json.loads(path.read_text())
        unsigned = {key: value for key, value in evidence.items() if key != "artifact_sha256"}
        self.assertEqual(lowerer._canonical(unsigned), evidence["artifact_sha256"])
        artifact = lowerer.generate_model_kernel(ORACLE)
        self.assertEqual(evidence["futil_sha256"], artifact.provenance["futil_sha256"])
        self.assertEqual(evidence["generator_sha256"], hashlib.sha256(LOWERER.read_bytes()).hexdigest())
        self.assertEqual(evidence["provenance_sha256"], artifact.provenance["artifact_sha256"])
        self.assertFalse(evidence["execution_verified"])


if __name__ == "__main__":
    unittest.main()
