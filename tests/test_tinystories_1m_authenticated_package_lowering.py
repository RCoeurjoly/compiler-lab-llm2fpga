"""Tests for the fail-closed authenticated TinyStories package lowering gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/lower_tinystories_1m_authenticated_package.py"


def load_adapter():
    path = ROOT / "TinyStories/model_adapter_reference_package.py"
    spec = importlib.util.spec_from_file_location("package_adapter_for_lowering_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = load_adapter()


class AuthenticatedPackageLoweringTest(unittest.TestCase):
    """Synthetic fixtures keep trust-boundary tests runnable without local inputs."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / "package"
        self.export = self.root / "export"
        self.package.mkdir()
        self.export.mkdir()
        self.contract_path = self.root / "contract.json"
        self._write_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def _write_fixture(self) -> None:
        boundaries = {
            name: [float(index + 1)] * (64 if index % 2 == 0 else 256)
            for index, name in enumerate(sorted(ADAPTER._expected_activation_names(8)))
        }
        manifest = {"model": {"n_layer": 8}, "activation_scales": boundaries}
        self.write_json(self.package / "manifest.json", manifest)
        for name, content in (("weights.bin", b"weights"), ("scales.bin", b"scales"), ("calibration_ids.bin", b"ids"), ("receipt.json", b"package-receipt")):
            (self.package / name).write_bytes(content)
        contract = {
            "model": {
                "name": "TinyStories-1M", "source_model_id": "synthetic/tinystories", "source_revision": "a" * 40,
                "n_layer": 8, "hidden_size": 64, "n_head": 16, "head_dim": 4, "vocab_size": 50257,
                "max_context": 32, "tie_word_embeddings": True, "activation_function": "gelu_new",
            },
            "tokenizer": {"type": "synthetic"},
            "package": {
                "manifest_sha256": self.digest(self.package / "manifest.json"),
                "sha256": self.digest(self.package / "weights.bin"),
                "files": {"scales.bin": self.digest(self.package / "scales.bin"), "calibration_ids.bin": self.digest(self.package / "calibration_ids.bin"), "receipt.json": self.digest(self.package / "receipt.json")},
            },
            "memory_image": {"bytes": len(b"weights")},
        }
        self.write_json(self.contract_path, contract)
        (self.export / "exported.pt2").write_bytes(b"serialized export")
        (self.export / "numeric-trace.json").write_text("{}\n", encoding="utf-8")
        verified_input = {
            "schema": "tinystories-1m-reference-compiler-input-v1", "status": "identity_verified_adapter_required",
            "frozen_contract_sha256": self.digest(self.contract_path), "frozen_contract_path": str(self.contract_path),
            "package": {"path": str(self.package), "manifest_sha256": contract["package"]["manifest_sha256"], "weights_sha256": contract["package"]["sha256"], "scales_sha256": contract["package"]["files"]["scales.bin"], "calibration_ids_sha256": contract["package"]["files"]["calibration_ids.bin"], "receipt_sha256": contract["package"]["files"]["receipt.json"], "weight_bytes": len(b"weights")},
            "model": {"source_model_id": contract["model"]["source_model_id"], "source_revision": contract["model"]["source_revision"], "model_type": "gpt_neo", "n_layer": 8, "hidden_size": 64, "n_head": 16, "head_dim": 4, "vocab_size": 50257, "max_context": 32, "tie_word_embeddings": True, "activation_function": "gelu_new"},
        }
        receipt = {
            "schema": "tinystories-1m-package-gpt-neo-adapter-v1", "status": "dequantized_weight_export_ready",
            "identity": {"contract_sha256": self.digest(self.contract_path), "model": contract["model"], "tokenizer": contract["tokenizer"], "package": contract["package"], "config_sha256": ADAPTER.CONFIG_SHA256},
            "verified_input": verified_input, "activation_qdq_boundaries": ADAPTER._activation_boundaries(manifest),
            "activation_qdq_execution": {"status": "metadata_only", "reason_code": "activation_rounding_semantics_unavailable"},
            "artifacts": {"exported_program": {"path": "exported.pt2", "sha256": self.digest(self.export / "exported.pt2")}, "numeric_trace": {"path": "numeric-trace.json", "sha256": self.digest(self.export / "numeric-trace.json")}},
        }
        receipt["receipt_sha256"] = ADAPTER.receipt_sha256(receipt)
        self.write_json(self.export / "adapter-receipt.json", receipt)

    def run_gate(self, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python", str(SCRIPT), "--contract", str(self.contract_path), "--package-export", str(self.export), "--package", str(self.package), "--out-dir", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)

    def mutate_receipt(self, mutate) -> None:
        path = self.export / "adapter-receipt.json"
        receipt = json.loads(path.read_text())
        mutate(receipt)
        receipt["receipt_sha256"] = ADAPTER.receipt_sha256(receipt)
        self.write_json(path, receipt)

    def test_metadata_only_qdq_is_preserved_and_cannot_be_labelled_aligned(self) -> None:
        output = self.root / "lowered"
        completed = self.run_gate(output)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        attempt = json.loads((output / "lowering-attempt.json").read_text())
        self.assertEqual((attempt["status"], attempt["alignment_status"], attempt["activation_qdq_boundary_count"]), ("unsupported", "unaligned", 97))
        self.assertEqual(attempt["failure"]["code"], "activation_rounding_semantics_unavailable")
        self.assertIsNone(attempt["compiler_artifact"])

    def test_rejects_rehashed_unrelated_verified_input_and_boundary_content(self) -> None:
        self.mutate_receipt(lambda receipt: receipt["verified_input"].__setitem__("status", "forged"))
        completed = self.run_gate(self.root / "bad-verifier")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("verifier_identity_mismatch", completed.stderr)
        self._write_fixture()
        self.mutate_receipt(lambda receipt: receipt["activation_qdq_boundaries"]["lm_head.input"].__setitem__("width", 17))
        completed = self.run_gate(self.root / "bad-boundary")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("activation_boundary_content_mismatch", completed.stderr)

    def test_rejects_bad_adapter_hash_and_nonempty_output_atomically(self) -> None:
        receipt_path = self.export / "adapter-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["receipt_sha256"] = "0" * 64
        self.write_json(receipt_path, receipt)
        output = self.root / "bad-hash"
        completed = self.run_gate(output)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("adapter_receipt_hash_mismatch", completed.stderr)
        self.assertFalse(output.exists())
        self._write_fixture()
        output.mkdir()
        (output / "preserve-me").write_text("x", encoding="utf-8")
        completed = self.run_gate(output)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("output_not_empty", completed.stderr)
        self.assertEqual((output / "preserve-me").read_text(encoding="utf-8"), "x")

    def test_nix_entrypoint_is_declared_without_rc_or_transport(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn('"tinystories-1m-authenticated-package-lowering"', flake)
        block = flake[flake.index('"tinystories-1m-authenticated-package-lowering"'):]
        self.assertIn("lower_tinystories_1m_authenticated_package.py", block)
        self.assertNotIn("representative-core", block[:3500])
        self.assertNotIn("pcie", block[:3500].lower())
        self.assertNotIn("ddr3", block[:3500].lower())


if __name__ == "__main__":
    unittest.main()
