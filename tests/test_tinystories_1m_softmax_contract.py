import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/inspect_tinystories_1m_softmax_contract.py"
spec = importlib.util.spec_from_file_location("softmax_contract", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TinyStoriesSoftmaxContractTests(unittest.TestCase):
    def test_reference_contract_is_content_bound_and_unaligned(self):
        report = module.build_report(module.DEFAULT_REFERENCE_ROOT)
        self.assertEqual(
            report["status"], "reference_contract_recovered_compiler_boundary_unaligned"
        )
        self.assertFalse(report["comparison"]["same_contract"])
        self.assertFalse(report["authority"]["functional_equivalence"])
        self.assertEqual(report["reference"]["contract"]["exponential"]["lut_entries"], 4096)
        self.assertEqual(report["reference"]["contract"]["score"]["post_shift"], 24)
        self.assertEqual(report["vectors"]["special_zero_delta"]["output_q1_20"], 1 << 20)
        self.assertGreater(report["compiler_boundary"]["boundary_report_sha256"].__len__(), 0)

    def test_known_source_hashes_are_rechecked(self):
        report = module.build_report(module.DEFAULT_REFERENCE_ROOT)
        for relative, record in report["reference"]["files"].items():
            path = module.DEFAULT_REFERENCE_ROOT / relative
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_missing_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            report = module.build_report(Path(directory))
        self.assertEqual(report["status"], "unsupported")
        self.assertIn("missing reference files", report["failure"])
        self.assertIsNone(report["reference"]["contract"])

    def test_report_artifact_matches_current_reference(self):
        artifact = ROOT / "artifacts/comparison/tinystories-1m-softmax-contract-diagnostic.json"
        data = json.loads(artifact.read_text(encoding="utf-8"))
        current = module.build_report(module.DEFAULT_REFERENCE_ROOT)
        self.assertEqual(data, current)


if __name__ == "__main__":
    unittest.main()
