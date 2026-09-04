from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCK_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json"
)
ATTENTION_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json"
)
MLP_FIXTURE = (
    ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
BLOCK_CAPTURE = ROOT / "TinyStories/capture_fixed_point_block_composition_slice.py"
BLOCK_LOWERER = (
    ROOT / "scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py"
)
SV_RECEIPT = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-block-composition-sv-receipt.json"
)


def load_capture():
    if not BLOCK_CAPTURE.is_file():
        raise AssertionError("missing authenticated block-composition capture module")
    spec = importlib.util.spec_from_file_location(
        "fixed_point_block_composition_capture", BLOCK_CAPTURE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_lowerer():
    if not BLOCK_LOWERER.is_file():
        raise AssertionError("missing fixed-point complete-block Calyx lowerer")
    spec = importlib.util.spec_from_file_location(
        "fixed_point_block_composition_calyx", BLOCK_LOWERER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def flatten(values):
    for value in values:
        if isinstance(value, list):
            yield from flatten(value)
        else:
            yield value


def signed_i64_add(left: int, right: int) -> int:
    unsigned = (left + right) & ((1 << 64) - 1)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned


def reseal_block_fixture(fixture: dict) -> None:
    record = fixture["tensors"]["block_output_q16_16"]
    payload = {
        key: record[key] for key in ("semantic", "shape", "dtype", "values")
    }
    record["canonical_sha256"] = canonical_sha256(payload)
    raw = b"".join(struct.pack("<q", value) for value in flatten(record["values"]))
    record["little_endian_int64_sha256"] = hashlib.sha256(raw).hexdigest()
    record["bytes"] = len(raw)
    tensor_receipts = {
        "block_output_q16_16": {
            key: record[key]
            for key in (
                "semantic",
                "shape",
                "dtype",
                "canonical_sha256",
                "little_endian_int64_sha256",
                "bytes",
            )
        }
    }
    binding_payload = {
        key: fixture[key]
        for key in (
            "schema",
            "status",
            "identity",
            "prompt_tokens",
            "slice",
            "arithmetic",
            "linked_attention",
            "linked_mlp",
        )
    } | {"tensor_receipts": tensor_receipts}
    binding = canonical_sha256(binding_payload)
    fixture["tensor_fixture_receipt_sha256"] = binding
    record["fixture_receipt_sha256"] = binding
    unsigned = {
        key: value for key, value in fixture.items() if key != "receipt_sha256"
    }
    fixture["receipt_sha256"] = canonical_sha256(unsigned)


class BlockCompositionTest(unittest.TestCase):
    def test_receipt_justifies_cell_share_exception_with_exact_simulation_failure(self):
        """Catches an inherited waiver lacking exact complete-block evidence."""
        lowerer = load_lowerer()
        receipt = json.loads(SV_RECEIPT.read_text(encoding="utf-8"))
        lowerer.validate_composed_block_receipt(
            receipt,
            BLOCK_FIXTURE,
            ATTENTION_FIXTURE,
            MLP_FIXTURE,
            verify_artifacts=False,
        )
        policy = receipt["calyx_compile_policy"]

        self.assertEqual(
            policy.get("reason"),
            "disable cell-share because default sharing makes the exact "
            "complete-block non-synthesis simulation SV contain circular "
            "combinational logic at main.gelu_input_abs_out; Verilator 5.022 "
            "rejects it as UNOPTFLAT, while synthesis SV passes Yosys with only "
            "expected undriven external-memory write_data warnings",
        )
        self.assertEqual(
            policy.get("exception_evidence"),
            {
                "futil_sha256": "ab0ec932bf4a76c97df3beb11dd71a5309fe65e2bd36492ce18dc63f009622c2",
                "default_cell_share_simulation_sv": {
                    "calyx_mode": "-b verilog (without --synthesis)",
                    "verilator": "5.022",
                    "result": "rejected",
                    "diagnostic_class": "UNOPTFLAT circular combinational logic",
                    "first_signal": "main.gelu_input_abs_out",
                },
                "default_cell_share_synthesis_sv": {
                    "calyx_mode": "--synthesis --disable-verify -b verilog",
                    "yosys": "0.66",
                    "post_techmap_loop_diagnostics": 0,
                    "expected_undriven_external_memory_write_data_bits": 1840,
                },
            },
        )

    def test_complete_block_receipt_binds_all_linked_authority(self):
        """Catches incomplete provenance or synthesis detached from simulation."""
        lowerer = load_lowerer()
        receipt = lowerer.run_composed_block_sv(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        block = json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        attention = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        mlp = json.loads(MLP_FIXTURE.read_text(encoding="utf-8"))
        expected_names = set(attention["tensors"]) | set(mlp["tensors"]) | {
            "block_output_q16_16"
        }

        self.assertEqual(receipt["execution"]["component_count"], 1)
        self.assertFalse(receipt["execution"]["host_intermediate"])
        self.assertEqual(len(expected_names), 84)
        self.assertEqual(set(receipt["observed"]["checkpoints"]), expected_names)
        self.assertEqual(
            receipt["observed"]["block_output_q16_16_sha256"],
            block["tensors"]["block_output_q16_16"][
                "little_endian_int64_sha256"
            ],
        )
        self.assertEqual(
            receipt["linked_fixtures"]["mlp_c_fc_input_q16_16_sha256"],
            mlp["tensors"]["c_fc_input_q16_16"][
                "little_endian_int64_sha256"
            ],
        )
        self.assertEqual(
            receipt["synthesis"]["same_futil_sha256"],
            receipt["generated_artifacts"]["futil"]["sha256"],
        )
        unsigned = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        self.assertEqual(receipt["receipt_sha256"], canonical_sha256(unsigned))
        self.assertTrue(SV_RECEIPT.is_file())
        self.assertEqual(
            json.loads(SV_RECEIPT.read_text(encoding="utf-8")), receipt
        )

    def test_complete_block_receipt_rejects_tampering(self):
        """Catches both ordinary edits and resealed checkpoint substitutions."""
        lowerer = load_lowerer()
        receipt = json.loads(SV_RECEIPT.read_text(encoding="utf-8"))
        lowerer.validate_composed_block_receipt(
            receipt,
            BLOCK_FIXTURE,
            ATTENTION_FIXTURE,
            MLP_FIXTURE,
            verify_artifacts=False,
        )

        changed_cycle = copy.deepcopy(receipt)
        changed_cycle["execution"]["cycles"] += 1
        with self.assertRaisesRegex(ValueError, "receipt self-hash mismatch"):
            lowerer.validate_composed_block_receipt(
                changed_cycle,
                BLOCK_FIXTURE,
                ATTENTION_FIXTURE,
                MLP_FIXTURE,
                verify_artifacts=False,
            )

        substituted_checkpoint = copy.deepcopy(receipt)
        substituted_checkpoint["observed"]["checkpoints"][
            "block_output_q16_16"
        ]["little_endian_int64_sha256"] = "0" * 64
        unsigned = {
            key: value
            for key, value in substituted_checkpoint.items()
            if key != "receipt_sha256"
        }
        substituted_checkpoint["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaisesRegex(ValueError, "observed records mismatch"):
            lowerer.validate_composed_block_receipt(
                substituted_checkpoint,
                BLOCK_FIXTURE,
                ATTENTION_FIXTURE,
                MLP_FIXTURE,
                verify_artifacts=False,
            )

    def test_receipt_memory_partition_and_artifacts_are_exact(self):
        """Catches host checkpoint preloads or missing artifact hash bindings."""
        lowerer = load_lowerer()
        receipt = json.loads(SV_RECEIPT.read_text(encoding="utf-8"))
        execution = receipt["execution"]
        sources = set(execution["host_preload_memories"])
        computed = set(execution["hardware_owned_memories"])

        self.assertFalse(sources & computed)
        self.assertEqual(len(sources), 34)
        self.assertEqual(len(computed), 49)
        self.assertEqual(len(execution["observed_records"]), 84)
        self.assertEqual(
            execution["direct_handoffs"],
            [
                "ln2_output_q16_16_to_c_fc_input_qdq",
                "attention_residual_q16_16_and_c_proj_output_q16_16_to_block_output_q16_16",
            ],
        )
        self.assertEqual(
            set(receipt["generated_artifacts"]),
            {"futil", "sv", "synthesis_sv", "harness"},
        )
        for record in receipt["generated_artifacts"].values():
            self.assertTrue(Path(record["path"]).is_absolute())
            self.assertGreater(record["bytes"], 0)
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            receipt["calyx_compile_policy"]["same_futil_sha256"],
            receipt["generated_artifacts"]["futil"]["sha256"],
        )
        self.assertEqual(
            receipt["calyx_compile_policy"]["disabled_passes"], ["cell-share"]
        )

    def test_one_generated_main_observes_exact_complete_block(self):
        """Catches host composition or any divergent complete-block checkpoint."""
        lowerer = load_lowerer()
        artifact = lowerer.generate_block_kernel(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        observed = lowerer.run_block_sv(
            artifact, BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        block = json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        attention = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        mlp = json.loads(MLP_FIXTURE.read_text(encoding="utf-8"))

        expected_names = set(attention["tensors"]) | set(mlp["tensors"]) | {
            "block_output_q16_16"
        }
        self.assertEqual(observed["component_count"], 1)
        self.assertFalse(observed["host_intermediate"])
        self.assertEqual(set(observed["little_endian_int64_sha256"]), expected_names)
        for fixture in (attention, mlp, block):
            for name, record in fixture["tensors"].items():
                self.assertEqual(observed[name], record["values"], name)
                self.assertEqual(
                    observed["little_endian_int64_sha256"][name],
                    record["little_endian_int64_sha256"],
                    name,
                )

        self.assertEqual(
            observed["c_fc_input_q16_16"],
            mlp["tensors"]["c_fc_input_q16_16"]["values"],
        )
        self.assertEqual(
            observed["block_output_q16_16"],
            block["tensors"]["block_output_q16_16"]["values"],
        )
        self.assertGreater(observed["cycles"], 131072)

        self.assertEqual(artifact.futil.count("component main("), 1)
        self.assertIn(
            "c_fc_gemv_code_signed.in = c_fc_input_codes_i8.read_data;",
            artifact.futil,
        )
        self.assertIn(
            "block_output_add.left = attention_residual_q16_16.read_data;",
            artifact.futil,
        )
        self.assertIn(
            "block_output_add.right = c_proj_output_q16_16.read_data;",
            artifact.futil,
        )
        self.assertFalse(
            set(artifact.provenance["host_preload_memories"])
            & set(artifact.provenance["hardware_owned_memories"])
        )
        self.assertEqual(
            artifact.provenance["calyx_disabled_passes"], ["cell-share"]
        )
        harness = Path(observed["generated_sv_artifacts"]["harness"]).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("kExpected", harness)
        self.assertEqual(
            len(
                re.findall(
                    r"^static const std::int64_t\s+kSource[0-9]+\[",
                    harness,
                    re.MULTILINE,
                )
            ),
            len(artifact.provenance["host_preload_memories"]),
        )
        for name in artifact.provenance["hardware_owned_memories"]:
            assignment = (
                rf"main__DOT__{re.escape(name)}__DOT__mem\[i\]\s*=\s*([^;]+);"
            )
            self.assertEqual(re.findall(assignment, harness), ["0"], name)

    def test_block_runner_reauthenticates_after_generation(self):
        """Catches trusting only the fixtures used when generating the artifact."""
        lowerer = load_lowerer()
        artifact = lowerer.generate_block_kernel(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        mutated = json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        mutated["tensors"]["block_output_q16_16"]["values"][0][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "mutated-block.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture tensor canonical hash"):
                lowerer.run_block_sv(
                    artifact, candidate, ATTENTION_FIXTURE, MLP_FIXTURE
                )

    def test_block_fixture_links_both_slices_and_replays_final_residual(self):
        """Catches a missing authority link or incorrect final residual."""
        capture_block = load_capture()
        fixture = capture_block.verify_fixture(BLOCK_FIXTURE)
        capture_block.verify_block_output_replay(BLOCK_FIXTURE)
        attention = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        mlp = json.loads(MLP_FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(fixture["slice"], {"block": 0, "rows": 4, "width": 64})
        self.assertEqual(
            fixture["tensors"]["block_output_q16_16"]["shape"], [4, 64]
        )
        self.assertEqual(
            fixture["linked_attention"]["receipt_sha256"],
            attention["receipt_sha256"],
        )
        self.assertEqual(
            fixture["linked_mlp"]["receipt_sha256"], mlp["receipt_sha256"]
        )
        attention_residual = attention["tensors"]["attention_residual_q16_16"][
            "values"
        ]
        c_proj_output = mlp["tensors"]["c_proj_output_q16_16"]["values"]
        independently_added = [
            [signed_i64_add(left, right) for left, right in zip(left_row, right_row)]
            for left_row, right_row in zip(attention_residual, c_proj_output)
        ]
        self.assertEqual(
            fixture["tensors"]["block_output_q16_16"]["values"],
            independently_added,
        )

    def test_fixture_contains_only_new_output_and_hash_only_link_records(self):
        """Catches duplication of attention/MLP tensor values in the new fixture."""
        fixture = load_capture().verify_fixture(BLOCK_FIXTURE)
        output = fixture["tensors"]["block_output_q16_16"]

        self.assertEqual(set(fixture["tensors"]), {"block_output_q16_16"})
        self.assertEqual(output["semantic"], "block_0_output_q16_16")
        self.assertEqual(output["dtype"], "int64")
        self.assertEqual(output["bytes"], 2048)
        self.assertEqual(
            output["canonical_sha256"],
            "762fe81857a2460b50c9375a56ef8378b7938d8f7fcfc7ec16bd73fefa063ef4",
        )
        self.assertEqual(
            output["little_endian_int64_sha256"],
            "61a7016bc7936ae32cefdf8153cf4560454c662e6c0ea6351144f3a5b377bedf",
        )
        self.assertEqual(len(fixture["linked_attention"]["tensor_receipts"]), 61)
        self.assertEqual(len(fixture["linked_mlp"]["tensor_receipts"]), 25)
        self.assertNotIn('"values"', json.dumps(fixture["linked_attention"]))
        self.assertNotIn('"values"', json.dumps(fixture["linked_mlp"]))
        unsigned = {
            key: value for key, value in fixture.items() if key != "receipt_sha256"
        }
        self.assertEqual(fixture["receipt_sha256"], canonical_sha256(unsigned))

    def test_replay_rejects_fully_resealed_block_output_mutation(self):
        """Catches a replay that trusts a self-consistent but wrong final output."""
        capture_block = load_capture()
        mutated = json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        mutated["tensors"]["block_output_q16_16"]["values"][0][0] += 1
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-output.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            capture_block.verify_fixture(candidate)
            with self.assertRaisesRegex(ValueError, "block output residual replay"):
                capture_block.verify_block_output_replay(candidate)

    def test_fixture_rejects_resealed_linked_record_mutation(self):
        """Catches accepting a linked record hash that differs from its authority."""
        capture_block = load_capture()
        mutated = copy.deepcopy(
            json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        )
        mutated["linked_mlp"]["tensor_receipts"]["c_proj_output_q16_16"][
            "canonical_sha256"
        ] = "0" * 64
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-linked-record.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "linked mlp mismatch"):
                capture_block.verify_fixture(candidate)

    def test_fixture_rejects_resealed_linked_identity_mutation(self):
        """Catches accepting a linked fixture with a different source identity."""
        capture_block = load_capture()
        mutated = copy.deepcopy(
            json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        )
        mutated["linked_attention"]["identity"]["adapter_sha256"] = "0" * 64
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-linked-identity.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "linked attention mismatch"):
                capture_block.verify_fixture(candidate)


if __name__ == "__main__":
    unittest.main()
