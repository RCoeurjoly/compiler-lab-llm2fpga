"""Verification tests for preserved live Task 5 determinism bundles."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "pipeline"
    / "verify_tinystories_1m_exact_frontier_determinism.py"
)
BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-frontier-determinism"
)
SPEC = importlib.util.spec_from_file_location("exact_frontier_determinism", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PreservedDeterminismBundleTest(unittest.TestCase):
    def test_two_preserved_live_runs_verify_and_compare_byte_identical(self) -> None:
        result = MODULE.verify_determinism_bundles(BUNDLES)

        self.assertEqual(result["source_commit"], "f26177ee480187dd1abf5ee9b1324c61bcceab02")
        self.assertEqual(result["runs"], ["run-1", "run-2"])
        self.assertEqual(
            result["receipt_file_sha256"],
            "b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55",
        )
        self.assertEqual(
            result["receipt_self_hash"],
            "af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b",
        )
        self.assertTrue(result["byte_identical"])

    def test_manifest_marks_timestamps_and_runtime_noncanonical(self) -> None:
        result = MODULE.verify_determinism_bundles(BUNDLES)

        self.assertTrue(result["noncanonical_metadata_present"])

    def test_substantive_mutation_of_preserved_live_log_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-bundle-mutation-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            capture_log = mutated / "run-2" / "compiler-import-capture.log"
            original = capture_log.read_bytes()
            changed = original.replace(b"torch.operator", b"torch.operat0r", 1)
            self.assertNotEqual(original, changed)
            self.assertEqual(len(original), len(changed))
            capture_log.write_bytes(changed)

            with self.assertRaisesRegex(MODULE.VerificationError, "SHA-256"):
                MODULE.verify_determinism_bundles(mutated)


if __name__ == "__main__":
    unittest.main()
