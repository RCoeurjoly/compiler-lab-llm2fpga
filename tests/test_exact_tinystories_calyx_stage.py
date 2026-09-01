#!/usr/bin/env python3
"""Contract tests for the fail-closed exact TinyStories Calyx stage."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/pipeline/run_exact_tinystories_calyx.py"
PACKAGE = "tiny-stories-1m-kev-gpt-exact-calyx-frontier"
REALISTIC_RECEIPT = {
    "first_locations": {},
    "parser_validation": {
        "authorized_identity": {
            "canonical_path": "/nix/store/pinned-mlir/bin/mlir-opt",
            "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
            "version": "21.1.2",
        },
        "identity_status": "verified",
        "input_status": "accepted",
        "observed_identity": {
            "canonical_path": "/nix/store/pinned-mlir/bin/mlir-opt",
            "sha256": "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912",
            "version_output": "LLVM version 21.1.2\\n",
        },
    },
    "prohibited_ops": {},
    "scanner_diagnostics": [],
    "schema_version": 3,
    "status": "ok",
}


def _load_runner():
    spec = importlib.util.spec_from_file_location("exact_tinystories_calyx", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExactTinyStoriesCalyxStageTest(unittest.TestCase):
    """The production changes that break these tests accept invalid Calyx."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_runner()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="exact-calyx-stage-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "pre-calyx.mlir"
        self.input.write_text("module { func.func @main() { return } }\n", encoding="utf-8")
        self.tool = self.root / "fake-circt-opt"
        self.tool.write_text(
            """#!/usr/bin/env python3
import os
import pathlib
import sys

args = sys.argv[1:]
if "--lower-scf-to-calyx=top-level-function=main" not in args:
    exit_code = int(os.environ.get("FAKE_PARSE_EXIT", "0"))
    if exit_code == 0 and args[args.index("-o") + 1] != "/dev/null":
        pathlib.Path(args[args.index("-o") + 1]).write_bytes(pathlib.Path(args[0]).read_bytes())
    sys.exit(exit_code)
output = pathlib.Path(args[args.index("-o") + 1])
output.write_text(os.environ.get("FAKE_OUTPUT", ""), encoding="utf-8")
sys.stdout.write(os.environ.get("FAKE_STDOUT", ""))
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
""",
            encoding="utf-8",
        )
        self.tool.chmod(0o755)

    def _run(self, **environment: str) -> tuple[dict[str, object], Path]:
        output = self.root / "out"
        with patch.dict(os.environ, environment, clear=False):
            result = self.module.run_calyx(self.input, output, self.tool)
        return result, output

    def _assert_rejected(self, result: dict[str, object], output: Path) -> None:
        self.assertEqual(result["stage"], "calyx")
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["artifact_accepted"])
        self.assertFalse((output / "model.calyx.mlir").exists())

    def _write_predecessor(self, authorized: bool = True) -> tuple[Path, str, str]:
        predecessor = self.root / "predecessor"
        predecessor.mkdir()
        prepared = b"prepared"
        (predecessor / "pre-calyx.mlir").write_bytes(prepared)
        receipt = dict(REALISTIC_RECEIPT)
        receipt["parser_validation"] = json.loads(json.dumps(receipt["parser_validation"]))
        receipt["sha256"] = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        (predecessor / "pre-calyx-legality.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (predecessor / "manifest.json").write_text(
            json.dumps({"calyx_authorized": authorized}), encoding="utf-8"
        )
        return predecessor, hashlib.sha256(prepared).hexdigest(), receipt["sha256"]

    def test_rejects_zero_exit_with_unhandled_operation_and_preserves_partial(self) -> None:
        """Dropping terminal diagnostics would incorrectly accept a partial artifact."""
        result, output = self._run(
            FAKE_OUTPUT="calyx.component @main() {}\n",
            FAKE_STDERR="Unhandled operation during BuildOpGroups()\n",
        )

        self._assert_rejected(result, output)
        self.assertEqual(result["first_diagnostic"], "Unhandled operation during BuildOpGroups()")
        self.assertEqual((output / "partial.calyx.mlir").read_text(), "calyx.component @main() {}\n")
        self.assertIn("Unhandled operation", (output / "lower-scf-to-calyx.log").read_text())

    def test_rejects_nonzero_exit_and_preserves_nonempty_output(self) -> None:
        """Treating a nonzero backend exit as successful would expose a rejected artifact."""
        result, output = self._run(FAKE_EXIT="1", FAKE_OUTPUT="calyx.component @main() {}\n")

        self._assert_rejected(result, output)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual((output / "partial.calyx.mlir").read_text(), "calyx.component @main() {}\n")

    def test_rejects_zero_exit_with_empty_output(self) -> None:
        """Accepting an empty successful invocation would create a false frontier success."""
        result, output = self._run(FAKE_OUTPUT="")

        self._assert_rejected(result, output)
        self.assertEqual(result["first_diagnostic"], "Calyx lowering produced empty output")
        self.assertFalse((output / "partial.calyx.mlir").exists())

    def test_rejects_malformed_output(self) -> None:
        """Skipping the parser check would accept malformed Calyx text."""
        result, output = self._run(FAKE_OUTPUT="malformed calyx\n", FAKE_PARSE_EXIT="1")

        self._assert_rejected(result, output)
        self.assertEqual(result["first_diagnostic"], "Calyx candidate failed to parse")
        self.assertEqual((output / "partial.calyx.mlir").read_text(), "malformed calyx\n")

    def test_rejects_parseable_output_without_main_component(self) -> None:
        """Accepting any parser-clean output would permit the wrong Calyx entrypoint."""
        result, output = self._run(FAKE_OUTPUT="calyx.component @helper() {}\n")

        self._assert_rejected(result, output)
        self.assertEqual(
            result["first_diagnostic"],
            "Calyx candidate does not define calyx.component @main",
        )
        self.assertEqual(
            (output / "partial.calyx.mlir").read_text(), "calyx.component @helper() {}\n"
        )

    def test_rejects_comment_or_string_that_spoofs_main_component(self) -> None:
        """Searching raw Calyx text must not let comments or strings create an entrypoint."""
        result, output = self._run(
            FAKE_OUTPUT=(
                "calyx.component @helper() {}\n"
                "// calyx.component @main() {}\n"
                "\"calyx.component @main() {}\"\n"
            )
        )

        self._assert_rejected(result, output)
        self.assertEqual(
            result["first_diagnostic"],
            "Calyx candidate does not define calyx.component @main",
        )

    def test_accepts_only_parseable_main_component(self) -> None:
        """Accepting any parser-clean output would allow a non-main Calyx artifact."""
        result, output = self._run(FAKE_OUTPUT="calyx.component @main() {}\n")

        self.assertEqual(result["stage"], "calyx")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["artifact_accepted"])
        self.assertIsNone(result["first_diagnostic"])
        self.assertEqual((output / "model.calyx.mlir").read_text(), "calyx.component @main() {}\n")
        self.assertFalse((output / "partial.calyx.mlir").exists())
        manifest = json.loads((output / "manifest.json").read_text())
        unsigned = {key: value for key, value in manifest.items() if key != "sha256"}
        self.assertEqual(manifest["sha256"], hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest())

    def test_rejects_predecessor_without_calyx_authorization(self) -> None:
        """Ignoring predecessor authorization would bypass the independent pre-Calyx gate."""
        predecessor, prepared_sha256, receipt_sha256 = self._write_predecessor(False)

        with self.assertRaisesRegex(ValueError, "calyx_authorized"):
            self.module.validate_predecessor(
                predecessor, prepared_sha256, receipt_sha256,
            )

    def test_validates_realistic_receipt_self_hash_not_its_file_hash(self) -> None:
        """Comparing the fixed receipt self-hash with JSON bytes rejects the real package."""
        predecessor, prepared_sha256, receipt_sha256 = self._write_predecessor()

        validated = self.module.validate_predecessor(
            predecessor, prepared_sha256, receipt_sha256
        )

        self.assertEqual(validated["receipt"]["sha256"], hashlib.sha256(
            (predecessor / "pre-calyx-legality.json").read_bytes()
        ).hexdigest())

    def test_rejects_predecessor_receipt_with_invalid_canonical_self_hash(self) -> None:
        """Trusting a receipt sha256 field without recomputing it permits forged legality."""
        predecessor, prepared_sha256, receipt_sha256 = self._write_predecessor()
        receipt_path = predecessor / "pre-calyx-legality.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["status"] = "blocked"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "receipt self-hash"):
            self.module.validate_predecessor(predecessor, prepared_sha256, receipt_sha256)

    def test_rejects_predecessor_hash_mismatch(self) -> None:
        """Ignoring prepared or receipt hashes would permit route substitution."""
        predecessor, prepared_sha256, receipt_sha256 = self._write_predecessor()

        with self.assertRaisesRegex(ValueError, "prepared SHA-256"):
            self.module.validate_predecessor(predecessor, "0" * 64, receipt_sha256)
        with self.assertRaisesRegex(ValueError, "receipt SHA-256"):
            self.module.validate_predecessor(predecessor, prepared_sha256, "1" * 64)

    def test_reused_output_clears_stale_accepted_artifact_before_failure(self) -> None:
        """A rejected rerun must never retain a previous accepted model artifact."""
        _, output = self._run(FAKE_OUTPUT="calyx.component @main() {}\n")
        result, output = self._run(
            FAKE_OUTPUT="calyx.component @main() {}\n",
            FAKE_STDERR="Unhandled operation during BuildOpGroups()\n",
        )

        self._assert_rejected(result, output)
        self.assertTrue((output / "partial.calyx.mlir").is_file())
        self.assertFalse((output / "model.calyx.mlir").exists())

    def test_failed_empty_output_is_a_complete_artifactless_diagnostic_bundle(self) -> None:
        """The Nix boundary must retain a failed manifest and log when no partial exists."""
        result, output = self._run(FAKE_OUTPUT="")

        self._assert_rejected(result, output)
        self.assertTrue((output / "manifest.json").is_file())
        self.assertTrue((output / "lower-scf-to-calyx.log").is_file())
        self.assertIsNone(result["artifact"])
        self.assertIsNone(result["partial_artifact"])
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--validate-output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_registration_exports_hash_bound_diagnostic_package(self) -> None:
        """A detached legacy route would not bind the approved predecessor package."""
        completed = subprocess.run(
            ["nix", "eval", "--raw", f".#packages.x86_64-linux.{PACKAGE}.name"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, PACKAGE)


if __name__ == "__main__":
    unittest.main()
