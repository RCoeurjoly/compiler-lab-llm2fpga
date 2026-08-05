import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = REPO_ROOT / "scripts" / "pipeline" / "audit_rc_ddr3_compatibility.py"
MAPPING_PATH = REPO_ROOT / "scripts" / "pipeline" / "generate_rc_ddr3_mapping.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load(AUDIT_PATH, "audit_rc_ddr3_compatibility")
mapping = _load(MAPPING_PATH, "generate_rc_ddr3_mapping")
compat_tests = _load(REPO_ROOT / "tests" / "test_rc_ddr3_compatibility.py", "compat_fixture")


class RcDdr3MappingTest(unittest.TestCase):
    def setUp(self):
        self.abi = compat_tests._memory_abi()
        self.bindings = compat_tests._bindings(self.abi)
        self.compatibility = audit.audit_compatibility(self.abi, self.bindings)

    def test_mapping_contains_only_learned_tensors_with_aligned_byte_layout(self):
        receipt = mapping.generate_mapping(self.compatibility, self.bindings)
        self.assertEqual(receipt["schema"], "rc-ddr3-learned-tensor-mapping-v1")
        self.assertEqual(len(receipt["ports"]), 44)
        self.assertEqual([row["port"] for row in receipt["ports"]],
                         list(range(25)) + list(range(27, 46)))
        self.assertEqual(receipt["ports"][0]["logical_byte_address"], 0)
        self.assertEqual(receipt["ports"][0]["byte_length"], 16)
        self.assertEqual(receipt["ports"][1]["logical_byte_address"], 16)
        self.assertTrue(all(row["logical_byte_address"] % 16 == 0 for row in receipt["ports"]))
        self.assertEqual(receipt["ports"][-1]["source"], "calyx-memory-binding")
        self.assertEqual(receipt["local_port_exclusions"], [25, 26] + list(range(46, 146)))
        self.assertEqual(receipt["compatibility_sha256"], self.compatibility["sha256"])
        self.assertEqual(receipt["calyx_memory_bindings_sha256"], self.bindings["sha256"])

    def test_mapping_rejects_tampered_compatibility_receipt(self):
        self.compatibility["ports"][0]["classification"] = "local-output"
        with self.assertRaisesRegex(ValueError, "canonical JSON"):
            mapping.generate_mapping(self.compatibility, self.bindings)


if __name__ == "__main__":
    unittest.main()
