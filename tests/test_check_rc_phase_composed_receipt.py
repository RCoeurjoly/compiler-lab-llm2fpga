"""Fail-closed acceptance for the retained RC simulation diagnostic."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.check_rc_phase_composed_receipt import verify_simulation_output


def fixture(root: Path) -> None:
    report = {
        "schema": "rc-phase-composed-sv-equivalence-v1",
        "status": "pass", "compile_returncode": 0, "simulation_returncode": 0,
        "expected_tokens": [0, 0, 4], "actual_tokens": [0, 0, 4],
        "readback_word_count": 237, "actual_readback_word_count": 237,
        "mismatch_count": 0, "first_mismatch": None, "handoff_checked_words": 136,
    }
    (root / "report.json").write_text(json.dumps(report))
    (root / "runner-exit-code").write_text("0\n")
    (root / "readback.hex").write_text("".join(
        f"{address} {([0, 0, 4][[0, 71, 150].index(address)] if address in (0, 71, 150) else 0):016x}\n"
        for address in range(237)
    ))


class AcceptanceTests(unittest.TestCase):
    def test_accepts_exact_complete_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = verify_simulation_output(root)
            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["tokens"], [0, 0, 4])
            self.assertEqual(result["readback_words"], 237)

    def test_rejects_failure_even_when_diagnostic_derivation_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            report = json.loads((root / "report.json").read_text())
            report["status"] = "mismatch"
            (root / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "status"):
                verify_simulation_output(root)

    def test_rejects_missing_or_reordered_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            lines = (root / "readback.hex").read_text().splitlines()
            (root / "readback.hex").write_text("\n".join(lines[1:] + lines[:1]) + "\n")
            with self.assertRaisesRegex(ValueError, "readback address"):
                verify_simulation_output(root)

    def test_rejects_nonzero_runner_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "runner-exit-code").write_text("1\n")
            with self.assertRaisesRegex(ValueError, "runner"):
                verify_simulation_output(root)

    def test_rejects_token_disagreement_with_raw_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            lines = (root / "readback.hex").read_text().splitlines()
            lines[150] = "150 0000000000000003"
            (root / "readback.hex").write_text("\n".join(lines) + "\n")
            with self.assertRaisesRegex(ValueError, "token readback"):
                verify_simulation_output(root)

    def test_rejects_missing_all_word_handoff_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            report = json.loads((root / "report.json").read_text())
            report["handoff_checked_words"] = 0
            (root / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "handoff"):
                verify_simulation_output(root)


if __name__ == "__main__":
    unittest.main()
