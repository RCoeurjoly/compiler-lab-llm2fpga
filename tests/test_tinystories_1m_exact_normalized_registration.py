#!/usr/bin/env python3
"""Integration contract for the exact normalized pre-Calyx registration."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ALIAS = "tiny-stories-1m-kev-gpt-exact-normalized-flat-scf"
MODULE = ROOT / "nix/exact-tinystories-normalized.nix"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py"
NORMALIZED_SHA256 = "e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77"
C22_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
PLUGIN_SHA256 = "79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738"
NORMALIZATION_PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
)
PREPARATION_PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "llm2fpga-drop-calyx-unsupported-asserts,"
    "llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,"
    "llm2fpga-lower-exact-math-for-calyx,"
    "llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)"
)
REGISTERED = (
    "memref.collapse_shape",
    "memref.copy",
    "memref.expand_shape",
    "memref.reinterpret_cast",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class ExactNormalizedRegistrationTest(unittest.TestCase):
    """The production change that breaks these tests is a detached/unsafe stage."""

    @classmethod
    def setUpClass(cls) -> None:
        # This must exercise the registered flake boundary, not a pre-existing
        # evidence file.  Nix reuses a completed store output when available.
        completed = subprocess.run(
            ["nix", "build", "--no-link", "--print-out-paths", f".#${ALIAS}".replace("$", "")],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "registered exact normalized package did not build:\n"
                + completed.stderr
            )
        cls.output = Path(completed.stdout.strip())

    def _manifest(self) -> dict[str, object]:
        return json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))

    def _verifier_module(self):
        spec = importlib.util.spec_from_file_location("exact_normalized_verify", VERIFIER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_registered_package_replays_the_exact_normalized_artifact(self) -> None:
        """Removing the flake alias/module or changing a bound hash must fail."""
        self.assertTrue(MODULE.is_file(), "registered derivation module is absent")
        self.assertTrue(VERIFIER.is_file(), "independent verifier is absent")
        manifest = self._manifest()
        self.assertEqual(manifest["normalization"]["pipeline"], NORMALIZATION_PIPELINE)
        self.assertEqual(manifest["normalization"]["input"]["sha256"], C22_SHA256)
        self.assertEqual(manifest["normalization"]["plugin"]["sha256"], PLUGIN_SHA256)
        self.assertEqual(manifest["normalization"]["output"]["sha256"], NORMALIZED_SHA256)
        self.assertEqual(_sha256(self.output / "flat.scf.mlir"), NORMALIZED_SHA256)
        self.assertEqual(
            manifest["normalization"]["registered_blocker_counts"],
            {name: 0 for name in REGISTERED},
        )

    def test_preparation_is_parsed_and_authorized_only_by_its_legality_receipt(self) -> None:
        """A false clean receipt or an altered no-scout pipeline must fail."""
        manifest = self._manifest()
        legality = json.loads((self.output / "pre-calyx-legality.json").read_text())
        self.assertEqual(manifest["preparation"]["pipeline"], PREPARATION_PIPELINE)
        self.assertEqual(manifest["preparation"]["parse_status"], "ok")
        self.assertEqual(legality["schema_version"], 3)
        unsigned = dict(legality)
        del unsigned["sha256"]
        self.assertEqual(legality["sha256"], hashlib.sha256(_canonical(unsigned)).hexdigest())
        self.assertEqual(
            manifest["calyx_authorized"], legality["status"] == "ok"
        )

    def test_manifest_commands_do_not_cross_the_precalyx_boundary(self) -> None:
        """Replacing preparation with Calyx/SV/synthesis/board work must fail."""
        commands = self._manifest()["commands"]
        forbidden = (
            "circt-opt",
            "/bin/calyx",
            "calyx ",
            "sv_mlir",
            "systemverilog",
            "yosys",
            "nextpnr",
            "vivado",
            "board",
        )
        rendered = "\n".join(" ".join(command) for command in commands.values())
        self.assertTrue(all(term not in rendered.lower() for term in forbidden), rendered)
        self.assertTrue(all(command[0].endswith(("/mlir-opt", "/python3")) for command in commands.values()))

    def test_independent_verifier_rejects_identity_and_legality_mutations(self) -> None:
        """Stale c22/plugin/output, false-clean legality, or pipeline edits must fail."""
        verifier = self._verifier_module()
        manifest = self._manifest()
        for path, replacement in (
            (("normalization", "input", "sha256"), "0" * 64),
            (("normalization", "plugin", "sha256"), "1" * 64),
            (("normalization", "output", "sha256"), "2" * 64),
            (("preparation", "pipeline"), "builtin.module(cse)"),
            (("preparation", "legality", "status"), "ok"),
        ):
            candidate = json.loads(json.dumps(manifest))
            cursor = candidate
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = replacement
            with self.assertRaises(ValueError, msg="mutation should be rejected: " + ".".join(path)):
                verifier.validate_manifest(candidate, self.output)

    def test_derivation_source_closure_excludes_the_evidence_directory(self) -> None:
        """An evidence-only mutation must not be an input to the derivation."""
        derivation = subprocess.run(
            ["nix", "eval", "--raw", f".#${ALIAS}.drvPath".replace("$", "")],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        derivation_payload = json.loads(
            subprocess.run(
                ["nix", "derivation", "show", derivation],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout
        )
        payload = next(iter(derivation_payload["derivations"].values()))
        source_names = "\n".join(payload["inputs"]["srcs"])
        self.assertIn("tinystories-1m-exact-c22-input", source_names)
        self.assertNotIn("rank1-copy-extension-evidence", source_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
