"""Exercise first-divergence reporting and rejection of incomplete traces."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analysis/compare_memory_traces.py"
GOOD = "Q 0 0000000c\nR 0 0000000c 00112233445566778899aabbccddeeff\n"


class CompareMemoryTracesTest(unittest.TestCase):
    def compare(self, reference, candidate):
        with tempfile.TemporaryDirectory() as directory:
            ref, got = Path(directory) / "reference", Path(directory) / "candidate"
            ref.write_text(reference)
            got.write_text(candidate)
            result = subprocess.run([sys.executable, str(SCRIPT), str(ref), str(got)],
                                    capture_output=True, text=True, timeout=10)
            self.assertTrue(result.stdout, result.stderr)
            return result.returncode, json.loads(result.stdout)

    def test_complete_identical_trace(self):
        code, report = self.compare(GOOD, GOOD)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "match")
        self.assertEqual(report["transactions"], 1)

    def test_first_response_data_divergence(self):
        code, report = self.compare(GOOD, GOOD.replace("ddeeff", "ddeefe"))
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "mismatch")
        self.assertEqual(report["line"], 2)
        self.assertEqual(report["boundary"], "response")

    def test_first_request_address_divergence(self):
        code, report = self.compare(GOOD, GOOD.replace("0000000c", "0000000d"))
        self.assertEqual(code, 1)
        self.assertEqual(report["line"], 1)
        self.assertEqual(report["boundary"], "request")

    def test_empty_and_incomplete_identical_traces_are_not_success(self):
        for trace in ("", "Q 0 0000000c\n", GOOD.replace("R 0", "R 1"),
                      GOOD.replace("R 0 0000000c", "R 0 0000000d")):
            with self.subTest(trace=trace):
                code, report = self.compare(trace, trace)
                self.assertEqual(code, 2)
                self.assertEqual(report["status"], "invalid")

    def test_shorter_complete_trace_is_not_match(self):
        second = GOOD.replace("Q 0", "Q 1").replace("R 0", "R 1")
        code, report = self.compare(GOOD + second, GOOD)
        self.assertEqual(code, 1)
        self.assertEqual(report["line"], 3)


if __name__ == "__main__":
    unittest.main()
