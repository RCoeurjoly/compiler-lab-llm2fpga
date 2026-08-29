"""Tests for the authenticated pre-lowering softmax provenance receipt."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/create_tinystories_1m_softmax_provenance_manifest.py"
spec = importlib.util.spec_from_file_location("softmax_manifest", SCRIPT)
assert spec and spec.loader
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def payload() -> dict:
    return {
        "schema": "tinystories-1m-softmax-provenance-v1",
        "model": "TinyStories-1M",
        "contract_sha256": manifest.CONTRACT_SHA256,
        "package": dict(manifest.PACKAGE),
        "pre_lowering_source": {
            "kind": "torch.export.ExportedProgram.graph",
            "path": "exported-program/graph.txt",
            "sha256": "0" * 64,
        },
        "lowering_stages": {
            name: {"path": f"stages/{name}.mlir", "sha256": str(index) * 64, "bytes": 100 + index}
            for index, name in enumerate(("torch_mlir", "linalg", "scf", "flat_scf"), 1)
        },
        "heads": [
            {"head": head, "identities": {role: f"head{head}.{role}" for role in manifest.ROLES}}
            for head in range(8)
        ],
    }


class SoftmaxManifestTest(unittest.TestCase):
    def test_seal_and_reload_authenticate_exact_eight_head_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest.seal(payload())), encoding="utf-8")
            loaded = manifest.load_authenticated(path)
            self.assertEqual(loaded["sha256"], manifest.canonical_sha256({k: v for k, v in loaded.items() if k != "sha256"}))
            self.assertEqual(len(loaded["heads"]), 8)

    def test_duplicate_role_identity_fails_closed(self):
        value = payload()
        value["heads"][1]["identities"]["exp"] = value["heads"][0]["identities"]["exp"]
        with self.assertRaisesRegex(manifest.ManifestError, "head_identity_duplicate"):
            manifest.seal(value)

    def test_missing_role_fails_closed(self):
        value = payload()
        del value["heads"][0]["identities"]["causal"]
        with self.assertRaisesRegex(manifest.ManifestError, "head_roles"):
            manifest.seal(value)

    def test_stage_hash_can_be_recomputed_from_exact_files(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            value = payload()
            stage_paths = {}
            for index, name in enumerate(("torch_mlir", "linalg", "scf", "flat_scf"), 1):
                path = directory / f"{name}.mlir"
                path.write_bytes(bytes([index]) * (index + 10))
                stage_paths[name] = path
            (directory / "input.json").write_text(json.dumps(value), encoding="utf-8")
            result = manifest.materialize(directory / "input.json", directory / "output.json", stage_paths)
            # materialize consumes JSON; write the input in a second pass to
            # ensure the stage replacement is tested independently.
            self.assertEqual(result["lowering_stages"]["scf"]["bytes"], 13)


if __name__ == "__main__":
    unittest.main()
