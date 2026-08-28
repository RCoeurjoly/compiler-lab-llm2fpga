"""Tests for the immutable TinyStories-1M compiler-input verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "comparison" / "verify_tinystories_1m_reference_input.py"
CONTRACT = ROOT / "artifacts" / "reference" / "tinystories-1m-kev-gpt-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
SOURCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")


def load_module():
    spec = importlib.util.spec_from_file_location("reference_input", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStories1MReferenceInputTest(unittest.TestCase):
    def test_compiler_registry_pins_the_frozen_reference_revision(self) -> None:
        contract = json.loads(CONTRACT.read_text())
        flake = (ROOT / "flake.nix").read_text()
        self.assertIn(
            f'revision = "{contract["model"]["source_revision"]}";',
            flake,
        )

    @unittest.skipUnless(PACKAGE.is_dir(), "validated external reference package is unavailable")
    def test_verified_package_receipt_records_exact_contract_identity(self) -> None:
        module = load_module()
        result = module.verify_input(CONTRACT, PACKAGE)

        self.assertEqual(result["status"], "identity_verified_adapter_required")
        self.assertEqual(result["frozen_contract_sha256"], hashlib.sha256(CONTRACT.read_bytes()).hexdigest())
        self.assertEqual(result["package"]["manifest_sha256"], "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35")
        self.assertEqual(result["package"]["weights_sha256"], "caa140a70f824334d626e20819effabb3a56c28f35cc5c84e6f5f174b3f6bf4e")
        self.assertEqual(result["package"]["scales_sha256"], "a81faadf9ab21a525a8a20870f2fa97572c66bbf6b88c5cbe2a29cd253355155")
        self.assertEqual(result["model"]["source_revision"], "ac533fb8b4f69c71894bf96badfe11e6294d9fcf")
        self.assertEqual(result["quantization"]["weight_format"], "symmetric_int8_per_output")
        self.assertEqual(result["quantization"]["activation_scale_entries"], 97)
        self.assertEqual(result["quantization"]["activation_scale_lengths"], [64, 256])
        self.assertIn("does not deserialize the package", result["adapter_requirement"])

    @unittest.skipUnless(PACKAGE.is_dir(), "validated external reference package is unavailable")
    def test_rejects_tampered_package_even_when_contract_is_unchanged(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = Path(temp_dir) / "package"
            shutil.copytree(PACKAGE, candidate)
            weights = candidate / "weights.bin"
            data = bytearray(weights.read_bytes())
            data[0] ^= 1
            weights.write_bytes(data)

            with self.assertRaisesRegex(module.InputVerificationError, "package_hash_mismatch"):
                module.verify_input(CONTRACT, candidate)

    @unittest.skipUnless(PACKAGE.is_dir(), "validated external reference package is unavailable")
    def test_cli_writes_fail_closed_identity_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "identity.json"
            completed = subprocess.run(
                ["python", str(SCRIPT), "--contract", str(CONTRACT), "--package", str(PACKAGE), "--output", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt["status"], "identity_verified_adapter_required")


if __name__ == "__main__":
    unittest.main()
