import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "artifacts/reference/tinystories-1m-export-provenance.json"


class ExactExportProvenanceManifestTest(unittest.TestCase):
    def test_manifest_is_canonical_and_complete(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "tinystories-1m-export-provenance-v1")
        expected = data["expected"]
        for key in (
            "contract", "audit_file", "audit_payload", "package_manifest",
            "package_receipt", "task_2_file", "task_2_artifact",
            "task_2_receipt", "task_3_file", "task_3_artifact", "task_3_result",
        ):
            self.assertRegex(expected[key], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
