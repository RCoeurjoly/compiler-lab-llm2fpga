from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/exp_table"))
from generate_rc_exp_table import generate_table  # noqa: E402
from table_format import HEADER, decode_table  # noqa: E402


class ExpTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path("/tmp/rc-exp-table-test")
        self.tmp.mkdir(exist_ok=True)
        self.domain = self.tmp / "domain.json"
        self.domain.write_text(json.dumps({"sites": {"softmax": {
            "derived_pre_exp_finite_min": -0.0009765625,
            "derived_pre_exp_finite_max": 0.0,
            "boundary": {"scale": 2.0 ** -12}}}}))

    def test_deterministic_valid_table_and_header(self) -> None:
        a = self.tmp / "a.bin"; b = self.tmp / "b.bin"
        generate_table(self.domain, a, 4, "float32")
        generate_table(self.domain, b, 4, "float32")
        self.assertEqual(a.read_bytes(), b.read_bytes())
        spec = decode_table(a)
        self.assertEqual(spec.entry_count, 16)
        payload = a.read_bytes()[HEADER.size:]
        values = [struct.unpack("<f", payload[i:i + 4])[0] for i in range(0, len(payload), 4)]
        self.assertLess(values[0], values[-1])
        self.assertAlmostEqual(spec.input_max, 0.0)

    def test_receipt_contains_source_hash(self) -> None:
        out = self.tmp / "table.bin"
        result = generate_table(self.domain, out, 3, "float32")
        receipt = json.loads(Path(result["receipt"]).read_text())
        self.assertEqual(receipt["kind"], "rc-exp-table")
        self.assertEqual(receipt["table"]["entry_count"], 8)


if __name__ == "__main__":
    unittest.main()
