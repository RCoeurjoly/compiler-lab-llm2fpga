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


def receipt_self_hash(receipt: dict) -> str:
    unsigned = {key: value for key, value in receipt.items() if key != "sha256"}
    raw = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def byte_binding(path: Path) -> dict[str, int | str]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


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
            representative = next(iter(broken["classes"].values()))[
                "representative"
            ]
            broken_path = root / "reproducers" / Path(
                representative["path"]
            ).relative_to(REPRODUCERS.relative_to(ROOT))
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


class ImmutableTrustRootAttackTest(unittest.TestCase):
    def _rebind_contract(self, contract: dict, receipt: dict, receipt_path: Path) -> None:
        receipt["sha256"] = receipt_self_hash(receipt)
        contract["source"]["c22_receipt"].update(byte_binding(receipt_path))
        contract["c22_receipt_self_sha256"] = receipt["sha256"]
        contract["task_1_through_3_identities"] = copy.deepcopy(
            receipt["frozen_task_1_through_3_identities"]
        )
        tool = next(
            binding
            for binding in receipt["registered_build_execution"]["flat-scf"][
                "derivation_tool_bindings"
            ]
            if Path(binding["path"]).name == "mlir-opt"
        )
        contract["tool"] = {
            key: tool[key] for key in ("path", "bytes", "sha256")
        }
        contract["sha256"] = canonical_self_hash(contract)

    def _run_full_default(self, contract_path: Path, receipt_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python",
                str(VERIFIER),
                "--contract",
                str(contract_path),
                "--receipt",
                str(receipt_path),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_full_default_verifier_rejects_rehashed_receipt_model_identity_and_tool_attacks(self) -> None:
        original_contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        original_receipt = json.loads(
            (LIVE_RUN / "receipt.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_tool = root / "fake" / "mlir-opt"
            fake_tool.parent.mkdir()
            fake_tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_tool.chmod(0o755)

            attacks = []

            altered_bytes = copy.deepcopy(original_receipt)
            altered_bytes["status"] = "forged-authenticated"
            attacks.append(("altered receipt bytes", altered_bytes, None))

            altered_schema = copy.deepcopy(original_receipt)
            altered_schema["schema"] = "forged-frontier-v5"
            attacks.append(("altered receipt schema", altered_schema, None))

            altered_model = copy.deepcopy(original_receipt)
            altered_model["model"] = "different-model"
            attacks.append(("altered frozen model", altered_model, "different-model"))

            altered_identity = copy.deepcopy(original_receipt)
            altered_identity["frozen_task_1_through_3_identities"][
                "adapter_sha256"
            ] = "0" * 64
            attacks.append(("altered Task 1--3 identity", altered_identity, None))

            altered_tool = copy.deepcopy(original_receipt)
            tool_binding = next(
                binding
                for binding in altered_tool["registered_build_execution"]["flat-scf"][
                    "derivation_tool_bindings"
                ]
                if Path(binding["path"]).name == "mlir-opt"
            )
            tool_binding.update({"path": str(fake_tool), **byte_binding(fake_tool)})
            attacks.append(("altered tool path hash and fake executable", altered_tool, None))

            altered_tool_hash = copy.deepcopy(original_receipt)
            hash_binding = next(
                binding
                for binding in altered_tool_hash["registered_build_execution"]["flat-scf"][
                    "derivation_tool_bindings"
                ]
                if Path(binding["path"]).name == "mlir-opt"
            )
            hash_binding["sha256"] = "f" * 64
            attacks.append(("altered tool hash", altered_tool_hash, None))

            for index, (name, receipt, model) in enumerate(attacks):
                with self.subTest(name=name):
                    receipt_path = root / f"receipt-{index}.json"
                    contract_path = root / f"contract-{index}.json"
                    contract = copy.deepcopy(original_contract)
                    if model is not None:
                        contract["model"] = model
                    receipt["sha256"] = receipt_self_hash(receipt)
                    receipt_path.write_text(
                        json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
                    )
                    self._rebind_contract(contract, receipt, receipt_path)
                    receipt_path.write_text(
                        json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
                    )
                    contract["source"]["c22_receipt"].update(byte_binding(receipt_path))
                    contract["sha256"] = canonical_self_hash(contract)
                    contract_path.write_text(
                        json.dumps(contract, sort_keys=True) + "\n", encoding="utf-8"
                    )
                    completed = self._run_full_default(contract_path, receipt_path)
                    self.assertNotEqual(
                        completed.returncode,
                        0,
                        f"{name} was accepted:\n{completed.stdout}{completed.stderr}",
                    )

    def test_full_default_verifier_rejects_contract_only_model_rebinding(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        contract["model"] = "different-model"
        contract["sha256"] = canonical_self_hash(contract)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(contract, sort_keys=True) + "\n", encoding="utf-8")
            completed = self._run_full_default(path, LIVE_RUN / "receipt.json")
            self.assertNotEqual(
                completed.returncode,
                0,
                f"contract-only model mutation accepted:\n{completed.stdout}{completed.stderr}",
            )


class StandaloneInterestingnessAttackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = load_module(EXTRACTOR, "exact_memref_sidecar_attack_extractor")
        cls.verifier = load_module(VERIFIER, "exact_memref_sidecar_attack_verifier")
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def _run_checker(self, candidate: Path, metadata: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python",
                str(VERIFIER),
                "--check-representative",
                str(candidate),
                "--metadata",
                str(metadata),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _canonical_paths(self, operation: str) -> tuple[Path, Path]:
        representative = self.contract["classes"][operation]["representative"]
        return ROOT / representative["path"], ROOT / representative["metadata"]

    def _assert_pinned_parse(self, candidate: Path) -> None:
        completed = subprocess.run(
            [self.contract["tool"]["path"], str(candidate), "-o", "/dev/null"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"escaped-name RED candidate must be valid pinned MLIR:\n{completed.stderr}",
        )

    def _assert_pinned_reject(self, candidate: Path) -> None:
        completed = subprocess.run(
            [self.contract["tool"]["path"], str(candidate), "-o", "/dev/null"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(
            completed.returncode,
            0,
            "pinned MLIR unexpectedly accepted unsupported comment trivia",
        )

    def test_rejects_escaped_generic_names_across_line_comment_trivia(self) -> None:
        copy_module, copy_metadata = self._canonical_paths("memref.copy")
        collapse_module, collapse_metadata = self._canonical_paths(
            "memref.collapse_shape"
        )
        copy_types = "(memref<1xi64>, memref<1xi64>) -> ()"
        same_class = {
            "single-comment": (
                r'"memref.\63opy" // legal token-separating comment'
                "\n      (%source, %target) : "
                + copy_types
            ),
            "repeated-comments-blank-lines": (
                r'"memref.c\6Fpy" // first comment'
                "\n\n      // second comment\n\n      (%source, %target) : "
                + copy_types
            ),
            "carriage-return-comment": (
                r'"memref\2E\63opy" // carriage return ends comment'
                "\r      (%source, %target) : "
                + copy_types
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates: list[tuple[str, Path, Path]] = []
            for name, generic in same_class.items():
                candidate = root / f"comment-{name}.mlir"
                candidate.write_text(
                    copy_module.read_text(encoding="utf-8").replace(
                        "    return", f"    {generic}\n    return"
                    ),
                    encoding="utf-8",
                )
                candidates.append((name, candidate, copy_metadata))

            different = root / "comment-different-class.mlir"
            different.write_text(
                collapse_module.read_text(encoding="utf-8")
                .replace(
                    ") {",
                    ", %target: memref<1x4x256xi64>) {",
                    1,
                )
                .replace(
                    "    return",
                    r'    "memref.\63opy" // different registered class'
                    "\n      (%source, %target) : "
                    "(memref<1x4x256xi64>, memref<1x4x256xi64>) -> ()\n"
                    "    return",
                ),
                encoding="utf-8",
            )
            candidates.append(("different-class", different, collapse_metadata))

            for name, candidate, metadata in candidates:
                with self.subTest(name=name):
                    self._assert_pinned_parse(candidate)
                    completed = self._run_checker(candidate, metadata)
                    self.assertNotEqual(
                        completed.returncode,
                        0,
                        f"comment-separated generic registered operation accepted:\n"
                        f"{completed.stdout}{completed.stderr}",
                    )

    def test_rejects_unsupported_or_unterminated_comment_trivia(self) -> None:
        module, _ = self._canonical_paths("memref.copy")
        unsupported = {
            "block": r'"memref.\63opy" /* block */ (%source, %target)',
            "nested-block": (
                r'"memref.\63opy" /* outer /* nested */ outer */ '
                "(%source, %target)"
            ),
            "unterminated-block": r'"memref.\63opy" /* unterminated',
            "line-comment-to-eof": r'"memref.\63opy" // no operand list',
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, spelling in unsupported.items():
                with self.subTest(name=name):
                    candidate = root / f"unsupported-{name}.mlir"
                    candidate.write_text(
                        module.read_text(encoding="utf-8").replace(
                            "    return", f"    {spelling}\n    return"
                        ),
                        encoding="utf-8",
                    )
                    self._assert_pinned_reject(candidate)
                    with self.assertRaisesRegex(ValueError, "comment|trivia"):
                        self.verifier._independent_operations(spelling)

    def test_rejects_valid_escaped_generic_registered_names(self) -> None:
        copy_module, copy_metadata = self._canonical_paths("memref.copy")
        collapse_module, collapse_metadata = self._canonical_paths(
            "memref.collapse_shape"
        )
        generic_copy_types = "(memref<1xi64>, memref<1xi64>) -> ()"
        escaped_same = {
            "lowercase-hex": rf'"memref.c\6fpy"(%source, %target) : {generic_copy_types}',
            "uppercase-hex": rf'"memref.c\6Fpy"(%source, %target) : {generic_copy_types}',
            "multi-escape": rf'"memref\2E\63\6fpy"(%source, %target) : {generic_copy_types}',
            "newline-whitespace": (
                r'"memref.\63opy"' + "\n      (%source, %target) : "
                + generic_copy_types
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates: list[tuple[str, Path, Path]] = []
            for name, generic in escaped_same.items():
                candidate = root / f"same-{name}.mlir"
                candidate.write_text(
                    copy_module.read_text(encoding="utf-8").replace(
                        "    return", f"    {generic}\n    return"
                    ),
                    encoding="utf-8",
                )
                candidates.append((name, candidate, copy_metadata))

            different = root / "different-class.mlir"
            different.write_text(
                collapse_module.read_text(encoding="utf-8")
                .replace(
                    ") {",
                    ", %target: memref<1x4x256xi64>) {",
                    1,
                )
                .replace(
                    "    return",
                    r'    "memref.\63opy"(%source, %target) : '
                    "(memref<1x4x256xi64>, memref<1x4x256xi64>) -> ()\n"
                    "    return",
                ),
                encoding="utf-8",
            )
            candidates.append(("different-class", different, collapse_metadata))

            for name, candidate, metadata in candidates:
                with self.subTest(name=name):
                    self._assert_pinned_parse(candidate)
                    completed = self._run_checker(candidate, metadata)
                    self.assertNotEqual(
                        completed.returncode,
                        0,
                        f"escaped generic registered operation accepted:\n"
                        f"{completed.stdout}{completed.stderr}",
                    )

    def test_independent_scanner_rejects_malformed_or_ambiguous_escapes(self) -> None:
        malformed = (
            r'"memref.\qopy"() : () -> ()',
            r'"memref.\6opy"() : () -> ()',
            r'"memref.\6"() : () -> ()',
            '"memref.\\',
        )
        for spelling in malformed:
            with self.subTest(spelling=spelling):
                with self.assertRaisesRegex(ValueError, "escape|string"):
                    self.verifier._independent_operations(spelling)

    def test_rejects_extra_generic_same_and_different_registered_operations(self) -> None:
        copy_module, copy_metadata = self._canonical_paths("memref.copy")
        collapse_module, collapse_metadata = self._canonical_paths(
            "memref.collapse_shape"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generic_same = root / "generic-same.mlir"
            generic_same.write_text(
                copy_module.read_text(encoding="utf-8").replace(
                    "    return",
                    '    "memref.copy"(%source, %target) : '
                    "(memref<1xi64>, memref<1xi64>) -> ()\n    return",
                ),
                encoding="utf-8",
            )
            generic_different = root / "generic-different.mlir"
            generic_different.write_text(
                collapse_module.read_text(encoding="utf-8")
                .replace(
                    ") {",
                    ", %target: memref<1x4x256xi64>) {",
                    1,
                )
                .replace(
                    "    return",
                    '    "memref.copy"(%source, %target) : '
                    "(memref<1x4x256xi64>, memref<1x4x256xi64>) -> ()\n    return",
                ),
                encoding="utf-8",
            )
            for name, candidate, metadata in (
                ("same", generic_same, copy_metadata),
                ("different", generic_different, collapse_metadata),
            ):
                with self.subTest(name=name):
                    completed = self._run_checker(candidate, metadata)
                    self.assertNotEqual(
                        completed.returncode,
                        0,
                        f"generic {name}-class operation accepted:\n"
                        f"{completed.stdout}{completed.stderr}",
                    )

    def test_rejects_extra_custom_same_and_different_registered_operations(self) -> None:
        module, metadata = self._canonical_paths("memref.copy")
        original = module.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            same = root / "same.mlir"
            same.write_text(
                original.replace(
                    "    return",
                    "    memref.copy %source, %target : memref<1xi64> to memref<1xi64>\n    return",
                ),
                encoding="utf-8",
            )
            different = root / "different.mlir"
            different.write_text(
                original.replace(
                    "    return",
                    "    %view = memref.reinterpret_cast %source to offset: [0], "
                    "sizes: [1], strides: [1] : memref<1xi64> to "
                    "memref<1xi64, strided<[1]>>\n    return",
                ),
                encoding="utf-8",
            )
            for name, candidate in (("same", same), ("different", different)):
                with self.subTest(name=name):
                    completed = self._run_checker(candidate, metadata)
                    self.assertNotEqual(
                        completed.returncode,
                        0,
                        f"extra custom {name}-class operation accepted:\n"
                        f"{completed.stdout}{completed.stderr}",
                    )

    def test_rejects_wrong_but_self_consistent_sidecar_signature_and_hash(self) -> None:
        module, metadata_path = self._canonical_paths("memref.copy")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "wrong-signature.mlir"
            candidate.write_text(
                module.read_text(encoding="utf-8").replace("1xi64", "2xi64"),
                encoding="utf-8",
            )
            operations = self.extractor.parse_registered_operations(
                candidate.read_text(encoding="utf-8")
            )
            self.assertEqual(len(operations), 1)
            signature = operations[0]["signature"]
            sidecar = json.loads(metadata_path.read_text(encoding="utf-8"))
            sidecar["signature"] = signature
            sidecar["signature_sha256"] = hashlib.sha256(
                json.dumps(
                    signature, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            sidecar["selection_tuple"][1] = json.dumps(
                signature, sort_keys=True, separators=(",", ":")
            )
            metadata = root / "wrong-sidecar.json"
            metadata.write_text(
                json.dumps(sidecar, sort_keys=True) + "\n", encoding="utf-8"
            )
            completed = self._run_checker(candidate, metadata)
            self.assertNotEqual(
                completed.returncode,
                0,
                "wrong self-consistent sidecar accepted:\n"
                + completed.stdout
                + completed.stderr,
            )

if __name__ == "__main__":
    unittest.main()
