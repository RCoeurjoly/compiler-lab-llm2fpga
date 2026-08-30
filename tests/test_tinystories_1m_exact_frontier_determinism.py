"""Verification tests for preserved live Task 5 determinism bundles."""

from __future__ import annotations

import importlib.util
import copy
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "pipeline"
    / "verify_tinystories_1m_exact_frontier_determinism.py"
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
