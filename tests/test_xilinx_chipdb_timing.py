import importlib.util
from pathlib import Path
import struct
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/pipeline/check_xilinx_chipdb_timing.py"
spec = importlib.util.spec_from_file_location("chipdb_timing", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChipdbTimingTest(unittest.TestCase):
    def fixture(self, count):
        data = bytearray(256)
        for offset, value in ((0, 8), (32, 40), (40, 1), (80, 1),
                              (84, 11), (128, count), (132, 127), (136, 259)):
            struct.pack_into("<i", data, offset, value)
        data[192:204] = b"xc7k480t-test"
        return data

    def test_empty_cell_table_is_rejected(self):
        report = module.inspect(self.fixture(0))
        self.assertEqual(report["status"], "missing_cell_timing")
        self.assertEqual(report["device"], "xc7k480t-test")
        self.assertEqual(report["wire_timing_classes"], 127)

    def test_nonempty_table_is_not_timing_closure(self):
        report = module.inspect(self.fixture(4))
        self.assertEqual(report["timed_tile_types"], 4)
        self.assertFalse(report["timing_closure_verified"])

    def test_invalid_pointer_rejected(self):
        data = self.fixture(1)
        struct.pack_into("<i", data, 0, -100)
        with self.assertRaisesRegex(ValueError, "outside file"):
            module.inspect(data)


if __name__ == "__main__":
    unittest.main()
