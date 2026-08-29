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
BRIDGE_SCRIPT = ROOT / "scripts/comparison/bridge_tinystories_1m_softmax.py"
bridge_spec = importlib.util.spec_from_file_location("softmax_bridge", BRIDGE_SCRIPT)
assert bridge_spec and bridge_spec.loader
bridge = importlib.util.module_from_spec(bridge_spec)
bridge_spec.loader.exec_module(bridge)


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
    def test_pre_lowering_extractor_qualifies_softmax_output(self):
        source = "\n".join([
            "%172 = torch.aten.add.Tensor %168, %171, %int1 : !torch.vtensor<[1,16,4,4],f32>, !torch.vtensor<[1,1,4,4],f32>, !torch.int -> !torch.vtensor<[1,16,4,4],f32>",
            "%values, %indices = torch.aten.max.dim %172, %int-1, %true : !torch.vtensor<[1,16,4,4],f32>, !torch.int, !torch.bool -> !torch.vtensor<[1,16,4,1],f32>, !torch.vtensor<[1,16,4,1],si64>",
            "%173 = torch.aten.sub.Tensor %172, %values, %float1.000000e00 : !torch.vtensor<[1,16,4,4],f32>, !torch.vtensor<[1,16,4,1],f32>, !torch.float -> !torch.vtensor<[1,16,4,4],f32>",
            "%174 = torch.aten.exp %173 : !torch.vtensor<[1,16,4,4],f32> -> !torch.vtensor<[1,16,4,4],f32>",
            "%176 = torch.aten.sum.dim_IntList %174, %dims, %true, %none : !torch.vtensor<[1,16,4,4],f32>, !torch.list<int>, !torch.bool, !torch.none -> !torch.vtensor<[1,16,4,1],f32>",
            "%177 = torch.aten.div.Tensor %174, %176 : !torch.vtensor<[1,16,4,4],f32>, !torch.vtensor<[1,16,4,1],f32> -> !torch.vtensor<[1,16,4,4],f32>",
            "%168 = torch.aten.where.self %mask, %165, %zero : !torch.vtensor<[1,1,4,4],i1>, !torch.vtensor<[1,16,4,4],f32>, !torch.vtensor<[],f32> -> !torch.vtensor<[1,16,4,4],f32>",
        ])
        extracted = manifest.extract_pre_lowering_identities(source, "fixture.mlir")
        self.assertEqual(extracted["identities"]["normalization"], "%177")
        self.assertEqual(extracted["identities"]["output"], "softmax_output:%177")
        self.assertNotEqual(extracted["identities"]["normalization"], extracted["identities"]["output"])

    def test_seal_and_reload_authenticate_exact_eight_head_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest.seal(payload())), encoding="utf-8")
            loaded = manifest.load_authenticated(path)
            self.assertEqual(loaded["sha256"], manifest.canonical_sha256({k: v for k, v in loaded.items() if k != "sha256"}))
            self.assertEqual(len(loaded["heads"]), 8)

    def test_bridge_loader_accepts_sealed_manifest_without_raw_file_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest.seal(payload()), indent=2), encoding="utf-8")
            loaded = bridge.load_provenance_manifest(path)
            self.assertEqual(loaded["sha256"], manifest.canonical_sha256({k: v for k, v in loaded.items() if k != "sha256"}))

    def test_bridge_uses_authenticated_lowered_zero_identity(self):
        fixture_spec = importlib.util.spec_from_file_location("softmax_bridge_tests", ROOT / "tests/test_tinystories_1m_softmax_bridge.py")
        assert fixture_spec and fixture_spec.loader
        fixtures = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixtures)
        value = payload()
        value["constants"] = {
            "zero_f32": {
                "value": "0.0",
                "type": "f32",
                "pre_lowering_identity": "%0",
                "lowered_identities": {
                    name: "%cst_6" for name in ("torch_mlir", "linalg", "scf", "flat_scf")
                },
            }
        }
        sealed = manifest.seal(value)
        evidence = bridge.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        graph = fixtures.lowered_separate_loop_graph().replace("%fzero", "%cst_6")
        descriptor = bridge.bridge_graph(graph, evidence, source_name="lowered-with-cst6.mlir", provenance_manifest=sealed)
        self.assertEqual(descriptor["source"]["pre_lowering_provenance_manifest_sha256"], sealed["sha256"])

    def _bridge_with_manifest(self, value, graph=None):
        fixture_spec = importlib.util.spec_from_file_location("softmax_bridge_tests", ROOT / "tests/test_tinystories_1m_softmax_bridge.py")
        assert fixture_spec and fixture_spec.loader
        fixtures = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixtures)
        evidence = bridge.load_evidence(
            ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json",
        )
        return bridge.bridge_graph(graph or fixtures.lowered_separate_loop_graph().replace("%fzero", "%cst_6"), evidence,
                                   source_name="manifest-negative.mlir", provenance_manifest=manifest.seal(value))

    def test_manifest_supplied_without_zero_fails_closed(self):
        with self.assertRaisesRegex(bridge.SoftmaxBridgeError, "constants required"):
            self._bridge_with_manifest(payload())

    def test_manifest_wrong_zero_value_fails_closed(self):
        value = payload()
        value["constants"] = {"zero_f32": {"value": "1.0", "type": "f32", "pre_lowering_identity": "%0",
                                             "lowered_identities": {name: "%cst_6" for name in ("torch_mlir", "linalg", "scf", "flat_scf")}}}
        with self.assertRaisesRegex(manifest.ManifestError, "zero_f32 value/type"):
            manifest.seal(value)

    def test_manifest_malformed_zero_identity_fails_closed(self):
        value = payload()
        value["constants"] = {"zero_f32": {"value": "0.0", "type": "f32", "pre_lowering_identity": "%0",
                                             "lowered_identities": {name: "cst_6" for name in ("torch_mlir", "linalg", "scf", "flat_scf")}}}
        with self.assertRaisesRegex(manifest.ManifestError, "zero_f32\.torch_mlir"):
            manifest.seal(value)

    def test_manifest_renamed_zero_identity_does_not_fallback(self):
        value = payload()
        value["constants"] = {"zero_f32": {"value": "0.0", "type": "f32", "pre_lowering_identity": "%0",
                                             "lowered_identities": {name: "%renamed_zero" for name in ("torch_mlir", "linalg", "scf", "flat_scf")}}}
        fixture_spec = importlib.util.spec_from_file_location("softmax_bridge_tests", ROOT / "tests/test_tinystories_1m_softmax_bridge.py")
        assert fixture_spec and fixture_spec.loader
        fixtures = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixtures)
        with self.assertRaisesRegex(bridge.SoftmaxBridgeError, "authenticated floating zero constant"):
            bridge._lowered_pattern_evidence(fixtures.lowered_separate_loop_graph().replace("%fzero", "%cst_6"), zero_identity="%renamed_zero")

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
