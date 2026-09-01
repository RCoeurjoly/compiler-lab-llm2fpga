#!/usr/bin/env python3
"""Contract tests for the fail-closed exact TinyStories Calyx stage."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/pipeline/run_exact_tinystories_calyx.py"
PACKAGE = "tiny-stories-1m-kev-gpt-exact-calyx-frontier"


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
    sys.exit(int(os.environ.get("FAKE_PARSE_EXIT", "0")))
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
        predecessor = self.root / "predecessor"
        predecessor.mkdir()
        (predecessor / "pre-calyx.mlir").write_bytes(b"prepared")
        (predecessor / "pre-calyx-legality.json").write_bytes(b"receipt")
        (predecessor / "manifest.json").write_text(
            json.dumps({"calyx_authorized": False}), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "calyx_authorized"):
            self.module.validate_predecessor(
                predecessor, hashlib.sha256(b"prepared").hexdigest(),
                hashlib.sha256(b"receipt").hexdigest(),
            )

    def test_rejects_predecessor_hash_mismatch(self) -> None:
        """Ignoring prepared or receipt hashes would permit route substitution."""
        predecessor = self.root / "predecessor"
        predecessor.mkdir()
        (predecessor / "pre-calyx.mlir").write_bytes(b"prepared")
        (predecessor / "pre-calyx-legality.json").write_bytes(b"receipt")
        (predecessor / "manifest.json").write_text(
            json.dumps({"calyx_authorized": True}), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "prepared SHA-256"):
            self.module.validate_predecessor(predecessor, "0" * 64, hashlib.sha256(b"receipt").hexdigest())
        with self.assertRaisesRegex(ValueError, "receipt SHA-256"):
            self.module.validate_predecessor(predecessor, hashlib.sha256(b"prepared").hexdigest(), "1" * 64)

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
