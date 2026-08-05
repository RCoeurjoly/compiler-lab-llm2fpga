import importlib.util
import hashlib
import json
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
        pins = {"addr0": "output", "content_en": "output", "write_en": "output", "write_data": "output", "read_data": "input", "done": "input"}
        evidence = {"schema": "rc-sv-routing-evidence-v1", "source_sha256": "a" * 64, "memory_abi_sha256": self.abi["sha256"], "completion": {"max_outstanding": 1, "response": "one-done-per-accepted-request"}, "ports": [{"port": port, "pins": pins, "write_enable": "proven-zero" if port in audit.LEARNED_PORTS else "dynamic"} for port in range(146)]}
        evidence["canonical_json"] = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        evidence["sha256"] = hashlib.sha256(evidence["canonical_json"].encode()).hexdigest()
        self.compatibility = audit.audit_compatibility(self.abi, self.bindings, sv_evidence=evidence)
        self.image, self.manifest = self._image_evidence()
        self.manifest_bytes = json.dumps(self.manifest, sort_keys=True, separators=(",", ":")).encode()
        self.bindings["image_sha256"] = hashlib.sha256(self.image).hexdigest()
        self.bindings["image_manifest_sha256"] = hashlib.sha256(self.manifest_bytes).hexdigest()
        payload = {key: value for key, value in self.bindings.items() if key not in ("canonical_json", "sha256")}
        self.bindings["canonical_json"] = audit._canonical(payload)
        self.bindings["sha256"] = audit._sha(self.bindings["canonical_json"])
        evidence["memory_abi_sha256"] = self.abi["sha256"]
        evidence["canonical_json"] = json.dumps({key: value for key, value in evidence.items() if key not in ("canonical_json", "sha256")}, sort_keys=True, separators=(",", ":"))
        evidence["sha256"] = hashlib.sha256(evidence["canonical_json"].encode()).hexdigest()
        self.compatibility = audit.audit_compatibility(self.abi, self.bindings, sv_evidence=evidence)

    def _image_evidence(self):
        payload = bytearray()
        segments = []
        names = [f"state/_frozen_param{port}" for port in range(21)] + [
            "state/transformer.h.0.attn.attention.bias",
            "state/transformer.h.0.attn.attention.lifted_tensor_0",
            "state/transformer.h.1.attn.attention.bias",
            "state/transformer.h.1.attn.attention.lifted_tensor_1",
        ]
        for port, name in enumerate(names):
            offset = len(payload)
            raw = bytes([port + 1]) * 16
            payload.extend(raw)
            segments.append({"name": name, "offset": offset, "byte_length": len(raw),
                             "source_category": "state", "dtype": "float32", "shape": [4]})
        for row in self.bindings["ports"]:
            offset = len(payload)
            raw = b"".join(word.to_bytes(4, "little") for word in row["words_u32"])
            payload.extend(raw)
            row["image_segment_aliases"] = [f"state/tensor_{row['port']}"]
            segments.append({"name": row["image_segment_aliases"][0], "offset": offset,
                             "byte_length": len(raw), "source_category": "state",
                             "dtype": "float32", "shape": [4]})
        return bytes(payload), {"segments": segments}

    def test_mapping_contains_only_learned_tensors_with_aligned_byte_layout(self):
        receipt = mapping.generate_mapping(self.compatibility, self.bindings, self.image, self.manifest_bytes)
        self.assertEqual(receipt["schema"], "rc-ddr3-learned-tensor-mapping-v1")
        self.assertEqual(len(receipt["ports"]), 44)
        self.assertEqual([row["port"] for row in receipt["ports"]],
                         list(range(25)) + list(range(27, 46)))
        self.assertEqual(receipt["ports"][0]["logical_byte_address"], 0)
        self.assertEqual(receipt["ports"][0]["byte_length"], 16)
        self.assertEqual(receipt["ports"][1]["logical_byte_address"], 16)
        self.assertEqual(receipt["ports"][-1]["logical_byte_address"], 688)
        self.assertEqual(receipt["ports"][-1]["source"], "calyx-memory-binding")
        self.assertEqual(receipt["local_port_exclusions"], [25, 26] + list(range(46, 146)))
        self.assertEqual(receipt["compatibility_sha256"], self.compatibility["sha256"])
        self.assertEqual(receipt["calyx_memory_bindings_sha256"], self.bindings["sha256"])

    def test_mapping_rejects_tampered_compatibility_receipt(self):
        self.compatibility["ports"][0]["classification"] = "local-output"
        with self.assertRaisesRegex(ValueError, "canonical JSON"):
            mapping.generate_mapping(self.compatibility, self.bindings, self.image, self.manifest_bytes)

    def test_mapping_rejects_image_evidence_that_does_not_match_the_binding_receipt(self):
        with self.assertRaisesRegex(ValueError, "image SHA-256"):
            mapping.generate_mapping(self.compatibility, self.bindings, self.image + b"x", self.manifest_bytes)

    def test_mapping_rejects_tampered_source_manifest_offsets(self):
        tampered = json.loads(self.manifest_bytes)
        tampered["segments"][1]["offset"] = 0
        with self.assertRaisesRegex(ValueError, "manifest SHA-256"):
            mapping.generate_mapping(self.compatibility, self.bindings, self.image,
                                     json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode())

    def test_mapping_rejects_rehashed_learned_port_metadata_that_disagrees_with_source_dtype(self):
        self.compatibility["ports"][0]["width_bits"] = 16
        self.compatibility["ports"][0]["depth_words"] = 8
        self.compatibility["learned_tensor_ports"] = [
            row for row in self.compatibility["ports"]
            if row["classification"] == "ddr3-learned-tensor"
        ]
        payload = {key: value for key, value in self.compatibility.items()
                   if key not in ("canonical_json", "sha256")}
        self.compatibility["canonical_json"] = mapping._canonical(payload)
        self.compatibility["sha256"] = mapping._sha(self.compatibility["canonical_json"])
        with self.assertRaisesRegex(ValueError, "authoritative source-image dtype"):
            mapping.generate_mapping(self.compatibility, self.bindings, self.image, self.manifest_bytes)


if __name__ == "__main__":
    unittest.main()
