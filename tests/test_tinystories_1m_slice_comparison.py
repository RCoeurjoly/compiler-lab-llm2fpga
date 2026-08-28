"""Tests for the fail-closed TinyStories-1M slice comparison harness."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/comparison/compare_tinystories_1m_slice.py"
CONTRACT_PATH = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
SLICE_MANIFEST_PATH = ROOT / "artifacts/comparison/tinystories-1m-slice-manifest.json"

TRACE_SCHEMA = "tinystories-1m-transformer-block-token-step-trace-v1"
CHECKPOINT_SHAPES = {
    "block.input": [64],
    "block.ln_1.output": [64],
    "block.attention.q": [16, 4],
    "block.attention.k": [16, 4],
    "block.attention.v": [16, 4],
    "block.attention.output": [64],
    "block.residual.attention": [64],
    "block.ln_2.output": [64],
    "block.mlp.fc_in": [256],
    "block.mlp.activation": [256],
    "block.mlp.fc_out": [64],
    "block.output": [64],
}


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def zero_tensor(shape: list[int]) -> object:
    if len(shape) == 1:
        return [0] * shape[0]
    return [zero_tensor(shape[1:]) for _ in range(shape[0])]


def trace_identity(manifest: dict[str, object]) -> dict[str, object]:
    contract = fixture_contract()
    return {
        "model": "TinyStories-1M",
        "contract_sha256": comparison.sha256_file(CONTRACT_PATH),
        "slice_kind": "one_transformer_block_token_step",
        "slice_manifest_sha256": canonical_sha256(manifest),
        "block_index": 0,
        "token_index": 3,
        "input_tokens_sha256": canonical_sha256(contract["reference"]["prompt_tokens"]),
    }


def make_trace(manifest: dict[str, object], shapes: dict[str, list[int]] | None = None) -> dict[str, object]:
    selected_shapes = CHECKPOINT_SHAPES if shapes is None else shapes
    checkpoints = {}
    for name, shape in selected_shapes.items():
        values = zero_tensor(shape)
        payload = {"shape": shape, "values": values}
        checkpoints[name] = {**payload, "sha256": canonical_sha256(payload)}
    trace = {
        "schema": TRACE_SCHEMA,
        "identity": trace_identity(manifest),
        "checkpoints": checkpoints,
    }
    trace["sha256"] = canonical_sha256(trace)
    return trace


def rehash_trace(trace: dict[str, object]) -> None:
    trace.pop("sha256", None)
    trace["sha256"] = canonical_sha256(trace)


def set_checkpoint(evidence: dict[str, object], name: str, values: object) -> None:
    checkpoint = evidence["trace"]["checkpoints"][name]
    payload = {"shape": checkpoint["shape"], "values": values}
    evidence["trace"]["checkpoints"][name] = {**payload, "sha256": canonical_sha256(payload)}
    rehash_trace(evidence["trace"])
    evidence["checkpoint_tensors"][name] = values


def load_module():
    spec = importlib.util.spec_from_file_location("compare_tinystories_1m_slice", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


comparison = load_module()
_FIXTURE_TEMP_DIRS: list[tempfile.TemporaryDirectory[str]] = []


def fixture_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def fixture_slice_manifest() -> dict[str, object]:
    source = ROOT / "tests/fixtures/tinystories-1m-slice-source.sv"
    extracted = ROOT / "tests/fixtures/tinystories-1m-slice-extracted.sv"
    metadata = ROOT / "tests/fixtures/tinystories-1m-slice-metadata.json"
    identity = metadata_contract_identity()
    return {
        "schema": "tinystories-1m-compiler-slice-manifest-v1",
        "status": "ready",
        "model": "TinyStories-1M",
        "contract": {
            "path": "artifacts/reference/tinystories-1m-kev-gpt-contract.json",
            "sha256": comparison.sha256_file(CONTRACT_PATH),
            "identity": identity,
        },
        "source_metadata": {"path": str(metadata), "sha256": comparison.sha256_file(metadata)},
        "slice": {
            "kind": "one_transformer_block_token_step",
            "anchor_module": "transformer_block_token_step",
            "dependency_closure": ["transformer_block_token_step"],
            "artifacts": [{
                "module": "transformer_block_token_step",
                "source": str(source),
                "source_sha256": comparison.sha256_file(source),
                "extracted": str(extracted),
                "sha256": comparison.sha256_file(extracted),
            }],
        },
    }


def metadata_contract_identity() -> dict[str, object]:
    contract = fixture_contract()
    return {
        "model": {key: contract["model"][key] for key in ("name", "source_model_id", "source_revision")},
        "package": {key: contract["package"][key] for key in ("sha256", "manifest_sha256")},
    }


def fixtures() -> tuple[dict[str, object], dict[str, object]]:
    manifest = fixture_slice_manifest()
    report_directory = tempfile.TemporaryDirectory(prefix="tinystories-1m-evidence-")
    _FIXTURE_TEMP_DIRS.append(report_directory)
    report_root = Path(report_directory.name)
    reference_artifact = report_root / "reference-netlist.v"
    compiler_artifact = report_root / "compiler-netlist.v"
    shutil.copyfile(ROOT / "tests/fixtures/tinystories-1m-slice-extracted.sv", reference_artifact)
    shutil.copyfile(ROOT / "tests/fixtures/tinystories-1m-slice-extracted.sv", compiler_artifact)
    contract_sha256 = comparison.sha256_file(CONTRACT_PATH)
    slice_manifest_sha256 = canonical_sha256(manifest)

    def binding(side: str, kind: str, artifact: Path, measurement_id: str) -> dict[str, object]:
        return {
            "side": side,
            "measurement_kind": kind,
            "contract_sha256": contract_sha256,
            "slice_manifest_sha256": slice_manifest_sha256,
            "artifact_path": str(artifact),
            "artifact_sha256": comparison.sha256_file(artifact),
            "measurement_id": measurement_id,
        }

    reference_resource_report = report_root / "reference-yosys.json"
    compiler_resource_report = report_root / "compiler-yosys.json"
    reference_resource_binding = binding("reference", "resources", reference_artifact, "reference-yosys")
    compiler_resource_binding = binding("compiler", "resources", compiler_artifact, "compiler-yosys")
    reference_resource_report.write_text(json.dumps({"cells": {"lut": 100, "ff": 20, "bram": 2, "dsp": 3, "memory_bits": 512}, "evidence_binding": reference_resource_binding}), encoding="utf-8")
    compiler_resource_report.write_text(json.dumps({"cells": {"lut": 120, "ff": 25, "bram": 2, "dsp": 3, "memory_bits": 1024}, "evidence_binding": compiler_resource_binding}), encoding="utf-8")

    def timing_receipt(path: Path, evidence_binding: dict[str, object], frequency: float, delay: float, cycles: int, overhead: int) -> None:
        lines = [
            f"Max frequency: {frequency} MHz",
            *(f"{key}: {value}" for key, value in evidence_binding.items()),
            f"clock domain 'core_clk' max frequency: {frequency} MHz",
            f"critical path domain='core_clk' from='block/state_q[0]' to='block/out_q[0]' delay={delay} ns",
            f"cycles_per_token: {cycles}",
            f"interface_overhead_cycles: {overhead}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    reference_timing_report = report_root / "reference-nextpnr.rpt"
    compiler_timing_report = report_root / "compiler-nextpnr.rpt"
    reference_timing_binding = binding("reference", "timing", reference_artifact, "reference-timing")
    compiler_timing_binding = binding("compiler", "timing", compiler_artifact, "compiler-timing")
    timing_receipt(reference_timing_report, reference_timing_binding, 100.0, 10.0, 4, 1)
    timing_receipt(compiler_timing_report, compiler_timing_binding, 80.0, 12.5, 5, 2)
    trace = make_trace(manifest)
    checkpoint_tensors = {name: entry["values"] for name, entry in trace["checkpoints"].items()}
    reference = {
        "contract": fixture_contract(),
        "contract_sha256": comparison.sha256_file(CONTRACT_PATH),
        "checkpoint_tensors": checkpoint_tensors,
        "trace": json.loads(json.dumps(trace)),
        "output_tokens": fixture_contract()["reference"]["tokens"],
        "resources": {"lut": 100, "ff": 20, "bram": 2, "dsp": 3, "memory_bits": 512, "path": str(reference_resource_report), "sha256": comparison.sha256_file(reference_resource_report), **reference_resource_binding},
        "timing": {"max_frequency_mhz": 100.0, "critical_paths": [{"clock_domain": "core_clk", "from": "block/state_q[0]", "to": "block/out_q[0]", "delay_ns": 10.0}], "clock_domains": [{"name": "core_clk", "max_frequency_mhz": 100.0}], "cycles_per_token": 4, "interface_overhead_cycles": 1, "path": str(reference_timing_report), "sha256": comparison.sha256_file(reference_timing_report), **reference_timing_binding},
        "provenance": {"source": "reference-fixture"},
    }
    compiler = {
        "contract": fixture_contract(),
        "contract_sha256": comparison.sha256_file(CONTRACT_PATH),
        "checkpoint_tensors": json.loads(json.dumps(checkpoint_tensors)),
        "trace": json.loads(json.dumps(trace)),
        "output_tokens": fixture_contract()["reference"]["tokens"],
        "resources": {"lut": 120, "ff": 25, "bram": 2, "dsp": 3, "memory_bits": 1024, "path": str(compiler_resource_report), "sha256": comparison.sha256_file(compiler_resource_report), **compiler_resource_binding},
        "timing": {"max_frequency_mhz": 80.0, "critical_paths": [{"clock_domain": "core_clk", "from": "block/state_q[0]", "to": "block/out_q[0]", "delay_ns": 12.5}], "clock_domains": [{"name": "core_clk", "max_frequency_mhz": 80.0}], "cycles_per_token": 5, "interface_overhead_cycles": 2, "path": str(compiler_timing_report), "sha256": comparison.sha256_file(compiler_timing_report), **compiler_timing_binding},
        "provenance": {
            "source": "compiler-fixture",
            "annotations": [
                {"kind": "buffer", "module": "block.buffer", "source_operation": "aten.add", "compiler_stage": "lowering", "resource": "lut", "measurement_id": "compiler-yosys", "measured_delta": 20}
            ],
        },
    }
    return reference, compiler


def run_compare(reference: dict[str, object], compiler: dict[str, object], manifest: dict[str, object], **kwargs: object) -> dict[str, object]:
    return comparison.compare(reference, compiler, manifest, frozen_contract=fixture_contract(), frozen_contract_path=CONTRACT_PATH, frozen_contract_sha256=comparison.sha256_file(CONTRACT_PATH), **kwargs)


class TinyStories1MSliceComparisonTest(unittest.TestCase):
    def test_comparison_rejects_mismatched_quantization(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest(), quantization="different")
        self.assertEqual(result["status"], "contract_mismatch")
        self.assertIn("quantization", result["reasons"][0])

    def test_comparison_reports_resource_and_timing_fields_when_aligned(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "aligned")
        self.assertEqual(result["resources"]["lut_delta"], 20)
        self.assertEqual(result["timing"]["critical_paths"]["compiler"][0]["delay_ns"], 12.5)
        self.assertEqual(result["timing"]["critical_paths"]["compiler"][0]["clock_domain"], "core_clk")
        self.assertEqual(result["timing"]["cycles_per_token_delta"], 1)
        self.assertEqual(result["waste_map"][0]["source_operation"], "aten.add")

    def test_requires_exact_checkpoints_and_final_outputs_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        del compiler["checkpoint_tensors"]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])

    def test_empty_checkpoints_or_tokens_are_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        compiler["checkpoint_tensors"] = {}
        compiler["output_tokens"] = []
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])

    def test_null_or_malformed_checkpoint_tensor_is_incomplete(self) -> None:
        malformed_values = (None, True, [1, True], [1, None], [[1], [2, 3]], [float("inf")], "not-a-tensor", {})
        for value in malformed_values:
            with self.subTest(value=value):
                reference, compiler = fixtures()
                compiler["checkpoint_tensors"] = {"block.out": value}
                result = run_compare(reference, compiler, fixture_slice_manifest())
                self.assertEqual(result["status"], "incomplete")
                self.assertIsNone(result["resources"])

    def test_boolean_or_out_of_range_output_token_is_incomplete(self) -> None:
        for value in ([True], [-1], [0x10000], [1.5]):
            with self.subTest(value=value):
                reference, compiler = fixtures()
                compiler["output_tokens"] = value
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_empty_resource_or_timing_evidence_is_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        compiler["resources"] = {}
        compiler["timing"] = {"max_frequency_mhz": 80.0, "critical_paths": [], "cycles_per_token": 5, "interface_overhead_cycles": 2}
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        self.assertIsNone(result["timing"])

    def test_missing_report_provenance_is_incomplete_not_aligned(self) -> None:
        reference, compiler = fixtures()
        del compiler["resources"]["sha256"]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        for evidence_kind in ("resources", "timing"):
            with self.subTest(evidence_kind=evidence_kind, field="path"):
                reference, compiler = fixtures()
                del compiler[evidence_kind]["path"]
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_compare_has_no_frozen_contract_bypass(self) -> None:
        reference, compiler = fixtures()
        with self.assertRaises(TypeError):
            comparison.compare(reference, compiler, fixture_slice_manifest())

    def test_equal_side_outputs_that_differ_from_frozen_reference_are_mismatch(self) -> None:
        reference, compiler = fixtures()
        reference["output_tokens"] = [99]
        compiler["output_tokens"] = [99]
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "functional_mismatch")

    def test_public_api_rejects_slice_manifest_contract_sha_mismatch(self) -> None:
        reference, compiler = fixtures()
        manifest = fixture_slice_manifest()
        manifest["contract"]["sha256"] = "0" * 64
        result = run_compare(reference, compiler, manifest)
        self.assertEqual(result["status"], "contract_mismatch")

    def test_report_provenance_requires_existing_content_matching_hash(self) -> None:
        reference, compiler = fixtures()
        compiler["timing"]["path"] = "/does/not/exist"
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        reference, compiler = fixtures()
        compiler["resources"]["sha256"] = "0" * 64
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")

    def test_cross_side_resource_or_timing_receipt_reuse_is_rejected(self) -> None:
        for evidence_kind in ("resources", "timing"):
            with self.subTest(evidence_kind=evidence_kind):
                reference, compiler = fixtures()
                compiler[evidence_kind] = json.loads(json.dumps(reference[evidence_kind]))
                result = run_compare(reference, compiler, fixture_slice_manifest())
                self.assertEqual(result["status"], "incomplete")
                self.assertIsNone(result[evidence_kind])

    def test_stale_synthesized_artifact_binding_is_rejected(self) -> None:
        for evidence_kind in ("resources", "timing"):
            with self.subTest(evidence_kind=evidence_kind):
                reference, compiler = fixtures()
                Path(compiler[evidence_kind]["artifact_path"]).write_text(
                    "module stale_netlist; endmodule\n", encoding="utf-8"
                )
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_every_measurement_identity_must_be_distinct(self) -> None:
        reference, compiler = fixtures()
        resource_path = Path(compiler["resources"]["path"])
        resource_receipt = json.loads(resource_path.read_text(encoding="utf-8"))
        duplicate_id = reference["resources"]["measurement_id"]
        resource_receipt["evidence_binding"]["measurement_id"] = duplicate_id
        resource_path.write_text(json.dumps(resource_receipt), encoding="utf-8")
        compiler["resources"]["measurement_id"] = duplicate_id
        compiler["resources"]["sha256"] = comparison.sha256_file(resource_path)
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_correctly_hashed_unrelated_report_cannot_authenticate_claimed_measurements(self) -> None:
        reference, compiler = fixtures()
        compiler["resources"]["path"] = str(CONTRACT_PATH)
        compiler["resources"]["sha256"] = comparison.sha256_file(CONTRACT_PATH)
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["resources"])
        reference, compiler = fixtures()
        compiler["timing"]["path"] = str(CONTRACT_PATH)
        compiler["timing"]["sha256"] = comparison.sha256_file(CONTRACT_PATH)
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_report_measurements_must_equal_parsed_contents(self) -> None:
        reference, compiler = fixtures()
        compiler["resources"]["lut"] = 121
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")
        reference, compiler = fixtures()
        compiler["timing"]["cycles_per_token"] = 6
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "incomplete")

    def test_timing_numeric_domains_are_strict(self) -> None:
        mutations = (
            ("max_frequency_mhz", 0),
            ("max_frequency_mhz", True),
            ("cycles_per_token", 0),
            ("cycles_per_token", True),
            ("interface_overhead_cycles", -1),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                reference, compiler = fixtures()
                compiler["timing"][field] = value
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")
        for value in (None, True, 0, -1, float("inf"), float("nan"), "12.5"):
            with self.subTest(delay_ns=value):
                reference, compiler = fixtures()
                compiler["timing"]["critical_paths"] = [{"clock_domain": "core_clk", "from": "start", "to": "end", "delay_ns": value}]
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_timing_clock_domain_and_endpoints_are_authenticated(self) -> None:
        for field, value in (("clock_domain", "forged_clk"), ("from", "forged/start"), ("to", "forged/end")):
            with self.subTest(field=field):
                reference, compiler = fixtures()
                compiler["timing"]["critical_paths"][0][field] = value
                self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")
        reference, compiler = fixtures()
        compiler["timing"]["clock_domains"][0]["name"] = "forged_clk"
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_ready_manifest_requires_exact_identity_and_bounded_hashed_closure(self) -> None:
        mutations = (
            ("schema", "forged-schema"),
            ("model", "TinyStories-3M"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                reference, compiler = fixtures()
                manifest = fixture_slice_manifest()
                manifest[field] = value
                self.assertEqual(run_compare(reference, compiler, manifest)["status"], "incomplete")
        for mutation in ("kind", "empty_closure", "source_hash", "extracted_hash", "contract_identity", "contract_path"):
            with self.subTest(mutation=mutation):
                reference, compiler = fixtures()
                manifest = fixture_slice_manifest()
                if mutation == "kind":
                    manifest["slice"]["kind"] = "arbitrary_slice"
                elif mutation == "empty_closure":
                    manifest["slice"]["dependency_closure"] = []
                    manifest["slice"]["artifacts"] = []
                elif mutation == "source_hash":
                    manifest["slice"]["artifacts"][0]["source_sha256"] = "0" * 64
                elif mutation == "extracted_hash":
                    manifest["slice"]["artifacts"][0]["sha256"] = "0" * 64
                elif mutation == "contract_path":
                    manifest["contract"]["path"] = str(ROOT / "tests/fixtures/tinystories-1m-slice-source.sv")
                else:
                    manifest["contract"]["identity"]["model"]["source_revision"] = "forged"
                self.assertEqual(run_compare(reference, compiler, manifest)["status"], "incomplete")

    def test_ready_manifest_rejects_hashed_non_rtl_artifact(self) -> None:
        manifest = fixture_slice_manifest()
        artifact = manifest["slice"]["artifacts"][0]
        artifact["source"] = str(CONTRACT_PATH)
        artifact["source_sha256"] = comparison.sha256_file(CONTRACT_PATH)
        artifact["extracted"] = str(CONTRACT_PATH)
        artifact["sha256"] = comparison.sha256_file(CONTRACT_PATH)
        reasons = comparison._validate_ready_slice_manifest(
            manifest,
            fixture_contract(),
            CONTRACT_PATH,
            comparison.sha256_file(CONTRACT_PATH),
        )
        self.assertTrue(reasons)
        self.assertTrue(any("RTL" in reason or "module" in reason for reason in reasons))

    def test_ready_manifest_rejects_extracted_module_content_not_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = Path(directory) / "forged.sv"
            extracted.write_text("module transformer_block_token_step; wire forged; endmodule\n", encoding="utf-8")
            manifest = fixture_slice_manifest()
            artifact = manifest["slice"]["artifacts"][0]
            artifact["extracted"] = str(extracted)
            artifact["sha256"] = comparison.sha256_file(extracted)
            reasons = comparison._validate_ready_slice_manifest(
                manifest,
                fixture_contract(),
                CONTRACT_PATH,
                comparison.sha256_file(CONTRACT_PATH),
            )
            self.assertTrue(any("content" in reason for reason in reasons))

    def test_ready_manifest_rederives_anchor_and_dependency_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "slice.sv"
            source.write_text(
                "module helper; endmodule\n"
                "// llm2fpga.slice_kind=one_transformer_block_token_step\n"
                "module transformer_block_token_step; helper u_helper(); endmodule\n",
                encoding="utf-8",
            )
            helper = root / "helper.sv"
            anchor = root / "anchor.sv"
            helper.write_text("module helper; endmodule\n", encoding="utf-8")
            anchor.write_text("module transformer_block_token_step; helper u_helper(); endmodule\n", encoding="utf-8")
            manifest = fixture_slice_manifest()
            manifest["slice"] = {
                "kind": "one_transformer_block_token_step",
                "anchor_module": "helper",
                "dependency_closure": ["helper", "transformer_block_token_step"],
                "artifacts": [
                    {"module": "helper", "source": str(source), "source_sha256": comparison.sha256_file(source), "extracted": str(helper), "sha256": comparison.sha256_file(helper)},
                    {"module": "transformer_block_token_step", "source": str(source), "source_sha256": comparison.sha256_file(source), "extracted": str(anchor), "sha256": comparison.sha256_file(anchor)},
                ],
            }
            reasons = comparison._validate_ready_slice_manifest(
                manifest,
                fixture_contract(),
                CONTRACT_PATH,
                comparison.sha256_file(CONTRACT_PATH),
            )
            self.assertTrue(any("anchor module" in reason for reason in reasons))

    def test_arbitrary_missing_or_extra_checkpoints_cannot_align(self) -> None:
        cases = {
            "arbitrary": {"arbitrary": [1]},
            "missing": {name: shape for name, shape in CHECKPOINT_SHAPES.items() if name != "block.ln_1.output"},
            "extra": {**CHECKPOINT_SHAPES, "block.unexpected": [1]},
        }
        for label, shapes in cases.items():
            with self.subTest(label=label):
                reference, compiler = fixtures()
                manifest = fixture_slice_manifest()
                reference["trace"] = make_trace(manifest, shapes)
                compiler["trace"] = make_trace(manifest, shapes)
                reference["checkpoint_tensors"] = {name: entry["values"] for name, entry in reference["trace"]["checkpoints"].items()}
                compiler["checkpoint_tensors"] = json.loads(json.dumps(reference["checkpoint_tensors"]))
                self.assertEqual(run_compare(reference, compiler, manifest)["status"], "incomplete")

    def test_trace_identity_and_checkpoint_hash_are_authenticated(self) -> None:
        reference, compiler = fixtures()
        compiler["trace"]["identity"]["token_index"] = 2
        rehash_trace(compiler["trace"])
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

        reference, compiler = fixtures()
        compiler["trace"]["checkpoints"]["block.output"]["sha256"] = "0" * 64
        rehash_trace(compiler["trace"])
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_trace_checkpoint_shapes_and_values_are_exact(self) -> None:
        reference, compiler = fixtures()
        payload = {"shape": [63], "values": [0] * 63}
        compiler["trace"]["checkpoints"]["block.output"] = {**payload, "sha256": canonical_sha256(payload)}
        compiler["checkpoint_tensors"]["block.output"] = payload["values"]
        rehash_trace(compiler["trace"])
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

        reference, compiler = fixtures()
        payload = {"shape": [64], "values": [False] + [0] * 63}
        compiler["trace"]["checkpoints"]["block.output"] = {**payload, "sha256": canonical_sha256(payload)}
        compiler["checkpoint_tensors"]["block.output"] = payload["values"]
        rehash_trace(compiler["trace"])
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["status"], "incomplete")

    def test_full_contract_identity_rejects_abi_and_reference_changes(self) -> None:
        reference, compiler = fixtures()
        compiler["contract"]["command_abi"]["version"] = 99
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")
        reference, compiler = fixtures()
        compiler["contract"]["reference"]["tokens"][0] = 12
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")

    def test_frozen_contract_hash_binds_each_evidence_side(self) -> None:
        reference, compiler = fixtures()
        compiler["contract_sha256"] = "f" * 64
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "contract_mismatch")

    def test_reports_functional_mismatch_before_efficiency_deltas(self) -> None:
        reference, compiler = fixtures()
        set_checkpoint(compiler, "block.output", [1] + [0] * 63)
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["status"], "functional_mismatch")
        self.assertIsNone(result["resources"])
        self.assertEqual(result["functional"]["first_mismatch"]["checkpoint"], "block.output")

    def test_report_parsers_preserve_raw_provenance_and_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            yosys = root / "yosys.json"
            yosys.write_text(json.dumps({"cells": {"lut": 12, "ff": 8, "bram": 1, "dsp": 2, "memory_bits": 256}}), encoding="utf-8")
            timing = root / "nextpnr.rpt"
            timing.write_text("Max frequency: 83.33 MHz\nmeasurement_id: parser-test\nclock domain 'core_clk' max frequency: 83.33 MHz\ncritical path domain='core_clk' from='start' to='end' delay=12.0 ns\ncycles_per_token: 9\ninterface_overhead_cycles: 2\n", encoding="utf-8")
            resources = comparison.parse_yosys_statistics(yosys)
            parsed_timing = comparison.parse_nextpnr_timing(timing)
            self.assertEqual(resources["lut"], 12)
            self.assertEqual(resources["sha256"], comparison.sha256_file(yosys))
            self.assertEqual(parsed_timing["max_frequency_mhz"], 83.33)
            self.assertEqual(parsed_timing["critical_paths"][0]["delay_ns"], 12.0)
            self.assertEqual(parsed_timing["critical_paths"][0]["from"], "start")
            self.assertEqual(parsed_timing["clock_domains"][0]["name"], "core_clk")
            self.assertEqual(parsed_timing["cycles_per_token"], 9)

    def test_yosys_structural_utilization_json_preserves_real_statistics(self) -> None:
        path = ROOT / "artifacts/full-tinystories-pt2e-w8a8-scout/yosys-slang-structural-utilization.json"
        parsed = comparison.parse_yosys_statistics(path)
        self.assertEqual(parsed["memory_bits"], 236744916)
        self.assertEqual(parsed["structural_cells"]["$mux"], 708653)
        self.assertIsNone(parsed["lut"])

    def test_yosys_standard_stat_json_uses_top_module_cell_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stat.json"
            path.write_text(json.dumps({"modules": {"top": {"num_cells_by_type": {"LUT6": 11, "FDRE": 12, "RAMB36E1": 2, "DSP48E1": 3}}}}), encoding="utf-8")
            parsed = comparison.parse_yosys_statistics(path)
            self.assertEqual(parsed["lut"], 11)
            self.assertEqual(parsed["ff"], 12)
            self.assertEqual(parsed["bram"], 2)
            self.assertEqual(parsed["dsp"], 3)

    def test_manifest_contract_hash_mismatch_is_not_compared(self) -> None:
        manifest = fixture_slice_manifest()
        manifest["contract"]["sha256"] = "0" * 64
        self.assertEqual(comparison.manifest_contract_status(CONTRACT_PATH, manifest), "contract_mismatch")

    def test_waste_entries_require_stage_and_exact_measured_delta(self) -> None:
        reference, compiler = fixtures()
        result = run_compare(reference, compiler, fixture_slice_manifest())
        self.assertEqual(result["waste_map"][0]["measured_delta"], 20)
        self.assertEqual(result["waste_map"][0]["measurement_id"], "compiler-yosys")
        del compiler["provenance"]["annotations"][0]["compiler_stage"]
        self.assertEqual(run_compare(reference, compiler, fixture_slice_manifest())["waste_map"], [])

    def test_checked_in_comparison_is_honestly_incomplete_without_full_artifacts(self) -> None:
        committed = ROOT / "artifacts/comparison/tinystories-1m-slice-comparison.json"
        original = committed.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.json"
            self.assertEqual(comparison.main(["--contract", str(CONTRACT_PATH), "--slice-manifest", str(SLICE_MANIFEST_PATH), "--out", str(output)]), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "incomplete")
            self.assertIsNone(result["resources"])
            self.assertIsNone(result["timing"])
        self.assertEqual(committed.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
