import tempfile
import unittest
from pathlib import Path

from TinyStories import rc_serving_direct_export as direct


class RcServingDirectExportTest(unittest.TestCase):
    def test_bundle_manifest_requires_three_named_phase_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("prefill-8", "decode-8", "decode-9"):
                (root / name).mkdir()
            manifest = direct.bundle_manifest(
                root,
                {
                    "prefill-8": "a" * 64,
                    "decode-8": "b" * 64,
                    "decode-9": "c" * 64,
                },
            )
            self.assertEqual(
                [phase["name"] for phase in manifest["phases"]],
                ["prefill-8", "decode-8", "decode-9"],
            )
            self.assertEqual(
                manifest["artifact_kind"], "direct-native-cache-export-bundle"
            )
            self.assertEqual(manifest["numeric_format"], "native-fp32-source")
            self.assertEqual(manifest["quantization_status"], "unproven")

    def test_materializer_is_not_the_generic_single_program_materializer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (
            root
            / "scripts"
            / "pipeline"
            / "materialize_rc_serving_direct_exports.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("materialize-pytorch-exported.py", source)
        self.assertIn("prefill-8", source)
        self.assertIn("decode-8", source)
        self.assertIn("decode-9", source)


if __name__ == "__main__":
    unittest.main()
