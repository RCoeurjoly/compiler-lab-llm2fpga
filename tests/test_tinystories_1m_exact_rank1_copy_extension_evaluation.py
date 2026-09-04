#!/usr/bin/env python3
"""Authenticated replay gate for the exact direct rank-one copy extension."""

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
EVALUATOR = ROOT / "scripts/pipeline/evaluate_tinystories_1m_exact_rank1_copy_extension.py"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_rank1_copy_extension.py"
EVALUATION = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evaluation.json"
)
EVIDENCE = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence"
)
REPORT = (
    ROOT / "docs/results/2026-09-01-tinystories-1m-rank1-copy-extension-evaluation.md"
)
PREVIOUS_RECEIPT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json"
)
PREVIOUS_OUTPUT = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence"
    / "complete-retained-c22-flat-scf/output.mlir"
)
CONTRACT = ROOT / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
FLAT_SCF = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf"
    / "run-1/flat.scf.mlir"
)
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
PASS_ONLY_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx)"
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)
RUN_IDS = (
    "semantic-size1-pass-only",
    "semantic-size1-integrated",
    "semantic-size64-pass-only",
    "semantic-size64-integrated",
    "complete-retained-c22-flat-scf",
)
TOOL_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
PREVIOUS_RECEIPT_SHA256 = "eae77d6f74ccb5091ec6b6ab3d1876b6326a34fee6e974c29ea7dc1b5e7946ad"
PREVIOUS_SELF_SHA256 = "6e7772175d4f4acf1badae01df293f7f37419fc05e74e2f5da1d04f85bc0a540"
PREVIOUS_OUTPUT_SHA256 = "733e65144ef46004a5de4fde3a38c418b8ed894daf4482f32cd468157389ce9f"
PREVIOUS_PLUGIN_SHA256 = "9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984"
PLUGIN_SHA256 = "79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
TASK1_COMMIT = "8b08bd21a683abfa2837e1aa62c57e5bc77be439"
PASS_SOURCE_BLOB = "3c570a72637686161b27d5d78474aef34eea5697"
PASS_SOURCE_SHA256 = "a7461a22d405212534b9d3a6a0df415d8a960042ba253459e2e14e3c1e894756"


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
    def test_all_task2_surfaces_start_absent_then_must_exist(self) -> None:
        for path in (EVALUATOR, VERIFIER, EVALUATION, EVIDENCE, REPORT):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"absent Task 2 surface: {path}")


