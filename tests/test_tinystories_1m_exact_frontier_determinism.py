"""Verification tests for preserved live Task 5 determinism bundles."""

from __future__ import annotations

import importlib.util
import copy
import gzip
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "pipeline"
    / "verify_tinystories_1m_exact_frontier_determinism.py"
)
CLASSIFIER_SCRIPT = (
    ROOT / "scripts" / "pipeline" / "classify_tinystories_1m_exact_frontier.py"
)
BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-frontier-determinism"
)
CURRENT_BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-frontier-determinism-scf"
)
SPEC = importlib.util.spec_from_file_location("exact_frontier_determinism", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CLASSIFIER_SPEC = importlib.util.spec_from_file_location(
    "exact_frontier_compiler_fixture", CLASSIFIER_SCRIPT
)
if CLASSIFIER_SPEC is None or CLASSIFIER_SPEC.loader is None:
    raise RuntimeError(f"cannot load {CLASSIFIER_SCRIPT}")
CLASSIFIER = importlib.util.module_from_spec(CLASSIFIER_SPEC)
sys.modules[CLASSIFIER_SPEC.name] = CLASSIFIER
CLASSIFIER_SPEC.loader.exec_module(CLASSIFIER)
SUCCESSOR_SCRIPT = (
    ROOT
    / "scripts"
    / "pipeline"
    / "verify_tinystories_1m_exact_successor_frontier_determinism.py"
)
SUCCESSOR_BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-successor-frontier-determinism"
)
LEFT_SHIFT_SUCCESS_BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-left-shift-success-determinism"
)
FLAT_SCF_BUNDLES = (
    ROOT
    / "artifacts"
    / "comparison"
    / "tinystories-1m-exact-frontier-determinism-flat-scf"
)


class PreservedDeterminismBundleTest(unittest.TestCase):
    def test_current_scf_captures_are_byte_identical_and_self_hashed(self) -> None:
        result = MODULE.verify_determinism_bundles(CURRENT_BUNDLES)

        self.assertEqual(result["runs"], ["run-1", "run-2"])
        self.assertEqual(result["first_invalid_stage"], "scf")
        self.assertTrue(result["byte_identical"])
        self.assertRegex(result["receipt_self_hash"], r"^[0-9a-f]{64}$")

    def test_two_preserved_live_runs_verify_and_compare_byte_identical(self) -> None:
        result = MODULE.verify_determinism_bundles(BUNDLES)

        self.assertEqual(result["source_commit"], "f26177ee480187dd1abf5ee9b1324c61bcceab02")
        self.assertEqual(result["runs"], ["run-1", "run-2"])
        self.assertEqual(
            result["receipt_file_sha256"],
            "b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55",
        )
        self.assertEqual(
            result["receipt_self_hash"],
            "af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b",
        )
        self.assertTrue(result["byte_identical"])

    def test_manifest_marks_timestamps_and_runtime_noncanonical(self) -> None:
        result = MODULE.verify_determinism_bundles(BUNDLES)

        self.assertTrue(result["noncanonical_metadata_present"])

    def test_substantive_mutation_of_preserved_live_log_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-bundle-mutation-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            capture_log = mutated / "run-2" / "compiler-import-capture.log"
            original = capture_log.read_bytes()
            changed = original.replace(b"torch.operator", b"torch.operat0r", 1)
            self.assertNotEqual(original, changed)
            self.assertEqual(len(original), len(changed))
            capture_log.write_bytes(changed)

            with self.assertRaisesRegex(MODULE.VerificationError, "SHA-256"):
                MODULE.verify_determinism_bundles(mutated)


