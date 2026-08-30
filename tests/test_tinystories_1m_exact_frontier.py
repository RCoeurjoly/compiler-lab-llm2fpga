"""Fail-closed tests for the exact TinyStories current-pipeline frontier."""

from __future__ import annotations

import importlib.util
import gzip
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "classify_tinystories_1m_exact_frontier.py"
REPORT = ROOT / "artifacts" / "comparison" / "tinystories-1m-exact-current-pipeline-frontier.json"
SPEC = importlib.util.spec_from_file_location("exact_frontier", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

StageRecord = MODULE.StageRecord
classify_frontier = MODULE.classify_frontier


SHA_A = "a" * 64
SHA_B = "b" * 64
STAGES = [
    "pytorch-exported",
    "torch-mlir",
    "linalg",
    "scf",
    "flat-scf",
    "calyx",
    "calyx-native-sv",
]
TEMP_LOGS = tempfile.TemporaryDirectory(prefix="exact-frontier-tests-")
LOG_SEQUENCE = itertools.count()


def _log(stage: str, text: str) -> tuple[str, int, str]:
    path = Path(TEMP_LOGS.name) / f"{next(LOG_SEQUENCE):04d}-{stage}.log"
    data = text.encode("utf-8")
    path.write_bytes(data)
    return str(path), len(data), hashlib.sha256(data).hexdigest()


def valid(
    stage: str, *, artifact_sha256: str = SHA_A, log_text: str = ""
) -> StageRecord:
    log, log_bytes, log_sha256 = _log(stage, log_text)
    return StageRecord(
        stage=stage,
        status="succeeded",
        artifact=f"/nix/store/example-{stage}/artifact.mlir",
        artifact_bytes=17,
        artifact_sha256=artifact_sha256,
        artifact_accepted=True,
        command=f"build {stage}",
        tool_revisions={"tool": f"{stage}-revision"},
        log=log,
        log_sha256=log_sha256,
        log_bytes=log_bytes,
        terminal_diagnostics=(),
        upstream_identity="upstream-sha256",
        exit_code=0,
    )


def invalid(
    stage: str,
    diagnostic: str,
    *,
    status: str = "compiler_failure",
    supplied_diagnostics: tuple[str, ...] | None = None,
) -> StageRecord:
    log, log_bytes, log_sha256 = _log(stage, diagnostic + "\n")
    return StageRecord(
        stage=stage,
        status=status,
        artifact=f"/nix/store/example-{stage}/rejected-partial.mlir",
        artifact_bytes=11,
        artifact_sha256=SHA_B,
        artifact_accepted=False,
        command=f"build {stage}",
        tool_revisions={"tool": f"{stage}-revision"},
        log=log,
        log_sha256=log_sha256,
        log_bytes=log_bytes,
        terminal_diagnostics=(diagnostic,) if supplied_diagnostics is None else supplied_diagnostics,
        upstream_identity="upstream-sha256",
        exit_code=1,
    )


def prefix_to_invalid(stage: str, diagnostic: str, **kwargs: object) -> list[StageRecord]:
    position = STAGES.index(stage)
    return [valid(name) for name in STAGES[:position]] + [
        invalid(stage, diagnostic, **kwargs)
    ]


class ExactFrontierClassifierTest(unittest.TestCase):
    def test_classifier_reports_the_earliest_invalid_stage(self) -> None:
        result = classify_frontier(
            prefix_to_invalid("calyx", "Unhandled operation during BuildOpGroups(): math.exp")
        )

        self.assertEqual(result.status, "compiler_frontier")
        self.assertEqual(result.frontier, "calyx_frontier")
        self.assertEqual(result.stage, "calyx")
        self.assertIn("math.exp", result.diagnostic)

    def test_classifier_rejects_records_after_the_first_invalid_stage(self) -> None:
        records = prefix_to_invalid("calyx", "Unhandled operation: math.exp")
        records.append(invalid("calyx-native-sv", "cascade"))

        with self.assertRaisesRegex(ValueError, "end at the first invalid"):
            classify_frontier(records)

    def test_classifier_rejects_records_out_of_causal_order(self) -> None:
        # Catches calling a later stage "earliest" from a reordered receipt.
        with self.assertRaisesRegex(ValueError, "contiguous prefix"):
            classify_frontier([valid("pytorch-exported"), invalid("linalg", "earlier")])

    def test_classifier_rejects_isolated_later_stage_without_prior_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "contiguous prefix"):
            classify_frontier([invalid("calyx", "Unhandled operation: math.exp")])

    def test_successful_stage_requires_all_evidence_bindings(self) -> None:
        # Catches fail-open validation when a successful stage lacks evidence.
        required_fields = {
            "artifact": "",
            "artifact_bytes": 0,
            "artifact_sha256": "not-a-sha",
            "artifact_accepted": False,
            "command": "",
            "tool_revisions": {},
            "log": "",
            "log_sha256": "not-a-sha",
            "log_bytes": 1,
            "upstream_identity": "",
            "exit_code": 3,
        }
        for field, missing in required_fields.items():
            with self.subTest(field=field):
                record = valid("pytorch-exported")
                record = StageRecord(**{**record.__dict__, field: missing})
                with self.assertRaisesRegex(ValueError, field):
                    classify_frontier([record])

    def test_zero_exit_partial_calyx_output_with_diagnostic_is_rejected(self) -> None:
        # Catches trusting caller diagnostics or exit code over the actual log.
        log, log_bytes, log_sha256 = _log(
            "calyx", "Unhandled operation during BuildOpGroups(): math.exp\n"
        )
        record = StageRecord(
            **{
                **valid("calyx").__dict__,
                "artifact_accepted": False,
                "log": log,
                "log_bytes": log_bytes,
                "log_sha256": log_sha256,
                "terminal_diagnostics": (),
            }
        )

        result = classify_frontier([valid(name) for name in STAGES[:5]] + [record])

        self.assertEqual(result.status, "compiler_frontier")
        self.assertEqual(result.frontier, "calyx_frontier")
        self.assertIn("math.exp", result.diagnostic)

    def test_classifier_hashes_the_actual_log(self) -> None:
        record = invalid(
            "torch-mlir",
            "error: failed to legalize operation 'torch.operator'",
            supplied_diagnostics=(),
        )
        record = StageRecord(**{**record.__dict__, "log_sha256": SHA_A})

        with self.assertRaisesRegex(ValueError, "log_sha256.*actual log"):
            classify_frontier([valid("pytorch-exported"), record])

    def test_classifier_rejects_log_size_mismatch(self) -> None:
        record = valid("pytorch-exported")
        record = StageRecord(**{**record.__dict__, "log_bytes": 7})

        with self.assertRaisesRegex(ValueError, "log_bytes.*actual log"):
            classify_frontier([record])

    def test_caller_diagnostic_cannot_substitute_for_a_clean_failure_log(self) -> None:
        record = invalid("torch-mlir", "claimed compiler failure")
        clean_log, log_bytes, log_sha256 = _log("torch-mlir", "ordinary progress\n")
        record = StageRecord(
            **{
                **record.__dict__,
                "log": clean_log,
                "log_bytes": log_bytes,
                "log_sha256": log_sha256,
            }
        )

        with self.assertRaisesRegex(ValueError, "actual log contains no terminal diagnostic"):
            classify_frontier([valid("pytorch-exported"), record])

    def test_diagnosed_output_cannot_be_marked_accepted(self) -> None:
        # Catches contradictory receipts that promote a partial failed output.
        record = StageRecord(
            **{
                **invalid("calyx", "Unhandled operation: math.exp").__dict__,
                "artifact_accepted": True,
                "exit_code": 0,
            }
        )

        with self.assertRaisesRegex(ValueError, "artifact_accepted"):
            classify_frontier(prefix_to_invalid("calyx", "Unhandled operation: math.exp")[:-1] + [record])

    def test_environment_failure_is_not_reported_as_compiler_frontier(self) -> None:
        # Catches misclassifying Nix/store/network failures as compiler gaps.
        record = invalid(
            "torch-mlir",
            "error: failed to download substitute",
            status="environment_failure",
            supplied_diagnostics=(),
        )

        result = classify_frontier([valid("pytorch-exported"), record])

        self.assertEqual(result.status, "environment_failure")
        self.assertIsNone(result.frontier)
        self.assertEqual(result.stage, "torch-mlir")

    def test_stage_names_map_to_the_spec_frontiers(self) -> None:
        # Catches drift between registered stage names and the design's labels.
        expected = {
            "pytorch-exported": "export_frontier",
            "torch-mlir": "torch_mlir_frontier",
            "linalg": "pre_calyx_frontier",
            "scf": "pre_calyx_frontier",
            "flat-scf": "pre_calyx_frontier",
            "calyx": "calyx_frontier",
            "calyx-native-sv": "sv_frontier",
        }
        for stage, frontier in expected.items():
            with self.subTest(stage=stage):
                diagnostic = "error: compiler failure"
                self.assertEqual(
                    classify_frontier(prefix_to_invalid(stage, diagnostic)).frontier,
                    frontier,
                )

    def test_all_valid_stages_have_no_frontier(self) -> None:
        result = classify_frontier([valid(stage) for stage in STAGES])

        self.assertEqual(result.status, "complete")
        self.assertIsNone(result.frontier)
        self.assertIsNone(result.stage)
        self.assertIsNone(result.diagnostic)

    def test_incomplete_successful_prefix_is_not_complete(self) -> None:
        with self.assertRaisesRegex(ValueError, "incomplete successful prefix"):
            classify_frontier([valid("pytorch-exported"), valid("torch-mlir")])


