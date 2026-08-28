"""Tests for fail-closed TinyStories-1M compiler-slice extraction."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/comparison/extract_tinystories_1m_block_slice.py"
MANIFEST_PATH = ROOT / "artifacts/comparison/tinystories-1m-slice-manifest.json"
CONTRACT_PATH = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"


def load_module():
    spec = importlib.util.spec_from_file_location("extract_tinystories_1m_block_slice", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = load_module()


def contract_identity() -> dict[str, object]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    return {
        "model": {key: contract["model"][key] for key in ("name", "source_model_id", "source_revision")},
        "package": {key: contract["package"][key] for key in ("sha256", "manifest_sha256")},
    }


class TinyStories1MSliceManifestTest(unittest.TestCase):
    def test_checked_in_manifest_honestly_records_missing_full_model_artifact(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["model"], "TinyStories-1M")
        self.assertEqual(manifest["slice"]["kind"], "one_transformer_block_token_step")
        self.assertEqual(manifest["status"], "source_artifact_unavailable")
        self.assertEqual(manifest["slice"]["dependency_closure"], [])
        self.assertEqual(manifest["failure"]["code"], "source_artifact_unavailable")
        self.assertEqual(manifest["discovery"]["status"], "inspected-no-source-artifact")
        self.assertTrue(manifest["discovery"]["repository_candidates"])

    def test_extracts_complete_block_and_bounded_dependency_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "model.sv"
            source.write_text(
                "module helper(input logic x, output logic y); assign y = x; endmodule\n"
                "// llm2fpga.slice_kind=one_transformer_block_token_step\n"
                "module generated_opaque_9(input logic x, output logic y); helper u_helper(.x(x), .y(y)); endmodule\n"
                "module unrelated_debug_probe(input logic x, output logic y); assign y = x; endmodule\n",
                encoding="utf-8",
            )
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"contract_identity": contract_identity()}), encoding="utf-8")
            manifest = extractor.extract([source], metadata, CONTRACT_PATH, root / "slice")
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(manifest["slice"]["kind"], "one_transformer_block_token_step")
            self.assertEqual(manifest["slice"]["dependency_closure"], ["generated_opaque_9", "helper"])
            self.assertEqual(manifest["slice"]["artifacts"][0]["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual([artifact["module"] for artifact in manifest["slice"]["artifacts"]], ["generated_opaque_9", "helper"])
            extracted_text = "".join(Path(artifact["extracted"]).read_text(encoding="utf-8") for artifact in manifest["slice"]["artifacts"])
            self.assertNotIn("unrelated_debug_probe", extracted_text)

    def test_discovery_records_known_paths_before_declaring_artifact_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            found, discovery = extractor.discover_sources(root)
            self.assertEqual(found, [])
            self.assertTrue(discovery["repository_candidates"])
            self.assertTrue(discovery["nix_output_policy"])
            output = root / "result.json"
            self.assertEqual(extractor.main(["--repo-root", str(root), "--out", str(output)]), 2)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "source_artifact_unavailable")
            self.assertEqual(result["discovery"], discovery)

    def test_contract_mismatch_writes_no_comparison_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "model.sv"
            source.write_text("module transformer_block_token_step; endmodule\n", encoding="utf-8")
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"contract_identity": {}}), encoding="utf-8")
            output = root / "result.json"
            self.assertEqual(extractor.main([
                "--input", str(source), "--metadata", str(metadata), "--slice-dir", str(root / "slice"), "--out", str(output),
            ]), 2)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "contract_mismatch")
            self.assertFalse((root / "slice").exists())

    def test_unbounded_closure_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "model.sv"
            source.write_text("module transformer_block_token_step; absent u_absent(); endmodule\n", encoding="utf-8")
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"contract_identity": contract_identity()}), encoding="utf-8")
            with self.assertRaises(extractor.ExtractionError) as caught:
                extractor.extract([source], metadata, CONTRACT_PATH, root / "slice")
            self.assertEqual(caught.exception.code, "unbounded_dependency_closure")


if __name__ == "__main__":
    unittest.main()
