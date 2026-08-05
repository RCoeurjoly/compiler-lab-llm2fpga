from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/exp_table"))
from table_to_hex import convert  # noqa: E402


class TableHexTests(unittest.TestCase):
    def test_hex_has_one_word_per_entry(self) -> None:
        out = Path("/tmp/rc-exp-table-test/table.hex")
        convert(ROOT / "artifacts/rc_exp_table.bin", out)
        lines = out.read_text().splitlines()
        self.assertEqual(len(lines), 256)
        self.assertTrue(all(len(line) == 8 for line in lines))


if __name__ == "__main__":
    unittest.main()
