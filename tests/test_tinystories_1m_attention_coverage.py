import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("coverage", ROOT / "scripts/comparison/audit_tinystories_1m_attention_coverage.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AttentionCoverageTest(unittest.TestCase):
    def test_exp_sites_are_layers_and_each_covers_sixteen_heads(self):
        graph = "\n".join(["scf.for %h = %c0 to %c16 step %c1 {", " scf.for %q = %c0 to %c4 step %c1 {", "  scf.for %k = %c0 to %c4 step %c1 {", "   %x = math.exp %d : f32", "  }", " }", "}"] * 8)
        report = MODULE.audit(graph)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["exp_site_count"], 8)
        self.assertEqual(report["attention_exp_site_count"], 8)
        self.assertEqual(report["head_count"], 16)
        self.assertTrue(report["claims"]["all_heads_covered"])
        self.assertFalse(report["claims"]["head_count_equals_exp_site_count"])

    def test_missing_sixteen_head_loop_fails_closed(self):
        report = MODULE.audit("scf.for %h = %c0 to %c8 step %c1 {\n %x = math.exp %d : f32\n}\n" * 8)
        self.assertEqual(report["status"], "fail")

    def test_layernorm_exp_is_not_attention(self):
        graph = "\n".join(["scf.for %h = %c0 to %c16 step %c1 {", " %x = math.exp %d : f32", "}"] * 8)
        report = MODULE.audit(graph)
        self.assertEqual(report["attention_exp_site_count"], 0)
        self.assertEqual(report["layernorm_exp_site_count"], 8)
        self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
