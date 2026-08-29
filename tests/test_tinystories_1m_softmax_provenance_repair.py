import importlib.util, json, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("repair", ROOT / "scripts/comparison/repair_tinystories_1m_softmax_provenance.py")
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
class ProvenanceRepairTest(unittest.TestCase):
    def test_repair_adds_current_graph_binding_and_reseals(self):
        source = json.loads((ROOT / "artifacts/comparison/tinystories-1m-softmax-provenance.json").read_text())
        result = mod.repair(source)
        self.assertEqual(result["layer_count"], 8); self.assertEqual(result["heads_per_layer"], 16)
        self.assertEqual(result["constants"]["zero_f32"]["lowered_identities"]["flat_scf"], "%cst_6")
        self.assertEqual(result["sha256"], mod.canonical({k:v for k,v in result.items() if k != "sha256"}))
    def test_repair_preserves_authenticated_package_and_stages(self):
        source = json.loads((ROOT / "artifacts/comparison/tinystories-1m-softmax-provenance.json").read_text())
        result = mod.repair(source)
        self.assertEqual(result["package"], source["package"]); self.assertEqual(result["lowering_stages"], source["lowering_stages"])
        self.assertEqual(result["heads"], source["heads"])
if __name__ == "__main__": unittest.main()
