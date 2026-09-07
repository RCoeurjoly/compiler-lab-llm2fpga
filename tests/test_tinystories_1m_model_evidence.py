"""Mutation-oriented checks of the saved-run audit, without rerunning RTL."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_audit():
    path = ROOT / "scripts/pipeline/audit_fixed_point_model_evidence.py"
    if not path.exists():
        raise AssertionError("missing independent saved-run evidence audit")
    spec = importlib.util.spec_from_file_location("model_evidence_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SavedTranscriptTests(unittest.TestCase):
    def test_missing_default_preload_warning_is_rejected(self):
        audit = load_audit()
        self.assertTrue(hasattr(audit, "verify_meminit_warnings"), "missing default-preload exclusion audit")
        futil = "@external source = seq_mem_d1(64, 4, 2);\n@external computed = seq_mem_d1(64, 4, 2);"
        warnings = ["DATA (path to meminit files): ", "%Warning: /source.dat:0: $readmem file not found", "%Warning: /computed.dat:0: $readmem file not found"]
        audit.verify_meminit_warnings(warnings, futil)
        for changed in (warnings[:-1], warnings + [warnings[-1]], warnings[1:]):
            with self.assertRaises(ValueError):
                audit.verify_meminit_warnings(changed, futil)

    def test_saved_evidence_rejects_rehashed_resource_and_claim_tampering(self):
        audit = load_audit()
        self.assertTrue(hasattr(audit, "validate_evidence"), "missing receipt revalidation")
        evidence = json.loads((ROOT / "artifacts/reference/tinystories-1m-model-same-futil-evidence.json").read_text())
        audit.validate_evidence(evidence, verify_artifacts=False)
        for mutation in ("resource", "fit", "events", "self_hash"):
            changed = copy.deepcopy(evidence)
            if mutation == "resource":
                changed["resources"]["memory_bits"] += 1
            elif mutation == "fit":
                changed["claims"]["board_fit"] = True
            elif mutation == "events":
                changed["saved_execution"]["events"].pop()
            else:
                changed["artifact_sha256"] = "0" * 64
            if mutation != "self_hash":
                changed["artifact_sha256"] = audit.canonical({k: v for k, v in changed.items() if k != "artifact_sha256"})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.validate_evidence(changed, verify_artifacts=False)

    def test_resource_parser_uses_exact_json_memory_bits(self):
        audit = load_audit()
        stats = {"modules": {"\\main": {}}, "design": {"num_cells": 14066, "num_memories": 104, "num_memory_bits": 138494624, "num_processes": 852}}
        self.assertEqual(audit.parse_resources(stats), {"cells": 14066, "memories": 104, "memory_bits": 138494624, "processes": 852})
        for field in ("num_cells", "num_memories", "num_memory_bits", "num_processes"):
            changed = copy.deepcopy(stats)
            changed["design"][field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.parse_resources(changed)

    def setUp(self):
        self.audit = load_audit()
        self.oracle = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json").read_text())
        # Independent miniature transcript: exact model boundary names and
        # contexts, but synthetic cycle numbers; no files or simulator needed.
        self.events = []
        names = ["embedding.token", "embedding.position", "embedding.sum", *[f"block.{i}" for i in range(8)], "final_ln", "lm_head.full_context_logits", "lm_head.last_logits"]
        for run in range(2):
            self.events.append(dict(event="isolation", run=run, reset=True, idle=True, invalid=True))
            for step in range(2):
                for index, name in enumerate(names):
                    self.events.append(dict(event="boundary", run=run, step=step, boundary=name, file=f"{run}-{step}-{name}.bin", cycles=100 * step + index + 1))
                self.events.append(dict(event="selected", run=run, step=step, token=[11, 612][step], context=[7454, 2402, 257, 640, 11, 612][:5 + step], cycles=100 * step + 20))
            self.events.append(dict(event="complete", run=run, cycles=121))

    def test_accepts_both_complete_ordered_runs(self):
        result = self.audit.validate_transcript(self.events, self.oracle)
        self.assertEqual(result["boundary_count"], 56)
        self.assertEqual(result["cycles"], [121, 121])
        self.assertEqual(result["selected_tokens"], [[11, 612], [11, 612]])

    def test_rejects_missing_duplicate_unknown_and_reordered_events(self):
        for mutation in ("missing", "duplicate", "unknown", "reordered"):
            events = copy.deepcopy(self.events)
            if mutation == "missing":
                events.pop(35)
            elif mutation == "duplicate":
                events.insert(35, events[35])
            elif mutation == "unknown":
                events[35]["event"] = "host_injection"
            else:
                events[35], events[36] = events[36], events[35]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.audit.validate_transcript(events, self.oracle)

    def test_rejects_second_run_context_and_snapshot_alias(self):
        for mutation in ("context", "file", "run", "isolation", "extra_field"):
            events = copy.deepcopy(self.events)
            if mutation == "context":
                events[47]["context"][-1] = 612
            elif mutation == "file":
                events[33]["file"] = events[1]["file"]
            elif mutation == "run":
                events[33]["run"] = 0
            elif mutation == "isolation":
                events[32]["reset"] = False
            else:
                events[33]["host_hidden"] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.audit.validate_transcript(events, self.oracle)

    def test_rejects_backward_noninteger_and_nondeterministic_cycles(self):
        for value in (0, True, 1.5, 999):
            events = copy.deepcopy(self.events)
            events[34]["cycles"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.audit.validate_transcript(events, self.oracle)
        events = copy.deepcopy(self.events)
        events[-1]["cycles"] += 1
        with self.assertRaises(ValueError):
            self.audit.validate_transcript(events, self.oracle)

    def test_rejects_tampered_second_run_snapshot(self):
        import hashlib
        import struct
        import tempfile
        raw = struct.pack("<qq", -7, 12)
        record = {"bytes": 16, "shape": [1, 2], "dtype": "int64", "little_endian_int64_sha256": hashlib.sha256(raw).hexdigest(), "sha256": hashlib.sha256(b'{"dtype":"int64","shape":[1,2],"values":[[-7,12]]}').hexdigest()}
        event = dict(event="boundary", run=1, step=0, boundary="embedding.sum", file="1-0-embedding.sum.bin", cycles=12)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / event["file"]
            path.write_bytes(raw)
            observed = self.audit.verify_snapshot(event, Path(tmp), record)
            self.assertEqual(observed["run"], 1)
            path.write_bytes(struct.pack("<qq", -7, 13))
            with self.assertRaisesRegex(ValueError, "run=1 step=0 boundary=embedding.sum"):
                self.audit.verify_snapshot(event, Path(tmp), record)


if __name__ == "__main__":
    unittest.main()
