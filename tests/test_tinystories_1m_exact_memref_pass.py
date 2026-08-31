#!/usr/bin/env python3
"""Behavioral contract for the exact TinyStories memref-pass evaluation."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "scripts/pipeline/evaluate_tinystories_1m_exact_memref_pass.py"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py"
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
EVALUATION = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
EVIDENCE = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evidence"
RESULT = ROOT / "docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REGISTERED = {
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
}
CLASSIFICATIONS = {
    "eliminated",
    "preserved",
    "rewritten_equivalent",
    "new_invalid",
}
TOOL_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
PLUGIN_SHA256 = "6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_rehash(value: dict) -> dict:
    value["sha256"] = None
    value["sha256"] = sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    return value


def binding(path: Path) -> dict:
    data = path.read_bytes()
    try:
        rendered = str(path.relative_to(ROOT))
    except ValueError:
        rendered = str(path)
    return {"path": rendered, "bytes": len(data), "sha256": sha256(data)}


class ProductionSurfaceTest(unittest.TestCase):
    def test_all_task3_production_surfaces_exist(self) -> None:
        for path in (EVALUATOR, VERIFIER, EVALUATION, EVIDENCE, RESULT):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"absent Task 3 surface: {path}")


@unittest.skipUnless(EVALUATOR.is_file(), "Task 3 evaluator not implemented")
class EvaluatorUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module(EVALUATOR, "exact_memref_pass_evaluator_unit")

    def test_signature_classifier_distinguishes_all_four_states(self) -> None:
        before = {
            "operation": "memref.copy",
            "operand_memrefs": [{"shape": [2], "strides": [1], "offset": 0}],
            "result_memrefs": [],
        }
        equivalent = copy.deepcopy(before)
        equivalent["operand_memrefs"][0]["text"] = "memref<2xi64>"
        exact = copy.deepcopy(equivalent)
        self.assertEqual(
            self.module.classify_signature(before, [], valid=True), "eliminated"
        )
        self.assertEqual(
            self.module.classify_signature(exact, [exact], valid=True), "preserved"
        )
        self.assertEqual(
            self.module.classify_signature(before, [equivalent], valid=True),
            "rewritten_equivalent",
        )
        self.assertEqual(
            self.module.classify_signature(before, [], valid=False), "new_invalid"
        )

    def test_decision_gate_is_exact_and_fail_closed(self) -> None:
        zero = {name: 0 for name in REGISTERED}
        self.assertEqual(
            self.module.apply_decision_gate(
                parseable=True,
                blocker_counts=zero,
                invalid_signatures=[],
                unknown_blocker_classes=[],
                invariant_status="proven",
            ),
            "register_existing_pass",
        )
        for mutation in (
            {"parseable": False},
            {"blocker_counts": {**zero, "memref.copy": 1}},
            {"invalid_signatures": ["bad"]},
            {"unknown_blocker_classes": ["memref.subview"]},
            {"invariant_status": "unavailable_due_invalid_output"},
            {"invariant_status": "unproven"},
        ):
            args = {
                "parseable": True,
                "blocker_counts": zero,
                "invalid_signatures": [],
                "unknown_blocker_classes": [],
                "invariant_status": "proven",
            }
            args.update(mutation)
            self.assertEqual(
                self.module.apply_decision_gate(**args), "compiler_pass_extension"
            )

    def test_post_pass_census_allows_eliminated_registered_classes(self) -> None:
        self.assertTrue(
            hasattr(self.module, "summarize_registered_operations"),
            "evaluator lacks a zero-tolerant post-pass census",
        )
        summary = self.module.summarize_registered_operations([])
        self.assertEqual(
            {name: summary["classes"][name]["count"] for name in REGISTERED},
            {name: 0 for name in REGISTERED},
        )

    def test_invalid_subview_frontier_is_canonicalized_from_exact_diagnostic(self) -> None:
        self.assertTrue(
            hasattr(self.module, "diagnose_invalid_frontier"),
            "evaluator does not classify a newly invalid operation",
        )
        parser = self.module._load_task2_extractor()
        source = """module {
  func.func @main(%arg: memref<64x64xi64>) {
    %view = memref.subview %arg[0, 0] [64, 1] [1, 1] : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    return
  }
}
"""
        diagnostic = (
            "input.mlir:3:13: error: expected 1 offset values, got 2\n"
            "input.mlir:3:13: note: see current operation: %0 = "
            '"memref.subview"(%arg)\n'
        ).encode()
        invalid = self.module.diagnose_invalid_frontier(diagnostic, source, parser)
        self.assertEqual(invalid["operation"], "memref.subview")
        self.assertEqual(invalid["source_location"]["line"], 3)
        self.assertEqual(invalid["signature"]["offsets"], [0, 0])
        self.assertEqual(invalid["signature"]["sizes"], [64, 1])
        self.assertEqual(invalid["signature"]["strides"], [1, 1])


@unittest.skipUnless(EVALUATION.is_file(), "Task 3 evidence not produced")
class CommittedEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT.read_bytes()
        cls.contract = json.loads(cls.contract_bytes)
        cls.evaluation_bytes = EVALUATION.read_bytes()
        cls.payload = json.loads(cls.evaluation_bytes)

    def test_inputs_tools_plugin_and_pipeline_are_exactly_pinned(self) -> None:
        payload = self.payload
        self.assertEqual(payload["schema"], "tinystories-1m-exact-memref-pass-v1")
        self.assertEqual(sha256(self.contract_bytes), CONTRACT_SHA256)
        self.assertEqual(payload["task2_contract"]["sha256"], CONTRACT_SHA256)
        self.assertEqual(payload["input"]["sha256"], FLAT_SCF_SHA256)
        self.assertFalse(payload["provenance"]["current_alias_realized"])
        self.assertEqual(
            payload["provenance"]["payload_source"],
            "retained-authenticated-c22-output",
        )
        self.assertEqual(payload["tool"]["sha256"], TOOL_SHA256)
        self.assertEqual(payload["plugin"]["sha256"], PLUGIN_SHA256)
        self.assertEqual(payload["pipeline"], PIPELINE)
        command_text = "\n".join(
            " ".join(run["command"]) for run in payload["executions"]
        ).lower()
        self.assertNotIn("calyx", command_text.replace("for-calyx", ""))
        self.assertNotIn("circt-opt", command_text)
        self.assertNotIn("lower-scf-to-calyx", command_text)

    def test_every_representative_precedes_the_complete_artifact(self) -> None:
        runs = self.payload["executions"]
        self.assertEqual(len(runs), len(REGISTERED) * 2 + 1)
        self.assertEqual([run["sequence"] for run in runs], list(range(1, 10)))
        self.assertEqual({run["operation"] for run in runs[:4]}, REGISTERED)
        self.assertTrue(all(run["kind"] == "representative" for run in runs[:4]))
        self.assertEqual({run["operation"] for run in runs[4:8]}, REGISTERED)
        self.assertTrue(all(run["kind"] == "semantic_probe" for run in runs[4:8]))
        self.assertEqual(runs[-1]["kind"], "complete")
        self.assertEqual(runs[-1]["input"]["sha256"], FLAT_SCF_SHA256)

    def test_exact_execution_bytes_are_retained_and_outputs_parse(self) -> None:
        tool = Path(self.payload["tool"]["path"])
        for run in self.payload["executions"]:
            with self.subTest(run=run["id"]):
                self.assertGreater(run["elapsed_ns"], 0)
                for stream in ("stdout", "stderr", "output"):
                    binding = run[stream]
                    path = ROOT / binding["path"]
                    data = path.read_bytes()
                    self.assertEqual(len(data), binding["bytes"])
                    self.assertEqual(sha256(data), binding["sha256"])
                if run["kind"] in {"representative", "semantic_probe"} or run["parseable"]:
                    self.assertEqual(run["exit_code"], 0)
                    parsed = subprocess.run(
                        [str(tool), str(ROOT / run["output"]["path"]), "-o", "/dev/null"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    self.assertEqual(parsed.returncode, 0, parsed.stderr.decode(errors="replace"))
                else:
                    self.assertNotEqual(run["exit_code"], 0)
                    self.assertGreater(run["stderr"]["bytes"], 0)

    def test_before_after_censuses_and_all_signature_mappings_are_complete(self) -> None:
        complete = self.payload["complete"]
        expected_before = {
            name: self.contract["classes"][name]["count"] for name in REGISTERED
        }
        self.assertEqual(complete["before"]["blocker_counts"], expected_before)
        self.assertEqual(
            sum(complete["before"]["blocker_counts"].values()), 20_280
        )
        mappings = complete["signature_mappings"]
        expected_hashes = {
            entry["signature_sha256"]
            for item in self.contract["classes"].values()
            for entry in item["signatures"]
        }
        self.assertEqual({entry["input_signature_sha256"] for entry in mappings}, expected_hashes)
        self.assertEqual(len(mappings), 895)
        self.assertTrue(
            all(entry["classification"] in CLASSIFICATIONS for entry in mappings)
        )
        self.assertEqual(complete["unknown_blocker_classes"], [])
        if complete["parseable"]:
            self.assertEqual(complete["new_invalid_signatures"], [])
            self.assertEqual(complete["invariant_status"], "proven")
        else:
            self.assertEqual(
                complete["invariant_status"], "unavailable_due_invalid_output"
            )
            self.assertEqual(len(complete["new_invalid_signatures"]), 1)
            self.assertEqual(
                complete["new_invalid_signatures"][0]["operation"], "memref.subview"
            )

    def test_decision_and_successor_identity_follow_only_the_exact_gate(self) -> None:
        complete = self.payload["complete"]
        gate_satisfied = (
            complete["parseable"]
            and all(value == 0 for value in complete["after"]["blocker_counts"].values())
            and not complete["new_invalid_signatures"]
            and not complete["unknown_blocker_classes"]
            and complete["invariant_status"] == "proven"
        )
        expected = "register_existing_pass" if gate_satisfied else "compiler_pass_extension"
        self.assertEqual(self.payload["decision"], expected)
        if expected == "register_existing_pass":
            normalized = self.payload["normalized_artifact"]
            self.assertEqual(
                normalized["sha256"],
                self.payload["executions"][-1]["output"]["sha256"],
            )
            self.assertNotIn("earliest_remaining_signature", self.payload)
        else:
            earliest = self.payload["earliest_remaining_signature"]
            self.assertEqual(
                earliest["operation"], complete["new_invalid_signatures"][0]["operation"]
            )
            reproducer = ROOT / earliest["reproducer"]["path"]
            self.assertEqual(sha256(reproducer.read_bytes()), earliest["reproducer"]["sha256"])
            self.assertEqual(earliest["reproducer"]["operation_count"], 1)

    def test_semantically_live_probes_prove_shape_layout_and_access_maps(self) -> None:
        self.assertIn(
            "semantic_probes", self.payload,
            "evaluation lacks semantically live representative probes",
        )
        probes = self.payload["semantic_probes"]
        self.assertEqual({probe["operation"] for probe in probes}, REGISTERED)
        self.assertTrue(all(probe["invariant_status"] == "proven" for probe in probes))
        for probe in probes:
            with self.subTest(operation=probe["operation"]):
                self.assertTrue(probe["before"]["access_maps"])
                self.assertEqual(
                    probe["before"]["access_maps"], probe["after"]["access_maps"]
                )
                self.assertEqual(
                    probe["before"]["element_count"],
                    probe["after"]["element_count"],
                )
                self.assertTrue(probe["checks"]["shape_layout_access_equivalent"])


@unittest.skipUnless(VERIFIER.is_file() and EVALUATION.is_file(), "Task 3 verifier absent")
class PublicVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_module(VERIFIER, "exact_memref_pass_verifier_attacks")
        cls.payload = json.loads(EVALUATION.read_bytes())

    def test_public_verifier_replays_the_exact_evaluation(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VERIFIER)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        self.assertIn(b"PASS", completed.stdout)

    def test_verifier_rejects_mutated_hash_pipeline_order_and_semantics(self) -> None:
        attacks = []
        wrong_hash = copy.deepcopy(self.payload)
        wrong_hash["input"]["sha256"] = "0" * 64
        attacks.append(("input SHA-256", canonical_rehash(wrong_hash)))
        wrong_pipeline = copy.deepcopy(self.payload)
        wrong_pipeline["pipeline"] += ",canonicalize"
        attacks.append(("pipeline", canonical_rehash(wrong_pipeline)))
        wrong_order = copy.deepcopy(self.payload)
        wrong_order["executions"][0], wrong_order["executions"][-1] = (
            wrong_order["executions"][-1],
            wrong_order["executions"][0],
        )
        attacks.append(("representative order", canonical_rehash(wrong_order)))
        wrong_invariant = copy.deepcopy(self.payload)
        wrong_invariant["complete"]["invariant_status"] = "proven"
        attacks.append(("invariant status", canonical_rehash(wrong_invariant)))
        wrong_unknown = copy.deepcopy(self.payload)
        wrong_unknown["complete"]["unknown_blocker_classes"] = ["memref.subview"]
        attacks.append(("unknown blocker", canonical_rehash(wrong_unknown)))
        wrong_census = copy.deepcopy(self.payload)
        wrong_census["complete"]["before"]["operation_census"]["memref.load"] += 1
        attacks.append(("operation census", canonical_rehash(wrong_census)))
        for message, payload in attacks:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.verifier.validate_payload(payload, ROOT, replay=False)

    def test_verifier_rejects_launcher_and_task2_identity_rebound(self) -> None:
        attacks = []
        launcher = copy.deepcopy(self.payload)
        launcher["python"]["path"] = "/bin/true"
        attacks.append(("python interpreter", canonical_rehash(launcher)))
        model = copy.deepcopy(self.payload)
        model["model"] = "rebound-model"
        model["python"]["path"] = "/bin/true"
        attacks.append(("model", canonical_rehash(model)))
        identities = copy.deepcopy(self.payload)
        identities["task_1_through_3_identities"] = {"rebound": "identity"}
        identities["python"]["path"] = "/bin/true"
        attacks.append(("Task 1--3 identities", canonical_rehash(identities)))
        provenance = copy.deepcopy(self.payload)
        provenance["provenance"].update(
            {
                "payload_source": "rebound",
                "c22_derivation": "/nix/store/rebound-c22.drv",
                "c22_output": "/nix/store/rebound-c22",
                "current_alias_derivation": "/nix/store/rebound-current.drv",
                "current_alias_output": "/nix/store/rebound-current",
                "current_alias_realized": True,
                "unrealized_current_alias_residual": "rebound",
            }
        )
        provenance["python"]["path"] = "/bin/true"
        attacks.append(("provenance", canonical_rehash(provenance)))
        for message, payload in attacks:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.verifier.validate_payload(payload, ROOT, replay=False)

    def test_verifier_rejects_rebound_authenticated_representative_during_replay(self) -> None:
        contract = json.loads(CONTRACT.read_bytes())
        representative = ROOT / contract["classes"]["memref.collapse_shape"][
            "representative"
        ]["path"]
        original = representative.read_bytes()
        payload = copy.deepcopy(self.payload)
        try:
            representative.write_bytes(
                original + b"\n// authenticated representative rebound attack\n"
            )
            payload["executions"][0]["input"] = binding(representative)
            payload["executions"][0]["input_after"] = binding(representative)
            payload["python"]["path"] = "/bin/true"
            canonical_rehash(payload)
            with self.assertRaisesRegex(ValueError, "representative binding"):
                self.verifier.validate_payload(payload, ROOT, replay=True)
        finally:
            representative.write_bytes(original)

    def test_verifier_rejects_rebound_parse_command_and_streams(self) -> None:
        report_binding = binding(RESULT)
        attacks = []
        wrong_command = copy.deepcopy(self.payload)
        wrong_command["executions"][0]["parse_check"]["command"] = ["/bin/true"]
        attacks.append(("parse command", canonical_rehash(wrong_command)))
        wrong_stdout = copy.deepcopy(self.payload)
        wrong_stdout["executions"][0]["parse_check"]["stdout"] = report_binding
        attacks.append(("parse stdout", canonical_rehash(wrong_stdout)))
        wrong_stderr = copy.deepcopy(self.payload)
        wrong_stderr["executions"][0]["parse_check"]["stderr"] = report_binding
        attacks.append(("parse stderr", canonical_rehash(wrong_stderr)))
        wrong_exit = copy.deepcopy(self.payload)
        wrong_exit["executions"][0]["parse_check"]["exit_code"] = 99
        attacks.append(("parse exit", canonical_rehash(wrong_exit)))
        for message, payload in attacks:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.verifier.validate_payload(payload, ROOT, replay=True)

    def test_verifier_rejects_rebound_reproducer_command_exit_and_streams(self) -> None:
        metadata_path = ROOT / self.payload["earliest_remaining_signature"][
            "reproducer"
        ]["metadata"]["path"]
        original = metadata_path.read_bytes()
        base_metadata = json.loads(original)
        report_binding = binding(RESULT)
        complete_stderr = self.payload["executions"][-1]["stderr"]
        mutations = {
            "reproducer command": ("command", ["/bin/true"]),
            "reproducer exit": ("exit_code", 99),
            "reproducer stdout": ("stdout", report_binding),
            "reproducer stderr": ("stderr", complete_stderr),
            "reproducer output": ("output", report_binding),
        }
        try:
            for message, (field, value) in mutations.items():
                with self.subTest(message=message):
                    metadata = copy.deepcopy(base_metadata)
                    metadata["execution"][field] = value
                    metadata_path.write_bytes(
                        json.dumps(
                            metadata,
                            sort_keys=True,
                            separators=(",", ":"),
                            allow_nan=False,
                        ).encode()
                        + b"\n"
                    )
                    payload = copy.deepcopy(self.payload)
                    payload["earliest_remaining_signature"]["reproducer"][
                        "metadata"
                    ] = binding(metadata_path)
                    canonical_rehash(payload)
                    with self.assertRaisesRegex(ValueError, message):
                        self.verifier.validate_payload(payload, ROOT, replay=True)
        finally:
            metadata_path.write_bytes(original)

    def test_verifier_rejects_semantic_probe_mutation(self) -> None:
        self.assertIn(
            "semantic_probes", self.payload,
            "evaluation lacks semantic probes for mutation testing",
        )
        payload = copy.deepcopy(self.payload)
        payload["semantic_probes"][0]["after"]["access_maps"][0][
            "linear_index"
        ] += 1
        canonical_rehash(payload)
        with self.assertRaisesRegex(ValueError, "semantic probe"):
            self.verifier.validate_payload(payload, ROOT, replay=False)

    def test_elapsed_time_is_positive_authenticated_observation_not_replay_equality(self) -> None:
        invalid = copy.deepcopy(self.payload)
        invalid["executions"][0]["elapsed_ns"] = 0
        canonical_rehash(invalid)
        with self.assertRaisesRegex(ValueError, "elapsed time invalid"):
            self.verifier.validate_payload(invalid, ROOT, replay=False)
        payload = copy.deepcopy(self.payload)
        payload["executions"][0]["elapsed_ns"] += 1_000_000_000
        metadata_path = ROOT / payload["earliest_remaining_signature"]["reproducer"][
            "metadata"
        ]["path"]
        original = metadata_path.read_bytes()
        try:
            metadata = json.loads(original)
            metadata["execution"]["elapsed_ns"] += 1_000_000_000
            metadata_path.write_bytes(
                json.dumps(
                    metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
                + b"\n"
            )
            payload["earliest_remaining_signature"]["reproducer"]["metadata"] = binding(
                metadata_path
            )
            canonical_rehash(payload)
            self.verifier.validate_payload(payload, ROOT, replay=True)
        finally:
            metadata_path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
