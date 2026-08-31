#!/usr/bin/env python3
"""Verify that compiler derivations see only their runtime script closure."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_REFERENCES = (ROOT / "flake.nix", ROOT / "nix/pipeline.nix")
RUNTIME_REFERENCE_RE = re.compile(r"\$\{pipelineScripts\}/([^\s\"\\]+)")
EXACT_ALIAS = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake"
EXACT_STAGES = ("torch", "linalg", "scf", "flat-scf")
CHECK_NAME = "pipeline-runtime-source-closure"


def _run(*command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def _runtime_references() -> list[str]:
    names = {
        Path(match.group(1)).name
        for source in PIPELINE_REFERENCES
        for match in RUNTIME_REFERENCE_RE.finditer(source.read_text(encoding="utf-8"))
    }
    return sorted(names)


def _copy_tracked_source(destination: Path) -> None:
    tracked = _run("git", "ls-files", "-z").stdout.split("\0")
    for relative in tracked:
        if not relative:
            continue
        source = ROOT / relative
        if not source.exists() and not source.is_symlink():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
            continue
        if source.is_dir():
            target.mkdir(exist_ok=True)
            continue
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)


def _flake_snapshot(source: Path) -> dict[str, object]:
    uri = f"path:{source}"
    derivations = " ".join(
        f'\"{stage}\" = f.packages.${{system}}.\"{EXACT_ALIAS}-{stage}\".drvPath;'
        for stage in EXACT_STAGES
    )
    expression = f'''
      let
        f = builtins.getFlake {json.dumps(uri)};
        system = builtins.currentSystem;
        closure = f.checks.${{system}}.{CHECK_NAME};
      in {{
        allowlist = closure.runtimeScriptBasenames;
        runtimeSource = toString closure.runtimeSource;
        derivations = {{ {derivations} }};
      }}
    '''
    evaluated = _run("nix", "eval", "--impure", "--json", "--expr", expression, check=False)
    if evaluated.returncode != 0:
        raise AssertionError(
            "flake does not expose the filtered pipeline runtime source closure:\n"
            + evaluated.stderr
        )
    value = json.loads(evaluated.stdout)
    runtime_source = Path(value["runtimeSource"])
    hashed = _run("nix", "hash", "path", "--type", "sha256", str(runtime_source))
    value["runtimeSourceNarHash"] = hashed.stdout.strip()
    return value


class ExactPipelineSourceClosureTest(unittest.TestCase):
    def test_runtime_source_is_exactly_the_sorted_referenced_basename_set(self) -> None:
        expected = _runtime_references()
        with tempfile.TemporaryDirectory(prefix="exact-pipeline-source-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            _copy_tracked_source(source)
            for relative in (
                "scripts/pipeline/docs/report.md",
                "scripts/pipeline/tests/test_report.py",
                "scripts/pipeline/artifacts/receipt.json",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("evidence only\n", encoding="utf-8")
            snapshot = _flake_snapshot(source)

        self.assertEqual(snapshot["allowlist"], expected)
        runtime_source = Path(snapshot["runtimeSource"])
        actual = sorted(
            str(path.relative_to(runtime_source))
            for path in runtime_source.rglob("*")
            if path.is_file()
        )
        self.assertEqual(actual, expected)
        self.assertNotIn("classify_tinystories_1m_exact_frontier.py", actual)
        self.assertNotIn(
            "verify_tinystories_1m_exact_frontier_determinism.py", actual
        )
        self.assertFalse(
            any(name.startswith(("docs/", "tests/", "artifacts/")) for name in actual)
        )

    def test_missing_referenced_runtime_script_fails_evaluation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-pipeline-missing-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            _copy_tracked_source(source)
            (source / "scripts/pipeline/torch_to_linalg.sh").unlink()
            with self.assertRaisesRegex(AssertionError, "missing pipeline runtime script"):
                _flake_snapshot(source)

    def test_evidence_only_mutation_preserves_runtime_nar_and_exact_derivations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="exact-pipeline-mutation-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            _copy_tracked_source(source)
            before = _flake_snapshot(source)
            verifier = (
                source
                / "scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py"
            )
            original = verifier.read_bytes()
            verifier.unlink()
            verifier.write_bytes(original + b"\n# evidence-only mutation\n")
            after = _flake_snapshot(source)

        self.assertEqual(
            before["runtimeSourceNarHash"], after["runtimeSourceNarHash"]
        )
        self.assertEqual(before["derivations"], after["derivations"])


if __name__ == "__main__":
    unittest.main()