class PublicBundleFilesystemBoundaryTest(unittest.TestCase):
    def test_public_v4_verifier_rejects_unlisted_later_stage_logs_in_both_runs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-extra-log-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(CURRENT_BUNDLES, mutated)
            for run_name in ("run-1", "run-2"):
                (mutated / run_name / "flat-scf.log").write_text(
                    "later stage must not exist\n", encoding="utf-8"
                )

            with self.assertRaisesRegex(MODULE.VerificationError, "run directory contents"):
                MODULE.verify_determinism_bundles(mutated)

    def test_public_verifier_rejects_unlisted_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-extra-artifact-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            (mutated / "run-1" / "flat-scf.mlir").write_text(
                "module {}\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(MODULE.VerificationError, "run directory contents"):
                MODULE.verify_determinism_bundles(mutated)

    def test_public_verifier_rejects_symlinked_canonical_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-symlink-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            target = mutated / "receipt-target.json"
            target.write_bytes((mutated / "run-1" / "receipt.json").read_bytes())
            receipt = mutated / "run-1" / "receipt.json"
            receipt.unlink()
            receipt.symlink_to(target)

            with self.assertRaisesRegex(MODULE.VerificationError, "regular file"):
                MODULE.verify_determinism_bundles(mutated)

    def test_public_verifier_rejects_missing_canonical_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-missing-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            (mutated / "run-2" / "torch-mlir.log").unlink()

            with self.assertRaisesRegex(MODULE.VerificationError, "run directory contents"):
                MODULE.verify_determinism_bundles(mutated)

    def test_public_verifier_rejects_unexpected_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-frontier-subdirectory-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(BUNDLES, mutated)
            (mutated / "run-1" / ".hidden-stage").mkdir()

            with self.assertRaisesRegex(MODULE.VerificationError, "run directory contents"):
                MODULE.verify_determinism_bundles(mutated)


class StrongCurrentReceiptValidationTest(unittest.TestCase):
    """Adversarial checks use self-consistent mutations against independent trust."""

    def setUp(self) -> None:
        run_root = CURRENT_BUNDLES / "run-1"
        self.receipt = json.loads((run_root / "receipt.json").read_text(encoding="utf-8"))
        self.files = {
            path.name: path.read_bytes() for path in run_root.iterdir() if path.is_file()
        }
        classifier = b"classifier-v4-fixture"
        verifier = b"verifier-v4-fixture"
        self.receipt["capture_tools"] = {
            "classifier": {
                "path": "scripts/pipeline/classify_tinystories_1m_exact_frontier.py",
                "sha256": hashlib.sha256(classifier).hexdigest(),
            },
            "determinism_verifier": {
                "path": "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py",
                "sha256": hashlib.sha256(verifier).hexdigest(),
            },
        }
        self.trust = {
            "repo_root": None,
            "capture_tool_paths": {
                "classifier": "scripts/pipeline/classify_tinystories_1m_exact_frontier.py",
                "determinism_verifier": "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py",
            },
            "capture_tool_bytes": {"classifier": classifier, "determinism_verifier": verifier},
            "semantic_gate": copy.deepcopy(self.receipt["semantic_gate"]),
            "identities": copy.deepcopy(self.receipt["frozen_task_1_through_3_identities"]),
            "decision_self_sha256": self.receipt["task_2_decision_self_sha256"],
            "predecessor": copy.deepcopy(self.receipt["predecessor_receipt"]),
            "derivations": {},
        }
        for stage in ("linalg", "scf"):
            drv = f"synthetic-{stage}-drv".encode()
            canonical_json = json.dumps(
                {"derivations": {f"synthetic-{stage}.drv": {"stage": stage}}},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            build_command = f"build exact {stage}"
            tool = f"tool-{stage}".encode()
            tool_bindings = [{
                "path": f"/nix/store/synthetic-{stage}-tool",
                "bytes": len(tool),
                "sha256": hashlib.sha256(tool).hexdigest(),
            }]
            artifact = (
                gzip.decompress(self.files["full-input.gz"])
                if stage == "linalg"
                else self.files["minimal-reproducer.json"]
            )
            live = {
                "path": f"/nix/store/synthetic-{stage}.drv",
                "file_bytes": drv,
                "file_sha256": hashlib.sha256(drv).hexdigest(),
                "canonical_json": canonical_json,
                "json_sha256": hashlib.sha256(canonical_json).hexdigest(),
                "build_command": build_command,
                "build_command_sha256": hashlib.sha256(build_command.encode()).hexdigest(),
                "tool_bindings": tool_bindings,
                "artifact_bytes": artifact,
                "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
                "output": f"/nix/store/synthetic-{stage}-output",
            }
            self.trust["derivations"][stage] = live
            execution = self.receipt["registered_build_execution"][stage]
            execution.update({
                "derivation": live["path"],
                "derivation_file_sha256": live["file_sha256"],
                "derivation_json_sha256": live["json_sha256"],
                "derivation_build_command": live["build_command"],
                "derivation_build_command_sha256": live["build_command_sha256"],
                "derivation_tool_bindings": live["tool_bindings"],
                "captured_derivation_bytes": len(drv),
                "captured_derivation_sha256": live["file_sha256"],
                "captured_derivation_json_bytes": len(canonical_json),
                "captured_derivation_json_sha256": live["json_sha256"],
                "captured_derivation": f"reproducers/scf/{stage}.drv",
                "captured_derivation_json": f"reproducers/scf/{stage}.derivation.json",
                "result": live["output"],
                "artifact": (
                    live["output"] if stage == "linalg" else f"{live['output']}/manifest.json"
                ),
            })
            self.files[f"{stage}.drv"] = drv
            self.files[f"{stage}.derivation.json"] = canonical_json
            record = self.receipt["stages"][[item["stage"] for item in self.receipt["stages"]].index(stage)]
            record["tool_revisions"]["build_command_sha256"] = live["build_command_sha256"]
            record["artifact"] = execution["artifact"]
        self.receipt["full_failing_input"]["source_artifact"] = self.trust["derivations"]["linalg"]["output"]
        self._rehash()
        MODULE._verify_v4_receipt(self.receipt, self.files, self.trust, "fixture")

    def _rehash(self) -> None:
        self.receipt["sha256"] = MODULE._canonical_receipt_hash(self.receipt)
        self.assertEqual(self.receipt["sha256"], MODULE._canonical_receipt_hash(self.receipt))

    def _reject(self, pattern: str) -> None:
        self._rehash()
        with self.assertRaisesRegex(MODULE.VerificationError, pattern):
            MODULE._verify_v4_receipt(self.receipt, self.files, self.trust, "fixture")

    def test_recomputed_self_hash_does_not_rescue_semantic_gate_or_probe_mutation(self) -> None:
        for key in ("status", "probe_report_sha256"):
            with self.subTest(key=key):
                original = self.receipt["semantic_gate"][key]
                self.receipt["semantic_gate"][key] = "mutated"
                self._reject("semantic gate/probe")
                self.receipt["semantic_gate"][key] = original

    def test_recomputed_self_hash_does_not_rescue_identity_or_predecessor_mutation(self) -> None:
        self.receipt["frozen_task_1_through_3_identities"]["task_1_audit_file_sha256"] = "0" * 64
        self._reject("Task 1-3 identity")
        self.receipt["frozen_task_1_through_3_identities"] = copy.deepcopy(self.trust["identities"])
        self.receipt["predecessor_receipt"]["self_sha256"] = "0" * 64
        self._reject("predecessor identity")

    def test_recomputed_self_hash_does_not_rescue_classifier_or_verifier_mutation(self) -> None:
        for name in ("classifier", "determinism_verifier"):
            with self.subTest(name=name):
                original = self.receipt["capture_tools"][name]["sha256"]
                self.receipt["capture_tools"][name]["sha256"] = "0" * 64
                self._reject(f"{name} source-commit-byte hash")
                self.receipt["capture_tools"][name]["sha256"] = original

    def test_recomputed_self_hash_does_not_rescue_derivation_tool_or_command_mutation(self) -> None:
        execution = self.receipt["registered_build_execution"]["linalg"]
        for key in ("derivation_file_sha256", "derivation_build_command", "derivation_tool_bindings"):
            with self.subTest(key=key):
                original = copy.deepcopy(execution[key])
                execution[key] = [] if key.endswith("bindings") else "mutated"
                self._reject("derivation hash|build command|tool binding")
                execution[key] = original

    def test_recomputed_self_hash_does_not_rescue_stage_semantics_mutation(self) -> None:
        scf = self.receipt["stages"][3]
        cases = (("exit_code", 9), ("status", "succeeded"), ("log_sha256", "0" * 64), ("terminal_diagnostics", []))
        for key, value in cases:
            with self.subTest(key=key):
                original = copy.deepcopy(scf[key])
                scf[key] = value
                self._reject("exit mismatch|status mismatch|log hash mismatch|terminal diagnostic")
                scf[key] = original

    def test_recomputed_self_hash_does_not_rescue_execution_acceptance_mutation(self) -> None:
        execution = self.receipt["registered_build_execution"]
        for stage, value in (("pytorch-exported", False), ("scf", True)):
            with self.subTest(stage=stage):
                original = execution[stage]["artifact_accepted"]
                execution[stage]["artifact_accepted"] = value
                self._reject("execution acceptance mismatch")
                execution[stage]["artifact_accepted"] = original

    def test_recomputed_self_hash_does_not_rescue_not_invoked_execution(self) -> None:
        self.receipt["registered_build_execution"]["scf"]["invoked"] = False
        self._reject("SCF execution was not invoked")

    def test_recomputed_self_hash_does_not_rescue_missing_or_extra_execution(self) -> None:
        execution = self.receipt["registered_build_execution"]
        removed = execution.pop("torch")
        self._reject("execution stage set mismatch")
        execution["torch"] = removed
        execution["flat-scf"] = copy.deepcopy(execution["scf"])
        self._reject("execution stage set mismatch")

    def test_recomputed_self_hash_does_not_rescue_execution_sequence_inconsistency(self) -> None:
        self.receipt["stages"][1], self.receipt["stages"][2] = (
            self.receipt["stages"][2],
            self.receipt["stages"][1],
        )
        self._reject("stage sequence mismatch")

    def test_recomputed_self_hash_does_not_rescue_later_canonical_evidence(self) -> None:
        self.files["flat-scf.log"] = b"later stage must not exist\n"
        self._reject("canonical evidence file set mismatch")

    def test_recomputed_self_hash_does_not_rescue_changed_linalg_content(self) -> None:
        content = gzip.decompress(self.files["full-input.gz"]) + b"\nmutated"
        self.files["full-input.gz"] = gzip.compress(content, mtime=0)
        full = self.receipt["full_failing_input"]
        full.update({
            "archive_bytes": len(self.files["full-input.gz"]),
            "archive_sha256": hashlib.sha256(self.files["full-input.gz"]).hexdigest(),
            "content_bytes": len(content),
            "content_sha256": hashlib.sha256(content).hexdigest(),
        })
        self.receipt["stages"][2].update({
            "artifact_bytes": len(content), "artifact_sha256": hashlib.sha256(content).hexdigest()
        })
        self._reject("differ from live derivation output")

    def test_recomputed_self_hash_does_not_rescue_scf_manifest_fields(self) -> None:
        for key in ("stage", "status", "reason"):
            with self.subTest(key=key):
                value = json.loads(self.files["minimal-reproducer.json"])
                value[key] = "mutated"
                data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
                self.files["minimal-reproducer.json"] = data
                self.receipt["minimal_reproducer"].update({
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
                })
                self.receipt["stages"][3].update({
                    "artifact_bytes": len(data), "artifact_sha256": hashlib.sha256(data).hexdigest()
                })
                self._reject("exact SCF manifest")
                self.files["minimal-reproducer.json"] = self.trust["derivations"]["scf"]["artifact_bytes"]


class FrontierEvidenceUnionValidationTest(unittest.TestCase):
    """Branch mutations start from copied bytes of the real SCF capture."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="exact-frontier-union-")
        self.addCleanup(self.temporary.cleanup)
        self.bundle = Path(self.temporary.name) / "bundle"
        shutil.copytree(CURRENT_BUNDLES, self.bundle)
        run_root = self.bundle / "run-1"
        self.receipt = json.loads((run_root / "receipt.json").read_text(encoding="utf-8"))
        self.receipt["schema"] = "tinystories-1m-exact-current-pipeline-frontier-v5"
        old_minimal = self.receipt.pop("minimal_reproducer")
        manifest = json.loads((run_root / "minimal-reproducer.json").read_text(encoding="utf-8"))
        self.receipt["frontier_evidence"] = {
            "kind": "control_manifest",
            "manifest": {
                "path": old_minimal["path"],
                "bytes": old_minimal["bytes"],
                "sha256": old_minimal["sha256"],
                "stage": manifest["stage"],
                "status": manifest["status"],
                "reason": manifest["reason"],
            },
            "operation": None,
            "types": None,
            "minimization": {
                "status": "not_applicable",
                "reason": "control_manifest_is_minimal",
            },
        }
        self.files = {
            path.name: path.read_bytes() for path in run_root.iterdir() if path.is_file()
        }
        for stage in ("pytorch-exported", "torch"):
            drv = f"synthetic {stage} derivation\n".encode()
            drv_json = json.dumps(
                {"derivations": {f"synthetic-{stage}.drv": {"stage": stage}}},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self.files[f"{stage}.drv"] = drv
            self.files[f"{stage}.derivation.json"] = drv_json
            execution = self.receipt["registered_build_execution"][stage]
            execution.update({
                "captured_derivation": f"reproducers/scf/{stage}.drv",
                "captured_derivation_bytes": len(drv),
                "captured_derivation_sha256": hashlib.sha256(drv).hexdigest(),
                "captured_derivation_json": f"reproducers/scf/{stage}.derivation.json",
                "captured_derivation_json_bytes": len(drv_json),
                "captured_derivation_json_sha256": hashlib.sha256(drv_json).hexdigest(),
            })

    def _compiler_failure(self) -> None:
        diagnostic = "error: failed to legalize operation 'scf.for' : (index) -> ()"
        self.files.pop("minimal-reproducer.json", None)
        self.files["scf.log"] = (diagnostic + "\n").encode()
        self.files["interestingness-test.sh"] = b"#!/bin/sh\nexit 0\n"
        self.files["interesting-full.log"] = b"exit_code: 0\n"
        self.files["reduction.log"] = b"mlir-reduce unavailable\n"
        self.receipt["frontier_evidence"] = {
            "kind": "compiler_failure",
            "manifest": None,
            "diagnostic": diagnostic,
            "operation": "scf.for",
            "types": "(index) -> ()",
            "interestingness": {
                "test": self._binding("interestingness-test.sh"),
                "full_log": self._binding("interesting-full.log"),
                "expected_exit": 1,
                "normalized_terminal_diagnostic": diagnostic,
            },
            "minimization": {
                "status": "not_practical",
                "reason": "mlir_reduce_unavailable",
                "reduction_log": self._binding("reduction.log"),
            },
        }
        stage = self.receipt["stages"][-1]
        execution = self.receipt["registered_build_execution"][stage["stage"]]
        self.receipt["diagnostic"] = diagnostic
        stage["exit_code"] = 1
        stage["terminal_diagnostics"] = [diagnostic]
        execution["exit_code"] = 1
        execution["result"] = None
        execution["derivation_tool_bindings"] = [{"path": "/bound/tool"}]
        for value in (stage, execution):
            value["log_bytes"] = len(self.files["scf.log"])
            value["log_sha256"] = hashlib.sha256(self.files["scf.log"]).hexdigest()
        full = gzip.decompress(self.files["full-input.gz"])
        stage.update({
            "artifact": self.receipt["full_failing_input"]["source_artifact"],
            "artifact_bytes": len(full),
            "artifact_sha256": hashlib.sha256(full).hexdigest(),
        })
        execution.update({
            "artifact": stage["artifact"],
            "artifact_bytes": stage["artifact_bytes"],
            "artifact_sha256": stage["artifact_sha256"],
        })

    def _completed_with_residuals(self) -> None:
        manifest = (
            b'{"artifact":"flat.scf.mlir","blockers":"blockers.json",'
            b'"stage":"flat-scf","status":"completed-with-residuals"}\n'
        )
        residual = b"module { func.func @main() }\n"
        blockers = b'{"residual_operations":["memref.alloc"]}\n'
        self.files["minimal-reproducer.json"] = manifest
        self.files["flat.scf.mlir"] = residual
        self.files["blockers.json"] = blockers
        self.live_flat_scf = {
            "output": "/nix/store/synthetic-flat-scf",
            "residual_payloads": {
                "flat.scf.mlir": {
                    "path": "/nix/store/synthetic-flat-scf/flat.scf.mlir",
                    "bytes": residual,
                    "sha256": hashlib.sha256(residual).hexdigest(),
                },
                "blockers.json": {
                    "path": "/nix/store/synthetic-flat-scf/blockers.json",
                    "bytes": blockers,
                    "sha256": hashlib.sha256(blockers).hexdigest(),
                },
            },
        }
        self.files["flat-scf.log"] = b"registered residual control output\n"
        self.files["flat-scf.drv"] = b"synthetic flat-scf derivation\n"
        self.files["flat-scf.derivation.json"] = b'{"derivations":{}}'

        scf_stage = self.receipt["stages"][-1]
        scf_stage.update({
            "status": "succeeded",
            "artifact_accepted": True,
            "terminal_diagnostics": [],
        })
        scf_execution = self.receipt["registered_build_execution"]["scf"]
        scf_execution["artifact_accepted"] = True

        flat_stage = copy.deepcopy(scf_stage)
        flat_stage.update({
            "stage": "flat-scf",
            "status": "compiler_failure",
            "artifact": "/nix/store/synthetic-flat-scf/manifest.json",
            "artifact_bytes": len(manifest),
            "artifact_sha256": hashlib.sha256(manifest).hexdigest(),
            "artifact_accepted": False,
            "log": "reproducers/flat-scf/flat-scf.log",
            "log_bytes": len(self.files["flat-scf.log"]),
            "log_sha256": hashlib.sha256(self.files["flat-scf.log"]).hexdigest(),
            "terminal_diagnostics": [
                "error: registered flat-scf manifest contract mismatch"
            ],
        })
        self.receipt["stages"].append(flat_stage)

        flat_execution = copy.deepcopy(scf_execution)
        flat_execution.update({
            "artifact": flat_stage["artifact"],
            "artifact_bytes": flat_stage["artifact_bytes"],
            "artifact_sha256": flat_stage["artifact_sha256"],
            "artifact_accepted": False,
            "log": flat_stage["log"],
            "log_bytes": flat_stage["log_bytes"],
            "log_sha256": flat_stage["log_sha256"],
            "captured_derivation": "reproducers/flat-scf/flat-scf.drv",
            "captured_derivation_bytes": len(self.files["flat-scf.drv"]),
            "captured_derivation_sha256": hashlib.sha256(
                self.files["flat-scf.drv"]
            ).hexdigest(),
            "captured_derivation_json": "reproducers/flat-scf/flat-scf.derivation.json",
            "captured_derivation_json_bytes": len(
                self.files["flat-scf.derivation.json"]
            ),
            "captured_derivation_json_sha256": hashlib.sha256(
                self.files["flat-scf.derivation.json"]
            ).hexdigest(),
        })
        self.receipt["registered_build_execution"]["flat-scf"] = flat_execution

        for stage, execution in self.receipt["registered_build_execution"].items():
            execution["captured_derivation"] = f"reproducers/flat-scf/{stage}.drv"
            execution["captured_derivation_json"] = (
                f"reproducers/flat-scf/{stage}.derivation.json"
            )

        self.receipt["pipeline_execution"].update({
            "first_invalid_stage": "flat-scf",
            "not_run": ["calyx", "calyx-native-sv"],
        })
        self.receipt["full_failing_input"]["path"] = (
            "reproducers/flat-scf/full-input.gz"
        )
        self.receipt["stage"] = "flat-scf"
        self.receipt["diagnostic"] = flat_stage["terminal_diagnostics"][0]
        self.receipt["frontier_evidence"] = {
            "kind": "control_manifest",
            "manifest": {
                **self._binding("minimal-reproducer.json", root="flat-scf"),
                "stage": "flat-scf",
                "status": "completed-with-residuals",
                "reason": None,
                "artifact": "flat.scf.mlir",
                "blockers": "blockers.json",
            },
            "residual_artifact": self._binding("flat.scf.mlir", root="flat-scf"),
            "blockers": self._binding("blockers.json", root="flat-scf"),
            "operation": None,
            "types": None,
            "minimization": {
                "status": "not_applicable",
                "reason": "control_manifest_is_minimal",
            },
        }

    def _binding(self, name: str, *, root: str = "scf") -> dict[str, object]:
        data = self.files[name]
        return {
            "path": f"reproducers/{root}/{name}",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def _rehash(self) -> None:
        self.receipt["sha256"] = MODULE._canonical_receipt_hash(self.receipt)

    def _reject(self, pattern: str) -> None:
        self._rehash()
        with self.assertRaisesRegex(MODULE.VerificationError, pattern):
            MODULE._verify_v5_frontier_evidence(
                self.receipt,
                self.files,
                "fixture",
                live_derivation=getattr(self, "live_flat_scf", None),
            )

    def test_control_manifest_branch_rejects_nonzero_exit_or_missing_manifest(self) -> None:
        stage = self.receipt["stages"][-1]
        execution = self.receipt["registered_build_execution"][stage["stage"]]
        stage["exit_code"] = execution["exit_code"] = 1
        self._reject("control manifest.*zero exit")
        stage["exit_code"] = execution["exit_code"] = 0
        self.files.pop("minimal-reproducer.json")
        self._reject("control manifest.*missing")

    def test_compiler_failure_branch_rejects_zero_exit_or_any_manifest(self) -> None:
        self._compiler_failure()
        stage = self.receipt["stages"][-1]
        execution = self.receipt["registered_build_execution"][stage["stage"]]
        stage["exit_code"] = execution["exit_code"] = 0
        self._reject("compiler failure.*nonzero exit")
        stage["exit_code"] = execution["exit_code"] = 1
        self.receipt["frontier_evidence"]["manifest"] = {}
        self._reject("compiler failure.*manifest")

    def test_compiler_failure_branch_preserves_linalg_input_log_tool_and_command(self) -> None:
        self._compiler_failure()
        self.receipt["full_failing_input"]["content_sha256"] = "0" * 64
        self._reject("full input")
        self.receipt["full_failing_input"]["content_sha256"] = hashlib.sha256(
            gzip.decompress(self.files["full-input.gz"])
        ).hexdigest()
        self.receipt["stages"][-1]["log_sha256"] = "0" * 64
        self._reject("failure log")
        self.receipt["stages"][-1]["log_sha256"] = hashlib.sha256(
            self.files["scf.log"]
        ).hexdigest()
        execution = self.receipt["registered_build_execution"]["scf"]
        execution["derivation_tool_bindings"] = []
        self._reject("tool binding")
        execution["derivation_tool_bindings"] = [{"path": "/bound/tool"}]
        execution["derivation_build_command"] = "mutated"
        self._reject("build command")

    def test_compiler_failure_branch_rejects_unbound_operation_or_types(self) -> None:
        self._compiler_failure()
        self.receipt["frontier_evidence"]["operation"] = "scf.while"
        self._reject("operation")
        self.receipt["frontier_evidence"]["operation"] = None
        self.receipt["frontier_evidence"]["types"] = "(i1) -> i1"
        self._reject("types")

    def test_branch_specific_directory_sets_reject_cross_branch_files(self) -> None:
        self.files["interestingness-test.sh"] = b"cross-branch\n"
        self._reject("directory contents")
        self.files.pop("interestingness-test.sh")
        self._compiler_failure()
        self.files["minimal-reproducer.json"] = b"{}\n"
        self._reject("directory contents")

    def test_completed_with_residuals_control_manifest_binds_payloads(self) -> None:
        self._completed_with_residuals()

        try:
            expected = MODULE._verify_v5_frontier_evidence(
                self.receipt,
                self.files,
                "fixture",
                live_derivation=self.live_flat_scf,
            )
        except MODULE.VerificationError as error:
            self.fail(str(error))

        self.assertIn("flat.scf.mlir", expected)
        self.assertIn("blockers.json", expected)

    def test_completed_with_residuals_rejects_missing_or_altered_payloads(self) -> None:
        self._completed_with_residuals()
        original = self.files.pop("blockers.json")
        self._reject("blockers")
        self.files["blockers.json"] = original + b" "
        self._reject("blockers")
        self.files["blockers.json"] = original
        self.files.pop("flat.scf.mlir")
        self._reject("residual artifact")

    def test_completed_with_residuals_rejects_manifest_lies_or_acceptance(self) -> None:
        self._completed_with_residuals()
        self.receipt["frontier_evidence"]["manifest"]["reason"] = "invented"
        self._reject("exact control manifest")
        self.receipt["frontier_evidence"]["manifest"]["reason"] = None
        self.receipt["stages"][-1]["artifact_accepted"] = True
        self.receipt["registered_build_execution"]["flat-scf"][
            "artifact_accepted"
        ] = True
        self._reject("invalid artifact was accepted")

    def test_completed_with_residuals_rejects_detached_payload_with_recomputed_hashes(self) -> None:
        self._completed_with_residuals()
        detached = self.files["blockers.json"] + b" "
        self.files["blockers.json"] = detached
        self.receipt["frontier_evidence"]["blockers"].update({
            "bytes": len(detached),
            "sha256": hashlib.sha256(detached).hexdigest(),
        })

        self._reject("differs from live registered output")
        self.assertEqual(
            self.receipt["sha256"], MODULE._canonical_receipt_hash(self.receipt)
        )

    def test_completed_with_residuals_rejects_altered_live_payload_path(self) -> None:
        self._completed_with_residuals()
        self.live_flat_scf["residual_payloads"]["flat.scf.mlir"]["path"] = (
            "/nix/store/detached/flat.scf.mlir"
        )

        self._reject("live residual payload path mismatch")
        self.assertEqual(
            self.receipt["sha256"], MODULE._canonical_receipt_hash(self.receipt)
        )

    def test_residual_replay_log_reconstructs_exact_classifier_validation(self) -> None:
        self._completed_with_residuals()
        raw = b"$ nix build .#flat-scf\nexit_code: 0\n--- stdout ---\n/store/out\n--- stderr ---\n"
        self.live_flat_scf.update({
            "artifact_bytes": self.files["minimal-reproducer.json"],
            "log_bytes": raw,
        })

        expected = raw + (
            b"--- classifier validation ---\n"
            b"error: registered flat-scf stage completed with residuals; "
            b"artifact remains rejected\n"
        )
        self.assertEqual(
            MODULE._expected_v5_replay_log(
                "flat-scf", self.live_flat_scf, residual_rejected=True
            ),
            expected,
        )

        self.live_flat_scf["artifact_bytes"] = (
            b'{"artifact":"detached.mlir","blockers":"blockers.json",'
            b'"stage":"flat-scf","status":"completed-with-residuals"}\n'
        )
        with self.assertRaisesRegex(MODULE.VerificationError, "live residual manifest"):
            MODULE._expected_v5_replay_log(
                "flat-scf", self.live_flat_scf, residual_rejected=True
            )


class V5PublicReceiptAdversarialTest(unittest.TestCase):
    """Mutations remain internally self-hashed and enter through the public verifier."""

    @classmethod
    def setUpClass(cls) -> None:
        receipt = json.loads(
            (FLAT_SCF_BUNDLES / "run-1" / "receipt.json").read_text(encoding="utf-8")
        )
        cls.trust = MODULE._independent_v5_trust(
            ROOT,
            receipt["source_commit"],
            [record["stage"] for record in receipt["stages"]],
        )

    @staticmethod
    def _adversarial_receipt_hash(receipt) -> str:
        unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
        canonical = json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), allow_nan=True
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _mutated_bundle(self, mutate):
        temporary = tempfile.TemporaryDirectory(prefix="exact-v5-public-mutation-")
        self.addCleanup(temporary.cleanup)
        bundle = Path(temporary.name) / "bundle"
        shutil.copytree(FLAT_SCF_BUNDLES, bundle, copy_function=os.link)
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        receipts = []
        for run_name in ("run-1", "run-2"):
            path = bundle / run_name / "receipt.json"
            receipt = json.loads(path.read_text(encoding="utf-8"))
            mutate(receipt)
            receipt["sha256"] = self._adversarial_receipt_hash(receipt)
            data = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(data)
            replacement.replace(path)
            binding = manifest["runs"][run_name]["files"]["receipt.json"]
            binding.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            manifest["runs"][run_name]["receipt_self_hash"] = receipt["sha256"]
            manifest["runs"][run_name]["source_commit"] = receipt["source_commit"]
            receipts.append((receipt, data))
        self.assertEqual(receipts[0], receipts[1])
        receipt, data = receipts[0]
        manifest["source_commit"] = receipt["source_commit"]
        manifest["expected_comparison"].update({
            "receipt_file_sha256": hashlib.sha256(data).hexdigest(),
            "receipt_self_hash": receipt["sha256"],
        })
        manifest_path = bundle / "manifest.json"
        replacement = manifest_path.with_suffix(".replacement")
        replacement.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        replacement.replace(manifest_path)
        return bundle

    def _reject(self, mutate, pattern: str) -> None:
        bundle = self._mutated_bundle(mutate)
        self._reject_bundle(bundle, pattern)

    def _reject_bundle(self, bundle: Path, pattern: str) -> None:
        root = bundle.parent
        current = (
            root
            / "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"
        )
        current.parent.mkdir(parents=True)
        os.link(bundle / "run-1/receipt.json", current)
        reproducers = root / "reproducers/flat-scf"
        reproducers.mkdir(parents=True)
        canonical_manifest = json.loads(
            (FLAT_SCF_BUNDLES / "manifest.json").read_text(encoding="utf-8")
        )
        for filename in set(canonical_manifest["canonical_files"]) - {"receipt.json"}:
            os.link(bundle / "run-1" / filename, reproducers / filename)
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=self.trust):
            with self.assertRaisesRegex(MODULE.VerificationError, pattern):
                MODULE.verify_public_v5_evidence(root, bundle)

    def _payload_mutated_bundle(self, filename: str):
        bundle = self._mutated_bundle(lambda _: None)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipts = []
        for run_name in ("run-1", "run-2"):
            payload_path = bundle / run_name / filename
            payload = payload_path.read_bytes() + b"\n"
            replacement = payload_path.with_suffix(payload_path.suffix + ".replacement")
            replacement.write_bytes(payload)
            replacement.replace(payload_path)
            payload_binding = manifest["runs"][run_name]["files"][filename]
            payload_binding.update({
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
            receipt_path = bundle / run_name / "receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if filename == "minimal-reproducer.json":
                binding = receipt["frontier_evidence"]["manifest"]
                receipt["stages"][-1].update({
                    "artifact_bytes": len(payload),
                    "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                })
                receipt["registered_build_execution"]["flat-scf"].update({
                    "artifact_bytes": len(payload),
                    "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                })
            elif filename == "flat.scf.mlir":
                binding = receipt["frontier_evidence"]["residual_artifact"]
            elif filename.endswith(".log"):
                stage = filename.removesuffix(".log")
                record = next(item for item in receipt["stages"] if item["stage"] == stage)
                run = receipt["registered_build_execution"][stage]
                record.update({
                    "log_bytes": len(payload),
                    "log_sha256": hashlib.sha256(payload).hexdigest(),
                })
                run.update({
                    "log_bytes": len(payload),
                    "log_sha256": hashlib.sha256(payload).hexdigest(),
                })
                binding = None
            else:
                binding = receipt["frontier_evidence"]["blockers"]
            if binding is not None:
                binding.update(payload_binding)
            receipt["sha256"] = MODULE._canonical_receipt_hash(receipt)
            receipt_data = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
            replacement = receipt_path.with_suffix(".replacement")
            replacement.write_bytes(receipt_data)
            replacement.replace(receipt_path)
            receipt_binding = manifest["runs"][run_name]["files"]["receipt.json"]
            receipt_binding.update({
                "bytes": len(receipt_data),
                "sha256": hashlib.sha256(receipt_data).hexdigest(),
            })
            manifest["runs"][run_name]["receipt_self_hash"] = receipt["sha256"]
            receipts.append((receipt, receipt_data))
        self.assertEqual(receipts[0], receipts[1])
        manifest["expected_comparison"].update({
            "receipt_file_sha256": hashlib.sha256(receipts[0][1]).hexdigest(),
            "receipt_self_hash": receipts[0][0]["sha256"],
        })
        replacement = manifest_path.with_suffix(".replacement")
        replacement.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        replacement.replace(manifest_path)
        return bundle

    def _manifest_mutated_bundle(self, mutate):
        bundle = self._mutated_bundle(lambda _: None)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutate(manifest)
        replacement = manifest_path.with_suffix(".replacement")
        replacement.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        replacement.replace(manifest_path)
        return bundle

    def test_public_verifier_rejects_each_stage_semantic_lie(self) -> None:
        cases = {
            "status": lambda r: r["stages"][-1].__setitem__("status", "succeeded"),
            "terminal_diagnostics": lambda r: r["stages"][-1].__setitem__(
                "terminal_diagnostics", []
            ),
            "artifact_bytes": lambda r: r["stages"][-1].__setitem__(
                "artifact_bytes", r["stages"][-1]["artifact_bytes"] + 1
            ),
            "upstream_identity": lambda r: r["stages"][-1].__setitem__(
                "upstream_identity", "0" * 64
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "stage semantics")

    def test_public_verifier_rejects_each_execution_semantic_lie(self) -> None:
        cases = {
            "invoked": ("invoked", False),
            "result": ("result", "/nix/store/detached"),
            "route_alias": ("route_alias", "detached-route"),
            "frontend": ("frontend", "torch"),
            "backend": ("backend", "detached-backend"),
            "artifact_bytes": ("artifact_bytes", 1),
        }
        for name, (key, value) in cases.items():
            with self.subTest(name=name):
                self._reject(
                    lambda r, key=key, value=value: r["registered_build_execution"][
                        "flat-scf"
                    ].__setitem__(key, value),
                    "execution semantics",
                )

    def test_public_verifier_rejects_acceptance_and_stage_order_lies(self) -> None:
        def accepted(receipt):
            receipt["stages"][-1]["artifact_accepted"] = True
            receipt["registered_build_execution"]["flat-scf"]["artifact_accepted"] = True

        self._reject(accepted, "invalid artifact|replay acceptance")

        def reordered(receipt):
            receipt["stages"][2], receipt["stages"][3] = (
                receipt["stages"][3],
                receipt["stages"][2],
            )

        self._reject(reordered, "stage order|sequence|executed prefix")

        self._reject(
            lambda receipt: receipt["stages"].append("ignored-stage-record"),
            "schema|stage order|sequence|executed prefix",
        )
        self._reject(
            lambda receipt: receipt["registered_build_execution"].__setitem__(
                "calyx", receipt["registered_build_execution"]["flat-scf"]
            ),
            "stage order|execution",
        )

    def test_public_verifier_rejects_top_level_diagnostic_and_combined_lies(self) -> None:
        self._reject(lambda r: r.__setitem__("diagnostic", "invented"), "diagnostic")

        def combined(receipt):
            receipt["diagnostic"] = "invented"
            receipt["stages"][-1].update({
                "status": "succeeded",
                "terminal_diagnostics": [],
                "artifact_bytes": 1,
                "upstream_identity": "0" * 64,
            })
            receipt["registered_build_execution"]["flat-scf"].update({
                "invoked": False,
                "result": "/nix/store/detached",
                "route_alias": "detached-route",
                "frontend": "torch",
                "backend": "detached-backend",
            })

        self._reject(combined, "diagnostic|stage semantics|execution semantics")

    def test_public_verifier_rejects_live_manifest_residual_and_blocker_substitutions(self) -> None:
        for filename in ("minimal-reproducer.json", "flat.scf.mlir", "blockers.json"):
            with self.subTest(filename=filename):
                bundle = self._payload_mutated_bundle(filename)
                self._reject_bundle(
                    bundle,
                    "stage semantics|registered output|live registered output|control manifest",
                )

    def test_public_verifier_rejects_detached_rehashed_log_payload(self) -> None:
        self._reject_bundle(
            self._payload_mutated_bundle("flat-scf.log"),
            "replay log",
        )

    def test_public_verifier_rejects_producer_commit_and_source_substitutions(self) -> None:
        self._reject(
            lambda r: r.__setitem__("source_commit", f"{r['source_commit']}^0"),
            "producer source commit",
        )
        self._reject(
            lambda r: r["pipeline_source_identity"].__setitem__(
                "evidence_source_commit", "4f07c607717705401a8fdfd906f8a142910b8af7"
            ),
            "pipeline source identity",
        )
        self._reject(
            lambda r: r["pipeline_source_identity"]["critical_inputs"]["flake.nix"].__setitem__(
                "workspace_sha256", "0" * 64
            ),
            "pipeline source identity|critical pipeline input",
        )

    def test_unpinned_source_commit_is_rejected_before_nix_trust_resolution(self) -> None:
        bundle = self._mutated_bundle(
            lambda r: r.__setitem__("source_commit", f"{r['source_commit']}^0")
        )
        with mock.patch.object(
            MODULE,
            "_independent_v5_trust",
            side_effect=AssertionError("must not resolve unpinned source"),
        ):
            with self.assertRaisesRegex(MODULE.VerificationError, "producer source commit"):
                MODULE.verify_determinism_bundles(bundle)

    def test_public_verifier_rejects_all_bound_provenance_substitutions(self) -> None:
        cases = {
            "flake archive": lambda r: r["pipeline_source_identity"].__setitem__(
                "flake_archive_nar_hash", "sha256-detached"
            ),
            "Nix source": lambda r: r["pipeline_source_identity"][
                "torch_derivation"
            ].__setitem__("output", "/nix/store/detached"),
            "Task identities": lambda r: r[
                "frozen_task_1_through_3_identities"
            ].__setitem__("adapter_sha256", "0" * 64),
            "semantic": lambda r: r["semantic_gate"].__setitem__(
                "probe_report_sha256", "0" * 64
            ),
            "predecessor": lambda r: r["predecessor_receipt"].__setitem__(
                "self_sha256", "0" * 64
            ),
            "producer verifier": lambda r: r["capture_tools"][
                "determinism_verifier"
            ].__setitem__("sha256", "0" * 64),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "source identity|frozen Task|semantic|predecessor|source-commit-byte")

    def test_public_verifier_rejects_log_path_and_byte_count_lies(self) -> None:
        cases = {
            "stage renamed log": lambda r: r["stages"][-1].__setitem__(
                "log", "reproducers/flat-scf/detached.log"
            ),
            "execution renamed log": lambda r: r["registered_build_execution"][
                "flat-scf"
            ].__setitem__("log", "reproducers/flat-scf/detached.log"),
            "stage false log bytes": lambda r: r["stages"][-1].__setitem__(
                "log_bytes", 1
            ),
            "execution false log bytes": lambda r: r[
                "registered_build_execution"
            ]["flat-scf"].__setitem__("log_bytes", 1),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "log")

    def test_public_verifier_rejects_added_removed_and_changed_tool_revisions(self) -> None:
        cases = {
            "added": lambda r: r["stages"][-1]["tool_revisions"].__setitem__(
                "invented", "detached"
            ),
            "removed": lambda r: r["stages"][-1]["tool_revisions"].pop(
                "derivation_json_sha256"
            ),
            "changed": lambda r: r["stages"][-1]["tool_revisions"].__setitem__(
                "evidence_source_commit", "0" * 40
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "tool revision")

    def test_public_verifier_rejects_every_claim_flag_lie(self) -> None:
        claim_names = (
            "backend_model_quantization_ddr_pcie_changed",
            "board_inference",
            "calyx_native_sv",
            "functional_equivalence",
            "resource_or_timing",
            "syntax_validated",
            "synthesis_validated",
        )
        for claim in claim_names:
            with self.subTest(claim=claim):
                self._reject(
                    lambda r, claim=claim: r["claims"].__setitem__(claim, True),
                    "claims",
                )

    def test_public_verifier_rejects_extra_and_missing_nested_schema_keys(self) -> None:
        cases = {
            "top extra": lambda r: r.__setitem__("invented", None),
            "top missing": lambda r: r.pop("claims"),
            "claims extra": lambda r: r["claims"].__setitem__("invented", False),
            "claims missing": lambda r: r["claims"].pop("functional_equivalence"),
            "capture tool extra": lambda r: r["capture_tools"]["classifier"].__setitem__(
                "invented", None
            ),
            "semantic gate extra": lambda r: r["semantic_gate"].__setitem__(
                "invented", None
            ),
            "semantic evidence extra": lambda r: r["semantic_gate"][
                "evidence"
            ].__setitem__("invented", None),
            "predecessor extra": lambda r: r["predecessor_receipt"].__setitem__(
                "invented", None
            ),
            "stage extra": lambda r: r["stages"][-1].__setitem__("invented", None),
            "stage missing": lambda r: r["stages"][-1].pop("log"),
            "execution extra": lambda r: r["registered_build_execution"][
                "flat-scf"
            ].__setitem__("invented", None),
            "execution missing": lambda r: r["registered_build_execution"][
                "flat-scf"
            ].pop("log"),
            "execution tool binding extra": lambda r: r[
                "registered_build_execution"
            ]["flat-scf"]["derivation_tool_bindings"][0].__setitem__("invented", None),
            "pipeline extra": lambda r: r["pipeline_execution"].__setitem__(
                "invented", None
            ),
            "frontier extra": lambda r: r["frontier_evidence"].__setitem__(
                "invented", None
            ),
            "frontier missing": lambda r: r["frontier_evidence"].pop("operation"),
            "manifest extra": lambda r: r["frontier_evidence"]["manifest"].__setitem__(
                "invented", None
            ),
            "manifest missing": lambda r: r["frontier_evidence"]["manifest"].pop(
                "reason"
            ),
            "residual binding extra": lambda r: r["frontier_evidence"][
                "residual_artifact"
            ].__setitem__("invented", None),
            "blocker binding missing": lambda r: r["frontier_evidence"][
                "blockers"
            ].pop("bytes"),
            "minimization extra": lambda r: r["frontier_evidence"][
                "minimization"
            ].__setitem__("invented", None),
            "identity extra": lambda r: r[
                "frozen_task_1_through_3_identities"
            ].__setitem__("invented", "0" * 64),
            "source extra": lambda r: r["pipeline_source_identity"].__setitem__(
                "invented", None
            ),
            "critical input extra": lambda r: r["pipeline_source_identity"][
                "critical_inputs"
            ]["flake.nix"].__setitem__("invented", None),
            "source derivation extra": lambda r: r["pipeline_source_identity"][
                "torch_derivation"
            ].__setitem__("invented", None),
            "full input extra": lambda r: r["full_failing_input"].__setitem__(
                "invented", None
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "schema|keys|identity|minimization")

    def test_public_verifier_rejects_combined_log_tool_claim_and_schema_lies(self) -> None:
        def combined(receipt):
            receipt["stages"][-1].update({
                "log": "reproducers/flat-scf/detached.log",
                "log_bytes": 1,
                "invented": None,
            })
            receipt["stages"][-1]["tool_revisions"]["invented"] = "detached"
            receipt["registered_build_execution"]["flat-scf"].update({
                "log": "reproducers/flat-scf/detached.log",
                "log_bytes": 1,
            })
            receipt["claims"]["functional_equivalence"] = True

        self._reject(combined, "schema|log|tool revision|claims")

    def test_public_verifier_rejects_bool_int_and_float_confusion(self) -> None:
        def false_exit_codes(receipt):
            receipt["stages"][-1]["exit_code"] = False
            receipt["registered_build_execution"]["flat-scf"]["exit_code"] = False

        cases = {
            "claim integer zero": lambda r: r["claims"].__setitem__(
                "functional_equivalence", 0
            ),
            "false exit codes": false_exit_codes,
            "float artifact bytes": lambda r: r["stages"][-1].__setitem__(
                "artifact_bytes", float(r["stages"][-1]["artifact_bytes"])
            ),
            "integer pipeline boolean": lambda r: r["pipeline_execution"].__setitem__(
                "stopped_after_first_invalid_stage", 1
            ),
            "integer invoked boolean": lambda r: r["registered_build_execution"][
                "flat-scf"
            ].__setitem__("invoked", 1),
            "float semantic integer": lambda r: r["semantic_gate"]["evidence"][
                "contract"
            ]["shift_one_output"].__setitem__(0, -3.0),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "JSON type")

    def test_public_verifier_rejects_recursive_type_and_range_swaps(self) -> None:
        cases = {
            "top string to null": lambda r: r.__setitem__("model", None),
            "capture object to list": lambda r: r.__setitem__("capture_tools", []),
            "diagnostic string to list": lambda r: r.__setitem__("diagnostic", []),
            "log path string to null": lambda r: r["stages"][-1].__setitem__(
                "log", None
            ),
            "diagnostic list to dict": lambda r: r["stages"][-1].__setitem__(
                "terminal_diagnostics", {}
            ),
            "diagnostic element to int": lambda r: r["stages"][-1][
                "terminal_diagnostics"
            ].__setitem__(0, 1),
            "registered order element to bool": lambda r: r["pipeline_execution"][
                "registered_order"
            ].__setitem__(0, False),
            "operation null to string": lambda r: r["frontier_evidence"].__setitem__(
                "operation", "none"
            ),
            "manifest null reason to bool": lambda r: r["frontier_evidence"][
                "manifest"
            ].__setitem__("reason", False),
            "minimization string to null": lambda r: r["frontier_evidence"][
                "minimization"
            ].__setitem__("reason", None),
            "negative full input bytes": lambda r: r["full_failing_input"].__setitem__(
                "archive_bytes", -1
            ),
            "negative tool binding bytes": lambda r: r[
                "registered_build_execution"
            ]["flat-scf"]["derivation_tool_bindings"][0].__setitem__("bytes", -1),
            "critical inputs dict to list": lambda r: r[
                "pipeline_source_identity"
            ].__setitem__("critical_inputs", []),
            "derivation source element to int": lambda r: r[
                "pipeline_source_identity"
            ]["torch_derivation"]["input_sources"].__setitem__(0, 1),
            "identity hash string to null": lambda r: r[
                "frozen_task_1_through_3_identities"
            ].__setitem__("adapter_sha256", None),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, "JSON type")

    def test_public_verifier_rejects_nonfinite_json_numbers(self) -> None:
        for name, value in (
            ("nan", float("nan")),
            ("positive infinity", float("inf")),
            ("negative infinity", float("-inf")),
        ):
            with self.subTest(name=name):
                self._reject(
                    lambda r, value=value: r["stages"][-1].__setitem__(
                        "artifact_bytes", value
                    ),
                    "JSON type",
                )

    def test_public_verifier_rejects_bundle_manifest_type_confusion(self) -> None:
        cases = {
            "integer expected boolean": lambda m: m["expected_comparison"].__setitem__(
                "byte_identical", 1
            ),
            "float file bytes": lambda m: m["runs"]["run-1"]["files"][
                "receipt.json"
            ].__setitem__(
                "bytes", float(m["runs"]["run-1"]["files"]["receipt.json"]["bytes"])
            ),
            "negative file bytes": lambda m: m["runs"]["run-1"]["files"][
                "receipt.json"
            ].__setitem__("bytes", -1),
            "canonical file element to int": lambda m: m["canonical_files"].__setitem__(
                0, 1
            ),
            "run object to list": lambda m: m["runs"].__setitem__("run-1", []),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject_bundle(
                    self._manifest_mutated_bundle(mutate),
                    "JSON type",
                )


class V5PublicIntegrationAdversarialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        receipt = json.loads(
            (FLAT_SCF_BUNDLES / "run-1" / "receipt.json").read_text(encoding="utf-8")
        )
        cls.trust = MODULE._independent_v5_trust(
            ROOT,
            receipt["source_commit"],
            [record["stage"] for record in receipt["stages"]],
        )

    def _public_tree(self):
        temporary = tempfile.TemporaryDirectory(prefix="exact-v5-public-tree-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bundle = (
            root
            / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf"
        )
        bundle.parent.mkdir(parents=True)
        shutil.copytree(FLAT_SCF_BUNDLES, bundle, copy_function=os.link)
        current = root / "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"
        os.link(FLAT_SCF_BUNDLES / "run-1/receipt.json", current)
        reproducers = root / "reproducers/flat-scf"
        reproducers.parent.mkdir(parents=True)
        shutil.copytree(ROOT / "reproducers/flat-scf", reproducers, copy_function=os.link)
        return root, bundle, current, reproducers

    @staticmethod
    def _replace(path: Path, data: bytes) -> None:
        replacement = path.with_name(path.name + ".replacement")
        replacement.write_bytes(data)
        replacement.replace(path)

    def _reject(self, mutate, pattern: str) -> None:
        root, bundle, current, reproducers = self._public_tree()
        mutate(current, reproducers)
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=self.trust):
            with self.assertRaisesRegex(MODULE.VerificationError, pattern):
                MODULE.verify_public_v5_evidence(root, bundle)

    def test_public_verifier_accepts_exact_current_receipt_and_reproducer_tree(self) -> None:
        root, bundle, _, _ = self._public_tree()
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=self.trust):
            result = MODULE.verify_public_v5_evidence(root, bundle)
        self.assertEqual(result["public_reproducer_file_count"], 19)

    def test_public_verifier_rejects_detached_current_receipt(self) -> None:
        self._reject(
            lambda current, _: self._replace(current, b"{}\n"),
            "public receipt",
        )

    def test_public_verifier_rejects_unversioned_bundle_manifest_key(self) -> None:
        root, bundle, _, _ = self._public_tree()
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["invented"] = None
        self._replace(
            manifest_path,
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=self.trust):
            with self.assertRaisesRegex(MODULE.VerificationError, "manifest schema"):
                MODULE.verify_public_v5_evidence(root, bundle)

    def test_public_verifier_rejects_mutated_live_bound_payloads(self) -> None:
        for filename in ("flat.scf.mlir", "blockers.json"):
            with self.subTest(filename=filename):
                self._reject(
                    lambda _, reproducers, filename=filename: self._replace(
                        reproducers / filename,
                        (reproducers / filename).read_bytes() + b"detached",
                    ),
                    "public reproducer",
                )

    def test_public_verifier_rejects_extra_missing_symlink_subdir_and_nonregular(self) -> None:
        cases = {
            "extra": lambda r: (r / "extra").write_bytes(b"extra"),
            "missing": lambda r: (r / "blockers.json").unlink(),
            "symlink": lambda r: ((r / "blockers.json").unlink(), (r / "blockers.json").symlink_to("flat.scf.mlir")),
            "subdir": lambda r: (r / "subdir").mkdir(),
            "nonregular": lambda r: os.mkfifo(r / "fifo"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(lambda _, reproducers, mutate=mutate: mutate(reproducers), "public reproducer")


class V5CompilerFailurePublicIntegrationTest(unittest.TestCase):
    """A real two-run on-disk compiler-failure bundle uses classifier serialization."""

    @classmethod
    def setUpClass(cls) -> None:
        receipt = json.loads(
            (FLAT_SCF_BUNDLES / "run-1" / "receipt.json").read_text(encoding="utf-8")
        )
        cls.base_trust = MODULE._independent_v5_trust(
            ROOT,
            receipt["source_commit"],
            [record["stage"] for record in receipt["stages"]],
        )

    @staticmethod
    def _json_bytes(value: object) -> bytes:
        return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()

    @staticmethod
    def _binding(path: str, data: bytes) -> dict[str, object]:
        return {
            "path": path,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def _fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="exact-v5-compiler-public-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source_receipt = json.loads(
            (FLAT_SCF_BUNDLES / "run-1" / "receipt.json").read_text(encoding="utf-8")
        )
        receipt = copy.deepcopy(source_receipt)
        trust = copy.deepcopy(self.base_trust)
        stages = ["pytorch-exported", "torch", "linalg", "scf"]
        diagnostic = "error: failed to legalize operation 'scf.for' : (index) -> ()"

        fixture_tools = root / "fixture-tools"
        fixture_tools.mkdir()
        compiler = fixture_tools / "mlir-opt"
        compiler.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' {shlex.quote(diagnostic)} >&2\n"
            "exit 7\n",
            encoding="utf-8",
        )
        compiler.chmod(0o755)
        upstream = fixture_tools / "input.linalg.mlir"
        upstream.write_bytes(trust["derivations"]["linalg"]["artifact_bytes"])
        build_command = (
            f"{shlex.quote(str(compiler))} {shlex.quote(str(upstream))} -o \"$out\""
        )
        tool_binding = self._binding(str(compiler), compiler.read_bytes())

        command = [
            "nix", "build", "--no-link", "--print-out-paths", "-L",
            ".#tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-scf",
        ]
        compiler_log = MODULE._canonical_execution_evidence(
            command,
            subprocess.CompletedProcess(command, 7, "", diagnostic + "\n"),
        )
        trust["derivations"]["linalg"]["artifact_path"] = str(upstream)
        failing_live = trust["derivations"]["scf"]
        failing_live.update({
            "artifact_bytes": upstream.read_bytes(),
            "artifact_path": str(upstream),
            "build_command": build_command,
            "build_command_sha256": hashlib.sha256(build_command.encode()).hexdigest(),
            "tool_bindings": [tool_binding],
            "exit_code": 7,
            "log_bytes": compiler_log,
        })

        files: dict[str, bytes] = {}
        source_run = FLAT_SCF_BUNDLES / "run-1"
        for stage in stages:
            for suffix in ("log", "drv", "derivation.json"):
                filename = f"{stage}.{suffix}"
                files[filename] = (source_run / filename).read_bytes()
        files["scf.log"] = compiler_log
        files["full-input.gz"] = gzip.compress(upstream.read_bytes(), mtime=0)

        interestingness_script = root / "interestingness-test.sh"
        CLASSIFIER._write_interestingness_test(
            interestingness_script,
            build_command=build_command,
            upstream_input=upstream,
            expected_exit=7,
            expected_diagnostic=diagnostic,
            operation="scf.for",
            types="(index) -> ()",
        )
        files["interestingness-test.sh"] = interestingness_script.read_bytes()
        replay = subprocess.run(
            [str(interestingness_script), str(upstream)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
        files["interesting-full.log"] = MODULE._canonical_execution_evidence(
            [str(interestingness_script), str(upstream)],
            replay,
            {
                str(root): "<evidence-dir>",
                str(upstream): "<full-input>",
            },
        )
        files["reduction.log"] = b"mlir-reduce is unavailable beside the bound mlir-opt tool\n"

        receipt["stages"] = receipt["stages"][:4]
        receipt["registered_build_execution"] = {
            stage: receipt["registered_build_execution"][stage] for stage in stages
        }
        receipt["pipeline_execution"].update({
            "first_invalid_stage": "scf",
            "not_run": ["flat-scf", "calyx", "calyx-native-sv"],
        })
        receipt["stage"] = "scf"
        receipt["diagnostic"] = diagnostic
        receipt["frontier"] = "pre_calyx_frontier"
        for stage_record in receipt["stages"]:
            stage = stage_record["stage"]
            stage_record["log"] = f"reproducers/scf/{stage}.log"
            stage_record["log_bytes"] = len(files[f"{stage}.log"])
            stage_record["log_sha256"] = hashlib.sha256(files[f"{stage}.log"]).hexdigest()
            execution = receipt["registered_build_execution"][stage]
            execution["log"] = stage_record["log"]
            execution["log_bytes"] = stage_record["log_bytes"]
            execution["log_sha256"] = stage_record["log_sha256"]
            execution["captured_derivation"] = f"reproducers/scf/{stage}.drv"
            execution["captured_derivation_json"] = (
                f"reproducers/scf/{stage}.derivation.json"
            )

        linalg_stage = receipt["stages"][-2]
        linalg_execution = receipt["registered_build_execution"]["linalg"]
        linalg_stage["artifact"] = str(upstream)
        linalg_execution["artifact"] = str(upstream)
        failing_stage = receipt["stages"][-1]
        failing_execution = receipt["registered_build_execution"]["scf"]
        artifact_sha = hashlib.sha256(upstream.read_bytes()).hexdigest()
        failing_stage.update({
            "artifact": str(upstream),
            "artifact_bytes": len(upstream.read_bytes()),
            "artifact_sha256": artifact_sha,
            "artifact_accepted": False,
            "exit_code": 7,
            "status": "compiler_failure",
            "terminal_diagnostics": [diagnostic],
        })
        failing_stage["tool_revisions"]["build_command_sha256"] = failing_live[
            "build_command_sha256"
        ]
        failing_execution.update({
            "artifact": str(upstream),
            "artifact_bytes": len(upstream.read_bytes()),
            "artifact_sha256": artifact_sha,
            "artifact_accepted": False,
            "derivation_build_command": build_command,
            "derivation_build_command_sha256": failing_live["build_command_sha256"],
            "derivation_tool_bindings": [tool_binding],
            "exit_code": 7,
            "result": None,
        })
        receipt["full_failing_input"] = {
            **self._binding("reproducers/scf/full-input.gz", files["full-input.gz"]),
            "archive_bytes": len(files["full-input.gz"]),
            "archive_sha256": hashlib.sha256(files["full-input.gz"]).hexdigest(),
            "content_bytes": len(upstream.read_bytes()),
            "content_sha256": artifact_sha,
            "source_artifact": str(upstream),
            "source_stage": "linalg",
        }
        receipt["full_failing_input"].pop("bytes", None)
        receipt["full_failing_input"].pop("sha256", None)

        compiler_result = CLASSIFIER.CompilerFailure(
            kind="compiler_failure",
            upstream_input=upstream,
            log=root / "scf.log",
            diagnostic=diagnostic,
            operation="scf.for",
            types="(index) -> ()",
        )
        receipt["frontier_evidence"] = CLASSIFIER._serialize_frontier_evidence(
            stage="scf",
            result=compiler_result,
            canonical_root="reproducers/scf",
            interestingness={
                "test": self._binding(
                    "reproducers/scf/interestingness-test.sh",
                    files["interestingness-test.sh"],
                ),
                "full_log": self._binding(
                    "reproducers/scf/interesting-full.log",
                    files["interesting-full.log"],
                ),
                "expected_exit": 7,
                "normalized_terminal_diagnostic": diagnostic,
            },
            minimization={
                "status": "not_practical",
                "reason": "mlir_reduce_unavailable",
                "reduction_log": self._binding(
                    "reproducers/scf/reduction.log", files["reduction.log"]
                ),
            },
        )
        receipt["sha256"] = MODULE._canonical_receipt_hash(receipt)
        files["receipt.json"] = self._json_bytes(receipt)

        canonical_files = sorted(files)
        file_manifest = {
            name: {
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in files.items()
        }
        receipt_file_sha = hashlib.sha256(files["receipt.json"]).hexdigest()
        bundle_manifest = {
            "schema": "tinystories-1m-exact-frontier-determinism-bundles-v3",
            "source_commit": receipt["source_commit"],
            "canonical_files": canonical_files,
            "expected_comparison": {
                "byte_identical": True,
                "first_invalid_stage": "scf",
                "receipt_file_sha256": receipt_file_sha,
                "receipt_self_hash": receipt["sha256"],
            },
            "runs": {
                name: {
                    "files": copy.deepcopy(file_manifest),
                    "receipt_self_hash": receipt["sha256"],
                    "source_commit": receipt["source_commit"],
                }
                for name in ("run-1", "run-2")
            },
        }
        bundle = root / "artifacts/comparison/compiler-failure-bundle"
        bundle.mkdir(parents=True)
        (bundle / "manifest.json").write_bytes(self._json_bytes(bundle_manifest))
        for run_name in ("run-1", "run-2"):
            run = bundle / run_name
            run.mkdir()
            for name, data in files.items():
                (run / name).write_bytes(data)
        public_receipt = (
            root / "artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"
        )
        public_receipt.parent.mkdir(parents=True, exist_ok=True)
        public_receipt.write_bytes(files["receipt.json"])
        public_reproducers = root / "reproducers/scf"
        public_reproducers.mkdir(parents=True)
        for name, data in files.items():
            if name != "receipt.json":
                (public_reproducers / name).write_bytes(data)
        return root, bundle, trust, public_receipt, public_reproducers

    def test_public_verifier_accepts_classifier_serialized_compiler_failure_bundle(self) -> None:
        root, bundle, trust, _, _ = self._fixture()
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=trust):
            result = MODULE.verify_public_v5_evidence(root, bundle)
        self.assertEqual(result["frontier_evidence_kind"], "compiler_failure")
        self.assertEqual(result["first_invalid_stage"], "scf")

    def test_public_verifier_rejects_self_consistent_fake_predicate_and_logs(self) -> None:
        def fake_predicate(root, bundle, current, reproducers):
            script = b"#!/usr/bin/env bash\nexit 0\n"
            candidate = root / "full-input.mlir"
            candidate.write_bytes(b"module {}\n")
            executable = root / "interestingness-test.sh"
            executable.write_bytes(script)
            executable.chmod(0o755)
            replay = subprocess.run(
                [str(executable), str(candidate)], text=True, capture_output=True
            )
            fake_log = MODULE._canonical_execution_evidence(
                [str(executable), str(candidate)],
                replay,
                {
                    str(root): "<evidence-dir>",
                    str(candidate): "<full-input>",
                },
            )
            self._replace_canonical_file(
                bundle, reproducers, "interestingness-test.sh", script
            )
            self._replace_canonical_file(
                bundle, reproducers, "interesting-full.log", fake_log
            )

            def mutate(receipt):
                interestingness = receipt["frontier_evidence"]["interestingness"]
                interestingness["test"] = self._binding(
                    "reproducers/scf/interestingness-test.sh", script
                )
                interestingness["full_log"] = self._binding(
                    "reproducers/scf/interesting-full.log", fake_log
                )

            self._rewrite_receipts(bundle, current, mutate)

        self._reject(fake_predicate, "predicate bytes|independently reconstructed")

    def _rewrite_receipts(self, bundle: Path, current: Path, mutate) -> None:
        receipt = json.loads((bundle / "run-1/receipt.json").read_text(encoding="utf-8"))
        mutate(receipt)
        receipt["sha256"] = MODULE._canonical_receipt_hash(receipt)
        payload = self._json_bytes(receipt)
        current.write_bytes(payload)
        for run_name in ("run-1", "run-2"):
            (bundle / run_name / "receipt.json").write_bytes(payload)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        binding = {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for run_name in ("run-1", "run-2"):
            manifest["runs"][run_name]["files"]["receipt.json"] = binding
            manifest["runs"][run_name]["receipt_self_hash"] = receipt["sha256"]
        manifest["expected_comparison"]["receipt_file_sha256"] = binding["sha256"]
        manifest["expected_comparison"]["receipt_self_hash"] = receipt["sha256"]
        manifest_path.write_bytes(self._json_bytes(manifest))

    def _replace_canonical_file(
        self,
        bundle: Path,
        reproducers: Path,
        filename: str,
        payload: bytes,
    ) -> None:
        for run_name in ("run-1", "run-2"):
            (bundle / run_name / filename).write_bytes(payload)
        (reproducers / filename).write_bytes(payload)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        binding = {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for run_name in ("run-1", "run-2"):
            manifest["runs"][run_name]["files"][filename] = binding
        manifest_path.write_bytes(self._json_bytes(manifest))

    def _add_canonical_file(
        self,
        bundle: Path,
        reproducers: Path,
        filename: str,
        payload: bytes,
    ) -> None:
        self._replace_canonical_file(bundle, reproducers, filename, payload)
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["canonical_files"] = sorted([*manifest["canonical_files"], filename])
        manifest_path.write_bytes(self._json_bytes(manifest))

    def _remove_canonical_file(
        self, bundle: Path, reproducers: Path, filename: str
    ) -> None:
        for run_name in ("run-1", "run-2"):
            (bundle / run_name / filename).unlink()
        (reproducers / filename).unlink()
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["canonical_files"].remove(filename)
        for run_name in ("run-1", "run-2"):
            manifest["runs"][run_name]["files"].pop(filename)
        manifest_path.write_bytes(self._json_bytes(manifest))

    def _reject(self, mutate, pattern: str) -> None:
        root, bundle, trust, current, reproducers = self._fixture()
        mutate(root, bundle, current, reproducers)
        with mock.patch.object(MODULE, "_independent_v5_trust", return_value=trust):
            with self.assertRaisesRegex(MODULE.VerificationError, pattern):
                MODULE.verify_public_v5_evidence(root, bundle)

    def test_public_compiler_branch_rejects_crossed_files_and_manifest_injection(self) -> None:
        cases = {
            "crossed control file": (
                lambda _r, b, _c, p: self._add_canonical_file(
                    b, p, "minimal-reproducer.json", b'{}\n'
                ),
                "directory contents",
            ),
            "manifest injection": (
                lambda _r, b, c, _p: self._rewrite_receipts(
                    b, c, lambda receipt: receipt["frontier_evidence"].__setitem__("manifest", {})
                ),
                "compiler frontier.manifest",
            ),
        }
        for name, (mutate, pattern) in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, pattern)

    def test_public_compiler_branch_rejects_missing_log_input_or_tool_binding(self) -> None:
        cases = {
            "log": (
                lambda _r, b, _c, p: self._remove_canonical_file(b, p, "scf.log"),
                "missing scf log|directory contents",
            ),
            "input": (
                lambda _r, b, _c, p: self._remove_canonical_file(b, p, "full-input.gz"),
                "full input|directory contents",
            ),
            "tool binding": (
                lambda _r, b, c, _p: self._rewrite_receipts(
                    b,
                    c,
                    lambda receipt: receipt["registered_build_execution"]["scf"].__setitem__(
                        "derivation_tool_bindings", []
                    ),
                ),
                "tool binding|derivation/tool",
            ),
        }
        for name, (mutate, pattern) in cases.items():
            with self.subTest(name=name):
                self._reject(mutate, pattern)

    def test_public_compiler_branch_rejects_zero_exit_and_environmental_diagnostic(self) -> None:
        def zero_exit(_root, bundle, current, _reproducers):
            def mutate(receipt):
                receipt["stages"][-1]["exit_code"] = 0
                receipt["registered_build_execution"]["scf"]["exit_code"] = 0
                receipt["frontier_evidence"]["interestingness"]["expected_exit"] = 0
            self._rewrite_receipts(bundle, current, mutate)

        def environment(_root, bundle, current, reproducers):
            diagnostic = (
                "error: cannot connect to socket at "
                "'/nix/var/nix/daemon-socket/socket': Permission denied"
            )
            command = [
                "nix", "build", "--no-link", "--print-out-paths", "-L",
                ".#tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-scf",
            ]
            payload = MODULE._canonical_execution_evidence(
                command,
                subprocess.CompletedProcess(command, 1, "", diagnostic + "\n"),
            )
            self._replace_canonical_file(bundle, reproducers, "scf.log", payload)

            def mutate(receipt):
                receipt["diagnostic"] = diagnostic
                receipt["frontier_evidence"]["diagnostic"] = diagnostic
                receipt["frontier_evidence"]["interestingness"][
                    "normalized_terminal_diagnostic"
                ] = diagnostic
                receipt["stages"][-1]["terminal_diagnostics"] = [diagnostic]
                for value in (
                    receipt["stages"][-1],
                    receipt["registered_build_execution"]["scf"],
                ):
                    value["log_bytes"] = len(payload)
                    value["log_sha256"] = hashlib.sha256(payload).hexdigest()
            self._rewrite_receipts(bundle, current, mutate)

        for name, mutate, pattern in (
            ("zero exit", zero_exit, "nonzero exit|replay exit"),
            ("environment", environment, "environmental/Nix failure"),
        ):
            with self.subTest(name=name):
                self._reject(mutate, pattern)

    def test_public_compiler_branch_rejects_operation_type_and_combined_mutations(self) -> None:
        cases = {
            "operation": lambda receipt: receipt["frontier_evidence"].__setitem__(
                "operation", "scf.while"
            ),
            "types": lambda receipt: receipt["frontier_evidence"].__setitem__(
                "types", "(i1) -> i1"
            ),
            "combined": lambda receipt: (
                receipt["frontier_evidence"].__setitem__("operation", "scf.while"),
                receipt["registered_build_execution"]["scf"].__setitem__(
                    "derivation_tool_bindings", []
                ),
                receipt["stages"][-1].__setitem__("exit_code", 0),
            ),
        }
        for name, receipt_mutation in cases.items():
            with self.subTest(name=name):
                self._reject(
                    lambda _r, b, c, _p, m=receipt_mutation: self._rewrite_receipts(b, c, m),
                    "operation/types|tool binding|nonzero exit|replay exit",
                )

    def test_public_compiler_branch_rejects_schema_and_type_mutations(self) -> None:
        cases = {
            "extra frontier key": lambda receipt: receipt["frontier_evidence"].__setitem__(
                "invented", None
            ),
            "missing interestingness key": lambda receipt: receipt["frontier_evidence"][
                "interestingness"
            ].pop("full_log"),
            "extra minimization key": lambda receipt: receipt["frontier_evidence"][
                "minimization"
            ].__setitem__("invented", None),
            "boolean exit": lambda receipt: receipt["frontier_evidence"][
                "interestingness"
            ].__setitem__("expected_exit", True),
            "list operation": lambda receipt: receipt["frontier_evidence"].__setitem__(
                "operation", []
            ),
            "string failed result": lambda receipt: receipt[
                "registered_build_execution"
            ]["scf"].__setitem__("result", "/nix/store/invented"),
        }
        for name, receipt_mutation in cases.items():
            with self.subTest(name=name):
                self._reject(
                    lambda _r, b, c, _p, m=receipt_mutation: self._rewrite_receipts(b, c, m),
                    "schema|JSON type",
                )

    def test_public_compiler_branch_rejects_extra_missing_and_nonregular_entries(self) -> None:
        cases = {
            "extra": lambda _r, b, _c, _p: (b / "run-1/extra").write_bytes(b"extra"),
            "missing": lambda _r, b, _c, _p: (b / "run-2/scf.log").unlink(),
            "symlink": lambda _r, b, _c, _p: (
                (b / "run-1/scf.log").unlink(),
                (b / "run-1/scf.log").symlink_to("linalg.log"),
            ),
            "subdir": lambda _r, b, _c, _p: (b / "run-2/subdir").mkdir(),
            "nonregular": lambda _r, _b, _c, p: os.mkfifo(p / "fifo"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._reject(
                    mutate,
                    "directory contents|regular files|public reproducer|missing scf log",
                )


class GeneratedMlirDiffScopeTest(unittest.TestCase):
    def test_only_three_live_bound_generated_mlir_files_disable_git_diff(self) -> None:
        generated = [
            "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/flat.scf.mlir",
            "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-2/flat.scf.mlir",
            "reproducers/flat-scf/flat.scf.mlir",
        ]
        ordinary = "tests/fixtures/redundant_integer_casts.mlir"
        result = subprocess.run(
            ["git", "check-attr", "diff", "--", *generated, ordinary],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        values = {
            line.split(": ", 2)[0]: line.split(": ", 2)[2]
            for line in result.stdout.splitlines()
        }
        self.assertEqual([values[path] for path in generated], ["unset"] * 3)
        self.assertEqual(values[ordinary], "unspecified")


class SuccessorFrontierDeterminismBundleTest(unittest.TestCase):
    @staticmethod
    def _load_verifier():
        if not SUCCESSOR_SCRIPT.is_file():
            raise AssertionError(f"missing successor verifier: {SUCCESSOR_SCRIPT}")
        spec = importlib.util.spec_from_file_location(
            "exact_successor_frontier_determinism", SUCCESSOR_SCRIPT
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {SUCCESSOR_SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_two_successor_captures_are_byte_identical_and_fully_bound(self) -> None:
        self.assertTrue(SUCCESSOR_SCRIPT.is_file())
        self.assertTrue(SUCCESSOR_BUNDLES.is_dir())
        verifier = self._load_verifier()

        result = verifier.verify_successor_bundles(SUCCESSOR_BUNDLES)

        self.assertEqual(result["runs"], ["run-1", "run-2"])
        self.assertTrue(result["byte_identical"])
        self.assertEqual(result["frontier_operation"], "torch.aten.bitwise_left_shift.Tensor_Scalar")
        self.assertEqual(result["pre_reduce_right_shift_count"], 0)
        self.assertGreater(result["raw_right_shift_count"], 0)
        self.assertGreater(result["raw_left_shift_count"], 0)

    def test_successor_verifier_rejects_a_mutated_full_failing_input(self) -> None:
        self.assertTrue(SUCCESSOR_SCRIPT.is_file())
        self.assertTrue(SUCCESSOR_BUNDLES.is_dir())
        verifier = self._load_verifier()
        with tempfile.TemporaryDirectory(prefix="exact-successor-mutation-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(SUCCESSOR_BUNDLES, mutated)
            archive = mutated / "run-2" / "full-failing-ir.mlir.gz"
            changed = bytearray(archive.read_bytes())
            changed[-1] ^= 1
            archive.write_bytes(changed)

            with self.assertRaisesRegex(verifier.VerificationError, "SHA-256"):
                verifier.verify_successor_bundles(mutated)


class LeftShiftSuccessDeterminismBundleTest(unittest.TestCase):
    def test_two_registered_torch_success_captures_are_byte_identical_and_bound(self) -> None:
        verifier = SuccessorFrontierDeterminismBundleTest._load_verifier()

        result = verifier.verify_success_bundles(LEFT_SHIFT_SUCCESS_BUNDLES)

        self.assertEqual(result["runs"], ["run-1", "run-2"])
        self.assertTrue(result["byte_identical"])
        self.assertEqual(result["status"], "registered_torch_valid")
        self.assertGreater(result["artifact_bytes"], 0)
        self.assertEqual(result["task_identity_count"], 3)

    def test_success_verifier_rejects_a_mutated_registered_torch_artifact(self) -> None:
        verifier = SuccessorFrontierDeterminismBundleTest._load_verifier()
        with tempfile.TemporaryDirectory(prefix="exact-left-success-mutation-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(LEFT_SHIFT_SUCCESS_BUNDLES, mutated)
            archive = mutated / "run-2" / "torch-artifact.mlir.gz"
            changed = bytearray(archive.read_bytes())
            changed[-1] ^= 1
            archive.write_bytes(changed)

            with self.assertRaisesRegex(verifier.VerificationError, "SHA-256"):
                verifier.verify_success_bundles(mutated)


class NestedHistoricalBundleFilesystemBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = SuccessorFrontierDeterminismBundleTest._load_verifier()

    def test_successor_public_verifier_rejects_unlisted_later_stage_logs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-successor-extra-log-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(SUCCESSOR_BUNDLES, mutated)
            for run_name in ("run-1", "run-2"):
                (mutated / run_name / "flat-scf.log").write_text(
                    "later stage must not exist\n", encoding="utf-8"
                )

            with self.assertRaisesRegex(self.verifier.VerificationError, "run directory contents"):
                self.verifier.verify_successor_bundles(mutated)

    def test_success_public_verifier_rejects_unlisted_later_stage_logs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-success-extra-log-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(LEFT_SHIFT_SUCCESS_BUNDLES, mutated)
            for run_name in ("run-1", "run-2"):
                (mutated / run_name / "flat-scf.log").write_text(
                    "later stage must not exist\n", encoding="utf-8"
                )

            with self.assertRaisesRegex(self.verifier.VerificationError, "run directory contents"):
                self.verifier.verify_success_bundles(mutated)

    def test_both_public_verifiers_reject_unlisted_hidden_files(self) -> None:
        cases = (
            (SUCCESSOR_BUNDLES, self.verifier.verify_successor_bundles),
            (LEFT_SHIFT_SUCCESS_BUNDLES, self.verifier.verify_success_bundles),
        )
        for source, verify in cases:
            with self.subTest(bundle=source.name), tempfile.TemporaryDirectory(
                prefix="exact-historical-hidden-"
            ) as temporary:
                mutated = Path(temporary) / "bundles"
                shutil.copytree(source, mutated)
                (mutated / "run-1" / ".flat-scf.mlir").write_text(
                    "module {}\n", encoding="utf-8"
                )

                with self.assertRaisesRegex(self.verifier.VerificationError, "run directory contents"):
                    verify(mutated)

    def test_nested_verifiers_reject_missing_files_and_symlink_substitution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-successor-missing-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(SUCCESSOR_BUNDLES, mutated)
            (mutated / "run-2" / "torch-mlir.log").unlink()
            with self.assertRaisesRegex(self.verifier.VerificationError, "run directory contents"):
                self.verifier.verify_successor_bundles(mutated)

        with tempfile.TemporaryDirectory(prefix="exact-success-symlink-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(LEFT_SHIFT_SUCCESS_BUNDLES, mutated)
            target = mutated / "receipt-target.json"
            receipt = mutated / "run-1" / "receipt.json"
            target.write_bytes(receipt.read_bytes())
            receipt.unlink()
            receipt.symlink_to(target)
            with self.assertRaisesRegex(self.verifier.VerificationError, "regular file"):
                self.verifier.verify_success_bundles(mutated)

    def test_both_public_verifiers_reject_unexpected_subdirectories(self) -> None:
        cases = (
            (SUCCESSOR_BUNDLES, self.verifier.verify_successor_bundles),
            (LEFT_SHIFT_SUCCESS_BUNDLES, self.verifier.verify_success_bundles),
        )
        for source, verify in cases:
            with self.subTest(bundle=source.name), tempfile.TemporaryDirectory(
                prefix="exact-historical-subdir-"
            ) as temporary:
                mutated = Path(temporary) / "bundles"
                shutil.copytree(source, mutated)
                (mutated / "run-2" / ".later-stage").mkdir()

                with self.assertRaisesRegex(self.verifier.VerificationError, "run directory contents"):
                    verify(mutated)

    def test_public_verifier_rejects_nonregular_special_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-historical-fifo-") as temporary:
            mutated = Path(temporary) / "bundles"
            shutil.copytree(SUCCESSOR_BUNDLES, mutated)
            os.mkfifo(mutated / "run-1" / ".later-stage.fifo")

            with self.assertRaisesRegex(self.verifier.VerificationError, "regular files"):
                self.verifier.verify_successor_bundles(mutated)


if __name__ == "__main__":
    unittest.main()
