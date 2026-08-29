"""Tests for the fail-closed authenticated TinyStories package lowering gate."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/lower_tinystories_1m_authenticated_package.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path("/home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/snapshots/77f1b168e219585646439073245fe87e56b3023e")
MATERIALIZER = ROOT / "scripts/comparison/materialize_tinystories_1m_package_export.py"


@unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
class AuthenticatedPackageLoweringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.export = root / "export"
        completed = subprocess.run([
            "python", str(MATERIALIZER), "--contract", str(CONTRACT), "--package", str(PACKAGE),
            "--model-path", str(MODEL), "--out-dir", str(cls.export),
        ], cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode:
            raise RuntimeError(completed.stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def run_gate(self, output: Path, export: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([
            "python", str(SCRIPT), "--contract", str(CONTRACT), "--package-export", str(export or self.export),
            "--package", str(PACKAGE), "--out-dir", str(output),
        ], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_metadata_only_qdq_is_preserved_and_cannot_be_labelled_aligned(self) -> None:
        output = Path(self.temp.name) / "lowered"
        completed = self.run_gate(output)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        attempt = json.loads((output / "lowering-attempt.json").read_text())
        self.assertEqual(attempt["status"], "unsupported")
        self.assertEqual(attempt["alignment_status"], "unaligned")
        self.assertEqual(attempt["activation_qdq_boundary_count"], 97)
        self.assertEqual(attempt["failure"]["code"], "activation_rounding_semantics_unavailable")
        self.assertIsNone(attempt["compiler_artifact"])
        self.assertEqual(attempt, json.loads((output / "compiler-artifact-metadata.json").read_text()))
        for name in ("canonical-contract.json", "adapter-receipt.json", "package-receipt.json", "exported.pt2", "numeric-trace.json"):
            self.assertTrue((output / name).is_file(), name)
        self.assertEqual(
            attempt["package_export"]["exported_program_sha256"],
            hashlib.sha256((output / "exported.pt2").read_bytes()).hexdigest(),
        )

    def test_tampered_export_is_rejected_before_a_lowering_record(self) -> None:
        export = Path(self.temp.name) / "tampered-export"
        shutil.copytree(self.export, export)
        export.joinpath("exported.pt2").write_bytes(b"tampered")
        output = Path(self.temp.name) / "tampered-result"
        completed = self.run_gate(output, export)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("artifact_hash_mismatch", completed.stderr)
        self.assertFalse((output / "lowering-attempt.json").exists())

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
