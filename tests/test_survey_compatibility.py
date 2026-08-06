from __future__ import annotations

import hashlib
import csv
import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from survey.scripts.run_compatibility import (
    ALLOWED_FAILURE_CODES,
    FIXTURES,
    RECEIPT_REQUIRED_FIELDS,
    ROUTES,
    RouteReceipt,
    RouteSpec,
    execute_commands,
    record_route,
    run_route,
    validate_receipt,
    write_route_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
COMPATIBILITY = ROOT / "survey/compatibility"


class CompatibilityContractTests(unittest.TestCase):
    def test_command_execution_preserves_failure_and_continues_diagnostics(self) -> None:
        stdout, stderr, results = execute_commands(
            (
                "printf 'before\\n'",
                "printf 'observed failure\\n' >&2; exit 7",
                "printf 'after\\n'",
            ),
            cwd=ROOT,
        )
        self.assertEqual([result["exit_code"] for result in results], [0, 7, 0])
        self.assertIn("before", stdout)
        self.assertIn("after", stdout)
        self.assertIn("observed failure", stderr)

    def test_registry_has_exactly_the_eight_frozen_routes(self) -> None:
        self.assertEqual(
            list(ROUTES),
            ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
        )
        self.assertEqual(
            [route.slug for route in ROUTES.values()],
            [
                "R1-mlir-circt",
                "R2-parameterized-rtl",
                "R3-mase",
                "R4-mlir-hls",
                "R5-finn",
                "R6-hls4ml",
                "R7-open-accelerator",
                "R8-cpu-fpga-fallback",
            ],
        )

    def test_m2_fixture_is_static_stateful_and_token_exact(self) -> None:
        self.assertEqual(
            FIXTURES["M2-tiny-lm"],
            {
                "blocks": 2,
                "d_model": 128,
                "heads": 4,
                "d_ff": 256,
                "vocabulary": 256,
                "max_sequence": 32,
                "batch_size": 1,
                "decode_tokens": 4,
                "decode_mode": "greedy",
                "kv_state": "persistent_across_decode_steps",
                "acceptance": {"token_ids": "identical"},
            },
        )
        self.assertEqual(set(FIXTURES), {"M0-operators", "M1-block", "M2-tiny-lm", "M3-repository-fixture"})

    def test_m2_pass_rejects_host_control_or_unverified_kv_state(self) -> None:
        receipt = RouteReceipt.controlled_failure(
            route=ROUTES["R2"],
            actual_stage="M2_STATEFUL_DECODE",
            failure_code="F_STATE",
            next_bounded_action="Implement the stateful decode loop in hardware.",
        ).to_dict()
        claimed_pass = {
            **receipt,
            "status": "PASSED",
            "decision": "CANDIDATE",
            "failure_code": "NONE",
            "fixture": "M2-tiny-lm",
            "simulation_evidence": ["m2-simulation.json"],
            "m2_evidence": {
                "implemented": True,
                "kv_state_persistent": True,
                "token_ids_identical": True,
                "token_loop_control": "host",
            },
        }
        with self.assertRaisesRegex(ValueError, "M2"):
            validate_receipt(claimed_pass)

        claimed_pass["m2_evidence"]["token_loop_control"] = "hardware"
        validate_receipt(claimed_pass)

    def test_failed_hard_gate_cannot_be_primary(self) -> None:
        receipt = RouteReceipt.controlled_failure(
            route=ROUTES["R3"],
            actual_stage="SOURCE_PIN",
            failure_code="F_SOURCE_MISSING",
            next_bounded_action="Add a source URL and immutable commit to the audited inventory.",
        )
        validate_receipt(receipt.to_dict())

        with self.assertRaisesRegex(ValueError, "PRIMARY"):
            validate_receipt({**receipt.to_dict(), "decision": "PRIMARY"})

    def test_receipt_schema_rejects_unknown_failures_and_missing_fields(self) -> None:
        receipt = RouteReceipt.controlled_failure(
            route=ROUTES["R5"],
            actual_stage="ARTIFACT_ATTRIBUTION",
            failure_code="F_SOURCE_MISSING",
            next_bounded_action="Attribute and audit a FINN repository release.",
        ).to_dict()
        self.assertTrue(set(RECEIPT_REQUIRED_FIELDS).issubset(receipt))
        self.assertIn("F_VENDOR_IP", ALLOWED_FAILURE_CODES)

        with self.assertRaisesRegex(ValueError, "failure_code"):
            validate_receipt({**receipt, "failure_code": "F_UNKNOWN"})

        receipt.pop("environment_manifest")
        with self.assertRaisesRegex(ValueError, "environment_manifest"):
            validate_receipt(receipt)

    def test_commands_are_hash_checked_after_the_receipt_is_written(self) -> None:
        receipt = RouteReceipt.controlled_failure(
            route=ROUTES["R6"],
            actual_stage="ARTIFACT_ATTRIBUTION",
            failure_code="F_SOURCE_MISSING",
            next_bounded_action="Attribute and audit the transformer extension source.",
            executed_commands=("sha256sum survey/build/artifact_inventory.csv",),
        )
        receipt = replace(
            receipt,
            command_results=(
                {
                    "index": 1,
                    "command": "sha256sum survey/build/artifact_inventory.csv",
                    "exit_code": 0,
                },
            ),
        )
        with TemporaryDirectory() as temporary:
            route_dir = Path(temporary) / ROUTES["R6"].slug
            write_route_receipt(receipt, route_dir)
            manifest = json.loads((route_dir / "manifest.json").read_text())
            commands = (route_dir / "commands.sh").read_bytes()
            self.assertEqual(
                manifest["commands_sha256"], hashlib.sha256(commands).hexdigest()
            )
            validate_receipt(manifest, route_dir)

            (route_dir / "commands.sh").write_text("exit 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "commands_sha256"):
                validate_receipt(manifest, route_dir)

    def test_command_results_must_describe_the_exact_executed_commands(self) -> None:
        receipt = RouteReceipt.controlled_failure(
            route=ROUTES["R3"],
            actual_stage="SOURCE_PIN",
            failure_code="F_SOURCE_MISSING",
            next_bounded_action="Pin the attributed source release.",
            executed_commands=("printf 'audit only\\n'",),
        ).to_dict()
        receipt["command_results"] = [
            {"index": 1, "command": "printf 'different\\n'", "exit_code": 0}
        ]
        with self.assertRaisesRegex(ValueError, "command_results"):
            validate_receipt(receipt)

    def test_sixteen_hour_cap_stops_an_unbounded_route_without_rtl(self) -> None:
        route = RouteSpec(
            route_id="R9",
            slug="R9-test",
            title="unbounded test route",
            route_family="TEST",
            expected_stage="M1_RTL",
            source_evidence="fixture://source",
            source_commit="a" * 40,
            source_sha256="b" * 64,
            complete_elaboratable_rtl=False,
            bounded_corrective_action="",
            first_gate="M1_RTL",
            first_failure_code="F_RTL",
            first_failure_detail="No complete independently elaboratable RTL exists.",
        )
        receipt = run_route(route, budget_hours=16)
        self.assertEqual(receipt.status, "STOPPED")
        self.assertEqual(receipt.failure_code, "F_RTL")
        self.assertNotEqual(receipt.decision, "PRIMARY")

    def test_record_route_executes_the_frozen_gate_checks_and_writes_receipt(self) -> None:
        with TemporaryDirectory() as temporary:
            route_dir = Path(temporary) / ROUTES["R3"].slug
            receipt = record_route(ROUTES["R3"], route_dir, budget_hours=16)
            manifest = json.loads((route_dir / "manifest.json").read_text())
        self.assertEqual(receipt.actual_stage, "SOURCE_PIN")
        self.assertEqual(receipt.failure_code, "F_SOURCE_MISSING")
        self.assertEqual([row["exit_code"] for row in manifest["command_results"]], [0, 0])
        self.assertIn("matching_artifact_rows=0", receipt.stdout)


class RecordedReceiptTests(unittest.TestCase):
    def test_frozen_fixture_and_summary_outputs_cover_the_recorded_routes(self) -> None:
        fixture_path = ROOT / "survey/build/compatibility_fixtures.json"
        self.assertEqual(json.loads(fixture_path.read_text()), FIXTURES)

        with (ROOT / "survey/build/compatibility_summary.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["route_id"] for row in rows], list(ROUTES))
        self.assertTrue(all(row["status"] == "STOPPED" for row in rows))
        self.assertTrue(all(row["decision"] != "PRIMARY" for row in rows))

    def test_all_recorded_receipts_validate_and_reference_existing_evidence(self) -> None:
        for route in ROUTES.values():
            with self.subTest(route=route.route_id):
                route_dir = COMPATIBILITY / route.slug
                for name in (
                    "README.md",
                    "manifest.json",
                    "commands.sh",
                    "stdout.log",
                    "stderr.log",
                ):
                    self.assertTrue((route_dir / name).is_file(), f"missing {name}")
                manifest = json.loads((route_dir / "manifest.json").read_text())
                validate_receipt(manifest, route_dir)
                self.assertEqual(manifest["route_id"], route.route_id)
                self.assertEqual(manifest["status"], "STOPPED")
                self.assertEqual(manifest["decision"], "INELIGIBLE")
                self.assertNotEqual(manifest["failure_code"], "NONE")
                self.assertEqual(manifest["simulation_evidence"], [])
                self.assertEqual(manifest["m2_evidence"], {})


if __name__ == "__main__":
    unittest.main()
