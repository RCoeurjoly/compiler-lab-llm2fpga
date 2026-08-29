"""Executable evidence for the TinyStories-1M compiler/reference boundary."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/diagnose_tinystories_1m_contract_alignment.py"
METADATA = ROOT / "artifacts/comparison/tinystories-1m-baseline-float-sv-metadata.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
REPORT = ROOT / "artifacts/comparison/tinystories-1m-contract-alignment.json"


def load_module():
    spec = importlib.util.spec_from_file_location("contract_alignment", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alignment = load_module()


class TinyStories1MContractAlignmentTest(unittest.TestCase):
    def test_realized_compiler_sidecar_reports_each_identity_mismatch(self) -> None:
        result = alignment.diagnose(CONTRACT, METADATA)
        self.assertEqual(result["status"], "contract_mismatch")
        self.assertEqual(result["first_boundary"]["code"], "compiler_package_identity")
        paths = {item["path"] for item in result["mismatches"]}
        self.assertIn("package.sha256", paths)
        self.assertIn("package.manifest_sha256", paths)
        self.assertIn("compiler_quantization", result["next_boundary"]["required_evidence"])
        blocker = result["first_boundary"]["source_api_blocker"]
        self.assertEqual(blocker["export_adapter"], "TinyStories/model_adapter.py")
        self.assertEqual(blocker["package_transport"], "runtime --package argument; not a Nix input")
        self.assertIn("FP32 torch.export.ExportedProgram", blocker["export_input"])

    def test_matching_identity_is_not_promoted_to_quantization_alignment(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        metadata = json.loads(METADATA.read_text(encoding="utf-8"))
        metadata["contract_identity"] = {
            "model": {
                "name": contract["model"]["name"],
                "source_model_id": contract["model"]["source_model_id"],
                "source_revision": contract["model"]["source_revision"],
            },
            "package": {
                "sha256": contract["package"]["sha256"],
                "manifest_sha256": contract["package"]["manifest_sha256"],
            },
        }
        result = alignment._diagnose_documents(
            contract,
            metadata,
            contract_path=Path("contract.json"),
            metadata_path=Path("metadata.json"),
            contract_sha256=alignment.CANONICAL_CONTRACT_SHA256,
            metadata_sha256=alignment.CANONICAL_METADATA_SHA256,
        )
        self.assertEqual(result["status"], "compiler_quantization_unverified")
        self.assertEqual(result["mismatches"], [])
        self.assertIn("compiler_quantization", result["next_boundary"]["required_evidence"])
        self.assertIn("identity metadata alone", result["first_boundary"]["source_api_blocker"]["reason"])

    def test_copied_contract_is_rejected_even_when_content_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "contract.json"
            candidate.write_bytes(CONTRACT.read_bytes())
            with self.assertRaisesRegex(alignment.AlignmentEvidenceError, "contract_path_not_canonical"):
                alignment.diagnose(candidate, METADATA)

    def test_modified_copied_metadata_is_rejected_before_semantic_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "metadata.json"
            document = json.loads(METADATA.read_text(encoding="utf-8"))
            document["contract_identity"]["model"]["source_revision"] = "0" * 40
            candidate.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(alignment.AlignmentEvidenceError, "compiler_metadata_path_not_canonical"):
                alignment.diagnose(CONTRACT, candidate)

    def test_checked_in_report_is_self_consistent_and_fail_closed(self) -> None:
        result = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "contract_mismatch")
        self.assertEqual(result["first_boundary"]["code"], "compiler_package_identity")
        self.assertIn("source_api_blocker", result["first_boundary"])
        self.assertEqual(
            result["sha256"],
            alignment.canonical_sha256({key: value for key, value in result.items() if key != "sha256"}),
        )


if __name__ == "__main__":
    unittest.main()
