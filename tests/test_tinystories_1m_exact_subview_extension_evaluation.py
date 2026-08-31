#!/usr/bin/env python3
"""Authenticated replay contract for the exact static-subview extension."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = (
    ROOT / "scripts/pipeline/evaluate_tinystories_1m_exact_subview_extension.py"
)
VERIFIER = (
    ROOT / "scripts/pipeline/verify_tinystories_1m_exact_subview_extension.py"
)
EVALUATION = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json"
)
EVIDENCE = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence"
)
REPORT = (
    ROOT / "docs/results/2026-09-01-tinystories-1m-subview-extension-evaluation.md"
)
BASELINE = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json"
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
RUN_IDS = (
    "predecessor-task3-subview",
    "semantic-identity-offset",
    "semantic-nonzero-offset-stride",
    "complete-retained-c22-flat-scf",
)
TOOL_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
BASELINE_PLUGIN_SHA256 = (
    "6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744"
)
PLUGIN_SHA256 = "6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
BASELINE_SHA256 = "26e0ddcaf0abc6100332378d2cacf0555f3560a7635bcdd60dbb9f47bd5ad0d8"
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
EARLIEST_SIGNATURE_SHA256 = (
    "6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693"
)


def digest(data: bytes) -> str:
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
    value["sha256"] = digest(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    return value


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        rendered = str(path.relative_to(ROOT))
    except ValueError:
        rendered = str(path)
    return {"path": rendered, "bytes": len(raw), "sha256": digest(raw)}


class ProductionSurfaceTest(unittest.TestCase):
    def test_all_task3_surfaces_start_absent_then_must_exist(self) -> None:
        for path in (EVALUATOR, VERIFIER, EVALUATION, EVIDENCE, REPORT):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"absent Task 3 surface: {path}")


@unittest.skipUnless(EVALUATOR.is_file(), "Task 3 evaluator not implemented")
class EvaluatorUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module(EVALUATOR, "exact_subview_extension_evaluator_unit")

    def test_decision_gate_accepts_valid_output_with_measured_residuals(self) -> None:
        residuals = {name: index + 1 for index, name in enumerate(REGISTERED)}
        self.assertEqual(
            self.module.apply_decision_gate(
                parseable=True,
                blocker_counts=residuals,
                new_invalid_classes=[],
                semantic_status="proven",
            ),
            "valid_normalized_output",
        )
        for mutation in (
            {"parseable": False},
            {"blocker_counts": {**residuals, "unknown": 1}},
            {"blocker_counts": {**residuals, "memref.copy": None}},
            {"new_invalid_classes": ["memref.unknown_view"]},
            {"semantic_status": "unproven"},
        ):
            arguments = {
                "parseable": True,
                "blocker_counts": residuals,
                "new_invalid_classes": [],
                "semantic_status": "proven",
            }
            arguments.update(mutation)
            self.assertEqual(
                self.module.apply_decision_gate(**arguments),
                "next_compiler_frontier",
            )

    def test_affine_proof_rejects_non_affine_symbolic_products(self) -> None:
        source = """module {
  func.func @probe(%source: memref<4096xi64>, %i0: index, %i1: index) -> i64 {
    %product = arith.muli %i0, %i1 : index
    %value = memref.load %source[%product] : memref<4096xi64>
    return %value : i64
  }
}
"""
        proof = self.module.derive_affine_proof(
            source,
            probe_id="semantic-identity-offset",
        )
        self.assertEqual(proof["affine_status"], "unproven")

    def test_new_invalid_class_census_decodes_generic_operation_names(self) -> None:
        before = self.module.operation_census("module {\n}\n")
        after = self.module.operation_census(
            'module {\n  "memref.future\\5fview"() : () -> ()\n}\n'
        )
        self.assertEqual(after, {"memref.future_view": 1})
        self.assertEqual(
            self.module.new_invalid_classes(before, after),
            ["memref.future_view"],
        )


@unittest.skipUnless(EVALUATION.is_file(), "Task 3 evidence not produced")
class CommittedEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(EVALUATION.read_bytes())
        cls.baseline = json.loads(BASELINE.read_bytes())
        cls.contract = json.loads(CONTRACT.read_bytes())

    def test_immutable_model_task_contract_input_tool_and_plugins_are_pinned(self) -> None:
        payload = self.payload
        self.assertEqual(payload["schema"], "tinystories-1m-exact-subview-extension-v1")
        self.assertEqual(payload["status"], "evaluated")
        self.assertEqual(payload["model"], "tiny-stories-1m-kev-gpt-exact")
        self.assertEqual(digest(BASELINE.read_bytes()), BASELINE_SHA256)
        self.assertEqual(digest(CONTRACT.read_bytes()), CONTRACT_SHA256)
        self.assertEqual(payload["baseline_evaluation"]["sha256"], BASELINE_SHA256)
        self.assertEqual(payload["task2_contract"]["sha256"], CONTRACT_SHA256)
        self.assertEqual(payload["input"]["bytes"], 18_933_168)
        self.assertEqual(payload["input"]["sha256"], FLAT_SCF_SHA256)
        self.assertEqual(payload["tool"]["sha256"], TOOL_SHA256)
        self.assertEqual(payload["baseline_plugin"]["sha256"], BASELINE_PLUGIN_SHA256)
        self.assertEqual(payload["plugin"]["sha256"], PLUGIN_SHA256)
        self.assertNotEqual(payload["plugin"]["sha256"], payload["baseline_plugin"]["sha256"])
        self.assertEqual(payload["pipeline"], PIPELINE)
        self.assertEqual(
            payload["task_1_through_3_identities"],
            self.contract["task_1_through_3_identities"],
        )
        self.assertEqual(
            payload["baseline_observation"]["evaluation_self_sha256"],
            self.baseline["sha256"],
        )
        self.assertEqual(
            payload["baseline_observation"]["frontier_signature_sha256"],
            EARLIEST_SIGNATURE_SHA256,
        )

    def test_causal_execution_order_and_exact_commands_are_closed(self) -> None:
        runs = self.payload["executions"]
        self.assertEqual([run["sequence"] for run in runs], [1, 2, 3, 4])
        self.assertEqual([run["id"] for run in runs], list(RUN_IDS))
        self.assertEqual(
            [run["kind"] for run in runs],
            ["predecessor_reproducer", "semantic_probe", "semantic_probe", "complete"],
        )
        self.assertTrue(all(run["causal_preconditions_satisfied"] for run in runs))
        self.assertEqual(runs[-1]["input"]["sha256"], FLAT_SCF_SHA256)
        for run in runs:
            command = run["command"]
            self.assertEqual(command[0], self.payload["tool"]["path"])
            self.assertIn(
                f"--load-pass-plugin={self.payload['plugin']['path']}", command
            )
            self.assertIn(f"--pass-pipeline={PIPELINE}", command)
            lowered = " ".join(command).lower().replace("for-calyx", "")
            self.assertNotIn("calyx", lowered)
            self.assertNotIn("circt-opt", lowered)
            self.assertNotIn("lower-scf-to-calyx", lowered)

    def test_streams_outputs_and_parse_checks_are_exactly_retained(self) -> None:
        for run in self.payload["executions"]:
            with self.subTest(run=run["id"]):
                self.assertGreater(run["elapsed_ns"], 0)
                self.assertEqual(run["input"], run["input_after"])
                for stream in ("stdout", "stderr", "output"):
                    path = ROOT / run[stream]["path"]
                    self.assertEqual(binding(path), run[stream])
                for stream in ("stdout", "stderr"):
                    path = ROOT / run["parse_check"][stream]["path"]
                    self.assertEqual(binding(path), run["parse_check"][stream])
                expected_parseable = (
                    run["exit_code"] == 0
                    and run["parse_check"]["exit_code"] == 0
                )
                self.assertIs(run["parseable"], expected_parseable)

    def test_predecessor_and_both_complete_affine_proofs_precede_full_replay(self) -> None:
        predecessor = self.payload["predecessor_reproducer"]
        self.assertEqual(predecessor["signature_sha256"], EARLIEST_SIGNATURE_SHA256)
        self.assertEqual(predecessor["legalization_status"], "proven")
        self.assertTrue(all(predecessor["checks"].values()))
        probes = self.payload["semantic_probes"]
        self.assertEqual(
            [probe["id"] for probe in probes],
            ["semantic-identity-offset", "semantic-nonzero-offset-stride"],
        )
        expected = ((0, [64, 1]), (64, [128, 2]))
        for probe, (offset, coefficients) in zip(probes, expected):
            with self.subTest(probe=probe["id"]):
                self.assertEqual(probe["invariant_status"], "proven")
                self.assertTrue(all(probe["checks"].values()))
                for phase in ("before", "after"):
                    proof = probe[phase]
                    self.assertEqual(proof["affine_status"], "proven")
                    self.assertEqual(len(proof["index_variables"]), 2)
                    self.assertEqual(
                        {item["kind"] for item in proof["access_maps"]},
                        {"load", "store"},
                    )
                    for access in proof["access_maps"]:
                        self.assertEqual(access["linear_formula"]["offset"], offset)
                        self.assertEqual(
                            access["linear_formula"]["coefficients"], coefficients
                        )
                        self.assertEqual(access["base"]["argument"], 0)
                        self.assertTrue(all(item["range"]["in_bounds"] for item in access["raw_indices"]))

    def test_closed_decision_records_exact_residuals_or_one_frontier(self) -> None:
        complete = self.payload["complete"]
        expected_before = {
            name: self.contract["classes"][name]["count"] for name in REGISTERED
        }
        self.assertEqual(complete["before"]["registered_blocker_counts"], expected_before)
        self.assertEqual(set(complete["after"]["registered_blocker_counts"]), set(REGISTERED))
        gate = (
            complete["parseable"]
            and all(isinstance(value, int) for value in complete["after"]["registered_blocker_counts"].values())
            and not complete["new_invalid_classes"]
            and complete["invariant_status"] == "proven"
        )
        expected = "valid_normalized_output" if gate else "next_compiler_frontier"
        self.assertEqual(self.payload["decision"], expected)
        if expected == "valid_normalized_output":
            self.assertEqual(
                self.payload["normalized_artifact"],
                self.payload["executions"][-1]["output"],
            )
            self.assertNotIn("next_frontier", self.payload)
        else:
            self.assertNotIn("normalized_artifact", self.payload)
            frontier = self.payload["next_frontier"]
            self.assertIn(
                frontier["kind"],
                {"diagnostic", "new_invalid_class", "residual_registered_blocker"},
            )
            self.assertEqual(frontier["reproducer"]["operation_count"], 1)


@unittest.skipUnless(
    VERIFIER.is_file() and EVALUATION.is_file(), "Task 3 verifier/evidence absent"
)
class PublicVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_module(VERIFIER, "exact_subview_extension_verifier_attacks")
        cls.payload = json.loads(EVALUATION.read_bytes())

    def assert_rejected(self, label: str, payload: dict) -> None:
        with self.assertRaisesRegex(ValueError, label):
            self.verifier.validate_payload(payload, ROOT, replay=False)

    def test_public_verifier_replays_exact_commands_and_bytes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VERIFIER)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        self.assertIn(b"PASS", completed.stdout)

    def test_verifier_rejects_identity_pipeline_baseline_and_path_rebinding(self) -> None:
        attacks = []
        plugin = copy.deepcopy(self.payload)
        plugin["plugin"]["path"] = plugin["baseline_plugin"]["path"]
        attacks.append(("plugin identity", canonical_rehash(plugin)))
        source = copy.deepcopy(self.payload)
        source["input"]["sha256"] = "0" * 64
        attacks.append(("input identity", canonical_rehash(source)))
        baseline = copy.deepcopy(self.payload)
        baseline["baseline_observation"]["evaluation_self_sha256"] = "0" * 64
        attacks.append(("baseline observation", canonical_rehash(baseline)))
        pipeline = copy.deepcopy(self.payload)
        pipeline["pipeline"] += ",canonicalize"
        attacks.append(("pipeline", canonical_rehash(pipeline)))
        command = copy.deepcopy(self.payload)
        command["executions"][0]["command"][1] = str(REPORT)
        attacks.append(("exact pass command", canonical_rehash(command)))
        evidence_path = copy.deepcopy(self.payload)
        evidence_path["executions"][0]["stdout"] = binding(REPORT)
        attacks.append(("canonical evidence path", canonical_rehash(evidence_path)))
        stale_output = copy.deepcopy(self.payload)
        stale_output["executions"][-1]["output"] = copy.deepcopy(
            stale_output["baseline_observation"]["complete_output"]
        )
        attacks.append(("canonical evidence path", canonical_rehash(stale_output)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_open_schemas_and_crossed_decision_union(self) -> None:
        attacks = []
        top = copy.deepcopy(self.payload)
        top["registration_claim"] = True
        attacks.append(("top-level schema", canonical_rehash(top)))
        run = copy.deepcopy(self.payload)
        run["executions"][0]["registration_claim"] = True
        attacks.append(("execution schema", canonical_rehash(run)))
        complete = copy.deepcopy(self.payload)
        complete["complete"]["registration_claim"] = True
        attacks.append(("complete schema", canonical_rehash(complete)))
        crossed = copy.deepcopy(self.payload)
        if crossed["decision"] == "valid_normalized_output":
            crossed["next_frontier"] = {
                "kind": "residual_registered_blocker",
                "operation": "memref.copy",
            }
        else:
            crossed["normalized_artifact"] = copy.deepcopy(
                crossed["executions"][-1]["output"]
            )
        attacks.append(("decision schema", canonical_rehash(crossed)))
        wrong_status = copy.deepcopy(self.payload)
        wrong_status["status"] = "registered"
        attacks.append(("status", canonical_rehash(wrong_status)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_false_valid_claim_counts_and_new_classes(self) -> None:
        counts = copy.deepcopy(self.payload)
        current = counts["complete"]["after"]["registered_blocker_counts"]["memref.copy"]
        counts["complete"]["after"]["registered_blocker_counts"]["memref.copy"] = (
            0 if current is None else current + 1
        )
        attacks = [("after blocker census", canonical_rehash(counts))]
        new_class = copy.deepcopy(self.payload)
        new_class["complete"]["new_invalid_classes"] = ["memref.fake_view"]
        attacks.append(("new invalid classes", canonical_rehash(new_class)))
        false_valid = copy.deepcopy(self.payload)
        if false_valid["decision"] == "next_compiler_frontier":
            false_valid["decision"] = "valid_normalized_output"
            false_valid.pop("next_frontier")
            false_valid["normalized_artifact"] = copy.deepcopy(
                false_valid["executions"][-1]["output"]
            )
        else:
            false_valid["decision"] = "next_compiler_frontier"
            false_valid.pop("normalized_artifact")
            false_valid["next_frontier"] = {
                "kind": "residual_registered_blocker",
                "operation": "memref.copy",
            }
        attacks.append(("decision gate|frontier schema", canonical_rehash(false_valid)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_affine_coefficient_offset_bound_and_base_mutations(self) -> None:
        mutations = (
            (
                "semantic probe",
                lambda probe: probe["after"]["access_maps"][0]["linear_formula"][
                    "coefficients"
                ].__setitem__(0, 7),
            ),
            (
                "semantic probe",
                lambda probe: probe["after"]["access_maps"][0]["linear_formula"].__setitem__(
                    "offset", 7
                ),
            ),
            (
                "semantic probe",
                lambda probe: probe["after"]["index_variables"][0].__setitem__(
                    "upper_exclusive", 7
                ),
            ),
            (
                "semantic probe",
                lambda probe: probe["after"]["access_maps"][0]["base"].__setitem__(
                    "argument", 7
                ),
            ),
            (
                "semantic probe",
                lambda probe: probe["after"]["access_maps"][0]["base"].__setitem__(
                    "role", "source"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=mutate):
                payload = copy.deepcopy(self.payload)
                mutate(payload["semantic_probes"][0])
                self.assert_rejected(label, canonical_rehash(payload))

    def test_verifier_rejects_noncanonical_or_unreconstructed_next_frontier(self) -> None:
        payload = copy.deepcopy(self.payload)
        if payload["decision"] == "next_compiler_frontier":
            payload["next_frontier"]["operation"] = "memref.copy"
        else:
            payload["decision"] = "next_compiler_frontier"
            payload.pop("normalized_artifact")
            payload["next_frontier"] = {
                "kind": "residual_registered_blocker",
                "operation": "memref.copy",
                "signature": {},
                "signature_sha256": digest(b"{}"),
                "source_location": {
                    "function": None,
                    "line": 0,
                    "column": 0,
                    "mlir": None,
                },
                "diagnostic": None,
                "reproducer": {
                    **binding(REPORT),
                    "operation_count": 1,
                    "metadata": binding(REPORT),
                },
            }
        self.assert_rejected("decision gate|earliest frontier", canonical_rehash(payload))


if __name__ == "__main__":
    unittest.main()
