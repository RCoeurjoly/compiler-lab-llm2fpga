"""Reachable-domain and independent-logits authorities for the exact model."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import copy
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
CERTIFIER = ROOT / "scripts/comparison/certify_tinystories_1m_exact_reachable_domain.py"
CAPTURE = ROOT / "scripts/comparison/capture_tinystories_1m_fixed_logits.py"
CERTIFICATE = ROOT / "artifacts/reference/tinystories-1m-exact-reachable-domain.json"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-logits-oracle.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
AUDIT = ROOT / "artifacts/reference/tinystories-1m-exact-input-audit.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
SOFTMAX = ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
REFERENCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")


def canonical_digest(values: list[int]) -> str:
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def expected_summary(values: list[int], module: str, term: str) -> dict:
    minimum = min(values)
    maximum = max(values)
    worst_index = max(range(len(values)), key=lambda index: abs(values[index]))
    worst = values[worst_index]
    return {
        "ordered_values_sha256": canonical_digest(values),
        "element_count": len(values),
        "signed_minimum": {"value": minimum, "output_index": values.index(minimum)},
        "signed_maximum": {"value": maximum, "output_index": values.index(maximum)},
        "absolute_maximum": {
            "value": worst, "magnitude": abs(worst), "output_index": worst_index,
        },
        "worst_case_witness": {
            "module": module, "output": worst_index, "term": term,
            "value": worst, "absolute_value": abs(worst),
        },
        "first_failure_witness": None,
    }


def gemv_specs() -> list[tuple[str, str, str | None]]:
    specs = []
    for layer in range(8):
        block, source = f"blocks.{layer}", f"transformer.h.{layer}"
        specs.extend((
            (f"{source}.attn.attention.q_proj", f"{block}.attn.q.weight", None),
            (f"{source}.attn.attention.k_proj", f"{block}.attn.k.weight", None),
            (f"{source}.attn.attention.v_proj", f"{block}.attn.v.weight", None),
            (f"{source}.attn.attention.out_proj", f"{block}.attn.out.weight",
             f"{block}.attn.out.bias"),
            (f"{source}.mlp.c_fc", f"{block}.mlp.fc.weight", f"{block}.mlp.fc.bias"),
            (f"{source}.mlp.c_proj", f"{block}.mlp.proj.weight", f"{block}.mlp.proj.bias"),
        ))
    return specs + [("lm_head", "token_embedding.weight", None)]


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PACKAGE.is_dir() and REFERENCE.is_dir(), "canonical inputs unavailable")
class ExactReachableDomainCertificateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.certifier = load_script(CERTIFIER, "exact_reachable_domain")
        cls.certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))

    def test_checked_in_certificate_rederives_exactly(self) -> None:
        actual = self.certifier.derive_certificate(
            CONTRACT, AUDIT, PROFILE, SOFTMAX, PACKAGE, REFERENCE, ROOT
        )

        self.assertEqual(actual, self.certificate)
        self.assertEqual(actual["status"], "proven_reachable_domain_equivalent")
        self.assertEqual(actual["certificate_sha256"], self.certifier.certificate_sha256(actual))

    def test_all_layernorm_sites_have_closed_width_and_output_proofs(self) -> None:
        layer_norm = self.certificate["layer_norm"]
        calls = layer_norm["calls"]

        self.assertEqual(len(calls), 17)
        self.assertEqual(calls[0]["name"], "transformer.h.0.ln_1")
        self.assertEqual(calls[-1]["name"], "transformer.ln_f")
        for call in calls:
            with self.subTest(call=call["name"]):
                self.assertEqual(len(call["input_bounds_q16_16"]["lower_by_channel"]), 64)
                self.assertEqual(len(call["input_bounds_q16_16"]["upper_by_channel"]), 64)
                self.assertTrue(all(call["proof"]["inequalities"].values()))
                self.assertLess(call["proof"]["square_sum_abs_bound"], 2**63)
                self.assertLess(call["proof"]["affine_output_abs_bound"], 2**31)
                self.assertEqual(call["edge_witnesses"]["status"], "runtime_rtl_matched")
        self.assertEqual(layer_norm["conclusion"], "runtime_and_synthesizable_rtl_identical_on_reachable_domain")

    def test_unprovable_layernorm_interval_reports_exact_failed_inequality(self) -> None:
        result = self.certifier.prove_layernorm_interval(
            "adversarial", [-2**31] * 32 + [2**31 - 1] * 32,
            [-2**31] * 32 + [2**31 - 1] * 32,
            [65536] * 64, [0] * 64,
        )

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["failing_inequality"], "runtime_square_sum_fits_signed_int64")

    def test_gelu_exhaustively_matches_independent_runtime_and_rtl_evaluators(self) -> None:
        nonlinear = self.certificate["nonlinear"]
        proof = nonlinear["gelu"]["semantic_equivalence"]

        self.assertEqual(len(nonlinear["gelu"]["calls"]), 8)
        self.assertEqual(nonlinear["gelu"]["calls"][-1]["name"], "transformer.h.7.mlp.gelu")
        self.assertEqual(proof["status"], "exhaustive_runtime_rtl_equivalent")
        self.assertEqual(proof["input_domain"], {
            "format": "signed_q4.12_int16",
            "minimum": -32768,
            "maximum": 32767,
            "count": 65536,
        })
        self.assertEqual(proof["comparison"]["pass_count"], 65536)
        self.assertIsNone(proof["comparison"]["mismatch_witness"])
        self.assertEqual(proof["runtime_lut"]["entry_count"], 8192)
        self.assertEqual(proof["runtime_lut"]["values_sha256"],
                         proof["rtl_lut"]["values_sha256"])
        self.assertRegex(proof["rtl_lut"]["mem_sha256"], r"^[0-9a-f]{64}$")

        sources = self.certifier.materialize_semantic_sources(CONTRACT, AUDIT, REFERENCE)
        runtime_lut, rtl_gelu_lut, _ = self.certifier.materialize_luts(sources)
        corrupted = copy.deepcopy(rtl_gelu_lut)
        corrupted[0] += 1
        failed = self.certifier.prove_gelu_semantics(runtime_lut, corrupted)
        self.assertEqual(failed["status"], "identity_frontier")
        self.assertEqual(failed["comparison"]["mismatch_witness"]["input_q4_12"], -32768)

    def test_attention_operators_exp_and_divider_have_executable_source_bound_proofs(self) -> None:
        attention = self.certificate["nonlinear"]["attention_softmax"]
        exp = attention["exp_equivalence"]
        operators = attention["operator_equivalence"]

        self.assertEqual(len(attention["calls"]), 8)
        self.assertEqual(
            attention["calls"][-1]["name"],
            "transformer.h.7.attn.attention",
        )
        self.assertEqual(exp["status"], "exhaustive_effective_domain_equivalent")
        self.assertEqual(exp["effective_delta_domain"], [-4096, 0])
        self.assertEqual(exp["comparison"]["pass_count"], 4101)
        self.assertEqual(exp["comparison"]["outside_clamp_representatives"],
                         [-2147483648, -4097, 1, 2147483647])
        self.assertIsNone(exp["comparison"]["mismatch_witness"])
        self.assertEqual(exp["runtime_lut"]["values_sha256"],
                         exp["rtl_lut"]["values_sha256"])
        self.assertEqual(operators["status"], "source_derived_equivalent_on_certified_intervals")
        self.assertEqual(set(operators["equations"]), {
            "score_sum", "score_shift", "score_max", "delta", "probability_sum",
            "context_numerator", "rounding_correction", "restoring_division",
        })
        self.assertEqual(operators["divider"]["status"], "representatives_and_invariant_proven")
        self.assertGreaterEqual(operators["divider"]["comparison"]["pass_count"], 100)
        self.assertIsNone(operators["divider"]["comparison"]["mismatch_witness"])
        self.assertEqual(operators["divider"]["zero_denominator_policy"], "quotient_zero")
        self.assertTrue(all(call["proof"]["all"] for call in attention["calls"]))

        sources = self.certifier.materialize_semantic_sources(CONTRACT, AUDIT, REFERENCE)
        runtime_exp, rtl_exp = self.certifier.materialize_luts(sources)[2]
        corrupted = copy.deepcopy(rtl_exp)
        corrupted[0] += 1
        failed = self.certifier.prove_exp_semantics(runtime_exp, corrupted)
        self.assertEqual(failed["status"], "identity_frontier")
        self.assertEqual(failed["comparison"]["mismatch_witness"]["delta"], -4096)

    def test_every_semantic_authority_is_materialized_from_the_pinned_git_blobs(self) -> None:
        authentication = self.certificate["source_authentication"]

        self.assertEqual(authentication["status"],
                         "materialized_git_blobs_match_authenticated_closure")
        self.assertEqual(authentication["revision"],
                         "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f")
        self.assertEqual(authentication["source_count"], 6)
        self.assertEqual(set(authentication["materialized_sources"]), {
            "tinystories/hardware_reference.py",
            "tinystories/rtl_memories.py",
            "fpga/rtl/gptneo_layernorm.sv",
            "fpga/rtl/gptneo_gelu.sv",
            "fpga/rtl/gptneo_attention.sv",
            "fpga/rtl/gptneo_iterative_divider.sv",
        })
        source_paths = set(self.certificate["identity"]["semantic_sources"])
        self.assertEqual(source_paths, set(authentication["materialized_sources"]))

    def _independent_gemv_summaries(self) -> dict[str, dict[str, dict]]:
        manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        weights_image = (PACKAGE / "weights.bin").read_bytes()
        scales_image = (PACKAGE / "scales.bin").read_bytes()
        result = {}
        for module, weight_name, bias_name in gemv_specs():
            descriptor = manifest["tensors"][weight_name]
            weight_raw = weights_image[
                descriptor["offset"]:descriptor["offset"] + descriptor["nbytes"]
            ]
            weights = torch.frombuffer(bytearray(weight_raw), dtype=torch.int8).reshape(
                descriptor["logical_shape"]
            ).to(torch.int64)
            input_scales = torch.round(torch.tensor(
                manifest["activation_scales"][f"{module}.input"], dtype=torch.float64
            ) * (1 << 24)).to(torch.int64)
            lower_scaled, upper_scaled = -128 * input_scales, 127 * input_scales
            first, second = (
                weights * lower_scaled.unsqueeze(0), weights * upper_scaled.unsqueeze(0)
            )
            accumulator_min = torch.minimum(first, second).sum(dim=1).tolist()
            accumulator_max = torch.maximum(first, second).sum(dim=1).tolist()
            scale_raw = scales_image[
                descriptor["scale_offset"]:
                descriptor["scale_offset"] + descriptor["scale_nbytes"]
            ]
            weight_scales = torch.round(
                torch.frombuffer(bytearray(scale_raw), dtype=torch.float32).to(torch.float64)
                * (1 << 24)
            ).to(torch.int64).tolist()
            if bias_name is None:
                bias = [0] * len(accumulator_min)
            else:
                bias_descriptor = manifest["tensors"][bias_name]
                bias_raw = weights_image[
                    bias_descriptor["offset"]:
                    bias_descriptor["offset"] + bias_descriptor["nbytes"]
                ]
                bias = torch.round(
                    torch.frombuffer(bytearray(bias_raw), dtype=torch.float32).to(torch.float64)
                    * (1 << 16)
                ).to(torch.int64).tolist()

            def round_shift(value: int) -> int:
                rounded = (abs(value) + (1 << 31)) >> 32
                return -rounded if value < 0 else rounded

            pre_min = [round_shift(value * scale) + offset for value, scale, offset in zip(
                accumulator_min, weight_scales, bias, strict=True
            )]
            pre_max = [round_shift(value * scale) + offset for value, scale, offset in zip(
                accumulator_max, weight_scales, bias, strict=True
            )]
            arrays = {
                "accumulator_min": accumulator_min,
                "accumulator_max": accumulator_max,
                "pre_output_q16_min": pre_min,
                "pre_output_q16_max": pre_max,
            }
            result[module] = {
                term: expected_summary(values, module, term) for term, values in arrays.items()
            }
        return result

    def test_all_49_gemvs_rederive_compact_ordered_summaries_and_ranges(self) -> None:
        gemv = self.certificate["gemv"]
        calls = gemv["calls"]
        expected = self._independent_gemv_summaries()

        self.assertEqual(gemv["status"], "all_preoutput_q16_ranges_proven")
        self.assertEqual(len(calls), 49)
        self.assertEqual(calls[0]["name"], "transformer.h.0.attn.attention.q_proj")
        self.assertEqual(calls[-1]["name"], "lm_head")
        for call in calls:
            with self.subTest(call=call["name"]):
                output_count = call["output_count"]
                self.assertNotIn("per_output_bounds", call)
                summaries = call["per_output_summaries"]
                self.assertEqual(summaries, expected[call["name"]])
                self.assertTrue(all(
                    summary["element_count"] == output_count for summary in summaries.values()
                ))
                self.assertTrue(all(call["proof"]["inequalities"].values()))
                self.assertLess(call["proof"]["pre_output_q16_abs_bound"], 2**31)
                self.assertIsNone(call["first_failure_witness"])
        self.assertEqual(max(call["proof"]["pre_output_q16_abs_bound"] for call in calls),
                         6848534)

    def test_certificate_compacts_raw_exhaustive_arrays_without_losing_order_identity(self) -> None:
        self.assertLess(CERTIFICATE.stat().st_size, 1_000_000)
        first = self.certifier.summarize_ordered_values(
            [7, -9, 7], "test.module", "test_term"
        )
        reordered = self.certifier.summarize_ordered_values(
            [7, 7, -9], "test.module", "test_term"
        )

        self.assertEqual(first, expected_summary([7, -9, 7], "test.module", "test_term"))
        self.assertEqual(reordered,
                         expected_summary([7, 7, -9], "test.module", "test_term"))
        self.assertNotEqual(first["ordered_values_sha256"], reordered["ordered_values_sha256"])
        self.assertEqual(first["element_count"], reordered["element_count"])
        self.assertEqual(first["signed_minimum"]["value"],
                         reordered["signed_minimum"]["value"])

    def test_expanded_gemv_input_box_fails_at_the_first_module_output_inequality(self) -> None:
        result = self.certifier.derive_gemv_certificate(
            PACKAGE, input_code_min=-(2**40), input_code_max=2**40,
        )

        self.assertEqual(result["status"], "identity_frontier")
        self.assertEqual(result["failing_call"], "transformer.h.0.attn.attention.q_proj")
        self.assertEqual(result["failing_output"], 0)
        self.assertEqual(result["failing_inequality"],
                         "gemv_term_fits_signed_int64")
        self.assertEqual(result["first_failure_witness"], {
            "module": "transformer.h.0.attn.attention.q_proj",
            "output": 0,
            "term": "gemv_term_fits_signed_int64",
        })


@unittest.skipUnless(PACKAGE.is_dir() and REFERENCE.is_dir(), "canonical inputs unavailable")
class IndependentFixedLogitsOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture = load_script(CAPTURE, "capture_fixed_logits")
        cls.oracle = json.loads(ORACLE.read_text(encoding="utf-8"))

    def test_oracle_is_reproduced_by_pinned_external_reference(self) -> None:
        actual = self.capture.capture_fixed_logits(CONTRACT, AUDIT, PACKAGE, REFERENCE)

        self.assertEqual(actual, self.oracle)
        self.assertEqual(actual["status"], "independent_pinned_fixed_reference")
        self.assertEqual(len(actual["logits"]["values"]), 50257)
        self.assertEqual(actual["next_token"], 11)
        self.assertEqual(actual["oracle_sha256"], self.capture.oracle_sha256(actual))

    def test_oracle_vector_hash_agrees_with_existing_independent_softmax_receipt(self) -> None:
        softmax = json.loads(SOFTMAX.read_text(encoding="utf-8"))
        values = self.oracle["logits"]["values"]

        self.assertEqual(
            self.oracle["logits"]["canonical_sha256"],
            hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest(),
        )
        self.assertEqual(
            self.oracle["logits"]["canonical_sha256"],
            softmax["last_token_logits_q16_16_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
