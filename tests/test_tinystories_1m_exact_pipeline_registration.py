import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_KEY = "tiny-stories-1m-kev-gpt-exact"
EXPECTED_MANIFEST_SHA256 = "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35"
EXPECTED_IDENTITIES = {
    "adapter_sha256": "ee2af98f4f2dfcae20dbe43432bc4bcf6e8ea9340308ec735bd2c1549c16b92c",
    "contract_sha256": "859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c",
    "task_1_audit_file_sha256": "3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd",
    "task_1_audit_payload_sha256": "7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766",
    "task_2_artifact_file_sha256": "3bc578d7f13263f438d8e7d3f4d3b80386afa89accb859da74d1a4404606eae7",
    "task_2_artifact_sha256": "8f74d35cc90d534fb385608c9cdf1f6f5bb0a5aad83eb6c34133e4b7b6f1e938",
    "task_2_model_receipt_sha256": "f061dbf4f91bf5389acb0f27ce4b9e672f6f3831478907e01900e60e8869235b",
    "task_3_generation_file_sha256": "b15fe696a21b8fa9ddf0ae17c6cc264c8cac0dbbdd51880b924452de5d388762",
    "task_3_generation_artifact_sha256": "2e4f35b2875127bff7d74bcdc404edd3afad1c8fc6693dca05cd7a1636b22b69",
    "task_3_generation_result_sha256": "3113e57cc016292804beb2e35e6443ca8fc7cd1439272abde0cb62edc1c77524",
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


class TinyStories1mExactPipelineRegistrationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
