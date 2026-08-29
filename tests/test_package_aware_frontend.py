"""Tests for the package-aware compiler export frontend boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
MATERIALIZER = ROOT / "scripts" / "materialize-pytorch-exported.py"
ADAPTER = ROOT / "TinyStories" / "model_adapter_reference_package.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/"
    "snapshots/77f1b168e219585646439073245fe87e56b3023e"
)


def load_materializer():
    spec = importlib.util.spec_from_file_location("materialize_pytorch_exported", MATERIALIZER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageAwareFrontendTest(unittest.TestCase):
    def test_nix_exposes_explicit_package_aware_export_target(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn('name = "tinystories-1m-package-aware-export"', flake)
        self.assertIn('apps."tinystories-1m-package-aware-export"', flake)
        self.assertIn("model_adapter_reference_package.py", flake)
        self.assertIn("--contract ${sourceRoot}/artifacts/reference/tinystories-1m-kev-gpt-contract.json", flake)

    def test_package_export_manifest_records_content_provenance(self) -> None:
        materializer = load_materializer()
        with __import__("tempfile").TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            package.mkdir()
            for name in ("manifest.json", "weights.bin", "scales.bin", "calibration_ids.bin", "receipt.json"):
                (package / name).write_bytes(name.encode("ascii"))
            contract = Path(directory) / "contract.json"
            contract.write_text("{}", encoding="utf-8")
            provenance = materializer.package_provenance(str(package), str(contract))
            self.assertEqual(provenance["contract"]["sha256"], __import__("hashlib").sha256(b"{}").hexdigest())
            self.assertEqual(set(provenance["package"]["files"]), {
                "manifest.json", "weights.bin", "scales.bin", "calibration_ids.bin", "receipt.json"
            })

    def test_reference_adapter_exposes_explicit_package_frontend(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("def export_program_with_package", source)
        self.assertIn("contract_path", source)
        self.assertIn("package_path", source)

    def test_materializer_dispatches_package_frontend_without_fallback(self) -> None:
        materializer = load_materializer()
        calls: list[tuple[str | None, str | None, str | None]] = []

        class FakeExport:
            example_inputs = None

        class PackageAdapter:
            def export_program_with_package(self, model_path, package_path, contract_path):
                calls.append((model_path, package_path, contract_path))
                return FakeExport()

        exported, source, _ = materializer.adapter_exported_program(PackageAdapter(), "model", "package", "contract")
        self.assertIsInstance(exported, FakeExport)
        self.assertEqual(source, "adapter.export_program_with_package")
        self.assertEqual(calls, [("model", "package", "contract")])

    def test_package_arguments_are_required_as_a_pair(self) -> None:
        materializer = load_materializer()
        with self.assertRaisesRegex(ValueError, "package and contract"):
            materializer.adapter_exported_program(
                object(), "model", "package", None
            )

    def test_package_request_rejects_legacy_fp32_adapter(self) -> None:
        materializer = load_materializer()
        with self.assertRaisesRegex(SystemExit, "does not expose"):
            materializer.adapter_exported_program(object(), "model", "package", "contract")

    @unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
    def test_cli_materializes_explicit_package_frontend(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "export"
            result = subprocess.run(
                [
                    "python",
                    str(MATERIALIZER),
                    "--adapter",
                    str(ADAPTER),
                    "--model-path",
                    str(MODEL),
                    "--package",
                    str(PACKAGE),
                    "--contract",
                    str(CONTRACT),
                    "--out-dir",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["export_source"], "adapter.export_program_with_package")
            self.assertEqual(manifest["package_path"], str(PACKAGE))
            self.assertEqual(manifest["contract_path"], str(CONTRACT))


if __name__ == "__main__":
    unittest.main()
