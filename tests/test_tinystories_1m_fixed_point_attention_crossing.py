from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTENTION_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json"
)
MLP_FIXTURE = (
    ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
ATTENTION_CAPTURE = ROOT / "TinyStories/capture_fixed_point_attention_crossing_slice.py"
MLP_CAPTURE = ROOT / "TinyStories/capture_fixed_point_mlp_crossing_slice.py"
ATTENTION_LOWERER = (
    ROOT / "scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py"
)


EXPECTED_SHAPES = {
    "block_input_q16_16": [4, 64],
    "ln1_gamma_q16_16": [64],
    "ln1_beta_q16_16": [64],
    "ln1_output_q16_16": [4, 64],
    "attention_score_q8": [4, 16, 4],
    "attention_maximum_q8": [4, 16],
    "attention_delta_q8": [4, 16, 4],
    "attention_exp_q1_20": [4, 16, 4],
    "attention_denominator_q1_20": [4, 16],
    "attention_numerator_q17_36": [4, 16, 4],
    "attention_context_heads_q16_16": [4, 16, 4],
    "attention_context_q16_16": [4, 64],
    "attention_exp_lut_q1_20": [4096],
    "attention_residual_q16_16": [4, 64],
    "ln2_gamma_q16_16": [64],
    "ln2_beta_q16_16": [64],
    "ln2_output_q16_16": [4, 64],
    "c_fc_input_codes_i8": [4, 64],
    "c_fc_input_scale_q8_24": [64],
    "c_fc_input_q16_16": [4, 64],
}
for _prefix in ("q", "k", "v", "out"):
    EXPECTED_SHAPES.update(
        {
            f"{_prefix}_input_codes_i8": [4, 64],
            f"{_prefix}_input_scale_q8_24": [64],
            f"{_prefix}_input_q16_16": [4, 64],
            f"{_prefix}_accumulator_i64": [4, 64],
            f"{_prefix}_post_weight_rescale_bias_q16_16": [4, 64],
            f"{_prefix}_output_codes_i8": [4, 64],
            f"{_prefix}_output_scale_q8_24": [64],
            f"{_prefix}_output_q16_16": [4, 64],
            f"{_prefix}_weight_codes_i8": [64, 64],
            f"{_prefix}_weight_scale_q8_24": [64],
        }
    )
EXPECTED_SHAPES["out_bias_q16_16"] = [64]

CAUSAL_SOURCE_MEMORIES = [
    "attention_exp_lut_q1_20",
    "block_input_q16_16",
    "k_input_scale_q8_24",
    "k_output_scale_q8_24",
    "k_weight_codes_i8",
    "k_weight_scale_q8_24",
    "ln1_beta_q16_16",
    "ln1_gamma_q16_16",
    "q_input_scale_q8_24",
    "q_output_scale_q8_24",
    "q_weight_codes_i8",
    "q_weight_scale_q8_24",
    "v_input_scale_q8_24",
    "v_output_scale_q8_24",
    "v_weight_codes_i8",
    "v_weight_scale_q8_24",
]

CAUSAL_COMPUTED_CHECKPOINTS = [
    "ln1_output_q16_16",
    "q_input_codes_i8",
    "q_input_q16_16",
    "q_accumulator_i64",
    "q_post_weight_rescale_bias_q16_16",
    "q_output_codes_i8",
    "q_output_q16_16",
    "k_input_codes_i8",
    "k_input_q16_16",
    "k_accumulator_i64",
    "k_post_weight_rescale_bias_q16_16",
    "k_output_codes_i8",
    "k_output_q16_16",
    "v_input_codes_i8",
    "v_input_q16_16",
    "v_accumulator_i64",
    "v_post_weight_rescale_bias_q16_16",
    "v_output_codes_i8",
    "v_output_q16_16",
    "attention_score_q8",
    "attention_maximum_q8",
    "attention_delta_q8",
    "attention_exp_q1_20",
    "attention_denominator_q1_20",
    "attention_numerator_q17_36",
    "attention_context_heads_q16_16",
    "attention_context_q16_16",
]


def load_module(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AttentionCrossingTest(unittest.TestCase):
    def test_generated_sv_observes_exact_qkv_and_causal_context(self):
        """Catches missing/wrong hardware checkpoints or fixture-seeded results."""
        lowerer = load_module(
            ATTENTION_LOWERER, "fixed_point_attention_causal_lowerer"
        )
        artifact = lowerer.generate_causal_attention_kernel(ATTENTION_FIXTURE)
        observed = lowerer.run_causal_attention_sv(artifact, ATTENTION_FIXTURE)
        fixture = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))

        for name in CAUSAL_COMPUTED_CHECKPOINTS:
            self.assertEqual(observed[name], fixture["tensors"][name]["values"], name)
            self.assertEqual(
                observed["little_endian_int64_sha256"][name],
                fixture["tensors"][name]["little_endian_int64_sha256"],
                name,
            )

        self.assertEqual(
            artifact.provenance["host_preload_memories"], CAUSAL_SOURCE_MEMORIES
        )
        self.assertEqual(
            artifact.provenance["hardware_owned_memories"],
            CAUSAL_COMPUTED_CHECKPOINTS,
        )
        self.assertEqual(artifact.provenance["calyx_disabled_passes"], ["cell-share"])
        self.assertEqual(artifact.futil.count("component main("), 1)
        self.assertGreater(observed["cycles"], 256)

        harness = Path(
            artifact.provenance["generated_sv_artifacts"]["harness"]
        ).read_text(encoding="utf-8")
        self.assertNotIn("kExpected", harness)
        for name in CAUSAL_COMPUTED_CHECKPOINTS:
            self.assertNotIn(f"preload_{name}", harness)

    def test_generated_sv_observes_exact_ln1(self):
        """Catches any generated LayerNorm result that diverges from the fixture."""
        lowerer = load_module(ATTENTION_LOWERER, "fixed_point_attention_lowerer")
        artifact = lowerer.generate_ln1_kernel(ATTENTION_FIXTURE)
        observed = lowerer.run_ln1_sv(artifact, ATTENTION_FIXTURE)
        fixture = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            observed["ln1_q16_16"],
            fixture["tensors"]["ln1_output_q16_16"]["values"],
        )
        self.assertEqual(
            observed["little_endian_int64_sha256"],
            fixture["tensors"]["ln1_output_q16_16"][
                "little_endian_int64_sha256"
            ],
        )
        self.assertEqual(
            artifact.provenance["host_preload_memories"],
            [
                "block_input_q16_16",
                "ln1_gamma_q16_16",
                "ln1_beta_q16_16",
            ],
        )
        self.assertEqual(
            artifact.provenance["hardware_owned_memories"], ["ln1_q16_16"]
        )
        self.assertEqual(
            artifact.provenance["calyx_disabled_passes"], ["cell-share"]
        )
        self.assertEqual(artifact.futil.count("component main("), 1)
        harness = Path(
            artifact.provenance["generated_sv_artifacts"]["harness"]
        ).read_text(encoding="utf-8")
        preload_arrays = [
            line
            for line in harness.splitlines()
            if line.startswith("static const std::int64_t k")
        ]
        self.assertEqual(len(preload_arrays), 3)
        self.assertNotIn("kExpected", harness)
        self.assertNotIn("kLn1Output", harness)

    def test_ln1_sv_rejects_post_generation_fixture_mutation(self):
        """Catches a runner that trusts only generation-time fixture authority."""
        lowerer = load_module(
            ATTENTION_LOWERER, "fixed_point_attention_lowerer_mutation"
        )
        artifact = lowerer.generate_ln1_kernel(ATTENTION_FIXTURE)
        mutated = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        mutated["tensors"]["block_input_q16_16"]["values"][0][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "mutated-fixture.json"
            fixture_path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture.*hash|fixture.*authority"):
                lowerer.run_ln1_sv(artifact, fixture_path)

    def test_attention_fixture_replays_and_links_mlp_input(self):
        """Catches an incomplete four-row trace or a divergent MLP handoff."""
        capture_attention = load_module(
            ATTENTION_CAPTURE, "fixed_point_attention_crossing_capture"
        )
        capture_mlp = load_module(MLP_CAPTURE, "fixed_point_mlp_crossing_capture")
        attention = capture_attention.verify_fixture(ATTENTION_FIXTURE)
        capture_attention.verify_fixed_point_replay(ATTENTION_FIXTURE)
        mlp = capture_mlp.verify_fixture(MLP_FIXTURE)

        self.assertEqual(
            attention["schema"],
            "tinystories-1m-fixed-point-attention-crossing-slice-v1",
        )
        self.assertEqual(attention["prompt_tokens"], [7454, 2402, 257, 640])
        self.assertEqual(attention["slice"]["rows"], 4)
        self.assertEqual(attention["slice"]["heads"], 16)
        self.assertEqual(attention["slice"]["head_width"], 4)
        self.assertEqual(
            attention["slice"]["observation_indices"],
            {
                "q_qdq": [0, 6],
                "q_accumulator": 0,
                "k_qdq": [6, 12],
                "k_accumulator": 1,
                "v_qdq": [12, 18],
                "v_accumulator": 2,
                "out_qdq": [18, 24],
                "out_accumulator": 3,
                "ln1_nonlinear": 0,
                "attention_context_nonlinear": 1,
                "ln2_nonlinear": 2,
                "c_fc_input_qdq": [24, 27],
            },
        )
        self.assertEqual(
            {name: record["shape"] for name, record in attention["tensors"].items()},
            EXPECTED_SHAPES,
        )
        for name in (
            "c_fc_input_codes_i8",
            "c_fc_input_scale_q8_24",
            "c_fc_input_q16_16",
        ):
            self.assertEqual(
                attention["linked_mlp"][name]["little_endian_int64_sha256"],
                mlp["tensors"][name]["little_endian_int64_sha256"],
                name,
            )
            self.assertEqual(
                attention["tensors"][name]["values"],
                mlp["tensors"][name]["values"],
                name,
            )

    def test_fixture_rejects_corrupted_causal_checkpoint(self):
        """Catches causal values that are changed without authenticated hashes."""
        capture_attention = load_module(
            ATTENTION_CAPTURE, "fixed_point_attention_crossing_capture_corruption"
        )
        fixture = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        corrupted = copy.deepcopy(fixture)
        corrupted["tensors"]["attention_score_q8"]["values"][3][15][3] += 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupted.json"
            path.write_text(json.dumps(corrupted), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                capture_attention.verify_fixture(path)


if __name__ == "__main__":
    unittest.main()
