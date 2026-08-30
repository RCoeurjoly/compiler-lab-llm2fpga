import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATERIALIZER = ROOT / "scripts" / "materialize-pytorch-exported.py"
EXACT_ADAPTER = ROOT / "TinyStories" / "model_adapter_exact_package.py"
MODEL_KEY = "tiny-stories-1m-kev-gpt-exact"
EXPECTED_MANIFEST_SHA256 = "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35"
EXPECTED_IDENTITIES = {
    "adapter_sha256": "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e",
    "contract_sha256": "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c",
    "task_1_audit_file_sha256": "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd",
    "task_1_audit_payload_sha256": "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766",
    "task_2_artifact_file_sha256": "173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a",
    "task_2_artifact_sha256": "af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838",
    "task_2_model_receipt_sha256": "5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834",
    "task_3_generation_file_sha256": "e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3",
    "task_3_generation_artifact_sha256": "9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3",
    "task_3_generation_result_sha256": "c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644",
}
EXPECTED_STAGES = {
    "hf-snapshot",
    "pytorch-exported",
    "torch",
    "torch-stats",
    "tosa",
    "linalg",
    "scf",
    "flat-scf",
    "calyx",
    "calyx-sv",
    "calyx-native-sv",
    "calyx-hw-sv",
    "cf",
    "cf-stats",
    "llvm",
    "handshake",
    "hs-ext",
    "hw0",
    "hw",
    "hw-clean",
    "sv-mlir",
    "sv",
    "sv-provenance-report",
    "il",
    "yosys-stat",
}


def load_registration(model_key: str) -> dict[str, object]:
    result = subprocess.run(
        ["nix", "build", "--no-link", "--print-out-paths", ".#model-registry"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    registry = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
    return registry[model_key]


def load_exact_export_command() -> str:
    result = subprocess.run(
        ["nix", "derivation", "show", f".#{MODEL_KEY}-pytorch-exported"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    derivations = json.loads(result.stdout)["derivations"]
    matching = [
        derivation for derivation in derivations.values()
        if isinstance(derivation, dict)
        and isinstance(derivation.get("env"), dict)
        and derivation["env"].get("name") == f"{MODEL_KEY}-pytorch-exported"
    ]
    if len(matching) != 1:
        raise AssertionError(f"expected one exact export derivation, found {len(matching)}")
    return matching[0]["env"]["buildCommand"]


class TinyStories1mExactPipelineRegistrationTest(unittest.TestCase):
    def test_exact_adapter_loads_through_the_export_materializer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "--adapter",
                    str(EXACT_ADAPTER),
                    "--contract",
                    "missing-contract.json",
                    "--package",
                    "missing-package",
                    "--model-path",
                    "missing-model",
                    "--out-dir",
                    "out",
                ],
                cwd=temporary_directory,
                text=True,
                capture_output=True,
            )
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertNotIn("No module named 'TinyStories'", result.stderr)
        self.assertNotIn("adapter does not expose export_program_with_package", result.stderr)

    def test_exact_model_uses_existing_pipeline_and_canonical_package(self) -> None:
        # This fails if the registration is omitted, changes pipeline stages, or
        # drifts away from the Task 1 package identity.
        registration = load_registration(MODEL_KEY)
        self.assertEqual(registration["source"]["backend_overrides"], [])
        self.assertEqual(
            registration["source"]["package_manifest_sha256"],
            EXPECTED_MANIFEST_SHA256,
        )
        for name, expected in EXPECTED_IDENTITIES.items():
            self.assertEqual(registration["source"][name], expected)
        self.assertEqual(set(registration["packages"]), EXPECTED_STAGES)

    def test_exact_export_command_uses_pinned_store_package_and_valid_cli_contract(self) -> None:
        command = load_exact_export_command()
        self.assertNotIn("/home/", command)
        self.assertIn("model_packages/tinystories-1m", command)
        self.assertIn("model_adapter_exact_package.py", command)
        self.assertIn(
            "2026-08-28-reference-guided-tinystories-1m-compiler-design.md",
            command,
        )
        materializer = command.split("materialize-pytorch-exported.py", 1)[1].split(
            '--out-dir "$out"', 1
        )[0]
        self.assertNotIn("--audit", materializer)
        provenance_write = command.split(" write", 1)[1]
        self.assertIn("--audit \"$audit\"", provenance_write)

    def test_materializer_rejects_the_provenance_only_audit_flag(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(MATERIALIZER),
                "--adapter",
                "adapter.py",
                "--out-dir",
                "out",
                "--audit",
                "audit.json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --audit audit.json", result.stderr)

    def test_kevgpt_input_is_pinned_and_package_is_not_an_impure_sandbox_path(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        lock = json.loads((ROOT / "flake.lock").read_text(encoding="utf-8"))
        kev = lock["nodes"]["kev-gpt-src"]
        self.assertNotIn("extra-sandbox-paths", flake)
        self.assertEqual(kev["locked"]["rev"], "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f")
        self.assertFalse(kev["flake"])


if __name__ == "__main__":
    unittest.main()
