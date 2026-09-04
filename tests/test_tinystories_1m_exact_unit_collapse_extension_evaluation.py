#!/usr/bin/env python3
"""Authenticated replay contract for the exact strided unit-collapse extension."""

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
EVALUATOR = ROOT / "scripts/pipeline/evaluate_tinystories_1m_exact_unit_collapse_extension.py"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_unit_collapse_extension.py"
EVALUATION = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json"
)
EVIDENCE = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence"
)
REPORT = (
    ROOT / "docs/results/2026-09-01-tinystories-1m-unit-collapse-extension-evaluation.md"
)
PREVIOUS_RECEIPT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json"
)
PREVIOUS_OUTPUT = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-subview-extension-evidence"
    / "complete-retained-c22-flat-scf/output.mlir"
)
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
    "semantic-offset-zero",
    "semantic-offset-seven",
    "semantic-collapsed-copy",
    "complete-retained-c22-flat-scf",
)
TOOL_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
PREVIOUS_RECEIPT_SHA256 = "467229e04ed6f82cf2f8c3596e7cd754ab0510b10fe443ae248735af0fd0c343"
PREVIOUS_OUTPUT_SHA256 = "42d682b642b899b10bc0814a7786a5803d69b839148e79bbfdc803425e261f34"
PREVIOUS_PLUGIN_SHA256 = "6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9"
PLUGIN_SHA256 = "9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984"
FLAT_SCF_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
CONTRACT_SHA256 = "c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910"
TASK1_COMMIT = "3dbfea4dd9bbd03e1032412cc2dee17b1b924d92"
PASS_SOURCE_BLOB = "dd2e2ba5956e640353a49574356cee1572c3debc"
PASS_SOURCE_SHA256 = "2f9f4a1aa949b5288c4136ddb275e1f9745e91e3d69c38d8c5c7b7c26637f10c"


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
        cls.module = load_module(EVALUATOR, "exact_unit_collapse_evaluator_unit")
        cls.verifier = load_module(
            VERIFIER, "exact_unit_collapse_verifier_census_unit"
        )

    def generic_print(self, source: str) -> str:
        with tempfile.TemporaryDirectory(prefix="task2-census-red-") as raw:
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

    def censuses(self, generic_ir: str) -> tuple[dict[str, int], dict[str, int]]:
        return (
            self.module.operation_census(generic_ir),
            self.verifier._operation_census(generic_ir),
        )

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

    def test_predecessor_authentication_is_historical_not_current_source_bound(self) -> None:
        authenticated = self.module.authenticate_predecessor_receipt()
        self.assertEqual(authenticated["sha256"], PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(
            authenticated["normalized_artifact"]["sha256"],
            PREVIOUS_OUTPUT_SHA256,
        )
        self.assertEqual(authenticated["plugin"]["sha256"], PREVIOUS_PLUGIN_SHA256)

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
            probe_id="semantic-offset-zero",
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

    def test_result_bearing_generic_memref_cast_forces_frontier(self) -> None:
        before_source = """module {
  func.func @probe(%source: memref<4xi64>) -> memref<4xi64> {
    return %source : memref<4xi64>
  }
}
"""
        after_source = """module {
  func.func @probe(%source: memref<4xi64>) -> memref<?xi64> {
    %cast = "memref.cast"(%source) : (memref<4xi64>) -> memref<?xi64>
    return %cast : memref<?xi64>
  }
}
"""
        before_generic = self.generic_print(before_source)
        after_generic = self.generic_print(after_source)
        evaluator_before, verifier_before = self.censuses(before_generic)
        evaluator_after, verifier_after = self.censuses(after_generic)
        evaluator_invalid = self.module.new_invalid_classes(
            evaluator_before, evaluator_after
        )
        verifier_invalid = self.verifier._new_invalid(
            verifier_before, verifier_after
        )
        with self.subTest(surface="evaluator false-valid decision"):
            self.assertEqual(
                self.module.apply_decision_gate(
                    parseable=True,
                    blocker_counts={name: 0 for name in REGISTERED},
                    new_invalid_classes=evaluator_invalid,
                    semantic_status="proven",
                ),
                "next_compiler_frontier",
            )
        for surface, after, invalid in (
            ("evaluator", evaluator_after, evaluator_invalid),
            ("verifier", verifier_after, verifier_invalid),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(after.get("memref.cast"), 1)
                self.assertEqual(invalid, ["memref.cast"])

    def test_result_bearing_escaped_generic_name_is_decoded(self) -> None:
        source = """module {
  func.func @probe(%source: memref<4xi64>) -> memref<?xi64> {
    %cast = "memref.c\\61st"(%source) : (memref<4xi64>) -> memref<?xi64>
    return %cast : memref<?xi64>
  }
}
"""
        self.generic_print(source)
        evaluator, verifier = self.censuses(source)
        self.assertEqual(evaluator.get("memref.cast"), 1)
        self.assertEqual(verifier.get("memref.cast"), 1)

    def test_custom_memref_transpose_is_an_exact_new_class(self) -> None:
        before_source = """module {
  func.func @probe(%source: memref<2x3xi64>) -> memref<2x3xi64> {
    return %source : memref<2x3xi64>
  }
}
"""
        after_source = """module {
  func.func @probe(%source: memref<2x3xi64>) -> memref<3x2xi64, strided<[1, 3]>> {
    %transpose = memref.transpose %source (d0, d1) -> (d1, d0) : memref<2x3xi64> to memref<3x2xi64, strided<[1, 3]>>
    return %transpose : memref<3x2xi64, strided<[1, 3]>>
  }
}
"""
        before_generic = self.generic_print(before_source)
        after_generic = self.generic_print(after_source)
        for before, after, invalid in (
            (
                self.module.operation_census(before_generic),
                self.module.operation_census(after_generic),
                self.module.new_invalid_classes,
            ),
            (
                self.verifier._operation_census(before_generic),
                self.verifier._operation_census(after_generic),
                self.verifier._new_invalid,
            ),
        ):
            with self.subTest(parser=invalid.__module__):
                self.assertEqual(after.get("memref.transpose"), 1)
                self.assertEqual(invalid(before, after), ["memref.transpose"])

    def test_canonical_generic_census_includes_result_and_core_operations(self) -> None:
        source = """module {
  func.func @core(%upper: index) -> index {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %result = scf.for %i = %c0 to %upper step %c1 iter_args(%sum = %c0) -> index {
      %next = arith.addi %sum, %i : index
      scf.yield %next : index
    }
    return %result : index
  }
}
"""
        generic = self.generic_print(source)
        expected = {
            "arith.addi": 1,
            "arith.constant": 2,
            "builtin.module": 1,
            "func.func": 1,
            "func.return": 1,
            "scf.for": 1,
            "scf.yield": 1,
        }
        evaluator, verifier = self.censuses(generic)
        self.assertEqual(evaluator, expected)
        self.assertEqual(verifier, expected)

    def test_earliest_pair_follows_def_use_order_not_largest_class(self) -> None:
        source = """module {
  func.func @pair(%source: memref<8x8xi64>, %target: memref<8x8xi64>) {
    %sub = memref.subview %source[0, 0] [8, 1] [1, 1]
      : memref<8x8xi64> to memref<8x1xi64, strided<[8, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<8x1xi64, strided<[8, 1]>> into memref<8xi64, strided<[8]>>
    memref.copy %flat, %flat
      : memref<8xi64, strided<[8]>> to memref<8xi64, strided<[8]>>
    memref.copy %flat, %flat
      : memref<8xi64, strided<[8]>> to memref<8xi64, strided<[8]>>
    return
  }
}
"""
        pair = self.module.derive_earliest_residual_pair(source)
        self.assertEqual(pair["blocker"]["operation"], "memref.collapse_shape")
        self.assertEqual(
            [item["operation"] for item in pair["defining_view_chain"]],
            ["memref.subview"],
        )


@unittest.skipUnless(EVALUATION.is_file(), "Task 2 evidence not produced")
class CommittedEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(EVALUATION.read_bytes())
        cls.previous = json.loads(PREVIOUS_RECEIPT.read_bytes())
        cls.contract = json.loads(CONTRACT.read_bytes())

    def test_immutable_model_task_contract_input_tool_and_plugins_are_pinned(self) -> None:
        payload = self.payload
        self.assertEqual(payload["schema"], "tinystories-1m-exact-unit-collapse-extension-v1")
        self.assertEqual(payload["status"], "evaluated")
        self.assertEqual(payload["model"], "tiny-stories-1m-kev-gpt-exact")
        self.assertEqual(digest(PREVIOUS_RECEIPT.read_bytes()), PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(digest(PREVIOUS_OUTPUT.read_bytes()), PREVIOUS_OUTPUT_SHA256)
        self.assertEqual(digest(CONTRACT.read_bytes()), CONTRACT_SHA256)
        self.assertEqual(payload["predecessor_evaluation"]["sha256"], PREVIOUS_RECEIPT_SHA256)
        self.assertEqual(payload["predecessor_normalized_artifact"]["sha256"], PREVIOUS_OUTPUT_SHA256)
        self.assertEqual(payload["task2_contract"]["sha256"], CONTRACT_SHA256)
        self.assertEqual(payload["input"]["bytes"], 18_933_168)
        self.assertEqual(payload["input"]["sha256"], FLAT_SCF_SHA256)
        self.assertEqual(payload["tool"]["sha256"], TOOL_SHA256)
        self.assertEqual(payload["predecessor_plugin"]["sha256"], PREVIOUS_PLUGIN_SHA256)
        self.assertEqual(payload["plugin"]["sha256"], PLUGIN_SHA256)
        self.assertNotEqual(payload["plugin"]["sha256"], payload["predecessor_plugin"]["sha256"])
        self.assertEqual(payload["pipeline"], PIPELINE)
        self.assertEqual(
            payload["task_1_through_3_identities"],
            self.contract["task_1_through_3_identities"],
        )
        self.assertEqual(
            payload["predecessor_observation"]["evaluation_self_sha256"],
            self.previous["sha256"],
        )
        self.assertEqual(payload["source_revision"]["assigned_base"], TASK1_COMMIT)
        self.assertEqual(payload["source_revision"]["task1_commit"], TASK1_COMMIT)
        self.assertEqual(payload["source_revision"]["pass_source_blob"], PASS_SOURCE_BLOB)
        self.assertEqual(payload["source_revision"]["pass_source"]["sha256"], PASS_SOURCE_SHA256)

    def test_causal_execution_order_and_exact_commands_are_closed(self) -> None:
        runs = self.payload["executions"]
        self.assertEqual([run["sequence"] for run in runs], [1, 2, 3, 4])
        self.assertEqual([run["id"] for run in runs], list(RUN_IDS))
        self.assertEqual(
            [run["kind"] for run in runs],
            ["semantic_probe", "semantic_probe", "semantic_probe", "complete"],
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
            self.assertEqual(
                [item["subject"] for item in run["generic_prints"]],
                ["input", "output"],
            )
            for generic in run["generic_prints"]:
                self.assertEqual(generic["command"][0], self.payload["tool"]["path"])
                self.assertIn("-mlir-print-op-generic", generic["command"])
                self.assertEqual(generic["exit_code"], 0)

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
                for generic in run["generic_prints"]:
                    for stream in ("stdout", "stderr", "output"):
                        path = ROOT / generic[stream]["path"]
                        self.assertEqual(binding(path), generic[stream])
                expected_parseable = (
                    run["exit_code"] == 0
                    and run["parse_check"]["exit_code"] == 0
                )
                self.assertIs(run["parseable"], expected_parseable)

    def test_three_complete_affine_proofs_precede_full_replay(self) -> None:
        probes = self.payload["semantic_probes"]
        self.assertEqual(
            [probe["id"] for probe in probes],
            ["semantic-offset-zero", "semantic-offset-seven", "semantic-collapsed-copy"],
        )
        expected = (
            ((0, 0), ([64], [64]), (0, 0)),
            ((0, 0), ([64], [64]), (7, 7)),
            ((0, 1), ([64], [64]), (7, 0)),
        )
        for probe, (base_arguments, coefficients, offsets) in zip(probes, expected):
            with self.subTest(probe=probe["id"]):
                self.assertEqual(probe["invariant_status"], "proven")
                self.assertTrue(all(probe["checks"].values()))
                for phase in ("before", "after"):
                    proof = probe[phase]
                    self.assertEqual(proof["affine_status"], "proven")
                    self.assertEqual(len(proof["index_variables"]), 1)
                    self.assertEqual(
                        {item["kind"] for item in proof["access_maps"]},
                        {"load", "store"},
                    )
                    ordered = sorted(
                        proof["access_maps"], key=lambda item: item["kind"]
                    )
                    # load sorts before store; literals are derived by hand.
                    self.assertEqual(
                        [item["base"]["argument"] for item in ordered],
                        list(base_arguments),
                    )
                    self.assertEqual(
                        [item["linear_formula"]["coefficients"] for item in ordered],
                        list(coefficients),
                    )
                    self.assertEqual(
                        [item["linear_formula"]["offset"] for item in ordered],
                        list(offsets),
                    )
                    for access in ordered:
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
            residual_total = sum(
                complete["after"]["registered_blocker_counts"].values()
            )
            if residual_total:
                pair = self.payload["next_pair"]
                self.assertEqual(pair["kind"], "earliest_residual_defining_chain")
                self.assertIn(pair["blocker"]["operation"], REGISTERED)
                self.assertGreaterEqual(len(pair["defining_view_chain"]), 1)
                self.assertTrue(all(pair["checks"].values()))
                self.assertEqual(pair["reproducer"]["registered_operation_count"], 1)
                self.assertGreaterEqual(pair["reproducer"]["view_operation_count"], 1)
            else:
                self.assertNotIn("next_pair", self.payload)
        else:
            self.assertNotIn("normalized_artifact", self.payload)
            self.assertNotIn("next_pair", self.payload)
            frontier = self.payload["next_frontier"]
            self.assertIn(
                frontier["kind"],
                {"diagnostic", "new_invalid_class", "residual_registered_blocker"},
            )
            self.assertEqual(frontier["reproducer"]["operation_count"], 1)


@unittest.skipUnless(
    VERIFIER.is_file() and EVALUATION.is_file(), "Task 2 verifier/evidence absent"
)
class PublicVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_module(VERIFIER, "exact_unit_collapse_verifier_attacks")
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

    def test_verifier_rejects_identity_pipeline_predecessor_and_path_rebinding(self) -> None:
        attacks = []
        plugin = copy.deepcopy(self.payload)
        plugin["plugin"]["path"] = plugin["predecessor_plugin"]["path"]
        attacks.append(("plugin identity", canonical_rehash(plugin)))
        source = copy.deepcopy(self.payload)
        source["input"]["sha256"] = "0" * 64
        attacks.append(("input identity", canonical_rehash(source)))
        predecessor = copy.deepcopy(self.payload)
        predecessor["predecessor_observation"]["evaluation_self_sha256"] = "0" * 64
        attacks.append(("predecessor observation", canonical_rehash(predecessor)))
        prior_output = copy.deepcopy(self.payload)
        prior_output["predecessor_normalized_artifact"]["sha256"] = "0" * 64
        attacks.append(("predecessor normalized artifact", canonical_rehash(prior_output)))
        source_revision = copy.deepcopy(self.payload)
        source_revision["source_revision"]["pass_source_blob"] = "0" * 40
        attacks.append(("source revision", canonical_rehash(source_revision)))
        pipeline = copy.deepcopy(self.payload)
        pipeline["pipeline"] += ",canonicalize"
        attacks.append(("pipeline", canonical_rehash(pipeline)))
        command = copy.deepcopy(self.payload)
        command["executions"][0]["command"][1] = str(REPORT)
        attacks.append(("exact pass command", canonical_rehash(command)))
        generic_command = copy.deepcopy(self.payload)
        generic_command["executions"][0]["generic_prints"][0]["command"][1] = str(REPORT)
        attacks.append(("exact generic command", canonical_rehash(generic_command)))
        evidence_path = copy.deepcopy(self.payload)
        evidence_path["executions"][0]["stdout"] = binding(REPORT)
        attacks.append(("canonical evidence path", canonical_rehash(evidence_path)))
        stale_output = copy.deepcopy(self.payload)
        stale_output["executions"][-1]["output"] = copy.deepcopy(
            stale_output["predecessor_normalized_artifact"]
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
        census = copy.deepcopy(self.payload)
        census["complete"]["after"]["operation_census"]["func.return"] += 1
        attacks.append(("after operation census", canonical_rehash(census)))
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
            false_valid.pop("next_pair", None)
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

    def test_verifier_rejects_noncanonical_or_unreconstructed_next_pair(self) -> None:
        payload = copy.deepcopy(self.payload)
        if payload["decision"] == "valid_normalized_output" and "next_pair" in payload:
            actual = payload["next_pair"]["blocker"]["operation"]
            payload["next_pair"]["blocker"]["operation"] = next(
                name for name in REGISTERED if name != actual
            )
            self.assert_rejected("earliest residual pair", canonical_rehash(payload))
            payload = copy.deepcopy(self.payload)
            payload["next_pair"]["defining_view_chain"] = []
            self.assert_rejected("earliest residual pair", canonical_rehash(payload))
            return
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
