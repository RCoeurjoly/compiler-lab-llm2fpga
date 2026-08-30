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
import shlex
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
    "torch",
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
            "torch",
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
        self.assertEqual(result.stage, "torch")

    def test_stage_names_map_to_the_spec_frontiers(self) -> None:
        # Catches drift between registered stage names and the design's labels.
        expected = {
            "pytorch-exported": "export_frontier",
            "torch": "torch_mlir_frontier",
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
            classify_frontier([valid("pytorch-exported"), valid("torch")])


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


class AuthenticatedPipelineRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="exact-scf-result-union-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.linalg_input = root / "input.linalg.mlir"
        self.linalg_input.write_text("module {}\n", encoding="utf-8")
        self.unavailable_scf_output = root / "scf-output"
        self.unavailable_scf_output.mkdir()
        (self.unavailable_scf_output / "manifest.json").write_text(
            '{"reason":"no direct SCF route","stage":"scf","status":"unavailable"}\n',
            encoding="utf-8",
        )
        self.scf_log = root / "scf-control.log"
        self.scf_log.write_text("registered control output\n", encoding="utf-8")
        self.nonzero_scf_log = root / "scf-compiler.log"
        self.nonzero_scf_log.write_text(
            "error: failed to legalize operation 'scf.for' : (index) -> ()\n",
            encoding="utf-8",
        )
        self.no_output_path = root / "no-output"

    def test_exact_runner_selects_registered_linalg_no_handshake_alias(self) -> None:
        model = "tiny-stories-1m-kev-gpt-exact"
        self.assertEqual(
            MODULE._registered_attribute(model, "pytorch-exported"),
            "tiny-stories-1m-kev-gpt-exact-pytorch-exported",
        )
        for stage in (
            "torch",
            "linalg",
            "scf",
            "flat-scf",
            "calyx",
            "calyx-native-sv",
        ):
            self.assertEqual(
                MODULE._registered_attribute(model, stage),
                f"tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-{stage}",
            )

    def test_zero_exit_unavailable_manifest_returns_control_manifest_failure(self) -> None:
        result = MODULE._classify_registered_result(
            stage="scf",
            exit_code=0,
            output=self.unavailable_scf_output,
            upstream_input=self.linalg_input,
            log=self.scf_log,
        )
        self.assertIsInstance(result, MODULE.ControlManifestFailure)
        self.assertEqual(result.kind, "control_manifest")
        self.assertEqual(result.manifest, self.unavailable_scf_output / "manifest.json")
        self.assertEqual(result.upstream_input, self.linalg_input)

    def test_nonzero_scf_failure_returns_compiler_failure_without_manifest(self) -> None:
        result = MODULE._classify_registered_result(
            stage="scf",
            exit_code=1,
            output=self.no_output_path,
            upstream_input=self.linalg_input,
            log=self.nonzero_scf_log,
        )
        self.assertIsInstance(result, MODULE.CompilerFailure)
        self.assertEqual(result.kind, "compiler_failure")
        self.assertEqual(result.upstream_input, self.linalg_input)
        self.assertEqual(result.log, self.nonzero_scf_log)
        self.assertFalse(hasattr(result, "manifest"))

    def test_nonzero_scf_failure_preserves_full_diagnostic_and_optional_operation_types(self) -> None:
        identified = MODULE._classify_registered_result(
            stage="scf",
            exit_code=1,
            output=self.no_output_path,
            upstream_input=self.linalg_input,
            log=self.nonzero_scf_log,
        )
        self.assertEqual(
            identified.diagnostic,
            "error: failed to legalize operation 'scf.for' : (index) -> ()",
        )
        self.assertEqual(identified.operation, "scf.for")
        self.assertEqual(identified.types, "(index) -> ()")
        anonymous_log = Path(self.temporary.name) / "anonymous.log"
        anonymous_log.write_text("error: compiler terminated\n", encoding="utf-8")
        anonymous = MODULE._classify_registered_result(
            stage="scf",
            exit_code=2,
            output=self.no_output_path,
            upstream_input=self.linalg_input,
            log=anonymous_log,
        )
        self.assertIsNone(anonymous.operation)
        self.assertIsNone(anonymous.types)

    def test_control_manifest_frontier_evidence_uses_exact_union_contract(self) -> None:
        result = MODULE._classify_registered_result(
            stage="scf",
            exit_code=0,
            output=self.unavailable_scf_output,
            upstream_input=self.linalg_input,
            log=self.scf_log,
        )
        manifest = result.manifest.read_bytes()

        evidence = MODULE._serialize_frontier_evidence(
            stage="scf",
            result=result,
            canonical_root="reproducers/scf",
            manifest_binding={
                "path": "reproducers/scf/minimal-reproducer.json",
                "bytes": len(manifest),
                "sha256": hashlib.sha256(manifest).hexdigest(),
            },
        )

        self.assertEqual(evidence["kind"], "control_manifest")
        self.assertEqual(evidence["operation"], None)
        self.assertEqual(evidence["types"], None)
        self.assertEqual(
            evidence["minimization"],
            {"status": "not_applicable", "reason": "control_manifest_is_minimal"},
        )
        self.assertEqual(evidence["manifest"]["stage"], "scf")
        self.assertEqual(evidence["manifest"]["status"], "unavailable")
        self.assertEqual(evidence["manifest"]["reason"], "no direct SCF route")

    def test_compiler_failure_frontier_evidence_has_no_manifest_and_binds_attempt(self) -> None:
        result = MODULE._classify_registered_result(
            stage="scf",
            exit_code=1,
            output=self.no_output_path,
            upstream_input=self.linalg_input,
            log=self.nonzero_scf_log,
        )
        interestingness = {
            "test": {"path": "reproducers/scf/interestingness-test.sh", "bytes": 17, "sha256": SHA_A},
            "full_log": {"path": "reproducers/scf/interesting-full.log", "bytes": 19, "sha256": SHA_B},
        }
        minimization = {
            "status": "not_practical",
            "reason": "mlir_reduce_unavailable",
            "reduction_log": {"path": "reproducers/scf/reduction.log", "bytes": 21, "sha256": SHA_A},
        }

        evidence = MODULE._serialize_frontier_evidence(
            stage="scf",
            result=result,
            canonical_root="reproducers/scf",
            interestingness=interestingness,
            minimization=minimization,
        )

        self.assertEqual(evidence["kind"], "compiler_failure")
        self.assertIsNone(evidence["manifest"])
        self.assertEqual(evidence["operation"], "scf.for")
        self.assertEqual(evidence["types"], "(index) -> ()")
        self.assertEqual(evidence["interestingness"], interestingness)
        self.assertEqual(evidence["minimization"], minimization)

    def test_interestingness_script_substitutes_candidate_and_matches_exact_failure(self) -> None:
        compiler = Path(self.temporary.name) / "compiler.sh"
        compiler.write_text(
            "#!/bin/sh\n"
            "if grep -q INTERESTING \"$1\"; then\n"
            "  echo \"error: failed to legalize operation 'scf.for' : (index) -> ()\" >&2\n"
            "  exit 7\n"
            "fi\n"
            "echo \"error: unrelated failure\" >&2\n"
            "exit 3\n",
            encoding="utf-8",
        )
        compiler.chmod(0o755)
        original = Path(self.temporary.name) / "original.mlir"
        original.write_text("ORIGINAL\n", encoding="utf-8")
        interesting = Path(self.temporary.name) / "interesting.mlir"
        interesting.write_text("INTERESTING\nscf.for : (index) -> ()\n", encoding="utf-8")
        boring = Path(self.temporary.name) / "boring.mlir"
        boring.write_text("BORING\n", encoding="utf-8")
        script = Path(self.temporary.name) / "interestingness-test.sh"
        build_command = (
            f"{shlex.quote(str(compiler))} {shlex.quote(str(original))} \"$out\""
        )

        MODULE._write_interestingness_test(
            script,
            build_command=build_command,
            upstream_input=original,
            expected_exit=7,
            expected_diagnostic="error: failed to legalize operation 'scf.for' : (index) -> ()",
            operation="scf.for",
            types="(index) -> ()",
        )

        accepted = subprocess.run([str(script), str(interesting)], capture_output=True, text=True)
        rejected = subprocess.run([str(script), str(boring)], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(str(interesting), accepted.stdout + accepted.stderr)
        self.assertNotIn(str(original), script.read_text(encoding="utf-8"))

    def test_export_provenance_manifest_is_not_a_control_stage_status(self) -> None:
        # Catches rejecting a valid export because its provenance schema has no status.
        with tempfile.TemporaryDirectory(prefix="exact-export-manifest-") as temporary:
            output = Path(temporary)
            (output / "manifest.json").write_text(
                '{"stage":"pytorch-exported","files":{"serialized":"exported.pt2"}}\n',
                encoding="utf-8",
            )

            manifest, diagnostic = MODULE._manifest_diagnostic(
                "pytorch-exported", output
            )

        self.assertIsNone(manifest)
        self.assertIsNone(diagnostic)

    def test_semantic_verifier_is_the_first_pipeline_action(self) -> None:
        # Catches any registered build or derivation lookup before Task 2 is replayed.
        commands: list[list[str]] = []

        def stop_after_first(command: list[str], **_: object) -> object:
            commands.append(command)
            raise RuntimeError("semantic gate sentinel")

        with mock.patch.object(MODULE, "_run", side_effect=stop_after_first):
            with self.assertRaisesRegex(RuntimeError, "semantic gate sentinel"):
                MODULE.build_current_frontier_receipt(
                    ROOT, "tiny-stories-1m-kev-gpt-exact"
                )

        self.assertEqual(
            commands,
            [[
                "nix",
                "develop",
                "-c",
                "python",
                "scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py",
                "--probe-report",
                "artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json",
            ]],
        )

    def test_registered_pipeline_stops_immediately_after_first_invalid_stage(self) -> None:
        # Catches a cascading Linalg failure being followed by SCF or backend builds.
        visited: list[str] = []

        def execute(stage: str, upstream: StageRecord | None) -> StageRecord:
            visited.append(stage)
            if stage == "linalg":
                return invalid("linalg", "error: linalg frontier")
            return valid(stage)

        records = MODULE._run_registered_pipeline(execute)

        self.assertEqual(visited, ["pytorch-exported", "torch", "linalg"])
        self.assertEqual([record.stage for record in records], visited)
        self.assertFalse(records[-1].artifact_accepted)

    def test_alias_prefix_hash_mismatch_is_rejected_before_scf(self) -> None:
        authenticated = {
            "torch": "e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674",
            "linalg": "f4792aef4a0054386bf4e9e6399cc107e6d947b4d608e97e6041ccdf2ffb59c8",
        }
        model = "tiny-stories-1m-kev-gpt-exact"
        for mutated_stage in ("torch", "linalg"):
            with self.subTest(mutated_stage=mutated_stage):
                trusted = {**authenticated, mutated_stage: "0" * 64}
                visited: list[str] = []
                alias_attributes: list[str] = []

                def execute(stage: str, upstream: StageRecord | None) -> StageRecord:
                    visited.append(stage)
                    if stage in authenticated:
                        alias_attributes.append(MODULE._registered_attribute(model, stage))
                    return valid(stage, artifact_sha256=authenticated.get(stage, SHA_A))

                with mock.patch.object(
                    MODULE,
                    "_AUTHENTICATED_DIRECT_STAGE_SHA256",
                    trusted,
                ):
                    with self.assertRaisesRegex(RuntimeError, "authenticated alias prefix"):
                        MODULE._run_registered_pipeline(execute)

                self.assertEqual(
                    alias_attributes,
                    [
                        "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-torch",
                        "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-linalg",
                    ],
                )
                self.assertNotIn("scf", visited)

    def test_two_capture_bundles_must_be_byte_identical(self) -> None:
        # Catches comparing only receipt fields while logs or failing inputs differ.
        with tempfile.TemporaryDirectory(prefix="exact-frontier-bundles-") as temporary:
            root = Path(temporary)
            first = root / "run-1"
            second = root / "run-2"
            first.mkdir()
            second.mkdir()
            for directory in (first, second):
                (directory / "receipt.json").write_bytes(b'{"same":true}\n')
                (directory / "stage.log").write_bytes(b"error: same\n")

            MODULE._require_byte_identical_bundles(
                first, second, ("receipt.json", "stage.log")
            )
            (second / "stage.log").write_bytes(b"error: changed\n")
            with self.assertRaisesRegex(RuntimeError, "stage.log"):
                MODULE._require_byte_identical_bundles(
                    first, second, ("receipt.json", "stage.log")
                )


class CanonicalCaptureNormalizationTest(unittest.TestCase):
    @staticmethod
    def _evidence(
        capture_root: str, diagnostic: str
    ) -> tuple[str, bytes]:
        command = [
            "/nix/store/python-env/bin/python",
            "/nix/store/compile-pytorch.py",
            "--exported-program-dir",
            "/nix/store/exact-export",
            "--out",
            f"{capture_root}/requested-torch.mlir",
        ]
        result = subprocess.CompletedProcess(
            command,
            1,
            "",
            (
                'loc("/build/exact-adapter/model.py":879:0): error: '
                f"{diagnostic}\n"
                "For Torch-MLIR developers, reproduce with:\n"
                f"$ /nix/store/torch-mlir-opt {capture_root}/UnnammedModule.mlir\n"
            ),
        )
        return MODULE._canonical_execution_evidence(
            command, result, {capture_root: "<capture-tmp>"}
        )

    def test_two_capture_roots_have_identical_canonical_inputs_and_hash(self) -> None:
        first_command, first_log = self._evidence(
            "/tmp/nix-shell.first/capture-a", "failed to legalize torch.operator"
        )
        second_command, second_log = self._evidence(
            "/tmp/nix-shell.second/capture-b", "failed to legalize torch.operator"
        )

        self.assertEqual(first_command, second_command)
        self.assertEqual(first_log, second_log)
        self.assertEqual(hashlib.sha256(first_log).hexdigest(), hashlib.sha256(second_log).hexdigest())
        self.assertIn("<capture-tmp>/requested-torch.mlir", first_command)
        self.assertIn('/build/exact-adapter/model.py', first_log.decode())
        self.assertIn('/nix/store/torch-mlir-opt', first_log.decode())

    def test_substantive_diagnostic_mutation_changes_canonical_log_hash(self) -> None:
        _, original = self._evidence(
            "/tmp/nix-shell.first/capture-a", "failed to legalize torch.operator"
        )
        _, mutated = self._evidence(
            "/tmp/nix-shell.second/capture-b", "failed to legalize torch.fake_operator"
        )

        self.assertNotEqual(original, mutated)
        self.assertNotEqual(
            hashlib.sha256(original).hexdigest(), hashlib.sha256(mutated).hexdigest()
        )

    def test_cached_and_fresh_nix_progress_produce_identical_evidence(self) -> None:
        # Catches cache state leaking into otherwise identical stage bundles.
        command = ["nix", "build", "--no-link", "--print-out-paths", ".#stage"]
        cached = subprocess.CompletedProcess(command, 0, "/nix/store/result\n", "")
        fresh = subprocess.CompletedProcess(
            command,
            0,
            "/nix/store/result\n",
            (
                "this derivation will be built:\n"
                "  /nix/store/example-stage.drv\n"
                "building '/nix/store/example-stage.drv'...\n"
            ),
        )

        self.assertEqual(
            MODULE._canonical_execution_evidence(command, cached),
            MODULE._canonical_execution_evidence(command, fresh),
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
        self.assertEqual(self.report["frontier"], "pre_calyx_frontier")
        self.assertEqual(self.report["stage"], "scf")
        self.assertTrue(self.report["pipeline_execution"]["stopped_after_first_invalid_stage"])
        self.assertEqual(
            self.report["pipeline_execution"]["not_run"],
            ["flat-scf", "calyx", "calyx-native-sv"],
        )

    def test_every_record_binds_artifact_command_tools_log_and_upstream(self) -> None:
        self.assertEqual(
            [record["stage"] for record in self.report["stages"]],
            ["pytorch-exported", "torch", "linalg", "scf"],
        )
        for record in self.report["stages"]:
            self.assertGreater(record["artifact_bytes"], 0)
            self.assertRegex(record["artifact_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["command"])
            self.assertTrue(record["tool_revisions"])
            self.assertTrue(record["log"])
            self.assertRegex(record["log_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["upstream_identity"])
        self.assertTrue(all(record["artifact_accepted"] for record in self.report["stages"][:-1]))
        self.assertFalse(self.report["stages"][-1]["artifact_accepted"])

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
        self.assertTrue(
            source["flake_archive_source"].endswith(
                f"?rev={source['evidence_source_commit']}"
            )
        )
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
        self.assertEqual(set(execution), {"pytorch-exported", "torch", "linalg", "scf"})
        for stage, run in execution.items():
            self.assertTrue(run["invoked"])
            self.assertEqual(run["exit_code"], 0)
            self.assertIn("nix build", run["command"])
            log = ROOT / run["log"]
            self.assertEqual(log.stat().st_size, run["log_bytes"])
            self.assertEqual(hashlib.sha256(log.read_bytes()).hexdigest(), run["log_sha256"])
            self.assertRegex(run["derivation_json_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(run["artifact_accepted"], stage != "scf")

    def test_full_capture_and_reproducer_hashes_are_bound(self) -> None:
        archive = ROOT / self.report["full_failing_input"]["path"]
        reproducer = ROOT / self.report["minimal_reproducer"]["path"]
        self.assertEqual(
            hashlib.sha256(archive.read_bytes()).hexdigest(),
            self.report["full_failing_input"]["archive_sha256"],
        )
        with gzip.open(archive, "rb") as stream:
            full = stream.read()
        self.assertEqual(len(full), self.report["full_failing_input"]["content_bytes"])
        self.assertEqual(
            hashlib.sha256(full).hexdigest(), self.report["full_failing_input"]["content_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(reproducer.read_bytes()).hexdigest(),
            self.report["minimal_reproducer"]["sha256"],
        )
        self.assertEqual(json.loads(reproducer.read_text(encoding="utf-8"))["status"], "unavailable")
        self.assertTrue(self.report["minimal_reproducer"]["operation_and_types_not_applicable"])

    def test_semantic_gate_and_predecessor_are_bound(self) -> None:
        gate = self.report["semantic_gate"]
        self.assertEqual(gate["status"], "accepted")
        self.assertEqual(gate["evidence"]["semantic_probe"]["status"], "accepted")
        self.assertEqual(gate["evidence"]["registered_stage"]["status"], "accepted")
        self.assertEqual(
            hashlib.sha256((ROOT / gate["probe_report"]).read_bytes()).hexdigest(),
            gate["probe_report_sha256"],
        )
        predecessor = self.report["predecessor_receipt"]
        self.assertEqual(
            predecessor["historical_bundle"],
            "artifacts/comparison/tinystories-1m-exact-frontier-determinism",
        )
        self.assertRegex(predecessor["file_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(predecessor["self_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(self.report["frozen_task_1_through_3_identities"]), 11)

    def test_receipt_claims_no_downstream_success_or_pipeline_change(self) -> None:
        self.assertTrue(all(value is False for value in self.report["claims"].values()))


if __name__ == "__main__":
    unittest.main()