class PipelineSourceAuthenticationTest(unittest.TestCase):
    @staticmethod
    def _result(command: list[str], returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    def test_dirty_critical_pipeline_input_is_rejected(self) -> None:
        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if command[:3] == ["git", "rev-parse", "HEAD"]:
                return self._result(command, stdout="evidence\n")
            if command[:3] == ["git", "merge-base", "--is-ancestor"]:
                return self._result(command)
            if command[:3] == ["git", "status", "--porcelain"]:
                return self._result(command, stdout=" M flake.nix\n")
            raise AssertionError(f"unexpected command after dirty input: {command}")

        with mock.patch.object(MODULE, "_CRITICAL_PIPELINE_INPUTS", ("flake.nix",)), mock.patch.object(
            MODULE, "_run", side_effect=fake_run
        ):
            with self.assertRaisesRegex(RuntimeError, "critical pipeline inputs are dirty"):
                MODULE._authenticate_pipeline_source(
                    ROOT, {"input_sources": []}, {"input_sources": []}
                )

    def test_pipeline_input_mutated_since_task4_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-source-auth-") as temporary:
            repo = Path(temporary) / "repo"
            archive = Path(temporary) / "archive"
            repo.mkdir()
            archive.mkdir()
            (repo / "flake.nix").write_bytes(b"mutated")
            (archive / "flake.nix").write_bytes(b"accepted")

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[:3] == ["git", "rev-parse", "HEAD"]:
                    return self._result(command, stdout="evidence\n")
                if command[:3] == ["git", "merge-base", "--is-ancestor"]:
                    return self._result(command)
                if command[:3] == ["git", "status", "--porcelain"]:
                    return self._result(command)
                if command[:3] == ["nix", "flake", "archive"]:
                    return self._result(command, stdout=json.dumps({"path": str(archive)}))
                if command[:3] == ["nix", "hash", "path"]:
                    return self._result(command, stdout="sha256-example=\n")
                raise AssertionError(f"unexpected command before byte rejection: {command}")

            with mock.patch.object(MODULE, "_CRITICAL_PIPELINE_INPUTS", ("flake.nix",)), mock.patch.object(
                MODULE, "_run", side_effect=fake_run
            ), mock.patch.object(MODULE, "_git_bytes", return_value=b"accepted"):
                with self.assertRaisesRegex(RuntimeError, "mutated since Task 4"):
                    MODULE._authenticate_pipeline_source(
                        repo, {"input_sources": []}, {"input_sources": []}
                    )


class ExactFrontierReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_receipt_is_self_hashed_and_names_only_the_first_frontier(self) -> None:
        unsigned = {key: value for key, value in self.report.items() if key != "sha256"}
        expected = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        self.assertEqual(self.report["sha256"], expected)
        self.assertEqual(self.report["frontier"], "torch_mlir_frontier")
        self.assertEqual(self.report["stage"], "torch-mlir")
        self.assertTrue(self.report["pipeline_execution"]["stopped_after_first_invalid_stage"])
        self.assertEqual(
            self.report["pipeline_execution"]["not_run"],
            ["linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"],
        )

    def test_every_record_binds_artifact_command_tools_log_and_upstream(self) -> None:
        self.assertEqual(
            [record["stage"] for record in self.report["stages"]],
            ["pytorch-exported", "torch-mlir"],
        )
        for record in self.report["stages"]:
            self.assertGreater(record["artifact_bytes"], 0)
            self.assertRegex(record["artifact_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["command"])
            self.assertTrue(record["tool_revisions"])
            self.assertTrue(record["log"])
            self.assertRegex(record["log_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["upstream_identity"])
        self.assertTrue(self.report["stages"][0]["artifact_accepted"])
        self.assertFalse(self.report["stages"][1]["artifact_accepted"])

    def test_receipt_proves_task4_ancestry_and_evaluated_source_bytes(self) -> None:
        source = self.report["pipeline_source_identity"]
        self.assertEqual(
            source["accepted_task4_commit"],
            "7eed3592a661c0cb3c417dc59b29839266446b2d",
        )
        self.assertNotEqual(
            source["evidence_source_commit"], source["accepted_task4_commit"]
        )
        self.assertTrue(source["task4_is_ancestor"])
        self.assertTrue(source["critical_inputs_clean"])
        self.assertRegex(source["flake_archive_nar_hash"], r"^sha256-")
        required = {
            "flake.nix",
            "flake.lock",
            "nix/models.nix",
            "nix/pipeline.nix",
            "scripts/compile-pytorch.py",
            "scripts/materialize-pytorch-exported.py",
            "TinyStories/model_adapter_exact_package.py",
            "artifacts/reference/tinystories-1m-exact-input-contract.json",
            "artifacts/reference/tinystories-1m-exact-input-audit.json",
            "artifacts/reference/tinystories-1m-exact-package-model.json",
            "artifacts/reference/tinystories-1m-exact-generation.json",
        }
        self.assertTrue(required.issubset(source["critical_inputs"]))
        for path in required:
            binding = source["critical_inputs"][path]
            self.assertRegex(binding["workspace_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(binding["workspace_sha256"], binding["task4_sha256"])
            self.assertEqual(binding["workspace_sha256"], binding["flake_archive_sha256"])
            self.assertRegex(binding["task4_blob"], r"^[0-9a-f]{40,64}$")

    def test_registered_builds_were_invoked_in_this_run(self) -> None:
        execution = self.report["registered_build_execution"]
        export = execution["pytorch-exported"]
        torch = execution["torch-mlir"]
        self.assertTrue(export["invoked"])
        self.assertTrue(torch["invoked"])
        self.assertEqual(export["exit_code"], 0)
        self.assertNotEqual(torch["exit_code"], 0)
        self.assertIn("nix build", export["command"])
        self.assertIn("nix build", torch["command"])
        for run in (export, torch):
            log = ROOT / run["log"]
            self.assertEqual(log.stat().st_size, run["log_bytes"])
            self.assertEqual(hashlib.sha256(log.read_bytes()).hexdigest(), run["log_sha256"])
            self.assertRegex(run["derivation_json_sha256"], r"^[0-9a-f]{64}$")

    def test_full_capture_and_reproducer_hashes_are_bound(self) -> None:
        archive = ROOT / self.report["full_failing_ir"]["archive"]
        reproducer = ROOT / self.report["minimal_reproducer"]["path"]
        self.assertEqual(
            hashlib.sha256(archive.read_bytes()).hexdigest(),
            self.report["full_failing_ir"]["archive_sha256"],
        )
        with gzip.open(archive, "rb") as stream:
            full = stream.read()
        self.assertEqual(len(full), self.report["full_failing_ir"]["content_bytes"])
        self.assertEqual(
            hashlib.sha256(full).hexdigest(),
            self.report["full_failing_ir"]["content_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(reproducer.read_bytes()).hexdigest(),
            self.report["minimal_reproducer"]["sha256"],
        )
        capture = self.report["compiler_import_capture"]
        self.assertTrue(capture["executed"])
        self.assertNotEqual(capture["exit_code"], 0)
        self.assertEqual(capture["export_sha256"], self.report["stages"][0]["artifact_sha256"])
        self.assertEqual(capture["produced_ir_sha256"], self.report["full_failing_ir"]["content_sha256"])
        self.assertEqual(capture["produced_ir_bytes"], self.report["full_failing_ir"]["content_bytes"])
        capture_log = ROOT / capture["log"]
        self.assertEqual(hashlib.sha256(capture_log.read_bytes()).hexdigest(), capture["log_sha256"])
        self.assertRegex(capture["compile_script_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(capture["torch_mlir_opt_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("torchdynamo-export-to-torch-backend-pipeline", capture["pass_pipeline"])

    def test_receipt_claims_no_downstream_success_or_pipeline_change(self) -> None:
        self.assertTrue(all(value is False for value in self.report["claims"].values()))


if __name__ == "__main__":
    unittest.main()
