import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts.pipeline.run_rc_serving_w4a8_integrated_sv import (
    classify_process_result,
    compare_composed_readback,
    run_composed,
    run_bounded_command,
    normalize_composed_sources,
)


class ComposedReadbackTests(unittest.TestCase):
    def test_first_cache_word_mismatch_reports_phase_port_word_and_bit(self):
        manifest = {
            "readback_words": 4,
            "phases": [{"name": "prefill-8", "token_address": 0,
                        "logits": {"port": 32, "offset": 42, "words": 1},
                        "cache_outputs": [{"leaf": 0, "port": 33,
                                           "readback_address": 2, "words": 2}]}],
        }
        observation = {"phases": [{"name": "prefill-8", "token": 2,
                                   "logits": [1.0],
                                   "cache_leaves": [{"little_endian_hex": "000000800000803f"}]}]}
        actual = {0: 2, 1: 0x3F800000, 2: 0x80000000, 3: 0x3F800001}
        result = compare_composed_readback(manifest, observation, actual, [2])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["first_mismatch"], {
            "address": 3, "phase": "prefill-8", "port": 33, "word": 1,
            "expected": "0x3f800000", "actual": "0x3f800001", "first_differing_bit": 0,
        })

    def test_exact_readback_and_token_outputs_pass(self):
        manifest = {"readback_words": 2, "phases": [{"name": "prefill-8", "token_address": 0,
                    "logits": {"port": 32, "offset": 42, "words": 1}, "cache_outputs": []}]}
        observation = {"phases": [{"name": "prefill-8", "token": 2,
                                   "logits": [-1.0], "cache_leaves": []}]}
        result = compare_composed_readback(manifest, observation,
                                           {0: 2, 1: 0xBF800000}, [2])
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["first_mismatch"])

    def test_timeout_signal9_and_semantic_mismatch_are_distinct(self):
        self.assertEqual(classify_process_result("compile", timed_out=True, returncode=None), "compile_timeout")
        self.assertEqual(classify_process_result("compile", timed_out=False, returncode=-9), "compile_signal9")
        self.assertEqual(classify_process_result("simulation", timed_out=False, returncode=137), "simulation_signal9")
        self.assertEqual(classify_process_result("simulation", timed_out=False, returncode=1), "simulation_failure")

    def test_compile_signal9_keeps_a_diagnostic_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            shell = package / "rc_phase_composed.sv"
            shell.write_text("module rc_phase_composed; endmodule\n")
            phase = package / "phase.sv"
            phase.write_text("module generated_phase; endmodule\n")
            manifest = {"readback_words": 2, "phases": []}
            manifest_path = root / "handoff.json"
            manifest_path.write_text(json.dumps(manifest))
            observation_path = root / "observation.json"
            observation_path.write_text(json.dumps({"phases": []}))
            receipt = {
                "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                "files": {shell.name: hashlib.sha256(shell.read_bytes()).hexdigest(),
                          str(phase): hashlib.sha256(phase.read_bytes()).hexdigest()},
                "sources": [str(phase)],
            }
            (package / "receipt.json").write_text(json.dumps(receipt))
            fake = root / "fake-verilator"
            fake.write_text("#!/bin/sh\nexit 137\n")
            fake.chmod(0o755)
            work = root / "work"
            report = run_composed(package, manifest_path, observation_path, work,
                                  verilator=str(fake), compile_timeout_seconds=10)
            self.assertEqual(report["status"], "compile_signal9")
            self.assertEqual(json.loads((work / "report.json").read_text())["status"], "compile_signal9")

    def test_timeout_kills_compiler_child_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "child-survived"
            command = ["sh", "-c", f"(sleep 1; touch {marker}) & wait"]
            with (root / "compile.log").open("w") as log:
                timed_out, _ = run_bounded_command(command, cwd=root, log=log,
                                                   timeout_seconds=0.2, max_memory_gib=1)
            self.assertTrue(timed_out)
            time.sleep(1.1)
            self.assertFalse(marker.exists(), "a compiler child survived the timeout")

    def test_normalizes_generated_phase_only_after_preserving_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "generated.sv"
            terms = [f"state == 13'd{i}" for i in range(3000)]
            raw = "module main_1; logic fsm0_write_en; assign fsm0_write_en = " + " | ".join(terms) + "; endmodule\n"
            original.write_text(raw)
            normalized = normalize_composed_sources([original], root / "simulation")
            self.assertEqual(original.read_text(), raw)
            self.assertEqual(len(normalized), 1)
            self.assertLess(max(map(len, normalized[0].read_text().splitlines())), 40_000)


if __name__ == "__main__":
    unittest.main()
