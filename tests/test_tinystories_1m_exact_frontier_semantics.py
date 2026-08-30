from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
FIXTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-shift-semantics.json"
DECISION = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"

SPEC = importlib.util.spec_from_file_location("exact_frontier_semantics", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactFrontierSemanticContractTest(unittest.TestCase):
    def _probe_report(self, stage: Path, derivation: Path, tool: Path) -> dict[str, object]:
        decision = json.loads(DECISION.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cases = [
            {"id": case["id"], "status": "ok", "output": case["expected"]}
            for case in fixture["valid_cases"]
        ] + [
            {"id": case["id"], "status": case["status"], "diagnostic": case["diagnostic"]}
            for case in fixture["invalid_cases"]
        ]
        report = {
            "schema": "tinystories-1m-exact-shift-semantic-probe-v1",
            "decision_sha256": decision["sha256"],
            "fixture_file_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "fixture_self_hash": fixture["sha256"],
            "producer": {
                "script_path": decision["semantic_regression"]["probe_producer_script_path"],
                "script_sha256": decision["semantic_regression"]["probe_producer_script_sha256"],
                "command": ["python", "probe.py"],
            },
            "stage": {
                "attribute": decision["semantic_regression"]["registered_stage_attribute"],
                "build_command": decision["semantic_regression"]["registered_stage_build_command"],
                "build_command_sha256": decision["semantic_regression"]["registered_stage_build_command_sha256"],
                "artifact": str(stage),
                "artifact_sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
                "derivation": str(derivation),
                "derivation_sha256": hashlib.sha256(derivation.read_bytes()).hexdigest(),
            },
            "tool": {
                "binary": str(tool),
                "binary_sha256": hashlib.sha256(tool.read_bytes()).hexdigest(),
                "pipeline": decision["semantic_regression"]["torch_mlir_pipeline"],
                "pipeline_sha256": decision["semantic_regression"]["torch_mlir_pipeline_sha256"],
            },
            "executor": {
                "path": decision["semantic_regression"]["probe_executor_contract_path"],
                "sha256": "b" * 64,
                "command": ["executor", "--out", "results.json"],
            },
            "cases": cases,
        }
        report["producer"]["command_sha256"] = MODULE.canonical_sha256(report["producer"]["command"])
        report["executor"]["command_sha256"] = MODULE.canonical_sha256(report["executor"]["command"])
        report["sha256"] = MODULE.canonical_sha256(report)
        return report

    def test_probe_rejects_detached_or_misbinding_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, derivation, tool = root / "torch.mlir", root / "torch.drv", root / "torch-mlir-opt"
            stage.write_text("module {}\n", encoding="utf-8")
            derivation.write_text("derivation", encoding="utf-8")
            tool.write_text("tool", encoding="utf-8")
            report_path = root / "probe.json"
            report = self._probe_report(stage, derivation, tool)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = MODULE.verify_probe_report(report_path, FIXTURE, DECISION, derivation_resolver=lambda _: derivation)
            self.assertEqual(result["status"], "accepted")
            for mutation, diagnostic in (
                (("stage", "artifact_sha256", "0" * 64), "probe_stage_artifact_hash"),
                (("producer", "script_sha256", "0" * 64), "probe_producer_script_hash"),
                (("tool", "binary_sha256", "0" * 64), "probe_tool_binary_hash"),
                (("tool", "pipeline_sha256", "0" * 64), "probe_pipeline_hash"),
                (("decision_sha256", None, "0" * 64), "probe_decision_hash"),
            ):
                altered = json.loads(json.dumps(report))
                parent, key, value = mutation
                if key is None:
                    altered[parent] = value
                else:
                    altered[parent][key] = value
                altered["sha256"] = MODULE.canonical_sha256({k: v for k, v in altered.items() if k != "sha256"})
                report_path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, diagnostic):
                    MODULE.verify_probe_report(report_path, FIXTURE, DECISION, derivation_resolver=lambda _: derivation)

    def test_probe_rejects_stale_hash_and_duplicate_extra_or_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, derivation, tool = root / "torch.mlir", root / "torch.drv", root / "torch-mlir-opt"
            stage.write_text("module {}\n", encoding="utf-8")
            derivation.write_text("derivation", encoding="utf-8")
            tool.write_text("tool", encoding="utf-8")
            report_path = root / "probe.json"
            report = self._probe_report(stage, derivation, tool)
            for modifier, diagnostic in (
                (lambda value: value.__setitem__("sha256", "0" * 64), "probe_self_hash"),
                (lambda value: value["cases"].append(dict(value["cases"][0])), "probe_case_duplicate"),
                (lambda value: value["cases"].append({"id": "extra", "status": "ok", "output": {}}), "probe_case_set"),
                (lambda value: value["cases"].pop(), "probe_case_set"),
            ):
                altered = json.loads(json.dumps(report))
                modifier(altered)
                if diagnostic != "probe_self_hash":
                    altered["sha256"] = MODULE.canonical_sha256({k: v for k, v in altered.items() if k != "sha256"})
                report_path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, diagnostic):
                    MODULE.verify_probe_report(report_path, FIXTURE, DECISION, derivation_resolver=lambda _: derivation)

            stale_decision = json.loads(DECISION.read_text(encoding="utf-8"))
            stale_decision["decision"]["expected_observable_improvement"] = "stale"
            stale_path = root / "stale-decision.json"
            stale_path.write_text(json.dumps(stale_decision), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decision_self_hash"):
                MODULE.verify_probe_report(report_path, FIXTURE, stale_path, derivation_resolver=lambda _: derivation)

    def test_contract_interprets_signed_si64_shift_vectors(self) -> None:
        result = MODULE.verify_contract(FIXTURE, DECISION)
        self.assertEqual(result["valid_cases"], ["shift_one", "shift_zero", "shift_sixty_two"])
        self.assertEqual(result["rejected_cases"], ["negative_shift", "shift_greater_than_sixty_two"])
        self.assertEqual(result["shift_one_output"], [-3, -1, 0, 0, 2])

    def test_registered_stage_requires_current_task_identity_hashes(self) -> None:
        decision = json.loads(DECISION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "torch.mlir"
            stage.write_text("module {}\n", encoding="utf-8")
            result = MODULE.verify_registered_stage(stage, decision)
            self.assertEqual(result["status"], "accepted")
            decision["identity_hashes"]["task_3_generation_result_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "task3_generation_result_hash"):
                MODULE.verify_registered_stage(stage, decision)


if __name__ == "__main__":
    unittest.main()
