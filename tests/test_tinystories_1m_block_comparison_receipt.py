"""Tests for the complete-block comparison evidence receipt."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/receipt_tinystories_1m_block_comparison.py"
SLICE_SCHEMA = "tinystories-1m-compiler-slice-manifest-v1"
spec = importlib.util.spec_from_file_location("block_receipt", SCRIPT)
assert spec and spec.loader
receipt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipt)


def sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def zeros(shape: tuple[int, ...]) -> object:
    if not shape:
        return 0
    return [zeros(shape[1:]) for _ in range(shape[0])]


def contract() -> dict[str, object]:
    return {"model": {"name": "TinyStories-1M"}, "reference": {"prompt_tokens": [1, 2, 3, 4]}}


def manifest(*, accepted: bool = False) -> dict[str, object]:
    status = "accepted" if accepted else "unavailable"
    return {
        "schema": SLICE_SCHEMA,
        "status": status,
        "model": "TinyStories-1M",
        "slice": {"kind": receipt.SLICE_KIND, "status": status},
    }


def trace(manifest_sha: str, contract_sha: str, *, alter: str | None = None) -> dict[str, object]:
    identity = {"model": "TinyStories-1M", "contract_sha256": contract_sha, "slice_kind": receipt.SLICE_KIND, "slice_manifest_sha256": manifest_sha, "block_index": 0, "token_index": 3, "input_tokens_sha256": sha([1, 2, 3, 4])}
    checkpoints = {}
    for name, shape in receipt.CHECKPOINTS:
        values = zeros(shape)
        if name == alter:
            values = [1] + values[1:]
        payload = {"shape": list(shape), "values": values}
        checkpoints[name] = {**payload, "sha256": sha(payload)}
    value = {"schema": receipt.TRACE_SCHEMA, "identity": identity, "checkpoints": checkpoints}
    return {**value, "sha256": sha(value)}


class BlockReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.contract_path = root / "contract.json"
        self.manifest_path = root / "slice.json"
        self.contract_path.write_text(json.dumps(contract()), encoding="utf-8")
        self.manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
        self.contract_sha = receipt.sha256_file(self.contract_path)
        self.manifest_sha = receipt.sha256_file(self.manifest_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def side(self, *, alter: str | None = None) -> dict[str, object]:
        return {"trace": trace(self.manifest_sha, self.contract_sha, alter=alter), "output_tokens": [10, 11, 12]}

    def add_metric(self, side: dict[str, object], side_name: str, kind: str, value: object) -> None:
        report = Path(self.tmp.name) / f"{side_name}-{kind}.json"
        measurement_id = f"{side_name}-{kind}"
        binding = {
            "side": side_name,
            "measurement_kind": kind,
            "contract_sha256": self.contract_sha,
            "slice_manifest_sha256": self.manifest_sha,
            "measurement_id": measurement_id,
        }
        report_payload = {"measurement_id": measurement_id, "binding": binding, "value": value}
        report.write_text(json.dumps(report_payload, allow_nan=False), encoding="utf-8")
        side[kind] = {
            "path": str(report),
            "sha256": receipt.sha256_file(report),
            "measurement_id": measurement_id,
            "binding": binding,
            "value": value,
        }

    def complete_sides(self) -> tuple[dict[str, object], dict[str, object]]:
        reference = self.side()
        compiler = self.side()
        values = {
            "resources": {"lut": 1},
            "timing": {"wns_ns": 0.1},
            "memory": {"bytes": 1},
            "latency": {"seconds": 0.1},
            "throughput": {"tokens_per_second": 1.0},
        }
        for side_name, side in (("reference", reference), ("compiler", compiler)):
            side["provenance"] = {"source": side_name, "llm_assistance_disclosure": "disclosed", "reference_role": "behavioral oracle"}
            for kind, value in values.items():
                self.add_metric(side, side_name, kind, value)
        return reference, compiler

    def test_missing_evidence_is_explicitly_incomplete(self) -> None:
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, {}, {})
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["claims"]["functional_equivalence"])
        for kind in ("resources", "timing", "memory", "latency", "throughput"):
            self.assertEqual(result["evidence"][kind]["status"], "unavailable")
        self.assertIn("complete reference/compiler functional traces", " ".join(result["blocking_reasons"]))

    def test_trace_requires_complete_fixed_qk_checkpoint_set(self) -> None:
        bad = self.side()
        del bad["trace"]["checkpoints"]["block.attention.k.int8"]
        bad["trace"].pop("sha256")
        bad["trace"]["sha256"] = sha({key: value for key, value in bad["trace"].items() if key != "sha256"})
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, bad, self.side())
        self.assertEqual(result["evidence"]["functional"]["status"], "unavailable")

    def test_metric_hash_or_binding_failure_stays_unavailable(self) -> None:
        side = self.side()
        report = Path(self.tmp.name) / "yosys.json"
        report.write_text('{"lut": 1}', encoding="utf-8")
        side["resources"] = {"path": str(report), "sha256": "0" * 64, "measurement_id": "r", "binding": {"side": "reference", "measurement_kind": "resources", "contract_sha256": self.contract_sha, "slice_manifest_sha256": self.manifest_sha, "measurement_id": "r"}, "value": {"lut": 1}}
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, side, {})
        self.assertEqual(result["evidence"]["resources"]["reference"]["status"], "unavailable")

    def test_complete_synthetic_receipt_requires_every_category_and_both_provenances(self) -> None:
        reference, compiler = self.complete_sides()
        accepted_manifest = manifest(accepted=True)
        result = receipt.build_receipt(contract(), self.contract_sha, accepted_manifest, self.manifest_sha, reference, compiler)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["claims"]["functional_equivalence"])
        self.assertFalse(result["claims"]["optimization"])
        self.assertFalse(result["claims"]["hardware_inference"])

    def test_same_tokens_with_different_checkpoint_is_mismatch(self) -> None:
        result = receipt.build_receipt(
            contract(), self.contract_sha, manifest(accepted=True), self.manifest_sha,
            self.side(), self.side(alter="block.ln_1.output"),
        )
        functional = result["evidence"]["functional"]
        self.assertEqual(functional["status"], "mismatch")
        self.assertEqual(functional["first_mismatch"]["checkpoint"], "block.ln_1.output")

    def test_complete_claim_requires_accepted_slice_manifest(self) -> None:
        reference, compiler = self.complete_sides()
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, reference, compiler)
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["claims"]["functional_equivalence"])
        self.assertIn("slice manifest", " ".join(result["blocking_reasons"]))

    def test_metric_value_must_equal_hashed_report_value(self) -> None:
        side = self.side()
        self.add_metric(side, "reference", "resources", {"lut": 1})
        side["resources"]["value"] = {"lut": 999}
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, side, {})
        self.assertEqual(result["evidence"]["resources"]["reference"]["status"], "unavailable")

    def test_metric_domain_rejects_negative_latency(self) -> None:
        side = self.side()
        self.add_metric(side, "reference", "latency", {"seconds": -1.0})
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, side, {})
        self.assertEqual(result["evidence"]["latency"]["reference"]["status"], "unavailable")

    def test_receipt_has_canonical_self_hash(self) -> None:
        result = receipt.build_receipt(contract(), self.contract_sha, manifest(), self.manifest_sha, {}, {})
        digest = result.pop("sha256")
        self.assertEqual(digest, receipt.canonical_sha256(result))

    def test_cli_hashes_all_supplied_evidence_inputs(self) -> None:
        reference_path = Path(self.tmp.name) / "reference.json"
        compiler_path = Path(self.tmp.name) / "compiler.json"
        probe_path = Path(self.tmp.name) / "probe.json"
        out_path = Path(self.tmp.name) / "receipt.json"
        reference_path.write_text(json.dumps(self.side()), encoding="utf-8")
        compiler_path.write_text(json.dumps(self.side()), encoding="utf-8")
        probe_path.write_text(json.dumps({"schema": receipt.FIXED_QK_TRACE_SCHEMA}), encoding="utf-8")
        self.assertEqual(receipt.main([
            "--contract", str(self.contract_path), "--slice-manifest", str(self.manifest_path),
            "--reference-evidence", str(reference_path), "--compiler-evidence", str(compiler_path),
            "--fixed-qk-probe", str(probe_path), "--out", str(out_path),
        ]), 0)
        result = json.loads(out_path.read_text(encoding="utf-8"))
        for key, path in (("reference_evidence", reference_path), ("compiler_evidence", compiler_path), ("fixed_qk_probe", probe_path)):
            self.assertEqual(result["inputs"][key]["sha256"], receipt.sha256_file(path))
        digest = result.pop("sha256")
        self.assertEqual(digest, receipt.canonical_sha256(result))

    def test_equal_outputs_are_checked_against_frozen_reference_when_present(self) -> None:
        frozen = contract()
        frozen["reference"]["tokens"] = [99]
        reference = self.side()
        compiler = self.side()
        result = receipt.build_receipt(frozen, self.contract_sha, manifest(), self.manifest_sha, reference, compiler)
        self.assertEqual(result["evidence"]["functional"]["status"], "mismatch")
        self.assertEqual(result["evidence"]["functional"]["first_mismatch"]["checkpoint"], "final_output_tokens")


if __name__ == "__main__":
    unittest.main()
