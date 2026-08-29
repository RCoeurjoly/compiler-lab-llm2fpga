import importlib.util, json, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("replay", ROOT / "scripts/comparison/verify_tinystories_1m_fixed_softmax_replay.py")
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
class FixedSoftmaxReplayTest(unittest.TestCase):
    def test_authenticated_rows_replay_exactly(self):
        ref = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json").read_text())
        result = mod.replay(ref)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["rows_checked"], 16)
    def test_tampered_score_is_rejected(self):
        ref = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json").read_text())
        ref["softmax_rows"][0]["score_codes_q8_8"][0] += 1
        self.assertEqual(mod.replay(ref)["status"], "fail")
