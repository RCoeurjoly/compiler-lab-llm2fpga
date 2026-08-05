import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pipeline" / "audit_rc_ddr3_compatibility.py"


def _load_module():
    return _load_module_from(SCRIPT_PATH, "audit_rc_ddr3_compatibility")


def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def _sha(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _memory_abi():
    rows = []
    for number in range(146):
        if number <= 24 or 27 <= number <= 45:
            kind, width, depth = "image", 32, 4
        elif number == 25:
            kind, width, depth = "token", 64, 8
        elif number == 26:
            kind, width, depth = "output", 8, 64
        else:
            kind, width, depth = "scratch", 8, 4
        rows.append({"number": number, "width": width, "depth": depth,
                     "kind": kind, "write_enable_sha256": "0" * 64})
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {"schema": "rc-sv-memory-abi-v1", "ports": rows,
            "canonical_json": canonical, "sha256": _sha(canonical)}


def _bindings(abi):
    rows = []
    for ordinal in range(19):
        words = [ordinal + 1] * 4
        raw = b"".join(word.to_bytes(4, "little") for word in words)
        rows.append({"port": 27 + ordinal, "ordinal": ordinal,
                     "global": f"tensor_{ordinal}", "source_shape": [4],
                     "lowered_shape": [4], "shape_transform": "identity",
                     "word_count": 4, "words_u32": words,
                     "raw_sha256": hashlib.sha256(raw).hexdigest(),
                     "image_segment_aliases": [f"state/tensor_{ordinal}"]})
    payload = {"schema": "rc-calyx-external-memory-bindings-v1",
               "flat_scf_sha256": "1" * 64, "pre_calyx_sha256": "2" * 64,
               "image_sha256": "3" * 64, "image_manifest_sha256": "4" * 64,
               "memory_abi_sha256": abi["sha256"], "ports": rows}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {**payload, "canonical_json": canonical, "sha256": _sha(canonical)}


class RcDdr3CompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.abi = _memory_abi()
        self.bindings = _bindings(self.abi)

    def test_audit_classifies_all_ports_and_emits_a_canonical_receipt(self):
        receipt = audit.audit_compatibility(self.abi, self.bindings)
        self.assertEqual(receipt["schema"], "rc-ddr3-compatibility-v1")
        self.assertEqual(receipt["memory_abi_sha256"], self.abi["sha256"])
        self.assertEqual(receipt["calyx_memory_bindings_sha256"], self.bindings["sha256"])
        self.assertEqual(len(receipt["ports"]), 146)
        self.assertEqual([row["port"] for row in receipt["ports"]], list(range(146)))
        self.assertEqual([row["port"] for row in receipt["learned_tensor_ports"]],
                         list(range(25)) + list(range(27, 46)))
        self.assertEqual(receipt["ports"][25]["classification"], "local-token-input")
        self.assertEqual(receipt["ports"][26]["classification"], "local-output")
        self.assertEqual(receipt["ports"][46]["classification"], "local-mutable-scratch")
        self.assertEqual(receipt["wishbone"], {"address_unit_bytes": 16,
                                                "data_width_bits": 128,
                                                "max_outstanding": 1,
                                                "read_only": True,
                                                "response": "ack-after-accepted-read",
                                                "write_supported": False})
        self.assertEqual(receipt["sha256"], _sha(receipt["canonical_json"]))

    def test_audit_rejects_receipts_with_stale_cross_hashes(self):
        stale = copy.deepcopy(self.bindings)
        stale["memory_abi_sha256"] = "f" * 64
        payload = {key: value for key, value in stale.items() if key not in ("canonical_json", "sha256")}
        stale["canonical_json"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        stale["sha256"] = _sha(stale["canonical_json"])
        with self.assertRaisesRegex(ValueError, "does not bind"):
            audit.audit_compatibility(self.abi, stale)

    def test_audit_rejects_noncanonical_or_changed_port_contract(self):
        changed = copy.deepcopy(self.abi)
        changed["ports"][0]["width"] = 24
        with self.assertRaisesRegex(ValueError, "canonical JSON"):
            audit.audit_compatibility(changed, self.bindings)

    def test_audit_rejects_a_byte_incompatible_learned_tensor_width(self):
        changed = copy.deepcopy(self.abi)
        changed["ports"][0]["width"] = 7
        canonical = json.dumps(changed["ports"], sort_keys=True, separators=(",", ":"))
        changed["canonical_json"] = canonical
        changed["sha256"] = _sha(canonical)
        bindings = copy.deepcopy(self.bindings)
        bindings["memory_abi_sha256"] = changed["sha256"]
        payload = {key: value for key, value in bindings.items() if key not in ("canonical_json", "sha256")}
        bindings["canonical_json"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        bindings["sha256"] = _sha(bindings["canonical_json"])
        with self.assertRaisesRegex(ValueError, "128-bit DDR3"):
            audit.audit_compatibility(changed, bindings)

    def test_cli_writes_deterministic_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "memory-abi.json").write_text(json.dumps(self.abi))
            (root / "calyx-memory-bindings.json").write_text(json.dumps(self.bindings))
            out = root / "ddr3-compatibility.json"
            audit.main(["--memory-abi", str(root / "memory-abi.json"),
                        "--calyx-memory-bindings", str(root / "calyx-memory-bindings.json"),
                        "--out", str(out)])
            self.assertEqual(out.read_text(), audit.render_receipt(
                audit.audit_compatibility(self.abi, self.bindings)))

    def test_audit_invokes_task_one_source_closure_validator(self):
        closure_path = REPO_ROOT / "scripts" / "pipeline" / "materialize_ddr3_source_closure.py"
        closure = _load_module_from(closure_path, "ddr3_source_closure")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for logical_path in closure.SOURCE_PATHS:
                path = root / logical_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(logical_path)
            manifest = closure.build_manifest(root)
            receipt = audit.audit_compatibility(self.abi, self.bindings, manifest, root)
            self.assertIn("ddr3_source_closure_sha256", receipt)
            (root / closure.SOURCE_PATHS[0]).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "Task 1 validation"):
                audit.audit_compatibility(self.abi, self.bindings, manifest, root)


if __name__ == "__main__":
    unittest.main()
