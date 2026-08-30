"""Fail-closed tests for the exact TinyStories current-pipeline frontier."""

from __future__ import annotations

import importlib.util
import gzip
import hashlib
import json
import sys
import unittest
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


def valid(stage: str, *, artifact_sha256: str = SHA_A) -> StageRecord:
    return StageRecord(
        stage=stage,
        status="succeeded",
        artifact=f"/nix/store/example-{stage}/artifact.mlir",
        artifact_bytes=17,
        artifact_sha256=artifact_sha256,
        artifact_accepted=True,
        command=f"build {stage}",
        tool_revisions={"tool": f"{stage}-revision"},
        log=f"logs/{stage}.log",
        log_sha256=SHA_B,
        log_bytes=0,
        terminal_diagnostics=(),
        upstream_identity="upstream-sha256",
        exit_code=0,
    )


def invalid(stage: str, diagnostic: str) -> StageRecord:
    return StageRecord(
        stage=stage,
        status="compiler_failure",
        artifact=f"/nix/store/example-{stage}/rejected-partial.mlir",
        artifact_bytes=11,
        artifact_sha256=SHA_B,
        artifact_accepted=False,
        command=f"build {stage}",
        tool_revisions={"tool": f"{stage}-revision"},
        log=f"logs/{stage}.log",
        log_sha256=SHA_A,
        log_bytes=31,
        terminal_diagnostics=(diagnostic,),
        upstream_identity="upstream-sha256",
        exit_code=1,
    )


class ExactFrontierClassifierTest(unittest.TestCase):
    def test_classifier_reports_the_earliest_invalid_stage(self) -> None:
        # Catches classifiers that overwrite the causal Calyx failure with the
        # later SV cascade.
        result = classify_frontier(
            [valid("torch_mlir"), invalid("calyx", "math.exp"), invalid("sv", "cascade")]
        )

        self.assertEqual(result.status, "compiler_frontier")
        self.assertEqual(result.frontier, "calyx_frontier")
        self.assertEqual(result.stage, "calyx")
        self.assertEqual(result.diagnostic, "math.exp")

    def test_classifier_rejects_records_out_of_causal_order(self) -> None:
        # Catches calling a later stage "earliest" from a reordered receipt.
        with self.assertRaisesRegex(ValueError, "causal order"):
            classify_frontier([valid("calyx"), invalid("torch-mlir", "earlier")])

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
            "log_sha256": "",
            "upstream_identity": "",
            "exit_code": 3,
        }
        for field, missing in required_fields.items():
            with self.subTest(field=field):
                record = valid("linalg")
                record = StageRecord(**{**record.__dict__, field: missing})
                with self.assertRaisesRegex(ValueError, field):
                    classify_frontier([record])

    def test_zero_exit_partial_calyx_output_with_diagnostic_is_rejected(self) -> None:
        # Catches trusting exit code/output presence over terminal diagnostics.
        record = StageRecord(
            **{
                **valid("calyx").__dict__,
                "artifact_accepted": False,
                "terminal_diagnostics": (
                    "Unhandled operation during BuildOpGroups(): math.exp",
                ),
            }
        )

        result = classify_frontier([record])

        self.assertEqual(result.status, "compiler_frontier")
        self.assertEqual(result.frontier, "calyx_frontier")
        self.assertIn("math.exp", result.diagnostic)

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
            classify_frontier([record])

    def test_environment_failure_is_not_reported_as_compiler_frontier(self) -> None:
        # Catches misclassifying Nix/store/network failures as compiler gaps.
        record = StageRecord(
            **{
                **invalid("torch-mlir", "failed to download substitute").__dict__,
                "status": "environment_failure",
            }
        )

        result = classify_frontier([record])

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
                self.assertEqual(classify_frontier([invalid(stage, "failure")]).frontier, frontier)

    def test_all_valid_stages_have_no_frontier(self) -> None:
        # Catches inventing a frontier when all supplied stage records validate.
        result = classify_frontier(
            [valid("pytorch-exported"), valid("torch-mlir"), valid("linalg")]
        )

        self.assertEqual(result.status, "complete")
        self.assertIsNone(result.frontier)
        self.assertIsNone(result.stage)
        self.assertIsNone(result.diagnostic)


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

    def test_receipt_claims_no_downstream_success_or_pipeline_change(self) -> None:
        self.assertTrue(all(value is False for value in self.report["claims"].values()))


if __name__ == "__main__":
    unittest.main()
