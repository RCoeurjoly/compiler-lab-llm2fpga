#!/usr/bin/env python3
"""Integration contract for the exact normalized pre-Calyx registration."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ALIAS = "tiny-stories-1m-kev-gpt-exact-normalized-flat-scf"
MODULE = ROOT / "nix/exact-tinystories-normalized.nix"
SHARED_PIPELINE = ROOT / "nix/pipeline.nix"
VERIFIER = ROOT / "scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py"
NORMALIZED_SHA256 = "e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77"
C22_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
PLUGIN_SHA256 = "901fd383935d5af48e616eb881ae1b72408f4cb26dfbef94ea7be3049d61760f"
NORMALIZATION_PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
)
PREPARATION_PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "llm2fpga-drop-calyx-unsupported-asserts,"
    "llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,"
    "llm2fpga-lower-exact-math-for-calyx,"
    "llm2fpga-lower-negf-for-calyx,"
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


def _binding(path: Path) -> dict[str, object]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}


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

    def _copy_bundle(self, temporary: Path, verifier):
        bundle = temporary / "bundle"
        bundle.mkdir()
        for name in ("flat.scf.mlir", "pre-calyx.mlir", "pre-calyx-legality.json", "manifest.json"):
            target = bundle / name
            shutil.copy2(self.output / name, target)
            target.chmod(0o600)
        manifest = json.loads((bundle / "manifest.json").read_text())
        authority = verifier._resolve_authority()
        manifest["commands"] = verifier._expected_commands(authority, bundle)
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        )
        verifier.verify_output(bundle)
        return bundle, authority

    def _drv_path(self, root: Path = ROOT) -> str:
        return subprocess.run(
            ["nix", "eval", "--raw", f".#${ALIAS}.drvPath".replace("$", "")],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

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

    def test_shared_and_exact_preparation_literals_lower_negf_once_in_order(self) -> None:
        """Omitting, duplicating, or moving NegF breaks the preparation contract."""
        exact = MODULE.read_text(encoding="utf-8")
        shared = SHARED_PIPELINE.read_text(encoding="utf-8")
        exact_expected = (
            "llm2fpga-lower-exact-math-for-calyx,"
            "llm2fpga-lower-negf-for-calyx,"
            "llm2fpga-lower-i1-uitofp-for-calyx"
        )
        shared_expected = (
            "llm2fpga-lower-exact-math-for-calyx,"
            "llm2fpga-lower-negf-for-calyx${scoutMathPass},"
            "llm2fpga-lower-i1-uitofp-for-calyx"
        )
        self.assertEqual(exact.count("llm2fpga-lower-negf-for-calyx"), 1)
        self.assertIn(exact_expected, exact)
        self.assertEqual(shared.count("llm2fpga-lower-negf-for-calyx"), 1)
        self.assertIn(shared_expected, shared)

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

    def test_preparation_replay_eliminates_the_three_carried_math_frontiers(self) -> None:
        """A stale plugin authority or retained i64 Absi must fail this successor."""
        manifest = self._manifest()
        legality = json.loads((self.output / "pre-calyx-legality.json").read_text())
        self.assertEqual(legality["prohibited_ops"].get("math.floor", 0), 0)
        self.assertEqual(legality["prohibited_ops"].get("arith.negf", 0), 0)
        self.assertEqual(legality["prohibited_ops"].get("math.absi", 0), 0)
        if legality["prohibited_ops"] or legality["scanner_diagnostics"]:
            self.assertEqual(legality["status"], "blocked")
            self.assertFalse(manifest["calyx_authorized"])
            self.assertTrue(legality["first_locations"])
        else:
            self.assertEqual(legality["status"], "ok")
            self.assertTrue(manifest["calyx_authorized"])

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

    def test_independent_verifier_rejects_identity_pipeline_and_legality_mutations(self) -> None:
        """Stale authority, malformed NegF ordering, or false-clean legality must fail."""
        verifier = self._verifier_module()
        manifest = self._manifest()
        for path, replacement in (
            (("normalization", "input", "sha256"), "0" * 64),
            (("normalization", "plugin", "sha256"), "1" * 64),
            (("normalization", "output", "sha256"), "2" * 64),
            (("preparation", "output", "sha256"), "3" * 64),
            (("preparation", "pipeline"), PREPARATION_PIPELINE.replace(
                ",llm2fpga-lower-negf-for-calyx", ""
            )),
            (("preparation", "pipeline"), PREPARATION_PIPELINE.replace(
                ",llm2fpga-lower-negf-for-calyx", ",llm2fpga-lower-negf-for-calyx,llm2fpga-lower-negf-for-calyx"
            )),
            (("preparation", "pipeline"), PREPARATION_PIPELINE.replace(
                "llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-negf-for-calyx,llm2fpga-lower-i1-uitofp-for-calyx",
                "llm2fpga-lower-negf-for-calyx,llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-i1-uitofp-for-calyx",
            )),
            (("preparation", "legality", "status"), "blocked"),
        ):
            candidate = json.loads(json.dumps(manifest))
            cursor = candidate
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = replacement
            with self.assertRaises(ValueError, msg="mutation should be rejected: " + ".".join(path)):
                verifier.validate_manifest(candidate, self.output)

    def test_verifier_rejects_coherent_clean_prepared_replacement(self) -> None:
        """Replacing preparation output with parser-clean MLIR must fail replay."""
        verifier = self._verifier_module()
        with tempfile.TemporaryDirectory(prefix="exact-prepared-forgery-", dir="/dev/shm") as raw:
            bundle, authority = self._copy_bundle(Path(raw), verifier)
            manifest = json.loads((bundle / "manifest.json").read_text())
            prepared = bundle / "pre-calyx.mlir"
            prepared.write_text("module {}\n", encoding="utf-8")
            legality = bundle / "pre-calyx-legality.json"
            completed = subprocess.run(
                [
                    authority["python"], authority["checker"], str(prepared),
                    str(legality), "--mlir-opt", authority["mlir_opt"],
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 0)
            receipt = json.loads(legality.read_text())
            self.assertEqual(receipt["status"], "ok")
            manifest["preparation"]["output"] = _binding(prepared)
            manifest["preparation"]["legality"] = {
                "path": legality.name,
                "sha256": _sha256(legality),
                "status": receipt["status"],
                "receipt_sha256": receipt["sha256"],
            }
            manifest["calyx_authorized"] = True
            (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaisesRegex(ValueError, "preparation replay mismatch"):
                verifier.verify_output(bundle)

    def test_verifier_rejects_coherent_resigned_receipt_from_stub_checker(self) -> None:
        """A manifest-selected checker stub cannot turn the blocked bundle clean."""
        verifier = self._verifier_module()
        with tempfile.TemporaryDirectory(prefix="exact-checker-forgery-", dir="/dev/shm") as raw:
            bundle, _ = self._copy_bundle(Path(raw), verifier)
            manifest = json.loads((bundle / "manifest.json").read_text())
            authentic = json.loads((bundle / "pre-calyx-legality.json").read_text())
            forged = {
                "schema_version": 3,
                "status": "ok",
                "prohibited_ops": {},
                "first_locations": {},
                "scanner_diagnostics": [],
                "parser_validation": authentic["parser_validation"],
            }
            forged["sha256"] = hashlib.sha256(_canonical(forged)).hexdigest()
            legality = bundle / "pre-calyx-legality.json"
            legality.write_text(json.dumps(forged, sort_keys=True) + "\n")
            stub = Path(raw) / "false_clean_checker.py"
            stub.write_text(
                "from pathlib import Path\nimport sys\n"
                + "Path(sys.argv[2]).write_text(" + repr(json.dumps(forged, sort_keys=True) + "\n") + ")\n",
                encoding="utf-8",
            )
            manifest["commands"]["preflight"][1] = str(stub)
            manifest["preparation"]["legality"] = {
                "path": legality.name,
                "sha256": _sha256(legality),
                "status": "ok",
                "receipt_sha256": forged["sha256"],
            }
            manifest["calyx_authorized"] = True
            (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaisesRegex(ValueError, "manifest command vector mismatch"):
                verifier.verify_output(bundle)

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

    def test_tracked_evidence_mutation_in_isolated_worktree_keeps_exact_drv(self) -> None:
        """A tracked excluded evidence byte cannot perturb the file-scoped stage."""
        relative = Path(
            "artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence/"
            "semantic-size1-pass-only/stdout.bin"
        )
        live_bytes = (ROOT / relative).read_bytes()
        with tempfile.TemporaryDirectory(prefix="exact-evidence-worktree-", dir="/dev/shm") as raw:
            worktree = Path(raw) / "source"
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                tracked = worktree / relative
                subprocess.run(
                    ["git", "ls-files", "--error-unmatch", str(relative)],
                    cwd=worktree,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                before = self._drv_path(worktree)
                tracked.write_bytes(b"task-2 isolated evidence mutation\n")
                self.assertEqual(before, self._drv_path(worktree))
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=ROOT,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
        self.assertEqual((ROOT / relative).read_bytes(), live_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
