from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py"
FIXTURE = ROOT / "artifacts/comparison/tinystories-1m-exact-shift-semantics.json"
DECISION = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-decision.json"
EXECUTOR = ROOT / "scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py"
PRODUCER = ROOT / "scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py"
LINALG_TO_LLVM_PIPELINE = [
    "--empty-tensor-to-alloc-tensor",
    "--one-shot-bufferize=bufferize-function-boundaries",
    "--convert-bufferization-to-memref",
    "--linalg-generalize-named-ops",
    "--convert-linalg-to-loops",
    "--lower-affine",
    "--convert-scf-to-cf",
    "--expand-strided-metadata",
    "--finalize-memref-to-llvm",
    "--convert-index-to-llvm",
    "--convert-arith-to-llvm",
    "--convert-math-to-llvm",
    "--convert-cf-to-llvm",
    "--convert-func-to-llvm",
    "--reconcile-unrealized-casts",
]

SPEC = importlib.util.spec_from_file_location("exact_frontier_semantics", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactFrontierSemanticContractTest(unittest.TestCase):
    def _probe_report(
        self,
        stage: Path,
        derivation: Path,
        tool: Path,
        mlir_opt: Path,
        mlir_runner: Path,
    ) -> dict[str, object]:
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
                "sha256": hashlib.sha256(EXECUTOR.read_bytes()).hexdigest(),
                "command": ["executor", "--out", "results.json"],
                "compiler_route": {
                    "torch_backend_pipeline": "torch-backend-to-linalg-on-tensors-backend-pipeline",
                    "linalg_to_llvm_pipeline": LINALG_TO_LLVM_PIPELINE,
                    "mlir_opt": {
                        "binary": str(mlir_opt),
                        "binary_sha256": hashlib.sha256(mlir_opt.read_bytes()).hexdigest(),
                    },
                    "mlir_runner": {
                        "binary": str(mlir_runner),
                        "binary_sha256": hashlib.sha256(mlir_runner.read_bytes()).hexdigest(),
                    },
                },
            },
            "cases": cases,
        }
        for record in report["cases"]:
            if record["status"] == "ok":
                record["compiler_evidence"] = {
                    "torch_module_sha256": "1" * 64,
                    "torch_frontend_output_sha256": "2" * 64,
                    "linalg_output_sha256": "3" * 64,
                    "native_module_sha256": "4" * 64,
                    "runner_stdout_sha256": "5" * 64,
                }
            else:
                record["compiler_evidence"] = {
                    "torch_module_sha256": "1" * 64,
                    "compiler_exit_code": 1,
                    "compiler_stderr_sha256": "2" * 64,
                }
        report["producer"]["command_sha256"] = MODULE.canonical_sha256(report["producer"]["command"])
        report["executor"]["command_sha256"] = MODULE.canonical_sha256(report["executor"]["command"])
        report["sha256"] = MODULE.canonical_sha256(report)
        return report

    def test_probe_rejects_detached_or_misbinding_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, derivation, tool = root / "torch.mlir", root / "torch.drv", root / "torch-mlir-opt"
            mlir_opt, mlir_runner = root / "mlir-opt", root / "mlir-runner"
            stage.write_text("module {}\n", encoding="utf-8")
            derivation.write_text("derivation", encoding="utf-8")
            tool.write_text("tool", encoding="utf-8")
            mlir_opt.write_text("mlir-opt", encoding="utf-8")
            mlir_runner.write_text("mlir-runner", encoding="utf-8")
            report_path = root / "probe.json"
            report = self._probe_report(stage, derivation, tool, mlir_opt, mlir_runner)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = MODULE.verify_probe_report(report_path, FIXTURE, DECISION, derivation_resolver=lambda _: derivation)
            self.assertEqual(result["status"], "accepted")
            for mutation, diagnostic in (
                (("stage", "artifact_sha256", "0" * 64), "probe_stage_artifact_hash"),
                (("producer", "script_sha256", "0" * 64), "probe_producer_script_hash"),
                (("tool", "binary_sha256", "0" * 64), "probe_tool_binary_hash"),
                (("tool", "pipeline_sha256", "0" * 64), "probe_pipeline_hash"),
                (("executor", "sha256", "0" * 64), "probe_executor_hash"),
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
            for modifier, diagnostic in (
                (
                    lambda value: value["executor"]["compiler_route"].__setitem__(
                        "torch_backend_pipeline", "detached"
                    ),
                    "probe_torch_backend_pipeline",
                ),
                (
                    lambda value: value["executor"]["compiler_route"].__setitem__(
                        "linalg_to_llvm_pipeline", ["--canonicalize"]
                    ),
                    "probe_linalg_to_llvm_pipeline",
                ),
                (
                    lambda value: value["executor"]["compiler_route"]["mlir_opt"].__setitem__(
                        "binary_sha256", "0" * 64
                    ),
                    "probe_mlir_opt_binary_hash",
                ),
            ):
                altered = json.loads(json.dumps(report))
                modifier(altered)
                altered["sha256"] = MODULE.canonical_sha256(
                    {key: value for key, value in altered.items() if key != "sha256"}
                )
                report_path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, diagnostic):
                    MODULE.verify_probe_report(report_path, FIXTURE, DECISION, derivation_resolver=lambda _: derivation)

    def test_probe_rejects_stale_hash_and_duplicate_extra_or_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage, derivation, tool = root / "torch.mlir", root / "torch.drv", root / "torch-mlir-opt"
            mlir_opt, mlir_runner = root / "mlir-opt", root / "mlir-runner"
            stage.write_text("module {}\n", encoding="utf-8")
            derivation.write_text("derivation", encoding="utf-8")
            tool.write_text("tool", encoding="utf-8")
            mlir_opt.write_text("mlir-opt", encoding="utf-8")
            mlir_runner.write_text("mlir-runner", encoding="utf-8")
            report_path = root / "probe.json"
            report = self._probe_report(stage, derivation, tool, mlir_opt, mlir_runner)
            for modifier, diagnostic in (
                (lambda value: value.__setitem__("sha256", "0" * 64), "probe_self_hash"),
                (lambda value: value["cases"].append(dict(value["cases"][0])), "probe_case_duplicate"),
                (lambda value: value["cases"].append({"id": "extra", "status": "ok", "output": {}}), "probe_case_set"),
                (lambda value: value["cases"].pop(), "probe_case_set"),
                (
                    lambda value: value["cases"][0].pop("compiler_evidence"),
                    "lowered_compiler_evidence:shift_one",
                ),
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


class ExactShiftCompilerExecutorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stage_result = subprocess.run(
            [
                "nix",
                "build",
                "--no-link",
                "--print-out-paths",
                "-L",
                ".#tiny-stories-1m-kev-gpt-exact-torch",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.stage = Path(stage_result.stdout.strip())
        tool = shutil.which("torch-mlir-opt")
        if tool is None:
            raise AssertionError("executor tests require the pinned Nix development environment")
        cls.tool = Path(tool).resolve()
        cls.pipeline = json.loads(DECISION.read_text(encoding="utf-8"))["semantic_regression"][
            "torch_mlir_pipeline"
        ]

    def _run_executor(
        self,
        out: Path,
        *,
        stage: Path | None = None,
        fixture: Path = FIXTURE,
        tool: Path | None = None,
        pipeline: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.assertTrue(EXECUTOR.is_file(), f"missing compiler-backed executor: {EXECUTOR}")
        return subprocess.run(
            [
                str(EXECUTOR),
                "--stage-artifact",
                str(stage or self.stage),
                "--fixture",
                str(fixture),
                "--tool",
                str(tool or self.tool),
                "--pass-pipeline",
                pipeline or self.pipeline,
                "--out",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def _assert_rejected(self, result: subprocess.CompletedProcess[str], diagnostic: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(diagnostic, result.stderr)

    def test_executor_uses_pinned_compilers_and_returns_exact_fixture_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "executor.json"
            result = self._run_executor(out)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            execution = json.loads(out.read_text(encoding="utf-8"))

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(execution["schema"], "tinystories-1m-exact-shift-executor-results-v1")
        self.assertEqual(execution["stage_artifact_sha256"], hashlib.sha256(self.stage.read_bytes()).hexdigest())
        self.assertEqual(execution["fixture_file_sha256"], hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(execution["tool_binary_sha256"], hashlib.sha256(self.tool.read_bytes()).hexdigest())
        self.assertEqual(execution["pipeline_sha256"], MODULE.canonical_sha256(self.pipeline))
        route = execution["compiler_route"]
        self.assertEqual(route["linalg_to_llvm_pipeline"], LINALG_TO_LLVM_PIPELINE)
        self.assertEqual(Path(route["mlir_opt"]["binary"]).name, "mlir-opt")
        self.assertEqual(Path(route["mlir_runner"]["binary"]).name, "mlir-runner")
        for name in ("mlir_opt", "mlir_runner"):
            binary = Path(route[name]["binary"])
            self.assertEqual(route[name]["binary_sha256"], hashlib.sha256(binary.read_bytes()).hexdigest())

        expected_ids = [case["id"] for case in fixture["valid_cases"] + fixture["invalid_cases"]]
        self.assertEqual([case["id"] for case in execution["cases"]], expected_ids)
        by_id = {case["id"]: case for case in execution["cases"]}
        for case in fixture["valid_cases"]:
            record = by_id[case["id"]]
            self.assertEqual(record["status"], "ok")
            self.assertEqual(record["output"], case["expected"])
            self.assertEqual(
                set(record["compiler_evidence"]),
                {
                    "torch_module_sha256",
                    "torch_frontend_output_sha256",
                    "linalg_output_sha256",
                    "native_module_sha256",
                    "runner_stdout_sha256",
                },
            )
        for case in fixture["invalid_cases"]:
            record = by_id[case["id"]]
            self.assertEqual(record["status"], case["status"])
            self.assertEqual(record["diagnostic"], case["diagnostic"])
            self.assertNotIn("output", record)
            self.assertEqual(record["compiler_evidence"]["compiler_exit_code"], 1)

    def test_executor_rejects_detached_stage_altered_tool_or_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            detached_stage = root / "detached.mlir"
            detached_stage.write_text(
                "// torch.aten.bitwise_right_shift.Tensor\nmodule {}\n",
                encoding="utf-8",
            )
            result = self._run_executor(root / "detached.json", stage=detached_stage)
            self._assert_rejected(result, "executor_stage_artifact_hash")

            fake_tool = root / "torch-mlir-opt"
            fake_tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(fake_tool, 0o755)
            result = self._run_executor(root / "tool.json", tool=fake_tool)
            self._assert_rejected(result, "executor_tool_binary_hash")

            result = self._run_executor(root / "pipeline.json", pipeline=self.pipeline + ", canonicalize")
            self._assert_rejected(result, "executor_pipeline")

    def test_executor_rejects_duplicate_extra_or_missing_fixture_cases(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mutations = (
                ("duplicate", lambda value: value["valid_cases"].append(dict(value["valid_cases"][0])), "executor_fixture_case_duplicate"),
                ("extra", lambda value: value["valid_cases"].append({"id": "extra"}), "executor_fixture_case_set"),
                ("missing", lambda value: value["valid_cases"].pop(), "executor_fixture_case_set"),
            )
            for name, mutate, diagnostic in mutations:
                altered = json.loads(json.dumps(fixture))
                mutate(altered)
                altered["sha256"] = MODULE.canonical_sha256(
                    {key: value for key, value in altered.items() if key != "sha256"}
                )
                path = root / f"{name}.json"
                path.write_text(json.dumps(altered), encoding="utf-8")
                result = self._run_executor(root / f"{name}-out.json", fixture=path)
                self._assert_rejected(result, diagnostic)

    def test_producer_is_byte_deterministic_for_the_same_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "probe.json"
            command = [
                "python",
                str(PRODUCER),
                "--executor",
                str(EXECUTOR),
                "--out",
                str(out),
            ]
            first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            first_bytes = out.read_bytes()
            second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(out.read_bytes(), first_bytes)


if __name__ == "__main__":
    unittest.main()
