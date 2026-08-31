#!/usr/bin/env python3
"""Contract tests for the exact TinyStories flat-SCF memref frontier."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py"
CONTRACT = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json"
)
REPRODUCERS = ROOT / "reproducers/tinystories-1m-exact-flat-scf-memref"
LIVE_RUN = (
    ROOT
    / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1"
)
REGISTERED = {
    "memref.reinterpret_cast",
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
}


FIXTURE = """module {
  func.func @fixture(
      %src: memref<6xi64, strided<[1]>>,
      %matrix: memref<2x3xi64>,
      %flat: memref<6xi64>,
      %dst: memref<2x3xi64>) {
    %view = memref.reinterpret_cast %src to
      offset: [0],
      sizes: [2, 3],
      strides: [3, 1] :
      memref<6xi64, strided<[1]>> to memref<2x3xi64>
      loc("fixture.mlir":10:5)
    %collapsed = memref.collapse_shape %matrix
      [[0, 1]] : memref<2x3xi64> into memref<6xi64>
      loc("fixture.mlir":14:5)
    memref.copy %matrix, %dst :
      memref<2x3xi64> to memref<2x3xi64>
      loc("fixture.mlir":17:5)
    %expanded = memref.expand_shape %flat
      [[0, 1]] output_shape [2, 3] :
      memref<6xi64> into memref<2x3xi64>
      loc("fixture.mlir":20:5)
    return
  }
}
"""


def load_module(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"required production module is absent: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load production module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_self_hash(payload: dict) -> str:
    rebound = copy.deepcopy(payload)
    rebound["sha256"] = None
    raw = json.dumps(rebound, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class MissingProductionSurfaceRedTest(unittest.TestCase):
    def test_extractor_exists(self) -> None:
        self.assertTrue(EXTRACTOR.is_file(), f"absent extractor: {EXTRACTOR}")

    def test_verifier_exists(self) -> None:
        self.assertTrue(VERIFIER.is_file(), f"absent verifier: {VERIFIER}")

    def test_contract_exists(self) -> None:
        self.assertTrue(CONTRACT.is_file(), f"absent contract: {CONTRACT}")

    def test_representatives_exist(self) -> None:
        self.assertTrue(
            REPRODUCERS.is_dir(), f"absent representatives: {REPRODUCERS}"
        )


class BalancedOperationParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = load_module(EXTRACTOR, "exact_memref_extractor")

    def test_balanced_multiline_parser_finds_exact_registered_operations(self) -> None:
        operations = self.extractor.parse_registered_operations(FIXTURE)
        self.assertEqual({operation["operation"] for operation in operations}, REGISTERED)
        self.assertEqual(len(operations), 4)
        by_name = {operation["operation"]: operation for operation in operations}
        reinterpret = by_name["memref.reinterpret_cast"]
        self.assertEqual(reinterpret["source_location"]["line"], 7)
        self.assertEqual(reinterpret["source_location"]["function"], "fixture")
        self.assertEqual(
            reinterpret["source_location"]["mlir"], 'loc("fixture.mlir":10:5)'
        )
        self.assertIn("strides: [3, 1]", reinterpret["text"])
        self.assertEqual(reinterpret["signature"]["offset"], [0])
        self.assertEqual(reinterpret["signature"]["sizes"], [2, 3])
        self.assertEqual(reinterpret["signature"]["strides"], [3, 1])

    def test_signatures_preserve_types_layouts_shapes_and_reassociation(self) -> None:
        by_name = {
            operation["operation"]: operation["signature"]
            for operation in self.extractor.parse_registered_operations(FIXTURE)
        }
        reinterpret = by_name["memref.reinterpret_cast"]
        self.assertEqual(reinterpret["operand_types"], ["memref<6xi64, strided<[1]>>"])
        self.assertEqual(reinterpret["result_types"], ["memref<2x3xi64>"])
        self.assertEqual(reinterpret["operand_memrefs"][0]["shape"], [6])
        self.assertEqual(reinterpret["operand_memrefs"][0]["strides"], [1])
        self.assertEqual(reinterpret["operand_memrefs"][0]["offset"], 0)
        collapse = by_name["memref.collapse_shape"]
        expand = by_name["memref.expand_shape"]
        self.assertEqual(collapse["reassociation"], [[0, 1]])
        self.assertEqual(expand["reassociation"], [[0, 1]])
        self.assertEqual(expand["output_shape"], [2, 3])
        self.assertEqual(expand["dynamic_operands"], [])

    def test_comments_and_strings_do_not_create_false_operations(self) -> None:
        text = FIXTURE.replace(
            "module {",
            '// memref.copy %fake, %fake : memref<1xi8> to memref<1xi8>\n'
            'module attributes {note = "memref.expand_shape"} {',
        )
        operations = self.extractor.parse_registered_operations(text)
        self.assertEqual(len(operations), 4)

    def test_blocker_report_is_compared_by_exact_class_count_and_location(self) -> None:
        operations = self.extractor.parse_registered_operations(FIXTURE)
        report = {
            "stage": "flat-scf",
            "blockers": [
                {"op": operation, "count": 1} for operation in sorted(REGISTERED)
            ],
            "locations": [
                {
                    "op": operation["operation"],
                    "line": operation["source_location"]["line"],
                    "function": "fixture",
                    "text": operation["text"].splitlines()[0].strip(),
                }
                for operation in operations
            ],
        }
        self.extractor.verify_blocker_report(operations, report)

        stale = copy.deepcopy(report)
        stale["blockers"][0]["count"] = 2
        with self.assertRaisesRegex(ValueError, "count"):
            self.extractor.verify_blocker_report(operations, stale)

        relocated = copy.deepcopy(report)
        relocated["locations"][0]["line"] += 1
        with self.assertRaisesRegex(ValueError, "location"):
            self.extractor.verify_blocker_report(operations, relocated)

        unknown = copy.deepcopy(report)
        unknown["blockers"].append({"op": "memref.subview", "count": 1})
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.extractor.verify_blocker_report(operations, unknown)

    def test_malformed_static_affine_metadata_fails_closed(self) -> None:
        bad_cases = {
            "reinterpret rank": FIXTURE.replace("sizes: [2, 3]", "sizes: [6]"),
            "strided layout": FIXTURE.replace(
                "strided<[1]>", "strided<[1, 2]>"
            ),
            "collapse reassociation": FIXTURE.replace("[[0, 1]] :", "[[0, 2]] :", 1),
            "expand output shape": FIXTURE.replace("output_shape [2, 3]", "output_shape [2, 4]"),
        }
        for name, text in bad_cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.extractor.parse_registered_operations(text)

    def test_representative_selection_is_lexicographic_and_not_input_order(self) -> None:
        operations = self.extractor.parse_registered_operations(FIXTURE)
        first = operations[0]
        altered = copy.deepcopy(first)
        altered["source_location"] = {
            "line": 999,
            "column": 1,
            "function": "zeta",
            "mlir": None,
        }
        altered["signature"] = copy.deepcopy(first["signature"])
        altered["signature"]["sizes"] = [3, 2]
        selected = self.extractor.select_representatives([altered, *operations])
        expected = min(
            [first, altered],
            key=self.extractor.representative_selection_tuple,
        )
        self.assertEqual(selected["memref.reinterpret_cast"], expected)


class CommittedContractIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = load_module(EXTRACTOR, "exact_memref_extractor_integration")

    def test_all_required_artifacts_exist_and_contract_is_canonical_self_hashed(self) -> None:
        self.assertTrue(VERIFIER.is_file(), VERIFIER)
        self.assertTrue(CONTRACT.is_file(), CONTRACT)
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "tinystories-1m-exact-memref-blockers-v1")
        self.assertEqual(payload["sha256"], canonical_self_hash(payload))
        self.assertEqual(set(payload["classes"]), REGISTERED)
        self.assertFalse(payload["nix"]["current_output_realized"])
        self.assertNotEqual(
            payload["nix"]["current_derivation"], payload["nix"]["c22_derivation"]
        )
        self.assertEqual(
            payload["nix"]["payload_source"],
            "retained-authenticated-c22-output",
        )
        self.assertEqual(payload["task1_runtime_equivalence"]["file_count"], 29)
        self.assertEqual(len(payload["task1_runtime_equivalence"]["files"]), 29)
        self.assertEqual(
            sum(entry["count"] for entry in payload["classes"].values()),
            len(payload["locations"]),
        )
        for operation in REGISTERED:
            entry = payload["classes"][operation]
            self.assertGreater(entry["count"], 0)
            self.assertEqual(sum(item["multiplicity"] for item in entry["signatures"]), entry["count"])
            representative = ROOT / entry["representative"]["path"]
            interestingness = ROOT / entry["representative"]["interestingness_test"]
            metadata = ROOT / entry["representative"]["metadata"]
            self.assertTrue(representative.is_file())
            self.assertTrue(interestingness.is_file())
            self.assertTrue(metadata.is_file())

    def test_contract_counts_locations_and_signatures_are_recomputed_from_live_mlir(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        operations = self.extractor.parse_registered_operations(
            (LIVE_RUN / "flat.scf.mlir").read_text(encoding="utf-8")
        )
        recomputed = self.extractor.summarize_operations(operations)
        self.assertEqual(payload["classes"], recomputed["classes"])
        self.assertEqual(payload["locations"], recomputed["locations"])
        self.extractor.verify_blocker_report(
            operations,
            json.loads((LIVE_RUN / "blockers.json").read_text(encoding="utf-8")),
        )

    def test_public_verifier_recomputes_contract_and_checks_pinned_representatives(self) -> None:
        completed = subprocess.run(
            ["python", str(VERIFIER), "--skip-nix-resolution"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("PASS", completed.stdout)
        self.assertIn("independently recomputed", completed.stdout)

    def test_every_representative_parses_and_exact_interestingness_accepts_only_its_signature(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        for operation, entry in payload["classes"].items():
            representative = ROOT / entry["representative"]["path"]
            interestingness = ROOT / entry["representative"]["interestingness_test"]
            accepted = subprocess.run(
                [str(interestingness), str(representative)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(
                accepted.returncode,
                0,
                f"{operation}: {accepted.stdout}{accepted.stderr}",
            )
            with tempfile.TemporaryDirectory() as directory:
                altered = Path(directory) / "altered.mlir"
                altered.write_text(
                    representative.read_text(encoding="utf-8").replace(
                        operation, "memref.subview", 1
                    ),
                    encoding="utf-8",
                )
                rejected = subprocess.run(
                    [str(interestingness), str(altered)],
                    cwd=ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                self.assertNotEqual(rejected.returncode, 0, operation)

    def test_verifier_rejects_stale_payload_unknown_class_and_broken_representative(self) -> None:
        verifier = load_module(VERIFIER, "exact_memref_verifier_attacks")
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPRODUCERS, root / "reproducers")
            copied = copy.deepcopy(payload)
            copied["source"]["flat_scf"]["sha256"] = "0" * 64
            copied["sha256"] = canonical_self_hash(copied)
            with self.assertRaisesRegex(ValueError, "flat.scf.mlir"):
                verifier.verify_contract_payload(
                    copied,
                    ROOT,
                    LIVE_RUN / "flat.scf.mlir",
                    LIVE_RUN / "blockers.json",
                    LIVE_RUN / "minimal-reproducer.json",
                    LIVE_RUN / "receipt.json",
                    skip_nix_resolution=True,
                    representative_root=root / "reproducers",
                )

            unknown = copy.deepcopy(payload)
            unknown["classes"]["memref.subview"] = copy.deepcopy(
                next(iter(unknown["classes"].values()))
            )
            unknown["sha256"] = canonical_self_hash(unknown)
            with self.assertRaisesRegex(ValueError, "unknown"):
                verifier.verify_contract_payload(
                    unknown,
                    ROOT,
                    LIVE_RUN / "flat.scf.mlir",
                    LIVE_RUN / "blockers.json",
                    LIVE_RUN / "minimal-reproducer.json",
                    LIVE_RUN / "receipt.json",
                    skip_nix_resolution=True,
                    representative_root=root / "reproducers",
                )

            broken = copy.deepcopy(payload)
            representative = next(iter(broken["classes"].values()))["representative"]
            broken_path = root / "reproducers" / Path(representative["path"]).relative_to(REPRODUCERS.relative_to(ROOT))
            broken_path.write_text("module { this is not mlir }\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "representative"):
                verifier.verify_contract_payload(
                    broken,
                    ROOT,
                    LIVE_RUN / "flat.scf.mlir",
                    LIVE_RUN / "blockers.json",
                    LIVE_RUN / "minimal-reproducer.json",
                    LIVE_RUN / "receipt.json",
                    skip_nix_resolution=True,
                    representative_root=root / "reproducers",
                )


if __name__ == "__main__":
    unittest.main()
