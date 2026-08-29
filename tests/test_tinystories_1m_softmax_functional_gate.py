from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONVERT = ROOT / "scripts/comparison/convert_softmax_to_kev_gpt_fixed_trace.py"
VERIFY = ROOT / "scripts/comparison/verify_tinystories_1m_softmax_functional_gate.py"
REFERENCE = ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
GATE = ROOT / "artifacts/comparison/tinystories-1m-softmax-functional-equivalence-gate.json"
ORACLE = ROOT / "artifacts/comparison/tinystories-1m-attention-softmax-oracle.json"
LOWERED_TRACE = ROOT / "artifacts/comparison/tinystories-1m-lowered-softmax-trace.json"
BOUND_TRACE = ROOT / "artifacts/comparison/tinystories-1m-bound-softmax-interpreter.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStories1mSoftmaxFunctionalGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.convert = load_module(CONVERT, "tinystories_softmax_fixed_convert")
        cls.verify = load_module(VERIFY, "tinystories_softmax_gate_verify")
        cls.reference = json.loads(REFERENCE.read_text(encoding="utf-8"))

    def test_float_only_trace_fails_closed_at_missing_fixed_row_boundary(self) -> None:
        report = self.convert.build_report(BOUND_TRACE, PROFILE, REFERENCE)
        self.assertEqual(report["schema"], "tinystories-1m-kev-gpt-fixed-conversion-trace-v1")
        self.assertEqual(report["status"], "fail_closed")
        self.assertEqual(
            report["comparison"]["first_missing_checkpoint"],
            "compiler_fixed_point_softmax_rows",
        )
        self.assertEqual(report["comparison"]["reference_row_count"], 16)
        self.assertFalse(report["claims"]["functional_equivalence"])

    def test_gate_reports_current_missing_compiler_numeric_boundary(self) -> None:
        report = self.verify.evaluate_gate(GATE, ORACLE, LOWERED_TRACE, REFERENCE)
        self.assertEqual(report["status"], "fail_closed")
        self.assertEqual(
            report["comparison"]["first_missing_checkpoint"],
            "compiler_fixed_point_softmax_rows",
        )
        self.assertEqual(
            report["comparison"]["blocking_artifact"]["path"],
            str(LOWERED_TRACE),
        )
        self.assertFalse(report["claims"]["functional_equivalence"])
        self.assertFalse(report["claims"]["rtl_equivalence"])
        self.assertFalse(report["claims"]["hardware_inference"])

    def test_compiler_trace_metadata_must_match_authenticated_reference_slice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            rows = json.loads(json.dumps(self.reference["softmax_rows"]))
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"] + [999],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": rows,
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, REFERENCE)
        self.assertEqual(report["status"], "fail_closed")
        self.assertEqual(
            report["comparison"]["first_missing_checkpoint"],
            "compiler_trace_metadata",
        )
        self.assertEqual(
            report["comparison"]["blocking_artifact"]["reason"],
            "metadata_mismatch",
        )
        self.assertEqual(report["comparison"]["blocking_artifact"]["field"], "prompt_tokens")

    def test_exact_fixed_point_compiler_rows_are_required_for_functional_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            rows = json.loads(json.dumps(self.reference["softmax_rows"]))
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": rows,
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, REFERENCE)
        self.assertEqual(report["status"], "matched")
        self.assertEqual(report["comparison"]["matched_rows"], 16)
        self.assertTrue(report["claims"]["functional_equivalence"])
        self.assertFalse(report["claims"]["rtl_equivalence"])
        self.assertFalse(report["claims"]["hardware_inference"])

    def test_first_row_mismatch_is_named_precisely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            rows = json.loads(json.dumps(self.reference["softmax_rows"]))
            rows[0]["score_codes_q8_8"][0] += 1
            rows[0]["sha256"] = self.convert.row_sha256(rows[0])
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": rows,
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, REFERENCE)
        self.assertEqual(report["status"], "mismatch")
        self.assertEqual(report["comparison"]["first_mismatch"]["head"], 0)
        self.assertEqual(report["comparison"]["first_mismatch"]["field"], "score_codes_q8_8")
        self.assertEqual(report["comparison"]["first_mismatch"]["index"], [0])
        self.assertFalse(report["claims"]["functional_equivalence"])

    def test_shortened_field_reports_missing_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            rows = json.loads(json.dumps(self.reference["softmax_rows"]))
            rows[0]["score_codes_q8_8"] = rows[0]["score_codes_q8_8"][:-1]
            rows[0]["sha256"] = self.convert.row_sha256(rows[0])
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": rows,
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, REFERENCE)
        self.assertEqual(report["status"], "mismatch")
        self.assertEqual(report["comparison"]["first_mismatch"]["field"], "score_codes_q8_8")
        self.assertEqual(report["comparison"]["first_mismatch"]["index"], [3])

    def test_extended_field_reports_extra_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            rows = json.loads(json.dumps(self.reference["softmax_rows"]))
            rows[0]["context_q16_16"] = rows[0]["context_q16_16"] + [7]
            rows[0]["sha256"] = self.convert.row_sha256(rows[0])
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": rows,
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, REFERENCE)
        self.assertEqual(report["status"], "mismatch")
        self.assertEqual(report["comparison"]["first_mismatch"]["field"], "context_q16_16")
        self.assertEqual(report["comparison"]["first_mismatch"]["index"], [4])

    def test_tampered_reference_rows_fail_closed_before_candidate_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reference_path = Path(directory) / "tampered-reference.json"
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            tampered_reference = json.loads(json.dumps(self.reference))
            tampered_reference["softmax_rows"][0]["score_codes_q8_8"][0] += 1
            reference_path.write_text(
                json.dumps(tampered_reference, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "prompt_tokens": self.reference["slice"]["prompt_tokens"],
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": json.loads(json.dumps(self.reference["softmax_rows"])),
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, reference_path)
        self.assertEqual(report["status"], "fail_closed")
        self.assertEqual(report["comparison"]["first_missing_checkpoint"], "reference_softmax_rows")
        self.assertEqual(report["comparison"]["blocking_artifact"]["reason"], "reference_row_identity_mismatch")
        self.assertEqual(report["comparison"]["blocking_artifact"]["head"], 0)

    def test_missing_reference_slice_prompt_tokens_fail_closed_before_candidate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reference_path = Path(directory) / "tampered-reference.json"
            trace_path = Path(directory) / "compiler-fixed-trace.json"
            tampered_reference = json.loads(json.dumps(self.reference))
            del tampered_reference["slice"]["prompt_tokens"]
            reference_path.write_text(
                json.dumps(tampered_reference, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            trace = {
                "schema": "tinystories-1m-compiler-fixed-softmax-trace-v1",
                "status": "matched",
                "block_index": self.reference["slice"]["block_index"],
                "token_index": self.reference["slice"]["token_index"],
                "rows": json.loads(json.dumps(self.reference["softmax_rows"])),
            }
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = self.verify.evaluate_gate(GATE, ORACLE, trace_path, reference_path)
        self.assertEqual(report["status"], "fail_closed")
        self.assertEqual(report["comparison"]["first_missing_checkpoint"], "reference_slice_metadata")
        self.assertEqual(report["comparison"]["blocking_artifact"]["reason"], "reference_slice_field_missing")
        self.assertEqual(report["comparison"]["blocking_artifact"]["field"], "prompt_tokens")


if __name__ == "__main__":
    unittest.main()
