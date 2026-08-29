import json, hashlib, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ABI = ROOT / "artifacts/comparison/tinystories-1m-softmax-external-rtl-abi-2026-08-29.json"
class ExternalRtlAbiTest(unittest.TestCase):
    def test_reference_module_matches_authenticated_abi(self):
        a = json.loads(ABI.read_text()); p = Path(a["reference_rtl"]["path"])
        self.assertTrue(p.is_file())
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), a["reference_rtl"]["sha256"])
        text = p.read_text()
        for port in ("in_q", "in_k", "in_v", "out_context", "out_index", "out_valid"):
            self.assertIn(port, text)
        self.assertEqual(a["parameters"]["NHEAD"], 16)
    def test_adapter_is_explicitly_not_claimed(self):
        a = json.loads(ABI.read_text()); self.assertFalse(a["claims"]["abi_adapter_implemented"]); self.assertFalse(a["claims"]["direct_adapter_valid"])
if __name__ == "__main__": unittest.main()