@unittest.skipUnless(EVALUATOR.is_file(), "Task 2 evaluator not implemented")
class EvaluatorUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module(EVALUATOR, "exact_rank1_copy_evaluator_unit")
        cls.verifier = load_module(VERIFIER, "exact_rank1_copy_verifier_unit")

    def generic_print(self, source: str) -> str:
        with tempfile.TemporaryDirectory(prefix="rank1-copy-census-") as raw:
            input_path = Path(raw) / "input.mlir"
            output_path = Path(raw) / "generic.mlir"
            input_path.write_text(source, encoding="utf-8")
            completed = subprocess.run(
                [
                    self.module.TOOL["path"],
                    str(input_path),
                    "-mlir-print-op-generic",
                    "-o",
                    str(output_path),
                ],
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
            return output_path.read_text(encoding="utf-8")

    def test_zero_gate_requires_every_closed_condition(self) -> None:
        zeros = {name: 0 for name in REGISTERED}
        arguments = {
            "pass_exit_zero": True,
            "parseable": True,
            "blocker_counts": zeros,
            "after_only_classes": [],
            "semantic_status": "proven",
        }
        self.assertTrue(self.module.apply_zero_blocker_gate(**arguments))
        mutations = (
            {"pass_exit_zero": False},
            {"parseable": False},
            {"blocker_counts": {**zeros, "memref.copy": 1}},
            {"blocker_counts": {name: 0 for name in REGISTERED[:-1]}},
            {"blocker_counts": {**zeros, "unknown": 0}},
            {"blocker_counts": {**zeros, "memref.copy": None}},
            {"after_only_classes": ["memref.future_view"]},
            {"semantic_status": "unproven"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(arguments)
                candidate.update(mutation)
                self.assertFalse(self.module.apply_zero_blocker_gate(**candidate))

    def test_predecessor_authentication_is_historical_and_exact(self) -> None:
        authenticated = self.module.authenticate_predecessor_receipt()
        self.assertEqual(authenticated["sha256"], PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(authenticated["self_sha256"], PREVIOUS_SELF_SHA256)
        self.assertEqual(
            authenticated["normalized_artifact"]["sha256"],
            PREVIOUS_OUTPUT_SHA256,
        )
        self.assertEqual(authenticated["plugin"]["sha256"], PREVIOUS_PLUGIN_SHA256)

    def test_generic_census_decodes_result_bearing_and_escaped_names(self) -> None:
        source = """module {
  func.func @probe(%source: memref<4xi64>) -> memref<?xi64> {
    %cast = \"memref.c\\61st\"(%source) : (memref<4xi64>) -> memref<?xi64>
    return %cast : memref<?xi64>
  }
}
"""
        generic = self.generic_print(source)
        evaluator = self.module.operation_census(generic)
        verifier = self.verifier._operation_census(generic)
        self.assertEqual(evaluator, verifier)
        self.assertEqual(evaluator.get("memref.cast"), 1)
        self.assertEqual(
            self.module.after_only_classes({}, evaluator),
            sorted(evaluator),
        )

    def test_earliest_residual_follows_source_order_and_definitions(self) -> None:
        source = """module {
  func.func @pair() {
    %source = memref.alloc() : memref<1xi64>
    %target = memref.alloc() : memref<1xi64>
    memref.copy %source, %target : memref<1xi64> to memref<1xi64>
    %late = memref.alloc() : memref<1xi64>
    memref.copy %target, %late : memref<1xi64> to memref<1xi64>
    return
  }
}
"""
        pair = self.module.derive_earliest_residual_pair(source)
        self.assertEqual(pair["blocker"]["operation"], "memref.copy")
        self.assertEqual(
            [item["result_ssa"] for item in pair["defining_chain"]],
            ["%source", "%target"],
        )


@unittest.skipUnless(EVALUATION.is_file(), "Task 2 evidence not produced")
class CommittedEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(EVALUATION.read_bytes())
        cls.previous = json.loads(PREVIOUS_RECEIPT.read_bytes())
        cls.contract = json.loads(CONTRACT.read_bytes())

    def test_all_historical_and_current_identities_are_pinned(self) -> None:
        payload = self.payload
        self.assertEqual(
            payload["schema"], "tinystories-1m-exact-rank1-copy-extension-v1"
        )
        self.assertEqual(payload["status"], "evaluated")
        self.assertEqual(payload["model"], "tiny-stories-1m-kev-gpt-exact")
        self.assertEqual(digest(PREVIOUS_RECEIPT.read_bytes()), PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(digest(PREVIOUS_OUTPUT.read_bytes()), PREVIOUS_OUTPUT_SHA256)
        self.assertEqual(digest(CONTRACT.read_bytes()), CONTRACT_SHA256)
        self.assertEqual(digest(FLAT_SCF.read_bytes()), FLAT_SCF_SHA256)
        self.assertEqual(payload["predecessor_evaluation"]["sha256"], PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(payload["predecessor_evaluation_self_sha256"], PREVIOUS_SELF_SHA256)
        self.assertEqual(payload["predecessor_normalized_artifact"]["sha256"], PREVIOUS_OUTPUT_SHA256)
        self.assertEqual(payload["task2_contract"]["sha256"], CONTRACT_SHA256)
        self.assertEqual(payload["input"]["bytes"], 18_933_168)
        self.assertEqual(payload["input"]["sha256"], FLAT_SCF_SHA256)
        self.assertEqual(payload["tool"]["sha256"], TOOL_SHA256)
        self.assertEqual(payload["predecessor_plugin"]["sha256"], PREVIOUS_PLUGIN_SHA256)
        self.assertEqual(payload["plugin"]["sha256"], PLUGIN_SHA256)
        self.assertNotEqual(payload["plugin"]["sha256"], payload["predecessor_plugin"]["sha256"])
        self.assertEqual(payload["pipeline"], PIPELINE)
        self.assertEqual(payload["probe_pipeline"], PASS_ONLY_PIPELINE)
        self.assertEqual(
            payload["task_1_through_3_identities"],
            self.contract["task_1_through_3_identities"],
        )
        self.assertEqual(payload["source_revision"]["assigned_base"], TASK1_COMMIT)
        self.assertEqual(payload["source_revision"]["task1_commit"], TASK1_COMMIT)
        self.assertEqual(payload["source_revision"]["pass_source_blob"], PASS_SOURCE_BLOB)
        self.assertEqual(payload["source_revision"]["pass_source"]["sha256"], PASS_SOURCE_SHA256)
        self.assertEqual(
            payload["predecessor_observation"]["registered_blocker_counts"],
            {
                "memref.collapse_shape": 0,
                "memref.copy": 1022,
                "memref.expand_shape": 0,
                "memref.reinterpret_cast": 0,
            },
        )

    def test_causal_execution_order_commands_and_no_calyx_are_closed(self) -> None:
        runs = self.payload["executions"]
        self.assertEqual([run["sequence"] for run in runs], [1, 2, 3, 4, 5])
        self.assertEqual([run["id"] for run in runs], list(RUN_IDS))
        self.assertEqual(
            [run["kind"] for run in runs],
            [
                "semantic_probe_pass_only",
                "semantic_probe_integrated",
                "semantic_probe_pass_only",
                "semantic_probe_integrated",
                "complete",
            ],
        )
        self.assertTrue(all(run["causal_preconditions_satisfied"] for run in runs))
        self.assertEqual(runs[-1]["input"]["sha256"], FLAT_SCF_SHA256)
        for run in runs:
            expected_pipeline = (
                PASS_ONLY_PIPELINE
                if run["kind"] == "semantic_probe_pass_only"
                else PIPELINE
            )
            command = run["command"]
            self.assertEqual(command[0], self.payload["tool"]["path"])
            self.assertIn(f"--load-pass-plugin={self.payload['plugin']['path']}", command)
            self.assertIn(f"--pass-pipeline={expected_pipeline}", command)
            lowered = " ".join(command).lower().replace("for-calyx", "")
            self.assertNotIn("calyx", lowered)
            self.assertNotIn("circt-opt", lowered)
            self.assertNotIn("lower-scf-to-calyx", lowered)
            self.assertEqual(
                [item["subject"] for item in run["generic_prints"]],
                ["input", "output"],
            )
            self.assertTrue(all(item["exit_code"] == 0 for item in run["generic_prints"]))

    def test_streams_outputs_parse_checks_and_generic_censuses_are_exact(self) -> None:
        for run in self.payload["executions"]:
            with self.subTest(run=run["id"]):
                self.assertGreater(run["elapsed_ns"], 0)
                self.assertEqual(run["input"], run["input_after"])
                for stream in ("stdout", "stderr", "output"):
                    self.assertEqual(binding(ROOT / run[stream]["path"]), run[stream])
                for stream in ("stdout", "stderr"):
                    self.assertEqual(
                        binding(ROOT / run["parse_check"][stream]["path"]),
                        run["parse_check"][stream],
                    )
                for generic in run["generic_prints"]:
                    for stream in ("stdout", "stderr", "output"):
                        self.assertEqual(
                            binding(ROOT / generic[stream]["path"]), generic[stream]
                        )
                self.assertIs(
                    run["parseable"],
                    run["exit_code"] == 0 and run["parse_check"]["exit_code"] == 0,
                )

    def test_both_copy_probes_prove_domain_index_bases_direction_and_liveness(self) -> None:
        probes = self.payload["semantic_probes"]
        self.assertEqual([probe["id"] for probe in probes], ["size1", "size64"])
        for probe, extent, live_index in zip(probes, (1, 64), (0, 63)):
            with self.subTest(probe=probe["id"]):
                self.assertEqual(probe["invariant_status"], "proven")
                self.assertTrue(all(probe["checks"].values()))
                proof = probe["proof"]
                self.assertEqual(proof["extent"], extent)
                self.assertEqual(proof["live_index"], live_index)
                self.assertTrue(proof["distinct_bases"])
                self.assertEqual(proof["source_allocation"], 0)
                self.assertEqual(proof["target_allocation"], 1)
                self.assertEqual(
                    proof["loop_domain"],
                    {"lower": 0, "upper_exclusive": extent, "step": 1},
                )
                self.assertEqual(
                    proof["copy_accesses"],
                    [
                        {
                            "kind": "load",
                            "role": "source",
                            "allocation": 0,
                            "offset": 0,
                            "coefficient": 1,
                        },
                        {
                            "kind": "store",
                            "role": "target",
                            "allocation": 1,
                            "offset": 0,
                            "coefficient": 1,
                        },
                    ],
                )
                self.assertEqual(
                    proof["live_flow"],
                    {
                        "input_argument": 0,
                        "source_store_index": live_index,
                        "target_load_index": live_index,
                        "returned_target_observation": True,
                    },
                )

    def test_closed_zero_gate_has_exact_four_zero_counts_and_handoff_only(self) -> None:
        payload = self.payload
        complete = payload["complete"]
        expected_before = {
            name: self.contract["classes"][name]["count"] for name in REGISTERED
        }
        self.assertEqual(complete["before"]["registered_blocker_counts"], expected_before)
        self.assertEqual(
            complete["after"]["registered_blocker_counts"],
            {name: 0 for name in REGISTERED},
        )
        self.assertEqual(complete["after"]["registered_operation_count"], 0)
        self.assertEqual(complete["after_only_operation_classes"], [])
        self.assertTrue(complete["parseable"])
        self.assertEqual(complete["invariant_status"], "proven")
        self.assertTrue(payload["zero_registered_blockers"])
        self.assertEqual(payload["decision"], "zero_registered_blockers")
        self.assertEqual(payload["normalized_artifact"], payload["executions"][-1]["output"])
        self.assertEqual(payload["handoff"]["artifact"], payload["normalized_artifact"])
        self.assertEqual(
            payload["handoff"]["next_plan"],
            "separate-stage-registration-and-pre-calyx-legality",
        )
        self.assertFalse(payload["handoff"]["stage_registration_authorized"])
        self.assertFalse(payload["handoff"]["calyx_authorized"])
        self.assertNotIn("next_pair", payload)
        self.assertNotIn("next_frontier", payload)


@unittest.skipUnless(
    VERIFIER.is_file() and EVALUATION.is_file(), "Task 2 verifier/evidence absent"
)
class PublicVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_module(VERIFIER, "exact_rank1_copy_verifier_attacks")
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
        self.assertIn(b"zero_registered_blockers: true", completed.stdout)

    def test_verifier_rejects_rehashed_identity_command_path_and_stale_output_mutations(self) -> None:
        attacks = []
        plugin = copy.deepcopy(self.payload)
        plugin["plugin"]["path"] = plugin["predecessor_plugin"]["path"]
        attacks.append(("plugin identity", canonical_rehash(plugin)))
        source = copy.deepcopy(self.payload)
        source["input"]["sha256"] = "0" * 64
        attacks.append(("input identity", canonical_rehash(source)))
        predecessor = copy.deepcopy(self.payload)
        predecessor["predecessor_evaluation_self_sha256"] = "0" * 64
        attacks.append(("predecessor", canonical_rehash(predecessor)))
        source_revision = copy.deepcopy(self.payload)
        source_revision["source_revision"]["pass_source_blob"] = "0" * 40
        attacks.append(("source revision", canonical_rehash(source_revision)))
        pipeline = copy.deepcopy(self.payload)
        pipeline["pipeline"] += ",canonicalize"
        attacks.append(("pipeline", canonical_rehash(pipeline)))
        command = copy.deepcopy(self.payload)
        command["executions"][0]["command"][1] = str(REPORT)
        attacks.append(("exact pass command", canonical_rehash(command)))
        generic = copy.deepcopy(self.payload)
        generic["executions"][0]["generic_prints"][0]["command"][1] = str(REPORT)
        attacks.append(("exact generic command", canonical_rehash(generic)))
        evidence_path = copy.deepcopy(self.payload)
        evidence_path["executions"][0]["stdout"] = binding(REPORT)
        attacks.append(("canonical evidence path", canonical_rehash(evidence_path)))
        stale = copy.deepcopy(self.payload)
        stale["executions"][-1]["output"] = copy.deepcopy(
            stale["predecessor_normalized_artifact"]
        )
        attacks.append(("canonical evidence path|stale output", canonical_rehash(stale)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_stage_registration_calyx_and_crossed_decision_fields(self) -> None:
        attacks = []
        top = copy.deepcopy(self.payload)
        top["stage_registration"] = {"status": "registered"}
        attacks.append(("top-level schema", canonical_rehash(top)))
        run = copy.deepcopy(self.payload)
        run["executions"][0]["calyx_executed"] = True
        attacks.append(("execution schema", canonical_rehash(run)))
        authorized = copy.deepcopy(self.payload)
        authorized["handoff"]["stage_registration_authorized"] = True
        attacks.append(("stage registration authorization", canonical_rehash(authorized)))
        calyx = copy.deepcopy(self.payload)
        calyx["handoff"]["calyx_authorized"] = True
        attacks.append(("Calyx authorization", canonical_rehash(calyx)))
        crossed = copy.deepcopy(self.payload)
        crossed["next_pair"] = {"kind": "earliest_residual_defining_chain"}
        attacks.append(("decision schema", canonical_rehash(crossed)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_false_zero_counts_census_and_after_only_classes(self) -> None:
        attacks = []
        counts = copy.deepcopy(self.payload)
        counts["complete"]["after"]["registered_blocker_counts"]["memref.copy"] = 1
        attacks.append(("after blocker census", canonical_rehash(counts)))
        census = copy.deepcopy(self.payload)
        census["complete"]["after"]["operation_census"]["func.return"] += 1
        attacks.append(("after operation census", canonical_rehash(census)))
        new_class = copy.deepcopy(self.payload)
        new_class["complete"]["after_only_operation_classes"] = ["memref.fake_view"]
        attacks.append(("after-only operation classes", canonical_rehash(new_class)))
        false_zero = copy.deepcopy(self.payload)
        false_zero["zero_registered_blockers"] = False
        attacks.append(("zero blocker gate", canonical_rehash(false_zero)))
        for label, payload in attacks:
            with self.subTest(label=label):
                self.assert_rejected(label, payload)

    def test_verifier_rejects_direction_loop_index_base_and_live_flow_mutations(self) -> None:
        mutations = (
            (
                "semantic probe",
                lambda proof: proof["copy_accesses"][0].__setitem__("role", "target"),
            ),
            (
                "semantic probe",
                lambda proof: proof["copy_accesses"][0].__setitem__("coefficient", 2),
            ),
            (
                "semantic probe",
                lambda proof: proof["loop_domain"].__setitem__("upper_exclusive", 2),
            ),
            (
                "semantic probe",
                lambda proof: proof.__setitem__("source_allocation", 1),
            ),
            (
                "semantic probe",
                lambda proof: proof["live_flow"].__setitem__("returned_target_observation", False),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=mutate):
                payload = copy.deepcopy(self.payload)
                mutate(payload["semantic_probes"][0]["proof"])
                self.assert_rejected(label, canonical_rehash(payload))


if __name__ == "__main__":
    unittest.main()
