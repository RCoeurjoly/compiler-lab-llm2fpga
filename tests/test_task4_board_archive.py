"""The Task 4 evidence checker must validate observed JTAG data, not a passed flag."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "artifacts/task4/full16-board-2026-09-29"
ORACLE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-continuation-oracle.json"
CHECKER = ROOT / "scripts/pipeline/verify_task4_board_archive.py"


class Task4BoardArchiveTest(unittest.TestCase):
    def run_checker(self, archive: Path, directory: Path) -> subprocess.CompletedProcess[str]:
        configuration = directory / "configuration.json"
        configuration.write_text(json.dumps({
            "status": "source-rebuilt-accepted-task6-configuration",
            "archived_bitstream_sha256": "bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f",
            "frames_sha256": "c78a1ab40fea57c214194b95d989fa5ba5e4a32dbef1ea7a5a1595bde6931617",
            "decoded_bits_sha256": "2c3b88fc99f69e1914388e14ec3bcb5fcd5359e9c2d35c7e9ea81b88fe31cceb",
        }))
        return subprocess.run(
            [sys.executable, "-B", str(CHECKER), str(archive), str(ORACLE),
             str(configuration), str(directory / "verification.json")],
            cwd=ROOT, capture_output=True, text=True,
        )

    def test_authentic_archived_transactions_and_programming_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = self.run_checker(ARCHIVE, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            verified = json.loads((directory / "verification.json").read_text())
            self.assertEqual(verified["tokens"], [
                11, 612, 373, 257, 1310, 2576, 3706, 20037,
                13, 1375, 6151, 284, 711, 2354, 287, 262,
            ])
            self.assertEqual(verified["independently_programmed_sram_runs"], 3)

    def test_altered_raw_token_capture_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            altered = directory / "altered"
            shutil.copytree(ARCHIVE, altered)
            receipt_path = altered / "hardware/receipt.json"
            receipt = json.loads(receipt_path.read_text())
            transactions = receipt["runs"][0]["transactions"]
            first_read = next(index for index, item in enumerate(transactions)
                              if int(item["command"], 16) == 0x4000000000000000)
            transactions[first_read + 1]["captured"] = "000000000000000c"
            receipt_path.chmod(0o644)
            receipt_path.write_text(json.dumps(receipt))
            result = self.run_checker(altered, directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("token", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
