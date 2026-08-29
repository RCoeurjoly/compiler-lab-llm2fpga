"""Tests for the authenticated fixed-profile transformer-block lowering probe."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/lower_tinystories_1m_fixed_profile_slice.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
QDQ = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
TASK2 = ROOT / "artifacts/comparison/tinystories-1m-slice-manifest.json"
CANONICAL_INPUT = Path("/tmp/task3l-fixed-qdq-lowering")


def load_module():
    spec = importlib.util.spec_from_file_location("fixed_profile_slice_lowering", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedProfileSliceLoweringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_real_exported_program_inspection_finds_layer_norm(self) -> None:
        """Removing PT2 graph inspection must make this test fail."""
        import torch

        class LayerNormSlice(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.norm = torch.nn.LayerNorm(64)

            def forward(self, value: torch.Tensor) -> torch.Tensor:
                return self.norm(value)

        with tempfile.TemporaryDirectory() as temporary:
            exported = torch.export.export(
                LayerNormSlice().eval(), (torch.zeros((1, 4, 64), dtype=torch.float32),)
            )
            archive = Path(temporary) / "layernorm.pt2"
            torch.export.save(exported, archive)
            operations = self.module.inspect_exported_program(archive)

        self.assertEqual(operations[0]["target"], "aten.layer_norm.default")

    def test_missing_layer_norm_semantics_is_the_first_fail_closed_boundary(self) -> None:
        """Treating checkpoint examples as an operator definition must fail this test."""
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        result = self.module.classify_block_lowering(
            profile,
            [{"graph_index": 149, "name": "layer_norm", "target": "aten.layer_norm.default"}],
        )

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["first_unsupported_operation"]["checkpoint"], "block.ln_1")
        self.assertEqual(result["first_unsupported_operation"]["target"], "aten.layer_norm.default")
        self.assertEqual(
            result["first_unsupported_operation"]["code"],
            "fixed_layer_norm_semantics_unavailable",
        )
        self.assertEqual(result["semantically_defined_prefix"], ["block.input.activation_qdq"])

    def test_unsupported_report_cannot_claim_compiler_artifacts_or_equivalence(self) -> None:
        """Adding partial MLIR/SV or a simulated-equivalent claim must fail this test."""
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        result = self.module.make_unsupported_report(
            profile=profile,
            operations=[{"graph_index": 149, "name": "layer_norm", "target": "aten.layer_norm.default"}],
            evidence={"contract_sha256": "a" * 64},
        )

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["alignment_status"], "unaligned")
        self.assertEqual(result["software_trace"]["checkpoint_count"], 12)
        self.assertEqual(result["software_trace"]["status"], "authenticated_profile_trace_validated")
        self.assertEqual(result["compiler_slice_equivalence"]["status"], "not_run")
        self.assertEqual(
            result["compiler_slice_equivalence"]["reason_code"],
            "compiler_slice_not_emitted",
        )
        self.assertEqual(result["compiler_artifacts"], {"mlir": None, "systemverilog": None, "rtlil": None})
        self.assertFalse(result["board_authenticated"])

    def test_wrong_export_hash_is_rejected_before_graph_loading(self) -> None:
        """Substituting another PT2 archive must fail before it can influence the report."""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "not-the-canonical-export.pt2"
            path.write_bytes(b"not the authenticated export")
            with self.assertRaisesRegex(
                self.module.FixedProfileSliceLoweringError,
                "exported_program_identity_mismatch",
            ):
                self.module.validate_inputs(
                    contract_path=CONTRACT,
                    profile_path=PROFILE,
                    qdq_path=QDQ,
                    task2_path=TASK2,
                    lowering_dir=path.parent,
                    exported_program=path,
                )

    @unittest.skipUnless(
        (CANONICAL_INPUT / "exported.pt2").is_file()
        and (CANONICAL_INPUT / "lowering-attempt.json").is_file(),
        "Task 3l canonical materialization is unavailable",
    )
    def test_canonical_task3l_export_reports_exact_first_unsupported_op(self) -> None:
        """The authenticated full export must reach the same concrete boundary."""
        evidence = self.module.validate_inputs(
            contract_path=CONTRACT,
            profile_path=PROFILE,
            qdq_path=QDQ,
            task2_path=TASK2,
            lowering_dir=CANONICAL_INPUT,
            exported_program=CANONICAL_INPUT / "exported.pt2",
        )
        operations = self.module.inspect_exported_program(CANONICAL_INPUT / "exported.pt2")
        report = self.module.make_unsupported_report(
            profile=json.loads(PROFILE.read_text(encoding="utf-8")),
            operations=operations,
            evidence=evidence,
        )

        unsupported = report["first_unsupported_operation"]
        self.assertEqual((unsupported["graph_index"], unsupported["target"]), (149, "aten.layer_norm.default"))
        self.assertEqual(report["graph"]["exported_program_sha256"], "389964a2f39a8256bc824b58b60f681bd136f2868633125e8872ce9791c8e73e")
        self.assertEqual(report["task2_metadata"]["status"], "contract_mismatch")


if __name__ == "__main__":
    unittest.main()
